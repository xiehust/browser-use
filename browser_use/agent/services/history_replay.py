"""
History replay service for re-executing agent actions from saved histories.

This module provides functionality to replay agent execution histories with error
handling, retry logic, and action index updating for changed DOM structures.
"""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from browser_use.agent.views import ActionResult, AgentHistory, AgentHistoryList
from browser_use.browser.views import BrowserStateSummary
from browser_use.controller.registry.views import ActionModel
from browser_use.dom.history_tree_processor.service import (
	DOMHistoryElement,
	HistoryTreeProcessor,
)

if TYPE_CHECKING:
	from browser_use.agent.service import Agent


class HistoryReplayService:
	"""Service for replaying agent execution histories"""

	def __init__(self, agent: 'Agent'):
		self.agent = agent
		self.history_tree_processor = HistoryTreeProcessor()

	async def rerun_history(
		self,
		history: AgentHistoryList,
		max_retries: int = 3,
		skip_failures: bool = True,
		delay_between_actions: float = 2.0,
	) -> list[ActionResult]:
		"""
		Rerun a saved history of actions with error handling and retry logic.

		Args:
		    history: The history to replay
		    max_retries: Maximum number of retries per action
		    skip_failures: Whether to skip failed actions or stop execution
		    delay_between_actions: Delay between actions in seconds

		Returns:
		    List of action results
		"""
		# Execute initial actions if provided
		if self.agent.initial_actions:
			result = await self.agent.multi_act(self.agent.initial_actions)
			self.agent.state.last_result = result

		results = []

		for i, history_item in enumerate(history.history):
			goal = history_item.model_output.current_state.next_goal if history_item.model_output else ''
			self.agent.logger.info(f'Replaying step {i + 1}/{len(history.history)}: goal: {goal}')

			if (
				not history_item.model_output
				or not history_item.model_output.action
				or history_item.model_output.action == [None]
			):
				self.agent.logger.warning(f'Step {i + 1}: No action to replay, skipping')
				results.append(ActionResult(error='No action to replay'))
				continue

			retry_count = 0
			while retry_count < max_retries:
				try:
					result = await self._execute_history_step(history_item, delay_between_actions)
					results.extend(result)
					break

				except Exception as e:
					retry_count += 1
					if retry_count == max_retries:
						error_msg = f'Step {i + 1} failed after {max_retries} attempts: {str(e)}'
						self.agent.logger.error(error_msg)
						if skip_failures:
							results.append(ActionResult(error=error_msg))
							break
						else:
							raise e
					else:
						self.agent.logger.warning(f'Step {i + 1} failed, retrying {retry_count + 1}/{max_retries}: {str(e)}')
						await asyncio.sleep(1.0)  # Brief delay before retry

		return results

	async def _execute_history_step(self, history_item: AgentHistory, delay: float) -> list[ActionResult]:
		"""Execute a single step from history with action index updating"""
		if not history_item.model_output or not history_item.model_output.action:
			return [ActionResult(error='No action in history item')]

		browser_state_summary = await self.agent._get_browser_state_with_recovery()

		# Update action indices for current DOM state
		updated_actions = []
		for action in history_item.model_output.action:
			if action.get_index() is not None:
				# Find the historical element for this action
				historical_element = None
				if history_item.state and history_item.state.interacted_element:
					for element in history_item.state.interacted_element:
						if element and getattr(element, 'get_index', lambda: None)() == action.get_index():
							historical_element = element
							break

				updated_action = await self._update_action_indices(historical_element, action, browser_state_summary)
				if updated_action:
					updated_actions.append(updated_action)
				else:
					self.agent.logger.warning(f'Could not update action index for action: {action}')
					# Use original action as fallback
					updated_actions.append(action)
			else:
				# Action doesn't need index updating
				updated_actions.append(action)

		# Execute the updated actions
		result = await self.agent.multi_act(updated_actions)
		await asyncio.sleep(delay)
		return result

	async def _update_action_indices(
		self,
		historical_element: DOMHistoryElement | None,
		action: ActionModel,
		browser_state_summary: BrowserStateSummary,
	) -> ActionModel | None:
		"""Update action indices based on current DOM state"""
		if not historical_element:
			self.agent.logger.warning('No historical element provided for index updating')
			return action

		# Find matching element in current DOM
		current_elements = browser_state_summary.selector_map

		# Try to find element by matching properties
		best_match_index = None
		best_match_score = 0

		for current_index, current_element in current_elements.items():
			# Calculate similarity score based on element properties
			score = 0

			# Tag name match (high weight)
			if current_element.tag_name == getattr(historical_element, 'tag_name', ''):
				score += 50

			# Text content match - use safer attribute access
			hist_text = (
				getattr(historical_element, 'text', None)
				or getattr(historical_element, 'get_all_text_till_next_clickable_element', lambda **kwargs: '')()
			)
			curr_text = (
				getattr(current_element, 'text', None)
				or getattr(current_element, 'get_all_text_till_next_clickable_element', lambda **kwargs: '')()
			)

			if hist_text and curr_text:
				if hist_text.strip() == curr_text.strip():
					score += 30
				elif hist_text.strip() in curr_text.strip():
					score += 15

			# Attributes match - use safer attribute access
			hist_attrs = getattr(historical_element, 'attributes', {}) or {}
			curr_attrs = getattr(current_element, 'attributes', {}) or {}

			for attr_name in ['id', 'class', 'name', 'type']:
				if attr_name in hist_attrs and attr_name in curr_attrs:
					if hist_attrs[attr_name] == curr_attrs[attr_name]:
						score += 20 if attr_name == 'id' else 10

			# Update best match if this score is higher
			if score > best_match_score:
				best_match_score = score
				best_match_index = current_index

		if best_match_index is not None and best_match_score > 40:  # Minimum confidence threshold
			# Create updated action with new index
			action_dict = action.model_dump()
			action_name = next(iter(action_dict.keys()))
			action_params = action_dict[action_name]

			if isinstance(action_params, dict) and 'index' in action_params:
				action_params['index'] = best_match_index

				# Recreate the action model with updated index
				updated_action = type(action)(**action_dict)
				self.agent.logger.info(f'Updated action index from {action.get_index()} to {best_match_index}')
				return updated_action

		self.agent.logger.warning(f'Could not find suitable match for historical element (best score: {best_match_score})')
		return action

	async def load_and_rerun(self, history_file: str | Path | None = None, **kwargs) -> list[ActionResult]:
		"""Load history from file and rerun it"""
		if history_file is None:
			history_file = 'agent_history.json'

		history_path = Path(history_file)
		if not history_path.exists():
			raise FileNotFoundError(f'History file not found: {history_path}')

		# Load history from file
		history = AgentHistoryList.model_validate_json(history_path.read_text())

		self.agent.logger.info(f'Loading and rerunning history from {history_path}')
		return await self.rerun_history(history, **kwargs)
