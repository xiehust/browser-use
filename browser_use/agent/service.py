import asyncio
import gc
import inspect
import logging
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Generic, TypeVar

from dotenv import load_dotenv
from pydantic import ValidationError
from uuid_extensions import uuid7str

from browser_use.agent.cloud_events import (
	CreateAgentStepEvent,
)
from browser_use.agent.gif import create_history_gif
from browser_use.agent.message_manager.service import MessageManager
from browser_use.agent.message_manager.utils import save_conversation
from browser_use.agent.services import (
	AgentLogger,
	AgentSetupService,
	AgentUtils,
	FileSystemManager,
	HistoryReplayService,
)
from browser_use.agent.views import (
	ActionResult,
	AgentError,
	AgentHistory,
	AgentHistoryList,
	AgentOutput,
	AgentSettings,
	AgentState,
	AgentStepInfo,
	AgentStructuredOutput,
	BrowserStateHistory,
	StepMetadata,
)
from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.browser.types import Browser, BrowserContext, Page
from browser_use.browser.views import BrowserStateSummary
from browser_use.controller.registry.views import ActionModel
from browser_use.controller.service import Controller
from browser_use.dom.views import DEFAULT_INCLUDE_ATTRIBUTES
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import BaseMessage, UserMessage
from browser_use.observability import observe, observe_debug
from browser_use.sync import CloudSync
from browser_use.utils import SignalHandler, time_execution_async, time_execution_sync

load_dotenv()

logger = logging.getLogger(__name__)


def log_response(response: AgentOutput, registry=None, logger=None) -> None:
	"""Utility function to log the model's response."""

	# Use module logger if no logger provided
	if logger is None:
		logger = logging.getLogger(__name__)

	if 'success' in response.current_state.evaluation_previous_goal.lower():
		emoji = '👍'
	elif 'failure' in response.current_state.evaluation_previous_goal.lower():
		emoji = '⚠️'
	else:
		emoji = '❔'

	# Only log thinking if it's present
	if response.current_state.thinking:
		logger.info(f'💡 Thinking:\n{response.current_state.thinking}')
	logger.info(f'{emoji} Eval: {response.current_state.evaluation_previous_goal}')
	logger.info(f'🧠 Memory: {response.current_state.memory}')
	logger.info(f'🎯 Next goal: {response.current_state.next_goal}\n')


Context = TypeVar('Context')


AgentHookFunc = Callable[['Agent'], Awaitable[None]]


class Agent(Generic[Context, AgentStructuredOutput]):
	browser_session: BrowserSession | None = None
	_logger: logging.Logger | None = None

	# Type annotations for attributes that will be initialized during __init__
	eventbus: Any
	telemetry: Any
	file_system: Any
	file_system_path: str | None
	version: str | None
	source: str | None
	sensitive_data: dict[str, str | dict[str, str]] | None
	register_new_step_callback: Any
	register_done_callback: Any
	register_external_agent_status_raise_error_callback: Any
	context: Any
	has_downloads_path: bool
	_last_known_downloads: list[str]
	token_cost_service: Any
	enable_cloud_sync: bool
	cloud_sync: Any
	_external_pause_event: Any
	_force_exit_telemetry_logged: bool
	_message_manager: MessageManager | None  # Will be initialized in __init__
	unfiltered_actions: str  # Action descriptions for system prompt

	# ============================================================================
	# INITIALIZATION AND SETUP
	# ============================================================================

	@time_execution_sync('--init')
	def __init__(
		self,
		task: str,
		llm: BaseChatModel,
		# Optional parameters
		page: Page | None = None,
		browser: Browser | BrowserSession | None = None,
		browser_context: BrowserContext | None = None,
		browser_profile: BrowserProfile | None = None,
		browser_session: BrowserSession | None = None,
		controller: Controller[Context] | None = None,
		# Initial agent run parameters
		sensitive_data: dict[str, str | dict[str, str]] | None = None,
		initial_actions: list[dict[str, dict[str, Any]]] | None = None,
		# Cloud Callbacks
		register_new_step_callback: (
			Callable[['BrowserStateSummary', 'AgentOutput', int], None]  # Sync callback
			| Callable[['BrowserStateSummary', 'AgentOutput', int], Awaitable[None]]  # Async callback
			| None
		) = None,
		register_done_callback: (
			Callable[['AgentHistoryList'], Awaitable[None]]  # Async Callback
			| Callable[['AgentHistoryList'], None]  # Sync Callback
			| None
		) = None,
		register_external_agent_status_raise_error_callback: Callable[[], Awaitable[bool]] | None = None,
		# Agent settings
		output_model_schema: type[AgentStructuredOutput] | None = None,
		use_vision: bool = True,
		use_vision_for_planner: bool = False,  # Deprecated
		save_conversation_path: str | Path | None = None,
		save_conversation_path_encoding: str | None = 'utf-8',
		max_failures: int = 3,
		retry_delay: int = 10,
		override_system_message: str | None = None,
		extend_system_message: str | None = None,
		validate_output: bool = False,
		message_context: str | None = None,
		generate_gif: bool | str = False,
		available_file_paths: list[str] | None = None,
		include_attributes: list[str] = DEFAULT_INCLUDE_ATTRIBUTES,
		max_actions_per_step: int = 10,
		use_thinking: bool = True,
		max_history_items: int = 40,
		images_per_step: int = 1,
		page_extraction_llm: BaseChatModel | None = None,
		planner_llm: BaseChatModel | None = None,  # Deprecated
		planner_interval: int = 1,  # Deprecated
		is_planner_reasoning: bool = False,  # Deprecated
		extend_planner_system_message: str | None = None,  # Deprecated
		injected_agent_state: AgentState | None = None,
		context: Context | None = None,
		source: str | None = None,
		file_system_path: str | None = None,
		task_id: str | None = None,
		cloud_sync: CloudSync | None = None,
		calculate_cost: bool = False,
		display_files_in_done_text: bool = True,
		include_tool_call_examples: bool = False,
		**kwargs,
	):
		"""Initialize the Agent with all necessary components and services"""

		# Set defaults
		if page_extraction_llm is None:
			page_extraction_llm = llm
		if available_file_paths is None:
			available_file_paths = []

		# Basic attribute initialization
		self.id = task_id or uuid7str()
		self.task_id: str = self.id
		self.session_id: str = uuid7str()
		self.task = task
		self.llm = llm
		self.state = injected_agent_state or AgentState()

		# Initialize attributes that are used throughout the class
		self.sensitive_data = sensitive_data
		self.register_new_step_callback = register_new_step_callback
		self.register_done_callback = register_done_callback
		self.register_external_agent_status_raise_error_callback = register_external_agent_status_raise_error_callback
		self.context = context

		# Initialize browser session and file system placeholders
		self.browser_session: BrowserSession | None = None
		self.file_system = None
		# Initialize _message_manager as a placeholder - will be set properly by agent_utils.initialize_message_manager
		self._message_manager: MessageManager | None = None

		# Initialize additional attributes
		self._force_exit_telemetry_logged = False

		# Initialize download tracking attributes
		self.has_downloads_path = False
		self._last_known_downloads = []

		# Create instance-specific logger
		self._logger = logging.getLogger(f'browser_use.Agent[{self.task_id[-3:]}]')

		# Initialize services
		self.setup_service = AgentSetupService(self)
		self.filesystem_manager = FileSystemManager(self)
		self.agent_utils = AgentUtils(self)

		# Validate deprecated parameters
		kwargs = self.setup_service.validate_deprecated_parameters(
			planner_llm=planner_llm,
			use_vision_for_planner=use_vision_for_planner,
			is_planner_reasoning=is_planner_reasoning,
			extend_planner_system_message=extend_planner_system_message,
			planner_interval=planner_interval,
			**kwargs,
		)

		# Setup controller and output schema
		self.controller = (
			controller if controller is not None else Controller(display_files_in_done_text=display_files_in_done_text)
		)

		self.output_model_schema = output_model_schema
		if output_model_schema is not None:
			self.controller.use_structured_output_action(output_model_schema)

		# Create settings object
		self.settings = AgentSettings(
			use_vision=use_vision,
			use_vision_for_planner=False,  # Always False now (deprecated)
			save_conversation_path=save_conversation_path,
			save_conversation_path_encoding=save_conversation_path_encoding,
			max_failures=max_failures,
			retry_delay=retry_delay,
			override_system_message=override_system_message,
			extend_system_message=extend_system_message,
			validate_output=validate_output,
			message_context=message_context,
			generate_gif=generate_gif,
			available_file_paths=available_file_paths,
			include_attributes=include_attributes,
			max_actions_per_step=max_actions_per_step,
			use_thinking=use_thinking,
			max_history_items=max_history_items,
			images_per_step=images_per_step,
			page_extraction_llm=page_extraction_llm,
			planner_llm=None,  # Always None now (deprecated)
			planner_interval=1,  # Always 1 now (deprecated)
			is_planner_reasoning=False,  # Always False now (deprecated)
			extend_planner_system_message=None,  # Always None now (deprecated)
			calculate_cost=calculate_cost,
			include_tool_call_examples=include_tool_call_examples,
		)

		# Setup services (token cost, telemetry, event bus, cloud sync)
		self.setup_service.setup_services(
			llm=llm,
			page_extraction_llm=page_extraction_llm,
			calculate_cost=calculate_cost,
			injected_agent_state=injected_agent_state,
			cloud_sync=cloud_sync,
		)

		# Initialize file system
		self.filesystem_manager.initialize_file_system(file_system_path)

		# Setup version, action models, and LLM verification
		self.agent_utils.set_browser_use_version_and_source(source)
		self.agent_utils.setup_action_models()
		self.agent_utils.verify_and_setup_llm()

		# Handle model-specific settings
		self.setup_service.handle_model_specific_settings(llm)

		# Convert initial actions
		self.initial_actions = self.agent_utils.convert_initial_actions(initial_actions)

		# Log agent information
		self.agent_utils.log_agent_info()

		# Initialize message manager
		self.agent_utils.initialize_message_manager(
			task=task,
			sensitive_data=sensitive_data,
			override_system_message=override_system_message,
			extend_system_message=extend_system_message,
		)

		# Setup browser session
		self.setup_service.setup_browser_session(
			page=page,
			browser=browser,
			browser_context=browser_context,
			browser_profile=browser_profile,
			browser_session=browser_session,
		)

		# Validate sensitive data
		self.setup_service.validate_sensitive_data(sensitive_data)

		# Setup callbacks and context
		self.agent_utils.setup_callbacks(
			register_new_step_callback=register_new_step_callback,
			register_done_callback=register_done_callback,
			register_external_agent_status_raise_error_callback=register_external_agent_status_raise_error_callback,
			context=context,
		)

		# Setup conversation saving
		self.setup_service.setup_conversation_saving(save_conversation_path)

		# Setup download tracking
		self.setup_service.setup_download_tracking()

		# Setup pause control
		self.setup_service.setup_pause_control()

		# Initialize additional services
		self.agent_logger = AgentLogger(self)
		self.history_replay_service = HistoryReplayService(self)

	# ============================================================================
	# PROPERTIES AND UTILITY METHODS
	# ============================================================================

	@property
	def logger(self) -> logging.Logger:
		"""Get instance-specific logger with task ID in the name"""
		_browser_session_id = self.browser_session.id if self.browser_session else self.id
		_current_page_id = str(id(self.browser_session and self.browser_session.agent_current_page))[-2:]
		return logging.getLogger(f'browser_use.Agent🅰 {self.task_id[-4:]} on 🆂 {_browser_session_id[-4:]} 🅟 {_current_page_id}')

	@property
	def browser(self) -> Browser:
		assert self.browser_session is not None, 'BrowserSession is not set up'
		assert self.browser_session.browser is not None, 'Browser is not set up'
		return self.browser_session.browser

	@property
	def browser_context(self) -> BrowserContext:
		assert self.browser_session is not None, 'BrowserSession is not set up'
		assert self.browser_session.browser_context is not None, 'BrowserContext is not set up'
		return self.browser_session.browser_context

	@property
	def browser_profile(self) -> BrowserProfile:
		assert self.browser_session is not None, 'BrowserSession is not set up'
		return self.browser_session.browser_profile

	@property
	def message_manager(self) -> MessageManager:
		"""Get the message manager instance"""
		assert self._message_manager is not None, 'MessageManager is not initialized'
		return self._message_manager

	# ============================================================================
	# TASK AND STATE MANAGEMENT
	# ============================================================================

	def add_new_task(self, new_task: str) -> None:
		"""Add a new task to the agent, keeping the same task_id as tasks are continuous"""
		# Simply delegate to message manager - no need for new task_id or events
		# The task continues with new instructions, it doesn't end and start a new one
		self.task = new_task
		assert self._message_manager is not None, 'MessageManager is not initialized'
		self._message_manager.add_new_task(new_task)

	def save_file_system_state(self) -> None:
		"""Save current file system state to agent state"""
		self.filesystem_manager.save_file_system_state()

	def _update_available_file_paths(self, downloads: list[str]) -> None:
		"""Update available_file_paths with downloaded files"""
		self.filesystem_manager.update_available_file_paths(downloads)

	# ============================================================================
	# PAUSE, RESUME, AND STOP CONTROL
	# ============================================================================

	async def wait_until_resumed(self):
		"""Wait until the agent is resumed"""
		await self._external_pause_event.wait()

	def pause(self) -> None:
		"""
		Pause the agent.

		The agent will pause before the next step is executed.
		"""
		if self.state.paused:
			self.logger.debug('Agent is already paused')
			return

		self.state.paused = True
		self._external_pause_event.clear()

		self.logger.info(
			'🔄 Agent paused. Call agent.resume() to continue execution or use Ctrl+C to unpause and immediately exit.'
		)

	def resume(self) -> None:
		"""
		Resume the agent.

		The agent will continue execution from where it was paused.
		"""
		if not self.state.paused:
			self.logger.debug('Agent is not paused')
			return

		self.state.paused = False
		self._external_pause_event.set()

		self.logger.info('▶️ Agent resumed')

	def stop(self) -> None:
		"""
		Stop the agent.

		The agent will stop execution and cannot be resumed.
		"""
		self.state.stopped = True
		self.logger.info('🛑 Agent stopped')

	# ============================================================================
	# MAIN EXECUTION METHODS
	# ============================================================================

	@observe(name='agent.run', metadata={'task': '{{task}}', 'debug': '{{debug}}'})
	@time_execution_async('--run')
	async def run(
		self,
		max_steps: int = 100,
		on_step_start: AgentHookFunc | None = None,
		on_step_end: AgentHookFunc | None = None,
	) -> AgentHistoryList[AgentStructuredOutput]:
		"""
		Execute the task with maximum number of steps.

		Args:
			max_steps: Maximum number of steps to execute
			on_step_start: Optional callback before each step
			on_step_end: Optional callback after each step

		Returns:
			AgentHistoryList with execution history
		"""
		agent_run_error: str | None = None
		loop = asyncio.get_event_loop()

		# Initialize telemetry and signal handling
		signal_handler = self._setup_signal_handling(loop, max_steps)

		try:
			# Log agent startup
			self.agent_logger.log_agent_run()

			# Main execution loop
			await self._execute_task_loop(max_steps, on_step_start, on_step_end)

		except Exception as e:
			agent_run_error = self._handle_run_error(e)

		finally:
			# Cleanup and finalization
			await self._finalize_run(signal_handler, max_steps, agent_run_error)

		return self.state.history

	async def take_step(self, step_info: AgentStepInfo | None = None) -> tuple[bool, bool]:
		"""
		Take a step

		Returns:
		        Tuple[bool, bool]: (is_done, is_valid)
		"""
		await self.step(step_info)

		if self.state.history.is_done():
			await self.log_completion()
			if self.register_done_callback:
				if inspect.iscoroutinefunction(self.register_done_callback):
					await self.register_done_callback(self.state.history)
				else:
					self.register_done_callback(self.state.history)
			return True, True

		return False, True  # Not done, but step was valid

	@observe(name='agent.step', ignore_output=True, ignore_input=True)
	@time_execution_async('--step')
	async def step(self, step_info: AgentStepInfo | None = None) -> None:
		"""Execute one step of the task"""
		browser_state_summary = None

		try:
			browser_state_summary = await self._prepare_step_context(step_info)

			await self._get_next_action(browser_state_summary, step_info)

			await self._take_actions()

		except Exception as e:
			await self._handle_step_error(e)

		finally:
			await self._finalize_step(browser_state_summary)

	# ============================================================================
	# STEP EXECUTION HELPERS
	# ============================================================================

	@time_execution_async('--prepare_step_context')
	async def _prepare_step_context(self, step_info: AgentStepInfo | None = None) -> BrowserStateSummary:
		"""Prepare the context for the step: browser state, action models, page actions"""

		self.step_start_time = time.time()
		assert self.browser_session is not None, 'BrowserSession is not set up'
		assert self._message_manager is not None, 'MessageManager is not initialized'

		self.logger.debug(f'🌐 Step {self.state.n_steps + 1}: Getting browser state...')
		browser_state_summary = await self._get_browser_state_with_recovery(cache_clickable_elements_hashes=True)
		current_page = await self.browser_session.get_current_page()

		self.agent_logger.log_step_context(current_page, browser_state_summary)
		await self._raise_if_stopped_or_paused()

		# Update action models with page-specific actions
		self.logger.debug(f'📝 Step {self.state.n_steps + 1}: Updating action models...')
		await self._update_action_models_for_page(current_page)

		# Get page-specific filtered actions
		page_filtered_actions = self.controller.registry.get_prompt_description(current_page)

		# If there are page-specific actions, add them as a special message for this step only
		if page_filtered_actions:
			page_action_message = f'For this page, these additional actions are available:\n{page_filtered_actions}'
			self._message_manager._add_message_with_type(UserMessage(content=page_action_message))

		self.logger.debug(f'💬 Step {self.state.n_steps + 1}: Adding state message to context...')
		self._message_manager.add_state_message(
			browser_state_summary=browser_state_summary,
			model_output=self.state.last_model_output,
			result=self.state.last_result,
			step_info=step_info,
			use_vision=self.settings.use_vision,
			page_filtered_actions=page_filtered_actions if page_filtered_actions else None,
			sensitive_data=self.sensitive_data,
			agent_history_list=self.state.history,  # Pass AgentHistoryList for screenshots
		)
		await self._handle_final_step(step_info)
		return browser_state_summary

	@time_execution_async('--get_next_action')
	async def get_model_output(self, input_messages: list[BaseMessage]) -> AgentOutput:
		"""Get next action from LLM based on current state"""

		response = await self.llm.ainvoke(input_messages, output_format=self.AgentOutput)
		parsed = response.completion

		# cut the number of actions to max_actions_per_step if needed
		if len(parsed.action) > self.settings.max_actions_per_step:
			parsed.action = parsed.action[: self.settings.max_actions_per_step]

		if not (hasattr(self.state, 'paused') and (self.state.paused or self.state.stopped)):
			log_response(parsed, self.controller.registry.registry, self.logger)

		self.agent_logger.log_next_action_summary(parsed)
		return parsed

	@time_execution_async('--get_model_output_with_retry')
	async def _get_model_output_with_retry(self, input_messages: list[BaseMessage]) -> AgentOutput:
		"""Get model output with retry logic for empty actions"""
		model_output = await self.get_model_output(input_messages)
		self.logger.debug(
			f'✅ Step {self.state.n_steps + 1}: Got LLM response with {len(model_output.action) if model_output.action else 0} actions'
		)

		if (
			not model_output.action
			or not isinstance(model_output.action, list)
			or all(action.model_dump() == {} for action in model_output.action)
		):
			self.logger.warning('Model returned empty action. Retrying...')

			clarification_message = UserMessage(
				content='You forgot to return an action. Please respond only with a valid JSON action according to the expected format.'
			)

			retry_messages = input_messages + [clarification_message]
			model_output = await self.get_model_output(retry_messages)

			if not model_output.action or all(action.model_dump() == {} for action in model_output.action):
				self.logger.warning('Model still returned empty after retry. Inserting safe noop action.')
				action_instance = self.ActionModel()
				setattr(
					action_instance,
					'done',
					{
						'success': False,
						'text': 'No next action returned by LLM!',
					},
				)
				model_output.action = [action_instance]

		return model_output

	@time_execution_async('--handle_post_llm_processing')
	async def _handle_post_llm_processing(
		self, browser_state_summary: BrowserStateSummary, input_messages: list[BaseMessage]
	) -> None:
		"""Handle callbacks and conversation saving after LLM interaction"""
		if self.register_new_step_callback and self.state.last_model_output:
			if inspect.iscoroutinefunction(self.register_new_step_callback):
				await self.register_new_step_callback(browser_state_summary, self.state.last_model_output, self.state.n_steps)
			else:
				self.register_new_step_callback(browser_state_summary, self.state.last_model_output, self.state.n_steps)

		if self.settings.save_conversation_path and self.state.last_model_output:
			# Treat save_conversation_path as a directory (consistent with other recording paths)
			conversation_dir = Path(self.settings.save_conversation_path)
			conversation_filename = f'conversation_{self.id}_{self.state.n_steps}.txt'
			target = conversation_dir / conversation_filename
			await save_conversation(
				input_messages,
				self.state.last_model_output,
				target,
				self.settings.save_conversation_path_encoding,
			)

	@time_execution_async('--take_actions')
	async def _take_actions(self) -> None:
		"""Execute the actions from model output"""
		assert self.state.last_model_output is not None, 'Model output is not available'

		self.logger.debug(f'⚡ Step {self.state.n_steps}: Executing {len(self.state.last_model_output.action)} actions...')
		result = await self.multi_act(self.state.last_model_output.action)
		self.logger.debug(f'✅ Step {self.state.n_steps}: Actions completed')

		self.state.last_result = result
		await self._handle_post_action_processing()

	@time_execution_async('--finalize_step')
	async def _finalize_step(self, browser_state_summary: BrowserStateSummary | None) -> None:
		"""Finalize the step with history, logging, and events"""
		step_end_time = time.time()
		step_start_time = self.step_start_time
		if not self.state.last_result:
			return

		if browser_state_summary:
			metadata = StepMetadata(
				step_number=self.state.n_steps,
				step_start_time=step_start_time,
				step_end_time=step_end_time,
			)

			# Create and store history item directly
			if self.state.last_model_output:
				interacted_elements = AgentHistory.get_interacted_element(
					self.state.last_model_output, browser_state_summary.selector_map
				)
			else:
				interacted_elements = [None]

			state_history = BrowserStateHistory(
				url=browser_state_summary.url,
				title=browser_state_summary.title,
				tabs=browser_state_summary.tabs,
				interacted_element=interacted_elements,
				screenshot=browser_state_summary.screenshot,
			)

			history_item = AgentHistory(
				model_output=self.state.last_model_output,
				result=self.state.last_result,
				state=state_history,
				metadata=metadata,
			)

			self.state.history.history.append(history_item)

		# Log step completion summary
		self.agent_logger.log_step_completion_summary(step_start_time, self.state.last_result)

		# Save file system state after step completion
		self.save_file_system_state()

		# Emit both step created and executed events
		if browser_state_summary and self.state.last_model_output:
			# Extract key step data for the event
			actions_data = []
			if self.state.last_model_output.action:
				for action in self.state.last_model_output.action:
					action_dict = action.model_dump() if hasattr(action, 'model_dump') else {}
					actions_data.append(action_dict)

			# Emit CreateAgentStepEvent
			step_event = CreateAgentStepEvent.from_agent_step(
				self, self.state.last_model_output, self.state.last_result, actions_data, browser_state_summary
			)
			self.eventbus.dispatch(step_event)

	@time_execution_async('--handle_post_action_processing')
	async def _handle_post_action_processing(self) -> None:
		"""Handle post-action processing like download tracking and result logging"""
		assert self.browser_session is not None, 'BrowserSession is not set up'

		# Check for new downloads after executing actions
		if self.has_downloads_path:
			try:
				current_downloads = self.browser_session.downloaded_files
				if current_downloads != self._last_known_downloads:
					self._update_available_file_paths(current_downloads)
					self._last_known_downloads = current_downloads
			except Exception as e:
				self.logger.debug(f'📁 Failed to check for new downloads: {type(e).__name__}: {e}')

		self.state.consecutive_failures = 0
		self.logger.debug(f'🔄 Step {self.state.n_steps}: Consecutive failures reset to: {self.state.consecutive_failures}')

		# Log completion results
		if self.state.last_result and len(self.state.last_result) > 0 and self.state.last_result[-1].is_done:
			self.logger.info(f'📄 Result: {self.state.last_result[-1].extracted_content}')
			if self.state.last_result[-1].attachments:
				self.logger.info('📎 Click links below to access the attachments:')
				for file_path in self.state.last_result[-1].attachments:
					self.logger.info(f'👉 {file_path}')

	@time_execution_async('--handle_step_error')
	async def _handle_step_error(self, error: Exception) -> None:
		"""Handle all types of errors that can occur during a step"""

		# Handle InterruptedError specifically (agent pause/stop)
		if isinstance(error, InterruptedError):
			self.logger.debug(f'InterruptedError: {type(error).__name__}: {error}')
			self.state.consecutive_failures += 1
			self.state.last_result = [
				ActionResult(
					error='The agent was interrupted mid-step' + (f' - {error}' if error else ''),
				)
			]
			return

		# Handle all other exceptions
		include_trace = self.logger.isEnabledFor(logging.DEBUG)
		error_msg = AgentError.format_error(error, include_trace=include_trace)
		prefix = f'❌ Result failed {self.state.consecutive_failures + 1}/{self.settings.max_failures} times:\n '
		self.state.consecutive_failures += 1

		if isinstance(error, (ValidationError, ValueError)):
			self.logger.error(f'{prefix}{error_msg}')
			if 'Max token limit reached' in error_msg:
				# cut tokens from history
				# self._message_manager.settings.max_input_tokens = self.settings.max_input_tokens - 500
				# self.logger.info(
				# 	f'Cutting tokens from history - new max input tokens: {self._message_manager.settings.max_input_tokens}'
				# )
				# TODO: figure out what to do here
				pass

				# no longer cutting messages, because we revamped the message manager
				# self._message_manager.cut_messages()
		elif 'Could not parse response' in error_msg or 'tool_use_failed' in error_msg:
			# give model a hint how output should look like
			logger.debug(f'Model: {self.llm.model} failed')
			error_msg += '\n\nReturn a valid JSON object with the required fields.'
			logger.error(f'{prefix}{error_msg}')

		else:
			from anthropic import RateLimitError as AnthropicRateLimitError
			from google.api_core.exceptions import ResourceExhausted
			from openai import RateLimitError

			# Define a tuple of rate limit error types for easier maintenance
			RATE_LIMIT_ERRORS = (
				RateLimitError,  # OpenAI
				ResourceExhausted,  # Google
				AnthropicRateLimitError,  # Anthropic
			)

			if isinstance(error, RATE_LIMIT_ERRORS) or 'on tokens per minute (TPM): Limit' in error_msg:
				logger.warning(f'{prefix}{error_msg}')
				await asyncio.sleep(self.settings.retry_delay)
			else:
				self.logger.error(f'{prefix}{error_msg}')

		self.state.last_result = [ActionResult(error=error_msg, include_in_memory=True)]

	@time_execution_async('--_get_browser_state_with_recovery')
	@observe_debug(name='get_browser_state_with_recovery')
	async def _get_browser_state_with_recovery(self, cache_clickable_elements_hashes: bool = True) -> BrowserStateSummary:
		"""Get browser state with multiple fallback strategies for error recovery"""

		assert self.browser_session is not None, 'BrowserSession is not set up'

		# Try to get state summary with fallback, handling agent-specific error state
		try:
			return await self.browser_session.get_state_summary_with_fallback(cache_clickable_elements_hashes)
		except Exception as e:
			# Update agent state with error information
			if self.state.last_result is None:
				self.state.last_result = []
			self.state.last_result.append(ActionResult(error=str(e)))
			self.logger.error(f'Both full and minimal state retrieval failed: {type(e).__name__}: {e}')
			raise  # Re-raise since we couldn't recover

	@time_execution_async('--_update_action_models_for_page')
	async def _update_action_models_for_page(self, page) -> None:
		"""Update action models with page-specific actions"""
		# Create new action model with current page's filtered actions
		self.ActionModel = self.controller.registry.create_action_model(page=page)
		# Update output model with the new actions
		if self.settings.use_thinking:
			self.AgentOutput = AgentOutput.type_with_custom_actions(self.ActionModel)
		else:
			self.AgentOutput = AgentOutput.type_with_custom_actions_no_thinking(self.ActionModel)

		# Update done action model too
		self.DoneActionModel = self.controller.registry.create_action_model(include_actions=['done'], page=page)
		if self.settings.use_thinking:
			self.DoneAgentOutput = AgentOutput.type_with_custom_actions(self.DoneActionModel)
		else:
			self.DoneAgentOutput = AgentOutput.type_with_custom_actions_no_thinking(self.DoneActionModel)

	@time_execution_async('--_raise_if_stopped_or_paused')
	async def _raise_if_stopped_or_paused(self) -> None:
		"""Utility function that raises an InterruptedError if the agent is stopped or paused."""

		if self.register_external_agent_status_raise_error_callback:
			if await self.register_external_agent_status_raise_error_callback():
				raise InterruptedError

		if self.state.stopped or self.state.paused:
			# self.logger.debug('Agent paused after getting state')
			raise InterruptedError

	@time_execution_async('--_handle_final_step')
	async def _handle_final_step(self, step_info: AgentStepInfo | None = None) -> None:
		"""Handle special processing for the last step"""
		assert self._message_manager is not None, 'MessageManager is not initialized'

		if step_info and step_info.is_last_step():
			# Add last step warning if needed
			msg = 'Now comes your last step. Use only the "done" action now. No other actions - so here your action sequence must have length 1.'
			msg += '\nIf the task is not yet fully finished as requested by the user, set success in "done" to false! E.g. if not all steps are fully completed.'
			msg += '\nIf the task is fully finished, set success in "done" to true.'
			msg += '\nInclude everything you found out for the ultimate task in the done text.'
			self.logger.info('Last step finishing up')
			self._message_manager._add_message_with_type(UserMessage(content=msg))
			self.AgentOutput = self.DoneAgentOutput

	@time_execution_async('--_get_next_action')
	async def _get_next_action(self, browser_state_summary: BrowserStateSummary, step_info: AgentStepInfo | None = None) -> None:
		"""Execute LLM interaction with retry logic and handle callbacks"""
		assert self._message_manager is not None, 'MessageManager is not initialized'

		input_messages = self._message_manager.get_messages()
		self.logger.debug(
			f'🤖 Step {self.state.n_steps + 1}: Calling LLM with {len(input_messages)} messages (model: {self.llm.model})...'
		)

		try:
			model_output = await self._get_model_output_with_retry(input_messages)
			self.state.last_model_output = model_output

			# Check again for paused/stopped state after getting model output
			await self._raise_if_stopped_or_paused()

			self.state.n_steps += 1

			# Handle callbacks and conversation saving
			await self._handle_post_llm_processing(browser_state_summary, input_messages)

			self._message_manager._remove_last_state_message()  # we dont want the whole state in the chat history

			# check again if Ctrl+C was pressed before we commit the output to history
			await self._raise_if_stopped_or_paused()

		except Exception as e:
			# model call failed, remove last state message from history
			self._message_manager._remove_last_state_message()
			self.logger.error(f'❌ Step {self.state.n_steps + 1}: LLM call failed: {type(e).__name__}: {e}')
			raise e

	def _setup_signal_handling(self, loop: asyncio.AbstractEventLoop, max_steps: int):
		"""Setup signal handling for graceful shutdown"""
		from browser_use.utils import SignalHandler

		def on_force_exit_log_telemetry():
			self.agent_logger.log_agent_event(max_steps=max_steps, agent_run_error='SIGINT: Cancelled by user')
			if hasattr(self, 'telemetry') and self.telemetry:
				self.telemetry.flush()
			self._force_exit_telemetry_logged = True

		return SignalHandler(
			loop=loop,
			pause_callback=self.pause,
			resume_callback=self.resume,
			custom_exit_callback=on_force_exit_log_telemetry,
			exit_on_second_int=True,
		)

	@time_execution_async('--_execute_task_loop')
	async def _execute_task_loop(
		self,
		max_steps: int,
		on_step_start: AgentHookFunc | None = None,
		on_step_end: AgentHookFunc | None = None,
	) -> None:
		"""Execute the main task loop with step hooks"""
		for current_step in range(max_steps):
			await self._execute_single_step(current_step, max_steps, on_step_start, on_step_end)

			# Check if task is completed
			if self.state.history.is_done():
				self.logger.info(f'🎯 Task completed successfully in {current_step + 1} steps')
				break

			# Check for too many consecutive failures
			if self.state.consecutive_failures >= self.settings.max_failures:
				self.logger.error(f'❌ Task failed after {self.settings.max_failures} consecutive failures')
				break
		else:
			# Max steps reached without completion
			self.logger.warning(f'⏰ Max steps ({max_steps}) reached without task completion')

	@time_execution_async('--_execute_single_step')
	async def _execute_single_step(
		self,
		current_step: int,
		max_steps: int,
		on_step_start: AgentHookFunc | None = None,
		on_step_end: AgentHookFunc | None = None,
	) -> None:
		"""Execute a single step with proper error handling and hooks"""
		step_info = AgentStepInfo(step_number=current_step + 1, max_steps=max_steps)

		try:
			# Pre-step hook
			if on_step_start:
				await on_step_start(self)

			# Execute the step
			is_done, is_valid = await self.take_step(step_info)

			if not is_valid:
				self.logger.warning(f'⚠️ Step {current_step + 1} was invalid')

			# Post-step hook
			if on_step_end:
				await on_step_end(self)

		except InterruptedError:
			self.logger.info('🛑 Agent execution interrupted by user')
			raise
		except Exception as e:
			self.logger.error(f'❌ Step {current_step + 1} failed: {type(e).__name__}: {e}')
			raise

	@time_execution_sync('--_handle_run_error')
	def _handle_run_error(self, error: Exception) -> str:
		"""Handle and log run-level errors"""
		error_msg = str(error)

		if isinstance(error, InterruptedError):
			self.logger.info('🛑 Agent run interrupted')
			error_msg = 'SIGINT: Cancelled by user'
		else:
			self.logger.error(f'❌ Agent run failed: {type(error).__name__}: {error}')
			error_msg = f'{type(error).__name__}: {error}'

		return error_msg

	@time_execution_async('--_finalize_run')
	async def _finalize_run(
		self,
		signal_handler: SignalHandler,
		max_steps: int,
		agent_run_error: str | None = None,
	) -> None:
		"""Finalize the run with cleanup and telemetry"""
		try:
			# Cleanup signal handler
			signal_handler.unregister()  # type: ignore

			# Log telemetry if not already done
			if not getattr(self, '_force_exit_telemetry_logged', False):
				self.agent_logger.log_agent_event(max_steps=max_steps, agent_run_error=agent_run_error)

			# Generate GIF if requested
			await self._generate_gif_if_requested()

			# Handle completion callback
			if self.register_done_callback and self.state.history.is_done():
				if inspect.iscoroutinefunction(self.register_done_callback):
					await self.register_done_callback(self.state.history)
				else:
					self.register_done_callback(self.state.history)

		except Exception as e:
			self.logger.error(f'Error during run finalization: {e}')

	@time_execution_async('--_generate_gif_if_requested')
	async def _generate_gif_if_requested(self) -> None:
		"""Generate GIF from history if requested"""
		if not self.settings.generate_gif or not self.state.history.history:
			return

		try:
			gif_path = self.settings.generate_gif if isinstance(self.settings.generate_gif, str) else 'agent_history.gif'
			create_history_gif(self.task, self.state.history, gif_path)
			self.logger.info(f'🎬 GIF saved to {gif_path}')
		except Exception as e:
			self.logger.warning(f'Failed to generate GIF: {e}')

	@time_execution_async('--multi_act')
	@observe_debug()
	async def multi_act(
		self,
		actions: list[ActionModel],
		check_for_new_elements: bool = True,
	) -> list[ActionResult]:
		"""Execute multiple actions"""
		results: list[ActionResult] = []

		assert self.browser_session is not None, 'BrowserSession is not set up'
		cached_selector_map = await self.browser_session.get_selector_map()
		cached_path_hashes = {e.hash.branch_path_hash for e in cached_selector_map.values()}

		await self.browser_session.remove_highlights()

		for i, action in enumerate(actions):
			# DO NOT ALLOW TO CALL `done` AS A SINGLE ACTION
			if i > 0 and action.model_dump(exclude_unset=True).get('done') is not None:
				msg = f'Done action is allowed only as a single action - stopped after action {i} / {len(actions)}.'
				logger.info(msg)
				break

			if action.get_index() is not None and i != 0:
				new_browser_state_summary = await self.browser_session.get_state_summary(cache_clickable_elements_hashes=False)
				new_selector_map = new_browser_state_summary.selector_map

				# Detect index change after previous action
				orig_target = cached_selector_map.get(action.get_index())  # type: ignore
				orig_target_hash = orig_target.hash.branch_path_hash if orig_target else None
				new_target = new_selector_map.get(action.get_index())  # type: ignore
				new_target_hash = new_target.hash.branch_path_hash if new_target else None
				if orig_target_hash != new_target_hash:
					msg = f'Element index changed after action {i} / {len(actions)}, because page changed.'
					logger.info(msg)
					results.append(
						ActionResult(
							extracted_content=msg,
							include_in_memory=True,
							long_term_memory=msg,
						)
					)
					break

				new_path_hashes = {e.hash.branch_path_hash for e in new_selector_map.values()}
				if check_for_new_elements and not new_path_hashes.issubset(cached_path_hashes):
					# next action requires index but there are new elements on the page
					msg = f'Something new appeared after action {i} / {len(actions)}, following actions are NOT executed and should be retried.'
					logger.info(msg)
					results.append(
						ActionResult(
							extracted_content=msg,
							include_in_memory=True,
							long_term_memory=msg,
						)
					)
					break

			try:
				await self._raise_if_stopped_or_paused()

				result = await self.controller.act(
					action=action,
					browser_session=self.browser_session,
					file_system=self.file_system,
					page_extraction_llm=self.settings.page_extraction_llm,
					sensitive_data=self.sensitive_data,
					available_file_paths=self.settings.available_file_paths,
					context=self.context,
				)

				results.append(result)

				# Get action name from the action model
				action_data = action.model_dump(exclude_unset=True)
				action_name = next(iter(action_data.keys())) if action_data else 'unknown'
				action_params = getattr(action, action_name, '')
				self.logger.info(f'☑️ Executed action {i + 1}/{len(actions)}: {action_name}({action_params})')
				if results[-1].is_done or results[-1].error or i == len(actions) - 1:
					break

				await asyncio.sleep(self.browser_profile.wait_between_actions)
				# hash all elements. if it is a subset of cached_state its fine - else break (new elements on page)

			except Exception as e:
				# Handle any exceptions during action execution
				self.logger.error(f'Action {i + 1} failed: {type(e).__name__}: {e}')
				raise e

		return results

	@time_execution_async('--log_completion')
	async def log_completion(self) -> None:
		"""Log the completion of the task"""
		if self.state.history.is_successful():
			self.logger.info('✅ Task completed successfully')
		else:
			self.logger.info('❌ Task completed without success')

	@time_execution_async('--rerun_history')
	async def rerun_history(
		self,
		history: AgentHistoryList,
		max_retries: int = 3,
		skip_failures: bool = True,
		delay_between_actions: float = 2.0,
	) -> list[ActionResult]:
		"""Rerun a saved history of actions with error handling and retry logic"""
		return await self.history_replay_service.rerun_history(history, max_retries, skip_failures, delay_between_actions)

	@time_execution_async('--load_and_rerun')
	async def load_and_rerun(self, history_file: str | Path | None = None, **kwargs) -> list[ActionResult]:
		"""Load history from file and rerun it"""
		return await self.history_replay_service.load_and_rerun(history_file, **kwargs)

	@time_execution_sync('--save_history')
	def save_history(self, file_path: str | Path | None = None) -> None:
		"""Save the history to a file"""
		if not file_path:
			file_path = 'AgentHistory.json'
		self.state.history.save_to_file(file_path)

	@time_execution_sync('--_convert_initial_actions')
	def _convert_initial_actions(self, actions: list[dict[str, dict[str, Any]]] | None) -> list[ActionModel] | None:
		"""Convert initial actions from dict format to ActionModel format"""
		return self.agent_utils.convert_initial_actions(actions)

	@time_execution_sync('--_verify_and_setup_llm')
	def _verify_and_setup_llm(self) -> bool:
		"""Verify that the LLM API keys are setup and the LLM API is responding properly"""
		return self.agent_utils.verify_and_setup_llm()

	@time_execution_async('--close')
	async def close(self):
		"""Close all resources"""
		try:
			# First close browser resources
			assert self.browser_session is not None, 'BrowserSession is not set up'
			await self.browser_session.stop()

			# Force garbage collection
			gc.collect()

		except Exception as e:
			self.logger.error(f'Error during cleanup: {e}')
