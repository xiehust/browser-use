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
from browser_use.dom.serializer import ElementAnalysis
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


async def save_comprehensive_dom_tree_json(
	dom_service: DOMService, interactive_elements: list[dict], serialized: str, selector_map: dict, url: str
) -> str | None:
	"""Save comprehensive DOM tree data to JSON with enhanced structure and metadata."""
	try:
		print_subsection('💾 SAVING COMPREHENSIVE DOM TREE JSON')

		# Create tmp directory if it doesn't exist
		tmp_dir = Path('tmp')
		tmp_dir.mkdir(exist_ok=True)

		# Clean URL for filename
		safe_url = url.replace('://', '_').replace('/', '_').replace('?', '_').replace('&', '_')[:50]
		timestamp = int(time.time())

		# Comprehensive DOM tree JSON file
		dom_tree_file = tmp_dir / f'comprehensive_dom_tree_{safe_url}_{timestamp}.json'

		# Build comprehensive DOM tree structure
		comprehensive_dom_data = {
			'metadata': {
				'url': url,
				'timestamp': timestamp,
				'extraction_method': 'enhanced_comprehensive',
				'total_elements': len(interactive_elements),
				'selector_map_size': len(selector_map),
				'serialized_length': len(serialized),
				'version': '2.0.0',
			},
			'statistics': {
				'confidence_distribution': {},
				'element_type_distribution': {},
				'score_ranges': {
					'90-100': 0,
					'80-89': 0,
					'70-79': 0,
					'60-69': 0,
					'50-59': 0,
					'40-49': 0,
					'30-39': 0,
					'20-29': 0,
					'10-19': 0,
					'0-9': 0,
				},
				'category_distribution': {},
			},
			'interactive_elements': [],
			'serialized_output': serialized,
			'advanced_features': {
				'optimized_serialization': True,
				'performance_focused': True,
			},
		}

		# Process each element and build statistics
		for elem in interactive_elements:
			reasoning = elem.get('reasoning', {})
			confidence = reasoning.get('confidence', 'MINIMAL')
			score = reasoning.get('score', 0)
			element_type = reasoning.get('element_type', 'UNKNOWN')
			category = reasoning.get('element_category', 'unknown')

			# Update statistics
			comprehensive_dom_data['statistics']['confidence_distribution'][confidence] = (
				comprehensive_dom_data['statistics']['confidence_distribution'].get(confidence, 0) + 1
			)

			comprehensive_dom_data['statistics']['element_type_distribution'][element_type] = (
				comprehensive_dom_data['statistics']['element_type_distribution'].get(element_type, 0) + 1
			)

			comprehensive_dom_data['statistics']['category_distribution'][category] = (
				comprehensive_dom_data['statistics']['category_distribution'].get(category, 0) + 1
			)

			# Score ranges
			if score >= 90:
				comprehensive_dom_data['statistics']['score_ranges']['90-100'] += 1
			elif score >= 80:
				comprehensive_dom_data['statistics']['score_ranges']['80-89'] += 1
			elif score >= 70:
				comprehensive_dom_data['statistics']['score_ranges']['70-79'] += 1
			elif score >= 60:
				comprehensive_dom_data['statistics']['score_ranges']['60-69'] += 1
			elif score >= 50:
				comprehensive_dom_data['statistics']['score_ranges']['50-59'] += 1
			elif score >= 40:
				comprehensive_dom_data['statistics']['score_ranges']['40-49'] += 1
			elif score >= 30:
				comprehensive_dom_data['statistics']['score_ranges']['30-39'] += 1
			elif score >= 20:
				comprehensive_dom_data['statistics']['score_ranges']['20-29'] += 1
			elif score >= 10:
				comprehensive_dom_data['statistics']['score_ranges']['10-19'] += 1
			else:
				comprehensive_dom_data['statistics']['score_ranges']['0-9'] += 1

			# Add element to interactive_elements array
			comprehensive_dom_data['interactive_elements'].append(
				{
					'interactive_index': elem.get('interactive_index'),
					'element_name': elem.get('element_name'),
					'position': {
						'x': elem.get('x'),
						'y': elem.get('y'),
						'width': elem.get('width'),
						'height': elem.get('height'),
					},
					'reasoning': reasoning,
					'attributes': elem.get('attributes', {}),
					'is_clickable': elem.get('is_clickable', False),
					'is_scrollable': elem.get('is_scrollable', False),
					'frame_id': elem.get('frame_id'),
				}
			)

		# Save comprehensive version
		async with aiofiles.open(dom_tree_file, 'w', encoding='utf-8') as f:
			await f.write(json.dumps(comprehensive_dom_data, indent=2, ensure_ascii=False))

		# Also save a simplified version for easier consumption
		simplified_file = tmp_dir / f'simple_dom_tree_{safe_url}_{timestamp}.json'
		simplified_data = {
			'url': url,
			'timestamp': timestamp,
			'total_elements': len(interactive_elements),
			'elements': [
				{
					'index': elem.get('interactive_index'),
					'type': elem.get('reasoning', {}).get('element_type', 'UNKNOWN'),
					'confidence': elem.get('reasoning', {}).get('confidence', 'MINIMAL'),
					'score': elem.get('reasoning', {}).get('score', 0),
					'position': {
						'x': elem.get('x'),
						'y': elem.get('y'),
						'width': elem.get('width'),
						'height': elem.get('height'),
					},
					'primary_reason': elem.get('reasoning', {}).get('primary_reason', 'unknown'),
				}
				for elem in interactive_elements
			],
		}

		async with aiofiles.open(simplified_file, 'w', encoding='utf-8') as f:
			await f.write(json.dumps(simplified_data, indent=2, ensure_ascii=False))

		# Print absolute paths for easy access
		abs_dom_tree_path = dom_tree_file.absolute()
		abs_simplified_path = simplified_file.absolute()

		print(f'📁 Comprehensive DOM tree saved to: {abs_dom_tree_path}')
		print(f'📁 Simplified DOM tree saved to: {abs_simplified_path}')

		return str(abs_dom_tree_path)

	except Exception as e:
		print(f'❌ Error saving comprehensive DOM tree JSON: {e}')
		traceback.print_exc()
		return None


async def extract_interactive_elements_from_service(
	dom_service: DOMService, score_threshold: int = 15
) -> tuple[list[dict], str, dict]:
	"""Extract interactive elements with enhanced reasoning tracking and score-based filtering."""
	try:
		print_section_header('🔄 ENHANCED DOM EXTRACTION WITH REASONING AND SCORE FILTERING')

		print('📋 Extraction Configuration:')
		print('   • Method: get_serialized_dom_tree(use_enhanced_filtering=False)')
		print('   • Focus: Comprehensive detection with optimization')
		print(f'   • Score Threshold: {score_threshold} points (elements below this will be excluded)')
		print('   • Logging: Enhanced with reasoning tracking (reduced noise)')

		# **ENHANCED: Set flag to include ALL AX elements when score threshold is 0**
		if score_threshold == 0:
			print('   🎯 SPECIAL MODE: Score threshold 0 - including ALL AX tree elements!')
			# Pass flag through the DOM service call instead of trying to set it on serializer
			print('   ✅ Will use include_all_ax_elements=True in DOM service call')
		else:
			# Make sure flag is not set for normal operation
			print('   📊 Normal filtering mode - selective element detection')

		# Use the main DOMTreeSerializer which is already highly optimized
		# Pass the flag to include all AX elements when threshold = 0
		include_all_ax = score_threshold == 0
		serialized, selector_map = await dom_service.get_serialized_dom_tree(
			use_enhanced_filtering=False, include_all_ax_elements=include_all_ax
		)

		interactive_elements = []
		reasoning_summary = {
			'DEFINITE_confidence': 0,
			'LIKELY_confidence': 0,
			'POSSIBLE_confidence': 0,
			'QUESTIONABLE_confidence': 0,
			'MINIMAL_confidence': 0,
			'by_type': {},
			'by_reason': {},
		}

		print_subsection('🎯 INTERACTIVE ELEMENT ANALYSIS WITH SCORE FILTERING')

		# Extract bounding boxes for elements that have interactive indices
		total_processed = 0
		filtered_count = 0

		# Build a filtered selector map based on score threshold
		filtered_selector_map = {}

		for interactive_index, node in selector_map.items():
			total_processed += 1

			# **ENHANCED: For score threshold = 0, include ALL elements even without bounding boxes**
			if score_threshold == 0:
				# Include ALL elements when threshold=0, create fake bounding box if needed
				if node.snapshot_node and hasattr(node.snapshot_node, 'bounding_box') and node.snapshot_node.bounding_box:
					bbox = node.snapshot_node.bounding_box
					if bbox.get('width', 0) <= 0 or bbox.get('height', 0) <= 0:
						# Create fake bounding box for elements without valid dimensions
						bbox = {'x': 0, 'y': 0, 'width': 10, 'height': 10}
				else:
					# Create fake bounding box for elements without snapshot or bounding box
					bbox = {'x': 0, 'y': 0, 'width': 10, 'height': 10}
			else:
				# **NORMAL MODE: Only include elements with valid bounding boxes**
				if not (node.snapshot_node and hasattr(node.snapshot_node, 'bounding_box') and node.snapshot_node.bounding_box):
					continue
				bbox = node.snapshot_node.bounding_box
				# Only include elements with valid bounding boxes
				if bbox.get('width', 0) <= 0 or bbox.get('height', 0) <= 0:
					continue

			# Use ElementAnalysis from serializer for enhanced element analysis
			reasoning = ElementAnalysis.analyze_element_interactivity(node)

			# Apply score threshold filter (bypass for threshold=0 to include ALL AX elements)
			if score_threshold == 0 or reasoning.score >= score_threshold:
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

				# Convert ElementAnalysis to dict format - with JSON safety
				def make_json_safe(obj):
					"""Recursively ensure all values are JSON serializable."""
					if obj is None:
						return None
					elif isinstance(obj, (str, int, float, bool)):
						return obj
					elif isinstance(obj, list):
						return [make_json_safe(item) for item in obj]
					elif isinstance(obj, dict):
						return {str(k): make_json_safe(v) for k, v in obj.items()}
					else:
						# Convert any other type to string
						return str(obj)

				reasoning_dict = {
					'primary_reason': str(reasoning.primary_reason),
					'confidence': str(reasoning.confidence),
					'confidence_description': str(reasoning.confidence_description),
					'score': int(reasoning.score),
					'element_type': str(reasoning.element_type),
					'element_category': str(reasoning.element_category),
					'evidence': [str(e) for e in reasoning.evidence],
					'warnings': [str(w) for w in reasoning.warnings],
					'context_info': [str(c) for c in reasoning.context_info],
					'interactive_indicators': make_json_safe(reasoning.interactive_indicators),
					'event_listeners': [str(e) for e in reasoning.event_listeners],
					'computed_styles_info': make_json_safe(reasoning.computed_styles_info),
					'accessibility_info': make_json_safe(reasoning.accessibility_info),
					'positioning_info': make_json_safe(reasoning.positioning_info),
					'has_attributes': bool(len(node.attributes or {}) > 0),
					'attribute_count': int(len(node.attributes or {})),
					'all_attributes': make_json_safe(node.attributes or {}),
				}

				element['reasoning'] = reasoning_dict
				interactive_elements.append(element)

				# Keep this element in the filtered selector map
				filtered_selector_map[interactive_index] = node

				# Update statistics
				confidence = reasoning.confidence
				reasoning_summary[f'{confidence}_confidence'] += 1

				element_type = reasoning.element_type
				reasoning_summary['by_type'][element_type] = reasoning_summary['by_type'].get(element_type, 0) + 1

				primary_reason = reasoning.primary_reason
				reasoning_summary['by_reason'][primary_reason] = reasoning_summary['by_reason'].get(primary_reason, 0) + 1
			else:
				filtered_count += 1

		# Now regenerate the serialized string using only the filtered elements
		print(f'🎯 Regenerating serialized output with {len(filtered_selector_map)} filtered elements...')

		# Use the DOM service to regenerate serialized output with filtered selector map
		try:
			# Create a filtered version of the serialized output
			# We'll manually rebuild the serialized string using only the filtered elements
			filtered_serialized = await regenerate_serialized_with_threshold(dom_service, filtered_selector_map, score_threshold)

		except Exception as e:
			print(f'⚠️ Could not regenerate filtered serialized output: {e}')
			print('Using original serialized output (all elements)')
			filtered_serialized = serialized

		# Print detailed statistics
		print('📊 SCORE-FILTERED EXTRACTION RESULTS:')
		print(f'   • Total processed: {total_processed}')
		print(f'   • Score threshold: {score_threshold} points')
		print(f'   • Elements above threshold: {len(interactive_elements)}')
		print(f'   • Elements filtered out: {filtered_count}')
		print(f'   • Inclusion rate: {(len(interactive_elements) / max(total_processed, 1) * 100):.1f}%')
		print(f'   • Filtered serialized content length: {len(filtered_serialized):,} characters')
		print(f'   • Filtered selector map entries: {len(filtered_selector_map)}')

		print('\n🎯 CONFIDENCE BREAKDOWN (filtered results):')
		print(f'   • DEFINITE confidence: {reasoning_summary["DEFINITE_confidence"]} elements')
		print(f'   • LIKELY confidence: {reasoning_summary["LIKELY_confidence"]} elements')
		print(f'   • POSSIBLE confidence: {reasoning_summary["POSSIBLE_confidence"]} elements')
		print(f'   • QUESTIONABLE confidence: {reasoning_summary["QUESTIONABLE_confidence"]} elements')
		print(f'   • MINIMAL confidence: {reasoning_summary["MINIMAL_confidence"]} elements')

		print('\n📋 ELEMENT TYPE BREAKDOWN (filtered results):')
		for element_type, count in sorted(reasoning_summary['by_type'].items(), key=lambda x: x[1], reverse=True):
			print(f'   • {element_type}: {count}')

		print('\n🔍 REASONING BREAKDOWN (filtered results):')
		for reason, count in sorted(reasoning_summary['by_reason'].items(), key=lambda x: x[1], reverse=True):
			print(f'   • {reason}: {count}')

		# Performance-focused serialization - no iframe/shadow DOM processing for better speed
		print('\n🚀 PERFORMANCE OPTIMIZATIONS:')
		print('   • Fast AX tree processing')
		print('   • Viewport-based filtering')
		print('   • Score-based threshold filtering')
		print('   • Comprehensive cursor detection')
		print('   • No CDP errors from iframe/shadow DOM processing')

		# Show sample of each confidence level
		print('\n🎯 SAMPLE ELEMENTS BY CONFIDENCE (score-filtered):')
		confidence_levels = ['DEFINITE', 'LIKELY', 'POSSIBLE', 'QUESTIONABLE', 'MINIMAL']
		for confidence in confidence_levels:
			conf_elements = [e for e in interactive_elements if e['reasoning']['confidence'] == confidence]
			if conf_elements:
				emoji = {'DEFINITE': '🟢', 'LIKELY': '🟡', 'POSSIBLE': '🟠', 'QUESTIONABLE': '🔴', 'MINIMAL': '🟣'}[confidence]
				print(f'\n   {emoji} {confidence} ({len(conf_elements)} total):')
				for elem in conf_elements[:3]:  # Show first 3
					attrs = elem.get('attributes', {})
					key_info = []
					if attrs.get('id'):
						key_info.append(f"id='{attrs['id'][:20]}{'...' if len(attrs['id']) > 20 else ''}'")
					if attrs.get('class'):
						key_info.append(f"class='{attrs['class'][:30]}{'...' if len(attrs['class']) > 30 else ''}'")
					key_str = f' ({", ".join(key_info)})' if key_info else ''
					print(
						f'      [{elem["interactive_index"]}] {elem["reasoning"]["element_type"]}{key_str} - {elem["reasoning"]["score"]} pts'
					)
				if len(conf_elements) > 3:
					print(f'      ... and {len(conf_elements) - 3} more')

		return interactive_elements, filtered_serialized, filtered_selector_map

	except Exception as e:
		print_section_header('❌ EXTRACTION ERROR', char='!')
		print(f'Error: {str(e)}')
		print(f'Type: {type(e).__name__}')
		print('Traceback:')
		traceback.print_exc()
		return [], '', {}


async def regenerate_serialized_with_threshold(dom_service: DOMService, filtered_selector_map: dict, score_threshold: int) -> str:
	"""Regenerate serialized DOM output using only elements above the score threshold."""
	try:
		print(f'🔄 Regenerating serialized output with score threshold {score_threshold}...')

		# We need to create a new serialized representation using only the filtered elements
		# This is a simplified approach - we'll build the string manually from the filtered elements

		# Group elements by type for better organization
		grouped_elements = {}

		for idx, node in filtered_selector_map.items():
			# Analyze the element again to get its reasoning
			from browser_use.dom.serializer import ElementAnalysis

			reasoning = ElementAnalysis.analyze_element_interactivity(node)

			element_type = reasoning.element_type
			confidence = reasoning.confidence
			score = reasoning.score

			# Create clean categories without technical confidence levels
			if element_type in ['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA']:
				category = 'FORM ELEMENTS'
			elif element_type in ['A']:
				category = 'NAVIGATION'
			else:
				category = 'INTERACTIVE CONTENT'

			if category not in grouped_elements:
				grouped_elements[category] = []

				# Create clean element description with comprehensive text extraction
			attrs = node.attributes or {}

			# Determine clean element type
			if element_type == 'BUTTON':
				clean_type = 'Button'
			elif element_type == 'A':
				clean_type = 'Link'
			elif element_type in ['INPUT', 'TEXTAREA']:
				clean_type = 'Input'
			elif element_type == 'SELECT':
				clean_type = 'Dropdown'
			else:
				clean_type = element_type.title()

			element_desc = f'[{idx}] {clean_type}'

			# EXTRACT TEXT CONTENT USING PROPER DOM NODE METHODS
			meaningful_text = ''

			# Method 1: Try visible text from children (most comprehensive)
			if hasattr(node, 'children_nodes') and node.children_nodes:
				text_parts = []
				for child in node.children_nodes:
					if hasattr(child, 'node_value') and child.node_value:
						child_text = child.node_value.strip()
						if child_text and len(child_text) > 1:
							text_parts.append(child_text)
				if text_parts:
					combined_text = ' '.join(text_parts).strip()
					# Clean up whitespace
					import re

					meaningful_text = re.sub(r'\s+', ' ', combined_text)[:80]

			# Method 2: Try AX node text (accessibility tree)
			if not meaningful_text and hasattr(node, 'ax_node') and node.ax_node:
				if hasattr(node.ax_node, 'name') and node.ax_node.name:
					meaningful_text = node.ax_node.name.strip()[:80]

			# Method 3: Try snapshot node text content
			if not meaningful_text and hasattr(node, 'snapshot_node') and node.snapshot_node:
				snapshot = node.snapshot_node
				for text_attr in ['text_content', 'inner_text']:
					if hasattr(snapshot, text_attr):
						text_val = getattr(snapshot, text_attr)
						if text_val and len(text_val.strip()) > 1:
							meaningful_text = text_val.strip()[:80]
							break

			# Method 4: Extract from attributes with priority
			if not meaningful_text:
				# Priority order for attribute text extraction
				text_attrs = [
					('aria-label', ''),
					('title', 'title: '),
					('placeholder', 'placeholder: '),
					('value', ''),
					('alt', 'alt: '),
				]

				for attr_name, prefix in text_attrs:
					if attrs.get(attr_name):
						attr_text = attrs[attr_name].strip()
						if attr_text and len(attr_text) > 1:
							meaningful_text = f'{prefix}{attr_text}'[:80]
							break

			# Add the meaningful text if we found any
			if meaningful_text:
				element_desc += f' "{meaningful_text}"'

			# Add href information for links
			if element_type == 'A' and attrs.get('href'):
				href = attrs['href']
				if href.startswith('#'):
					element_desc += f' (jumps to: {href[1:20]})'
				elif href.startswith('mailto:'):
					element_desc += f' (email: {href[7:30]})'
				elif href.startswith('tel:'):
					element_desc += f' (phone: {href[4:20]})'
				elif len(href) > 1 and not href.startswith('javascript:'):
					if len(href) > 40:
						element_desc += f' (goes to: {href[:40]}...)'
					else:
						element_desc += f' (goes to: {href})'

			# Add role information if available and meaningful
			if attrs.get('role'):
				role = attrs['role'].strip()
				if role and role not in ['generic', 'presentation']:
					element_desc += f' role: {role}'

			# 9. State information for form elements
			state_info = []
			if 'checked' in attrs:
				state_info.append('checked')
			if 'disabled' in attrs:
				state_info.append('disabled')
			if 'required' in attrs:
				state_info.append('required')
			if 'selected' in attrs:
				state_info.append('selected')
			if 'readonly' in attrs:
				state_info.append('readonly')

			if state_info:
				element_desc += f' ({", ".join(state_info)})'

			grouped_elements[category].append(element_desc)

		# Build the clean serialized string
		serialized_parts = []

		for category, elements in grouped_elements.items():
			if elements:
				serialized_parts.append(f'{category}:')
				for element in elements:
					serialized_parts.append(f'  {element}')
				serialized_parts.append('')  # Empty line between categories

		# Remove trailing empty line
		if serialized_parts and serialized_parts[-1] == '':
			serialized_parts.pop()

		filtered_serialized = '\n'.join(serialized_parts)

		print(f'✅ Generated filtered serialized output: {len(filtered_serialized)} characters')
		print(f'📊 Categories: {len(grouped_elements)}, Total elements: {len(filtered_selector_map)}')

		return filtered_serialized

	except Exception as e:
		print(f'❌ Error regenerating serialized output: {e}')
		# Fallback to simple representation
		fallback = f'FILTERED ELEMENTS ({len(filtered_selector_map)}): ' + ', '.join(
			[f'[{idx}] {node.node_name}' for idx, node in list(filtered_selector_map.items())[:10]]
		)
		if len(filtered_selector_map) > 10:
			fallback += f' ... and {len(filtered_selector_map) - 10} more'
		return fallback


async def inject_highlighting_script(browser_session: BrowserSession, interactive_elements: list[dict]) -> None:
	"""Inject JavaScript to highlight interactive elements with sophisticated interactive debugging UI."""
	if not interactive_elements:
		print('⚠️ No interactive elements to highlight')
		return

	try:
		# Get the current page from the browser session
		page = await browser_session.get_current_page()

		print(f'📍 Creating sophisticated interactive debugging UI for {len(interactive_elements)} elements')

		# Create enhanced debugging script with interactive controls
		elements_json = json.dumps(interactive_elements)

		script = (
			"""
		(function() {
			// Remove any existing highlights
			const existingHighlights = document.querySelectorAll('[data-browser-use-highlight]');
			existingHighlights.forEach(el => el.remove());
			
			// Interactive elements data
			const interactiveElements = """
			+ elements_json
			+ """;
			
			console.log('=== BROWSER-USE INTERACTIVE DEBUGGING UI ===');
			console.log('Interactive elements:', interactiveElements.length);
			
			// Test websites for cycling - expanded list for better testing (DEFINED FIRST)
			const testWebsites = [
				{ name: 'Example.com', url: 'https://example.com' },
				{ name: 'Browser Use', url: 'https://browser-use.com' },
				{ name: 'GitHub', url: 'https://github.com' },
				{ name: 'Semantic UI', url: 'https://semantic-ui.com/modules/dropdown.html' },
				{ name: 'Google Flights', url: 'https://www.google.com/travel/flights' },
				{ name: 'Wikipedia', url: 'https://en.wikipedia.org/wiki/Internet' },
				{ name: 'Stack Overflow', url: 'https://stackoverflow.com' },
				{ name: 'Reddit', url: 'https://reddit.com' },
				{ name: 'YouTube', url: 'https://youtube.com' },
				{ name: 'Amazon', url: 'https://amazon.com' }
			];
			
			// Global state
			let state = {
				highlightsVisible: true,
				currentFilter: 'ALL',
				showSerializedData: false,
				showElementList: false,
				currentWebsiteIndex: 0,
				autoRefresh: false,
				scoreThreshold: 15  // Default minimum score threshold
			};
			
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
			function createTextElement(tag, text, styles) {
				const element = document.createElement(tag);
				element.textContent = text;
				if (styles) element.style.cssText = styles;
				return element;
			}
			
			// Create sophisticated debugging panel
			const debugPanel = document.createElement('div');
			debugPanel.setAttribute('data-browser-use-highlight', 'debug-panel');
			debugPanel.style.cssText = `
				position: fixed;
				top: 10px;
				right: 10px;
				background: linear-gradient(145deg, rgba(0, 0, 0, 0.95), rgba(20, 20, 20, 0.95));
				color: white;
				padding: 20px;
				border-radius: 15px;
				font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
				font-size: 12px;
				z-index: 1000010;
				box-shadow: 0 10px 40px rgba(0,0,0,0.8);
				border: 2px solid #4a90e2;
				backdrop-filter: blur(15px);
				min-width: 350px;
				max-width: 450px;
				max-height: 80vh;
				overflow-y: auto;
				pointer-events: auto;
				transition: all 0.3s ease;
			`;
			
			// Create panel content
			const panelContent = document.createElement('div');
			
			// Header with title and minimize button
			const header = document.createElement('div');
			header.style.cssText = 'display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;';
			
			const title = createTextElement('div', '🔍 Interactive Debug Console', 'color: #4a90e2; font-weight: bold; font-size: 14px;');
			
			const minimizeBtn = createTextElement('button', '−', `
				background: #4a90e2; color: white; border: none; border-radius: 50%;
				width: 25px; height: 25px; font-size: 16px; cursor: pointer;
				transition: all 0.2s ease;
			`);
			minimizeBtn.addEventListener('click', () => {
				const isMinimized = debugPanel.style.maxHeight === '50px';
				debugPanel.style.maxHeight = isMinimized ? '80vh' : '50px';
				debugPanel.style.overflow = isMinimized ? 'auto' : 'hidden';
				minimizeBtn.textContent = isMinimized ? '−' : '+';
			});
			
			header.appendChild(title);
			header.appendChild(minimizeBtn);
			panelContent.appendChild(header);
			
			// Statistics section
			const statsSection = document.createElement('div');
			statsSection.style.cssText = 'margin-bottom: 15px; padding: 10px; background: rgba(255,255,255,0.1); border-radius: 8px;';
			
			const stats = { definite: 0, likely: 0, possible: 0, questionable: 0, minimal: 0 };
			interactiveElements.forEach(el => {
				const confidence = el.reasoning ? el.reasoning.confidence : 'MINIMAL';
				if (confidence === 'DEFINITE') stats.definite++;
				else if (confidence === 'LIKELY') stats.likely++;
				else if (confidence === 'POSSIBLE') stats.possible++;
				else if (confidence === 'QUESTIONABLE') stats.questionable++;
				else stats.minimal++;
			});
			
			// Build stats section safely
			const statsTitle = document.createElement('div');
			statsTitle.style.cssText = 'color: #4a90e2; font-weight: bold; margin-bottom: 8px;';
			statsTitle.textContent = '📊 Element Statistics';
			statsSection.appendChild(statsTitle);
			
			const statsContent = document.createElement('div');
			statsContent.style.cssText = 'font-size: 11px; line-height: 1.4;';
			
			// Create individual stat lines
			const statLines = [
				`🟢 DEFINITE: ${stats.definite} (${(stats.definite/interactiveElements.length*100).toFixed(1)}%)`,
				`🟡 LIKELY: ${stats.likely} (${(stats.likely/interactiveElements.length*100).toFixed(1)}%)`,
				`🟠 POSSIBLE: ${stats.possible} (${(stats.possible/interactiveElements.length*100).toFixed(1)}%)`,
				`🔴 QUESTIONABLE: ${stats.questionable} (${(stats.questionable/interactiveElements.length*100).toFixed(1)}%)`,
				`🟣 MINIMAL: ${stats.minimal} (${(stats.minimal/interactiveElements.length*100).toFixed(1)}%)`,
				`Total: ${interactiveElements.length} elements`
			];
			
			statLines.forEach((line, index) => {
				const lineDiv = document.createElement('div');
				if (index === statLines.length - 1) {
					lineDiv.style.cssText = 'margin-top: 5px; font-weight: bold;';
				}
				lineDiv.textContent = line;
				statsContent.appendChild(lineDiv);
			});
			
			statsSection.appendChild(statsContent);
			panelContent.appendChild(statsSection);
			
			// Control buttons section
			const controlsSection = document.createElement('div');
			controlsSection.style.cssText = 'margin-bottom: 15px;';
			
			const controlsTitle = createTextElement('div', '🎮 Interactive Controls', 'color: #4a90e2; font-weight: bold; margin-bottom: 8px;');
			controlsSection.appendChild(controlsTitle);
			
			// Create button helper
			function createButton(text, onClick, color = '#4a90e2') {
				const btn = createTextElement('button', text, `
					background: ${color}; color: white; border: none; border-radius: 6px;
					padding: 6px 12px; margin: 2px; font-size: 10px; cursor: pointer;
					transition: all 0.2s ease; font-family: inherit;
				`);
				btn.addEventListener('mouseenter', () => btn.style.backgroundColor = '#2980b9');
				btn.addEventListener('mouseleave', () => btn.style.backgroundColor = color);
				btn.addEventListener('click', onClick);
				return btn;
			}
			
			// Row 1: Core controls
			const row1 = document.createElement('div');
			row1.style.cssText = 'margin-bottom: 8px;';
			
			const refreshBtn = createButton('🔄 Refresh', () => {
				location.reload();
			}, '#28a745');
			
			const toggleBtn = createButton('👁️ Toggle', () => {
				state.highlightsVisible = !state.highlightsVisible;
				container.style.display = state.highlightsVisible ? 'block' : 'none';
				toggleBtn.textContent = state.highlightsVisible ? '👁️ Hide' : '👁️ Show';
			});
			
			const exportBtn = createButton('💾 Export', () => {
				const data = {
					url: window.location.href,
					timestamp: new Date().toISOString(),
					elementCount: interactiveElements.length,
					statistics: stats,
					elements: interactiveElements.map(el => ({
						index: el.interactive_index,
						type: el.reasoning?.element_type,
						confidence: el.reasoning?.confidence,
						score: el.reasoning?.score,
						position: { x: el.x, y: el.y, width: el.width, height: el.height }
					}))
				};
				const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
				const url = URL.createObjectURL(blob);
				const a = document.createElement('a');
				a.href = url;
				a.download = `browser-use-analysis-${Date.now()}.json`;
				a.click();
				URL.revokeObjectURL(url);
			}, '#17a2b8');
			
			row1.appendChild(refreshBtn);
			row1.appendChild(toggleBtn);
			row1.appendChild(exportBtn);
			controlsSection.appendChild(row1);
			
			// Row 2: Website navigation
			const row2 = document.createElement('div');
			row2.style.cssText = 'margin-bottom: 8px;';
			
			const prevSiteBtn = createButton('⬅️ Prev', () => {
				state.currentWebsiteIndex = (state.currentWebsiteIndex - 1 + testWebsites.length) % testWebsites.length;
				const site = testWebsites[state.currentWebsiteIndex];
				if (confirm(`Navigate to ${site.name}?`)) {
					window.location.href = site.url;
				}
			}, '#6f42c1');
			
			const nextSiteBtn = createButton('Next ➡️', () => {
				state.currentWebsiteIndex = (state.currentWebsiteIndex + 1) % testWebsites.length;
				const site = testWebsites[state.currentWebsiteIndex];
				if (confirm(`Navigate to ${site.name}?`)) {
					window.location.href = site.url;
				}
			}, '#6f42c1');
			
			// NEW: Auto Next button for quick testing
			const autoNextBtn = createButton('🚀 Auto Next', () => {
				state.currentWebsiteIndex = (state.currentWebsiteIndex + 1) % testWebsites.length;
				const site = testWebsites[state.currentWebsiteIndex];
				
				// Show immediate feedback
				const feedback = document.createElement('div');
				feedback.style.cssText = `
					position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
					background: linear-gradient(45deg, #28a745, #20c997); color: white;
					padding: 20px 30px; border-radius: 15px; font-family: monospace;
					z-index: 1000025; font-size: 16px; text-align: center;
					box-shadow: 0 10px 30px rgba(0,0,0,0.5); animation: pulse 1s ease-in-out;
				`;
				// Build feedback content safely
				const feedbackText1 = document.createTextNode('🚀 Auto-navigating to ');
				feedback.appendChild(feedbackText1);
				
				const siteName = document.createElement('strong');
				siteName.textContent = site.name;
				feedback.appendChild(siteName);
				
				feedback.appendChild(document.createElement('br'));
				
				const siteUrl = document.createElement('small');
				siteUrl.style.cssText = 'opacity: 0.8;';
				siteUrl.textContent = site.url;
				feedback.appendChild(siteUrl);
				
				feedback.appendChild(document.createElement('br'));
				
				const progressDiv = document.createElement('div');
				progressDiv.style.cssText = 'margin-top: 10px; font-size: 12px;';
				progressDiv.textContent = `Site ${state.currentWebsiteIndex + 1} of ${testWebsites.length} • Auto-highlighting will start...`;
				feedback.appendChild(progressDiv);
				document.body.appendChild(feedback);
				
				// Navigate after brief delay
				setTimeout(() => {
					window.location.href = site.url;
				}, 1500);
				
				console.log(`🚀 AUTO-NAVIGATING: ${state.currentWebsiteIndex + 1}/${testWebsites.length} - ${site.name}`);
				console.log(`📍 URL: ${site.url}`);
			}, '#28a745');
			autoNextBtn.title = 'Automatically go to next website and re-highlight';
			
			const randomSiteBtn = createButton('🎲 Random', () => {
				state.currentWebsiteIndex = Math.floor(Math.random() * testWebsites.length);
				const site = testWebsites[state.currentWebsiteIndex];
				if (confirm(`Navigate to ${site.name}?`)) {
					window.location.href = site.url;
				}
			}, '#e83e8c');
			
			row2.appendChild(autoNextBtn);
			row2.appendChild(nextSiteBtn);
			row2.appendChild(prevSiteBtn);
			row2.appendChild(randomSiteBtn);
			controlsSection.appendChild(row2);
			
			// Row 3: Data viewing
			const row3 = document.createElement('div');
			row3.style.cssText = 'margin-bottom: 8px;';
			
			const serializedBtn = createButton('📄 Serialized', () => {
				state.showSerializedData = !state.showSerializedData;
				updateDataView();
			}, '#fd7e14');
			
			const elementsBtn = createButton('📋 Elements', () => {
				state.showElementList = !state.showElementList;
				updateElementList();
			}, '#20c997');
			
			const filterBtn = createButton('🔍 Filter', () => {
				const filters = ['ALL', 'DEFINITE', 'LIKELY', 'POSSIBLE', 'QUESTIONABLE', 'MINIMAL'];
				const currentIndex = filters.indexOf(state.currentFilter);
				state.currentFilter = filters[(currentIndex + 1) % filters.length];
				filterBtn.textContent = `🔍 ${state.currentFilter}`;
				applyFilter();
			}, '#ffc107');
			
			row3.appendChild(serializedBtn);
			row3.appendChild(elementsBtn);
			row3.appendChild(filterBtn);
			controlsSection.appendChild(row3);
			
			panelContent.appendChild(controlsSection);
			
			// Score threshold slider section
			const scoreSection = document.createElement('div');
			scoreSection.style.cssText = 'margin-bottom: 15px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px;';
			
			const scoreTitle = document.createElement('div');
			scoreTitle.style.cssText = 'color: #4a90e2; font-weight: bold; margin-bottom: 8px;';
			scoreTitle.textContent = '🎯 Score Threshold Filter';
			scoreSection.appendChild(scoreTitle);
			
			// Score info display
			const scoreInfo = document.createElement('div');
			scoreInfo.style.cssText = 'font-size: 10px; margin-bottom: 8px; color: #ccc;';
			scoreInfo.id = 'score-info';
			scoreSection.appendChild(scoreInfo);
			
			// Score slider
			const scoreSlider = document.createElement('input');
			scoreSlider.type = 'range';
			scoreSlider.min = '0';
			scoreSlider.max = '100';
			scoreSlider.value = state.scoreThreshold.toString();
			scoreSlider.style.cssText = `
				width: 100%; margin: 5px 0; height: 6px; border-radius: 3px;
				background: linear-gradient(90deg, #dc3545 0%, #ffc107 25%, #28a745 75%, #007bff 100%);
				outline: none; -webkit-appearance: none;
			`;
			
			// Score slider styling
			const sliderStyle = document.createElement('style');
			sliderStyle.textContent = `
				input[type="range"]::-webkit-slider-thumb {
					-webkit-appearance: none; appearance: none;
					width: 16px; height: 16px; border-radius: 50%;
					background: #4a90e2; cursor: pointer;
					box-shadow: 0 2px 6px rgba(0,0,0,0.3);
				}
				input[type="range"]::-moz-range-thumb {
					width: 16px; height: 16px; border-radius: 50%;
					background: #4a90e2; cursor: pointer; border: none;
					box-shadow: 0 2px 6px rgba(0,0,0,0.3);
				}
			`;
			document.head.appendChild(sliderStyle);
			
			// Score value display
			const scoreValue = document.createElement('div');
			scoreValue.style.cssText = 'text-align: center; font-size: 12px; font-weight: bold; margin-top: 5px;';
			scoreValue.id = 'score-value';
			scoreSection.appendChild(scoreValue);
			
			// Function to update score display and filter
			function updateScoreThreshold() {
				const threshold = parseInt(scoreSlider.value);
				state.scoreThreshold = threshold;
				
				// Update displays
				scoreValue.textContent = `Min Score: ${threshold} points`;
				
				// Count elements at current threshold
				const visibleCount = applyScoreThreshold();
				const totalCount = interactiveElements.length;
				const percentage = totalCount > 0 ? ((visibleCount / totalCount) * 100).toFixed(1) : '0';
				
				scoreInfo.textContent = `Showing ${visibleCount} of ${totalCount} elements (${percentage}%)`;
				
				// Update element list if open
				if (state.showElementList) {
					updateElementList();
				}
				
				console.log(`🎯 Score threshold updated: ${threshold} (showing ${visibleCount}/${totalCount} elements)`);
			}
			
			// Function to apply score threshold filter
			function applyScoreThreshold() {
				const highlights = container.querySelectorAll('[data-browser-use-highlight="element"]');
				let visibleCount = 0;
				
				highlights.forEach(highlight => {
					const elementId = highlight.getAttribute('data-element-id');
					const element = interactiveElements.find(el => el.interactive_index == elementId);
					const score = element?.reasoning?.score || 0;
					
					if (score >= state.scoreThreshold) {
						highlight.style.display = 'block';
						visibleCount++;
					} else {
						highlight.style.display = 'none';
					}
				});
				
				return visibleCount;
			}
			
			// Add slider event listener
			scoreSlider.addEventListener('input', updateScoreThreshold);
			
			// Add slider and value to section
			scoreSection.appendChild(scoreSlider);
			scoreSection.appendChild(scoreValue);
			
			// Initialize score display
			updateScoreThreshold();
			
			panelContent.appendChild(scoreSection);
			
			// Selected element details section
			const selectedElementSection = document.createElement('div');
			selectedElementSection.id = 'selected-element-details';
			selectedElementSection.style.cssText = 'margin-bottom: 15px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px; display: none;';
			
			const selectedElementTitle = document.createElement('div');
			selectedElementTitle.style.cssText = 'color: #4a90e2; font-weight: bold; margin-bottom: 8px; font-size: 11px;';
			selectedElementTitle.textContent = '🎯 Selected Element Details';
			selectedElementSection.appendChild(selectedElementTitle);
			
			const selectedElementContent = document.createElement('div');
			selectedElementContent.id = 'selected-element-content';
			selectedElementContent.style.cssText = 'max-height: 200px; overflow-y: auto; font-size: 10px; line-height: 1.4;';
			selectedElementSection.appendChild(selectedElementContent);
			
			panelContent.appendChild(selectedElementSection);
			
			// Data view section
			const dataView = document.createElement('div');
			dataView.id = 'data-view';
			dataView.style.cssText = 'margin-bottom: 15px; display: none;';
			panelContent.appendChild(dataView);
			
			// Element list section
			const elementList = document.createElement('div');
			elementList.id = 'element-list';
			elementList.style.cssText = 'margin-bottom: 15px; display: none;';
			panelContent.appendChild(elementList);
			
			// Quick search
			const searchSection = document.createElement('div');
			searchSection.style.cssText = 'margin-bottom: 15px;';
			
			const searchTitle = createTextElement('div', '🔍 Quick Search', 'color: #4a90e2; font-weight: bold; margin-bottom: 8px;');
			searchSection.appendChild(searchTitle);
			
			const searchInput = document.createElement('input');
			searchInput.type = 'text';
			searchInput.placeholder = 'Search elements...';
			searchInput.style.cssText = `
				width: 100%; padding: 6px; border: 1px solid #4a90e2; border-radius: 4px;
				background: rgba(255,255,255,0.1); color: white; font-size: 11px;
			`;
			searchInput.addEventListener('input', (e) => {
				const query = e.target.value.toLowerCase();
				applySearch(query);
			});
			searchSection.appendChild(searchInput);
			panelContent.appendChild(searchSection);
			
			// Performance metrics
			const perfSection = document.createElement('div');
			perfSection.style.cssText = 'margin-bottom: 15px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px;';
			
			const perfTitle = createTextElement('div', '⚡ Performance', 'color: #4a90e2; font-weight: bold; margin-bottom: 8px;');
			perfSection.appendChild(perfTitle);
			
			const perfContent = document.createElement('div');
			perfContent.style.cssText = 'font-size: 10px; line-height: 1.4;';
			// Build performance content safely
			const perfLines = [
				`🎯 Detection Rate: ${((stats.definite + stats.likely)/interactiveElements.length*100).toFixed(1)}%`,
				`📊 Confidence Score: ${(stats.definite*5 + stats.likely*4 + stats.possible*3 + stats.questionable*2 + stats.minimal*1)/interactiveElements.length/5*100}%`,
				`🔄 Load Time: ${performance.now().toFixed(0)}ms`,
				`💾 Memory: ~${(JSON.stringify(interactiveElements).length/1024).toFixed(1)}KB`
			];
			
			perfLines.forEach(line => {
				const lineDiv = document.createElement('div');
				lineDiv.textContent = line;
				perfContent.appendChild(lineDiv);
			});
			perfSection.appendChild(perfContent);
			panelContent.appendChild(perfSection);
			
			debugPanel.appendChild(panelContent);
			
			// Update functions
			function updateDataView() {
				if (state.showSerializedData) {
					dataView.style.display = 'block';
					
					// Clear existing content safely
					while (dataView.firstChild) {
						dataView.removeChild(dataView.firstChild);
					}
					
					// Build data view safely
					const dataTitle = document.createElement('div');
					dataTitle.style.cssText = 'color: #4a90e2; font-weight: bold; margin-bottom: 8px;';
					dataTitle.textContent = '📄 Serialized Data Preview';
					dataView.appendChild(dataTitle);
					
					const dataContent = document.createElement('div');
					dataContent.style.cssText = 'background: rgba(0,0,0,0.3); padding: 8px; border-radius: 4px; font-size: 9px; max-height: 200px; overflow-y: auto;';
					
					// Add basic info
					const infoLines = [
						`URL: ${window.location.href}`,
						`Timestamp: ${new Date().toLocaleString()}`,
						`Elements: ${interactiveElements.length}`
					];
					
					infoLines.forEach(line => {
						const lineDiv = document.createElement('div');
						lineDiv.textContent = line;
						dataContent.appendChild(lineDiv);
					});
					
					// Add separator
					const hr = document.createElement('hr');
					hr.style.cssText = 'border: 1px solid #333; margin: 8px 0;';
					dataContent.appendChild(hr);
					
					// Add element list
					interactiveElements.slice(0, 10).forEach(el => {
						const elementDiv = document.createElement('div');
						elementDiv.textContent = `[${el.interactive_index}] ${el.reasoning?.element_type || 'UNKNOWN'} (${el.reasoning?.score || 0}pts)`;
						dataContent.appendChild(elementDiv);
					});
					
					// Add "more" indicator if needed
					if (interactiveElements.length > 10) {
						const moreDiv = document.createElement('div');
						moreDiv.textContent = `... and ${interactiveElements.length - 10} more`;
						dataContent.appendChild(moreDiv);
					}
					
					dataView.appendChild(dataContent);
				} else {
					dataView.style.display = 'none';
				}
			}
			
			function updateElementList() {
				if (state.showElementList) {
					elementList.style.display = 'block';
					const filteredElements = interactiveElements.filter(el => {
						const confidence = el.reasoning?.confidence || 'MINIMAL';
						const score = el.reasoning?.score || 0;
						const passesConfidenceFilter = state.currentFilter === 'ALL' || confidence === state.currentFilter;
						const passesScoreThreshold = score >= state.scoreThreshold;
						return passesConfidenceFilter && passesScoreThreshold;
					});
					
					// Clear existing content safely
					while (elementList.firstChild) {
						elementList.removeChild(elementList.firstChild);
					}
					
					// Build element list safely
					const listTitle = document.createElement('div');
					listTitle.style.cssText = 'color: #4a90e2; font-weight: bold; margin-bottom: 8px;';
					listTitle.textContent = `📋 Element List (${filteredElements.length})`;
					elementList.appendChild(listTitle);
					
					const listContent = document.createElement('div');
					listContent.style.cssText = 'background: rgba(0,0,0,0.3); padding: 8px; border-radius: 4px; font-size: 9px; max-height: 200px; overflow-y: auto;';
					
					// Add each element
					filteredElements.forEach(el => {
						const conf = el.reasoning?.confidence || 'MINIMAL';
						const emoji = {'DEFINITE': '🟢', 'LIKELY': '🟡', 'POSSIBLE': '🟠', 'QUESTIONABLE': '🔴', 'MINIMAL': '🟣'}[conf];
						
						const elementDiv = document.createElement('div');
						elementDiv.style.cssText = 'margin: 2px 0; cursor: pointer; padding: 2px; border-radius: 2px;';
						elementDiv.textContent = `${emoji} [${el.interactive_index}] ${el.reasoning?.element_type || 'UNKNOWN'} (${el.reasoning?.score || 0}pts)`;
						
						// Add hover effects
						elementDiv.addEventListener('mouseover', () => {
							elementDiv.style.background = 'rgba(255,255,255,0.1)';
						});
						elementDiv.addEventListener('mouseout', () => {
							elementDiv.style.background = 'transparent';
						});
						
						// Add click handler
						elementDiv.addEventListener('click', () => {
							const highlight = document.querySelector(`[data-element-id="${el.interactive_index}"]`);
							if (highlight) {
								highlight.scrollIntoView({behavior: 'smooth', block: 'center'});
							}
						});
						
						listContent.appendChild(elementDiv);
					});
					
					elementList.appendChild(listContent);
				} else {
					elementList.style.display = 'none';
				}
			}
			
			function applyFilter() {
				const highlights = container.querySelectorAll('[data-browser-use-highlight="element"]');
				let visibleCount = 0;
				
				highlights.forEach(highlight => {
					const elementId = highlight.getAttribute('data-element-id');
					const element = interactiveElements.find(el => el.interactive_index == elementId);
					const confidence = element?.reasoning?.confidence || 'MINIMAL';
					const score = element?.reasoning?.score || 0;
					
					// Apply both confidence filter and score threshold
					const passesConfidenceFilter = state.currentFilter === 'ALL' || confidence === state.currentFilter;
					const passesScoreThreshold = score >= state.scoreThreshold;
					
					if (passesConfidenceFilter && passesScoreThreshold) {
						highlight.style.display = 'block';
						visibleCount++;
					} else {
						highlight.style.display = 'none';
					}
				});
				
				// Update score info display
				const scoreInfoEl = document.getElementById('score-info');
				if (scoreInfoEl) {
					const totalCount = interactiveElements.length;
					const percentage = totalCount > 0 ? ((visibleCount / totalCount) * 100).toFixed(1) : '0';
					scoreInfoEl.textContent = `Showing ${visibleCount} of ${totalCount} elements (${percentage}%)`;
				}
				
				updateElementList();
			}
			
			function applySearch(query) {
				if (!query) {
					applyFilter();
					return;
				}
				
				const highlights = container.querySelectorAll('[data-browser-use-highlight="element"]');
				highlights.forEach(highlight => {
					const elementId = highlight.getAttribute('data-element-id');
					const element = interactiveElements.find(el => el.interactive_index == elementId);
					
					const searchableText = [
						element?.reasoning?.element_type,
						element?.reasoning?.confidence,
						element?.reasoning?.primary_reason,
						...(element?.reasoning?.evidence || []),
						...(element?.attributes ? Object.values(element.attributes) : [])
					].join(' ').toLowerCase();
					
					if (searchableText.includes(query)) {
						highlight.style.display = 'block';
						highlight.style.boxShadow = '0 0 10px #ff6b6b';
					} else {
						highlight.style.display = 'none';
					}
				});
			}
			
			// Variables for hover state management
			let currentHoverElement = null;
			
			// Enhanced highlighting with ALL elements included
			interactiveElements.forEach((element, index) => {
				const highlight = document.createElement('div');
				highlight.setAttribute('data-browser-use-highlight', 'element');
				highlight.setAttribute('data-element-id', element.interactive_index);
				
				const reasoning = element.reasoning || {};
				const confidence = reasoning.confidence || 'MINIMAL';
				const score = reasoning.score || 0;
				
				// Determine styling based on confidence
				let borderColor = '#6c757d';
				let backgroundColor = 'rgba(108, 117, 125, 0.05)';
				let labelColor = '#6c757d';
				let borderWidth = '1px';
				let borderStyle = 'solid';
				let animation = 'none';
				
				if (confidence === 'DEFINITE') {
					borderColor = '#28a745';
					backgroundColor = 'rgba(40, 167, 69, 0.15)';
					labelColor = '#28a745';
					borderWidth = '3px';
					borderStyle = 'solid';
					animation = 'definite-pulse 2s ease-in-out infinite';
				} else if (confidence === 'LIKELY') {
					borderColor = '#ffc107';
					backgroundColor = 'rgba(255, 193, 7, 0.12)';
					labelColor = '#ffc107';
					borderWidth = '2px';
					borderStyle = 'solid';
				} else if (confidence === 'POSSIBLE') {
					borderColor = '#fd7e14';
					backgroundColor = 'rgba(253, 126, 20, 0.1)';
					labelColor = '#fd7e14';
					borderWidth = '2px';
					borderStyle = 'dashed';
				} else if (confidence === 'QUESTIONABLE') {
					borderColor = '#dc3545';
					backgroundColor = 'rgba(220, 53, 69, 0.08)';
					labelColor = '#dc3545';
					borderWidth = '1px';
					borderStyle = 'dotted';
				} else if (confidence === 'MINIMAL') {
					borderColor = '#6f42c1';
					backgroundColor = 'rgba(111, 66, 193, 0.05)';
					labelColor = '#6f42c1';
					borderWidth = '1px';
					borderStyle = 'dotted';
				}
				
				// Add special styling for high-scoring elements
				if (score >= 70) {
					animation = 'high-score-glow 3s ease-in-out infinite';
					borderWidth = '3px';
				}
				
				// Enhanced highlight styling with animations
				highlight.style.cssText = `
					position: absolute;
					left: ${element.x}px;
					top: ${element.y}px;
					width: ${element.width}px;
					height: ${element.height}px;
					border: ${borderWidth} ${borderStyle} ${borderColor};
					background-color: ${backgroundColor};
					pointer-events: auto;
					box-sizing: border-box;
					transition: all 0.3s ease;
					animation: ${animation};
					border-radius: 3px;
					cursor: help;
				`;
				
				// Enhanced label with score and confidence
				const labelText = element.interactive_index + ' (' + score + ')';
				const label = createTextElement('div', labelText, `
					position: absolute;
					top: -24px;
					left: 0;
					background-color: ${labelColor};
					color: white;
					padding: 3px 8px;
					font-size: 10px;
					font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
					font-weight: bold;
					border-radius: 4px;
					white-space: nowrap;
					z-index: 1000001;
					box-shadow: 0 2px 6px rgba(0,0,0,0.3);
					transition: all 0.3s ease;
					border: 1px solid rgba(255,255,255,0.3);
					pointer-events: none;
				`);
				
				// Add confidence badge
				const confidenceEmoji = {
					'DEFINITE': '🟢',
					'LIKELY': '🟡', 
					'POSSIBLE': '🟠',
					'QUESTIONABLE': '🔴',
					'MINIMAL': '🟣'
				}[confidence] || '❓';
				
				const confidenceBadge = createTextElement('div', confidenceEmoji, `
					position: absolute;
					top: -24px;
					right: 0;
					background-color: rgba(0, 0, 0, 0.8);
					color: white;
					padding: 2px 4px;
					font-size: 12px;
					border-radius: 3px;
					z-index: 1000001;
					box-shadow: 0 2px 4px rgba(0,0,0,0.3);
					pointer-events: none;
				`);
				
										// No tooltip creation - details will be shown in debug panel
			
			// Function to show element details in debug panel
			function showElementDetails() {
				const selectedSection = document.getElementById('selected-element-details');
				const selectedContent = document.getElementById('selected-element-content');
				
				if (!selectedSection || !selectedContent) return;
				
				// Clear existing content
				while (selectedContent.firstChild) {
					selectedContent.removeChild(selectedContent.firstChild);
				}
				
				// Build comprehensive element details
				const reasoning = element.reasoning || {};
				const primaryReason = reasoning.primary_reason || 'unknown';
				const evidence = reasoning.evidence || [];
				const warnings = reasoning.warnings || [];
				const elementType = reasoning.element_type || element.element_name || 'UNKNOWN';
				const confidenceDescription = reasoning.confidence_description || 'Unknown confidence';
				const attrs = element.attributes || {};
				const keyAttrs = ['id', 'class', 'type', 'role', 'aria-label', 'onclick', 'href'];
				const relevantAttrs = keyAttrs.filter(attr => attrs[attr]);
				
				// Header with element info
				const header = document.createElement('div');
				header.style.cssText = `color: ${labelColor}; font-weight: bold; font-size: 12px; margin-bottom: 8px; border-bottom: 1px solid #444; padding-bottom: 6px;`;
				header.textContent = confidenceEmoji + ' [' + element.interactive_index + '] ' + elementType.toUpperCase();
				selectedContent.appendChild(header);
				
				// Confidence with score
				const confidenceDiv = document.createElement('div');
				confidenceDiv.style.cssText = `color: ${labelColor}; font-size: 11px; font-weight: bold; margin-bottom: 8px; padding: 4px 8px; background-color: rgba(255, 255, 255, 0.1); border-radius: 4px; border-left: 3px solid ${labelColor};`;
				confidenceDiv.textContent = confidence + ' CONFIDENCE (' + score + ' points)';
				selectedContent.appendChild(confidenceDiv);
				
				// Description
				const descDiv = document.createElement('div');
				descDiv.style.cssText = 'color: #ccc; font-size: 10px; margin-bottom: 10px; font-style: italic; padding: 4px 8px; background-color: rgba(255, 255, 255, 0.05); border-radius: 4px;';
				descDiv.textContent = confidenceDescription;
				selectedContent.appendChild(descDiv);
				
				// Evidence
				if (evidence.length > 0) {
					const evidenceDiv = document.createElement('div');
					evidenceDiv.style.cssText = 'margin-bottom: 10px;';
					
					const evidenceTitle = document.createElement('div');
					evidenceTitle.style.cssText = 'color: #28a745; font-size: 10px; margin-bottom: 4px; font-weight: bold;';
					evidenceTitle.textContent = '✅ Evidence (' + evidence.length + '):';
					evidenceDiv.appendChild(evidenceTitle);
					
					evidence.slice(0, 5).forEach((ev, i) => {
						const evidenceItem = document.createElement('div');
						evidenceItem.style.cssText = 'color: #ccc; font-size: 9px; margin-bottom: 2px; border-left: 2px solid #28a745; padding-left: 8px; margin-left: 4px;';
						evidenceItem.textContent = (i + 1) + '. ' + ev;
						evidenceDiv.appendChild(evidenceItem);
					});
					
					if (evidence.length > 5) {
						const moreDiv = document.createElement('div');
						moreDiv.style.cssText = 'color: #999; font-size: 8px; font-style: italic; margin-top: 2px; padding-left: 12px;';
						moreDiv.textContent = '... and ' + (evidence.length - 5) + ' more';
						evidenceDiv.appendChild(moreDiv);
					}
					
					selectedContent.appendChild(evidenceDiv);
				}
				
				// Warnings
				if (warnings.length > 0) {
					const warningsDiv = document.createElement('div');
					warningsDiv.style.cssText = 'margin-bottom: 10px;';
					
					const warningsTitle = document.createElement('div');
					warningsTitle.style.cssText = 'color: #ffc107; font-size: 10px; margin-bottom: 4px; font-weight: bold;';
					warningsTitle.textContent = '⚠️ Warnings (' + warnings.length + '):';
					warningsDiv.appendChild(warningsTitle);
					
					warnings.slice(0, 3).forEach((warn, i) => {
						const warningItem = document.createElement('div');
						warningItem.style.cssText = 'color: #ffeb3b; font-size: 9px; margin-bottom: 2px; border-left: 2px solid #ffc107; padding-left: 8px; margin-left: 4px;';
						warningItem.textContent = (i + 1) + '. ' + warn;
						warningsDiv.appendChild(warningItem);
					});
					
					selectedContent.appendChild(warningsDiv);
				}
				
				// Key attributes
				if (relevantAttrs.length > 0) {
					const attrsDiv = document.createElement('div');
					attrsDiv.style.cssText = 'margin-bottom: 10px;';
					
					const attrsTitle = document.createElement('div');
					attrsTitle.style.cssText = 'color: #17a2b8; font-size: 10px; margin-bottom: 4px; font-weight: bold;';
					attrsTitle.textContent = '🏷️ Key Attributes:';
					attrsDiv.appendChild(attrsTitle);
					
					relevantAttrs.forEach(attr => {
						const attrItem = document.createElement('div');
						attrItem.style.cssText = 'color: #b3e5fc; font-size: 9px; margin-bottom: 2px; border-left: 2px solid #17a2b8; padding-left: 8px; margin-left: 4px;';
						const value = attrs[attr].toString();
						const displayValue = value.length > 40 ? value.substring(0, 40) + '...' : value;
						attrItem.textContent = attr + ': "' + displayValue + '"';
						attrsDiv.appendChild(attrItem);
					});
					
					selectedContent.appendChild(attrsDiv);
				}
				
				// Position info
				const positionDiv = document.createElement('div');
				positionDiv.style.cssText = 'color: #666; font-size: 9px; margin-top: 12px; border-top: 1px solid #333; padding-top: 8px;';
				const area = Math.round(element.width * element.height);
				positionDiv.textContent = 'Position: (' + Math.round(element.x) + ', ' + Math.round(element.y) + ') • Size: ' + Math.round(element.width) + '×' + Math.round(element.height) + ' • Area: ' + area + 'px²';
				selectedContent.appendChild(positionDiv);
				
				// Debug info
				const debugDiv = document.createElement('div');
				debugDiv.style.cssText = 'color: #888; font-size: 8px; margin-top: 8px; border-top: 1px solid #333; padding-top: 6px; font-style: italic;';
				debugDiv.textContent = 'Reason: ' + primaryReason + ' • Frame: ' + (element.frame_id || 'main') + ' • Clickable: ' + (element.is_clickable ? 'Yes' : 'No');
				selectedContent.appendChild(debugDiv);
				
				// Show the section
				selectedSection.style.display = 'block';
			}
			
			// Simple hover effects for visual feedback
			function showHoverEffect() {
				// Visual feedback for this element
				highlight.style.borderColor = '#ff6b6b';
				highlight.style.backgroundColor = 'rgba(255, 107, 107, 0.25)';
				highlight.style.borderWidth = '4px';
				highlight.style.boxShadow = '0 0 20px rgba(255, 107, 107, 0.6)';
				highlight.style.transform = 'scale(1.02)';
				highlight.style.zIndex = '1000006';
				
				// Label animation
				label.style.backgroundColor = '#ff6b6b';
				label.style.transform = 'scale(1.15) translateY(-2px)';
				label.style.boxShadow = '0 4px 12px rgba(255, 107, 107, 0.4)';
				
				// Badge animation
				confidenceBadge.style.transform = 'scale(1.2) rotate(5deg)';
			}
			
			function hideHoverEffect() {
				// Reset visual effects
				highlight.style.borderColor = borderColor;
				highlight.style.backgroundColor = backgroundColor;
				highlight.style.borderWidth = borderWidth;
				highlight.style.boxShadow = 'none';
				highlight.style.transform = 'scale(1)';
				highlight.style.zIndex = '999999';
				
				// Reset label
				label.style.backgroundColor = labelColor;
				label.style.transform = 'scale(1) translateY(0)';
				label.style.boxShadow = '0 2px 6px rgba(0,0,0,0.3)';
				
				// Reset badge
				confidenceBadge.style.transform = 'scale(1) rotate(0deg)';
			}
			
			// Add event listeners - hover for visual feedback, click for details
			highlight.addEventListener('mouseenter', showHoverEffect, false);
			highlight.addEventListener('mouseleave', hideHoverEffect, false);
				
							// Enhanced click handling with detailed logging and panel display
			highlight.addEventListener('click', function(e) {
				e.stopPropagation();
				
				// Show element details in debug panel
				showElementDetails();
				
				// Comprehensive click logging
				console.group('🎯 Element [' + element.interactive_index + '] CLICKED - DETAILED ANALYSIS');
				console.log('═'.repeat(60));
				console.log('🏷️  BASIC INFO:');
				console.log('   Type:', elementType);
				console.log('   Confidence:', confidence, '(' + score + ' points)');
				console.log('   Position:', element.x + ',' + element.y);
				console.log('   Size:', element.width + 'x' + element.height + ' (area: ' + Math.round(element.width * element.height) + 'px²)');
				console.log('   Primary Reason:', primaryReason);
				
				console.log('🔍 REASONING ANALYSIS:');
				console.log('   Category:', reasoning.element_category || 'unknown');
				console.log('   Description:', confidenceDescription);
				
				if (evidence.length > 0) {
					console.log('✅ EVIDENCE (' + evidence.length + ' items):');
					evidence.forEach((ev, i) => console.log('   ' + (i + 1) + '. ' + ev));
				}
				
				if (warnings.length > 0) {
					console.log('⚠️  WARNINGS (' + warnings.length + ' items):');
					warnings.forEach((warn, i) => console.log('   ' + (i + 1) + '. ' + warn));
				}
				
				if (Object.keys(attrs).length > 0) {
					console.log('🏷️  ALL ATTRIBUTES (' + Object.keys(attrs).length + ' total):');
					Object.entries(attrs).forEach(([key, value]) => {
						const displayValue = value.toString().length > 100 ? value.toString().substring(0, 100) + '...' : value;
						console.log('   ' + key + ':', displayValue);
					});
				}
				
				console.log('🔧 TECHNICAL INFO:');
				console.log('   Clickable:', element.is_clickable);
				console.log('   Scrollable:', element.is_scrollable);
				console.log('   Frame ID:', element.frame_id || 'main');
				console.log('   Has Attributes:', reasoning.has_attributes);
				console.log('   Attribute Count:', reasoning.attribute_count);
				
				console.log('═'.repeat(60));
				console.groupEnd();
				
				// Scroll element in debug panel list and highlight it
				const listItem = elementList.querySelector(`[onclick*="${element.interactive_index}"]`);
				if (listItem) {
					listItem.style.background = 'rgba(255, 107, 107, 0.3)';
					listItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
					setTimeout(() => {
						listItem.style.background = 'transparent';
					}, 2000);
				}
				
				// Flash effect on the element itself
				const originalBorder = highlight.style.border;
				highlight.style.border = '4px solid #ff6b6b';
				highlight.style.boxShadow = '0 0 30px rgba(255, 107, 107, 0.8)';
				setTimeout(() => {
					highlight.style.border = originalBorder;
					highlight.style.boxShadow = 'none';
				}, 1000);
			}, false);
				
							// Assemble element (no tooltip - details shown in debug panel)
			highlight.appendChild(label);
			highlight.appendChild(confidenceBadge);
			container.appendChild(highlight);
			});
			
			// Add enhanced animations based on score gradients
			const style = document.createElement('style');
			style.textContent = `
				@keyframes score-glow-80 {
					0%, 100% { 
						box-shadow: 0 0 8px currentColor; 
						transform: scale(1);
					}
					50% { 
						box-shadow: 0 0 20px currentColor, 0 0 30px currentColor; 
						transform: scale(1.02);
					}
				}
				
				@keyframes score-pulse-60 {
					0%, 100% { 
						box-shadow: 0 0 5px currentColor; 
						opacity: 1;
					}
					50% { 
						box-shadow: 0 0 15px currentColor; 
						opacity: 0.9;
					}
				}
				
				@keyframes score-fade-low {
					0%, 100% { 
						opacity: 0.7; 
					}
					50% { 
						opacity: 1; 
					}
				}
				
				[data-browser-use-highlight="element"]:hover {
					z-index: 1000000 !important;
					animation: none !important;
				}
				
				button:hover {
					transform: translateY(-1px) !important;
					box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
				}
			`;
			document.head.appendChild(style);
			
			// Add container and debug panel to document
			document.body.appendChild(container);
			document.body.appendChild(debugPanel);
			
			// Add keyboard shortcuts
			document.addEventListener('keydown', (e) => {
				if (e.ctrlKey) {
					switch(e.key.toLowerCase()) {
						case 'r':
							e.preventDefault();
							location.reload();
							break;
						case 'h':
							e.preventDefault();
							state.highlightsVisible = !state.highlightsVisible;
							container.style.display = state.highlightsVisible ? 'block' : 'none';
							break;
						case 'd':
							e.preventDefault();
							debugPanel.style.display = debugPanel.style.display === 'none' ? 'block' : 'none';
							break;
						case 'f':
							e.preventDefault();
							searchInput.focus();
							break;
					}
				}
			});
			
			console.log('✅ Interactive debugging UI loaded successfully');
			console.log('🎮 Keyboard shortcuts:');
			console.log('   Ctrl+R: Refresh');
			console.log('   Ctrl+H: Toggle highlights');
			console.log('   Ctrl+D: Toggle debug panel');
			console.log('   Ctrl+F: Focus search');
			console.log('📊 Interactive features ready!');
		})();
		"""
		)

		# Inject the enhanced script
		await page.evaluate(script)
		print('✅ 🎮 Interactive debugging UI injected successfully!')

		# Print summary of enhanced features
		confidence_counts = {'DEFINITE': 0, 'LIKELY': 0, 'POSSIBLE': 0, 'QUESTIONABLE': 0, 'MINIMAL': 0}
		for elem in interactive_elements:
			confidence = elem.get('reasoning', {}).get('confidence', 'MINIMAL')
			confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1

		print('\n🎮 INTERACTIVE DEBUGGING UI FEATURES:')
		print('📊 Live Statistics Dashboard')
		print('🎮 Interactive Control Panel with clickable buttons:')
		print('   • 🔄 Refresh - Reload the page')
		print('   • 👁️ Toggle - Show/hide highlights')
		print('   • 💾 Export - Download analysis as JSON')
		print('   • ⬅️➡️ Website Navigation - Cycle through test sites')
		print('   • 🎲 Random Site - Jump to random test website')
		print('   • 📄 Serialized Data View - Show/hide raw data')
		print('   • 📋 Element List - Interactive element browser')
		print('   • 🔍 Filter Controls - Filter by confidence level')
		print('🔍 Live Search - Find elements by type, attributes, etc.')
		print('⚡ Performance Metrics - Real-time stats')
		print('🎯 Click-to-Navigate - Click elements to scroll to them')

		print('\n⌨️  KEYBOARD SHORTCUTS:')
		print('   • Ctrl+R: Refresh page')
		print('   • Ctrl+H: Toggle highlights')
		print('   • Ctrl+D: Toggle debug panel')
		print('   • Ctrl+F: Focus search box')

		print('\n📊 Element Summary:')
		for conf_level, count in confidence_counts.items():
			emoji = {'DEFINITE': '🟢', 'LIKELY': '🟡', 'POSSIBLE': '🟠', 'QUESTIONABLE': '🔴', 'MINIMAL': '🟣'}[conf_level]
			pct = (count / len(interactive_elements) * 100) if interactive_elements else 0
			print(f'   {emoji} {conf_level}: {count} elements ({pct:.1f}%)')

		print(f'\n🎯 Total: {len(interactive_elements)} elements with full interactive debugging!')

	except Exception as e:
		print(f'❌ Error injecting interactive debugging UI: {e}')
		traceback.print_exc()


async def save_outputs_to_files(serialized: str, selector_map: dict, interactive_elements: list[dict], url: str) -> dict:
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
				confidence_counts = {'DEFINITE': 0, 'LIKELY': 0, 'POSSIBLE': 0, 'QUESTIONABLE': 0, 'MINIMAL': 0}
				reason_counts = {}
				type_counts = {}

				for elem in interactive_elements:
					reasoning = elem['reasoning']
					confidence = reasoning['confidence']
					confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1
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

		# Print absolute paths for easy access
		abs_serialized_path = serialized_file.absolute()
		abs_elements_path = elements_file.absolute()
		abs_selector_path = selector_file.absolute()

		print('📁 Files saved with full paths:')
		print(f'   • {abs_serialized_path}')
		print('     Enhanced DOM serialization with reasoning')
		print(f'   • {abs_elements_path}')
		print('     Interactive elements with detailed analysis')
		print(f'   • {abs_selector_path}')
		print('     Selector map for debugging')

		return {
			'serialized_file': str(abs_serialized_path),
			'elements_file': str(abs_elements_path),
			'selector_file': str(abs_selector_path),
		}

	except Exception as e:
		print(f'❌ Error saving enhanced files: {e}')
		traceback.print_exc()
		return {}


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
	has_structured_elements = '[' in serialized and '<' in serialized

	# Calculate information density
	avg_chars_per_element = len(serialized) / max(len(interactive_elements), 1)

	quality_score = 0
	notes = []

	if has_structured_elements:
		quality_score += 25
		notes.append('✅ Structured format')

	# Performance-focused features (no iframe/shadow DOM)
	quality_score += 30  # Bonus for performance optimization
	notes.append('✅ Optimized performance (no iframe/shadow DOM)')

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

		# Print absolute paths for easy access
		abs_serialized_path = serialized_file.absolute()
		abs_elements_path = elements_file.absolute()

		print('📁 Test outputs saved:')
		print(f'   • {abs_serialized_path}')
		print(f'   • {abs_elements_path}')

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

		# Print absolute path for easy access
		abs_summary_path = summary_file.absolute()
		print(f'\n📁 Comprehensive summary saved: {abs_summary_path}')

	except Exception as e:
		print(f'❌ Error saving comprehensive summary: {e}')


async def main():
	"""Main function for interactive DOM testing."""
	print('🔍 DOM Extraction Testing Tool')
	print('=' * 50)

	try:
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
		print('  ✅ Score-based threshold filtering')
		print('  ✅ Aggressive container removal')
		print('  ✅ Perfect sync between highlighting and serialization')
		print('=' * 60)

		# Use default score threshold - users can adjust via debug UI slider
		score_threshold = 0  # CHANGED: Test with threshold 0 to include ALL AX elements
		print('\n🎯 TESTING SCORE THRESHOLD = 0 MODE:')
		print('   • Using score threshold: 0 points (includes ALL AX elements)')
		print('   • 🎛️  This should include many more elements')
		print('   • 📊 Testing the enhanced scoring system')
		print('   • 🎮 Full interactive debugging features enabled')

		while True:
			try:
				# Get website choice
				url = get_website_choice()

				# Navigate to chosen website
				print(f'\n🌐 Navigating to: {url}')
				await browser_session.navigate_to(url)
				await asyncio.sleep(3)  # Wait for page to load

				while True:
					print('\n🔄 Extracting DOM with score-filtered comprehensive detection')
					print('=' * 60)

					# Extract interactive elements with score threshold
					interactive_elements, serialized, selector_map = await extract_interactive_elements_from_service(
						dom_service, score_threshold
					)

					# Print summary
					print('\n📊 Score-Filtered Extraction Results:')
					print(f'  - Score threshold: {score_threshold} points')
					print(f'  - Interactive elements detected: {len(interactive_elements)}')
					print(f'  - Serialized length: {len(serialized)} characters')
					print(f'  - Selector map entries: {len(selector_map)}')

					# Show performance optimization info
					print('  - 🚀 Performance optimizations active:')
					print('      - Fast AX tree processing')
					print('      - Score-based threshold filtering')
					print('      - No CDP errors from iframe/shadow DOM')
					print('      - Viewport-based filtering')

					# Show viewport info if available
					if interactive_elements:
						min_x = min(elem['x'] for elem in interactive_elements)
						max_x = max(elem['x'] + elem['width'] for elem in interactive_elements)
						min_y = min(elem['y'] for elem in interactive_elements)
						max_y = max(elem['y'] + elem['height'] for elem in interactive_elements)
						print(f'  - Element bounds: x({min_x:.0f}-{max_x:.0f}) y({min_y:.0f}-{max_y:.0f})')

					# Print sample elements
					if interactive_elements:
						print('\n🎯 Sample score-filtered interactive elements:')
						for elem in interactive_elements[:5]:
							score = elem.get('reasoning', {}).get('score', 0)
							confidence = elem.get('reasoning', {}).get('confidence', 'UNKNOWN')
							attrs_info = get_element_description(elem)
							print(
								f'      [{elem["interactive_index"]}] {elem["element_name"]}{attrs_info} - {score}pts ({confidence})'
							)
						if len(interactive_elements) > 5:
							print(f'      ... and {len(interactive_elements) - 5} more')

					# Highlight elements with full debug UI (only the filtered ones will be highlighted)
					await inject_highlighting_script(browser_session, interactive_elements)

					# Save outputs to files
					saved_files = await save_outputs_to_files(serialized, selector_map, interactive_elements, url)

					# Show where the LLM string representation is saved
					print('\n📄 LLM STRING REPRESENTATION SAVED:')
					if saved_files and 'serialized_file' in saved_files:
						print(f'   📁 File: {saved_files["serialized_file"]}')
						print('   📊 Content: Enhanced DOM serialization with reasoning')
						print(f'   📏 Size: {len(serialized):,} characters')
					else:
						print('   ⚠️  File location not available')

					# Save comprehensive DOM tree JSON
					json_file_path = await save_comprehensive_dom_tree_json(
						dom_service, interactive_elements, serialized, selector_map, url
					)
					if json_file_path:
						print(f'📄 DOM tree JSON also available at: {json_file_path}')

					# Print serialized output preview
					print('\n📄 Score-filtered serialized output preview (first 800 chars):')
					print('-' * 60)
					print(serialized[:800])
					if len(serialized) > 800:
						print('...[TRUNCATED]')
					print('-' * 60)

					# Ask what to do next
					print('\n⚡ Next action:')
					print('  1. Extract again (test for consistency)')
					print('  2. Test different website')
					print('  3. Inspect elements via CLI')
					print('  4. Extract & analyze AX tree')
					print('  5. Exit')
					print('  🎛️  Use debug UI slider to adjust threshold in real-time')

					try:
						next_choice = input('Enter choice (1, 2, 3, 4, or 5): ').strip()
						if next_choice == '1':
							continue  # Extract again
						elif next_choice == '2':
							break  # Go to website selection
						elif next_choice == '3':
							cli_inspection_mode(interactive_elements)
							continue  # Stay on same page after inspection
						elif next_choice == '4':
							# Extract and analyze AX tree
							print('\n🌳 Extracting and analyzing AX tree for interactive patterns...')
							ax_tree_path = await extract_and_save_ax_tree(dom_service, url)
							if ax_tree_path:
								print('\n✅ AX tree analysis complete!')
								print(f'📁 Files saved for analysis: {Path(ax_tree_path).parent}')
								print('🔍 Review the analysis to understand what interactive elements we might be missing')
								input('\n📋 Press ENTER to continue...')
							else:
								print('❌ Failed to extract AX tree')
							continue  # Stay on same page
						elif next_choice == '5':
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


async def test_website_direct(url: str, score_threshold: int = 15) -> None:
	"""Test a specific website directly without input() calls for better automation."""
	profile = BrowserProfile(headless=False, keep_alive=True)
	browser_session = BrowserSession(browser_profile=profile)

	try:
		await browser_session.start()
		dom_service = DOMService(browser_session)

		print_section_header(f'🌐 TESTING WEBSITE: {url}')
		print(f'🎯 Score threshold: {score_threshold} points')

		# Navigate to website
		print(f'📍 Navigating to: {url}')
		await browser_session.navigate_to(url)
		await asyncio.sleep(3)  # Wait for page to load

		# Extract interactive elements with score threshold
		interactive_elements, serialized, selector_map = await extract_interactive_elements_from_service(
			dom_service, score_threshold
		)

		# Inject highlighting
		await inject_highlighting_script(browser_session, interactive_elements)

		# Save outputs and show LLM string representation location
		saved_files = await save_outputs_to_files(serialized, selector_map, interactive_elements, url)

		print('\n📄 LLM STRING REPRESENTATION SAVED:')
		if saved_files and 'serialized_file' in saved_files:
			print(f'   📁 File: {saved_files["serialized_file"]}')
			print('   📊 Content: Enhanced DOM serialization with reasoning')
		else:
			print('   ⚠️  File location not available')

		print_section_header('✅ TESTING COMPLETE')
		print(f'🎯 Found {len(interactive_elements)} interactive elements (threshold: {score_threshold}pts)')
		print('🖥️  Browser will stay open for manual inspection')
		print('🔄 Press Ctrl+R in browser to refresh highlighting after scrolling')
		tmp_dir_abs = Path('tmp').absolute()
		print(f'📁 Check analysis files directory: {tmp_dir_abs}')
		print('')
		print('🚀 Ready to test another website!')

	except Exception as e:
		print(f'❌ Error testing website: {e}')
		traceback.print_exc()
	# Note: Browser stays open due to keep_alive=True


async def persistent_debug_mode():
	"""Persistent browser debugging mode - keeps browser open and allows navigation to multiple websites."""
	print('🚀' * 30)
	print('🎯 PERSISTENT BROWSER DEBUG MODE')
	print('🚀' * 30)
	print('✨ Features:')
	print('   • Browser stays open permanently')
	print('   • Navigate to any website')
	print('   • Debug UI automatically loads on each page')
	print('   • Configurable score threshold filtering')
	print('   • Type URLs or use shortcuts')
	print('   • Press ENTER to re-highlight current page')
	print('   • Type "inspect" to analyze specific elements by ID')
	print('   • Type "threshold" to change score threshold')
	print('   • Press Ctrl+C to exit')
	print('')

	profile = BrowserProfile(headless=False, keep_alive=True)
	browser_session = BrowserSession(browser_profile=profile)

	try:
		await browser_session.start()
		dom_service = DOMService(browser_session)

		# Use default score threshold - adjustable via debug UI slider
		score_threshold = 15
		print('🎯 INTERACTIVE DEBUG MODE:')
		print('   • Default threshold: 15 points (adjustable via slider in debug UI)')
		print('   • 🎛️  Real-time threshold adjustment available')
		print('   • 📊 Live statistics and filtering')
		print(f'\n✅ Starting with threshold: {score_threshold} points')

		# Initialize interactive elements for inspection
		interactive_elements = []

		print('\n🌐 WEBSITE SHORTCUTS:')
		shortcuts = {
			'1': ('Example.com', 'https://example.com'),
			'2': ('GitHub', 'https://github.com'),
			'3': ('Google Flights', 'https://www.google.com/travel/flights'),
			'4': ('Semantic UI', 'https://semantic-ui.com/modules/dropdown.html'),
			'5': ('Browser-use', 'https://browser-use.com'),
			'6': ('Wikipedia', 'https://en.wikipedia.org/wiki/Internet'),
			'7': ('Stack Overflow', 'https://stackoverflow.com'),
			'8': ('Reddit', 'https://reddit.com'),
			'9': ('YouTube', 'https://youtube.com'),
			'10': ('Amazon', 'https://amazon.com'),
			'11': ('Google Search', 'https://www.google.com/search?q=browser+automation'),
			'12': ('Twitter/X', 'https://twitter.com'),
			'13': ('LinkedIn', 'https://linkedin.com'),
			'14': ('MDN Docs', 'https://developer.mozilla.org/en-US/'),
			'15': ('HackerNews', 'https://news.ycombinator.com'),
			'16': ('NPM', 'https://www.npmjs.com'),
			'17': ('Docker Hub', 'https://hub.docker.com'),
			'18': ('Vercel', 'https://vercel.com'),
			'19': ('Stripe Docs', 'https://stripe.com/docs'),
			'20': ('OpenAI', 'https://openai.com'),
		}

		for key, (name, url) in shortcuts.items():
			print(f'   {key}. {name} ({url})')
		print('   Or enter any custom URL')
		print('')

		while True:
			try:
				print('🎯 Enter a website to debug:')
				print('   • Type a number (1-20) for shortcuts')
				print('   • Type any URL (https://...)')
				print('   • Press ENTER to re-highlight current page')
				print('   • Type "inspect" to inspect a specific element by ID')
				print('   • Type "help" for all shortcuts')
				print('   • Type "quit" to exit')
				print('   • 🎛️  Use the slider in debug UI to adjust threshold')

				choice = input('\n🌐 Website: ').strip()

				if choice.lower() in ['quit', 'exit', 'q']:
					print('👋 Exiting persistent debug mode...')
					break
				elif choice.lower() == 'help':
					print('\n🌐 AVAILABLE SHORTCUTS:')
					for key, (name, url) in shortcuts.items():
						print(f'   {key}. {name} - {url}')
					continue

				elif choice.lower() == 'inspect':
					# Element inspection mode
					if 'interactive_elements' in locals() and interactive_elements:
						print('\n🔍 ELEMENT INSPECTION MODE')
						print('=' * 50)
						print(
							f'Found {len(interactive_elements)} interactive elements on current page (threshold: {score_threshold}pts)'
						)
						available_ids = []
						for elem in interactive_elements:
							idx = elem.get('interactive_index')
							if idx is not None:
								available_ids.append(idx)
						print('Available element IDs:', sorted(available_ids))

						try:
							element_id = input('\n🎯 Enter element ID to inspect: ').strip()

							if element_id.lower() in ['quit', 'q', 'exit', 'back']:
								print('👋 Exiting inspection mode')
								continue
							elif element_id.isdigit():
								element_number = int(element_id)
								inspect_element_by_number(interactive_elements, element_number)
								input('\n📋 Press ENTER to continue...')
							else:
								print(f'❌ Invalid element ID: "{element_id}". Please enter a number.')
						except (EOFError, KeyboardInterrupt):
							print('\n👋 Exiting inspection mode')
					else:
						print('❌ No interactive elements available. Please navigate to a website first.')
					continue
				elif choice == '':
					# Empty input - re-run highlighting on current page
					print(f'🔄 Re-running highlighting on current page (threshold: {score_threshold}pts)...')
					url = None  # Don't navigate, just re-extract
					name = 'Current Page'
				elif choice in shortcuts:
					name, url = shortcuts[choice]
					print(f'🚀 Loading {name}...')
				elif choice.startswith('http'):
					url = choice
					name = url.split('://')[1].split('/')[0]
					print(f'🚀 Loading {name}...')
				else:
					print('❌ Invalid choice. Please enter a number (1-20) or a URL starting with http')
					continue

				# Navigate to the website (or skip if re-highlighting current page)
				if url is not None:
					print(f'📍 Navigating to: {url}')
					await browser_session.navigate_to(url)
					await asyncio.sleep(3)  # Wait for page load
				else:
					print('📍 Staying on current page')
					# Small delay to let any pending page changes settle
					await asyncio.sleep(1)

				# Extract and inject debug UI with score threshold
				print(f'🔍 Extracting interactive elements (threshold: {score_threshold}pts)...')
				current_elements, serialized, selector_map = await extract_interactive_elements_from_service(
					dom_service, score_threshold
				)

				# Update global interactive_elements for inspection
				interactive_elements = current_elements

				print('🎮 Injecting debug UI...')
				await inject_highlighting_script_safe(browser_session, current_elements)

				# Show quick summary
				confidence_counts = {'DEFINITE': 0, 'LIKELY': 0, 'POSSIBLE': 0, 'QUESTIONABLE': 0, 'MINIMAL': 0}
				for elem in current_elements:
					conf = elem.get('reasoning', {}).get('confidence', 'MINIMAL')
					confidence_counts[conf] = confidence_counts.get(conf, 0) + 1

				print(f'✅ Debug UI loaded! Found {len(current_elements)} interactive elements (threshold: {score_threshold}pts)')
				print(
					f'   🟢 DEFINITE: {confidence_counts["DEFINITE"]} | 🟡 LIKELY: {confidence_counts["LIKELY"]} | 🟠 POSSIBLE: {confidence_counts["POSSIBLE"]}'
				)
				print(f'   🔴 QUESTIONABLE: {confidence_counts["QUESTIONABLE"]} | 🟣 MINIMAL: {confidence_counts["MINIMAL"]}')
				print('🎯 Hover over elements to see details, click for full analysis!')
				print('')

			except KeyboardInterrupt:
				print('\n👋 Exiting persistent debug mode...')
				break
			except Exception as e:
				print(f'❌ Error: {e}')
				print('🔄 Continuing with next website...')
				continue

	except Exception as e:
		print(f'❌ Failed to start persistent debug mode: {e}')
		traceback.print_exc()
	finally:
		# Keep browser open even after errors
		print('🖥️  Browser will stay open for manual inspection')
		print('   (Close browser window manually when done)')


async def inject_highlighting_script_safe(browser_session: BrowserSession, interactive_elements: list[dict]) -> None:
	"""Inject JavaScript highlighting with CSP-safe methods (no innerHTML). ENHANCED with more detailed hover info and re-highlight refresh."""
	if not interactive_elements:
		print('⚠️ No interactive elements to highlight')
		return

	try:
		page = await browser_session.get_current_page()
		print(f'📍 Creating enhanced CSP-safe debugging UI for {len(interactive_elements)} elements')

		# Create CSP-safe script that avoids innerHTML
		elements_json = json.dumps(interactive_elements)

		# Get the serialized data from the current extraction
		# This should be available from the calling context
		try:
			# Get serialized data from the most recent extraction
			page = await browser_session.get_current_page()
			dom_service = DOMService(browser_session)
			current_serialized, _ = await dom_service.get_serialized_dom_tree(use_enhanced_filtering=False)
			serialized_json = json.dumps(current_serialized)
		except Exception as e:
			print(f'⚠️ Could not get current serialized data: {e}')
			serialized_json = json.dumps('Serialized data not available - try re-extracting elements')

		script = f"""
		(function() {{
			// Test websites for cycling - EXPANDED LIST WITH MORE VARIETY
			const testWebsites = [
				{{ name: 'Example.com', url: 'https://example.com' }},
				{{ name: 'Browser Use', url: 'https://browser-use.com' }},
				{{ name: 'GitHub', url: 'https://github.com' }},
				{{ name: 'Semantic UI', url: 'https://semantic-ui.com/modules/dropdown.html' }},
				{{ name: 'Google Flights', url: 'https://www.google.com/travel/flights' }},
				{{ name: 'Wikipedia', url: 'https://en.wikipedia.org/wiki/Internet' }},
				{{ name: 'Stack Overflow', url: 'https://stackoverflow.com' }},
				{{ name: 'Reddit', url: 'https://reddit.com' }},
				{{ name: 'YouTube', url: 'https://youtube.com' }},
				{{ name: 'Amazon', url: 'https://amazon.com' }},
				{{ name: 'Google Search', url: 'https://www.google.com/search?q=browser+automation' }},
				{{ name: 'Twitter/X', url: 'https://twitter.com' }},
				{{ name: 'LinkedIn', url: 'https://linkedin.com' }},
				{{ name: 'MDN Docs', url: 'https://developer.mozilla.org/en-US/' }},
				{{ name: 'HackerNews', url: 'https://news.ycombinator.com' }},
				{{ name: 'NPM', url: 'https://www.npmjs.com' }},
				{{ name: 'Docker Hub', url: 'https://hub.docker.com' }},
				{{ name: 'Vercel', url: 'https://vercel.com' }},
				{{ name: 'Stripe Docs', url: 'https://stripe.com/docs' }},
				{{ name: 'OpenAI', url: 'https://openai.com' }}
			];
			
			// Remove existing highlights
			const existingHighlights = document.querySelectorAll('[data-browser-use-highlight]');
			existingHighlights.forEach(el => el.remove());
			
			const interactiveElements = {elements_json};
			
			console.log('=== BROWSER-USE ENHANCED DEBUG UI ===');
			console.log('Interactive elements:', interactiveElements.length);
			console.log('Enhanced features: Re-highlight refresh, detailed hover info, AX tree data');
			
			// Global state
			let state = {{
				highlightsVisible: true,
				tooltipsEnabled: true,
				currentFilter: 'ALL',
				lastHighlightTime: Date.now(),
				currentWebsiteIndex: 0,
				scoreThreshold: 15,  // Default minimum score threshold
				isReextracting: false
			}};
			
			// Function to re-extract and re-highlight elements (triggers page reload for full re-extraction)
			async function reHighlightElements() {{
				console.log('🔄 Re-extracting elements (full reload)...');
				
				// Show loading indicator
				const loadingDiv = document.createElement('div');
				loadingDiv.style.cssText = `
					position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
					background: linear-gradient(45deg, #28a745, #20c997); color: white; padding: 20px;
					border-radius: 15px; font-family: monospace; z-index: 1000025;
					font-size: 16px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5);
				`;
				// Build loading content with safe DOM methods
				const loadingIcon = document.createTextNode('🔄 Re-extracting elements...');
				loadingDiv.appendChild(loadingIcon);
				loadingDiv.appendChild(document.createElement('br'));
				
				const loadingSmall = document.createElement('small');
				loadingSmall.style.cssText = 'opacity: 0.8;';
				loadingSmall.textContent = 'Triggering full DOM re-analysis';
				loadingDiv.appendChild(loadingSmall);
				loadingDiv.appendChild(document.createElement('br'));
				
				const loadingDesc = document.createElement('div');
				loadingDesc.style.cssText = 'margin-top: 10px; font-size: 12px;';
				loadingDesc.textContent = 'This will reload the page with fresh highlighting';
				loadingDiv.appendChild(loadingDesc);
				document.body.appendChild(loadingDiv);
				
				// Set flag to indicate we're re-extracting
				state.isReextracting = true;
				
				// Trigger page reload after brief delay (this will cause full re-extraction)
				setTimeout(() => {{
					location.reload();
				}}, 1500);
				
				console.log('🚀 Triggering page reload for full DOM re-extraction...');
			}}
			
			// Apply score threshold filter
			function applyScoreThreshold() {{
				const highlights = container.querySelectorAll('[data-browser-use-highlight="element"]');
				let visibleCount = 0;
				
				highlights.forEach(highlight => {{
					const elementId = highlight.getAttribute('data-element-id');
					const element = interactiveElements.find(el => el.interactive_index == elementId);
					const score = element?.reasoning?.score || 0;
					
					if (score >= state.scoreThreshold) {{
						highlight.style.display = 'block';
						visibleCount++;
					}} else {{
						highlight.style.display = 'none';
					}}
				}});
				
				console.log(`📊 Score filter: showing ${{visibleCount}} elements with score >= ${{state.scoreThreshold}}`);
				return visibleCount;
			}}
			
			// Create container
			const container = document.createElement('div');
			container.id = 'browser-use-debug-highlights';
			container.setAttribute('data-browser-use-highlight', 'container');
			container.style.cssText = `
				position: absolute; top: 0; left: 0; width: 100%; height: 100%;
				pointer-events: none; z-index: 999999;
			`;
			
			// Create enhanced debug panel
			const debugPanel = document.createElement('div');
			debugPanel.setAttribute('data-browser-use-highlight', 'debug-panel');
			debugPanel.style.cssText = `
				position: fixed; top: 10px; right: 10px;
				background: linear-gradient(145deg, rgba(0, 0, 0, 0.95), rgba(20, 20, 20, 0.95));
				color: white; padding: 20px; border-radius: 15px;
				font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
				font-size: 12px; z-index: 1000010;
				box-shadow: 0 10px 40px rgba(0,0,0,0.8);
				border: 2px solid #4a90e2; backdrop-filter: blur(15px);
				min-width: 320px; max-width: 450px; max-height: 80vh;
				overflow-y: auto; pointer-events: auto;
			`;
			
			// Create panel content using safe DOM methods
			const header = document.createElement('div');
			header.style.cssText = 'color: #4a90e2; font-weight: bold; font-size: 14px; margin-bottom: 15px; border-bottom: 2px solid #4a90e2; padding-bottom: 10px;';
			header.textContent = '🔍 Enhanced Debug Console';
			debugPanel.appendChild(header);
			
			// Statistics
			const stats = {{ definite: 0, likely: 0, possible: 0, questionable: 0, minimal: 0 }};
			interactiveElements.forEach(el => {{
				const confidence = el.reasoning ? el.reasoning.confidence : 'MINIMAL';
				if (confidence === 'DEFINITE') stats.definite++;
				else if (confidence === 'LIKELY') stats.likely++;
				else if (confidence === 'POSSIBLE') stats.possible++;
				else if (confidence === 'QUESTIONABLE') stats.questionable++;
				else stats.minimal++;
			}});
			
			const statsSection = document.createElement('div');
			statsSection.style.cssText = 'margin-bottom: 15px; padding: 10px; background: rgba(255,255,255,0.1); border-radius: 8px;';
			
			const statsTitle = document.createElement('div');
			statsTitle.style.cssText = 'color: #4a90e2; font-weight: bold; margin-bottom: 8px;';
			statsTitle.textContent = '📊 Element Statistics';
			statsSection.appendChild(statsTitle);
			
			const statsContent = document.createElement('div');
			statsContent.style.cssText = 'font-size: 11px; line-height: 1.4;';
			
			// Add stats lines safely  
			const statsLines = [
				`🟢 DEFINITE: ${{stats.definite}} (${{(stats.definite/interactiveElements.length*100).toFixed(1)}}%)`,
				`🟡 LIKELY: ${{stats.likely}} (${{(stats.likely/interactiveElements.length*100).toFixed(1)}}%)`,
				`🟠 POSSIBLE: ${{stats.possible}} (${{(stats.possible/interactiveElements.length*100).toFixed(1)}}%)`,
				`🔴 QUESTIONABLE: ${{stats.questionable}} (${{(stats.questionable/interactiveElements.length*100).toFixed(1)}}%)`,
				`🟣 MINIMAL: ${{stats.minimal}} (${{(stats.minimal/interactiveElements.length*100).toFixed(1)}}%)`,
				`📈 Total: ${{interactiveElements.length}} elements`
			];
			
			statsLines.forEach(line => {{
				const lineDiv = document.createElement('div');
				lineDiv.textContent = line;
				statsContent.appendChild(lineDiv);
			}});
			
			statsSection.appendChild(statsContent);
			debugPanel.appendChild(statsSection);
			
			// Score threshold slider section
			const scoreSection = document.createElement('div');
			scoreSection.style.cssText = 'margin-bottom: 15px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px;';
			
			const scoreTitle = document.createElement('div');
			scoreTitle.style.cssText = 'color: #4a90e2; font-weight: bold; margin-bottom: 8px; font-size: 11px;';
			scoreTitle.textContent = '🎯 Score Threshold Filter';
			scoreSection.appendChild(scoreTitle);
			
			// Score info display
			const scoreInfo = document.createElement('div');
			scoreInfo.style.cssText = 'font-size: 10px; margin-bottom: 8px; color: #ccc;';
			scoreInfo.id = 'score-info-safe';
			scoreSection.appendChild(scoreInfo);
			
			// Score slider
			const scoreSlider = document.createElement('input');
			scoreSlider.type = 'range';
			scoreSlider.min = '0';
			scoreSlider.max = '100';
			scoreSlider.value = state.scoreThreshold.toString();
			scoreSlider.style.cssText = `
				width: 100%; margin: 5px 0; height: 6px; border-radius: 3px;
				background: linear-gradient(90deg, #dc3545 0%, #ffc107 25%, #28a745 75%, #007bff 100%);
				outline: none; -webkit-appearance: none;
			`;
			
			// Score slider styling
			const sliderStyleSafe = document.createElement('style');
			sliderStyleSafe.textContent = `
				input[type="range"]::-webkit-slider-thumb {{
					-webkit-appearance: none; appearance: none;
					width: 16px; height: 16px; border-radius: 50%;
					background: #4a90e2; cursor: pointer;
					box-shadow: 0 2px 6px rgba(0,0,0,0.3);
				}}
				input[type="range"]::-moz-range-thumb {{
					width: 16px; height: 16px; border-radius: 50%;
					background: #4a90e2; cursor: pointer; border: none;
					box-shadow: 0 2px 6px rgba(0,0,0,0.3);
				}}
			`;
			document.head.appendChild(sliderStyleSafe);
			
			// Score value display
			const scoreValue = document.createElement('div');
			scoreValue.style.cssText = 'text-align: center; font-size: 12px; font-weight: bold; margin-top: 5px; color: #4a90e2;';
			scoreValue.id = 'score-value-safe';
			scoreSection.appendChild(scoreValue);
			
			// Function to update score display and filter
			function updateScoreThresholdSafe() {{
				const threshold = parseInt(scoreSlider.value);
				state.scoreThreshold = threshold;
				
				// Update displays
				scoreValue.textContent = `Min Score: ${{threshold}} points`;
				
				// Count elements at current threshold
				const visibleCount = applyScoreThreshold();
				const totalCount = interactiveElements.length;
				const percentage = totalCount > 0 ? ((visibleCount / totalCount) * 100).toFixed(1) : '0';
				
				scoreInfo.textContent = `Showing ${{visibleCount}} of ${{totalCount}} elements (${{percentage}}%)`;
				
				console.log(`🎯 Score threshold updated: ${{threshold}} (showing ${{visibleCount}}/${{totalCount}} elements)`);
			}}
			
			// Add slider event listener
			scoreSlider.addEventListener('input', updateScoreThresholdSafe);
			
			// Add slider and value to section
			scoreSection.appendChild(scoreSlider);
			scoreSection.appendChild(scoreValue);
			
			// Initialize score display
			updateScoreThresholdSafe();
			
			debugPanel.appendChild(scoreSection);
			
			console.log('✅ Enhanced debugging UI injected successfully');
		}})();
		"""

		await page.evaluate(script)

	except Exception as e:
		print('❌ Error injecting highlighting script: {e}')
		traceback.print_exc()


# Common test websites for quick testing
TEST_WEBSITES = {
	'simple': 'https://example.com',
	'browser-use': 'https://browser-use.com',
	'github': 'https://github.com',
	'semantic-ui': 'https://semantic-ui.com/modules/dropdown.html',
	'google-flights': 'https://www.google.com/travel/flights',
	'wikipedia': 'https://en.wikipedia.org/wiki/Internet',
	'google-search': 'https://www.google.com/search?q=browser+automation',
	'stackoverflow': 'https://stackoverflow.com',
	'reddit': 'https://www.reddit.com',
	'youtube': 'https://www.youtube.com',
	'amazon': 'https://www.amazon.com',
	'twitter': 'https://twitter.com',
}


def inspect_element_by_number(interactive_elements: list[dict], element_number: int) -> None:
	"""Inspect a specific element by its interactive index number with comprehensive details."""

	# Find element by interactive_index
	target_element = None
	for elem in interactive_elements:
		if elem.get('interactive_index') == element_number:
			target_element = elem
			break

	if not target_element:
		print(f'\n❌ Element [{element_number}] not found in interactive elements.')
		available_indices = []
		for elem in interactive_elements:
			idx = elem.get('interactive_index')
			if idx is not None and isinstance(idx, int):
				available_indices.append(idx)
		available_indices.sort()
		print(f'📋 Available elements: {available_indices}')
		return

	reasoning = target_element.get('reasoning', {})
	attrs = target_element.get('attributes', {})

	print('\n🔍 COMPREHENSIVE ELEMENT INSPECTION')
	print('=' * 80)

	# Enhanced header with visual indicators
	confidence_emoji = {
		'DEFINITE': '🟢',
		'LIKELY': '🟡',
		'POSSIBLE': '🟠',
		'QUESTIONABLE': '🔴',
		'MINIMAL': '🟣',
	}.get(reasoning.get('confidence'), '❓')

	print(f'\n🎯 ELEMENT [{element_number}] - {reasoning.get("element_type", "UNKNOWN")}')
	print(f'{confidence_emoji} {reasoning.get("confidence", "UNKNOWN")} CONFIDENCE ({reasoning.get("score", 0)} points)')
	print(f'📂 Category: {reasoning.get("element_category", "unknown").replace("_", " ").title()}')
	print(f'📄 Description: {reasoning.get("confidence_description", "No description")}')
	print(f'🎲 Primary Reason: {reasoning.get("primary_reason", "unknown").replace("_", " ").title()}')

	# Enhanced position and size information
	x, y = target_element.get('x', 0), target_element.get('y', 0)
	width, height = target_element.get('width', 0), target_element.get('height', 0)
	print('\n📍 POSITIONING & SIZE:')
	print(f'   • Position: ({x:.1f}, {y:.1f})')
	print(f'   • Size: {width:.1f}×{height:.1f}px')
	print(f'   • Area: {width * height:.0f} px²')
	print(f'   • Bounds: ({x:.1f}, {y:.1f}) to ({x + width:.1f}, {y + height:.1f})')
	if width > 0 and height > 0:
		aspect_ratio = width / height
		print(
			f'   • Aspect Ratio: {aspect_ratio:.2f}:1 ({"landscape" if aspect_ratio > 1 else "portrait" if aspect_ratio < 1 else "square"})'
		)

	# Element properties
	print('\n🔧 ELEMENT PROPERTIES:')
	print(f'   • Is Clickable: {target_element.get("is_clickable", False)}')
	print(f'   • Is Scrollable: {target_element.get("is_scrollable", False)}')
	print(f'   • Frame ID: {target_element.get("frame_id", "main")}')
	print(f'   • Has Attributes: {reasoning.get("has_attributes", False)}')
	print(f'   • Attribute Count: {reasoning.get("attribute_count", 0)}')

	# Evidence section with better formatting
	evidence = reasoning.get('evidence', [])
	if evidence:
		print(f'\n✅ EVIDENCE ({len(evidence)} items):')
		for i, ev in enumerate(evidence, 1):
			print(f'   {i:2d}. {ev}')
	else:
		print('\n❓ No evidence recorded')

	# Warnings section with better formatting
	warnings = reasoning.get('warnings', [])
	if warnings:
		print(f'\n⚠️  WARNINGS ({len(warnings)} items):')
		for i, warn in enumerate(warnings, 1):
			print(f'   {i:2d}. {warn}')

	# Context information with better formatting
	context_info = reasoning.get('context_info', [])
	if context_info:
		print(f'\n📋 CONTEXT INFORMATION ({len(context_info)} items):')
		for i, info in enumerate(context_info, 1):
			print(f'   {i:2d}. {info}')

	# Enhanced attributes section with categorization
	if attrs:
		print(f'\n🏷️  ALL ATTRIBUTES ({len(attrs)} total):')

		# Categorize attributes
		important_attrs = ['id', 'class', 'type', 'role', 'aria-label', 'aria-labelledby', 'href', 'src', 'alt', 'title']
		event_attrs = [k for k in attrs.keys() if k.startswith('on')]
		data_attrs = [k for k in attrs.keys() if k.startswith('data-')]
		aria_attrs = [k for k in attrs.keys() if k.startswith('aria-')]
		style_attrs = [k for k in attrs.keys() if k in ['style', 'class']]

		# Show important attributes first
		if any(attr in attrs for attr in important_attrs):
			print('\n   📌 IMPORTANT ATTRIBUTES:')
			for attr in important_attrs:
				if attr in attrs:
					value_str = str(attrs[attr])
					if len(value_str) > 100:
						value_str = value_str[:100] + '...'
					print(f'      • {attr}: "{value_str}"')

		# Show event attributes
		if event_attrs:
			print('\n   ⚡ EVENT ATTRIBUTES:')
			for attr in sorted(event_attrs):
				value_str = str(attrs[attr])
				if len(value_str) > 80:
					value_str = value_str[:80] + '...'
				print(f'      • {attr}: "{value_str}"')

		# Show data attributes
		if data_attrs:
			print('\n   💾 DATA ATTRIBUTES:')
			for attr in sorted(data_attrs):
				value_str = str(attrs[attr])
				if len(value_str) > 80:
					value_str = value_str[:80] + '...'
				print(f'      • {attr}: "{value_str}"')

		# Show ARIA attributes
		if aria_attrs:
			print('\n   ♿ ARIA ATTRIBUTES:')
			for attr in sorted(aria_attrs):
				value_str = str(attrs[attr])
				if len(value_str) > 80:
					value_str = value_str[:80] + '...'
				print(f'      • {attr}: "{value_str}"')

		# Show remaining attributes
		shown_attrs = set(important_attrs + event_attrs + data_attrs + aria_attrs)
		remaining_attrs = [k for k in attrs.keys() if k not in shown_attrs]
		if remaining_attrs:
			print('\n   🔧 OTHER ATTRIBUTES:')
			for attr in sorted(remaining_attrs):
				value_str = str(attrs[attr])
				if len(value_str) > 80:
					value_str = value_str[:80] + '...'
				print(f'      • {attr}: "{value_str}"')
	else:
		print('\n🏷️  No attributes found')

	# Enhanced scoring breakdown
	print('\n📊 DETAILED SCORING BREAKDOWN:')
	print(f'   • Final Score: {reasoning.get("score", 0)} points')
	print(f'   • Primary Reason: {reasoning.get("primary_reason", "unknown").replace("_", " ").title()}')
	print(f'   • Element Category: {reasoning.get("element_category", "unknown").replace("_", " ").title()}')

	# Score ranges for context with detailed explanations
	score = reasoning.get('score', 0)
	if score >= 70:
		print('   • Score Range: DEFINITE (70+ points) 🟢')
		print('     └─ Very likely to be interactive, high confidence')
	elif score >= 40:
		print('   • Score Range: LIKELY (40-69 points) 🟡')
		print('     └─ Probably interactive, good confidence')
	elif score >= 20:
		print('   • Score Range: POSSIBLE (20-39 points) 🟠')
		print('     └─ Possibly interactive, moderate confidence')
	elif score >= 10:
		print('   • Score Range: QUESTIONABLE (10-19 points) 🔴')
		print('     └─ Questionable interactivity, low confidence')
	else:
		print('   • Score Range: MINIMAL (<10 points) 🟣')
		print('     └─ Minimal interactivity, very low confidence')

	# Analysis recommendations
	print('\n🎯 ANALYSIS RECOMMENDATIONS:')
	confidence = reasoning.get('confidence', 'UNKNOWN')
	if confidence == 'DEFINITE':
		print('   ✅ This element should definitely be included in automation')
	elif confidence == 'LIKELY':
		print('   ✅ This element is probably safe to include in automation')
	elif confidence == 'POSSIBLE':
		print('   ⚠️  Consider including this element, but test thoroughly')
	elif confidence == 'QUESTIONABLE':
		print('   ⚠️  Use caution - this element might not be reliably interactive')
	elif confidence == 'MINIMAL':
		print('   ❌ This element is unlikely to be interactive - consider excluding')

	# Size analysis
	if width > 0 and height > 0:
		size_category = 'unknown'
		if width < 10 or height < 10:
			size_category = 'very small'
		elif width < 30 or height < 30:
			size_category = 'small'
		elif width < 100 or height < 100:
			size_category = 'medium'
		elif width < 300 or height < 300:
			size_category = 'large'
		else:
			size_category = 'very large'

		print('\n📏 SIZE ANALYSIS:')
		print(f'   • Size Category: {size_category.title()}')
		if size_category in ['very small', 'small']:
			print('   • Note: Small elements can still be interactive (buttons, icons, etc.)')
		elif size_category in ['very large']:
			print('   • Note: Large elements might be containers with nested interactive elements')

	print('=' * 80)


def cli_inspection_mode(interactive_elements: list[dict]) -> None:
	"""Interactive CLI inspection mode for elements."""

	if not interactive_elements:
		print('❌ No interactive elements to inspect.')
		return

	print('\n🔍 CLI INSPECTION MODE')
	print('=' * 50)
	print(f'Found {len(interactive_elements)} interactive elements')
	print('Commands:')
	print('  • Enter number (e.g., "1", "42") to inspect element')
	print('  • "list" - show all elements')
	print('  • "quit" or "q" - exit inspection mode')
	print('  • "help" - show this help')
	print('=' * 50)

	while True:
		try:
			cmd = input('\n🔍 Inspect element: ').strip().lower()

			if cmd in ['quit', 'q', 'exit']:
				print('👋 Exiting inspection mode.')
				break
			elif cmd in ['help', 'h']:
				print('\nCommands:')
				print('  • Enter number to inspect element')
				print('  • "list" - show all elements')
				print('  • "quit" - exit')
			elif cmd == 'list':
				print(f'\n📋 ALL {len(interactive_elements)} INTERACTIVE ELEMENTS:')
				for elem in sorted(interactive_elements, key=lambda x: x.get('interactive_index', 0)):
					idx = elem.get('interactive_index')
					reasoning = elem.get('reasoning', {})
					confidence = reasoning.get('confidence', 'UNKNOWN')
					score = reasoning.get('score', 0)
					element_type = reasoning.get('element_type', 'UNKNOWN')

					confidence_emoji = {
						'DEFINITE': '🟢',
						'LIKELY': '🟡',
						'POSSIBLE': '🟠',
						'QUESTIONABLE': '🔴',
						'REJECTED': '⚫',
					}.get(confidence, '❓')

					print(f'   [{idx:2d}] {element_type} - {confidence_emoji} {confidence} ({score} pts)')
			elif cmd.isdigit():
				element_number = int(cmd)
				inspect_element_by_number(interactive_elements, element_number)
			else:
				print(f'❌ Unknown command: "{cmd}". Type "help" for available commands.')

		except (EOFError, KeyboardInterrupt):
			print('\n👋 Exiting inspection mode.')
			break
		except Exception as e:
			print(f'❌ Error: {e}')


async def extract_and_save_ax_tree(dom_service: DOMService, url: str) -> str | None:
	"""Extract and save the complete AX tree as JSON for analysis."""
	try:
		print_section_header('🌳 EXTRACTING COMPLETE AX TREE FOR ANALYSIS')

		# Get the browser session to access the AX tree
		browser_session = dom_service.browser_session
		page = await browser_session.get_current_page()

		# Get the AX tree snapshot
		print('🔍 Getting AX tree snapshot...')
		ax_tree = await page.accessibility.snapshot()

		if not ax_tree:
			print('❌ Failed to get AX tree snapshot')
			return None

		# Create tmp directory if it doesn't exist
		tmp_dir = Path('tmp')
		tmp_dir.mkdir(exist_ok=True)

		# Clean URL for filename
		safe_url = url.replace('://', '_').replace('/', '_').replace('?', '_').replace('&', '_')[:50]
		timestamp = int(time.time())

		# Save complete AX tree
		ax_tree_file = tmp_dir / f'complete_ax_tree_{safe_url}_{timestamp}.json'

		print(f'💾 Saving AX tree to: {ax_tree_file}')
		async with aiofiles.open(ax_tree_file, 'w', encoding='utf-8') as f:
			await f.write(json.dumps(ax_tree, indent=2, ensure_ascii=False))

		# Analyze AX tree for interactive patterns
		interactive_patterns = analyze_ax_tree_patterns(ax_tree)

		# Save analysis
		analysis_file = tmp_dir / f'ax_tree_analysis_{safe_url}_{timestamp}.json'
		async with aiofiles.open(analysis_file, 'w', encoding='utf-8') as f:
			await f.write(json.dumps(interactive_patterns, indent=2, ensure_ascii=False))

		# Print absolute paths
		abs_ax_tree_path = ax_tree_file.absolute()
		abs_analysis_path = analysis_file.absolute()

		print(f'📁 Complete AX tree saved: {abs_ax_tree_path}')
		print(f'📁 Interactive analysis saved: {abs_analysis_path}')

		# Print key findings
		print('\n🔍 KEY INTERACTIVE PATTERNS FOUND:')
		print(f'   • Total nodes: {interactive_patterns["total_nodes"]}')
		print(f'   • Clickable nodes: {interactive_patterns["clickable_count"]}')
		print(f'   • Focusable nodes: {interactive_patterns["focusable_count"]}')
		print(f'   • Nodes with actions: {interactive_patterns["actionable_count"]}')

		print('\n🎯 TOP INTERACTIVE ROLES:')
		for role, count in list(interactive_patterns['roles_with_actions'].items())[:10]:
			print(f'   • {role}: {count} nodes')

		print('\n📋 COMMON INTERACTIVE PROPERTIES:')
		for prop, count in list(interactive_patterns['interactive_properties'].items())[:10]:
			print(f'   • {prop}: {count} occurrences')

		return str(abs_ax_tree_path)

	except Exception as e:
		print(f'❌ Error extracting AX tree: {e}')
		traceback.print_exc()
		return None


def analyze_ax_tree_patterns(ax_tree: dict) -> dict:
	"""Analyze AX tree to identify patterns that indicate interactivity."""

	def traverse_node(node, results):
		"""Recursively traverse AX tree nodes."""
		if not isinstance(node, dict):
			return

		results['total_nodes'] += 1

		# Get node properties
		role = node.get('role', '').lower()
		name = node.get('name', '')
		properties = node.get('properties', {})

		# Track roles
		if role:
			results['all_roles'][role] = results['all_roles'].get(role, 0) + 1

		# Check for interactive indicators
		is_interactive = False

		# Check if clickable
		if properties.get('clickable') or 'click' in str(properties).lower():
			results['clickable_count'] += 1
			is_interactive = True

		# Check if focusable
		if properties.get('focusable') or node.get('focusable'):
			results['focusable_count'] += 1
			is_interactive = True

		# Check for actions
		actions = node.get('actions', [])
		if actions:
			results['actionable_count'] += 1
			is_interactive = True
			for action in actions:
				action_name = action if isinstance(action, str) else str(action)
				results['action_types'][action_name] = results['action_types'].get(action_name, 0) + 1

		# Interactive roles
		interactive_roles = [
			'button',
			'link',
			'menuitem',
			'tab',
			'checkbox',
			'radio',
			'textbox',
			'combobox',
			'listbox',
			'option',
			'slider',
			'spinbutton',
			'switch',
			'searchbox',
			'menuitemcheckbox',
			'menuitemradio',
			'treeitem',
		]

		if role in interactive_roles:
			is_interactive = True
			results['roles_with_actions'][role] = results['roles_with_actions'].get(role, 0) + 1

		# Check for cursor pointer indication in computed styles or properties
		computed = node.get('computed', {})
		if computed:
			cursor = computed.get('cursor', '').lower()
			if cursor == 'pointer':
				results['cursor_pointer_count'] += 1
				is_interactive = True

		# Track interactive properties
		if is_interactive:
			results['interactive_nodes'] += 1

			# Collect all properties from interactive nodes
			for key, value in properties.items():
				prop_key = f'{key}={value}'
				results['interactive_properties'][prop_key] = results['interactive_properties'].get(prop_key, 0) + 1

			# Track interactive node with details
			results['interactive_node_details'].append(
				{
					'role': role,
					'name': name[:50] if name else '',
					'properties': properties,
					'actions': actions,
					'computed': computed,
				}
			)

		# Traverse children
		children = node.get('children', [])
		for child in children:
			traverse_node(child, results)

	# Initialize results
	results = {
		'total_nodes': 0,
		'interactive_nodes': 0,
		'clickable_count': 0,
		'focusable_count': 0,
		'actionable_count': 0,
		'cursor_pointer_count': 0,
		'all_roles': {},
		'roles_with_actions': {},
		'action_types': {},
		'interactive_properties': {},
		'interactive_node_details': [],
	}

	# Start traversal
	traverse_node(ax_tree, results)

	# Sort results by frequency
	results['all_roles'] = dict(sorted(results['all_roles'].items(), key=lambda x: x[1], reverse=True))
	results['roles_with_actions'] = dict(sorted(results['roles_with_actions'].items(), key=lambda x: x[1], reverse=True))
	results['action_types'] = dict(sorted(results['action_types'].items(), key=lambda x: x[1], reverse=True))
	results['interactive_properties'] = dict(sorted(results['interactive_properties'].items(), key=lambda x: x[1], reverse=True))

	return results


if __name__ == '__main__':
	asyncio.run(main())
