"""
Agent logging service for structured logging of agent execution.

This module provides centralized logging functionality for the browser-use agent,
including step context, action summaries, completion stats, and telemetry events.
"""

import json
import logging
import time
from typing import TYPE_CHECKING

from browser_use.agent.views import ActionResult, AgentOutput
from browser_use.telemetry.views import AgentTelemetryEvent

if TYPE_CHECKING:
	from browser_use.agent.service import Agent


class AgentLogger:
	"""Centralized logging service for agent execution"""

	def __init__(self, agent: 'Agent'):
		self.agent = agent

	def log_agent_run(self) -> None:
		"""Log the agent run start"""
		self.agent.logger.info(f'🚀 Starting task: {self.agent.task}')
		self.agent.logger.debug(f'🤖 Browser-Use Library Version {self.agent.version} ({self.agent.source})')

	def log_step_context(self, current_page, browser_state_summary) -> None:
		"""Log step context information"""
		url_short = current_page.url[:50] + '...' if len(current_page.url) > 50 else current_page.url
		interactive_count = len(browser_state_summary.selector_map) if browser_state_summary else 0
		self.agent.logger.info(
			f'📍 Step {self.agent.state.n_steps}: Evaluating page with {interactive_count} interactive elements on: {url_short}'
		)

	def log_next_action_summary(self, parsed: AgentOutput) -> None:
		"""Log a comprehensive summary of the next action(s)"""
		if not self.agent.logger.isEnabledFor(logging.DEBUG):
			return

		# Safe access to actions
		actions = getattr(parsed, 'action', None)
		if not actions or not hasattr(actions, '__iter__') or not hasattr(actions, '__len__'):
			return

		action_count = len(actions)
		if action_count == 0:
			return

		# Collect action details
		action_details = []
		for i, action in enumerate(actions):
			if not hasattr(action, 'model_dump'):
				continue

			action_data = action.model_dump(exclude_unset=True)
			action_name = next(iter(action_data.keys())) if action_data else 'unknown'
			action_params = action_data.get(action_name, {}) if action_data else {}

			# Format key parameters concisely
			param_summary = []
			if isinstance(action_params, dict):
				for key, value in action_params.items():
					if key == 'index':
						param_summary.append(f'#{value}')
					elif key == 'text' and isinstance(value, str):
						text_preview = value[:30] + '...' if len(value) > 30 else value
						param_summary.append(f'text="{text_preview}"')
					elif key == 'url':
						param_summary.append(f'url="{value}"')
					elif key == 'success':
						param_summary.append(f'success={value}')
					elif isinstance(value, (str, int, bool)):
						val_str = str(value)[:30] + '...' if len(str(value)) > 30 else str(value)
						param_summary.append(f'{key}={val_str}')

			param_str = f'({", ".join(param_summary)})' if param_summary else ''
			action_details.append(f'{action_name}{param_str}')

		if not action_details:
			return

		# Create summary based on single vs multi-action
		if action_count == 1:
			first_action = list(actions)[0]
			if hasattr(first_action, 'model_dump'):
				action_data = first_action.model_dump(exclude_unset=True)
				action_name = next(iter(action_data.keys())) if action_data else 'unknown'
			else:
				action_name = 'unknown'
			param_str = action_details[0].split('(', 1)[1].rstrip(')') if '(' in action_details[0] else ''
			param_str = f'({param_str})' if param_str else ''
			self.agent.logger.info(f'☝️ Decided next action: {action_name}{param_str}')
		else:
			summary_lines = [f'✌️ Decided next {action_count} multi-actions:']
			for i, detail in enumerate(action_details):
				summary_lines.append(f'          {i + 1}. {detail}')
			self.agent.logger.info('\n'.join(summary_lines))

	def log_step_completion_summary(self, step_start_time: float, result: list[ActionResult]) -> None:
		"""Log step completion summary with action count, timing, and success/failure stats"""
		if not result:
			return

		step_duration = time.time() - step_start_time
		action_count = len(result)

		# Count success and failures
		success_count = sum(1 for r in result if not r.error)
		failure_count = action_count - success_count

		# Format success/failure indicators
		success_indicator = f'✅ {success_count}' if success_count > 0 else ''
		failure_indicator = f'❌ {failure_count}' if failure_count > 0 else ''
		status_parts = [part for part in [success_indicator, failure_indicator] if part]
		status_str = ' | '.join(status_parts) if status_parts else '✅ 0'

		self.agent.logger.info(
			f'📍 Step {self.agent.state.n_steps}: Ran {action_count} actions in {step_duration:.2f}s: {status_str}'
		)

	def log_agent_event(self, max_steps: int, agent_run_error: str | None = None) -> None:
		"""Send the agent event for this run to telemetry"""

		token_summary = self.agent.token_cost_service.get_usage_tokens_for_model(self.agent.llm.model)

		# Prepare action_history data correctly
		action_history_data = []
		for item in self.agent.state.history.history:
			if item.model_output and item.model_output.action:
				# Convert each ActionModel in the step to its dictionary representation
				step_actions = [
					action.model_dump(exclude_unset=True)
					for action in item.model_output.action
					if action  # Ensure action is not None if list allows it
				]
				action_history_data.append(step_actions)
			else:
				# Append None or [] if a step had no actions or no model output
				action_history_data.append(None)

		final_res = self.agent.state.history.final_result()
		final_result_str = json.dumps(final_res) if final_res is not None else None

		self.agent.telemetry.capture(
			AgentTelemetryEvent(
				task=self.agent.task,
				model=self.agent.llm.model,
				model_provider=self.agent.llm.provider,
				planner_llm=self.agent.settings.planner_llm.model if self.agent.settings.planner_llm else None,
				max_steps=max_steps,
				max_actions_per_step=self.agent.settings.max_actions_per_step,
				use_vision=self.agent.settings.use_vision,
				use_validation=self.agent.settings.validate_output,
				version=self.agent.version or 'unknown',
				source=self.agent.source or 'unknown',
				action_errors=self.agent.state.history.errors(),
				action_history=action_history_data,
				urls_visited=self.agent.state.history.urls(),
				steps=self.agent.state.n_steps,
				total_input_tokens=token_summary.prompt_tokens,
				total_duration_seconds=self.agent.state.history.total_duration_seconds(),
				success=self.agent.state.history.is_successful(),
				final_result_response=final_result_str,
				error_message=agent_run_error,
			)
		)
