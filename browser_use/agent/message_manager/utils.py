from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import anyio
from langchain_core.messages import (
	AIMessage,
	BaseMessage,
	HumanMessage,
	SystemMessage,
	ToolMessage,
)

logger = logging.getLogger(__name__)

MODELS_WITHOUT_TOOL_SUPPORT_PATTERNS = [
	'deepseek-reasoner',
	'deepseek-r1',
	'.*gemma.*-it',
]


def is_model_without_tool_support(model_name: str) -> bool:
	return any(re.match(pattern, model_name) for pattern in MODELS_WITHOUT_TOOL_SUPPORT_PATTERNS)


def extract_json_from_model_output(content: str | BaseMessage) -> dict:
	"""Extract JSON from model output, handling both plain JSON and code-block-wrapped JSON."""
	try:
		# Extract string content from BaseMessage if needed
		content_str: str
		if isinstance(content, BaseMessage):
			# for langchain_core.messages.BaseMessage
			msg_content = content.content
			if isinstance(msg_content, list):
				## add by river	
				content_str = ''
				for content_block in msg_content:
					if isinstance(content_block, dict) and 'type' in content_block and content_block['type'] == 'text':
						content_str = content_block['text']
						break
			else:
				content_str = msg_content
		else:
			content_str = content
		# If content is wrapped in code blocks, extract just the JSON part
		if '```' in content_str:
			# Find the JSON content between code blocks
			content_str = content_str.split('```')[1]
			# Remove language identifier if present (e.g., 'json\n')
			if '\n' in content_str:
				content_str = content_str.split('\n', 1)[1]

		# remove html-like tags before the first { and after the last }
		# This handles cases like <|header_start|>assistant<|header_end|> and <function=AgentOutput>
		# Only remove content before { if content doesn't already start with {
		if not content_str.strip().startswith('{'):
			content_str = re.sub(r'^.*?(?=\{)', '', content_str, flags=re.DOTALL)

		# Remove common HTML-like tags and patterns at the end, but be more conservative
		# Look for patterns like </function>, <|header_start|>, etc. after the JSON
		content_str = re.sub(r'\}(\s*<[^>]*>.*?$)', '}', content_str, flags=re.DOTALL)
		content_str = re.sub(r'\}(\s*<\|[^|]*\|>.*?$)', '}', content_str, flags=re.DOTALL)

		# Handle extra characters after the JSON, including stray braces
		# Find the position of the last } that would close the main JSON object
		content_str = content_str.strip()

		if content_str.endswith('}'):
			# Try to parse and see if we get valid JSON
			try:
				json.loads(content_str)
			except json.JSONDecodeError:
				# If parsing fails, try to find the correct end of the JSON
				# by counting braces and removing anything after the balanced JSON
				brace_count = 0
				last_valid_pos = -1
				for i, char in enumerate(content_str):
					if char == '{':
						brace_count += 1
					elif char == '}':
						brace_count -= 1
						if brace_count == 0:
							last_valid_pos = i + 1
							break

				if last_valid_pos > 0:
					content_str = content_str[:last_valid_pos]

		# Fix control characters in JSON strings before parsing
		# This handles cases where literal control characters appear in JSON values
		content_str = _fix_control_characters_in_json(content_str)

		# Parse the cleaned content
		result_dict = json.loads(content_str)

		# if the key "function" and parameter key like "params"/"args"/"kwargs"/"parameters" are present, the final result is the value of the parameter key
		if 'function' in result_dict:
			params = result_dict.get(
				'params', result_dict.get('args', result_dict.get('kwargs', result_dict.get('parameters', {})))
			)
			if params:
				result_dict = params
		# some models occasionally respond with a list containing one dict: https://github.com/browser-use/browser-use/issues/1458
		if isinstance(result_dict, list) and len(result_dict) == 1 and isinstance(result_dict[0], dict):
			result_dict = result_dict[0]

		assert isinstance(result_dict, dict), f'Expected JSON dictionary in response, got JSON {type(result_dict)} instead'
		logger.debug(f'Successfully parsed model output: {result_dict}')
		return result_dict
	except json.JSONDecodeError as e:
		logger.warning(f'Failed to parse model output: {content} {str(e)}')
		raise ValueError(f'Could not parse response. {str(e)}')


def _fix_control_characters_in_json(content: str) -> str:
	"""Fix control characters in JSON string values to make them valid JSON."""
	try:
		# First try to parse as-is to see if it's already valid
		json.loads(content)
		return content
	except json.JSONDecodeError:
		pass

	# More sophisticated approach: only escape control characters inside string values
	# while preserving JSON structure formatting

	result = []
	i = 0
	in_string = False
	escaped = False

	while i < len(content):
		char = content[i]

		if not in_string:
			# Outside of string - check if we're entering a string
			if char == '"':
				in_string = True
			result.append(char)
		else:
			# Inside string - handle escaping and control characters
			if escaped:
				# Previous character was backslash, so this character is escaped
				result.append(char)
				escaped = False
			elif char == '\\':
				# This is an escape character
				result.append(char)
				escaped = True
			elif char == '"':
				# End of string
				result.append(char)
				in_string = False
			elif char == '\n':
				# Literal newline inside string - escape it
				result.append('\\n')
			elif char == '\r':
				# Literal carriage return inside string - escape it
				result.append('\\r')
			elif char == '\t':
				# Literal tab inside string - escape it
				result.append('\\t')
			elif char == '\b':
				# Literal backspace inside string - escape it
				result.append('\\b')
			elif char == '\f':
				# Literal form feed inside string - escape it
				result.append('\\f')
			elif ord(char) < 32:
				# Other control characters inside string - convert to unicode escape
				result.append(f'\\u{ord(char):04x}')
			else:
				# Normal character inside string
				result.append(char)

		i += 1

	return ''.join(result)


def convert_input_messages(input_messages: list[BaseMessage], model_name: str | None) -> list[BaseMessage]:
	"""Convert input messages to a format that is compatible with the planner model"""
	if model_name is None:
		return input_messages

	# TODO: use the auto-detected tool calling method from Agent._set_tool_calling_method(),
	# or abstract that logic out to reuse so we can autodetect the planner model's tool calling method as well
	if is_model_without_tool_support(model_name):
		converted_input_messages = _convert_messages_for_non_function_calling_models(input_messages)
		merged_input_messages = _merge_successive_messages(converted_input_messages, HumanMessage)
		merged_input_messages = _merge_successive_messages(merged_input_messages, AIMessage)
		return merged_input_messages
	return input_messages


def _convert_messages_for_non_function_calling_models(input_messages: list[BaseMessage]) -> list[BaseMessage]:
	"""Convert messages for non-function-calling models"""
	output_messages = []
	for message in input_messages:
		if isinstance(message, HumanMessage):
			output_messages.append(message)
		elif isinstance(message, SystemMessage):
			output_messages.append(message)
		elif isinstance(message, ToolMessage):
			output_messages.append(HumanMessage(content=message.content))
		elif isinstance(message, AIMessage):
			# check if tool_calls is a valid JSON object
			if message.tool_calls:
				tool_calls = json.dumps(message.tool_calls)
				output_messages.append(AIMessage(content=tool_calls))
			else:
				output_messages.append(message)
		else:
			raise ValueError(f'Unknown message type: {type(message)}')
	return output_messages


def _merge_successive_messages(messages: list[BaseMessage], class_to_merge: type[BaseMessage]) -> list[BaseMessage]:
	"""Some models like deepseek-reasoner dont allow multiple human messages in a row. This function merges them into one."""
	merged_messages = []
	streak = 0
	for message in messages:
		if isinstance(message, class_to_merge):
			streak += 1
			if streak > 1:
				if isinstance(message.content, list):
					merged_messages[-1].content += message.content[0]['text']  # type:ignore
				else:
					merged_messages[-1].content += message.content
			else:
				merged_messages.append(message)
		else:
			merged_messages.append(message)
			streak = 0
	return merged_messages


async def save_conversation(
	input_messages: list[BaseMessage], response: Any, target: str | Path, encoding: str | None = None
) -> None:
	"""Save conversation history to file asynchronously."""
	target_path = Path(target)

	# create folders if not exists
	if target_path.parent:
		await anyio.Path(target_path.parent).mkdir(parents=True, exist_ok=True)

	await anyio.Path(target_path).write_text(await _format_conversation(input_messages, response), encoding=encoding or 'utf-8')


async def _format_conversation(messages: list[BaseMessage], response: Any) -> str:
	"""Format the conversation including messages and response."""
	lines = []

	# Format messages
	for message in messages:
		lines.append(f' {message.__class__.__name__} ')

		if isinstance(message.content, list):
			for item in message.content:
				if isinstance(item, dict) and item.get('type') == 'text':
					lines.append(item['text'].strip())
		elif isinstance(message.content, str):
			try:
				content = json.loads(message.content)
				lines.append(json.dumps(content, indent=2))
			except json.JSONDecodeError:
				lines.append(message.content.strip())

		lines.append('')  # Empty line after each message

	# Format response
	lines.append(' RESPONSE')
	lines.append(json.dumps(json.loads(response.model_dump_json(exclude_unset=True)), indent=2))

	return '\n'.join(lines)


# Note: _write_messages_to_file and _write_response_to_file have been merged into _format_conversation
# This is more efficient for async operations and reduces file I/O
