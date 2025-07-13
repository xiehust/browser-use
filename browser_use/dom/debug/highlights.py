# 100% vibe coded

import json
import traceback

from browser_use.dom.service import DomService
from browser_use.dom.views import DOMSelectorMap


def analyze_element_interactivity(element: dict) -> dict:
	"""Analyze why an element is considered interactive and assign confidence level."""
	element_type = element['element_name'].lower()
	attributes = element.get('attributes', {})
	is_iframe_content = element.get('is_iframe_content', False)

	# Default reasoning structure
	reasoning = {'confidence': 'LOW', 'primary_reason': 'unknown', 'element_type': element_type, 'reasons': []}

	# Special handling for iframe content
	if is_iframe_content:
		reasoning['confidence'] = 'MEDIUM'
		reasoning['primary_reason'] = 'iframe_content'
		reasoning['reasons'].append('Element found inside iframe content')

	# High confidence elements
	if element_type in ['button', 'a', 'input', 'select', 'textarea']:
		confidence_level = 'MEDIUM' if is_iframe_content else 'HIGH'
		reasoning['confidence'] = confidence_level
		reasoning['primary_reason'] = 'semantic_element'
		reasoning['reasons'].append(f'Semantic interactive element: {element_type}')

	# Check for interactive attributes
	interactive_attrs = ['onclick', 'onchange', 'href', 'type', 'role']
	found_attrs = [attr for attr in interactive_attrs if attr in attributes]
	if found_attrs:
		if reasoning['confidence'] != 'HIGH':
			base_confidence = 'HIGH' if element_type in ['button', 'a'] else 'MEDIUM'
			reasoning['confidence'] = 'MEDIUM' if is_iframe_content else base_confidence
		reasoning['primary_reason'] = 'interactive_attributes'
		reasoning['reasons'].append(f'Interactive attributes: {", ".join(found_attrs)}')

	# Check for ARIA roles
	role = attributes.get('role', '').lower()
	if role in ['button', 'link', 'checkbox', 'radio', 'menuitem', 'tab']:
		reasoning['confidence'] = 'MEDIUM' if is_iframe_content else 'HIGH'
		reasoning['primary_reason'] = 'aria_role'
		reasoning['reasons'].append(f'Interactive ARIA role: {role}')

	# Check if marked as clickable from snapshot
	if element.get('is_clickable'):
		if reasoning['confidence'] == 'LOW':
			reasoning['confidence'] = 'MEDIUM'
		reasoning['reasons'].append('Marked as clickable in DOM snapshot')

	# Check for valid bounding box
	if element.get('width', 0) > 0 and element.get('height', 0) > 0:
		if is_iframe_content:
			reasoning['reasons'].append(f'Fallback positioning for iframe content: {element["width"]}x{element["height"]}')
		else:
			reasoning['reasons'].append(f'Valid bounding box: {element["width"]}x{element["height"]}')
	else:
		reasoning['confidence'] = 'LOW'
		reasoning['reasons'].append('Invalid or missing bounding box')

	# Fallback reasoning
	if not reasoning['reasons']:
		reasoning['reasons'].append('Element found in selector map')
		reasoning['primary_reason'] = 'selector_mapped'

	return reasoning


def _find_iframe_overlay_position(interactive_index: int, total_iframe_elements: int) -> dict:
	"""Calculate overlay position for iframe content elements to make them more visible."""
	# Position iframe elements in a more prominent overlay area
	# Use the center-right area of the viewport for better visibility

	# Calculate grid layout for iframe elements
	elements_per_row = 5  # Max 5 elements per row
	element_width = 180
	element_height = 25
	spacing_x = 10
	spacing_y = 5

	# Start position - center-right area of typical viewport
	start_x = 600  # Right side but not too far
	start_y = 100  # Top area but below navigation

	row = (interactive_index - 1) // elements_per_row
	col = (interactive_index - 1) % elements_per_row

	return {
		'x': start_x + col * (element_width + spacing_x),
		'y': start_y + row * (element_height + spacing_y),
		'width': element_width,
		'height': element_height,
	}


def convert_dom_selector_map_to_highlight_format(selector_map: DOMSelectorMap) -> list[dict]:
	"""Convert DOMSelectorMap to the format expected by the highlighting script."""
	elements = []

	# Count iframe content elements for better positioning
	iframe_elements = []
	for interactive_index, node in selector_map.items():
		if not node.snapshot_node or not node.snapshot_node.bounds:
			iframe_elements.append(interactive_index)

	iframe_counter = 0
	for interactive_index, node in selector_map.items():
		# Get bounding box from snapshot_node if available (adapted from working implementation)
		bbox = None
		is_iframe_content = False

		if node.snapshot_node:
			# Try bounds first, then clientRects
			rect = node.snapshot_node.bounds
			if rect:
				bbox = {'x': rect.x, 'y': rect.y, 'width': rect.width, 'height': rect.height}

		# Check if this is iframe content - reliable indicators:
		# 1. No snapshot_node (iframe content lacks snapshot data)
		# 2. No bounds even with snapshot_node (cross-origin iframe content)
		if not bbox:
			is_iframe_content = True
			iframe_counter += 1
			# Use prominent overlay positioning for iframe content
			# This ensures iframe elements are highly visible and organized
			bbox = _find_iframe_overlay_position(iframe_counter, len(iframe_elements))

		# Include all elements (both regular and iframe content)
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
			'text_content': node.get_all_children_text()[:50] if hasattr(node, 'get_all_children_text') else node.node_value[:50],
			'is_iframe_content': is_iframe_content,
		}

		# Analyze why this element is interactive
		reasoning = analyze_element_interactivity(element)
		element['reasoning'] = reasoning

		elements.append(element)

	return elements


async def remove_highlighting_script(dom_service: DomService) -> None:
	"""Remove all browser-use highlighting elements from the page."""
	try:
		# Get CDP client and session ID
		cdp_client = await dom_service._get_cdp_client()
		session_id = await dom_service._get_current_page_session_id()

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

		# Execute the removal script via CDP
		await cdp_client.send.Runtime.evaluate(params={'expression': script, 'returnByValue': True}, session_id=session_id)
		print('✅ All browser-use highlighting elements removed')

	except Exception as e:
		print(f'❌ Error removing highlighting elements: {e}')
		traceback.print_exc()


async def inject_highlighting_script(dom_service: DomService, interactive_elements: DOMSelectorMap) -> None:
	"""Inject JavaScript to highlight interactive elements with real coordinate resolution for iframe content."""
	if not interactive_elements:
		print('⚠️ No interactive elements to highlight')
		return

	try:
		# Performance safeguards - prevent browser crashes with too many elements
		MAX_HIGHLIGHTS = 200  # Reasonable limit to prevent timeouts
		total_elements = len(interactive_elements)

		if total_elements > MAX_HIGHLIGHTS:
			print(f'⚠️ Too many elements ({total_elements}) - limiting to first {MAX_HIGHLIGHTS} for performance')
			# Take first N elements (prioritizing earlier elements which are usually more important)
			limited_elements = dict(list(interactive_elements.items())[:MAX_HIGHLIGHTS])
		else:
			limited_elements = interactive_elements

		# Get CDP client and session ID
		cdp_client = await dom_service._get_cdp_client()
		session_id = await dom_service._get_current_page_session_id()

		print(f'📍 Creating robust highlighting for {len(limited_elements)} elements (total found: {total_elements})')

		# Remove any existing highlights first
		await remove_highlighting_script(dom_service)

		# Prepare element data for JavaScript resolution
		elements_data = []
		for interactive_index, node in limited_elements.items():
			element_info = {
				'interactive_index': interactive_index,
				'backend_node_id': node.backend_node_id,
				'node_id': node.node_id,
				'element_name': node.node_name,
				'xpath': node.xpath,
				'attributes': node.attributes or {},
				'is_iframe_content': not (node.snapshot_node and node.snapshot_node.bounds),
				'text_content': node.get_all_children_text()[:50]
				if hasattr(node, 'get_all_children_text')
				else node.node_value[:50],
			}
			elements_data.append(element_info)

		# Create comprehensive highlighting script with real coordinate resolution
		script = f"""
		(function() {{
			const elementsData = {json.dumps(elements_data)};
			const totalElementsFound = {total_elements};
			
			console.log('=== BROWSER-USE ENHANCED HIGHLIGHTING ===');
			console.log('Processing', elementsData.length, 'interactive elements with real coordinate resolution');
			if (totalElementsFound > elementsData.length) {{
				console.warn('Note: Limited to', elementsData.length, 'elements out of', totalElementsFound, 'total for performance');
			}}
			
			// High but reasonable z-index
			const HIGHLIGHT_Z_INDEX = 999999;
			
			// Create container for all highlights
			const container = document.createElement('div');
			container.id = 'browser-use-debug-highlights';
			container.setAttribute('data-browser-use-highlight', 'container');
			
			// Get document dimensions
			const docHeight = Math.max(
				document.body.scrollHeight,
				document.body.offsetHeight,
				document.documentElement.clientHeight,
				document.documentElement.scrollHeight,
				document.documentElement.offsetHeight
			);
			const docWidth = Math.max(
				document.body.scrollWidth,
				document.body.offsetWidth,
				document.documentElement.clientWidth,
				document.documentElement.scrollWidth,
				document.documentElement.offsetWidth
			);
			
			container.style.cssText = `
				position: absolute;
				top: 0;
				left: 0;
				width: ${{docWidth}}px;
				height: ${{docHeight}}px;
				pointer-events: none;
				z-index: ${{HIGHLIGHT_Z_INDEX}};
				overflow: visible;
				margin: 0;
				padding: 0;
				border: none;
				outline: none;
				box-shadow: none;
				background: none;
				font-family: inherit;
			`;
			
			// Helper function to create text nodes safely
			function createTextElement(tag, text, styles) {{
				const element = document.createElement(tag);
				element.textContent = text;
				if (styles) element.style.cssText = styles;
				return element;
			}}
			
			// Function to find element by backend node ID using DOM walker
			function findElementByBackendNodeId(backendNodeId, rootElement = document.documentElement) {{
				const walker = document.createTreeWalker(
					rootElement,
					NodeFilter.SHOW_ELEMENT,
					null,
					false
				);
				
				let node;
				while (node = walker.nextNode()) {{
					// Check if this element matches our backend node ID
					// We can't directly access backend node ID, so we'll use other attributes
					if (node.nodeType === Node.ELEMENT_NODE) {{
						// Try to match by unique characteristics
						return node; // For now, we'll implement a different approach
					}}
				}}
				return null;
			}}
			
			// Function to resolve element coordinates using CDP-like approach
			function resolveElementCoordinates(elementData) {{
				try {{
					// Try to find element using multiple strategies
					let element = null;
					
					// Strategy 1: Try XPath if available
					if (elementData.xpath) {{
						try {{
							const xpathResult = document.evaluate(
								'//' + elementData.xpath,
								document,
								null,
								XPathResult.FIRST_ORDERED_NODE_TYPE,
								null
							);
							element = xpathResult.singleNodeValue;
						}} catch (e) {{
							// XPath failed, try other methods
						}}
					}}
					
					// Strategy 2: Try to find by tag name and attributes
					if (!element) {{
						const candidates = document.getElementsByTagName(elementData.element_name);
						for (let candidate of candidates) {{
							// Simple matching by tag name for now
							if (candidate.tagName.toLowerCase() === elementData.element_name.toLowerCase()) {{
								element = candidate;
								break; // Take first match for now
							}}
						}}
					}}
					
					// Strategy 3: Look in all iframes (with timeout protection)
					if (!element) {{
						const iframes = document.querySelectorAll('iframe');
						for (let iframe of iframes) {{
							try {{
								const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
								if (iframeDoc) {{
									const iframeCandidates = iframeDoc.getElementsByTagName(elementData.element_name);
									for (let candidate of iframeCandidates) {{
										if (candidate.tagName.toLowerCase() === elementData.element_name.toLowerCase()) {{
											element = candidate;
											break;
										}}
									}}
									if (element) break;
								}}
							}} catch (e) {{
								// Cross-origin iframe, skip
								continue;
							}}
						}}
					}}
					
					if (element) {{
						const rect = element.getBoundingClientRect();
						const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
						const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
						
						return {{
							x: rect.left + scrollLeft,
							y: rect.top + scrollTop,
							width: rect.width,
							height: rect.height,
							found: true
						}};
					}} else {{
						// Fallback positioning for iframe content
						let fallbackY = 100;
						if (elementData.is_iframe_content) {{
							const iframeIndex = elementData.interactive_index % 10;
							fallbackY = 100 + (iframeIndex * 30);
						}}
						
						return {{
							x: elementData.is_iframe_content ? 600 : 50,
							y: fallbackY,
							width: elementData.is_iframe_content ? 180 : 100,
							height: 25,
							found: false
						}};
					}}
				}} catch (error) {{
					console.warn('Error resolving coordinates for element:', elementData.interactive_index, error);
					return {{
						x: 50,
						y: 100 + (elementData.interactive_index * 20),
						width: 100,
						height: 20,
						found: false
					}};
				}}
			}}
			
			// Process elements in batches to prevent browser lockup
			function createHighlightsBatched() {{
				const BATCH_SIZE = 20;  // Process 20 elements at a time
				let currentIndex = 0;
				
				function processBatch() {{
					const endIndex = Math.min(currentIndex + BATCH_SIZE, elementsData.length);
					
					// Process current batch
					for (let i = currentIndex; i < endIndex; i++) {{
						const elementData = elementsData[i];
						const coords = resolveElementCoordinates(elementData);  // Remove await - make it synchronous
						
						// Create highlight element
						const highlight = document.createElement('div');
						highlight.setAttribute('data-browser-use-highlight', 'element');
						highlight.setAttribute('data-element-id', elementData.interactive_index);
						
						// Determine styling based on element type
						const isIframeContent = elementData.is_iframe_content;
						const baseOutlineColor = isIframeContent ? '#9b59b6' : '#4a90e2';
						const backgroundStyle = isIframeContent ? 'rgba(155, 89, 182, 0.1)' : 'transparent';
						const foundIndicator = coords.found ? '' : ' (FALLBACK)';
						
						highlight.style.cssText = `
							position: absolute;
							left: ${{coords.x}}px;
							top: ${{coords.y}}px;
							width: ${{coords.width}}px;
							height: ${{coords.height}}px;
							outline: 2px solid ${{baseOutlineColor}};
							outline-offset: -2px;
							background: ${{backgroundStyle}};
							pointer-events: none;
							box-sizing: content-box;
							transition: all 0.2s ease;
							margin: 0;
							padding: 0;
							border: none;
							box-shadow: ${{isIframeContent ? '0 2px 8px rgba(155, 89, 182, 0.3)' : 'none'}};
							z-index: ${{isIframeContent ? HIGHLIGHT_Z_INDEX + 10 : HIGHLIGHT_Z_INDEX}};
						`;
						
						// Create enhanced label
						const labelText = isIframeContent ? `[${{elementData.interactive_index}}]🖼️` : elementData.interactive_index;
						const labelBgColor = isIframeContent ? '#9b59b6' : '#4a90e2';
						const labelPosition = isIframeContent ? 'top: -25px; left: -5px;' : 'top: -20px; left: 0;';
						
						const label = createTextElement('div', labelText + foundIndicator, `
							position: absolute;
							${{labelPosition}}
							background-color: ${{labelBgColor}};
							color: white;
							padding: ${{isIframeContent ? '3px 8px' : '2px 6px'}};
							font-size: ${{isIframeContent ? '11px' : '10px'}};
							font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
							font-weight: bold;
							border-radius: ${{isIframeContent ? '4px' : '3px'}};
							white-space: nowrap;
							z-index: ${{isIframeContent ? HIGHLIGHT_Z_INDEX + 11 : HIGHLIGHT_Z_INDEX + 1}};
							box-shadow: ${{isIframeContent ? '0 3px 8px rgba(155, 89, 182, 0.4)' : '0 2px 4px rgba(0,0,0,0.3)'}};
							border: ${{isIframeContent ? '1px solid rgba(255, 255, 255, 0.2)' : 'none'}};
							outline: none;
							margin: 0;
							line-height: 1.2;
						`);
						
						// Create detailed tooltip
						const tooltip = document.createElement('div');
						tooltip.setAttribute('data-browser-use-highlight', 'tooltip');
						tooltip.style.cssText = `
							position: absolute;
							top: -120px;
							left: 50%;
							transform: translateX(-50%);
							background-color: rgba(0, 0, 0, 0.95);
							color: white;
							padding: 10px 14px;
							font-size: 11px;
							font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
							border-radius: 6px;
							white-space: normal;
							z-index: ${{HIGHLIGHT_Z_INDEX + 20}};
							opacity: 0;
							visibility: hidden;
							transition: all 0.3s ease;
							box-shadow: 0 4px 12px rgba(0,0,0,0.5);
							border: 1px solid #555;
							max-width: 350px;
							line-height: 1.3;
							min-width: 180px;
							margin: 0;
						`;
						
						// Build tooltip content
						const status = coords.found ? '✅ FOUND' : '❌ FALLBACK';
						const typeIcon = isIframeContent ? '🖼️' : '🎯';
						const coordsText = `(${{Math.round(coords.x)}}, ${{Math.round(coords.y)}}) ${{Math.round(coords.width)}}×${{Math.round(coords.height)}}`;
						
						const header = createTextElement('div', `${{typeIcon}} [${{elementData.interactive_index}}] ${{elementData.element_name.toUpperCase()}}`, `
							color: ${{isIframeContent ? '#9b59b6' : '#4a90e2'}};
							font-weight: bold;
							font-size: 12px;
							margin-bottom: 6px;
							border-bottom: 1px solid #555;
							padding-bottom: 3px;
						`);
						
						const statusDiv = createTextElement('div', status, `
							color: ${{coords.found ? '#28a745' : '#fd7e14'}};
							font-size: 10px;
							font-weight: bold;
							margin-bottom: 6px;
						`);
						
						const coordsDiv = createTextElement('div', `Position: ${{coordsText}}`, `
							color: #ccc;
							font-size: 9px;
							margin-bottom: 4px;
						`);
						
						const textDiv = createTextElement('div', `Text: "${{elementData.text_content || 'No text'}}"`, `
							color: #aaa;
							font-size: 9px;
							font-style: italic;
						`);
						
						tooltip.appendChild(header);
						tooltip.appendChild(statusDiv);
						tooltip.appendChild(coordsDiv);
						tooltip.appendChild(textDiv);
						
						// Add hover effects
						highlight.addEventListener('mouseenter', () => {{
							highlight.style.outline = `3px solid #ff6b6b`;
							highlight.style.outlineOffset = '-1px';
							tooltip.style.opacity = '1';
							tooltip.style.visibility = 'visible';
							label.style.backgroundColor = '#ff6b6b';
							label.style.transform = 'scale(1.05)';
						}});
						
						highlight.addEventListener('mouseleave', () => {{
							highlight.style.outline = `2px solid ${{baseOutlineColor}}`;
							highlight.style.outlineOffset = '-2px';
							tooltip.style.opacity = '0';
							tooltip.style.visibility = 'hidden';
							label.style.backgroundColor = labelBgColor;
							label.style.transform = 'scale(1)';
						}});
						
						highlight.appendChild(tooltip);
						highlight.appendChild(label);
						container.appendChild(highlight);
					}}
					
					currentIndex = endIndex;
					
					// Continue with next batch if there are more elements
					if (currentIndex < elementsData.length) {{
						// Use requestAnimationFrame to prevent blocking the browser
						requestAnimationFrame(processBatch);
					}} else {{
						console.log('✅ Enhanced coordinate-resolved highlighting complete');
						if (totalElementsFound > elementsData.length) {{
							console.warn('Note: Showing', elementsData.length, 'highlights out of', totalElementsFound, 'total elements for performance');
						}}
					}}
				}}
				
				// Start processing
				processBatch();
			}}
			
			// Add container to document and create highlights
			document.body.appendChild(container);
			createHighlightsBatched();
		}})();
		"""

		# Inject the enhanced script via CDP
		await cdp_client.send.Runtime.evaluate(params={'expression': script, 'returnByValue': True}, session_id=session_id)
		print(f'✅ Enhanced coordinate-resolved highlighting injected for {len(limited_elements)} elements')
		if total_elements > MAX_HIGHLIGHTS:
			print(f'⚠️ Performance note: Limited to {MAX_HIGHLIGHTS} out of {total_elements} total elements')

	except Exception as e:
		print(f'❌ Error injecting enhanced highlighting script: {e}')
		import traceback

		traceback.print_exc()
