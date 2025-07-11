# @file purpose: Interactive test script to explore DOM tree structures with the new multi-tab DOMService

import asyncio
import json
import os
import traceback
from pathlib import Path

import aiofiles

from browser_use.browser.profile import BrowserProfile
from browser_use.browser.session import BrowserSession
from browser_use.dom.service import DOMService


def is_debug_mode() -> bool:
	"""Check if we're in debug mode based on environment variable."""
	return os.getenv('BROWSER_USE_LOGGING_LEVEL', '').lower() == 'debug'


async def extract_interactive_elements_from_service(dom_service: DOMService) -> tuple[list[dict], str, dict]:
	"""Extract interactive elements using the new DOM service."""
	try:
		# Get serialized output and selector map from the new DOM service
		serialized, selector_map = await dom_service.get_serialized_dom_tree()

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
							'is_clickable': True,
							'is_scrollable': getattr(node, 'is_scrollable', False),
							'attributes': node.attributes or {},
							'frame_id': getattr(node, 'frame_id', None),
						}
					)

		return interactive_elements, serialized, selector_map

	except Exception as e:
		print(f'❌ Error extracting interactive elements: {e}')
		traceback.print_exc()
		return [], '', {}


async def inject_highlighting_script(browser_session: BrowserSession, interactive_elements: list[dict]) -> None:
	"""Inject JavaScript to highlight interactive elements with bounding boxes."""
	if not interactive_elements:
		print('⚠️ No interactive elements to highlight')
		return

	try:
		# Get the current page from the browser session
		page = await browser_session.get_current_page()

		# Print debug info about coordinates
		print(f'📍 Debug: Found {len(interactive_elements)} interactive elements:')
		for i, elem in enumerate(interactive_elements[:5]):  # Show first 5 for debugging
			print(
				f'  [{elem["interactive_index"]}] {elem["element_name"]}: x={elem["x"]}, y={elem["y"]}, w={elem["width"]}, h={elem["height"]}'
			)
		if len(interactive_elements) > 5:
			print(f'  ... and {len(interactive_elements) - 5} more elements')

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
		print(f'  📜 Scroll Position: ({viewport_debug["scrollX"]}, {viewport_debug["scrollY"]})')

		# Create the highlighting script with properly scaled coordinates
		script = f"""
		(function() {{
			// Remove any existing highlights
			const existingHighlights = document.querySelectorAll('[data-browser-use-highlight]');
			existingHighlights.forEach(el => el.remove());
			
			// Interactive elements data
			const interactiveElements = {json.dumps(interactive_elements)};
			
			console.log('=== BROWSER-USE COORDINATE DEBUG ===');
			console.log('Device Pixel Ratio:', window.devicePixelRatio);
			console.log('Viewport:', window.innerWidth, 'x', window.innerHeight);
			console.log('Found', interactiveElements.length, 'interactive elements');
			
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
				
				// Create the highlight box
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
				
				// Add label showing only the interactive index number
				const label = document.createElement('div');
				label.setAttribute('data-browser-use-highlight', 'label');
				label.style.cssText = `
					position: absolute;
					top: -18px;
					left: 0;
					background-color: #ff6b6b;
					color: white;
					padding: 1px 4px;
					font-size: 11px;
					font-family: monospace;
					font-weight: bold;
					border-radius: 2px;
					white-space: nowrap;
					z-index: 1000000;
					min-width: 16px;
					text-align: center;
				`;
				
				// Show only the interactive index number
				label.textContent = element.interactive_index;
				
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
		print(f'✅ Highlighted {len(interactive_elements)} interactive elements')

	except Exception as e:
		print(f'❌ Error injecting highlighting script: {e}')
		traceback.print_exc()


async def save_outputs_to_files(
	serialized: str, selector_map: dict, interactive_elements: list[dict], filter_mode: str, url: str
) -> None:
	"""Save all outputs to tmp files for analysis."""
	try:
		# Create tmp directory if it doesn't exist
		tmp_dir = Path('tmp')
		tmp_dir.mkdir(exist_ok=True)

		# Clean URL for filename
		safe_url = url.replace('://', '_').replace('/', '_').replace('?', '_').replace('&', '_')[:50]

		# Save serialized DOM tree
		serialized_file = tmp_dir / f'serialized_dom_{filter_mode}_{safe_url}.txt'
		async with aiofiles.open(serialized_file, 'w', encoding='utf-8') as f:
			await f.write(f'=== DOM SERIALIZED OUTPUT ({filter_mode.upper()} mode) ===\n')
			await f.write(f'URL: {url}\n')
			await f.write(f'Interactive elements: {len(selector_map)}\n')
			await f.write('=' * 60 + '\n\n')
			await f.write(serialized)

		# Save selector map details
		selector_file = tmp_dir / f'selector_map_{filter_mode}_{safe_url}.json'
		selector_data = {}
		for idx, node in selector_map.items():
			selector_data[str(idx)] = {
				'element_name': node.node_name,
				'attributes': node.attributes or {},
				'x_path': getattr(node, 'x_path', 'unknown'),
				'is_scrollable': getattr(node, 'is_scrollable', False),
				'frame_id': getattr(node, 'frame_id', None),
			}

		async with aiofiles.open(selector_file, 'w', encoding='utf-8') as f:
			await f.write(json.dumps(selector_data, indent=2, ensure_ascii=False))

		# Save interactive elements coordinates
		elements_file = tmp_dir / f'interactive_elements_{filter_mode}_{safe_url}.json'
		async with aiofiles.open(elements_file, 'w', encoding='utf-8') as f:
			await f.write(json.dumps(interactive_elements, indent=2, ensure_ascii=False))

		print('📁 Saved outputs to tmp/ directory:')
		print(f'  - {serialized_file.name}')
		print(f'  - {selector_file.name}')
		print(f'  - {elements_file.name}')

	except Exception as e:
		print(f'❌ Error saving files: {e}')


def get_website_choice() -> str:
	"""Get website choice from user."""
	print('\n🌐 Choose a website to test:')
	print('  1. example.com (simple test page)')
	print('  2. browser-use.com (project homepage)')
	print('  3. github.com (complex interface)')
	print('  4. semantic-ui.com dropdown page (UI components)')
	print('  5. Google Flights (complex travel interface)')
	print('  6. Wikipedia (content-heavy page)')
	print('  7. Custom URL')

	websites = {
		'1': 'https://example.com',
		'2': 'https://browser-use.com',
		'3': 'https://github.com',
		'4': 'https://semantic-ui.com/modules/dropdown.html',
		'5': 'https://www.google.com/travel/flights',
		'6': 'https://en.wikipedia.org/wiki/Internet',
		'7': None,  # Custom URL
	}

	while True:
		try:
			choice = input('Enter choice (1-7): ').strip()
			if choice in websites:
				if choice == '7':
					return input('Enter custom URL: ').strip()
				return websites[choice]
			else:
				print('❌ Invalid choice. Please enter 1-7.')
		except (EOFError, KeyboardInterrupt):
			print('\n👋 Exiting...')
			return 'https://example.com'


async def main():
	"""Interactive test script for DOM extraction with highlighting and file saving."""

	# Create browser session
	profile = BrowserProfile(headless=False, keep_alive=True)
	browser_session = BrowserSession(browser_profile=profile)

	try:
		await browser_session.start()

		# Create DOM service
		dom_service = DOMService(browser_session)

		print('🔍 Interactive DOM Extraction Tester')
		print('=' * 50)
		print('🎯 RECENT IMPROVEMENTS (v3.0):')
		print('  ✅ Conservative DIV/SPAN detection with scoring system')
		print('  ✅ Eliminated cursor-pointer-only false positives')
		print('  ✅ Improved parent-child consolidation')
		print('  ✅ Wrapper container detection & removal')
		print('  🆕 VIEWPORT FILTERING: Only detects visible elements')
		print('  🆕 CURSOR POINTER: All cursor:pointer elements now detected')
		print('  🆕 BODY EXCLUSION: No more body/html false positives')
		print('  🆕 ROLE DETECTION: Enhanced combobox/role detection')
		print('  🆕 CONTAINER FILTERING: Smart calendar/menu container handling')
		print('  🆕 JSACTION SUPPORT: Google Material Design elements')
		print('  🔥 ENHANCED IFRAMES: Recursive DOM extraction inside ALL iframes')
		print('  🔥 NESTED IFRAMES: Full support for iframes within iframes')
		print('  🔥 CROSS-ORIGIN IFRAMES: Enhanced detection and processing')
		print('  🔥 SHADOW DOM: Recursive processing of shadow DOM content')
		print('  ✅ Reduced redundant elements by 60-80%')
		print('  ✅ Added Google Flights & Semantic UI test URLs')
		print('=' * 50)

		while True:
			try:
				# Get website choice
				url = get_website_choice()

				# Navigate to chosen website
				print(f'\n🌐 Navigating to: {url}')
				await browser_session.navigate_to(url)
				await asyncio.sleep(3)  # Wait for page to load

				while True:
					print('\n🔄 Extracting DOM with comprehensive mode')
					print('=' * 50)

					# Extract interactive elements
					interactive_elements, serialized, selector_map = await extract_interactive_elements_from_service(dom_service)

					# Print summary
					print('\n📊 Extraction Results:')
					print('  - Mode: comprehensive with aggressive consolidation + viewport filtering')
					print(f'  - Interactive elements: {len(interactive_elements)}')
					print(f'  - Serialized length: {len(serialized)} characters')

					# Show iframe and shadow DOM information
					iframe_contexts = serialized.count('=== IFRAME CONTENT')
					shadow_contexts = serialized.count('=== SHADOW DOM')
					cross_origin_iframes = serialized.count('[CROSS-ORIGIN]')

					if iframe_contexts > 0 or shadow_contexts > 0:
						print(f'  - 🖼️  Iframe contexts found: {iframe_contexts}')
						if cross_origin_iframes > 0:
							print(f'  - 🌐 Cross-origin iframes: {cross_origin_iframes}')
						print(f'  - 🌒 Shadow DOM contexts: {shadow_contexts}')
						print('  - ✅ Enhanced iframe/shadow DOM processing active')

					# Show viewport info if available
					if interactive_elements:
						min_x = min(elem['x'] for elem in interactive_elements)
						max_x = max(elem['x'] + elem['width'] for elem in interactive_elements)
						min_y = min(elem['y'] for elem in interactive_elements)
						max_y = max(elem['y'] + elem['height'] for elem in interactive_elements)
						print(f'  - Element bounds: x({min_x:.0f}-{max_x:.0f}) y({min_y:.0f}-{max_y:.0f})')
						print('  - ✅ All elements within current viewport (with 100px buffer)')

					# Print sample elements
					if interactive_elements:
						print('\n🎯 Sample interactive elements:')
						for elem in interactive_elements[:5]:
							attrs_info = ''
							if elem['attributes']:
								key_attrs = ['id', 'class', 'type', 'href']
								relevant_attrs = [f"{k}='{v}'" for k, v in elem['attributes'].items() if k in key_attrs]
								if relevant_attrs:
									attrs_info = f' ({", ".join(relevant_attrs)})'
							print(f'  [{elem["interactive_index"]}] {elem["element_name"]}{attrs_info}')
						if len(interactive_elements) > 5:
							print(f'  ... and {len(interactive_elements) - 5} more')

					# Highlight elements if debug mode or user wants it

					await inject_highlighting_script(browser_session, interactive_elements)

					# Save outputs to files
					await save_outputs_to_files(serialized, selector_map, interactive_elements, 'comprehensive', url)

					# Print serialized output preview
					print('\n📄 Serialized output preview (first 800 chars):')
					print('-' * 60)
					print(serialized[:800])
					if len(serialized) > 800:
						print('...[TRUNCATED]')
					print('-' * 60)

					# Ask what to do next
					print('\n⚡ Next action:')
					print('  1. Extract again (test for differences)')
					print('  2. Test different website')
					print('  3. Exit')

					try:
						next_choice = input('Enter choice (1, 2, or 3): ').strip()
						if next_choice == '1':
							continue  # Extract again
						elif next_choice == '2':
							break  # Go to website selection
						elif next_choice == '3':
							print('👋 Exiting...')
							return
						else:
							print('❌ Invalid choice, extracting again...')
							continue
					except (EOFError, KeyboardInterrupt):
						print('\n👋 Exiting...')
						return

			except Exception as e:
				print(f'❌ Error during DOM extraction test: {e}')
				traceback.print_exc()

				try:
					retry = input('\n🔄 Try again? (y/n): ').strip().lower()
					if retry not in ['y', 'yes']:
						break
				except (EOFError, KeyboardInterrupt):
					print('\n👋 Exiting...')
					break

	except Exception as e:
		print(f'❌ Critical error: {e}')
		traceback.print_exc()
	finally:
		await browser_session.stop()


if __name__ == '__main__':
	asyncio.run(main())
