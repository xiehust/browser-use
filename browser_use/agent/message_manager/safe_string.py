"""Safe string wrapper classes for protecting certain content from secret masking."""

from typing import Any


class SafeString:
	"""String wrapper that should not be subjected to secret masking.
	
	Used for system-generated content like DOM element indices that might
	accidentally match secret values but should never be masked.
	"""
	
	def __init__(self, value: str):
		self._value = value
	
	@property
	def value(self) -> str:
		return self._value
	
	def __str__(self) -> str:
		return self._value
	
	def __repr__(self) -> str:
		return f"SafeString({self._value!r})"
	
	def __add__(self, other: Any) -> 'MessagePart':
		if isinstance(other, SafeString):
			return MessagePart([self, other])
		elif isinstance(other, UnsafeString):
			return MessagePart([self, other])
		elif isinstance(other, MessagePart):
			return MessagePart([self] + other.parts)  # type: ignore
		elif isinstance(other, str):
			return MessagePart([self, UnsafeString(other)])
		else:
			raise TypeError(f"Cannot add SafeString to {type(other)}")
	
	def __radd__(self, other: Any) -> 'MessagePart':
		if isinstance(other, str):
			return MessagePart([UnsafeString(other), self])
		else:
			raise TypeError(f"Cannot add {type(other)} to SafeString")


class UnsafeString:
	"""String wrapper for content that should be subjected to secret masking.
	
	Used for user-provided content and other data that may contain sensitive
	values that need to be masked.
	"""
	
	def __init__(self, value: str):
		self._value = value
	
	@property
	def value(self) -> str:
		return self._value
	
	def __str__(self) -> str:
		return self._value
	
	def __repr__(self) -> str:
		return f"UnsafeString({self._value!r})"
	
	def __add__(self, other: Any) -> 'MessagePart':
		if isinstance(other, SafeString):
			return MessagePart([self, other])
		elif isinstance(other, UnsafeString):
			return MessagePart([self, other])
		elif isinstance(other, MessagePart):
			return MessagePart([self] + other.parts)  # type: ignore
		elif isinstance(other, str):
			return MessagePart([self, UnsafeString(other)])
		else:
			raise TypeError(f"Cannot add UnsafeString to {type(other)}")
	
	def __radd__(self, other: Any) -> 'MessagePart':
		if isinstance(other, str):
			return MessagePart([UnsafeString(other), self])
		else:
			raise TypeError(f"Cannot add {type(other)} to UnsafeString")


class MessagePart:
	"""Container for a sequence of SafeString and UnsafeString parts.
	
	Allows building up complex messages while preserving the safe/unsafe
	boundaries for proper secret masking.
	"""
	
	def __init__(self, parts: list[SafeString | UnsafeString]):
		self.parts = parts
	
	def __add__(self, other: Any) -> 'MessagePart':
		if isinstance(other, SafeString):
			return MessagePart(self.parts + [other])
		elif isinstance(other, UnsafeString):
			return MessagePart(self.parts + [other])
		elif isinstance(other, MessagePart):
			return MessagePart(self.parts + other.parts)
		elif isinstance(other, str):
			return MessagePart(self.parts + [UnsafeString(other)])
		else:
			raise TypeError(f"Cannot add MessagePart to {type(other)}")
	
	def __radd__(self, other: Any) -> 'MessagePart':
		if isinstance(other, str):
			return MessagePart([UnsafeString(other)] + self.parts)
		else:
			raise TypeError(f"Cannot add {type(other)} to MessagePart")
	
	def __str__(self) -> str:
		return ''.join(str(part) for part in self.parts)
	
	def __repr__(self) -> str:
		return f"MessagePart({self.parts!r})"
	
	def apply_secret_masking(self, sensitive_values: dict[str, str]) -> str:
		"""Apply secret masking only to UnsafeString parts."""
		result = []
		for part in self.parts:
			if isinstance(part, SafeString):
				result.append(part.value)
			elif isinstance(part, UnsafeString):
				masked_value = part.value
				for key, val in sensitive_values.items():
					masked_value = masked_value.replace(val, f'<secret>{key}</secret>')
				result.append(masked_value)
		return ''.join(result)