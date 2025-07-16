# 100% vibe coded
import asyncio

from browser_use.dom.service import DomService
from browser_use.dom.views import DOMSelectorMap
from browser_use.observability import observe_debug
from browser_use.utils import time_execution_async


def analyze_element_interactivity(element: dict) -> dict:
	"""Analyze why an element is considered interactive and assign confidence level."""
	element_type = element['element_name'].lower()
	attributes = element.get('attributes', {})

	# Default reasoning structure
	reasoning = {'confidence': 'LOW', 'primary_reason': 'unknown', 'element_type': element_type, 'reasons': []}

	# High confidence elements
	if element_type in ['button', 'a', 'input', 'select', 'textarea']:
		reasoning['confidence'] = 'HIGH'
		reasoning['primary_reason'] = 'semantic_element'
		reasoning['reasons'].append(f'Semantic interactive element: {element_type}')

	# Check for interactive attributes
	interactive_attrs = ['onclick', 'onchange', 'href', 'type', 'role']
	found_attrs = [attr for attr in interactive_attrs if attr in attributes]
	if found_attrs:
		if reasoning['confidence'] != 'HIGH':
			reasoning['confidence'] = 'HIGH' if element_type in ['button', 'a'] else 'MEDIUM'
		reasoning['primary_reason'] = 'interactive_attributes'
		reasoning['reasons'].append(f'Interactive attributes: {", ".join(found_attrs)}')

	# Check for ARIA roles
	role = attributes.get('role', '').lower()
	if role in ['button', 'link', 'checkbox', 'radio', 'menuitem', 'tab']:
		reasoning['confidence'] = 'HIGH'
		reasoning['primary_reason'] = 'aria_role'
		reasoning['reasons'].append(f'Interactive ARIA role: {role}')

	# Check if marked as clickable from snapshot
	if element.get('is_clickable'):
		if reasoning['confidence'] == 'LOW':
			reasoning['confidence'] = 'MEDIUM'
		reasoning['reasons'].append('Marked as clickable in DOM snapshot')

	# Check for valid bounding box
	if element.get('width', 0) > 0 and element.get('height', 0) > 0:
		reasoning['reasons'].append(f'Valid bounding box: {element["width"]}x{element["height"]}')
	else:
		reasoning['confidence'] = 'LOW'
		reasoning['reasons'].append('Invalid or missing bounding box')

	# Fallback reasoning
	if not reasoning['reasons']:
		reasoning['reasons'].append('Element found in selector map')
		reasoning['primary_reason'] = 'selector_mapped'

	return reasoning


def convert_dom_selector_map_to_highlight_format(selector_map: DOMSelectorMap) -> list[dict]:
	"""Convert DOMSelectorMap to the format expected by the highlighting script."""
	elements = []

	for interactive_index, node in selector_map.items():
		# Get bounding box from snapshot_node if available (adapted from working implementation)
		bbox = None
		if node.snapshot_node:
			# Try bounds first, then clientRects
			rect = node.snapshot_node.bounds
			if rect:
				bbox = {'x': rect.x, 'y': rect.y, 'width': rect.width, 'height': rect.height}

		# Only include elements with valid bounding boxes (following working implementation)
		if bbox and bbox.get('width', 0) > 0 and bbox.get('height', 0) > 0:
			element = {
				'x': bbox['x'],
				'y': bbox['y'],
				'width': bbox['width'],
				'height': bbox['height'],
				'interactive_index': interactive_index,
				'element_name': node.node_name,
				'is_clickable': node.snapshot_node.is_clickable if node.snapshot_node else True,
				'is_scrollable': getattr(node, 'is_scrollable', False),
				'attributes': node.attributes or {},
				'frame_id': getattr(node, 'frame_id', None),
				'node_id': node.node_id,
				'backend_node_id': node.backend_node_id,
				'xpath': node.xpath,
				'text_content': node.get_all_children_text()[:50]
				if hasattr(node, 'get_all_children_text')
				else node.node_value[:50],
			}

			# Analyze why this element is interactive
			reasoning = analyze_element_interactivity(element)
			element['reasoning'] = reasoning

			elements.append(element)
		else:
			# Skip elements without valid bounding boxes for now
			# Could add fallback positioning here if needed
			pass

	return elements


@time_execution_async('-- remove_highlighting_script')
@observe_debug(name='remove_highlighting_script', ignore_input=True, ignore_output=True)
async def remove_highlighting_script(dom_service: DomService) -> None:
	"""Remove all browser-use highlighting elements from the page."""
	await _remove_highlighting_script_impl(dom_service)


async def _remove_highlighting_script_impl(dom_service: DomService) -> None:
	"""Implementation of highlight removal with proper error handling."""
	try:
		# Get CDP client and session ID with timeout protection
		cdp_client = await asyncio.wait_for(dom_service.browser.get_cdp_client(), timeout=2.0)
		session_id = await asyncio.wait_for(dom_service.browser.get_current_page_cdp_session_id(), timeout=3.0)

		print('🧹 Removing browser-use highlighting elements')

		# Create script to remove all highlights
		script = """
		(function() {
			// Remove any existing highlights
			const existingHighlights = document.querySelectorAll('[data-browser-use-highlight]');
			console.log('Removing', existingHighlights.length, 'browser-use highlight elements');
			existingHighlights.forEach(el => el.remove());
		})();
		"""

		# Execute script with aggressive timeout
		await asyncio.wait_for(
			cdp_client.send.Runtime.evaluate(params={'expression': script, 'returnByValue': True}, session_id=session_id),
			timeout=1.0,
		)

		print('✅ All browser-use highlighting elements removed')

	except asyncio.TimeoutError:
		print('⚠️ Highlight removal timed out, but continuing...')
	except Exception as e:
		print(f'❌ Error removing highlighting elements: {e}')
		# Don't raise - highlighting removal is not critical for functionality


@time_execution_async('-- inject_highlighting_script')
@observe_debug(name='inject_highlighting_script', ignore_input=True, ignore_output=True)
async def inject_highlighting_script(dom_service: DomService, selector_map: 'DOMSelectorMap') -> None:
	"""Inject highlighting script into the page."""
	await _inject_highlighting_script_impl(dom_service, selector_map)


async def _inject_highlighting_script_impl(dom_service: DomService, selector_map: 'DOMSelectorMap') -> None:
	"""Implementation of highlight injection with proper error handling."""
	try:
		if not selector_map:
			print('⚠️ No interactive elements to highlight')
			return

		# Get CDP client and session ID with timeout protection
		cdp_client = await asyncio.wait_for(dom_service.browser.get_cdp_client(), timeout=2.0)
		session_id = await asyncio.wait_for(dom_service.browser.get_current_page_cdp_session_id(), timeout=3.0)

		# First remove any existing highlights
		await _remove_highlighting_script_impl(dom_service)

		print(f'📍 Creating CSP-safe highlighting for {len(selector_map)} elements')

		# Create highlighting script (simplified for speed)
		script = """
		(function() {
			// Simple highlighting without complex features
			const highlights = arguments[0];
			highlights.forEach(item => {
				try {
					const element = document.querySelector(item.selector);
					if (element) {
						element.setAttribute('data-browser-use-highlight', item.index);
						element.style.outline = '2px solid red';
					}
				} catch (e) {
					console.debug('Failed to highlight element:', item.selector, e);
				}
			});
		})
		"""

		# Prepare highlighting data (simplified)
		highlight_data = []
		for index, element in list(selector_map.items())[:50]:  # Limit to first 50 elements
			try:
				css_selector = f'[data-browser-use-highlight="{index}"]'
				highlight_data.append({'index': index, 'selector': css_selector})
			except Exception:
				continue

		# Execute script with aggressive timeout
		await asyncio.wait_for(
			cdp_client.send.Runtime.evaluate(
				params={'expression': script, 'arguments': [{'type': 'object', 'value': highlight_data}], 'returnByValue': True},
				session_id=session_id,
			),
			timeout=1.5,
		)

		print(f'✅ Enhanced CSP-safe highlighting injected for {len(highlight_data)} elements')

	except asyncio.TimeoutError:
		print('⚠️ Highlight injection timed out, but continuing...')
	except Exception as e:
		print(f'❌ Error injecting highlighting: {e}')
		# Don't raise - highlighting injection is not critical for functionality
