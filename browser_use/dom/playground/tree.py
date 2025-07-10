import asyncio
import json
import os

import aiofiles
import httpx
from playwright.async_api import async_playwright

from browser_use.browser import Browser
from browser_use.dom.serializer import DOMTreeSerializer
from browser_use.dom.service import DOMService


def is_debug_mode() -> bool:
	"""Check if we're in debug mode based on environment variable."""
	return os.getenv('BROWSER_USE_LOGGING_LEVEL', '').lower() == 'debug'


def extract_interactive_elements(root_node) -> list[dict]:
	"""Extract elements that will get interactive indices from the serializer."""
	if not root_node:
		return []

	# Use the actual serializer to determine which elements get interactive indices
	serializer = DOMTreeSerializer(root_node)
	_, selector_map = serializer.serialize_accessible_elements()

	interactive_elements = []

	# Extract bounding boxes for elements that have interactive indices
	for interactive_index, node in selector_map.items():
		if node.snapshot_node and node.snapshot_node.bounding_box:
			bbox = node.snapshot_node.bounding_box

			# Only include elements with valid bounding boxes
			if bbox.get('width', 0) > 0 and bbox.get('height', 0) > 0:
				interactive_elements.append(
					{
						'x': bbox['x'],
						'y': bbox['y'],
						'width': bbox['width'],
						'height': bbox['height'],
						'interactive_index': interactive_index,
						'element_name': node.node_name,
						'is_clickable': True,  # All elements with interactive indices are clickable
						'is_scrollable': node.is_scrollable,
						'attributes': node.attributes or {},
					}
				)

	return interactive_elements


async def inject_highlighting_script(browser: Browser, interactive_elements: list[dict]) -> None:
	"""Inject JavaScript to highlight interactive elements with bounding boxes."""
	if not interactive_elements:
		return

	# Get the current page from the browser session
	page = await browser.get_current_page()

	# Print debug info about coordinates
	if interactive_elements:
		print(f'📍 Debug: Found {len(interactive_elements)} interactive elements:')
		for elem in interactive_elements[:3]:  # Show first 3 for debugging
			print(
				f'  [{elem["interactive_index"]}] {elem["element_name"]}: x={elem["x"]}, y={elem["y"]}, w={elem["width"]}, h={elem["height"]}'
			)

	# Get basic viewport info for debugging
	viewport_debug = await page.evaluate("""
	() => {
		return {
			js_innerWidth: window.innerWidth,
			js_innerHeight: window.innerHeight,
			devicePixelRatio: window.devicePixelRatio,
			scrollX: window.pageXOffset || document.documentElement.scrollLeft || 0,
			scrollY: window.pageYOffset || document.documentElement.scrollTop || 0
		};
	}
	""")

	print('🖥️  **VIEWPORT DEBUG INFO**:')
	print(f'  JS Viewport: {viewport_debug["js_innerWidth"]}x{viewport_debug["js_innerHeight"]}')
	print(f'  Device Pixel Ratio: {viewport_debug["devicePixelRatio"]}')
	print(f'  Scroll Position: {viewport_debug["scrollX"]}, {viewport_debug["scrollY"]}')

	# Create the highlighting script with properly scaled coordinates
	script = f"""
	(function() {{
		// Remove any existing highlights
		const existingHighlights = document.querySelectorAll('[data-browser-use-highlight]');
		existingHighlights.forEach(el => el.remove());
		
		// Interactive elements data (coordinates should now be in CSS pixels)
		const interactiveElements = {json.dumps(interactive_elements)};
		
		console.log('=== COORDINATE DEBUG ===');
		console.log('Device Pixel Ratio:', window.devicePixelRatio);
		console.log('Viewport:', window.innerWidth, 'x', window.innerHeight);
		
		// Create container for all highlights
		const container = document.createElement('div');
		container.id = 'browser-use-debug-highlights';
		container.setAttribute('data-browser-use-highlight', 'container');
		container.style.cssText = `
			position: absolute;
			top: 0;
			left: 0;
			width: 100%;
			height: 100%;
			pointer-events: none;
			z-index: 999999;
		`;
		
		// Add highlights for each interactive element
		interactiveElements.forEach((element, index) => {{
			console.log(`Element [${{element.interactive_index}}] ${{element.element_name}}: x=${{element.x}}, y=${{element.y}}, w=${{element.width}}, h=${{element.height}}`);
			
			// Create the highlight box using coordinates as-is (should now be in CSS pixels)
			const highlight = document.createElement('div');
			highlight.setAttribute('data-browser-use-highlight', 'box');
			highlight.style.cssText = `
				position: absolute;
				left: ${{element.x}}px;
				top: ${{element.y}}px;
				width: ${{element.width}}px;
				height: ${{element.height}}px;
				border: 2px solid #ff6b6b;
				background-color: rgba(255, 107, 107, 0.1);
				pointer-events: none;
				box-sizing: border-box;
			`;
			
			// Add label showing interactive index
			const label = document.createElement('div');
			label.setAttribute('data-browser-use-highlight', 'label');
			label.style.cssText = `
				position: absolute;
				top: -22px;
				left: 0;
				background-color: #ff6b6b;
				color: white;
				padding: 2px 6px;
				font-size: 12px;
				font-family: monospace;
				font-weight: bold;
				border-radius: 3px;
				white-space: nowrap;
				z-index: 1000000;
			`;
			
			// Show interactive index and element info
			const scrollSuffix = element.is_scrollable ? '+SCROLL' : '';
			label.textContent = `[${{element.interactive_index}}] ${{element.element_name}}${{scrollSuffix}}`;
			
			highlight.appendChild(label);
			container.appendChild(highlight);
		}});
		
		// Add container to document body
		document.body.appendChild(container);
		
		console.log(`Browser-use debug: Highlighted ${{interactiveElements.length}} interactive elements`);
	}})();
	"""

	# Inject the script
	await page.evaluate(script)


async def highlight_interactive_elements_if_debug(browser: Browser, root_node) -> None:
	"""Highlight interactive elements only if in debug mode."""
	if not is_debug_mode():
		return

	try:
		# Extract elements that will get interactive indices
		interactive_elements = extract_interactive_elements(root_node)

		if interactive_elements:
			print(f'Debug mode: Highlighting {len(interactive_elements)} interactive elements')
			await inject_highlighting_script(browser, interactive_elements)
		else:
			print('Debug mode: No interactive elements found to highlight')

	except Exception as e:
		print(f'Debug highlighting failed: {e}')
		# Don't raise - highlighting is optional


async def main():
	"""Main function to test the enhanced DOM tree processing."""
	async with async_playwright() as p:
		playwright_browser = await p.chromium.launch(args=['--remote-debugging-port=9222'], headless=False)

		# Create Browser session with proper CDP setup
		browser = Browser(browser=playwright_browser)

		# Set up CDP URL
		async with httpx.AsyncClient() as client:
			version_info = await client.get('http://localhost:9222/json/version')
			browser.cdp_url = version_info.json()['webSocketDebuggerUrl']

		# Create a new tab and navigate
		page = 'wikipedia.org'

		await browser.create_new_tab(f'https://{page}')

		await browser._wait_for_page_and_frames_load()

		# Get DOM service
		dom_service = DOMService(browser)
		dom_tree = await dom_service.get_dom_tree()

		async with aiofiles.open('tmp/enhanced_dom_tree.json', 'w') as f:
			await f.write(json.dumps(dom_tree.__json__(), indent=1))

		# Get enhanced DOM tree
		while True:
			enhanced_tree = await dom_service.get_dom_tree()

			# Test highlighting in debug mode
			await highlight_interactive_elements_if_debug(browser, enhanced_tree)

			# Save the enhanced tree for inspection
			async with aiofiles.open('tmp/enhanced_dom_tree.json', 'w') as f:
				await f.write(json.dumps(enhanced_tree.__json__(), indent=2))

			print('Enhanced DOM tree saved to tmp/enhanced_dom_tree.json')
			input('Press Enter to continue...')

			serialized, selector_map = DOMTreeSerializer(enhanced_tree).serialize_accessible_elements()
			serialized, selector_map = DOMTreeSerializer(dom_tree).serialize_accessible_elements()
			async with aiofiles.open('tmp/serialized_dom_tree.txt', 'w') as f:
				await f.write(serialized)

		# print(serialized)

		await browser.stop()


if __name__ == '__main__':
	asyncio.run(main())
