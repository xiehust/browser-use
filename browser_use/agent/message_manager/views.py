from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from browser_use.llm.messages import BaseMessage

if TYPE_CHECKING:
	pass


class HistoryItem(BaseModel):
	"""Represents a single agent history item with its data and string representation"""

	step_number: int | None = None
	evaluation_previous_goal: str | None = None
	memory: str | None = None
	next_goal: str | None = None
	action_results: str | None = None
	error: str | None = None
	system_message: str | None = None

	model_config = ConfigDict(arbitrary_types_allowed=True)

	def model_post_init(self, __context) -> None:
		"""Validate that error and system_message are not both provided"""
		if self.error is not None and self.system_message is not None:
			raise ValueError('Cannot have both error and system_message at the same time')

	def to_string(self) -> str:
		"""Get string representation of the history item"""
		# Handle error case
		if self.error:
			step_str = f'step_{self.step_number}' if self.step_number is not None else 'step_unknown'
			return f'<{step_str}>\n{self.error}\n</{step_str}>'
		
		# Handle system message case
		if self.system_message:
			return f'<sys>\n{self.system_message}\n</sys>'
		
		# Handle regular step case
		step_str = f'step_{self.step_number}' if self.step_number is not None else 'step_unknown'
		
		content_parts = []
		if self.evaluation_previous_goal:
			content_parts.append(f'Evaluation of Previous Step: {self.evaluation_previous_goal}')
		if self.memory:
			content_parts.append(f'Memory: {self.memory}')
		if self.next_goal:
			content_parts.append(f'Next Goal: {self.next_goal}')
		if self.action_results:
			content_parts.append(self.action_results)
		
		content = '\n'.join(content_parts)
		return f'<{step_str}>\n{content}\n</{step_str}>'


class MessageHistory(BaseModel):
	"""History of messages"""

	system_message: BaseMessage | None = None
	state_message: BaseMessage | None = None
	consistent_messages: list[BaseMessage] = Field(default_factory=list)
	model_config = ConfigDict(arbitrary_types_allowed=True)

	def get_messages(self) -> list[BaseMessage]:
		"""Get all messages in order"""
		messages = []
		if self.system_message:
			messages.append(self.system_message)
		if self.state_message:
			messages.append(self.state_message)
		messages.extend(self.consistent_messages)
		return messages

	def clear_state_message(self) -> None:
		"""Clear the state message"""
		self.state_message = None

	def add_consistent_message(self, message: BaseMessage) -> None:
		"""Add a message to consistent messages"""
		self.consistent_messages.append(message)


class MessageManagerState(BaseModel):
	"""Holds the state for MessageManager"""

	history: MessageHistory = Field(default_factory=MessageHistory)
	tool_id: int = 1
	agent_history_items: list[HistoryItem] = Field(
		default_factory=lambda: [HistoryItem(step_number=0, system_message='Agent initialized')]
	)
	read_state_description: str = ''

	model_config = ConfigDict(arbitrary_types_allowed=True)
