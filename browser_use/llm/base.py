"""
We have switched all of our code from langchain to openai.types.chat.chat_completion_message_param.

For easier transition we have
"""

import asyncio
import logging
from typing import Any, Callable, Protocol, TypeVar, overload

from pydantic import BaseModel

from browser_use.llm.messages import BaseMessage
from browser_use.llm.views import ChatInvokeCompletion

T = TypeVar('T', bound=BaseModel)

logger = logging.getLogger(__name__)


async def exponential_backoff_retry(
	func: Callable,
	rate_limit_error_types: tuple,
	max_retries: int = 10,
	initial_delay: float = 1.0,
	exponential_base: float = 2.0,
	max_delay: float = 300.0,
) -> Any:
	"""
	Retry a function with exponential backoff when encountering rate limit errors.
	
	Args:
		func: The function to retry
		rate_limit_error_types: Tuple of exception types that indicate rate limiting
		max_retries: Maximum number of retry attempts (default: 10)
		initial_delay: Initial delay in seconds (default: 1.0)
		exponential_base: Base for exponential backoff (default: 2.0)
		max_delay: Maximum delay between retries in seconds (default: 300.0)
	
	Returns:
		The result of the function call
	
	Raises:
		The last exception encountered if all retries fail
	"""
	last_exception = None
	
	for attempt in range(max_retries + 1):  # +1 because first attempt is not a retry
		try:
			return await func()
		except rate_limit_error_types as e:
			last_exception = e
			
			if attempt == max_retries:
				logger.error(f"Rate limit retry failed after {max_retries} attempts: {e}")
				raise
			
			# Calculate delay with exponential backoff
			delay = min(initial_delay * (exponential_base ** attempt), max_delay)
			
			logger.warning(
				f"Rate limit error (attempt {attempt + 1}/{max_retries + 1}): {e}. "
				f"Retrying in {delay:.1f} seconds..."
			)
			
			await asyncio.sleep(delay)
		
		except Exception as e:
			# For non-rate-limit errors, don't retry
			raise e
	
	# This should never be reached due to the logic above, but just in case
	if last_exception:
		raise last_exception


class BaseChatModel(Protocol):
	_verified_api_keys: bool = False

	model: str

	@property
	def provider(self) -> str: ...

	@property
	def name(self) -> str: ...

	@property
	def model_name(self) -> str:
		# for legacy support
		return self.model

	@overload
	async def ainvoke(self, messages: list[BaseMessage], output_format: None = None) -> ChatInvokeCompletion[str]: ...

	@overload
	async def ainvoke(self, messages: list[BaseMessage], output_format: type[T]) -> ChatInvokeCompletion[T]: ...

	async def ainvoke(
		self, messages: list[BaseMessage], output_format: type[T] | None = None
	) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]: ...

	@classmethod
	def __get_pydantic_core_schema__(
		cls,
		source_type: type,
		handler: Any,
	) -> Any:
		"""
		Allow this Protocol to be used in Pydantic models -> very useful to typesafe the agent settings for example.
		Returns a schema that allows any object (since this is a Protocol).
		"""
		from pydantic_core import core_schema

		# Return a schema that accepts any object for Protocol types
		return core_schema.any_schema()
