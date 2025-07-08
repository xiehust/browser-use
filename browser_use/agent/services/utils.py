"""
Agent utility functions and setup helpers.

This module provides utility functions for the browser-use agent including
version detection, action model setup, and LLM verification.
"""

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from browser_use.agent.message_manager.service import MessageManager
from browser_use.agent.prompts import SystemPrompt
from browser_use.agent.views import AgentOutput
from browser_use.config import CONFIG
from browser_use.controller.registry.views import ActionModel
from browser_use.utils import get_browser_use_version

if TYPE_CHECKING:
	from browser_use.agent.service import Agent

logger = logging.getLogger(__name__)


class AgentUtils:
	"""Utility functions for agent setup and configuration"""

	def __init__(self, agent: 'Agent'):
		self.agent = agent

	def set_browser_use_version_and_source(self, source_override: str | None = None) -> None:
		"""Get the version from pyproject.toml and determine the source of the browser-use package"""
		# Use the helper function for version detection
		version = get_browser_use_version()

		# Determine source
		try:
			package_root = Path(__file__).parent.parent.parent
			repo_files = ['.git', 'README.md', 'docs', 'examples']
			if all(Path(package_root / file).exists() for file in repo_files):
				source = 'git'
			else:
				source = 'pip'
		except Exception as e:
			self.agent.logger.debug(f'Error determining source: {e}')
			source = 'unknown'

		if source_override is not None:
			source = source_override

		self.agent.version = version
		self.agent.source = source

	def setup_action_models(self) -> None:
		"""Setup dynamic action models from controller's registry"""
		# Initially only include actions with no filters
		self.agent.ActionModel = self.agent.controller.registry.create_action_model()

		# Create output model with the dynamic actions
		if self.agent.settings.use_thinking:
			self.agent.AgentOutput = AgentOutput.type_with_custom_actions(self.agent.ActionModel)
		else:
			self.agent.AgentOutput = AgentOutput.type_with_custom_actions_no_thinking(self.agent.ActionModel)

		# used to force the done action when max_steps is reached
		self.agent.DoneActionModel = self.agent.controller.registry.create_action_model(include_actions=['done'])
		if self.agent.settings.use_thinking:
			self.agent.DoneAgentOutput = AgentOutput.type_with_custom_actions(self.agent.DoneActionModel)
		else:
			self.agent.DoneAgentOutput = AgentOutput.type_with_custom_actions_no_thinking(self.agent.DoneActionModel)

	def verify_and_setup_llm(self) -> bool:
		"""
		Verify that the LLM API keys are setup and the LLM API is responding properly.
		Also handles tool calling method detection if in auto mode.
		"""
		# Skip verification if already done
		if getattr(self.agent.llm, '_verified_api_keys', None) is True or CONFIG.SKIP_LLM_API_KEY_VERIFICATION:
			setattr(self.agent.llm, '_verified_api_keys', True)
			return True

		# Additional verification logic can be added here
		return True

	def convert_initial_actions(self, actions: list[dict[str, dict[str, Any]]] | None) -> list[ActionModel] | None:
		"""Convert initial actions from dict format to ActionModel format"""
		if not actions:
			return None

		converted_actions = []
		for action_dict in actions:
			try:
				# Convert dict to ActionModel
				action_model = self.agent.ActionModel.model_validate(action_dict)
				converted_actions.append(action_model)
			except Exception as e:
				self.agent.logger.warning(f'Failed to convert initial action {action_dict}: {e}')
				continue

		return converted_actions if converted_actions else None

	def initialize_message_manager(
		self,
		task: str,
		sensitive_data: dict[str, str | dict[str, str]] | None = None,
		override_system_message: str | None = None,
		extend_system_message: str | None = None,
	) -> None:
		"""Initialize message manager with proper system prompt and settings"""

		# Initialize available actions for system prompt (only non-filtered actions)
		self.agent.unfiltered_actions = self.agent.controller.registry.get_prompt_description()

		# Initialize message manager with state
		self.agent._message_manager = MessageManager(
			task=task,
			system_message=SystemPrompt(
				action_description=self.agent.unfiltered_actions,
				max_actions_per_step=self.agent.settings.max_actions_per_step,
				override_system_message=override_system_message,
				extend_system_message=extend_system_message,
				use_thinking=self.agent.settings.use_thinking,
			).get_system_message(),
			file_system=self.agent.file_system,
			available_file_paths=self.agent.settings.available_file_paths,
			state=self.agent.state.message_manager_state,
			use_thinking=self.agent.settings.use_thinking,
			# Settings that were previously in MessageManagerSettings
			include_attributes=self.agent.settings.include_attributes,
			message_context=self.agent.settings.message_context,
			sensitive_data=sensitive_data,
			max_history_items=self.agent.settings.max_history_items,
			images_per_step=self.agent.settings.images_per_step,
			include_tool_call_examples=self.agent.settings.include_tool_call_examples,
		)

	def log_agent_info(self) -> None:
		"""Log agent initialization information"""
		self.agent.logger.info(
			f'🧠 Starting a browser-use agent {self.agent.version} with base_model={self.agent.llm.model}'
			f'{" +vision" if self.agent.settings.use_vision else ""}'
			f' extraction_model={self.agent.settings.page_extraction_llm.model if self.agent.settings.page_extraction_llm else "Unknown"}'
			f'{" +file_system" if self.agent.file_system else ""}'
		)

	def setup_callbacks(
		self,
		register_new_step_callback: Callable | None = None,
		register_done_callback: Callable | None = None,
		register_external_agent_status_raise_error_callback: Callable[[], Awaitable[bool]] | None = None,
		context: Any = None,
	) -> None:
		"""Setup agent callbacks and context"""
		self.agent.register_new_step_callback = register_new_step_callback
		self.agent.register_done_callback = register_done_callback
		self.agent.register_external_agent_status_raise_error_callback = register_external_agent_status_raise_error_callback
		self.agent.context = context
