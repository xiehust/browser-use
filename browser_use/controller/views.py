from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


# Action Input Models
class SearchGoogleAction(BaseModel):
	query: str


class GoToUrlAction(BaseModel):
	url: str
	new_tab: bool = False  # True to open in new tab, False to navigate in current tab


class ClickElementAction(BaseModel):
	index: int
	new_tab: bool = Field(default=False, description='set True to open any resulting navigation in a new tab, False otherwise')
	# expect_download: bool = Field(default=False, description='set True if expecting a download, False otherwise')  # moved to downloads_watchdog.py
	# click_count: int = 1  # TODO


class ClickElementByTextAction(BaseModel):
	"""Click element by visible text content - more reliable than index-based clicking"""

	text: str = Field(description='Visible text content of the element to click')
	tag_name: str | None = Field(default=None, description="Optional tag name to narrow down search (e.g. 'button', 'a', 'div')")
	new_tab: bool = Field(default=False, description='set True to open any resulting navigation in a new tab, False otherwise')


class ClickElementBySelectorAction(BaseModel):
	"""Click element by CSS selector or attribute - for more precise targeting"""

	selector: str = Field(description='CSS selector, role, aria-label, or attribute to target element')
	new_tab: bool = Field(default=False, description='set True to open any resulting navigation in a new tab, False otherwise')


class InputTextAction(BaseModel):
	index: int
	text: str


class InputTextByLabelAction(BaseModel):
	"""Input text into field by label text or placeholder - more reliable than index"""

	label_text: str = Field(description='Label text, placeholder text, or aria-label of the input field')
	text: str = Field(description='Text to input into the field')


class WaitForConditionAction(BaseModel):
	"""Enhanced wait action that waits for specific page conditions"""

	condition_type: str = Field(
		description="Type of condition to wait for: 'url_contains', 'selector_visible', 'text_present', 'network_idle', 'page_loaded'"
	)
	condition_value: str | None = Field(
		default=None, description='Value to wait for (URL fragment, selector, text content, etc.)'
	)
	timeout_seconds: int = Field(default=10, description='Maximum time to wait in seconds')


class DoneAction(BaseModel):
	text: str
	success: bool
	files_to_display: list[str] | None = []


T = TypeVar('T', bound=BaseModel)


class StructuredOutputAction(BaseModel, Generic[T]):
	success: bool = True
	data: T


class SwitchTabAction(BaseModel):
	page_id: int


class CloseTabAction(BaseModel):
	page_id: int


class ScrollAction(BaseModel):
	down: bool  # True to scroll down, False to scroll up
	num_pages: float  # Number of pages to scroll (0.5 = half page, 1.0 = one page, etc.)
	index: int | None = None  # Optional element index to find scroll container for


class ScrollUntilVisibleAction(BaseModel):
	"""Scroll container until specified content becomes visible"""

	target_selector: str | None = Field(default=None, description='CSS selector of element to scroll until visible')
	target_text: str | None = Field(default=None, description='Text content to scroll until visible')
	container_index: int | None = Field(default=None, description='Index of scroll container, defaults to main page')
	max_scrolls: int = Field(default=10, description='Maximum number of scroll attempts')


class SendKeysAction(BaseModel):
	keys: str


class UploadFileAction(BaseModel):
	index: int
	path: str


class ExtractPageContentAction(BaseModel):
	value: str


class CheckOverlayAction(BaseModel):
	"""Check for and handle modal overlays that might be blocking interactions"""

	close_overlay: bool = Field(default=True, description='Whether to attempt closing detected overlays')


class NoParamsAction(BaseModel):
	"""
	Accepts absolutely anything in the incoming data
	and discards it, so the final parsed model is empty.
	"""

	model_config = ConfigDict(extra='ignore')
	# No fields defined - all inputs are ignored automatically
