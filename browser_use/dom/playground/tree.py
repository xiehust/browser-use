# @file purpose: Interactive test script to explore DOM tree structures with optimized comprehensive detection

import asyncio
import json
import logging
import os
import time
import traceback
from pathlib import Path

import aiofiles

from browser_use.browser.profile import BrowserProfile
from browser_use.browser.session import BrowserSession
from browser_use.dom.service import DOMService

# Disable noisy logging
logging.getLogger('cdp_use').setLevel(logging.WARNING)
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('cdp_use.client').setLevel(logging.WARNING)


def is_debug_mode() -> bool:
	"""Check if we're in debug mode based on environment variable."""
	return os.getenv('BROWSER_USE_LOGGING_LEVEL', '').lower() == 'debug'


def print_section_header(title: str, char: str = '=', width: int = 80):
	"""Print a formatted section header for better log organization."""
	print(f'\n{char * width}')
	print(f'{title:^{width}}')
	print(f'{char * width}')


def print_subsection(title: str, char: str = '-', width: int = 60):
	"""Print a formatted subsection header."""
	print(f'\n{char * width}')
	print(f' {title}')
	print(f'{char * width}')


def analyze_element_interactivity(element: dict) -> dict:
	"""Analyze why an element is considered interactive and return reasoning."""
	reasons = []
	confidence = 'LOW'
	primary_reason = 'unknown'

	element_name = element.get('element_name', '').upper()
	attributes = element.get('attributes', {})

	# High confidence reasons
	if element_name in ['INPUT', 'BUTTON', 'SELECT', 'TEXTAREA']:
		primary_reason = 'form_element'
		reasons.append(f'Form element: {element_name}')
		if attributes.get('type'):
			reasons.append(f'Input type: {attributes["type"]}')
		confidence = 'HIGH'

	elif element_name == 'A' and attributes.get('href'):
		primary_reason = 'link_with_href'
		reasons.append(f'Link with href: {attributes["href"][:50]}...')
		confidence = 'HIGH'

	# Medium confidence reasons
	elif attributes.get('onclick'):
		primary_reason = 'onclick_handler'
		reasons.append('Has onclick handler')
		confidence = 'MEDIUM'

	elif attributes.get('role') in ['button', 'link', 'menuitem', 'tab']:
		primary_reason = 'interactive_role'
		reasons.append(f'Interactive role: {attributes["role"]}')
		confidence = 'MEDIUM'

	elif 'btn' in attributes.get('class', '').lower() or 'button' in attributes.get('class', '').lower():
		primary_reason = 'button_class'
		reasons.append('Button-like CSS class')
		confidence = 'MEDIUM'

	# Low confidence reasons
	elif element.get('is_scrollable'):
		primary_reason = 'scrollable'
		reasons.append('Scrollable element')
		confidence = 'LOW'

	elif element_name in ['DIV', 'SPAN'] and attributes:
		primary_reason = 'container_with_attributes'
		attr_count = len([k for k in attributes.keys() if not k.startswith('data-browser-use')])
		reasons.append(f'Container with {attr_count} attributes')
		confidence = 'LOW'

	# Check for additional indicators
	if attributes.get('aria-label'):
		reasons.append(f'ARIA label: {attributes["aria-label"][:30]}...')
	if attributes.get('id'):
		reasons.append(f'ID: {attributes["id"][:20]}...')
	if attributes.get('data-action'):
		reasons.append('Has data-action')

	return {
		'primary_reason': primary_reason,
		'reasons': reasons,
		'confidence': confidence,
		'element_type': element_name,
		'has_attributes': len(attributes) > 0,
	}


async def extract_interactive_elements_from_service(dom_service: DOMService) -> tuple[list[dict], str, dict]:
	"""Extract interactive elements with enhanced reasoning tracking and logging."""
	try:
		print_section_header('🔄 ENHANCED DOM EXTRACTION WITH REASONING')

		print('📋 Extraction Configuration:')
		print('   • Method: get_serialized_dom_tree(use_enhanced_filtering=False)')
		print('   • Focus: Comprehensive detection with optimization')
		print('   • Logging: Enhanced with reasoning tracking')

		# Use the main DOMTreeSerializer which is already highly optimized
		serialized, selector_map = await dom_service.get_serialized_dom_tree(use_enhanced_filtering=False)

		interactive_elements = []
		reasoning_summary = {'high_confidence': 0, 'medium_confidence': 0, 'low_confidence': 0, 'by_type': {}, 'by_reason': {}}

		print_subsection('🎯 INTERACTIVE ELEMENT ANALYSIS')

		# Extract bounding boxes for elements that have interactive indices
		for interactive_index, node in selector_map.items():
			if node.snapshot_node and hasattr(node.snapshot_node, 'bounding_box') and node.snapshot_node.bounding_box:
				bbox = node.snapshot_node.bounding_box

				# Only include elements with valid bounding boxes
				if bbox.get('width', 0) > 0 and bbox.get('height', 0) > 0:
					element = {
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

					# Analyze why this element is interactive
					reasoning = analyze_element_interactivity(element)
					element['reasoning'] = reasoning

					interactive_elements.append(element)

					# Update statistics
					confidence = reasoning['confidence'].lower()
					reasoning_summary[f'{confidence}_confidence'] += 1

					element_type = reasoning['element_type']
					reasoning_summary['by_type'][element_type] = reasoning_summary['by_type'].get(element_type, 0) + 1

					primary_reason = reasoning['primary_reason']
					reasoning_summary['by_reason'][primary_reason] = reasoning_summary['by_reason'].get(primary_reason, 0) + 1

		# Print detailed statistics
		print('📊 EXTRACTION RESULTS:')
		print(f'   • Total interactive elements: {len(interactive_elements)}')
		print(f'   • Serialized content length: {len(serialized):,} characters')
		print(f'   • Selector map entries: {len(selector_map)}')

		print('\n🎯 CONFIDENCE BREAKDOWN:')
		print(f'   • High confidence: {reasoning_summary["high_confidence"]} elements')
		print(f'   • Medium confidence: {reasoning_summary["medium_confidence"]} elements')
		print(f'   • Low confidence: {reasoning_summary["low_confidence"]} elements')

		print('\n📋 ELEMENT TYPE BREAKDOWN:')
		for element_type, count in sorted(reasoning_summary['by_type'].items(), key=lambda x: x[1], reverse=True):
			print(f'   • {element_type}: {count}')

		print('\n🔍 REASONING BREAKDOWN:')
		for reason, count in sorted(reasoning_summary['by_reason'].items(), key=lambda x: x[1], reverse=True):
			print(f'   • {reason}: {count}')

		# Show iframe and shadow DOM information
		iframe_contexts = serialized.count('=== IFRAME CONTENT')
		shadow_contexts = serialized.count('=== SHADOW DOM')
		cross_origin_iframes = serialized.count('[CROSS-ORIGIN]')

		if iframe_contexts > 0 or shadow_contexts > 0:
			print('\n🖼️  ADVANCED CONTEXT DETECTION:')
			if iframe_contexts > 0:
				print(f'   • Iframe contexts: {iframe_contexts}')
			if cross_origin_iframes > 0:
				print(f'   • Cross-origin iframes: {cross_origin_iframes}')
			if shadow_contexts > 0:
				print(f'   • Shadow DOM contexts: {shadow_contexts}')

		# Sample element analysis for debugging
		if interactive_elements:
			print('\n🔬 SAMPLE ELEMENT ANALYSIS (first 5):')
			for i, elem in enumerate(interactive_elements[:5], 1):
				reasoning = elem['reasoning']
				print(f'   [{elem["interactive_index"]}] {reasoning["element_type"]} ({reasoning["confidence"]} confidence)')
				print(f'       └─ {reasoning["primary_reason"]}: {"; ".join(reasoning["reasons"][:2])}')

		return interactive_elements, serialized, selector_map

	except Exception as e:
		print_section_header('❌ EXTRACTION ERROR', char='!')
		print(f'Error: {str(e)}')
		print(f'Type: {type(e).__name__}')
		print('Traceback:')
		traceback.print_exc()
		return [], '', {}


async def inject_highlighting_script(browser_session: BrowserSession, interactive_elements: list[dict]) -> None:
	"""Inject JavaScript to highlight interactive elements with detailed hover tooltips that work around CSP restrictions."""
	if not interactive_elements:
		print('⚠️ No interactive elements to highlight')
		return

	try:
		# Get the current page from the browser session
		page = await browser_session.get_current_page()

		print(f'📍 Creating CSP-safe highlighting with detailed tooltips for {len(interactive_elements)} elements')

		# Create CSP-safe highlighting script using DOM methods instead of innerHTML
		script = f"""
		(function() {{
			// Remove any existing highlights
			const existingHighlights = document.querySelectorAll('[data-browser-use-highlight]');
			existingHighlights.forEach(el => el.remove());
			
			// Interactive elements data with reasoning
			const interactiveElements = {json.dumps(interactive_elements)};
			
			console.log('=== BROWSER-USE ENHANCED HIGHLIGHTING ===');
			console.log('Interactive elements with reasoning:', interactiveElements.length);
			
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
			
			// Helper function to create text nodes safely (CSP-friendly)
			function createTextElement(tag, text, styles) {{
				const element = document.createElement(tag);
				element.textContent = text;
				if (styles) element.style.cssText = styles;
				return element;
			}}
			
			// Add enhanced highlights with detailed tooltips
			interactiveElements.forEach((element, index) => {{
				const highlight = document.createElement('div');
				highlight.setAttribute('data-browser-use-highlight', 'element');
				highlight.setAttribute('data-element-id', element.interactive_index);
				highlight.style.cssText = `
					position: absolute;
					left: ${{element.x}}px;
					top: ${{element.y}}px;
					width: ${{element.width}}px;
					height: ${{element.height}}px;
					border: 2px solid #4a90e2;
					background-color: rgba(74, 144, 226, 0.1);
					pointer-events: none;
					box-sizing: border-box;
					transition: all 0.2s ease;
				`;
				
				// Enhanced label with interactive index
				const label = createTextElement('div', element.interactive_index, `
					position: absolute;
					top: -20px;
					left: 0;
					background-color: #4a90e2;
					color: white;
					padding: 2px 6px;
					font-size: 11px;
					font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
					font-weight: bold;
					border-radius: 3px;
					white-space: nowrap;
					z-index: 1000001;
					box-shadow: 0 2px 4px rgba(0,0,0,0.3);
				`);
				
				// Enhanced tooltip with detailed reasoning (CSP-safe)
				const tooltip = document.createElement('div');
				tooltip.setAttribute('data-browser-use-highlight', 'tooltip');
				tooltip.style.cssText = `
					position: absolute;
					top: -160px;
					left: 50%;
					transform: translateX(-50%);
					background-color: rgba(0, 0, 0, 0.95);
					color: white;
					padding: 12px 16px;
					font-size: 12px;
					font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
					border-radius: 8px;
					white-space: nowrap;
					z-index: 1000002;
					opacity: 0;
					visibility: hidden;
					transition: all 0.3s ease;
					box-shadow: 0 6px 20px rgba(0,0,0,0.5);
					border: 1px solid #666;
					max-width: 400px;
					white-space: normal;
					line-height: 1.4;
					min-width: 200px;
				`;
				
				// Build detailed tooltip content with reasoning (CSP-safe DOM creation)
				const reasoning = element.reasoning || {{}};
				const confidence = reasoning.confidence || 'UNKNOWN';
				const primaryReason = reasoning.primary_reason || 'unknown';
				const reasons = reasoning.reasons || [];
				const elementType = reasoning.element_type || element.element_name || 'UNKNOWN';
				
				// Determine confidence color and styling
				let confidenceColor = '#4a90e2';
				let confidenceIcon = '🔍';
				let borderColor = '#4a90e2';
				
				if (confidence === 'HIGH') {{
					confidenceColor = '#28a745';
					confidenceIcon = '✅';
					borderColor = '#28a745';
				}} else if (confidence === 'MEDIUM') {{
					confidenceColor = '#ffc107';
					confidenceIcon = '⚠️';
					borderColor = '#ffc107';
				}} else {{
					confidenceColor = '#fd7e14';
					confidenceIcon = '❓';
					borderColor = '#fd7e14';
				}}
				
				// Create tooltip header
				const header = createTextElement('div', `${{confidenceIcon}} [${{element.interactive_index}}] ${{elementType.toUpperCase()}}`, `
					color: ${{confidenceColor}};
					font-weight: bold;
					font-size: 13px;
					margin-bottom: 8px;
					border-bottom: 1px solid #666;
					padding-bottom: 4px;
				`);
				
				// Create confidence indicator
				const confidenceDiv = createTextElement('div', `${{confidence}} CONFIDENCE`, `
					color: ${{confidenceColor}};
					font-size: 11px;
					font-weight: bold;
					margin-bottom: 8px;
				`);
				
				// Create primary reason
				const primaryReasonDiv = createTextElement('div', `Primary: ${{primaryReason.replace('_', ' ').toUpperCase()}}`, `
					color: #fff;
					font-size: 11px;
					margin-bottom: 6px;
					font-weight: bold;
				`);
				
				// Create reasons list
				const reasonsContainer = document.createElement('div');
				reasonsContainer.style.cssText = `
					font-size: 10px;
					color: #ccc;
					margin-top: 4px;
				`;
				
				if (reasons.length > 0) {{
					const reasonsTitle = createTextElement('div', 'Evidence:', `
						color: #fff;
						font-size: 10px;
						margin-bottom: 4px;
						font-weight: bold;
					`);
					reasonsContainer.appendChild(reasonsTitle);
					
					reasons.slice(0, 4).forEach(reason => {{
						const reasonDiv = createTextElement('div', `• ${{reason}}`, `
							color: #ccc;
							font-size: 10px;
							margin-bottom: 2px;
							padding-left: 4px;
						`);
						reasonsContainer.appendChild(reasonDiv);
					}});
					
					if (reasons.length > 4) {{
						const moreDiv = createTextElement('div', `... and ${{reasons.length - 4}} more`, `
							color: #999;
							font-size: 9px;
							font-style: italic;
							margin-top: 2px;
						`);
						reasonsContainer.appendChild(moreDiv);
					}}
				}} else {{
					const noReasonsDiv = createTextElement('div', 'No specific evidence found', `
						color: #999;
						font-size: 10px;
						font-style: italic;
					`);
					reasonsContainer.appendChild(noReasonsDiv);
				}}
				
				// Add bounding box info
				const boundsDiv = createTextElement('div', `Position: (${{Math.round(element.x)}}, ${{Math.round(element.y)}}) Size: ${{Math.round(element.width)}}×${{Math.round(element.height)}}`, `
					color: #888;
					font-size: 9px;
					margin-top: 8px;
					border-top: 1px solid #444;
					padding-top: 4px;
				`);
				
				// Assemble tooltip
				tooltip.appendChild(header);
				tooltip.appendChild(confidenceDiv);
				tooltip.appendChild(primaryReasonDiv);
				tooltip.appendChild(reasonsContainer);
				tooltip.appendChild(boundsDiv);
				
				// Set highlight border color based on confidence
				highlight.style.borderColor = borderColor;
				label.style.backgroundColor = borderColor;
				
				// Add hover effects
				highlight.addEventListener('mouseenter', () => {{
					highlight.style.borderColor = '#ff6b6b';
					highlight.style.backgroundColor = 'rgba(255, 107, 107, 0.2)';
					highlight.style.borderWidth = '3px';
					highlight.style.boxShadow = '0 0 10px rgba(255, 107, 107, 0.5)';
					tooltip.style.opacity = '1';
					tooltip.style.visibility = 'visible';
					label.style.backgroundColor = '#ff6b6b';
					label.style.transform = 'scale(1.1)';
				}});
				
				highlight.addEventListener('mouseleave', () => {{
					highlight.style.borderColor = borderColor;
					highlight.style.backgroundColor = 'rgba(74, 144, 226, 0.1)';
					highlight.style.borderWidth = '2px';
					highlight.style.boxShadow = 'none';
					tooltip.style.opacity = '0';
					tooltip.style.visibility = 'hidden';
					label.style.backgroundColor = borderColor;
					label.style.transform = 'scale(1)';
				}});
				
				highlight.appendChild(tooltip);
				highlight.appendChild(label);
				container.appendChild(highlight);
			}});
			
			// Add enhanced legend with detailed statistics
			const legend = document.createElement('div');
			legend.setAttribute('data-browser-use-highlight', 'legend');
			legend.style.cssText = `
				position: fixed;
				top: 10px;
				right: 10px;
				background-color: rgba(0, 0, 0, 0.9);
				color: white;
				padding: 16px 20px;
				border-radius: 10px;
				font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
				font-size: 11px;
				z-index: 1000003;
				box-shadow: 0 6px 20px rgba(0,0,0,0.4);
				border: 1px solid #444;
				min-width: 250px;
				max-width: 300px;
			`;
			
			// Calculate detailed statistics
			const stats = {{ high: 0, medium: 0, low: 0 }};
			const reasonStats = {{}};
			const typeStats = {{}};
			
			interactiveElements.forEach(el => {{
				const reasoning = el.reasoning || {{}};
				const confidence = reasoning.confidence || 'UNKNOWN';
				const primaryReason = reasoning.primary_reason || 'unknown';
				const elementType = reasoning.element_type || el.element_name || 'UNKNOWN';
				
				// Count confidence levels
				if (confidence === 'HIGH') stats.high++;
				else if (confidence === 'MEDIUM') stats.medium++;
				else stats.low++;
				
				// Count primary reasons
				reasonStats[primaryReason] = (reasonStats[primaryReason] || 0) + 1;
				
				// Count element types
				typeStats[elementType] = (typeStats[elementType] || 0) + 1;
			}});
			
			// Create legend content
			const legendTitle = createTextElement('div', '🔍 Interactive Elements Analysis', `
				color: #4a90e2;
				font-weight: bold;
				font-size: 12px;
				margin-bottom: 10px;
				text-align: center;
			`);
			
			const totalCount = createTextElement('div', `Total Elements: ${{interactiveElements.length}}`, `
				color: #fff;
				font-size: 11px;
				margin-bottom: 8px;
				text-align: center;
			`);
			
			const confidenceSection = document.createElement('div');
			confidenceSection.style.cssText = 'margin-bottom: 8px; border-bottom: 1px solid #444; padding-bottom: 8px;';
			
			const confTitle = createTextElement('div', 'Confidence Levels:', `
				color: #ccc;
				font-size: 10px;
				margin-bottom: 4px;
			`);
			confidenceSection.appendChild(confTitle);
			
			const highConf = createTextElement('div', `✅ High: ${{stats.high}}`, `
				color: #28a745;
				font-size: 10px;
				margin-bottom: 2px;
			`);
			const medConf = createTextElement('div', `⚠️ Medium: ${{stats.medium}}`, `
				color: #ffc107;
				font-size: 10px;
				margin-bottom: 2px;
			`);
			const lowConf = createTextElement('div', `❓ Low: ${{stats.low}}`, `
				color: #fd7e14;
				font-size: 10px;
			`);
			
			confidenceSection.appendChild(highConf);
			confidenceSection.appendChild(medConf);
			confidenceSection.appendChild(lowConf);
			
			// Top element types
			const topTypes = Object.entries(typeStats)
				.sort((a, b) => b[1] - a[1])
				.slice(0, 3);
			
			const typesSection = document.createElement('div');
			typesSection.style.cssText = 'margin-bottom: 8px; border-bottom: 1px solid #444; padding-bottom: 8px;';
			
			const typesTitle = createTextElement('div', 'Top Element Types:', `
				color: #ccc;
				font-size: 10px;
				margin-bottom: 4px;
			`);
			typesSection.appendChild(typesTitle);
			
			topTypes.forEach(([type, count]) => {{
				const typeDiv = createTextElement('div', `${{type}}: ${{count}}`, `
					color: #fff;
					font-size: 10px;
					margin-bottom: 2px;
				`);
				typesSection.appendChild(typeDiv);
			}});
			
			// Top reasons
			const topReasons = Object.entries(reasonStats)
				.sort((a, b) => b[1] - a[1])
				.slice(0, 3);
			
			const reasonsSection = document.createElement('div');
			reasonsSection.style.cssText = 'margin-bottom: 8px;';
			
			const reasonsTitle = createTextElement('div', 'Top Reasons:', `
				color: #ccc;
				font-size: 10px;
				margin-bottom: 4px;
			`);
			reasonsSection.appendChild(reasonsTitle);
			
			topReasons.forEach(([reason, count]) => {{
				const reasonDiv = createTextElement('div', `${{reason.replace('_', ' ')}}: ${{count}}`, `
					color: #fff;
					font-size: 10px;
					margin-bottom: 2px;
				`);
				reasonsSection.appendChild(reasonDiv);
			}});
			
			const instructions = createTextElement('div', 'Hover elements for detailed analysis', `
				color: #999;
				font-size: 9px;
				text-align: center;
				margin-top: 6px;
				font-style: italic;
			`);
			
			// Assemble legend
			legend.appendChild(legendTitle);
			legend.appendChild(totalCount);
			legend.appendChild(confidenceSection);
			legend.appendChild(typesSection);
			legend.appendChild(reasonsSection);
			legend.appendChild(instructions);
			
			// Add container and legend to document
			document.body.appendChild(container);
			document.body.appendChild(legend);
			
			console.log('✅ Enhanced browser-use highlighting complete with detailed tooltips');
			console.log('📊 Statistics:', {{ confidence: stats, reasons: reasonStats, types: typeStats }});
		}})();
		"""

		# Inject the enhanced CSP-safe script
		await page.evaluate(script)
		print(f'✅ Enhanced CSP-safe highlighting with detailed tooltips injected for {len(interactive_elements)} elements')

		# Print summary of what was highlighted
		confidence_counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
		for elem in interactive_elements:
			confidence = elem.get('reasoning', {}).get('confidence', 'LOW')
			confidence_counts[confidence] += 1

		print('📊 Highlighting Summary:')
		print(f'   • High confidence elements: {confidence_counts["HIGH"]} (green borders)')
		print(f'   • Medium confidence elements: {confidence_counts["MEDIUM"]} (yellow borders)')
		print(f'   • Low confidence elements: {confidence_counts["LOW"]} (orange borders)')
		print('   • Hover any highlighted element to see detailed reasoning')

	except Exception as e:
		print(f'❌ Error injecting enhanced highlighting script: {e}')
		traceback.print_exc()


async def save_outputs_to_files(serialized: str, selector_map: dict, interactive_elements: list[dict], url: str) -> None:
	"""Save all outputs to tmp files for analysis with enhanced reasoning data."""
	try:
		print_subsection('💾 SAVING ANALYSIS FILES')

		# Create tmp directory if it doesn't exist
		tmp_dir = Path('tmp')
		tmp_dir.mkdir(exist_ok=True)

		# Clean URL for filename
		safe_url = url.replace('://', '_').replace('/', '_').replace('?', '_').replace('&', '_')[:50]

		# Save serialized DOM tree with enhanced metadata
		serialized_file = tmp_dir / f'enhanced_dom_{safe_url}.txt'
		async with aiofiles.open(serialized_file, 'w', encoding='utf-8') as f:
			await f.write('=== ENHANCED DOM SERIALIZATION WITH REASONING ===\n')
			await f.write(f'URL: {url}\n')
			await f.write(f'Timestamp: {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
			await f.write(f'Interactive elements: {len(interactive_elements)}\n')
			await f.write(f'Selector map entries: {len(selector_map)}\n')
			await f.write(f'Serialized length: {len(serialized)} characters\n')

			# Add reasoning summary
			if interactive_elements and 'reasoning' in interactive_elements[0]:
				confidence_counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
				reason_counts = {}
				type_counts = {}

				for elem in interactive_elements:
					reasoning = elem['reasoning']
					confidence_counts[reasoning['confidence']] += 1
					reason_counts[reasoning['primary_reason']] = reason_counts.get(reasoning['primary_reason'], 0) + 1
					type_counts[reasoning['element_type']] = type_counts.get(reasoning['element_type'], 0) + 1

				await f.write('\n=== REASONING ANALYSIS ===\n')
				await f.write('Confidence Distribution:\n')
				for conf, count in confidence_counts.items():
					await f.write(f'  • {conf}: {count}\n')

				await f.write('\nPrimary Reasons:\n')
				for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
					await f.write(f'  • {reason}: {count}\n')

				await f.write('\nElement Types:\n')
				for elem_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
					await f.write(f'  • {elem_type}: {count}\n')

			await f.write('=' * 60 + '\n\n')
			await f.write(serialized)

		# Save enhanced interactive elements with reasoning
		elements_file = tmp_dir / f'enhanced_elements_{safe_url}.json'
		async with aiofiles.open(elements_file, 'w', encoding='utf-8') as f:
			enhanced_data = {
				'metadata': {
					'url': url,
					'timestamp': time.time(),
					'total_elements': len(interactive_elements),
					'selector_map_size': len(selector_map),
				},
				'elements': interactive_elements,
			}
			await f.write(json.dumps(enhanced_data, indent=2, ensure_ascii=False))

		# Save detailed selector map
		selector_file = tmp_dir / f'enhanced_selector_map_{safe_url}.json'
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

		print('📁 Files saved to tmp/ directory:')
		print(f'   • {serialized_file.name} - Enhanced DOM serialization with reasoning')
		print(f'   • {elements_file.name} - Interactive elements with detailed analysis')
		print(f'   • {selector_file.name} - Selector map for debugging')

	except Exception as e:
		print(f'❌ Error saving enhanced files: {e}')
		traceback.print_exc()


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


async def run_comprehensive_website_tests():
	"""Run comprehensive tests on all major website types to validate serializer performance."""

	# Test websites covering different complexity levels
	test_websites = [
		{
			'name': 'Simple Static',
			'url': 'https://example.com',
			'expected_elements': (1, 10),  # min, max expected interactive elements
			'complexity': 'low',
		},
		{'name': 'Modern Homepage', 'url': 'https://browser-use.com', 'expected_elements': (10, 50), 'complexity': 'medium'},
		{'name': 'Complex Platform', 'url': 'https://github.com', 'expected_elements': (20, 100), 'complexity': 'high'},
		{
			'name': 'UI Components',
			'url': 'https://semantic-ui.com/modules/dropdown.html',
			'expected_elements': (15, 80),
			'complexity': 'medium',
		},
		{
			'name': 'Travel Application',
			'url': 'https://www.google.com/travel/flights',
			'expected_elements': (50, 300),
			'complexity': 'very_high',
		},
		{
			'name': 'Content Heavy',
			'url': 'https://en.wikipedia.org/wiki/Internet',
			'expected_elements': (30, 150),
			'complexity': 'high',
		},
	]

	# Create browser session
	profile = BrowserProfile(headless=False, keep_alive=True)
	browser_session = BrowserSession(browser_profile=profile)

	try:
		await browser_session.start()
		dom_service = DOMService(browser_session)

		print('🚀 COMPREHENSIVE DOM SERIALIZER TESTING SUITE')
		print('=' * 80)
		print(f'Testing {len(test_websites)} websites across different complexity levels')
		print('=' * 80)

		all_results = []

		for i, website in enumerate(test_websites, 1):
			print(f'\n🌐 TEST {i}/{len(test_websites)}: {website["name"]}')
			print(f'URL: {website["url"]}')
			print(f'Expected Complexity: {website["complexity"].upper()}')
			print('-' * 60)

			try:
				# Navigate to website
				print(f'📍 Navigating to {website["url"]}...')
				await browser_session.navigate_to(website['url'])
				await asyncio.sleep(4)  # Wait for page to load completely

				# Extract interactive elements with performance metrics
				interactive_elements, serialized, selector_map = await extract_interactive_elements_from_service(dom_service)

				# Try to get metrics if available (metrics are printed in the extraction process)
				metrics = None

				# Analyze results
				result = analyze_website_results(website, interactive_elements, serialized, selector_map, metrics)
				all_results.append(result)

				# Save detailed outputs
				await save_detailed_test_outputs(website, interactive_elements, serialized, selector_map)

				# Show sample elements
				print('\n🎯 Sample Interactive Elements (showing first 5):')
				for j, elem in enumerate(interactive_elements[:5], 1):
					attrs_info = get_element_description(elem)
					print(f'   [{elem["interactive_index"]}] {elem["element_name"]}{attrs_info}')

				if len(interactive_elements) > 5:
					print(f'   ... and {len(interactive_elements) - 5} more elements')

				# Show serialized preview
				print('\n📝 Serialized Output Preview (first 400 chars):')
				print('-' * 40)
				print(serialized[:400])
				if len(serialized) > 400:
					print('...[TRUNCATED]')
				print('-' * 40)

			except Exception as e:
				print(f'❌ Error testing {website["name"]}: {e}')
				traceback.print_exc()
				result = {
					'website': website,
					'status': 'failed',
					'error': str(e),
					'interactive_count': 0,
					'serialized_length': 0,
					'performance_rating': 'FAILED',
				}
				all_results.append(result)

			print(f'\n✅ Completed test {i}/{len(test_websites)}')

		# Generate comprehensive summary report
		print('\n' + '=' * 80)
		print('📊 COMPREHENSIVE TEST RESULTS SUMMARY')
		print('=' * 80)

		generate_comprehensive_report(all_results)

		# Save summary to file
		await save_comprehensive_summary(all_results)

	except Exception as e:
		print(f'❌ Critical error in testing suite: {e}')
		traceback.print_exc()
	finally:
		await browser_session.stop()


def analyze_website_results(website_config, interactive_elements, serialized, selector_map, metrics):
	"""Analyze results for a single website test."""

	result = {
		'website': website_config,
		'interactive_count': len(interactive_elements),
		'serialized_length': len(serialized),
		'selector_map_size': len(selector_map),
		'status': 'success',
		'metrics': metrics,
	}

	# Check if element count is within expected range
	min_expected, max_expected = website_config['expected_elements']
	element_count = len(interactive_elements)

	if element_count < min_expected:
		result['element_count_status'] = f'⚠️  LOW ({element_count} < {min_expected})'
	elif element_count > max_expected:
		result['element_count_status'] = f'⚠️  HIGH ({element_count} > {max_expected})'
	else:
		result['element_count_status'] = f'✅ GOOD ({element_count} in range {min_expected}-{max_expected})'

	# Performance rating
	if metrics:
		total_time = metrics.total_time
		if total_time < 0.05:
			result['performance_rating'] = '🔥 EXCELLENT'
		elif total_time < 0.1:
			result['performance_rating'] = '✅ GOOD'
		elif total_time < 0.2:
			result['performance_rating'] = '⚠️  MODERATE'
		else:
			result['performance_rating'] = '🐌 SLOW'
	else:
		# Estimate performance based on element count and complexity
		complexity_factor = {'low': 1.0, 'medium': 1.5, 'high': 2.0, 'very_high': 3.0}.get(website_config['complexity'], 1.0)

		estimated_complexity = len(interactive_elements) * complexity_factor

		if estimated_complexity < 50:
			result['performance_rating'] = '🔥 EXCELLENT (estimated)'
		elif estimated_complexity < 150:
			result['performance_rating'] = '✅ GOOD (estimated)'
		elif estimated_complexity < 300:
			result['performance_rating'] = '⚠️  MODERATE (estimated)'
		else:
			result['performance_rating'] = '🐌 SLOW (estimated)'

	# Quality analysis
	result['serialized_quality'] = analyze_serialized_quality(serialized, interactive_elements)

	return result


def analyze_serialized_quality(serialized, interactive_elements):
	"""Analyze the quality of the serialized output."""

	# Check for common quality indicators
	has_shadow_dom = 'SHADOW DOM' in serialized
	has_iframe = 'IFRAME CONTENT' in serialized
	has_structured_elements = '[' in serialized and '<' in serialized

	# Calculate information density
	avg_chars_per_element = len(serialized) / max(len(interactive_elements), 1)

	quality_score = 0
	notes = []

	if has_structured_elements:
		quality_score += 25
		notes.append('✅ Structured format')

	if has_shadow_dom:
		quality_score += 15
		notes.append('✅ Shadow DOM support')

	if has_iframe:
		quality_score += 15
		notes.append('✅ Iframe support')

	if 10 <= avg_chars_per_element <= 100:
		quality_score += 25
		notes.append('✅ Good information density')
	elif avg_chars_per_element < 10:
		notes.append('⚠️  Low information density')
	else:
		notes.append('⚠️  High information density')

	if len(interactive_elements) > 0:
		quality_score += 20
		notes.append('✅ Found interactive elements')
	else:
		notes.append('❌ No interactive elements found')

	return {
		'score': quality_score,
		'rating': get_quality_rating(quality_score),
		'notes': notes,
		'avg_chars_per_element': avg_chars_per_element,
	}


def get_quality_rating(score):
	"""Convert quality score to rating."""
	if score >= 90:
		return '🔥 EXCELLENT'
	elif score >= 70:
		return '✅ GOOD'
	elif score >= 50:
		return '⚠️  MODERATE'
	else:
		return '❌ POOR'


def get_element_description(elem):
	"""Get a readable description of an element."""
	attrs_info = ''
	if elem['attributes']:
		key_attrs = ['id', 'class', 'type', 'href', 'aria-label']
		relevant_attrs = []
		for k, v in elem['attributes'].items():
			if k in key_attrs and v:
				# Truncate long values
				value = str(v)[:30] + '...' if len(str(v)) > 30 else str(v)
				relevant_attrs.append(f"{k}='{value}'")
		if relevant_attrs:
			attrs_info = f' ({", ".join(relevant_attrs)})'
	return attrs_info


async def save_detailed_test_outputs(website_config, interactive_elements, serialized, selector_map):
	"""Save detailed test outputs for each website."""
	try:
		# Create tmp directory if it doesn't exist
		tmp_dir = Path('tmp/test_results')
		tmp_dir.mkdir(parents=True, exist_ok=True)

		# Clean name for filename
		safe_name = website_config['name'].replace(' ', '_').replace('/', '_').lower()

		# Save serialized output
		serialized_file = tmp_dir / f'{safe_name}_serialized.txt'
		async with aiofiles.open(serialized_file, 'w', encoding='utf-8') as f:
			await f.write('=== DOM SERIALIZATION TEST RESULTS ===\n')
			await f.write(f'Website: {website_config["name"]}\n')
			await f.write(f'URL: {website_config["url"]}\n')
			await f.write(f'Complexity: {website_config["complexity"]}\n')
			await f.write(f'Interactive elements: {len(interactive_elements)}\n')
			await f.write(f'Serialized length: {len(serialized)} characters\n')
			await f.write('=' * 60 + '\n\n')
			await f.write(serialized)

		# Save interactive elements details
		elements_file = tmp_dir / f'{safe_name}_elements.json'
		async with aiofiles.open(elements_file, 'w', encoding='utf-8') as f:
			await f.write(json.dumps(interactive_elements, indent=2, ensure_ascii=False))

		print(f'📁 Saved test outputs: {serialized_file.name}, {elements_file.name}')

	except Exception as e:
		print(f'❌ Error saving test outputs: {e}')


def generate_comprehensive_report(all_results):
	"""Generate a comprehensive report of all test results."""

	successful_tests = [r for r in all_results if r['status'] == 'success']
	failed_tests = [r for r in all_results if r['status'] == 'failed']

	print('📈 OVERALL STATISTICS:')
	print(f'   • Total Tests: {len(all_results)}')
	print(f'   • Successful: {len(successful_tests)}')
	print(f'   • Failed: {len(failed_tests)}')

	if successful_tests:
		# Performance summary
		print('\n⏱️  PERFORMANCE SUMMARY:')
		performance_ratings = {}
		for result in successful_tests:
			rating = result['performance_rating']
			performance_ratings[rating] = performance_ratings.get(rating, 0) + 1

		for rating, count in performance_ratings.items():
			print(f'   • {rating}: {count} websites')

		# Element count analysis
		print('\n📊 ELEMENT COUNT ANALYSIS:')
		total_elements = sum(r['interactive_count'] for r in successful_tests)
		avg_elements = total_elements / len(successful_tests)
		max_elements = max(r['interactive_count'] for r in successful_tests)
		min_elements = min(r['interactive_count'] for r in successful_tests)

		print(f'   • Total Interactive Elements: {total_elements:,}')
		print(f'   • Average per Website: {avg_elements:.1f}')
		print(f'   • Range: {min_elements} - {max_elements}')

		# Detailed results per website
		print('\n🌐 DETAILED RESULTS BY WEBSITE:')
		for result in successful_tests:
			website = result['website']
			print(f'\n   🔸 {website["name"]} ({website["complexity"].upper()})')
			print(f'      • Interactive Elements: {result["interactive_count"]}')
			print(f'      • Element Count Status: {result["element_count_status"]}')
			print(f'      • Performance: {result["performance_rating"]}')
			print(f'      • Serialized Length: {result["serialized_length"]:,} chars')
			if 'serialized_quality' in result:
				quality = result['serialized_quality']
				print(f'      • Quality: {quality["rating"]} ({quality["score"]}/100)')

			# Show metrics if available
			if result.get('metrics'):
				metrics = result['metrics']
				print(f'      • Timing: {metrics.total_time:.3f}s')
				if hasattr(metrics, 'ax_candidates') and hasattr(metrics, 'final_interactive_count'):
					reduction = (
						1 - metrics.final_interactive_count / max(metrics.ax_candidates + metrics.dom_candidates, 1)
					) * 100
					print(f'      • Reduction: {reduction:.1f}%')
			else:
				print('      • Metrics: Available in console output')

	if failed_tests:
		print('\n❌ FAILED TESTS:')
		for result in failed_tests:
			print(f'   • {result["website"]["name"]}: {result["error"]}')


async def save_comprehensive_summary(all_results):
	"""Save comprehensive summary to file."""
	try:
		tmp_dir = Path('tmp/test_results')
		tmp_dir.mkdir(parents=True, exist_ok=True)

		summary_file = tmp_dir / 'comprehensive_test_summary.json'

		# Prepare summary data
		summary_data = {
			'test_timestamp': time.time(),
			'total_tests': len(all_results),
			'successful_tests': len([r for r in all_results if r['status'] == 'success']),
			'failed_tests': len([r for r in all_results if r['status'] == 'failed']),
			'results': all_results,
		}

		async with aiofiles.open(summary_file, 'w', encoding='utf-8') as f:
			await f.write(json.dumps(summary_data, indent=2, ensure_ascii=False, default=str))

		print(f'\n📁 Comprehensive summary saved: {summary_file.name}')

	except Exception as e:
		print(f'❌ Error saving comprehensive summary: {e}')


async def main():
	"""Main function with choice between interactive and comprehensive testing."""
	print('🔍 DOM Extraction Testing Tool')
	print('=' * 50)
	print('Choose testing mode:')
	print('  1. Interactive testing (original)')
	print('  2. Comprehensive automated testing')

	try:
		choice = input('Enter choice (1 or 2): ').strip()
		if choice == '2':
			await run_comprehensive_website_tests()
		else:
			await interactive_testing_mode()
	except (EOFError, KeyboardInterrupt):
		print('\n👋 Exiting...')


async def interactive_testing_mode():
	"""Original interactive testing mode."""
	# Create browser session
	profile = BrowserProfile(headless=False, keep_alive=True)
	browser_session = BrowserSession(browser_profile=profile)

	try:
		await browser_session.start()

		# Create DOM service
		dom_service = DOMService(browser_session)

		print('🔍 Optimized Comprehensive DOM Extraction Tool')
		print('=' * 60)
		print('🎯 PURPOSE: Fast comprehensive DOM element detection')
		print('  ✅ AX tree-driven filtering for speed')
		print('  ✅ Viewport-based element filtering')
		print('  ✅ Aggressive container removal')
		print('  ✅ Perfect sync between highlighting and serialization')
		print('=' * 60)

		while True:
			try:
				# Get website choice
				url = get_website_choice()

				# Navigate to chosen website
				print(f'\n🌐 Navigating to: {url}')
				await browser_session.navigate_to(url)
				await asyncio.sleep(3)  # Wait for page to load

				while True:
					print('\n🔄 Extracting DOM with optimized comprehensive detection')
					print('=' * 60)

					# Extract interactive elements
					interactive_elements, serialized, selector_map = await extract_interactive_elements_from_service(dom_service)

					# Print summary
					print('\n📊 Extraction Results:')
					print(f'  - Interactive elements detected: {len(interactive_elements)}')
					print(f'  - Serialized length: {len(serialized)} characters')
					print(f'  - Selector map entries: {len(selector_map)}')

					# Show iframe and shadow DOM information
					iframe_contexts = serialized.count('=== IFRAME CONTENT')
					shadow_contexts = serialized.count('=== SHADOW DOM')
					cross_origin_iframes = serialized.count('[CROSS-ORIGIN]')

					if iframe_contexts > 0 or shadow_contexts > 0:
						print('  - 🖼️  Advanced features detected:')
						print(f'      - Iframe contexts: {iframe_contexts}')
						if cross_origin_iframes > 0:
							print(f'      - Cross-origin iframes: {cross_origin_iframes}')
						print(f'      - Shadow DOM contexts: {shadow_contexts}')

					# Show viewport info if available
					if interactive_elements:
						min_x = min(elem['x'] for elem in interactive_elements)
						max_x = max(elem['x'] + elem['width'] for elem in interactive_elements)
						min_y = min(elem['y'] for elem in interactive_elements)
						max_y = max(elem['y'] + elem['height'] for elem in interactive_elements)
						print(f'  - Element bounds: x({min_x:.0f}-{max_x:.0f}) y({min_y:.0f}-{max_y:.0f})')

					# Print sample elements
					if interactive_elements:
						print('\n🎯 Sample interactive elements:')
						for elem in interactive_elements[:5]:
							attrs_info = get_element_description(elem)
							print(f'      [{elem["interactive_index"]}] {elem["element_name"]}{attrs_info}')
						if len(interactive_elements) > 5:
							print(f'      ... and {len(interactive_elements) - 5} more')

					# Highlight elements
					await inject_highlighting_script(browser_session, interactive_elements)

					# Save outputs to files
					await save_outputs_to_files(serialized, selector_map, interactive_elements, url)

					# Print serialized output preview
					print('\n📄 Serialized output preview (first 800 chars):')
					print('-' * 60)
					print(serialized[:800])
					if len(serialized) > 800:
						print('...[TRUNCATED]')
					print('-' * 60)

					# Ask what to do next
					print('\n⚡ Next action:')
					print('  1. Extract again (test for consistency)')
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
				print(f'❌ Error during DOM extraction: {e}')
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
	print_section_header('🚀 ENHANCED DOM EXTRACTION TOOL')
	print('This tool provides enhanced DOM extraction with detailed reasoning tracking.')
	print('Features:')
	print('  • Enhanced hover tooltips showing why each element is interactive')
	print('  • Detailed logging with reasoning breakdown')
	print('  • Performance metrics and statistics')
	print('  • Structured output files for analysis')
	print('')
	print('⚠️  USAGE:')
	print('This script contains interactive input() calls.')
	print('To use it, run: python -m browser_use.dom.playground.tree')
	print('Or import the functions in your own script.')
	print('')
	print('🔧 AVAILABLE FUNCTIONS:')
	print('  • extract_interactive_elements_from_service() - Enhanced extraction with reasoning')
	print('  • inject_highlighting_script() - Enhanced tooltips with confidence indicators')
	print('  • analyze_element_interactivity() - Detailed reasoning analysis')
	print('  • save_outputs_to_files() - Save structured analysis files')
	print('')
	print('📋 COPY-PASTE READY LOGS:')
	print('All logs are structured for easy copy-paste analysis.')
	print('CDP debug logging has been disabled for cleaner output.')
	print_section_header('', char='=')

	# Don't run automatically - user mentioned input() calls
	asyncio.run(main())
