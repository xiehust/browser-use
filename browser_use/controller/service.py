import asyncio
import enum
import json
import logging
from typing import Generic, TypeVar

try:
	from lmnr import Laminar  # type: ignore
except ImportError:
	Laminar = None  # type: ignore
from pydantic import BaseModel

from browser_use.agent.views import ActionModel, ActionResult
from browser_use.browser import BrowserSession
from browser_use.browser.events import (
	ClickElementEvent,
	CloseTabEvent,
	GoBackEvent,
	NavigateToUrlEvent,
	ScrollEvent,
	ScrollToTextEvent,
	SendKeysEvent,
	SwitchTabEvent,
	TypeTextEvent,
)
from browser_use.browser.views import BrowserError
from browser_use.controller.registry.service import Registry
from browser_use.controller.views import (
	CheckOverlayAction,
	ClickElementAction,
	ClickElementBySelectorAction,
	ClickElementByTextAction,
	CloseTabAction,
	DoneAction,
	GoToUrlAction,
	InputTextAction,
	InputTextByLabelAction,
	NoParamsAction,
	ScrollAction,
	ScrollUntilVisibleAction,
	SearchGoogleAction,
	SendKeysAction,
	StructuredOutputAction,
	SwitchTabAction,
	WaitForConditionAction,
)
from browser_use.filesystem.file_system import FileSystem
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import UserMessage
from browser_use.observability import observe_debug
from browser_use.utils import time_execution_sync

logger = logging.getLogger(__name__)

# Import EnhancedDOMTreeNode and rebuild event models that have forward references to it
# This must be done after all imports are complete
ClickElementEvent.model_rebuild()
TypeTextEvent.model_rebuild()
ScrollEvent.model_rebuild()
# Note: UploadFileEvent also has node references but is not imported yet

Context = TypeVar('Context')

T = TypeVar('T', bound=BaseModel)


class Controller(Generic[Context]):
	def __init__(
		self,
		exclude_actions: list[str] = [],
		output_model: type[T] | None = None,
		display_files_in_done_text: bool = True,
	):
		self.registry = Registry[Context](exclude_actions)
		self.display_files_in_done_text = display_files_in_done_text

		"""Register all default browser actions"""

		self._register_done_action(output_model)

		# Basic Navigation Actions
		@self.registry.action(
			'Search the query in Google, the query should be a search query like humans search in Google, concrete and not vague or super long.',
			param_model=SearchGoogleAction,
		)
		async def search_google(params: SearchGoogleAction, browser_session: BrowserSession):
			search_url = f'https://www.google.com/search?q={params.query}&udm=14'

			# Check if there's already a tab open on Google or agent's about:blank
			use_new_tab = True
			try:
				tabs = await browser_session.get_tabs()
				# Get last 4 chars of browser session ID to identify agent's tabs
				browser_session_label = str(browser_session.id)[-4:]
				logger.debug(f'Checking {len(tabs)} tabs for reusable tab (browser_session_label: {browser_session_label})')

				for i, tab in enumerate(tabs):
					logger.debug(f'Tab {i}: url="{tab.url}", title="{tab.title}"')
					# Check if tab is on Google domain
					if tab.url and tab.url.strip('/').lower() in ('https://www.google.com', 'https://google.com'):
						# Found existing Google tab, navigate in it
						logger.debug(f'Found existing Google tab at index {i}: {tab.url}, reusing it')

						# Switch to this tab first if it's not the current one
						from browser_use.browser.events import SwitchTabEvent

						if browser_session.agent_focus and tab.id != browser_session.agent_focus.target_id:
							switch_event = browser_session.event_bus.dispatch(SwitchTabEvent(tab_index=i))
							await switch_event

						use_new_tab = False
						break
					# Check if it's an agent-owned about:blank page (has "Starting agent XXXX..." title)
					# IMPORTANT: about:blank is also used briefly for new tabs the agent is trying to open, dont take over those!
					elif tab.url == 'about:blank' and tab.title:
						# Check if this is our agent's about:blank page with DVD animation
						# The title should be "Starting agent XXXX..." where XXXX is the browser_session_label
						expected_title = f'Starting agent {browser_session_label}...'
						if tab.title == expected_title or browser_session_label in tab.title:
							# This is our agent's about:blank page
							logger.debug(f'Found agent-owned about:blank tab at index {i} with title: "{tab.title}", reusing it')

							# Switch to this tab first
							from browser_use.browser.events import SwitchTabEvent

							if browser_session.agent_focus and tab.id != browser_session.agent_focus.target_id:
								switch_event = browser_session.event_bus.dispatch(SwitchTabEvent(tab_index=i))
								await switch_event

							use_new_tab = False
							break
			except Exception as e:
				logger.debug(f'Could not check for existing tabs: {e}, using new tab')

			# Dispatch navigation event
			event = browser_session.event_bus.dispatch(
				NavigateToUrlEvent(
					url=search_url,
					new_tab=use_new_tab,
				)
			)
			await event

			msg = f'🔍  Searched for "{params.query}" in Google'
			logger.info(msg)
			return ActionResult(
				extracted_content=msg, include_in_memory=True, long_term_memory=f"Searched Google for '{params.query}'"
			)

		@self.registry.action(
			'Navigate to URL, set new_tab=True to open in new tab, False to navigate in current tab', param_model=GoToUrlAction
		)
		async def go_to_url(params: GoToUrlAction, browser_session: BrowserSession):
			try:
				# Dispatch navigation event
				event = browser_session.event_bus.dispatch(NavigateToUrlEvent(url=params.url, new_tab=params.new_tab))
				await event

				if params.new_tab:
					memory = f'Opened new tab with URL {params.url}'
					msg = f'🔗  Opened new tab with url {params.url}'
				else:
					memory = f'Navigated to {params.url}'
					msg = f'🔗 {memory}'

				logger.info(msg)
				return ActionResult(extracted_content=msg, include_in_memory=True, long_term_memory=memory)
			except Exception as e:
				error_msg = str(e)
				# Always log the actual error first for debugging
				browser_session.logger.error(f'❌ Navigation failed: {error_msg}')

				# Check if it's specifically a RuntimeError about CDP client
				if isinstance(e, RuntimeError) and 'CDP client not initialized' in error_msg:
					browser_session.logger.error('❌ Browser connection failed - CDP client not properly initialized')
					raise BrowserError(f'Browser connection error: {error_msg}')
				# Check for network-related errors
				elif any(
					err in error_msg
					for err in [
						'ERR_NAME_NOT_RESOLVED',
						'ERR_INTERNET_DISCONNECTED',
						'ERR_CONNECTION_REFUSED',
						'ERR_TIMED_OUT',
						'net::',
					]
				):
					site_unavailable_msg = f'Site unavailable: {params.url} - {error_msg}'
					browser_session.logger.warning(f'⚠️ {site_unavailable_msg}')
					raise BrowserError(site_unavailable_msg)
				else:
					# Re-raise the original error
					raise

		@self.registry.action('Go back', param_model=NoParamsAction)
		async def go_back(_: NoParamsAction, browser_session: BrowserSession):
			try:
				event = browser_session.event_bus.dispatch(GoBackEvent())
				await event
			except Exception as e:
				logger.error(f'Failed to dispatch GoBackEvent: {type(e).__name__}: {e}')
				raise ValueError(f'Failed to go back: {e}') from e
			msg = '🔙  Navigated back'
			logger.info(msg)
			return ActionResult(extracted_content=msg)

		@self.registry.action(
			'Wait for x seconds default 3 (max 10 seconds). This can be used to wait until the page is fully loaded.'
		)
		async def wait(seconds: int = 3):
			# Cap wait time at maximum 10 seconds
			# Reduce the wait time by 3 seconds to account for the llm call which takes at least 3 seconds
			# So if the model decides to wait for 5 seconds, the llm call took at least 3 seconds, so we only need to wait for 2 seconds
			actual_seconds = min(max(seconds - 3, 0), 10)
			msg = f'🕒  Waiting for {actual_seconds + 3} seconds'
			logger.info(msg)
			await asyncio.sleep(actual_seconds)
			return ActionResult(extracted_content=msg)

		@self.registry.action(
			'Wait for specific page conditions like URL changes, elements becoming visible, or content loading. More reliable than basic wait.',
			param_model=WaitForConditionAction,
		)
		async def wait_for_condition(params: WaitForConditionAction, browser_session: BrowserSession):
			cdp_session = await browser_session.get_or_create_cdp_session()
			timeout_seconds = min(params.timeout_seconds, 30)  # Cap at 30 seconds

			try:
				if params.condition_type == 'url_contains':
					if not params.condition_value:
						raise ValueError('condition_value required for url_contains')

					for _ in range(timeout_seconds * 2):  # Check every 0.5 seconds
						current_url = cdp_session.url
						if params.condition_value in current_url:
							msg = f'✅ URL now contains "{params.condition_value}": {current_url}'
							logger.info(msg)
							return ActionResult(extracted_content=msg, include_in_memory=True)
						await asyncio.sleep(0.5)

					msg = f'⏰ Timeout: URL still does not contain "{params.condition_value}" after {timeout_seconds}s'
					logger.warning(msg)
					return ActionResult(extracted_content=msg, include_in_memory=True)

				elif params.condition_type == 'selector_visible':
					if not params.condition_value:
						raise ValueError('condition_value required for selector_visible')

					for _ in range(timeout_seconds * 2):
						try:
							result = await cdp_session.cdp_client.send.Runtime.evaluate(
								params={
									'expression': f'''
										(() => {{
											const element = document.querySelector("{params.condition_value}");
											return element && element.offsetParent !== null;
										}})()
									''',
									'returnByValue': True,
								},
								session_id=cdp_session.session_id,
							)

							if result.get('result', {}).get('value'):
								msg = f'✅ Element "{params.condition_value}" is now visible'
								logger.info(msg)
								return ActionResult(extracted_content=msg, include_in_memory=True)
						except Exception as e:
							logger.debug(f'Error checking selector visibility: {e}')

						await asyncio.sleep(0.5)

					msg = f'⏰ Timeout: Element "{params.condition_value}" not visible after {timeout_seconds}s'
					logger.warning(msg)
					return ActionResult(extracted_content=msg, include_in_memory=True)

				elif params.condition_type == 'text_present':
					if not params.condition_value:
						raise ValueError('condition_value required for text_present')

					for _ in range(timeout_seconds * 2):
						try:
							result = await cdp_session.cdp_client.send.Runtime.evaluate(
								params={
									'expression': f'''
										document.body.innerText.includes("{params.condition_value}")
									''',
									'returnByValue': True,
								},
								session_id=cdp_session.session_id,
							)

							if result.get('result', {}).get('value'):
								msg = f'✅ Text "{params.condition_value}" is now present on page'
								logger.info(msg)
								return ActionResult(extracted_content=msg, include_in_memory=True)
						except Exception as e:
							logger.debug(f'Error checking text presence: {e}')

						await asyncio.sleep(0.5)

					msg = f'⏰ Timeout: Text "{params.condition_value}" not found after {timeout_seconds}s'
					logger.warning(msg)
					return ActionResult(extracted_content=msg, include_in_memory=True)

				elif params.condition_type == 'page_loaded':
					for _ in range(timeout_seconds * 2):
						try:
							ready_state = await cdp_session.cdp_client.send.Runtime.evaluate(
								params={'expression': 'document.readyState', 'returnByValue': True},
								session_id=cdp_session.session_id,
							)

							if ready_state.get('result', {}).get('value') == 'complete':
								msg = '✅ Page is now fully loaded'
								logger.info(msg)
								return ActionResult(extracted_content=msg, include_in_memory=True)
						except Exception as e:
							logger.debug(f'Error checking page ready state: {e}')

						await asyncio.sleep(0.5)

					msg = f'⏰ Timeout: Page not fully loaded after {timeout_seconds}s'
					logger.warning(msg)
					return ActionResult(extracted_content=msg, include_in_memory=True)

				elif params.condition_type == 'network_idle':
					# Wait for no network requests for 1 second
					await asyncio.sleep(1.0)  # Basic implementation
					msg = '✅ Network idle period detected'
					logger.info(msg)
					return ActionResult(extracted_content=msg, include_in_memory=True)

				else:
					raise ValueError(f'Unknown condition_type: {params.condition_type}')

			except Exception as e:
				msg = f'❌ Error waiting for condition: {e}'
				logger.error(msg)
				return ActionResult(extracted_content=msg, include_in_memory=True, error=str(e))

		# Element Interaction Actions

		@self.registry.action(
			'Click element by index, set new_tab=True to open any resulting navigation in a new tab',
			param_model=ClickElementAction,
		)
		async def click_element_by_index(params: ClickElementAction, browser_session: BrowserSession):
			# Look up the node from the selector map
			node = await browser_session.get_element_by_index(params.index)
			if node is None:
				raise ValueError(f'Element index {params.index} not found in DOM')

			# Dispatch click event with node
			try:
				await browser_session.event_bus.dispatch(ClickElementEvent(node=node, new_tab=params.new_tab))
			except Exception as e:
				logger.error(f'Failed to dispatch ClickElementEvent: {type(e).__name__}: {e}')
				raise ValueError(f'Failed to click element {params.index}: {e}') from e

			msg = f'🖱️ Clicked element with index {params.index}'
			logger.info(msg)
			return ActionResult(extracted_content=msg, include_in_memory=True, long_term_memory=msg)

		@self.registry.action(
			'Click and input text into a input interactive element',
			param_model=InputTextAction,
		)
		async def input_text(params: InputTextAction, browser_session: BrowserSession, has_sensitive_data: bool = False):
			# Look up the node from the selector map
			node = await browser_session.get_element_by_index(params.index)
			if node is None:
				raise ValueError(f'Element index {params.index} not found in DOM')

			# Dispatch type text event with node
			try:
				event = browser_session.event_bus.dispatch(TypeTextEvent(node=node, text=params.text))
				await event
			except Exception as e:
				# Log the full error for debugging
				logger.error(f'Failed to dispatch TypeTextEvent: {type(e).__name__}: {e}')
				# Re-raise with more context
				raise ValueError(f'Failed to input text into element {params.index}: {e}') from e

			# AUTO-ENTER for search fields: Automatically press Enter for search inputs
			should_auto_enter = False

			# Check if this is a search field based on element attributes
			if node.attributes:
				# Check for search-related attributes
				search_indicators = {'search', 'query', 'find', 'lookup', 'searchbox', 'search-input'}

				# Check input type
				input_type = node.attributes.get('type', '').lower()
				if input_type == 'search':
					should_auto_enter = True

				# Check class names
				class_list = node.attributes.get('class', '').lower()
				if any(indicator in class_list for indicator in search_indicators):
					should_auto_enter = True

				# Check id
				element_id = node.attributes.get('id', '').lower()
				if any(indicator in element_id for indicator in search_indicators):
					should_auto_enter = True

				# Check placeholder text
				placeholder = node.attributes.get('placeholder', '').lower()
				if any(indicator in placeholder for indicator in search_indicators):
					should_auto_enter = True

				# Check aria-label
				aria_label = node.attributes.get('aria-label', '').lower()
				if any(indicator in aria_label for indicator in search_indicators):
					should_auto_enter = True

			# Auto-press Enter for search fields
			if should_auto_enter:
				try:
					logger.info('🔍 Detected search field, auto-pressing Enter after input')
					enter_event = browser_session.event_bus.dispatch(SendKeysEvent(keys='Enter'))
					await enter_event
				except Exception as e:
					logger.warning(f'Failed to auto-press Enter: {e}')
					# Don't fail the entire action if Enter fails

			if not has_sensitive_data:
				msg = f'⌨️  Input {params.text} into index {params.index}'
				if should_auto_enter:
					msg += ' (+ Enter)'
			else:
				msg = f'⌨️  Input sensitive data into index {params.index}'
				if should_auto_enter:
					msg += ' (+ Enter)'

			logger.info(msg)
			return ActionResult(
				extracted_content=msg,
				include_in_memory=True,
				long_term_memory=f"Input '{params.text}' into element {params.index}."
				+ (' Pressed Enter automatically.' if should_auto_enter else ''),
			)

		# Enhanced Element Targeting Actions (Semantic)

		@self.registry.action(
			'Click element by visible text content - more reliable than index-based clicking for dynamic pages',
			param_model=ClickElementByTextAction,
		)
		async def click_element_by_text(params: ClickElementByTextAction, browser_session: BrowserSession):
			cdp_session = await browser_session.get_or_create_cdp_session()

			try:
				# Build JavaScript to find element by text
				tag_filter = f"'{params.tag_name.upper()}'" if params.tag_name else 'null'

				find_element_js = (
					'''
					(() => {
						const targetText = "'''
					+ params.text
					+ """";
						const tagFilter = """
					+ tag_filter
					+ """;
						
						// Get all elements
						const allElements = document.querySelectorAll('*');
						
						for (let element of allElements) {
							// Skip if tag filter specified and doesn't match
							if (tagFilter && element.tagName !== tagFilter) continue;
							
							// Check if element's text content matches (trimmed)
							const elementText = element.textContent ? element.textContent.trim() : '';
							if (elementText === targetText || elementText.includes(targetText)) {
								// Ensure element is visible and clickable
								const rect = element.getBoundingClientRect();
								const style = window.getComputedStyle(element);
								
								if (rect.width > 0 && rect.height > 0 && 
									style.visibility !== 'hidden' && 
									style.display !== 'none') {
									return {
										found: true,
										tagName: element.tagName,
										text: elementText,
										xpath: getXPath(element)
									};
								}
							}
						}
						
						return { found: false };
						
						function getXPath(element) {
							if (element.id) return `//*[@id="${element.id}"]`;
							
							const parts = [];
							while (element && element.nodeType === Node.ELEMENT_NODE) {
								const tagName = element.tagName.toLowerCase();
								
								// Simple counting approach
								let index = 1;
								let sibling = element.previousElementSibling;
								while (sibling) {
									if (sibling.tagName === element.tagName) {
										index++;
									}
									sibling = sibling.previousElementSibling;
								}
								
								// Only add index if there are multiple elements of same type
								const siblingCount = element.parentNode ? 
									Array.from(element.parentNode.children).filter(el => el.tagName === element.tagName).length : 1;
								
								const position = siblingCount > 1 ? `[${index}]` : '';
								parts.unshift(`${tagName}${position}`);
								element = element.parentElement;
							}
							
							return '/' + parts.join('/');
						}
					})()
				"""
				)

				result = await cdp_session.cdp_client.send.Runtime.evaluate(
					params={'expression': find_element_js, 'returnByValue': True}, session_id=cdp_session.session_id
				)

				element_info = result.get('result', {}).get('value', {})

				if not element_info.get('found'):
					tag_msg = f" with tag '{params.tag_name}'" if params.tag_name else ''
					raise ValueError(f'Element with text "{params.text}"{tag_msg} not found or not clickable')

				# Click the element using its xpath
				xpath = element_info['xpath']
				click_js = f"""
					(() => {{
						const element = document.evaluate('{xpath}', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
						if (element) {{
							element.click();
							return true;
						}}
						return false;
					}})()
				"""

				click_result = await cdp_session.cdp_client.send.Runtime.evaluate(
					params={'expression': click_js, 'returnByValue': True}, session_id=cdp_session.session_id
				)

				if not click_result.get('result', {}).get('value'):
					raise ValueError('Failed to click element - element not found during click')

				tag_msg = f' ({element_info["tagName"]})' if element_info.get('tagName') else ''
				msg = f'🖱️ Clicked element by text: "{params.text}"{tag_msg}'
				logger.info(msg)
				return ActionResult(extracted_content=msg, include_in_memory=True, long_term_memory=msg)

			except Exception as e:
				error_msg = f'Failed to click element by text "{params.text}": {e}'
				logger.error(error_msg)
				raise ValueError(error_msg) from e

		@self.registry.action(
			'Click element by CSS selector, aria-label, or other attributes - for precise targeting',
			param_model=ClickElementBySelectorAction,
		)
		async def click_element_by_selector(params: ClickElementBySelectorAction, browser_session: BrowserSession):
			cdp_session = await browser_session.get_or_create_cdp_session()

			try:
				# Try clicking using the selector
				click_js = f'''
					(() => {{
						const selector = "{params.selector}";
						
						// Try as CSS selector first
						let element = document.querySelector(selector);
						
						// If no match, try as attribute selector patterns
						if (!element) {{
							// Try aria-label
							element = document.querySelector(`[aria-label*="${{selector}}"]`);
						}}
						
						if (!element) {{
							// Try role
							element = document.querySelector(`[role="${{selector}}"]`);
						}}
						
						if (!element) {{
							// Try data attributes
							element = document.querySelector(`[data-*="${{selector}}"]`);
						}}
						
						if (element) {{
							// Check if element is visible and clickable
							const rect = element.getBoundingClientRect();
							const style = window.getComputedStyle(element);
							
							if (rect.width > 0 && rect.height > 0 && 
								style.visibility !== 'hidden' && 
								style.display !== 'none') {{
								element.click();
								return {{
									success: true,
									tagName: element.tagName,
									selector: selector
								}};
							}} else {{
								return {{
									success: false,
									error: 'Element found but not visible/clickable'
								}};
							}}
						}}
						
						return {{
							success: false,
							error: 'Element not found'
						}};
					}})()
				'''

				result = await cdp_session.cdp_client.send.Runtime.evaluate(
					params={'expression': click_js, 'returnByValue': True}, session_id=cdp_session.session_id
				)

				click_info = result.get('result', {}).get('value', {})

				if not click_info.get('success'):
					error = click_info.get('error', 'Unknown error')
					raise ValueError(f'Failed to click element with selector "{params.selector}": {error}')

				tag_name = click_info.get('tagName', '')
				msg = f'🖱️ Clicked element by selector: "{params.selector}" ({tag_name})'
				logger.info(msg)
				return ActionResult(extracted_content=msg, include_in_memory=True, long_term_memory=msg)

			except Exception as e:
				error_msg = f'Failed to click element by selector "{params.selector}": {e}'
				logger.error(error_msg)
				raise ValueError(error_msg) from e

		@self.registry.action(
			'Input text into field by label text, placeholder, or aria-label - more reliable than index-based input',
			param_model=InputTextByLabelAction,
		)
		async def input_text_by_label(params: InputTextByLabelAction, browser_session: BrowserSession):
			cdp_session = await browser_session.get_or_create_cdp_session()

			try:
				# Find input field by label
				find_input_js = f'''
					(() => {{
						const labelText = "{params.label_text}";
						
						// Try different ways to find the input
						
						// 1. Find label element with matching text and get associated input
						const labels = document.querySelectorAll('label');
						for (let label of labels) {{
							if (label.textContent && label.textContent.trim().includes(labelText)) {{
								// Try for attribute
								if (label.getAttribute('for')) {{
									const input = document.getElementById(label.getAttribute('for'));
									if (input && (input.tagName === 'INPUT' || input.tagName === 'TEXTAREA')) {{
										return {{
											found: true,
											method: 'label-for',
											element: input
										}};
									}}
								}}
								
								// Try nested input
								const nestedInput = label.querySelector('input, textarea');
								if (nestedInput) {{
									return {{
										found: true,
										method: 'label-nested',
										element: nestedInput
									}};
								}}
							}}
						}}
						
						// 2. Find input with matching placeholder
						const inputsWithPlaceholder = document.querySelectorAll('input[placeholder], textarea[placeholder]');
						for (let input of inputsWithPlaceholder) {{
							if (input.placeholder && input.placeholder.includes(labelText)) {{
								return {{
									found: true,
									method: 'placeholder',
									element: input
								}};
							}}
						}}
						
						// 3. Find input with matching aria-label
						const inputsWithAriaLabel = document.querySelectorAll('input[aria-label], textarea[aria-label]');
						for (let input of inputsWithAriaLabel) {{
							if (input.getAttribute('aria-label') && input.getAttribute('aria-label').includes(labelText)) {{
								return {{
									found: true,
									method: 'aria-label',
									element: input
								}};
							}}
						}}
						
						return {{ found: false }};
					}})()
				'''

				result = await cdp_session.cdp_client.send.Runtime.evaluate(
					params={'expression': find_input_js, 'returnByValue': True}, session_id=cdp_session.session_id
				)

				find_info = result.get('result', {}).get('value', {})

				if not find_info.get('found'):
					raise ValueError(f'Input field with label "{params.label_text}" not found')

				# Input text into the found element
				input_js = f'''
					(() => {{
						// Re-find the element (can't pass element objects through JSON)
						const labelText = "{params.label_text}";
						const inputText = "{params.text}";
						
						let targetInput = null;
						
						// Use same logic as above to find element again
						const labels = document.querySelectorAll('label');
						for (let label of labels) {{
							if (label.textContent && label.textContent.trim().includes(labelText)) {{
								if (label.getAttribute('for')) {{
									const input = document.getElementById(label.getAttribute('for'));
									if (input && (input.tagName === 'INPUT' || input.tagName === 'TEXTAREA')) {{
										targetInput = input;
										break;
									}}
								}}
								const nestedInput = label.querySelector('input, textarea');
								if (nestedInput) {{
									targetInput = nestedInput;
									break;
								}}
							}}
						}}
						
						if (!targetInput) {{
							const inputsWithPlaceholder = document.querySelectorAll('input[placeholder], textarea[placeholder]');
							for (let input of inputsWithPlaceholder) {{
								if (input.placeholder && input.placeholder.includes(labelText)) {{
									targetInput = input;
									break;
								}}
							}}
						}}
						
						if (!targetInput) {{
							const inputsWithAriaLabel = document.querySelectorAll('input[aria-label], textarea[aria-label]');
							for (let input of inputsWithAriaLabel) {{
								if (input.getAttribute('aria-label') && input.getAttribute('aria-label').includes(labelText)) {{
									targetInput = input;
									break;
								}}
							}}
						}}
						
						if (targetInput) {{
							// Clear existing content and input new text
							targetInput.focus();
							targetInput.select();
							targetInput.value = inputText;
							
							// Trigger input events
							targetInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
							targetInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
							
							return {{
								success: true,
								tagName: targetInput.tagName,
								placeholder: targetInput.placeholder || '',
								value: targetInput.value
							}};
						}}
						
						return {{ success: false }};
					}})()
				'''

				input_result = await cdp_session.cdp_client.send.Runtime.evaluate(
					params={'expression': input_js, 'returnByValue': True}, session_id=cdp_session.session_id
				)

				input_info = input_result.get('result', {}).get('value', {})

				if not input_info.get('success'):
					raise ValueError('Failed to input text - element not found during input operation')

				method = find_info.get('method', 'unknown')
				msg = f'⌨️ Input text "{params.text}" into field by {method}: "{params.label_text}"'
				logger.info(msg)
				return ActionResult(
					extracted_content=msg,
					include_in_memory=True,
					long_term_memory=f"Input '{params.text}' into field labeled '{params.label_text}'",
				)

			except Exception as e:
				error_msg = f'Failed to input text by label "{params.label_text}": {e}'
				logger.error(error_msg)
				raise ValueError(error_msg) from e

		@self.registry.action(
			'Check for and handle modal overlays that might be blocking interactions',
			param_model=CheckOverlayAction,
		)
		async def check_overlay(params: CheckOverlayAction, browser_session: BrowserSession):
			cdp_session = await browser_session.get_or_create_cdp_session()

			try:
				# Detect overlays/modals
				detect_overlay_js = """
					(() => {
						const overlays = [];
						
						// Common overlay selectors
						const overlaySelectors = [
							'[class*="modal"]',
							'[class*="overlay"]',
							'[class*="popup"]',
							'[class*="dialog"]',
							'[class*="backdrop"]',
							'[role="dialog"]',
							'[role="modal"]',
							'.fixed', 
							'[style*="position: fixed"]',
							'[style*="position:fixed"]'
						];
						
						for (let selector of overlaySelectors) {
							const elements = document.querySelectorAll(selector);
							for (let element of elements) {
								const rect = element.getBoundingClientRect();
								const style = window.getComputedStyle(element);
								
								// Check if element is large enough to be an overlay
								if (rect.width > window.innerWidth * 0.3 && 
									rect.height > window.innerHeight * 0.3 &&
									style.visibility !== 'hidden' && 
									style.display !== 'none' &&
									parseInt(style.zIndex) > 100) {
									
									overlays.push({
										selector: selector,
										zIndex: style.zIndex,
										width: rect.width,
										height: rect.height,
										element: element
									});
								}
							}
						}
						
						return {
							found: overlays.length > 0,
							count: overlays.length,
							overlays: overlays.map(o => ({
								selector: o.selector,
								zIndex: o.zIndex,
								width: o.width,
								height: o.height
							}))
						};
					})()
				"""

				result = await cdp_session.cdp_client.send.Runtime.evaluate(
					params={'expression': detect_overlay_js, 'returnByValue': True}, session_id=cdp_session.session_id
				)

				overlay_info = result.get('result', {}).get('value', {})

				if not overlay_info.get('found'):
					msg = '✅ No blocking overlays detected'
					logger.info(msg)
					return ActionResult(extracted_content=msg, include_in_memory=True)

				overlay_count = overlay_info.get('count', 0)
				msg = f'⚠️ Detected {overlay_count} potential overlay(s)'

				if params.close_overlay:
					# Try to close overlays
					close_overlay_js = """
						(() => {
							const closeAttempts = [];
							
							// Common close button selectors
							const closeSelectors = [
								'[aria-label*="close"]',
								'[title*="close"]',
								'[class*="close"]',
								'[class*="dismiss"]',
								'.modal-close',
								'.overlay-close',
								'button[type="button"]'
							];
							
							for (let selector of closeSelectors) {
								const closeButtons = document.querySelectorAll(selector);
								for (let button of closeButtons) {
									const rect = button.getBoundingClientRect();
									const style = window.getComputedStyle(button);
									
									if (rect.width > 0 && rect.height > 0 && 
										style.visibility !== 'hidden' && 
										style.display !== 'none') {
										
										button.click();
										closeAttempts.push({
											selector: selector,
											clicked: true
										});
										
										// Only click first found close button
										return {
											attempted: true,
											count: closeAttempts.length
										};
									}
								}
							}
							
							// Try pressing Escape key
							document.dispatchEvent(new KeyboardEvent('keydown', {
								key: 'Escape',
								keyCode: 27,
								which: 27,
								bubbles: true
							}));
							
							return {
								attempted: true,
								escapeTried: true,
								count: 0
							};
						})()
					"""

					close_result = await cdp_session.cdp_client.send.Runtime.evaluate(
						params={'expression': close_overlay_js, 'returnByValue': True}, session_id=cdp_session.session_id
					)

					close_info = close_result.get('result', {}).get('value', {})

					if close_info.get('attempted'):
						close_count = close_info.get('count', 0)
						escape_tried = close_info.get('escapeTried', False)
						msg += f' - Attempted to close (clicked {close_count} close buttons'
						if escape_tried:
							msg += ', tried Escape key'
						msg += ')'

				logger.info(msg)
				return ActionResult(extracted_content=msg, include_in_memory=True)

			except Exception as e:
				error_msg = f'Error checking overlays: {e}'
				logger.error(error_msg)
				return ActionResult(extracted_content=error_msg, include_in_memory=True, error=str(e))

		# @self.registry.action('Upload file to interactive element with file path', param_model=UploadFileAction)
		# async def upload_file(params: UploadFileAction, browser_session: BrowserSession, available_file_paths: list[str]):
		# 	if params.path not in available_file_paths:
		# 		raise BrowserError(f'File path {params.path} is not available')

		# 	if not os.path.exists(params.path):
		# 		raise BrowserError(f'File {params.path} does not exist')

		# 	# Look up the node from the selector map
		# 	node = EnhancedDOMTreeNode.from_element_index(browser_session, params.index)

		# 	# Dispatch upload file event with node
		# 	event = browser_session.event_bus.dispatch(
		# 		UploadFileEvent(
		# 			node=node,
		# 			file_path=params.path
		# 		)
		# 	)
		# 	await event

		# 	msg = f'📁 Successfully uploaded file to index {params.index}'
		# 	logger.info(msg)
		# 	return ActionResult(
		# 		extracted_content=msg,
		# 		include_in_memory=True,
		# 		long_term_memory=f'Uploaded file {params.path} to element {params.index}',
		# 	)

		# Tab Management Actions

		@self.registry.action('Switch tab', param_model=SwitchTabAction)
		async def switch_tab(params: SwitchTabAction, browser_session: BrowserSession):
			# Dispatch switch tab event
			event = browser_session.event_bus.dispatch(SwitchTabEvent(tab_index=params.page_id))
			await event

			msg = f'🔄  Switched to tab #{params.page_id}'
			logger.info(msg)
			return ActionResult(
				extracted_content=msg, include_in_memory=True, long_term_memory=f'Switched to tab {params.page_id}'
			)

		@self.registry.action('Close an existing tab', param_model=CloseTabAction)
		async def close_tab(params: CloseTabAction, browser_session: BrowserSession):
			# Dispatch close tab event
			event = browser_session.event_bus.dispatch(CloseTabEvent(tab_index=params.page_id))
			await event

			msg = f'❌  Closed tab #{params.page_id}'
			logger.info(msg)
			return ActionResult(
				extracted_content=msg,
				include_in_memory=True,
				long_term_memory=f'Closed tab {params.page_id}',
			)

		# Content Actions

		# TODO: Refactor to use events instead of direct page access
		# This action is temporarily disabled as it needs refactoring to use events

		@self.registry.action(
			"""Extract structured, semantic data (e.g. product description, price, all information about XYZ) from the current webpage based on a textual query.
		This tool takes the entire markdown of the page and extracts the query from it.
		Set extract_links=True ONLY if your query requires extracting links/URLs from the page.
		Only use this for specific queries for information retrieval from the page. Don't use this to get interactive elements - the tool does not see HTML elements, only the markdown.
		""",
		)
		async def extract_structured_data(
			query: str,
			extract_links: bool,
			browser_session: BrowserSession,
			page_extraction_llm: BaseChatModel,
			file_system: FileSystem,
		):
			loop = asyncio.get_event_loop()
			cdp_session = await browser_session.get_or_create_cdp_session()

			# Page state verification before extraction
			try:
				current_url = cdp_session.url

				# Check for about:blank or invalid URLs
				if not current_url or current_url.startswith('about:blank') or current_url == 'about:blank':
					return ActionResult(
						extracted_content='Cannot extract from blank page. Please navigate to a valid URL first.',
						include_in_memory=True,
						error='Page not loaded - currently on about:blank',
					)

				# Wait for page to be ready (check for document.readyState)
				try:
					ready_state = await cdp_session.cdp_client.send.Runtime.evaluate(
						params={'expression': 'document.readyState', 'returnByValue': True}, session_id=cdp_session.session_id
					)

					if ready_state.get('result', {}).get('value') != 'complete':
						# Wait up to 5 seconds for page to be ready
						for _ in range(10):
							await asyncio.sleep(0.5)
							ready_state = await cdp_session.cdp_client.send.Runtime.evaluate(
								params={'expression': 'document.readyState', 'returnByValue': True},
								session_id=cdp_session.session_id,
							)
							if ready_state.get('result', {}).get('value') == 'complete':
								break
						else:
							logger.warning(f'Page not fully loaded after 5 seconds, proceeding anyway. URL: {current_url}')

				except Exception as e:
					logger.warning(f'Could not check document ready state: {e}')

				# Verify the page has content (not empty body)
				try:
					body_check = await cdp_session.cdp_client.send.Runtime.evaluate(
						params={
							'expression': 'document.body && document.body.innerText.trim().length > 0',
							'returnByValue': True,
						},
						session_id=cdp_session.session_id,
					)

					has_content = body_check.get('result', {}).get('value', False)
					if not has_content:
						return ActionResult(
							extracted_content='Page appears to be empty or still loading. Please wait for content to load or navigate to a different page.',
							include_in_memory=True,
							error='Page has no content - body is empty',
						)

				except Exception as e:
					logger.warning(f'Could not check page content: {e}')

			except Exception as e:
				logger.warning(f'Page state verification failed: {e}')

			try:
				# Get the HTML content
				body_id = await cdp_session.cdp_client.send.DOM.getDocument(session_id=cdp_session.session_id)
				page_html_result = await cdp_session.cdp_client.send.DOM.getOuterHTML(
					params={'backendNodeId': body_id['root']['backendNodeId']}, session_id=cdp_session.session_id
				)
			except Exception as e:
				raise RuntimeError(f"Couldn't extract page content: {e}")

			page_html = page_html_result['outerHTML']

			# Additional verification - check if we got meaningful HTML
			if len(page_html.strip()) < 100:
				return ActionResult(
					extracted_content='Page content is too minimal for extraction. Please ensure the page has loaded completely.',
					include_in_memory=True,
					error='Insufficient page content for extraction',
				)

			# Simple markdown conversion
			try:
				import markdownify

				if extract_links:
					content = markdownify.markdownify(page_html, heading_style='ATX', bullets='-')
				else:
					content = markdownify.markdownify(page_html, heading_style='ATX', bullets='-', strip=['a'])
			except Exception as e:
				raise RuntimeError(f'Could not convert html to markdown: {type(e).__name__}')

			# Simple truncation to 30k characters
			if len(content) > 30000:
				content = content[:30000] + '\n\n... [Content truncated at 30k characters] ...'

			# Simple prompt
			prompt = f"""Extract the requested information from this webpage content.

Query: {query}

Webpage Content:
{content}

Provide the extracted information in a clear, structured format."""

			try:
				response = await asyncio.wait_for(
					page_extraction_llm.ainvoke([UserMessage(content=prompt)]),
					timeout=120.0,
				)

				extracted_content = f'Page Link: {cdp_session.url}\nQuery: {query}\nExtracted Content:\n{response.completion}'

				# Simple memory handling
				if len(extracted_content) < 1000:
					memory = extracted_content
					include_extracted_content_only_once = False
				else:
					save_result = await file_system.save_extracted_content(extracted_content)
					memory = f'Extracted content from {cdp_session.url} for query: {query}\nContent saved to file system: {save_result}'
					include_extracted_content_only_once = True

				logger.info(f'📄 {memory}')
				return ActionResult(
					extracted_content=extracted_content,
					include_extracted_content_only_once=include_extracted_content_only_once,
					long_term_memory=memory,
				)
			except Exception as e:
				logger.debug(f'Error extracting content: {e}')
				raise RuntimeError(str(e))

		@self.registry.action(
			'Scroll the page by specified number of pages (set down=True to scroll down, down=False to scroll up, num_pages=number of pages to scroll like 0.5 for half page, 1.0 for one page, etc.). Optional index parameter to scroll within a specific element or its scroll container (works well for dropdowns and custom UI components). Use index=0 or omit index to scroll the entire page.',
			param_model=ScrollAction,
		)
		async def scroll(params: ScrollAction, browser_session: BrowserSession):
			# Look up the node from the selector map if index is provided
			# Special case: index 0 means scroll the whole page (root/body element)
			node = None
			if params.index is not None and params.index != 0:
				try:
					node = await browser_session.get_element_by_index(params.index)
					if node is None:
						# Element not found - return error
						raise ValueError(f'Element index {params.index} not found in DOM')
				except Exception as e:
					# Error getting element - return error
					raise ValueError(f'Failed to get element {params.index}: {e}') from e

			# Dispatch scroll event with node - the complex logic is handled in the event handler
			# Convert pages to pixels (assuming 800px per page as standard viewport height)
			pixels = int(params.num_pages * 800)
			try:
				event = browser_session.event_bus.dispatch(
					ScrollEvent(direction='down' if params.down else 'up', amount=pixels, node=node)
				)
				await event
			except Exception as e:
				logger.error(f'Failed to dispatch ScrollEvent: {type(e).__name__}: {e}')
				raise ValueError(f'Failed to scroll: {e}') from e

			direction = 'down' if params.down else 'up'
			# If index is 0 or None, we're scrolling the page
			target = 'the page' if params.index is None or params.index == 0 else f'element {params.index}'

			if params.num_pages == 1.0:
				long_term_memory = f'Scrolled {direction} {target} by one page'
			else:
				long_term_memory = f'Scrolled {direction} {target} by {params.num_pages} pages'

			msg = f'🔍 {long_term_memory}'
			logger.info(msg)
			return ActionResult(extracted_content=msg, include_in_memory=True, long_term_memory=long_term_memory)

		@self.registry.action(
			'Scroll container until specified content becomes visible - more reliable than blind scrolling',
			param_model=ScrollUntilVisibleAction,
		)
		async def scroll_until_visible(params: ScrollUntilVisibleAction, browser_session: BrowserSession):
			cdp_session = await browser_session.get_or_create_cdp_session()

			# Validate parameters
			if not params.target_selector and not params.target_text:
				raise ValueError('Either target_selector or target_text must be specified')

			try:
				# Find container element if specified
				container_node = None
				if params.container_index is not None:
					container_node = await browser_session.get_element_by_index(params.container_index)
					if container_node is None:
						raise ValueError(f'Container element index {params.container_index} not found in DOM')

				for scroll_attempt in range(params.max_scrolls):
					# Check if target is now visible
					if params.target_selector:
						# Check for selector visibility
						check_js = f'''
							(() => {{
								const element = document.querySelector("{params.target_selector}");
								if (element) {{
									const rect = element.getBoundingClientRect();
									const style = window.getComputedStyle(element);
									
									// Check if element is visible in viewport
									return rect.top >= 0 && 
										   rect.left >= 0 && 
										   rect.bottom <= window.innerHeight && 
										   rect.right <= window.innerWidth &&
										   style.visibility !== 'hidden' && 
										   style.display !== 'none';
								}}
								return false;
							}})()
						'''
					else:
						# Check for text visibility
						check_js = f'''
							(() => {{
								const targetText = "{params.target_text}";
								const walker = document.createTreeWalker(
									document.body,
									NodeFilter.SHOW_TEXT,
									null,
									false
								);
								
								let node;
								while (node = walker.nextNode()) {{
									if (node.textContent && node.textContent.includes(targetText)) {{
										const parentElement = node.parentElement;
										if (parentElement) {{
											const rect = parentElement.getBoundingClientRect();
											const style = window.getComputedStyle(parentElement);
											
											// Check if text is visible in viewport
											if (rect.top >= 0 && 
												rect.left >= 0 && 
												rect.bottom <= window.innerHeight && 
												rect.right <= window.innerWidth &&
												style.visibility !== 'hidden' && 
												style.display !== 'none') {{
												return true;
											}}
										}}
									}}
								}}
								return false;
							}})()
						'''

					result = await cdp_session.cdp_client.send.Runtime.evaluate(
						params={'expression': check_js, 'returnByValue': True}, session_id=cdp_session.session_id
					)

					is_visible = result.get('result', {}).get('value', False)

					if is_visible:
						target_desc = params.target_selector if params.target_selector else f'text "{params.target_text}"'
						msg = f'✅ Found {target_desc} visible after {scroll_attempt} scroll(s)'
						logger.info(msg)
						return ActionResult(
							extracted_content=msg,
							include_in_memory=True,
							long_term_memory=f'Scrolled until {target_desc} became visible',
						)

					# Not visible yet, scroll down
					if scroll_attempt < params.max_scrolls - 1:  # Don't scroll on last attempt
						try:
							# Scroll down by half a page
							pixels = 400  # Half page scroll
							event = browser_session.event_bus.dispatch(
								ScrollEvent(direction='down', amount=pixels, node=container_node)
							)
							await event

							# Small delay to allow content to load
							await asyncio.sleep(0.5)

						except Exception as e:
							logger.warning(f'Scroll attempt {scroll_attempt + 1} failed: {e}')

				# Target not found after max scrolls
				target_desc = params.target_selector if params.target_selector else f'text "{params.target_text}"'
				msg = f'⏰ Could not find {target_desc} after {params.max_scrolls} scroll attempts'
				logger.warning(msg)
				return ActionResult(
					extracted_content=msg,
					include_in_memory=True,
					long_term_memory=f'Scrolled {params.max_scrolls} times but {target_desc} not found',
				)

			except Exception as e:
				error_msg = f'Error during scroll until visible: {e}'
				logger.error(error_msg)
				raise ValueError(error_msg) from e

		@self.registry.action(
			'Send strings of special keys to use Playwright page.keyboard.press - examples include Escape, Backspace, Insert, PageDown, Delete, Enter, or Shortcuts such as `Control+o`, `Control+Shift+T`',
			param_model=SendKeysAction,
		)
		async def send_keys(params: SendKeysAction, browser_session: BrowserSession):
			# Dispatch send keys event
			try:
				event = browser_session.event_bus.dispatch(SendKeysEvent(keys=params.keys))
				await event
			except Exception as e:
				logger.error(f'Failed to dispatch SendKeysEvent: {type(e).__name__}: {e}')
				raise ValueError(f'Failed to send keys: {e}') from e

			msg = f'⌨️  Sent keys: {params.keys}'
			logger.info(msg)
			return ActionResult(extracted_content=msg, include_in_memory=True, long_term_memory=f'Sent keys: {params.keys}')

		@self.registry.action(
			description='Scroll to a text in the current page',
		)
		async def scroll_to_text(text: str, browser_session: BrowserSession):  # type: ignore
			# Dispatch scroll to text event
			event = browser_session.event_bus.dispatch(ScrollToTextEvent(text=text))
			await event

			# Check result to see if text was found
			result = await event.event_result()
			if result and result.get('found'):
				msg = f'🔍  Scrolled to text: {text}'
				logger.info(msg)
				return ActionResult(extracted_content=msg, include_in_memory=True, long_term_memory=f'Scrolled to text: {text}')
			else:
				msg = f"Text '{text}' not found or not visible on page"
				logger.info(msg)
				return ActionResult(
					extracted_content=msg,
					include_in_memory=True,
					long_term_memory=f"Tried scrolling to text '{text}' but it was not found",
				)

		# File System Actions
		@self.registry.action(
			'Write or append content to file_name in file system. Allowed extensions are .md, .txt, .json, .csv, .pdf. For .pdf files, write the content in markdown format and it will automatically be converted to a properly formatted PDF document.'
		)
		async def write_file(
			file_name: str,
			content: str,
			file_system: FileSystem,
			append: bool = False,
			trailing_newline: bool = True,
			leading_newline: bool = False,
		):
			if trailing_newline:
				content += '\n'
			if leading_newline:
				content = '\n' + content
			if append:
				result = await file_system.append_file(file_name, content)
			else:
				result = await file_system.write_file(file_name, content)
			logger.info(f'💾 {result}')
			return ActionResult(extracted_content=result, include_in_memory=True, long_term_memory=result)

		@self.registry.action(
			'Replace old_str with new_str in file_name. old_str must exactly match the string to replace in original text. Recommended tool to mark completed items in todo.md or change specific contents in a file.'
		)
		async def replace_file_str(file_name: str, old_str: str, new_str: str, file_system: FileSystem):
			result = await file_system.replace_file_str(file_name, old_str, new_str)
			logger.info(f'💾 {result}')
			return ActionResult(extracted_content=result, include_in_memory=True, long_term_memory=result)

		@self.registry.action('Read file_name from file system')
		async def read_file(file_name: str, available_file_paths: list[str], file_system: FileSystem):
			if available_file_paths and file_name in available_file_paths:
				result = await file_system.read_file(file_name, external_file=True)
			else:
				result = await file_system.read_file(file_name)

			MAX_MEMORY_SIZE = 1000
			if len(result) > MAX_MEMORY_SIZE:
				lines = result.splitlines()
				display = ''
				lines_count = 0
				for line in lines:
					if len(display) + len(line) < MAX_MEMORY_SIZE:
						display += line + '\n'
						lines_count += 1
					else:
						break
				remaining_lines = len(lines) - lines_count
				memory = f'{display}{remaining_lines} more lines...' if remaining_lines > 0 else display
			else:
				memory = result
			logger.info(f'💾 {memory}')
			return ActionResult(
				extracted_content=result,
				include_in_memory=True,
				long_term_memory=memory,
				include_extracted_content_only_once=True,
			)

	# TODO: Refactor to use events instead of direct page/dom access
	# @self.registry.action(
	# 	description='Get all options from a native dropdown or ARIA menu',
	# )
	# async def get_dropdown_options(index: int, browser_session: BrowserSession) -> ActionResult:
	# 	"""Get all options from a native dropdown or ARIA menu"""

	# 	dom_element = await browser_session.get_dom_element_by_index(index)
	# 	if dom_element is None:
	# 		raise Exception(f'Element index {index} does not exist - retry or use alternative actions')

	# 	try:
	# 		# Frame-aware approach since we know it works
	# 		all_options = []
	# 		frame_index = 0

	# 		for frame in page.frames:
	# 			try:
	# 				# First check if it's a native select element
	# 				options = await frame.evaluate(
	# 					"""
	# 					(xpath) => {
	# 						const element = document.evaluate(xpath, document, null,
	# 							XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
	# 						if (!element) return null;

	# 						// Check if it's a native select element
	# 						if (element.tagName.toLowerCase() === 'select') {
	# 							return {
	# 								type: 'select',
	# 								options: Array.from(element.options).map(opt => ({
	# 									text: opt.text, //do not trim, because we are doing exact match in select_dropdown_option
	# 									value: opt.value,
	# 									index: opt.index
	# 								})),
	# 								id: element.id,
	# 								name: element.name
	# 							};
	# 						}

	# 						// Check if it's an ARIA menu
	# 						if (element.getAttribute('role') === 'menu' ||
	# 							element.getAttribute('role') === 'listbox' ||
	# 							element.getAttribute('role') === 'combobox') {
	# 							// Find all menu items
	# 							const menuItems = element.querySelectorAll('[role="menuitem"], [role="option"]');
	# 							const options = [];

	# 							menuItems.forEach((item, idx) => {
	# 								// Get the text content of the menu item
	# 								const text = item.textContent.trim();
	# 								if (text) {
	# 									options.push({
	# 										text: text,
	# 										value: text, // For ARIA menus, use text as value
	# 										index: idx
	# 									});
	# 								}
	# 							});

	# 							return {
	# 								type: 'aria',
	# 								options: options,
	# 								id: element.id || '',
	# 								name: element.getAttribute('aria-label') || ''
	# 							};
	# 						}

	# 						return null;
	# 					}
	# 				""",
	# 					dom_element.xpath,
	# 				)

	# 				if options:
	# 					logger.debug(f'Found {options["type"]} dropdown in frame {frame_index}')
	# 					logger.debug(f'Element ID: {options["id"]}, Name: {options["name"]}')

	# 					formatted_options = []
	# 					for opt in options['options']:
	# 						# encoding ensures AI uses the exact string in select_dropdown_option
	# 						encoded_text = json.dumps(opt['text'])
	# 						formatted_options.append(f'{opt["index"]}: text={encoded_text}')

	# 					all_options.extend(formatted_options)

	# 			except Exception as frame_e:
	# 				logger.debug(f'Frame {frame_index} evaluation failed: {str(frame_e)}')

	# 			frame_index += 1

	# 		if all_options:
	# 			msg = '\n'.join(all_options)
	# 			msg += '\nUse the exact text string in select_dropdown_option'
	# 			logger.info(msg)
	# 			return ActionResult(
	# 				extracted_content=msg,
	# 				include_in_memory=True,
	# 				long_term_memory=f'Found dropdown options for index {index}.',
	# 				include_extracted_content_only_once=True,
	# 			)
	# 		else:
	# 			msg = 'No options found in any frame for dropdown'
	# 			logger.info(msg)
	# 			return ActionResult(
	# 				extracted_content=msg, include_in_memory=True, long_term_memory='No dropdown options found'
	# 			)

	# 	except Exception as e:
	# 		logger.error(f'Failed to get dropdown options: {str(e)}')
	# 		msg = f'Error getting options: {str(e)}'
	# 		logger.info(msg)
	# 		return ActionResult(extracted_content=msg, include_in_memory=True)

	# TODO: Refactor to use events instead of direct page/dom access
	# @self.registry.action(
	# 	description='Select dropdown option or ARIA menu item for interactive element index by the text of the option you want to select',
	# )
	# async def select_dropdown_option(
	# 	index: int,
	# 	text: str,
	# 	browser_session: BrowserSession,
	# ) -> ActionResult:
	# 	"""Select dropdown option or ARIA menu item by the text of the option you want to select"""
	# 	page = await browser_session.get_current_page()
	# 	dom_element = await browser_session.get_dom_element_by_index(index)
	# 	if dom_element is None:
	# 		raise Exception(f'Element index {index} does not exist - retry or use alternative actions')

	# 	logger.debug(f"Attempting to select '{text}' using xpath: {dom_element.xpath}")
	# 	logger.debug(f'Element attributes: {dom_element.attributes}')
	# 	logger.debug(f'Element tag: {dom_element.tag_name}')

	# 	xpath = '//' + dom_element.xpath

	# 	try:
	# 		frame_index = 0
	# 		for frame in page.frames:
	# 			try:
	# 				logger.debug(f'Trying frame {frame_index} URL: {frame.url}')

	# 				# First check what type of element we're dealing with
	# 				element_info_js = """
	# 					(xpath) => {
	# 						try {
	# 							const element = document.evaluate(xpath, document, null,
	# 								XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
	# 							if (!element) return null;

	# 							const tagName = element.tagName.toLowerCase();
	# 							const role = element.getAttribute('role');

	# 							// Check if it's a native select
	# 							if (tagName === 'select') {
	# 								return {
	# 									type: 'select',
	# 									found: true,
	# 									id: element.id,
	# 									name: element.name,
	# 									tagName: element.tagName,
	# 									optionCount: element.options.length,
	# 									currentValue: element.value,
	# 									availableOptions: Array.from(element.options).map(o => o.text.trim())
	# 								};
	# 							}

	# 							// Check if it's an ARIA menu or similar
	# 							if (role === 'menu' || role === 'listbox' || role === 'combobox') {
	# 								const menuItems = element.querySelectorAll('[role="menuitem"], [role="option"]');
	# 								return {
	# 									type: 'aria',
	# 									found: true,
	# 									id: element.id || '',
	# 									role: role,
	# 									tagName: element.tagName,
	# 									itemCount: menuItems.length,
	# 									availableOptions: Array.from(menuItems).map(item => item.textContent.trim())
	# 								};
	# 							}

	# 							return {
	# 								error: `Element is neither a select nor an ARIA menu (tag: ${tagName}, role: ${role})`,
	# 								found: false
	# 							};
	# 						} catch (e) {
	# 							return {error: e.toString(), found: false};
	# 						}
	# 					}
	# 				"""

	# 				element_info = await frame.evaluate(element_info_js, dom_element.xpath)

	# 				if element_info and element_info.get('found'):
	# 					logger.debug(f'Found {element_info.get("type")} element in frame {frame_index}: {element_info}')

	# 					if element_info.get('type') == 'select':
	# 						# Handle native select element
	# 						# "label" because we are selecting by text
	# 						# nth(0) to disable error thrown by strict mode
	# 						# timeout=1000 because we are already waiting for all network events
	# 						selected_option_values = (
	# 							await frame.locator('//' + dom_element.xpath).nth(0).select_option(label=text, timeout=1000)
	# 						)

	# 						msg = f'selected option {text} with value {selected_option_values}'
	# 						logger.info(msg + f' in frame {frame_index}')

	# 						return ActionResult(
	# 							extracted_content=msg, include_in_memory=True, long_term_memory=f"Selected option '{text}'"
	# 						)

	# 					elif element_info.get('type') == 'aria':
	# 						# Handle ARIA menu
	# 						click_aria_item_js = """
	# 							(params) => {
	# 								const { xpath, targetText } = params;
	# 								try {
	# 									const element = document.evaluate(xpath, document, null,
	# 										XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
	# 									if (!element) return {success: false, error: 'Element not found'};

	# 									// Find all menu items
	# 									const menuItems = element.querySelectorAll('[role="menuitem"], [role="option"]');

	# 									for (const item of menuItems) {
	# 										const itemText = item.textContent.trim();
	# 										if (itemText === targetText) {
	# 											// Simulate click on the menu item
	# 											item.click();

	# 											// Also try dispatching a click event in case the click handler needs it
	# 											const clickEvent = new MouseEvent('click', {
	# 												view: window,
	# 												bubbles: true,
	# 												cancelable: true
	# 											});
	# 											item.dispatchEvent(clickEvent);

	# 											return {
	# 												success: true,
	# 												message: `Clicked menu item: ${targetText}`
	# 											};
	# 										}
	# 									}

	# 									return {
	# 										success: false,
	# 										error: `Menu item with text '${targetText}' not found`
	# 									};
	# 								} catch (e) {
	# 									return {success: false, error: e.toString()};
	# 								}
	# 							}
	# 						"""

	# 						result = await frame.evaluate(
	# 							click_aria_item_js, {'xpath': dom_element.xpath, 'targetText': text}
	# 						)

	# 						if result.get('success'):
	# 							msg = result.get('message', f'Selected ARIA menu item: {text}')
	# 							logger.info(msg + f' in frame {frame_index}')
	# 							return ActionResult(
	# 								extracted_content=msg,
	# 								include_in_memory=True,
	# 								long_term_memory=f"Selected menu item '{text}'",
	# 							)
	# 						else:
	# 							logger.error(f'Failed to select ARIA menu item: {result.get("error")}')
	# 							continue

	# 				elif element_info:
	# 					logger.error(f'Frame {frame_index} error: {element_info.get("error")}')
	# 					continue

	# 			except Exception as frame_e:
	# 				logger.error(f'Frame {frame_index} attempt failed: {str(frame_e)}')
	# 				logger.error(f'Frame type: {type(frame)}')
	# 				logger.error(f'Frame URL: {frame.url}')

	# 			frame_index += 1

	# 		msg = f"Could not select option '{text}' in any frame"
	# 		logger.info(msg)
	# 		return ActionResult(extracted_content=msg, include_in_memory=True, long_term_memory=msg)

	# 	except Exception as e:
	# 		msg = f'Selection failed: {str(e)}'
	# 		logger.error(msg)
	# 		raise BrowserError(msg)

	# @self.registry.action('Google Sheets: Get the contents of the entire sheet', domains=['https://docs.google.com'])
	# async def read_sheet_contents(browser_session: BrowserSession):
	# 	# Use send keys events to select and copy all cells
	# 	for key in ['Enter', 'Escape', 'ControlOrMeta+A', 'ControlOrMeta+C']:
	# 		event = browser_session.event_bus.dispatch(SendKeysEvent(keys=key))
	# 		await event

	# 	# Get page to evaluate clipboard
	# 	page = await browser_session.get_current_page()
	# 	extracted_tsv = await page.evaluate('() => navigator.clipboard.readText()')
	# 	return ActionResult(
	# 		extracted_content=extracted_tsv,
	# 		include_in_memory=True,
	# 		long_term_memory='Retrieved sheet contents',
	# 		include_extracted_content_only_once=True,
	# 	)

	# @self.registry.action('Google Sheets: Get the contents of a cell or range of cells', domains=['https://docs.google.com'])
	# async def read_cell_contents(cell_or_range: str, browser_session: BrowserSession):
	# 	page = await browser_session.get_current_page()

	# 	await select_cell_or_range(cell_or_range=cell_or_range, page=page)

	# 	await page.keyboard.press('ControlOrMeta+C')
	# 	await asyncio.sleep(0.1)
	# 	extracted_tsv = await page.evaluate('() => navigator.clipboard.readText()')
	# 	return ActionResult(
	# 		extracted_content=extracted_tsv,
	# 		include_in_memory=True,
	# 		long_term_memory=f'Retrieved contents from {cell_or_range}',
	# 		include_extracted_content_only_once=True,
	# 	)

	# @self.registry.action(
	# 	'Google Sheets: Update the content of a cell or range of cells', domains=['https://docs.google.com']
	# )
	# async def update_cell_contents(cell_or_range: str, new_contents_tsv: str, browser_session: BrowserSession):
	# 	page = await browser_session.get_current_page()

	# 	await select_cell_or_range(cell_or_range=cell_or_range, page=page)

	# 	# simulate paste event from clipboard with TSV content
	# 	await page.evaluate(f"""
	# 		const clipboardData = new DataTransfer();
	# 		clipboardData.setData('text/plain', `{new_contents_tsv}`);
	# 		document.activeElement.dispatchEvent(new ClipboardEvent('paste', {{clipboardData}}));
	# 	""")

	# 	return ActionResult(
	# 		extracted_content=f'Updated cells: {cell_or_range} = {new_contents_tsv}',
	# 		include_in_memory=False,
	# 		long_term_memory=f'Updated cells {cell_or_range} with {new_contents_tsv}',
	# 	)

	# @self.registry.action('Google Sheets: Clear whatever cells are currently selected', domains=['https://docs.google.com'])
	# async def clear_cell_contents(cell_or_range: str, browser_session: BrowserSession):
	# 	page = await browser_session.get_current_page()

	# 	await select_cell_or_range(cell_or_range=cell_or_range, page=page)

	# 	await page.keyboard.press('Backspace')
	# 	return ActionResult(
	# 		extracted_content=f'Cleared cells: {cell_or_range}',
	# 		include_in_memory=False,
	# 		long_term_memory=f'Cleared cells {cell_or_range}',
	# 	)

	# @self.registry.action('Google Sheets: Select a specific cell or range of cells', domains=['https://docs.google.com'])
	# async def select_cell_or_range(cell_or_range: str, browser_session: BrowserSession):
	# 	# Use send keys events for navigation
	# 	for key in ['Enter', 'Escape']:
	# 		event = browser_session.event_bus.dispatch(SendKeysEvent(keys=key))
	# 		await event
	# 	await asyncio.sleep(0.1)
	# 	for key in ['Home', 'ArrowUp']:
	# 		event = browser_session.event_bus.dispatch(SendKeysEvent(keys=key))
	# 		await event
	# 	await asyncio.sleep(0.1)
	# 	event = browser_session.event_bus.dispatch(SendKeysEvent(keys='Control+G'))
	# 	await event
	# 	await asyncio.sleep(0.2)
	# 	# Get page to type the cell range
	# 	page = await browser_session.get_current_page()
	# 	await page.keyboard.type(cell_or_range, delay=0.05)
	# 	await asyncio.sleep(0.2)
	# 	for key in ['Enter', 'Escape']:
	# 		event = browser_session.event_bus.dispatch(SendKeysEvent(keys=key))
	# 		await event
	# 		await asyncio.sleep(0.2)
	# 	return ActionResult(
	# 		extracted_content=f'Selected cells: {cell_or_range}',
	# 		include_in_memory=False,
	# 		long_term_memory=f'Selected cells {cell_or_range}',
	# 	)

	# @self.registry.action(
	# 	'Google Sheets: Fallback method to type text into (only one) currently selected cell',
	# 	domains=['https://docs.google.com'],
	# )
	# async def fallback_input_into_single_selected_cell(text: str, browser_session: BrowserSession):
	# 	# Get page to type text
	# 	page = await browser_session.get_current_page()
	# 	await page.keyboard.type(text, delay=0.1)
	# 	# Use send keys for Enter and ArrowUp
	# 	for key in ['Enter', 'ArrowUp']:
	# 		event = browser_session.event_bus.dispatch(SendKeysEvent(keys=key))
	# 		await event
	# 	return ActionResult(
	# 		extracted_content=f'Inputted text {text}',
	# 		include_in_memory=False,
	# 		long_term_memory=f"Inputted text '{text}' into cell",
	# 	)

	# Custom done action for structured output
	def _register_done_action(self, output_model: type[T] | None, display_files_in_done_text: bool = True):
		if output_model is not None:
			self.display_files_in_done_text = display_files_in_done_text

			@self.registry.action(
				'Complete task - with return text and if the task is finished (success=True) or not yet completely finished (success=False), because last step is reached',
				param_model=StructuredOutputAction[output_model],
			)
			async def done(params: StructuredOutputAction):
				# Exclude success from the output JSON since it's an internal parameter
				output_dict = params.data.model_dump()

				# Enums are not serializable, convert to string
				for key, value in output_dict.items():
					if isinstance(value, enum.Enum):
						output_dict[key] = value.value

				return ActionResult(
					is_done=True,
					success=params.success,
					extracted_content=json.dumps(output_dict),
					long_term_memory=f'Task completed. Success Status: {params.success}',
				)

		else:

			@self.registry.action(
				'Complete task - provide a summary of results for the user. Set success=True if task completed successfully, false otherwise. Text should be your response to the user summarizing results. Include files you would like to display to the user in files_to_display.',
				param_model=DoneAction,
			)
			async def done(params: DoneAction, file_system: FileSystem):
				user_message = params.text

				len_text = len(params.text)
				len_max_memory = 100
				memory = f'Task completed: {params.success} - {params.text[:len_max_memory]}'
				if len_text > len_max_memory:
					memory += f' - {len_text - len_max_memory} more characters'

				attachments = []
				if params.files_to_display:
					if self.display_files_in_done_text:
						file_msg = ''
						for file_name in params.files_to_display:
							if file_name == 'todo.md':
								continue
							file_content = file_system.display_file(file_name)
							if file_content:
								file_msg += f'\n\n{file_name}:\n{file_content}'
								attachments.append(file_name)
						if file_msg:
							user_message += '\n\nAttachments:'
							user_message += file_msg
						else:
							logger.warning('Agent wanted to display files but none were found')
					else:
						for file_name in params.files_to_display:
							if file_name == 'todo.md':
								continue
							file_content = file_system.display_file(file_name)
							if file_content:
								attachments.append(file_name)

				attachments = [str(file_system.get_dir() / file_name) for file_name in attachments]

				return ActionResult(
					is_done=True,
					success=params.success,
					extracted_content=user_message,
					long_term_memory=memory,
					attachments=attachments,
				)

	def use_structured_output_action(self, output_model: type[T]):
		self._register_done_action(output_model)

	# Register ---------------------------------------------------------------

	def action(self, description: str, **kwargs):
		"""Decorator for registering custom actions

		@param description: Describe the LLM what the function does (better description == better function calling)
		"""
		return self.registry.action(description, **kwargs)

	# Act --------------------------------------------------------------------
	@observe_debug(ignore_input=True, ignore_output=True, name='act')
	@time_execution_sync('--act')
	async def act(
		self,
		action: ActionModel,
		browser_session: BrowserSession,
		#
		page_extraction_llm: BaseChatModel | None = None,
		sensitive_data: dict[str, str | dict[str, str]] | None = None,
		available_file_paths: list[str] | None = None,
		file_system: FileSystem | None = None,
		#
		context: Context | None = None,
	) -> ActionResult:
		"""Execute an action"""

		for action_name, params in action.model_dump(exclude_unset=True).items():
			if params is not None:
				# Use Laminar span if available, otherwise use no-op context manager
				if Laminar is not None:
					span_context = Laminar.start_as_current_span(
						name=action_name,
						input={
							'action': action_name,
							'params': params,
						},
						span_type='TOOL',
					)
				else:
					# No-op context manager when lmnr is not available
					from contextlib import nullcontext

					span_context = nullcontext()

				with span_context:
					try:
						result = await self.registry.execute_action(
							action_name=action_name,
							params=params,
							browser_session=browser_session,
							page_extraction_llm=page_extraction_llm,
							file_system=file_system,
							sensitive_data=sensitive_data,
							available_file_paths=available_file_paths,
							context=context,
						)
					except Exception as e:
						result = ActionResult(error=str(e))

					if Laminar is not None:
						Laminar.set_span_output(result)

				if isinstance(result, str):
					return ActionResult(extracted_content=result)
				elif isinstance(result, ActionResult):
					return result
				elif result is None:
					return ActionResult()
				else:
					raise ValueError(f'Invalid action result type: {type(result)} of {result}')
		return ActionResult()
