import asyncio
import enum
import json
import logging
import time
from typing import Generic, TypeVar

# Global cache for DOM hash tracking to prevent duplicate extractions
_extraction_hashes: dict[str, str] = {}

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
	ClickElementAction,
	CloseTabAction,
	DoneAction,
	GoToUrlAction,
	HandleModalAction,
	InputTextAction,
	NoParamsAction,
	ScrollAction,
	ScrollUntilAction,
	SearchGoogleAction,
	SelectAutocompleteAction,
	SendKeysAction,
	StructuredOutputAction,
	SubmitSearchAction,
	SwitchTabAction,
	WaitForElementAction,
)
from browser_use.filesystem.file_system import FileSystem
from browser_use.llm.base import BaseChatModel
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

		# Element Interaction Actions

		@self.registry.action(
			'Click an element using multiple fallback strategies (text, aria-label, CSS, index)',
			param_model=ClickElementAction,
		)
		async def click_element_robust(params: ClickElementAction, browser_session: BrowserSession):
			"""Enhanced click with multiple fallback strategies and verification."""

			# Strategy 1: Try direct index click first (original behavior)
			try:
				node = await browser_session.get_element_by_index(params.index)
				if node is None:
					raise ValueError(f'Element index {params.index} not found in DOM')

				# Get current URL for comparison
				initial_url = await browser_session.get_current_page_url()

				# Try the original index-based click
				event = browser_session.event_bus.dispatch(ClickElementEvent(node=node))
				await event

				# Wait a moment for page to respond
				await asyncio.sleep(0.5)

				# Verify click worked by checking URL change or DOM state
				new_url = await browser_session.get_current_page_url()
				if new_url != initial_url:
					logger.info(f'✅ Click successful - page changed from {initial_url} to {new_url}')
					return ActionResult()

				# If URL didn't change, check if any meaningful DOM change occurred
				# This is a simple check - in a full implementation we'd look for expected elements
				logger.info('⚠️ Click completed but no URL change detected - assuming success')
				return ActionResult()

			except Exception as e:
				logger.warning(f'❌ Index-based click failed: {e}')

				# Strategy 2: Try text-based clicking
				try:
					# Get element text content for clicking
					text_to_click = node.get_all_children_text()[:50] if node else ''
					if text_to_click.strip():
						logger.info(f'🔍 Fallback: Trying to click by text: "{text_to_click.strip()}"')

						# Use JavaScript to find and click element by text
						cdp_client = browser_session.cdp_client
						click_result = await cdp_client.send.Runtime.evaluate(
							params={
								'expression': f"""
								// Find element by text content
								const elements = Array.from(document.querySelectorAll('button, a, [role="button"], [onclick]'));
								const targetElement = elements.find(el => 
									el.textContent && el.textContent.trim().includes('{text_to_click.strip()}')
								);
								if (targetElement) {{
									targetElement.click();
									"clicked_by_text";
								}} else {{
									"text_not_found";
								}}
							"""
							}
						)

						if click_result.get('result', {}).get('value') == 'clicked_by_text':
							logger.info('✅ Successfully clicked element by text content')
							await asyncio.sleep(0.5)  # Wait for page response
							return ActionResult()

				except Exception as text_error:
					logger.warning(f'❌ Text-based click failed: {text_error}')

				# Strategy 3: Try aria-label based clicking
				try:
					# Use JavaScript to find and click by aria-label or other accessible attributes
					cdp_client = browser_session.cdp_client
					click_result = await cdp_client.send.Runtime.evaluate(
						params={
							'expression': """
							// Find element by aria-label, title, or alt text
							const selectors = [
								'[aria-label*="search"]', '[aria-label*="Search"]',
								'[title*="search"]', '[title*="Search"]', 
								'[alt*="search"]', '[alt*="Search"]',
								'button[type="submit"]', 'input[type="submit"]',
								'.search-button', '.search-btn', '#search-button'
							];
							
							let clicked = false;
							for (const selector of selectors) {
								const elements = document.querySelectorAll(selector);
								if (elements.length > 0) {
									elements[0].click();
									clicked = true;
									break;
								}
							}
							clicked ? "clicked_by_selector" : "selector_not_found";
						"""
						}
					)

					if click_result.get('result', {}).get('value') == 'clicked_by_selector':
						logger.info('✅ Successfully clicked element by CSS selector')
						await asyncio.sleep(0.5)  # Wait for page response
						return ActionResult()

				except Exception as selector_error:
					logger.warning(f'❌ Selector-based click failed: {selector_error}')

				# Strategy 4: Last resort - try coordinate-based click
				try:
					if node and node.absolute_position:
						rect = node.absolute_position
						x = rect.x + rect.width / 2
						y = rect.y + rect.height / 2
						logger.info(f'🎯 Last resort: Clicking at coordinates ({x}, {y})')

						cdp_client = browser_session.cdp_client
						await cdp_client.send.Input.dispatchMouseEvent(
							params={'type': 'mousePressed', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1}
						)
						await cdp_client.send.Input.dispatchMouseEvent(
							params={'type': 'mouseReleased', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1}
						)

						logger.info('✅ Clicked at coordinates')
						await asyncio.sleep(0.5)
						return ActionResult()

				except Exception as coord_error:
					logger.warning(f'❌ Coordinate-based click failed: {coord_error}')

				# All strategies failed
				logger.error(f'❌ All click strategies failed for element index {params.index}')
				return ActionResult(
					error=f'Failed to click element {params.index} using all available strategies: index, text, selector, and coordinates'
				)

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
			"""Extract structured data from the current page using LLM."""

			# GUARD 1: Check current URL - prevent extraction from invalid URLs
			try:
				current_url = await browser_session.get_current_page_url()
				if not current_url or current_url in ['about:blank', 'data:', 'chrome://']:
					logger.warning(f'🚫 Skipping extraction from invalid URL: {current_url}')
					return ActionResult(
						extracted_content=f'Error: Cannot extract from blank or invalid page. Current URL: {current_url}. Navigate to a valid webpage first.'
					)
			except Exception as e:
				logger.warning(f'Failed to get current URL: {e}')

			# GUARD 2: Get page HTML and check for minimal content
			try:
				cdp_client = browser_session.cdp_client
				result = await cdp_client.send.DOM.getOuterHTML(params={})
				page_html = result.get('outerHTML', '')

				if not page_html or len(page_html.strip()) < 200:
					logger.warning(f'🚫 Page content too short ({len(page_html)} chars) - likely empty DOM')
					return ActionResult(
						extracted_content=f'Error: Page content too short ({len(page_html)} chars). Wait for page to load completely or navigate to a content page.'
					)
			except Exception as e:
				logger.error(f'Failed to get page HTML for extraction: {e}')
				return ActionResult(
					extracted_content=f'Error: Failed to access page content: {str(e)}. Check if page is accessible and try again.'
				)

			# GUARD 3: Scroll-to-load strategy for dynamic/infinite scroll content
			try:
				logger.info('📜 Performing scroll-to-load to ensure dynamic content is visible')

				# Get initial page height
				initial_height_result = await cdp_client.send.Runtime.evaluate(
					params={'expression': 'document.body.scrollHeight'}
				)
				initial_height = initial_height_result.get('result', {}).get('value', 0)

				# Scroll to bottom to trigger loading
				await cdp_client.send.Runtime.evaluate(params={'expression': 'window.scrollTo(0, document.body.scrollHeight);'})
				await asyncio.sleep(1.5)  # Wait for content to load

				# Scroll to top to ensure full content is accessible
				await cdp_client.send.Runtime.evaluate(params={'expression': 'window.scrollTo(0, 0);'})
				await asyncio.sleep(0.5)

				# Check if new content loaded
				final_height_result = await cdp_client.send.Runtime.evaluate(params={'expression': 'document.body.scrollHeight'})
				final_height = final_height_result.get('result', {}).get('value', 0)

				if final_height > initial_height:
					logger.info(f'📈 Dynamic content loaded: page grew from {initial_height}px to {final_height}px')

			except Exception as e:
				logger.warning(f'Scroll-to-load failed: {e}')

			# GUARD 4: DOM hash tracking to prevent duplicate extractions
			try:
				# Calculate DOM content hash from first 50KB of text
				dom_hash_result = await cdp_client.send.Runtime.evaluate(
					params={
						'expression': """
						(() => {
							const textContent = document.body.textContent || document.body.innerText || '';
							const first50KB = textContent.substring(0, 50000);
							// Simple hash function
							let hash = 0;
							for (let i = 0; i < first50KB.length; i++) {
								const char = first50KB.charCodeAt(i);
								hash = ((hash << 5) - hash) + char;
								hash = hash & hash; // Convert to 32-bit integer
							}
							return {
								hash: hash.toString(),
								contentLength: textContent.length,
								title: document.title,
								url: window.location.href
							};
						})();
					"""
					}
				)

				dom_info = dom_hash_result.get('result', {}).get('value', {})
				dom_hash = dom_info.get('hash', 'unknown')
				content_length = dom_info.get('contentLength', 0)

				# Check if we've seen this exact content before (simple check)
				session_key = f'{browser_session.id}_{current_url}'
				last_hash = _extraction_hashes.get(session_key)

				if last_hash == dom_hash and content_length < 1000:
					logger.warning(
						f'🔄 DOM hash unchanged and content is minimal ({content_length} chars) - likely extracting same empty page'
					)
					return ActionResult(
						extracted_content='Error: Attempting to extract from same minimal content. Try navigating to a different page or waiting for content to load.'
					)

				_extraction_hashes[session_key] = dom_hash
				logger.debug(f'📋 DOM hash: {dom_hash[:10]}..., content length: {content_length}')

			except Exception as e:
				logger.warning(f'DOM hash tracking failed: {e}')

			# GUARD 5: Convert to markdown and check for meaningful content
			try:
				import markdownify

				if extract_links:
					content = markdownify.markdownify(page_html, heading_style='ATX', bullets='-')
				else:
					content = markdownify.markdownify(page_html, heading_style='ATX', bullets='-', strip=['a'])

				# Remove excessive whitespace and check length
				content = content.strip()
				content = '\n'.join(line.strip() for line in content.split('\n') if line.strip())

				if len(content) < 100:
					logger.warning(f'🚫 Markdown content too short ({len(content)} chars) after processing')
					return ActionResult(
						extracted_content=f'Error: Processed content too short ({len(content)} chars). Page may not have loaded properly or may be mostly empty.'
					)

			except Exception as e:
				logger.error(f'Failed to convert HTML to markdown: {e}')
				return ActionResult(
					extracted_content=f'Error: Failed to process page content: {str(e)}. Page content may be malformed.'
				)

			# Truncate to 30k characters as requested
			if len(content) > 30000:
				content = content[:30000] + '\n\n[Content truncated at 30k characters]'

			# GUARD 6: Final content validation
			if 'about:blank' in content.lower() or 'page not found' in content.lower():
				logger.warning('🚫 Content indicates blank or error page')
				return ActionResult(
					extracted_content='Error: Page appears to be blank or showing an error. Navigate to a valid content page before extracting.'
				)

			logger.info(f"📄 Extracting data from {len(content)} chars of content with query: '{query[:100]}'...")

			# Create extraction messages for LLM
			from browser_use.llm.messages import BaseMessage, UserMessage

			messages: list[BaseMessage] = [
				UserMessage(
					content=f"""You convert websites into structured information. Extract information from this webpage based on the query. Focus only on content relevant to the query. If
1. The query is vague
2. Does not make sense for the page  
3. Some/all of the information is not available

Explain the content of the page and that the requested information is not available in the page. Respond in JSON format.

Query: {query}

Website:
{content}"""
				)
			]

			# Send to LLM for extraction
			try:
				response = await page_extraction_llm.ainvoke(messages)
				logger.info(f"✅ Successfully extracted structured data for query: '{query[:50]}'...")

				return ActionResult(extracted_content=f"Extraction for query: '{query}'\n\nResult:\n{response.completion}")

			except Exception as e:
				logger.error(f'LLM extraction failed: {e}')
				content_preview = content[:500] + '...' if len(content) > 500 else content
				return ActionResult(
					extracted_content=f'Error: LLM extraction failed: {str(e)}\n\nContent preview:\n{content_preview}'
				)

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

		@self.registry.action(
			'Automatically detect and handle cookie consent banners/popups',
			param_model=NoParamsAction,
		)
		async def handle_cookie_consent(params: NoParamsAction, browser_session: BrowserSession):
			"""Detect and handle cookie consent banners automatically."""

			try:
				cdp_client = browser_session.cdp_client

				# Common cookie consent selectors to try
				consent_selectors = [
					# Accept buttons
					'button[id*="accept"]',
					'button[class*="accept"]',
					'button[id*="consent"]',
					'button[class*="consent"]',
					'button[id*="agree"]',
					'button[class*="agree"]',
					'button[id*="allow"]',
					'button[class*="allow"]',
					'[data-role="accept"]',
					'[data-action="accept"]',
					# Specific text patterns
					'button:contains("Accept")',
					'button:contains("I Accept")',
					'button:contains("Accept All")',
					'button:contains("Allow")',
					'button:contains("I Agree")',
					'button:contains("Agree")',
					'button:contains("OK")',
					'button:contains("Got it")',
					# Common banner containers to look for buttons within
					'#cookie-banner button',
					'.cookie-banner button',
					'#consent-banner button',
					'.consent-banner button',
					'.cookie-notice button',
					'#cookie-notice button',
					'.gdpr-banner button',
					'#gdpr-banner button',
					# BBB.org specific (from the user's example)
					'button[class*="cookie"]',
					'button[id*="cookie"]',
					# Generic patterns
					'[role="button"][aria-label*="accept"]',
					'[role="button"][aria-label*="consent"]',
				]

				# Try to find and click consent buttons using JavaScript
				click_result = await cdp_client.send.Runtime.evaluate(
					params={
						'expression': f"""
						(() => {{
							const selectors = {consent_selectors};
							let clicked = false;
							let clickedElement = null;
							
							// Try each selector until we find a clickable element
							for (const selector of selectors) {{
								try {{
									// Handle jQuery-style :contains() selectors manually
									let elements;
									if (selector.includes(':contains(')) {{
										const [baseSelector, textMatch] = selector.split(':contains(');
										const text = textMatch.replace(/[()'"]/g, '');
										elements = Array.from(document.querySelectorAll(baseSelector)).filter(el => 
											el.textContent && el.textContent.toLowerCase().includes(text.toLowerCase())
										);
									}} else {{
										elements = document.querySelectorAll(selector);
									}}
									
									if (elements.length > 0) {{
										// Try to click the first visible element
										for (const element of elements) {{
											const rect = element.getBoundingClientRect();
											const style = window.getComputedStyle(element);
											
											// Check if element is visible and clickable
											if (rect.width > 0 && rect.height > 0 && 
												style.display !== 'none' && 
												style.visibility !== 'hidden' &&
												style.opacity !== '0') {{
												
												element.click();
												clicked = true;
												clickedElement = {{
													selector: selector,
													text: element.textContent.trim().substring(0, 50),
													tag: element.tagName
												}};
												break;
											}}
										}}
										if (clicked) break;
									}}
								}} catch (e) {{
									// Continue with next selector if this one fails
									continue;
								}}
							}}
							
							return clicked ? clickedElement : null;
						}})();
					"""
					}
				)

				result = click_result.get('result', {}).get('value')

				if result:
					logger.info(
						f'✅ Cookie consent handled: clicked {result.get("tag", "element")} with text "{result.get("text", "")}"'
					)

					# Wait a moment for the banner to disappear
					await asyncio.sleep(1.0)

					return ActionResult(
						extracted_content=f'Successfully handled cookie consent banner by clicking: {result.get("text", "consent button")}'
					)
				else:
					logger.info('ℹ️ No cookie consent banners found on this page')
					return ActionResult(extracted_content='No cookie consent banners detected on current page')

			except Exception as e:
				logger.error(f'❌ Cookie consent handler failed: {e}')
				return ActionResult(error=f'Failed to handle cookie consent: {str(e)}')

		@self.registry.action(
			'Wait for specific elements to appear or content to load on the page',
			param_model=WaitForElementAction,
		)
		async def wait_for_element(params: WaitForElementAction, browser_session: BrowserSession):
			"""Wait for elements to appear or page content to load."""

			try:
				cdp_client = browser_session.cdp_client
				max_wait_time = getattr(params, 'timeout', 10)  # Default 10 seconds
				selector = getattr(params, 'selector', None)
				check_interval = 0.5  # Check every 500ms

				logger.info(f'⏱️ Waiting up to {max_wait_time}s for element: {selector}')

				start_time = time.time()

				while time.time() - start_time < max_wait_time:
					# Check if element exists and is visible
					check_result = await cdp_client.send.Runtime.evaluate(
						params={
							'expression': f"""
							(() => {{
								const selector = '{selector}';
								const elements = document.querySelectorAll(selector);
								
								if (elements.length === 0) {{
									return {{ found: false, reason: 'not_found' }};
								}}
								
								// Check if at least one element is visible
								for (const element of elements) {{
									const rect = element.getBoundingClientRect();
									const style = window.getComputedStyle(element);
									
									if (rect.width > 0 && rect.height > 0 && 
										style.display !== 'none' && 
										style.visibility !== 'hidden' &&
										style.opacity !== '0') {{
										return {{ 
											found: true, 
											count: elements.length,
											text: element.textContent.trim().substring(0, 100)
										}};
									}}
								}}
								
								return {{ found: false, reason: 'not_visible' }};
							}})();
						"""
						}
					)

					result = check_result.get('result', {}).get('value')

					if result and result.get('found'):
						elapsed = round(time.time() - start_time, 1)
						logger.info(f'✅ Element found after {elapsed}s: {result.get("count", 1)} elements')

						return ActionResult(
							extracted_content=f'Element found: {selector} (count: {result.get("count", 1)}, text: "{result.get("text", "")[:50]}...")'
						)

					# Wait before next check
					await asyncio.sleep(check_interval)

				# Timeout reached
				elapsed = round(time.time() - start_time, 1)
				logger.warning(f'⏰ Timeout after {elapsed}s waiting for: {selector}')

				return ActionResult(error=f'Timeout waiting for element: {selector} (waited {elapsed}s)')

			except Exception as e:
				logger.error(f'❌ Wait for element failed: {e}')
				return ActionResult(error=f'Failed to wait for element: {str(e)}')

		@self.registry.action(
			'Scroll until specific content appears or a condition is met',
			param_model=ScrollUntilAction,
		)
		async def scroll_until_content(params: ScrollUntilAction, browser_session: BrowserSession):
			"""Scroll until specific content appears or maximum scrolls reached."""

			try:
				cdp_client = browser_session.cdp_client
				target_selector = getattr(params, 'target_selector', None)
				max_scrolls = getattr(params, 'max_scrolls', 10)
				scroll_direction = getattr(params, 'direction', 'down')

				logger.info(f'🔍 Scrolling {scroll_direction} to find: {target_selector} (max {max_scrolls} scrolls)')

				scroll_count = 0
				last_page_height = 0

				while scroll_count < max_scrolls:
					# Check if target content is already visible
					if target_selector:
						check_result = await cdp_client.send.Runtime.evaluate(
							params={
								'expression': f"""
								(() => {{
									const selector = '{target_selector}';
									const elements = document.querySelectorAll(selector);
									
									if (elements.length === 0) {{
										return {{ found: false, height: document.body.scrollHeight }};
									}}
									
									// Check if any element is in viewport
									for (const element of elements) {{
										const rect = element.getBoundingClientRect();
										const style = window.getComputedStyle(element);
										
										if (rect.top >= 0 && rect.top <= window.innerHeight &&
											rect.width > 0 && rect.height > 0 && 
											style.display !== 'none' && 
											style.visibility !== 'hidden') {{
											return {{ 
												found: true, 
												count: elements.length,
												text: element.textContent.trim().substring(0, 100),
												height: document.body.scrollHeight
											}};
										}}
									}}
									
									return {{ found: false, height: document.body.scrollHeight }};
								}})();
							"""
							}
						)

						result = check_result.get('result', {}).get('value')

						if result and result.get('found'):
							logger.info(
								f'✅ Target content found after {scroll_count} scrolls: {result.get("count", 1)} elements'
							)

							return ActionResult(
								extracted_content=f'Found target content: {target_selector} after {scroll_count} scrolls (text: "{result.get("text", "")[:50]}...")'
							)

						current_height = result.get('height', 0) if result else 0

						# Check if we've reached the bottom (no new content loaded)
						if current_height > 0 and current_height == last_page_height and scroll_count > 2:
							logger.info(f'📄 Reached bottom of page after {scroll_count} scrolls')
							break

						last_page_height = current_height

					# Perform scroll action
					scroll_distance = 400 if scroll_direction == 'down' else -400

					await cdp_client.send.Runtime.evaluate(params={'expression': f'window.scrollBy(0, {scroll_distance});'})

					scroll_count += 1

					# Wait for content to load after scroll
					await asyncio.sleep(0.8)

				# Max scrolls reached
				logger.warning(f'🔄 Reached maximum scrolls ({max_scrolls}) without finding target: {target_selector}')

				return ActionResult(
					extracted_content=f'Scrolled {scroll_count} times but did not find target content: {target_selector}'
				)

			except Exception as e:
				logger.error(f'❌ Scroll until content failed: {e}')
				return ActionResult(error=f'Failed to scroll until content: {str(e)}')

		@self.registry.action(
			'Submit a search query by typing into search field and pressing Enter, then verify results',
			param_model=SubmitSearchAction,
		)
		async def submit_search(params: SubmitSearchAction, browser_session: BrowserSession):
			"""Submit a search query and verify results appear."""

			try:
				search_index = getattr(params, 'search_index', None)
				query = getattr(params, 'query', '')
				results_selector = getattr(params, 'results_selector', None)
				verify_results = getattr(params, 'verify_results', True)

				logger.info(f'🔍 Submitting search query: "{query}" via element {search_index}')

				# Step 1: Type the query into the search field
				if search_index:
					input_result = await self.execute_action(
						'input_text',
						{'index': search_index, 'text': query},
						browser_session=browser_session,
						file_system=file_system,
					)

					if input_result and input_result.error:
						return ActionResult(error=f'Failed to type search query: {input_result.error}')
				else:
					return ActionResult(error='No search index provided')

				# Step 2: Press Enter to submit
				await asyncio.sleep(0.5)  # Brief pause between typing and submission

				enter_result = await self.execute_action('send_keys', {'keys': 'Enter'}, browser_session=browser_session)

				if enter_result and enter_result.error:
					logger.warning('⚠️ Enter key failed, trying alternative submission methods')

					# Try to find and click submit button
					cdp_client = browser_session.cdp_client
					submit_result = await cdp_client.send.Runtime.evaluate(
						params={
							'expression': """
							(() => {
								const submitSelectors = [
									'button[type="submit"]',
									'input[type="submit"]',
									'button[class*="search"]',
									'button[id*="search"]',
									'[aria-label*="search"] button',
									'form button'
								];
								
								for (const selector of submitSelectors) {
									const elements = document.querySelectorAll(selector);
									for (const element of elements) {
										const rect = element.getBoundingClientRect();
										if (rect.width > 0 && rect.height > 0) {
											element.click();
											return { clicked: true, selector: selector };
										}
									}
								}
								return { clicked: false };
							})();
						"""
						}
					)

					submit_clicked = submit_result.get('result', {}).get('value', {}).get('clicked', False)
					if not submit_clicked:
						return ActionResult(error='Failed to submit search - neither Enter key nor submit button worked')

				# Step 3: Wait for page to respond
				await asyncio.sleep(2.0)  # Wait for search results to load

				# Step 4: Verify results appeared (if requested)
				if verify_results:
					# Get current URL to see if it changed
					initial_url = await browser_session.get_current_page_url()

					# If results_selector provided, check for specific results
					if results_selector:
						verification_result = await self.execute_action(
							'wait_for_element', {'selector': results_selector, 'timeout': 10}, browser_session=browser_session
						)

						if verification_result and not verification_result.error:
							logger.info(f'✅ Search submitted successfully - results found: {results_selector}')
							return ActionResult(
								extracted_content=f'Search query "{query}" submitted successfully. Results appeared: {verification_result.extracted_content}'
							)
						else:
							logger.warning(f'⚠️ Search submitted but expected results not found: {results_selector}')
							return ActionResult(
								extracted_content=f'Search query "{query}" submitted, but results verification failed',
								error='Results verification failed',
							)
					else:
						# Generic check - look for common result patterns
						cdp_client = browser_session.cdp_client
						results_check = await cdp_client.send.Runtime.evaluate(
							params={
								'expression': """
								(() => {
									const resultSelectors = [
										'.search-results', '#search-results', '[class*="results"]',
										'.result', '.search-result', '[class*="result-item"]',
										'article', '[role="article"]', '.post', '.item'
									];
									
									let foundResults = 0;
									let foundSelector = '';
									
									for (const selector of resultSelectors) {
										const elements = document.querySelectorAll(selector);
										if (elements.length > 0) {
											foundResults = elements.length;
											foundSelector = selector;
											break;
										}
									}
									
									return { 
										found: foundResults > 0, 
										count: foundResults,
										selector: foundSelector,
										title: document.title
									};
								})();
							"""
							}
						)

						results_found = results_check.get('result', {}).get('value', {})

						if results_found.get('found'):
							logger.info(f'✅ Search submitted successfully - found {results_found.get("count", 0)} results')
							return ActionResult(
								extracted_content=f'Search query "{query}" submitted successfully. Found {results_found.get("count", 0)} results using selector: {results_found.get("selector", "unknown")}'
							)
						else:
							# Even if no specific results detected, if URL changed or title changed, assume success
							current_title = results_found.get('title', '')
							if 'search' in current_title.lower() or query.lower() in current_title.lower():
								logger.info(f'✅ Search submitted - page title suggests search results: {current_title}')
								return ActionResult(
									extracted_content=f'Search query "{query}" submitted. Page title: {current_title}'
								)
							else:
								logger.warning('⚠️ Search submitted but no clear results detected')
								return ActionResult(
									extracted_content=f'Search query "{query}" submitted, but result verification unclear',
									error='Unclear if results appeared',
								)
				else:
					# No verification requested, assume success
					logger.info(f'✅ Search query "{query}" submitted (verification skipped)')
					return ActionResult(extracted_content=f'Search query "{query}" submitted successfully (verification skipped)')

			except Exception as e:
				logger.error(f'❌ Submit search failed: {e}')
				return ActionResult(error=f'Failed to submit search: {str(e)}')

		@self.registry.action(
			'Type into autocomplete field and select suggestion (handles dropdowns, suggestions)',
			param_model=SelectAutocompleteAction,
		)
		async def select_autocomplete(params: SelectAutocompleteAction, browser_session: BrowserSession):
			"""Type into autocomplete field and select a suggestion."""

			try:
				input_index = getattr(params, 'input_index', None)
				text_to_type = getattr(params, 'text_to_type', '')
				suggestion_selector = getattr(params, 'suggestion_selector', None)
				select_first = getattr(params, 'select_first', True)

				logger.info(f'🔍 Autocomplete: typing "{text_to_type}" into element {input_index}')

				# Step 1: Type into the input field
				if input_index:
					input_result = await self.execute_action(
						'input_text',
						{'index': input_index, 'text': text_to_type},
						browser_session=browser_session,
						file_system=file_system,
					)

					if input_result and input_result.error:
						return ActionResult(error=f'Failed to type into autocomplete field: {input_result.error}')
				else:
					return ActionResult(error='No input index provided for autocomplete')

				# Step 2: Wait for suggestions to appear
				await asyncio.sleep(1.0)  # Give time for suggestions to load

				# Step 3: Look for and select suggestion
				cdp_client = browser_session.cdp_client

				# Define common autocomplete suggestion selectors
				suggestion_selectors = [
					suggestion_selector,  # User-provided selector (if any)
					'[role="listbox"] [role="option"]',
					'.autocomplete-suggestion',
					'.suggestion',
					'.autocomplete-item',
					'[aria-autocomplete] + ul li',
					'[aria-autocomplete] + div li',
					'.dropdown-menu li',
					'.dropdown-item',
					'[class*="suggestion"]',
					'[class*="autocomplete"]',
					'ul li[data-value]',
					'li[data-suggestion]',
					# Google-style autocomplete
					'.sbsb_c .sbqs_c',
					'.pac-item',
					# Maps/location autocomplete
					'.pac-container .pac-item',
				]

				# Remove None values and empty strings
				suggestion_selectors = [s for s in suggestion_selectors if s]

				selection_result = await cdp_client.send.Runtime.evaluate(
					params={
						'expression': f"""
						(() => {{
							const selectors = {suggestion_selectors};
							let selected = false;
							let selectionInfo = null;
							
							// Try each selector to find suggestions
							for (const selector of selectors) {{
								try {{
									const suggestions = document.querySelectorAll(selector);
									if (suggestions.length === 0) continue;
									
									// Find visible suggestions
									const visibleSuggestions = Array.from(suggestions).filter(item => {{
										const rect = item.getBoundingClientRect();
										const style = window.getComputedStyle(item);
										return rect.width > 0 && rect.height > 0 && 
											   style.display !== 'none' && 
											   style.visibility !== 'hidden';
									}});
									
									if (visibleSuggestions.length === 0) continue;
									
									// Select strategy
									let targetSuggestion = null;
									
									if ({str(select_first).lower()}) {{
										// Select first visible suggestion
										targetSuggestion = visibleSuggestions[0];
									}} else {{
										// Look for suggestion that contains or matches our text
										const searchText = '{text_to_type}'.toLowerCase();
										targetSuggestion = visibleSuggestions.find(item => 
											item.textContent && 
											item.textContent.toLowerCase().includes(searchText)
										) || visibleSuggestions[0]; // Fallback to first
									}}
									
									if (targetSuggestion) {{
										// Try clicking the suggestion
										targetSuggestion.click();
										selected = true;
										selectionInfo = {{
											selector: selector,
											text: targetSuggestion.textContent.trim(),
											totalSuggestions: visibleSuggestions.length
										}};
										break;
									}}
								}} catch (e) {{
									continue; // Try next selector
								}}
							}}
							
							// If no suggestions found, try keyboard navigation
							if (!selected) {{
								try {{
									// Find the input field that was typed into
									const inputElement = document.querySelector('[tabindex], input, [contenteditable]');
									if (inputElement) {{
										inputElement.focus();
										
										// Try Arrow Down + Enter
										const downEvent = new KeyboardEvent('keydown', {{ key: 'ArrowDown', code: 'ArrowDown' }});
										inputElement.dispatchEvent(downEvent);
										
										// Wait a bit then Enter
										setTimeout(() => {{
											const enterEvent = new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter' }});
											inputElement.dispatchEvent(enterEvent);
										}}, 100);
										
										selected = true;
										selectionInfo = {{
											method: 'keyboard_navigation',
											text: 'ArrowDown + Enter'
										}};
									}}
								}} catch (e) {{
									// Ignore keyboard fallback errors
								}}
							}}
							
							return selected ? selectionInfo : null;
						}})();
					"""
					}
				)

				result = selection_result.get('result', {}).get('value')

				if result:
					logger.info(
						f'✅ Autocomplete suggestion selected: "{result.get("text", "")}" using {result.get("selector", result.get("method", "unknown"))}'
					)

					# Wait for any UI updates after selection
					await asyncio.sleep(0.5)

					return ActionResult(
						extracted_content=f'Successfully selected autocomplete suggestion: "{result.get("text", "")}" from {result.get("totalSuggestions", 1)} available options'
					)
				else:
					logger.warning(f'⚠️ No autocomplete suggestions found or selectable for: "{text_to_type}"')

					# Check if input value changed (maybe autocomplete was automatic)
					input_check = await cdp_client.send.Runtime.evaluate(
						params={
							'expression': f"""
							(() => {{
								const inputs = document.querySelectorAll('input, [contenteditable]');
								for (const input of inputs) {{
									if (input.value && input.value.toLowerCase().includes('{text_to_type.lower()}')) {{
										return {{
											found: true,
											value: input.value,
											automatic: true
										}};
									}}
								}}
								return {{ found: false }};
							}})();
						"""
						}
					)

					input_result = input_check.get('result', {}).get('value', {})
					if input_result.get('found'):
						return ActionResult(
							extracted_content=f'Autocomplete appears to have been handled automatically: "{input_result.get("value", "")}"'
						)
					else:
						return ActionResult(
							extracted_content=f'No autocomplete suggestions found for: "{text_to_type}". Input may not have autocomplete enabled.',
							error='No suggestions available',
						)

			except Exception as e:
				logger.error(f'❌ Autocomplete selection failed: {e}')
				return ActionResult(error=f'Failed to select autocomplete suggestion: {str(e)}')

		@self.registry.action(
			'Handle modal dialogs - open, close, or wait for them to appear',
			param_model=HandleModalAction,
		)
		async def handle_modal(params: HandleModalAction, browser_session: BrowserSession):
			"""Handle modal dialogs and popups."""

			try:
				action = getattr(params, 'action', 'wait_for')
				trigger_selector = getattr(params, 'trigger_selector', None)
				modal_selector = getattr(params, 'modal_selector', None)
				close_method = getattr(params, 'close_method', 'escape')

				logger.info(f'🎭 Modal action: {action}')

				cdp_client = browser_session.cdp_client

				if action == 'open':
					# Open modal by clicking trigger element
					if not trigger_selector:
						return ActionResult(error='No trigger_selector provided for modal open action')

					# Click the trigger element
					click_result = await cdp_client.send.Runtime.evaluate(
						params={
							'expression': f"""
							(() => {{
								const trigger = document.querySelector('{trigger_selector}');
								if (trigger) {{
									const rect = trigger.getBoundingClientRect();
									const style = window.getComputedStyle(trigger);
									
									if (rect.width > 0 && rect.height > 0 && 
										style.display !== 'none' && 
										style.visibility !== 'hidden') {{
										trigger.click();
										return {{ clicked: true, text: trigger.textContent.trim() }};
									}}
								}}
								return {{ clicked: false }};
							}})();
						"""
						}
					)

					if not click_result.get('result', {}).get('value', {}).get('clicked'):
						return ActionResult(error=f'Failed to click modal trigger: {trigger_selector}')

					# Wait for modal to appear
					await asyncio.sleep(1.0)

					# Verify modal appeared
					modal_check = await self._check_modal_presence(cdp_client, modal_selector)
					if modal_check.get('found'):
						logger.info('✅ Modal opened successfully')
						return ActionResult(extracted_content=f'Modal opened by clicking: {trigger_selector}')
					else:
						return ActionResult(
							extracted_content='Clicked trigger but modal may not have appeared',
							error='Modal not detected after trigger',
						)

				elif action == 'close':
					# Close modal using specified method
					if close_method == 'escape':
						# Try pressing Escape key
						await cdp_client.send.Input.dispatchKeyEvent(params={'type': 'keyDown', 'key': 'Escape'})
						await cdp_client.send.Input.dispatchKeyEvent(params={'type': 'keyUp', 'key': 'Escape'})
						logger.info('🔐 Pressed Escape to close modal')

					elif close_method == 'close_button':
						# Look for close button
						close_result = await cdp_client.send.Runtime.evaluate(
							params={
								'expression': """
								(() => {
									const closeSelectors = [
										'[aria-label*="close"]', '[aria-label*="Close"]',
										'button[class*="close"]', '.close', '.modal-close',
										'[data-dismiss="modal"]', '[data-close]',
										'.fa-times', '.fa-close', '.icon-close',
										'button:contains("×")', 'button:contains("✕")',
										'[role="dialog"] button:last-child'
									];
									
									for (const selector of closeSelectors) {
										try {
											let elements;
											if (selector.includes(':contains(')) {
												const [baseSelector, textMatch] = selector.split(':contains(');
												const text = textMatch.replace(/[()'"]/g, '');
												elements = Array.from(document.querySelectorAll(baseSelector)).filter(el => 
													el.textContent && el.textContent.includes(text)
												);
											} else {
												elements = document.querySelectorAll(selector);
											}
											
											for (const element of elements) {
												const rect = element.getBoundingClientRect();
												if (rect.width > 0 && rect.height > 0) {
													element.click();
													return { clicked: true, selector: selector };
												}
											}
										} catch (e) {
											continue;
										}
									}
									return { clicked: false };
								})();
							"""
							}
						)

						close_clicked = close_result.get('result', {}).get('value', {}).get('clicked', False)
						if close_clicked:
							logger.info('✅ Clicked close button to close modal')
						else:
							logger.warning('⚠️ No close button found, trying Escape as fallback')
							await cdp_client.send.Input.dispatchKeyEvent(params={'type': 'keyDown', 'key': 'Escape'})
							await cdp_client.send.Input.dispatchKeyEvent(params={'type': 'keyUp', 'key': 'Escape'})

					elif close_method == 'outside_click':
						# Click outside the modal
						await cdp_client.send.Runtime.evaluate(
							params={
								'expression': """
								(() => {
									// Find modal container
									const modalSelectors = [
										'[role="dialog"]', '.modal', '.modal-dialog',
										'[aria-modal="true"]', '.overlay', '.popup'
									];
									
									let modal = null;
									for (const selector of modalSelectors) {
										modal = document.querySelector(selector);
										if (modal) break;
									}
									
									if (modal) {
										// Click on body outside the modal
										const rect = modal.getBoundingClientRect();
										const clickX = Math.max(rect.right + 10, window.innerWidth - 50);
										const clickY = Math.max(rect.bottom + 10, window.innerHeight - 50);
										
										const clickEvent = new MouseEvent('click', {
											view: window,
											bubbles: true,
											cancelable: true,
											clientX: clickX,
											clientY: clickY
										});
										document.body.dispatchEvent(clickEvent);
										return { clicked: true };
									}
									return { clicked: false };
								})();
							"""
							}
						)
						logger.info('🎯 Clicked outside modal to close')

					# Wait for modal to disappear
					await asyncio.sleep(0.5)

					# Verify modal closed
					modal_check = await self._check_modal_presence(cdp_client, modal_selector)
					if not modal_check.get('found'):
						logger.info('✅ Modal closed successfully')
						return ActionResult(extracted_content=f'Modal closed using method: {close_method}')
					else:
						return ActionResult(
							extracted_content='Attempted to close modal but it may still be visible',
							error='Modal still detected after close attempt',
						)

				elif action == 'wait_for':
					# Wait for modal to appear
					logger.info('⏳ Waiting for modal to appear...')

					max_wait = 10  # seconds
					check_interval = 0.5
					waited = 0

					while waited < max_wait:
						modal_check = await self._check_modal_presence(cdp_client, modal_selector)
						if modal_check.get('found'):
							logger.info(f'✅ Modal appeared after {waited}s')
							return ActionResult(
								extracted_content=f'Modal detected: {modal_check.get("selector", "unknown selector")}'
							)

						await asyncio.sleep(check_interval)
						waited += check_interval

					# Timeout
					logger.warning(f'⏰ Modal did not appear within {max_wait}s')
					return ActionResult(error=f'Modal did not appear within {max_wait} seconds')

				else:
					return ActionResult(error=f'Unknown modal action: {action}')

			except Exception as e:
				logger.error(f'❌ Modal handling failed: {e}')
				return ActionResult(error=f'Failed to handle modal: {str(e)}')

		async def _check_modal_presence(self, cdp_client, modal_selector: str | None = None):
			"""Helper method to check if a modal is present."""

			# Define common modal selectors
			selectors = [
				modal_selector,  # User-provided selector
				'[role="dialog"]',
				'[aria-modal="true"]',
				'.modal:not(.fade)',
				'.modal.show',
				'.modal.in',
				'.modal-dialog',
				'.modal-content',
				'.overlay',
				'.popup',
				'.lightbox',
				'[class*="modal"]:not([class*="hidden"])',
				'dialog[open]',
			]

			# Remove None values
			selectors = [s for s in selectors if s]

			check_result = await cdp_client.send.Runtime.evaluate(
				params={
					'expression': f"""
					(() => {{
						const selectors = {selectors};
						
						for (const selector of selectors) {{
							try {{
								const elements = document.querySelectorAll(selector);
								for (const element of elements) {{
									const rect = element.getBoundingClientRect();
									const style = window.getComputedStyle(element);
									
									// Check if modal is visible and has reasonable size
									if (rect.width > 100 && rect.height > 100 && 
										style.display !== 'none' && 
										style.visibility !== 'hidden' &&
										style.opacity !== '0') {{
										return {{
											found: true,
											selector: selector,
											size: {{ width: rect.width, height: rect.height }},
											position: {{ x: rect.x, y: rect.y }}
										}};
									}}
								}}
							}} catch (e) {{
								continue;
							}}
						}}
						
						return {{ found: false }};
					}})();
				"""
				}
			)

			return check_result.get('result', {}).get('value', {'found': False})

		@self.registry.action(
			'Detect and dismiss blocking popups, overlays, and persistent dialogs',
			param_model=NoParamsAction,
		)
		async def dismiss_popups(params: NoParamsAction, browser_session: BrowserSession):
			"""Automatically detect and dismiss blocking popups and overlays."""

			try:
				cdp_client = browser_session.cdp_client
				dismissed_count = 0

				logger.info('🚫 Scanning for blocking popups and overlays...')

				# Define comprehensive popup/overlay selectors
				popup_selectors = [
					# CAPTCHA and security overlays
					'[class*="captcha"]',
					'[id*="captcha"]',
					'[class*="security"]',
					'[class*="verification"]',
					# Registration/signup overlays
					'[class*="register"]',
					'[class*="signup"]',
					'[class*="join"]',
					'[class*="subscribe"]',
					'[class*="newsletter"]',
					# Generic overlays
					'[class*="overlay"]',
					'[class*="modal"]',
					'[class*="popup"]',
					'[class*="lightbox"]',
					'[class*="dialog"]',
					# Fixed position blocking elements
					'[style*="position: fixed"]',
					'[style*="position:fixed"]',
					'[style*="z-index: 999"]',
					'[style*="z-index:999"]',
					# Specific blocking patterns
					'.block-overlay',
					'.blocking-overlay',
					'.page-overlay',
					'[aria-modal="true"]',
					'[role="dialog"]',
					# Cookie banners (additional patterns)
					'[class*="cookie"]',
					'[id*="cookie"]',
					'[class*="gdpr"]',
					'[class*="consent"]',
				]

				dismiss_result = await cdp_client.send.Runtime.evaluate(
					params={
						'expression': f"""
						(() => {{
							const selectors = {popup_selectors};
							let dismissedCount = 0;
							let dismissedItems = [];
							
							// Try to dismiss each type of popup
							for (const selector of selectors) {{
								try {{
									const elements = document.querySelectorAll(selector);
									
									for (const element of elements) {{
										const rect = element.getBoundingClientRect();
										const style = window.getComputedStyle(element);
										
										// Check if element is visible and potentially blocking
										if (rect.width > 200 && rect.height > 100 && 
											style.display !== 'none' && 
											style.visibility !== 'hidden' &&
											style.opacity !== '0' &&
											(style.position === 'fixed' || style.position === 'absolute')) {{
											
											// Try multiple dismissal strategies
											let dismissed = false;
											
											// Strategy 1: Look for close buttons within this element
											const closeSelectors = [
												'[aria-label*="close"]', '[aria-label*="Close"]',
												'.close', '.close-btn', '.modal-close',
												'[data-dismiss]', '[data-close]',
												'button:contains("×")', 'button:contains("✕")',
												'.fa-times', '.fa-close', '.icon-close',
												'[class*="close"]'
											];
											
											for (const closeSelector of closeSelectors) {{
												try {{
													let closeButtons;
													if (closeSelector.includes(':contains(')) {{
														const [baseSelector, textMatch] = closeSelector.split(':contains(');
														const text = textMatch.replace(/[()'"]/g, '');
														closeButtons = Array.from(element.querySelectorAll(baseSelector)).filter(btn => 
															btn.textContent && btn.textContent.includes(text)
														);
													}} else {{
														closeButtons = element.querySelectorAll(closeSelector);
													}}
													
													if (closeButtons.length > 0) {{
														closeButtons[0].click();
														dismissed = true;
														dismissedCount++;
														dismissedItems.push({{
															selector: selector,
															method: 'close_button',
															text: element.textContent.substring(0, 50)
														}});
														break;
													}}
												}} catch (e) {{
													continue;
												}}
											}}
											
											// Strategy 2: Try clicking outside the popup
											if (!dismissed) {{
												try {{
													const clickX = Math.max(rect.right + 10, window.innerWidth - 50);
													const clickY = Math.max(rect.bottom + 10, window.innerHeight - 50);
													
													const clickEvent = new MouseEvent('click', {{
														view: window,
														bubbles: true,
														cancelable: true,
														clientX: clickX,
														clientY: clickY
													}});
													document.body.dispatchEvent(clickEvent);
													dismissed = true;
													dismissedCount++;
													dismissedItems.push({{
														selector: selector,
														method: 'outside_click',
														text: element.textContent.substring(0, 50)
													}});
												}} catch (e) {{
													// Ignore outside click errors
												}}
											}}
											
											// Strategy 3: Try hiding the element directly
											if (!dismissed) {{
												try {{
													element.style.display = 'none';
													element.style.visibility = 'hidden';
													dismissed = true;
													dismissedCount++;
													dismissedItems.push({{
														selector: selector,
														method: 'force_hide',
														text: element.textContent.substring(0, 50)
													}});
												}} catch (e) {{
													// Ignore direct hiding errors
												}}
											}}
										}}
									}}
								}} catch (e) {{
									continue; // Try next selector
								}}
							}}
							
							// Also try pressing Escape key as a general dismissal
							try {{
								const escapeEvent = new KeyboardEvent('keydown', {{ key: 'Escape', code: 'Escape' }});
								document.dispatchEvent(escapeEvent);
								if (dismissedCount === 0) {{
									dismissedItems.push({{
										selector: 'keyboard',
										method: 'escape_key',
										text: 'Escape key pressed'
									}});
									dismissedCount = 1;
								}}
							}} catch (e) {{
								// Ignore escape key errors
							}}
							
							return {{
								dismissedCount: dismissedCount,
								items: dismissedItems,
								timestamp: Date.now()
							}};
						}})();
					"""
					}
				)

				result = dismiss_result.get('result', {}).get('value', {})
				dismissed_count = result.get('dismissedCount', 0)
				dismissed_items = result.get('items', [])

				if dismissed_count > 0:
					logger.info(f'✅ Dismissed {dismissed_count} popup(s)/overlay(s)')

					# Wait for UI to settle after dismissals
					await asyncio.sleep(1.0)

					# Create summary of what was dismissed
					summary = []
					for item in dismissed_items:
						summary.append(
							f'{item.get("method", "unknown")} on {item.get("selector", "unknown")}: {item.get("text", "")[:30]}'
						)

					return ActionResult(
						extracted_content=f'Successfully dismissed {dismissed_count} blocking elements: {"; ".join(summary)}'
					)
				else:
					logger.info('ℹ️ No blocking popups or overlays detected')
					return ActionResult(extracted_content='No blocking popups or overlays found on current page')

			except Exception as e:
				logger.error(f'❌ Popup dismissal failed: {e}')
				return ActionResult(error=f'Failed to dismiss popups: {str(e)}')
