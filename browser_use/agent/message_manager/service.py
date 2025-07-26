from __future__ import annotations

import logging
import os
from typing import Literal

import aiohttp
from dotenv import load_dotenv

from browser_use.agent.message_manager.views import (
	HistoryItem,
)
from browser_use.agent.prompts import AgentMessagePrompt
from browser_use.agent.views import (
	ActionResult,
	AgentHistoryList,
	AgentOutput,
	AgentStepInfo,
	MessageManagerState,
)
from browser_use.browser.views import BrowserStateSummary
from browser_use.dom.utils import cap_text_length
from browser_use.dom.views import DOMElementNode, SelectorMap
from browser_use.filesystem.file_system import FileSystem
from browser_use.llm.messages import (
	BaseMessage,
	ContentPartTextParam,
	SystemMessage,
)
from browser_use.observability import observe_debug
from browser_use.utils import match_url_with_domain_pattern, time_execution_sync

logger = logging.getLogger(__name__)

# Load environment variables for Relace API
load_dotenv()


# ========== Logging Helper Functions ==========
# These functions are used ONLY for formatting debug log output.
# They do NOT affect the actual message content sent to the LLM.
# All logging functions start with _log_ for easy identification.


def _log_get_message_emoji(message: BaseMessage) -> str:
	"""Get emoji for a message type - used only for logging display"""
	emoji_map = {
		'UserMessage': '💬',
		'SystemMessage': '🧠',
		'AssistantMessage': '🔨',
	}
	return emoji_map.get(message.__class__.__name__, '🎮')


def _log_format_message_line(message: BaseMessage, content: str, is_last_message: bool, terminal_width: int) -> list[str]:
	"""Format a single message for logging display"""
	try:
		lines = []

		# Get emoji and token info
		emoji = _log_get_message_emoji(message)
		# token_str = str(message.metadata.tokens).rjust(4)
		# TODO: fix the token count
		token_str = '??? (TODO)'
		prefix = f'{emoji}[{token_str}]: '

		# Calculate available width (emoji=2 visual cols + [token]: =8 chars)
		content_width = terminal_width - 10

		# Handle last message wrapping
		if is_last_message and len(content) > content_width:
			# Find a good break point
			break_point = content.rfind(' ', 0, content_width)
			if break_point > content_width * 0.7:  # Keep at least 70% of line
				first_line = content[:break_point]
				rest = content[break_point + 1 :]
			else:
				# No good break point, just truncate
				first_line = content[:content_width]
				rest = content[content_width:]

			lines.append(prefix + first_line)

			# Second line with 10-space indent
			if rest:
				if len(rest) > terminal_width - 10:
					rest = rest[: terminal_width - 10]
				lines.append(' ' * 10 + rest)
		else:
			# Single line - truncate if needed
			if len(content) > content_width:
				content = content[:content_width]
			lines.append(prefix + content)

		return lines
	except Exception as e:
		logger.warning(f'Failed to format message line for logging: {e}')
		# Return a simple fallback line
		return ['❓[   ?]: [Error formatting message]']


# ========== End of Logging Helper Functions ==========


class RelaceRerankingService:
	"""Service for reranking DOM elements using the Relace API"""

	def __init__(self):
		self.api_key = os.getenv('RELACE_API_KEY')
		self.api_url = 'https://browseruseranker.endpoint.relace.run/v2/code/rank'
		self.headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}' if self.api_key else None}

	def is_available(self) -> bool:
		"""Check if the reranking service is available (API key is set)"""
		return self.api_key is not None

	def _is_minimal_navigation_element(self, element: DOMElementNode) -> bool:
		"""Check if element is a minimal navigation element that should be preserved"""
		if element.highlight_index is None:
			return False

		# Get element text - use minimal processing to check length
		text = element.get_all_text_till_next_clickable_element().strip()

		# Consider it minimal if:
		# 1. Very short text (0-3 characters) AND it's a button/link
		# 2. Common navigation patterns
		if len(text) <= 3 and element.tag_name.lower() in ['button', 'a', 'span', 'div']:
			return True

		# Common navigation text patterns (case-insensitive)
		nav_patterns = [
			'',
			'>',
			'<',
			'→',
			'←',
			'↑',
			'↓',
			'x',
			'+',
			'-',
			'=',
			'menu',
			'nav',
			'home',
			'back',
			'next',
			'prev',
			'close',
			'ok',
			'yes',
			'no',
			'go',
			'search',
			'submit',
			'login',
			'sign',
		]

		return text.lower() in nav_patterns or any(pattern in text.lower() for pattern in ['arrow', 'icon', 'btn'])

	def _build_enhanced_query(self, task: str, browser_state_summary, step_info=None) -> str:
		"""Build an enhanced query with additional context"""
		query_parts = [f'Task: {task}']

		# Add current URL context
		if hasattr(browser_state_summary, 'url') and browser_state_summary.url:
			from urllib.parse import urlparse

			domain = urlparse(browser_state_summary.url).netloc
			query_parts.append(f'Current website: {domain}')

		# Add page title context
		if hasattr(browser_state_summary, 'title') and browser_state_summary.title:
			query_parts.append(f'Page title: {browser_state_summary.title}')

		# Add step context
		if step_info:
			query_parts.append(f'Step {step_info.step_number + 1} of {step_info.max_steps}')

		# Add guidance for what elements to prioritize
		query_parts.append('Prioritize elements directly related to the task objective.')

		return ' | '.join(query_parts)

	def _extract_element_string(self, element: DOMElementNode, include_attributes: list[str] | None = None) -> str:
		"""Extract string representation of a single DOM element similar to clickable_elements_to_string format"""
		if element.highlight_index is None:
			return ''

		text = element.get_all_text_till_next_clickable_element()
		attributes_html_str = None

		if include_attributes:
			attributes_to_include = {
				key: str(value).strip()
				for key, value in element.attributes.items()
				if key in include_attributes and str(value).strip() != ''
			}

			# Same optimization logic as in clickable_elements_to_string
			ordered_keys = [key for key in include_attributes if key in attributes_to_include]

			if len(ordered_keys) > 1:
				keys_to_remove = set()
				seen_values = {}

				for key in ordered_keys:
					value = attributes_to_include[key]
					if len(value) > 5:
						if value in seen_values:
							keys_to_remove.add(key)
						else:
							seen_values[value] = key

				for key in keys_to_remove:
					del attributes_to_include[key]

			# Remove redundant attributes
			if element.tag_name == attributes_to_include.get('role'):
				del attributes_to_include['role']

			attrs_to_remove_if_text_matches = ['aria-label', 'placeholder', 'title']
			for attr in attrs_to_remove_if_text_matches:
				if (
					attributes_to_include.get(attr)
					and attributes_to_include.get(attr, '').strip().lower() == text.strip().lower()
				):
					del attributes_to_include[attr]

			if attributes_to_include.items():
				attributes_html_str = ' '.join(
					f'{key}={cap_text_length(value, 15)}' for key, value in attributes_to_include.items()
				)

		# Build the element string
		highlight_indicator = f'*[{element.highlight_index}]' if element.is_new else f'[{element.highlight_index}]'
		line = f'{highlight_indicator}<{element.tag_name}'

		if attributes_html_str:
			line += f' {attributes_html_str}'

		if text:
			text = text.strip()
			if not attributes_html_str:
				line += ' '
			line += f'>{text}'
		elif not attributes_html_str:
			line += ' '

		line += ' />'
		return line

	def _prepare_elements_for_api(self, selector_map: SelectorMap, include_attributes: list[str] | None = None) -> list[dict]:
		"""Convert selector map to format expected by Relace API"""
		elements_for_api = []

		for index, element in selector_map.items():
			if element.highlight_index is not None:  # Only interactive elements
				element_string = self._extract_element_string(element, include_attributes)
				if element_string:
					elements_for_api.append({'filename': str(index), 'code': element_string})

		return elements_for_api

	async def rerank_elements(
		self,
		selector_map: SelectorMap,
		task: str,
		include_attributes: list[str] | None = None,
		token_limit: int = 128000,
		browser_state_summary=None,
		step_info=None,
	) -> list[dict]:
		"""
		Rerank DOM elements using Relace API

		Returns:
			List of dicts with 'filename' (element index) and 'score' (relevance score)
		"""
		if not self.is_available():
			logger.warning('Relace API key not available, skipping reranking')
			return []

		try:
			# Prepare elements for API
			codebase = self._prepare_elements_for_api(selector_map, include_attributes)

			if not codebase:
				logger.debug('No interactive elements found for reranking')
				return []

			# Build enhanced query with context
			enhanced_query = self._build_enhanced_query(task, browser_state_summary, step_info)

			# Prepare API request
			data = {'query': enhanced_query, 'codebase': codebase, 'token_limit': token_limit}

			logger.debug(f'Sending {len(codebase)} elements to Relace reranking API')
			logger.debug(f'Enhanced query: {enhanced_query}')

			# Make API request
			timeout = aiohttp.ClientTimeout(total=10)
			async with aiohttp.ClientSession(timeout=timeout) as session:
				async with session.post(self.api_url, headers=self.headers, json=data) as response:
					response.raise_for_status()
					output = await response.json()
					ranked_results = output.get('results', [])

			logger.debug(f'Received {len(ranked_results)} ranked results from Relace API')
			return ranked_results

		except Exception as e:
			logger.warning(f'Relace reranking failed: {type(e).__name__}: {e}')
			return []

	def filter_and_reorder_selector_map(
		self,
		selector_map: SelectorMap,
		ranked_results: list[dict],
		score_threshold: float = 0.3,  # Lowered from 0.5 to 0.3
		has_consecutive_failures: bool = False,
		preserve_minimal_nav: bool = False,  # New option to preserve minimal navigation elements
	) -> SelectorMap:
		"""
		Filter and reorder selector map based on reranking results

		Args:
			selector_map: Original selector map
			ranked_results: Results from reranking API with filename and score
			score_threshold: Minimum score to include (default: 0.3)
			has_consecutive_failures: If True, keep all elements but prioritize high-scoring ones
			preserve_minimal_nav: If True, always include minimal navigation elements

		Returns:
			Filtered and reordered selector map maintaining original indices
		"""
		if not ranked_results:
			return selector_map

		# Create mapping from filename (index) to score
		score_map = {int(result['filename']): result['score'] for result in ranked_results}

		# Identify minimal navigation elements if preservation is enabled
		minimal_nav_elements = {}
		if preserve_minimal_nav:
			for index, element in selector_map.items():
				if self._is_minimal_navigation_element(element):
					minimal_nav_elements[index] = element

		if has_consecutive_failures:
			# Keep all elements but reorder: high scoring first, then minimal nav, then low scoring
			high_scoring = []
			minimal_nav = []
			low_scoring = []

			for index, element in selector_map.items():
				score = score_map.get(index, 0.0)

				if index in minimal_nav_elements:
					minimal_nav.append((index, element, score))
				elif score >= score_threshold:
					high_scoring.append((index, element, score))
				else:
					low_scoring.append((index, element, score))

			# Sort each category appropriately
			high_scoring.sort(key=lambda x: x[2], reverse=True)  # By score descending
			minimal_nav.sort(key=lambda x: x[0])  # By original index
			low_scoring.sort(key=lambda x: x[0])  # By original index

			# Rebuild selector map with prioritized order
			filtered_map = {}
			for index, element, score in high_scoring + minimal_nav + low_scoring:
				filtered_map[index] = element

			logger.info(
				f'Reordered {len(filtered_map)} elements (consecutive failures): {len(high_scoring)} high-scoring (≥{score_threshold}), {len(minimal_nav)} minimal nav, {len(low_scoring)} low-scoring'
			)

		else:
			# Filter out low-scoring elements but always preserve minimal navigation
			filtered_map = {}
			filtered_count = 0
			preserved_nav_count = 0

			for index, element in selector_map.items():
				score = score_map.get(index, 0.0)

				if index in minimal_nav_elements:
					# Always include minimal navigation elements
					filtered_map[index] = element
					preserved_nav_count += 1
				elif score >= score_threshold:
					# Include high-scoring elements
					filtered_map[index] = element
					filtered_count += 1

			logger.info(
				f'Filtered {len(selector_map)} elements to {len(filtered_map)} (threshold ≥{score_threshold}): {filtered_count} high-scoring + {preserved_nav_count} preserved nav elements'
			)

		return filtered_map


class MessageManager:
	def __init__(
		self,
		task: str,
		system_message: SystemMessage,
		file_system: FileSystem,
		state: MessageManagerState = MessageManagerState(),
		use_thinking: bool = True,
		include_attributes: list[str] | None = None,
		message_context: str | None = None,
		sensitive_data: dict[str, str | dict[str, str]] | None = None,
		max_history_items: int | None = None,
		images_per_step: int = 1,
		include_tool_call_examples: bool = False,
	):
		self.task = task
		self.state = state
		self.system_prompt = system_message
		self.file_system = file_system
		self.sensitive_data_description = ''
		self.use_thinking = use_thinking
		self.max_history_items = max_history_items
		self.images_per_step = images_per_step
		self.include_tool_call_examples = include_tool_call_examples

		assert max_history_items is None or max_history_items > 5, 'max_history_items must be None or greater than 5'

		# Store settings as direct attributes instead of in a settings object
		self.include_attributes = include_attributes or []
		self.message_context = message_context
		self.sensitive_data = sensitive_data
		self.last_input_messages = []

		# Initialize reranking service
		self.reranking_service = RelaceRerankingService()
		if self.reranking_service.is_available():
			logger.info('🎯 Relace reranking service initialized and available')
		else:
			logger.debug('🎯 Relace reranking service not available (no API key)')

		# Only initialize messages if state is empty
		if len(self.state.history.get_messages()) == 0:
			self._add_message_with_type(self.system_prompt, 'system')

	@property
	def agent_history_description(self) -> str:
		"""Build agent history description from list of items, respecting max_history_items limit"""
		if self.max_history_items is None:
			# Include all items
			return '\n'.join(item.to_string() for item in self.state.agent_history_items)

		total_items = len(self.state.agent_history_items)

		# If we have fewer items than the limit, just return all items
		if total_items <= self.max_history_items:
			return '\n'.join(item.to_string() for item in self.state.agent_history_items)

		# We have more items than the limit, so we need to omit some
		omitted_count = total_items - self.max_history_items

		# Show first item + omitted message + most recent (max_history_items - 1) items
		# The omitted message doesn't count against the limit, only real history items do
		recent_items_count = self.max_history_items - 1  # -1 for first item

		items_to_include = [
			self.state.agent_history_items[0].to_string(),  # Keep first item (initialization)
			f'<sys>[... {omitted_count} previous steps omitted...]</sys>',
		]
		# Add most recent items
		items_to_include.extend([item.to_string() for item in self.state.agent_history_items[-recent_items_count:]])

		return '\n'.join(items_to_include)

	def add_new_task(self, new_task: str) -> None:
		self.task = new_task
		task_update_item = HistoryItem(system_message=f'User updated <user_request> to: {new_task}')
		self.state.agent_history_items.append(task_update_item)

	@observe_debug(ignore_input=True, ignore_output=True, name='update_agent_history_description')
	def _update_agent_history_description(
		self,
		model_output: AgentOutput | None = None,
		result: list[ActionResult] | None = None,
		step_info: AgentStepInfo | None = None,
	) -> None:
		"""Update the agent history description"""

		if result is None:
			result = []
		step_number = step_info.step_number if step_info else None

		self.state.read_state_description = ''

		action_results = ''
		result_len = len(result)
		for idx, action_result in enumerate(result):
			if action_result.include_extracted_content_only_once and action_result.extracted_content:
				self.state.read_state_description += action_result.extracted_content + '\n'
				logger.debug(f'Added extracted_content to read_state_description: {action_result.extracted_content}')

			if action_result.long_term_memory:
				action_results += f'Action {idx + 1}/{result_len}: {action_result.long_term_memory}\n'
				logger.debug(f'Added long_term_memory to action_results: {action_result.long_term_memory}')
			elif action_result.extracted_content and not action_result.include_extracted_content_only_once:
				action_results += f'Action {idx + 1}/{result_len}: {action_result.extracted_content}\n'
				logger.debug(f'Added extracted_content to action_results: {action_result.extracted_content}')

			if action_result.error:
				if len(action_result.error) > 200:
					error_text = action_result.error[:100] + '......' + action_result.error[-100:]
				else:
					error_text = action_result.error
				action_results += f'Action {idx + 1}/{result_len}: {error_text}\n'
				logger.debug(f'Added error to action_results: {error_text}')

		if action_results:
			action_results = f'Action Results:\n{action_results}'
		action_results = action_results.strip('\n') if action_results else None

		# Build the history item
		if model_output is None:
			# Only add error history item if we have a valid step number
			if step_number is not None and step_number > 0:
				history_item = HistoryItem(step_number=step_number, error='Agent failed to output in the right format.')
				self.state.agent_history_items.append(history_item)
		else:
			history_item = HistoryItem(
				step_number=step_number,
				evaluation_previous_goal=model_output.current_state.evaluation_previous_goal,
				memory=model_output.current_state.memory,
				next_goal=model_output.current_state.next_goal,
				action_results=action_results,
			)
			self.state.agent_history_items.append(history_item)

	def _get_sensitive_data_description(self, current_page_url) -> str:
		sensitive_data = self.sensitive_data
		if not sensitive_data:
			return ''

		# Collect placeholders for sensitive data
		placeholders: set[str] = set()

		for key, value in sensitive_data.items():
			if isinstance(value, dict):
				# New format: {domain: {key: value}}
				if match_url_with_domain_pattern(current_page_url, key, True):
					placeholders.update(value.keys())
			else:
				# Old format: {key: value}
				placeholders.add(key)

		if placeholders:
			placeholder_list = sorted(list(placeholders))
			info = f'Here are placeholders for sensitive data:\n{placeholder_list}\n'
			info += 'To use them, write <secret>the placeholder name</secret>'
			return info

		return ''

	@observe_debug(ignore_input=True, ignore_output=True, name='add_state_message')
	@time_execution_sync('--add_state_message')
	async def add_state_message(
		self,
		browser_state_summary: BrowserStateSummary,
		model_output: AgentOutput | None = None,
		result: list[ActionResult] | None = None,
		step_info: AgentStepInfo | None = None,
		use_vision=True,
		page_filtered_actions: str | None = None,
		sensitive_data=None,
		agent_history_list: AgentHistoryList | None = None,  # Pass AgentHistoryList from agent
		available_file_paths: list[str] | None = None,  # Always pass current available_file_paths
		consecutive_failures: int = 0,  # Number of consecutive failures to determine reranking strategy
	) -> None:
		"""Add browser state as human message"""

		self._update_agent_history_description(model_output, result, step_info)
		if sensitive_data:
			self.sensitive_data_description = self._get_sensitive_data_description(browser_state_summary.url)

		# Apply reranking if service is available and we have interactive elements
		reranked_browser_state = browser_state_summary
		if self.reranking_service.is_available() and browser_state_summary.selector_map:
			try:
				# Use the task as the query for reranking with enhanced context
				ranked_results = await self.reranking_service.rerank_elements(
					browser_state_summary.selector_map,
					self.task,
					self.include_attributes,
					browser_state_summary=browser_state_summary,
					step_info=step_info,
				)

				if ranked_results:
					# Determine if we should apply strict filtering or keep all elements
					has_consecutive_failures = consecutive_failures >= 2

					# Filter and reorder the selector map based on ranking (now with 0.3 threshold and nav preservation)
					filtered_selector_map = self.reranking_service.filter_and_reorder_selector_map(
						browser_state_summary.selector_map,
						ranked_results,
						score_threshold=0.3,  # Lowered threshold
						has_consecutive_failures=has_consecutive_failures,
						preserve_minimal_nav=False,  # Enable preservation of minimal navigation elements
					)

					# Create a modified browser state with the filtered selector map
					# We need to import dataclasses.replace or copy the object
					from dataclasses import replace

					reranked_browser_state = replace(browser_state_summary, selector_map=filtered_selector_map)

					logger.debug(
						f'🎯 Applied reranking: {len(browser_state_summary.selector_map)} → {len(filtered_selector_map)} elements'
					)

			except Exception as e:
				logger.warning(f'🎯 Reranking failed, using original browser state: {type(e).__name__}: {e}')
				# Continue with original browser state if reranking fails

		# Extract previous screenshots if we need more than 1 image and have agent history
		screenshots = []
		if agent_history_list and self.images_per_step > 1:
			# Get previous screenshots and filter out None values
			raw_screenshots = agent_history_list.screenshots(n_last=self.images_per_step - 1, return_none_if_not_screenshot=False)
			screenshots = [s for s in raw_screenshots if s is not None]

		# add current screenshot to the end
		if reranked_browser_state.screenshot:
			screenshots.append(reranked_browser_state.screenshot)

		# otherwise add state message and result to next message (which will not stay in memory)
		assert reranked_browser_state
		state_message = AgentMessagePrompt(
			browser_state_summary=reranked_browser_state,  # Use the reranked browser state
			file_system=self.file_system,
			agent_history_description=self.agent_history_description,
			read_state_description=self.state.read_state_description,
			task=self.task,
			include_attributes=self.include_attributes,
			step_info=step_info,
			page_filtered_actions=page_filtered_actions,
			sensitive_data=self.sensitive_data_description,
			available_file_paths=available_file_paths,
			screenshots=screenshots,
		).get_user_message(use_vision)

		self._add_message_with_type(state_message, 'state')

	def _log_history_lines(self) -> str:
		"""Generate a formatted log string of message history for debugging / printing to terminal"""
		# TODO: fix logging

		# try:
		# 	total_input_tokens = 0
		# 	message_lines = []
		# 	terminal_width = shutil.get_terminal_size((80, 20)).columns

		# 	for i, m in enumerate(self.state.history.messages):
		# 		try:
		# 			total_input_tokens += m.metadata.tokens
		# 			is_last_message = i == len(self.state.history.messages) - 1

		# 			# Extract content for logging
		# 			content = _log_extract_message_content(m.message, is_last_message, m.metadata)

		# 			# Format the message line(s)
		# 			lines = _log_format_message_line(m, content, is_last_message, terminal_width)
		# 			message_lines.extend(lines)
		# 		except Exception as e:
		# 			logger.warning(f'Failed to format message {i} for logging: {e}')
		# 			# Add a fallback line for this message
		# 			message_lines.append('❓[   ?]: [Error formatting this message]')

		# 	# Build final log message
		# 	return (
		# 		f'📜 LLM Message history ({len(self.state.history.messages)} messages, {total_input_tokens} tokens):\n'
		# 		+ '\n'.join(message_lines)
		# 	)
		# except Exception as e:
		# 	logger.warning(f'Failed to generate history log: {e}')
		# 	# Return a minimal fallback message
		# 	return f'📜 LLM Message history (error generating log: {e})'

		return ''

	@time_execution_sync('--get_messages')
	def get_messages(self) -> list[BaseMessage]:
		"""Get current message list, potentially trimmed to max tokens"""

		# Log message history for debugging
		logger.debug(self._log_history_lines())
		self.last_input_messages = self.state.history.get_messages()
		return self.last_input_messages

	def _add_message_with_type(self, message: BaseMessage, message_type: Literal['system', 'state', 'consistent']) -> None:
		"""Add message to history"""

		# filter out sensitive data from the message
		if self.sensitive_data:
			message = self._filter_sensitive_data(message)

		if message_type == 'system':
			self.state.history.system_message = message
		elif message_type == 'state':
			self.state.history.state_message = message
		elif message_type == 'consistent':
			self.state.history.consistent_messages.append(message)
		else:
			raise ValueError(f'Invalid message type: {message_type}')

	@time_execution_sync('--filter_sensitive_data')
	def _filter_sensitive_data(self, message: BaseMessage) -> BaseMessage:
		"""Filter out sensitive data from the message"""

		def replace_sensitive(value: str) -> str:
			if not self.sensitive_data:
				return value

			# Collect all sensitive values, immediately converting old format to new format
			sensitive_values: dict[str, str] = {}

			# Process all sensitive data entries
			for key_or_domain, content in self.sensitive_data.items():
				if isinstance(content, dict):
					# Already in new format: {domain: {key: value}}
					for key, val in content.items():
						if val:  # Skip empty values
							sensitive_values[key] = val
				elif content:  # Old format: {key: value} - convert to new format internally
					# We treat this as if it was {'http*://*': {key_or_domain: content}}
					sensitive_values[key_or_domain] = content

			# If there are no valid sensitive data entries, just return the original value
			if not sensitive_values:
				logger.warning('No valid entries found in sensitive_data dictionary')
				return value

			# Replace all valid sensitive data values with their placeholder tags
			for key, val in sensitive_values.items():
				value = value.replace(val, f'<secret>{key}</secret>')

			return value

		if isinstance(message.content, str):
			message.content = replace_sensitive(message.content)
		elif isinstance(message.content, list):
			for i, item in enumerate(message.content):
				if isinstance(item, ContentPartTextParam):
					item.text = replace_sensitive(item.text)
					message.content[i] = item
		return message
