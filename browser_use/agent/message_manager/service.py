from __future__ import annotations

import logging
from typing import Literal

from browser_use.agent.message_manager.views import HistoryItem
from browser_use.agent.prompts import AgentMessagePrompt
from browser_use.agent.views import (
	ActionResult,
	AgentHistoryList,
	AgentOutput,
	AgentStepInfo,
	MessageManagerState,
)
from browser_use.browser.views import BrowserStateSummary
from browser_use.filesystem.file_system import FileSystem
from browser_use.llm.messages import BaseMessage, ContentPartTextParam, SystemMessage
from browser_use.observability import observe_debug
from browser_use.utils import match_url_with_domain_pattern, time_execution_sync

logger = logging.getLogger(__name__)


class MessageManager:
	"""Manages agent messages and conversation history"""

	def __init__(
		self,
		task: str,
		system_message: SystemMessage,
		file_system: FileSystem,
		state: MessageManagerState = MessageManagerState(),
		available_file_paths: list[str] | None = None,
		sensitive_data: dict[str, str | dict[str, str]] | None = None,
		max_history_items: int | None = None,
		images_per_step: int = 1,
		include_attributes: list[str] | None = None,
		message_context: str | None = None,
		use_thinking: bool = True,
		include_tool_call_examples: bool = False,
	):
		self.task = task
		self.state = state
		self.system_prompt = system_message
		self.file_system = file_system
		self.available_file_paths = available_file_paths
		self.sensitive_data = sensitive_data or {}
		self.max_history_items = max_history_items
		self.images_per_step = images_per_step
		self.include_attributes = include_attributes or []
		self.message_context = message_context
		self.use_thinking = use_thinking
		self.include_tool_call_examples = include_tool_call_examples
		self.last_input_messages: list[BaseMessage] = []

		if max_history_items is not None and max_history_items <= 5:
			raise ValueError('max_history_items must be None or greater than 5')

		# Initialize system message if state is empty
		if not self.state.history.get_messages():
			self._add_message(self.system_prompt, 'system')

	@property
	def agent_history_description(self) -> str:
		"""Build agent history description with max_history_items limit"""
		items = self.state.agent_history_items
		
		if self.max_history_items is None or len(items) <= self.max_history_items:
			return '\n'.join(item.to_string() for item in items)

		# Keep first item + most recent (max_history_items - 1) items
		omitted_count = len(items) - self.max_history_items
		recent_items = items[-(self.max_history_items - 1):]
		
		result = [
			items[0].to_string(),  # First item (initialization)
			f'<sys>[... {omitted_count} previous steps omitted...]</sys>',
		]
		result.extend(item.to_string() for item in recent_items)
		
		return '\n'.join(result)

	def add_new_task(self, new_task: str) -> None:
		"""Update task and add to history"""
		self.task = new_task
		self.state.agent_history_items.append(
			HistoryItem(system_message=f'User updated <user_request> to: {new_task}')
		)

	@observe_debug(name='update_agent_history_description')
	def _update_agent_history_description(
		self,
		model_output: AgentOutput | None = None,
		result: list[ActionResult] | None = None,
		step_info: AgentStepInfo | None = None,
	) -> None:
		"""Update agent history with results"""
		result = result or []
		step_number = step_info.step_number if step_info else None

		# Reset read state
		self.state.read_state_description = ''
		
		# Process action results
		action_results = self._build_action_results(result)
		
		# Create history item
		if model_output is None:
			if step_number is not None and step_number > 0:
				history_item = HistoryItem(
					step_number=step_number,
					error='Agent failed to output in the right format.'
				)
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

	def _build_action_results(self, results: list[ActionResult]) -> str | None:
		"""Build action results string from ActionResult list"""
		if not results:
			return None

		action_results = []
		for idx, action_result in enumerate(results, 1):
			# Handle extracted content that should only appear once
			if action_result.include_extracted_content_only_once and action_result.extracted_content:
				self.state.read_state_description += action_result.extracted_content + '\n'

			# Build action result text
			if action_result.long_term_memory:
				action_results.append(f'Action {idx}/{len(results)}: {action_result.long_term_memory}')
			elif action_result.extracted_content and not action_result.include_extracted_content_only_once:
				action_results.append(f'Action {idx}/{len(results)}: {action_result.extracted_content}')

			# Handle errors
			if action_result.error:
				error_text = self._truncate_error(action_result.error)
				action_results.append(f'Action {idx}/{len(results)}: {error_text}')

		return f'Action Results:\n{chr(10).join(action_results)}' if action_results else None

	def _truncate_error(self, error: str) -> str:
		"""Truncate long error messages"""
		if len(error) <= 200:
			return error
		return error[:100] + '......' + error[-100:]

	def _get_sensitive_data_description(self, current_page_url: str) -> str:
		"""Get description of available sensitive data placeholders"""
		if not self.sensitive_data:
			return ''

		placeholders = set()
		for key, value in self.sensitive_data.items():
			if isinstance(value, dict):
				# New format: {domain: {key: value}}
				if match_url_with_domain_pattern(current_page_url, key, True):
					placeholders.update(value.keys())
			else:
				# Old format: {key: value}
				placeholders.add(key)

		if not placeholders:
			return ''

		placeholder_list = sorted(placeholders)
		return (
			f'Here are placeholders for sensitive data:\n{placeholder_list}\n'
			'To use them, write <secret>the placeholder name</secret>'
		)

	@observe_debug(name='add_state_message')
	@time_execution_sync('--add_state_message')
	def add_state_message(
		self,
		browser_state_summary: BrowserStateSummary,
		model_output: AgentOutput | None = None,
		result: list[ActionResult] | None = None,
		step_info: AgentStepInfo | None = None,
		use_vision: bool = True,
		page_filtered_actions: str | None = None,
		sensitive_data: dict | None = None,
		agent_history_list: AgentHistoryList | None = None,
	) -> None:
		"""Add browser state as user message"""
		self._update_agent_history_description(model_output, result, step_info)
		
		# Get sensitive data description
		sensitive_data_desc = ''
		if sensitive_data:
			sensitive_data_desc = self._get_sensitive_data_description(browser_state_summary.url)

		# Handle screenshots
		screenshots = self._get_screenshots(browser_state_summary, agent_history_list)

		# Create state message
		state_message = AgentMessagePrompt(
			browser_state_summary=browser_state_summary,
			file_system=self.file_system,
			agent_history_description=self.agent_history_description,
			read_state_description=self.state.read_state_description,
			task=self.task,
			include_attributes=self.include_attributes,
			step_info=step_info,
			page_filtered_actions=page_filtered_actions,
			sensitive_data=sensitive_data_desc,
			available_file_paths=self.available_file_paths,
			screenshots=screenshots,
		).get_user_message(use_vision)

		self._add_message(state_message, 'state')

	def _get_screenshots(self, browser_state_summary: BrowserStateSummary, agent_history_list: AgentHistoryList | None) -> list:
		"""Get screenshots for the current step"""
		screenshots = []
		
		# Get previous screenshots if needed
		if agent_history_list and self.images_per_step > 1:
			previous_screenshots = agent_history_list.screenshots(
				n_last=self.images_per_step - 1,
				return_none_if_not_screenshot=False
			)
			screenshots.extend(s for s in previous_screenshots if s is not None)

		# Add current screenshot
		if browser_state_summary.screenshot:
			screenshots.append(browser_state_summary.screenshot)

		return screenshots

	@time_execution_sync('--get_messages')
	def get_messages(self) -> list[BaseMessage]:
		"""Get current message list"""
		self.last_input_messages = self.state.history.get_messages()
		return self.last_input_messages

	def _add_message(self, message: BaseMessage, message_type: Literal['system', 'state', 'consistent']) -> None:
		"""Add message to history with sensitive data filtering"""
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
		"""Filter sensitive data from message content"""
		if not self.sensitive_data:
			return message

		# Collect all sensitive values
		sensitive_values = {}
		for key_or_domain, content in self.sensitive_data.items():
			if isinstance(content, dict):
				# New format: {domain: {key: value}}
				for key, val in content.items():
					if val:  # Skip empty values
						sensitive_values[key] = val
			elif content:  # Old format: {key: value}
				sensitive_values[key_or_domain] = content

		if not sensitive_values:
			return message

		# Replace sensitive values with placeholders
		message = message.model_copy(deep=True)
		if isinstance(message.content, str):
			message.content = self._replace_sensitive_values(message.content, sensitive_values)
		elif isinstance(message.content, list):
			for i, item in enumerate(message.content):
				if isinstance(item, ContentPartTextParam):
					item.text = self._replace_sensitive_values(item.text, sensitive_values)
					message.content[i] = item

		return message

	def _replace_sensitive_values(self, text: str, sensitive_values: dict[str, str]) -> str:
		"""Replace sensitive values in text with placeholders"""
		for key, value in sensitive_values.items():
			text = text.replace(value, f'<secret>{key}</secret>')
		return text
