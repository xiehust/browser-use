# @file purpose: Serializes enhanced DOM trees to string format for LLM consumption

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from cdp_use.cdp.accessibility.types import AXPropertyName

from browser_use.dom.views import DEFAULT_INCLUDE_ATTRIBUTES, EnhancedDOMTreeNode, NodeType


class ElementGroup(Enum):
	"""Types of element groups for semantic organization."""

	FORM = 'FORM'
	NAVIGATION = 'NAVIGATION'
	DROPDOWN = 'DROPDOWN'
	MENU = 'MENU'
	TABLE = 'TABLE'
	LIST = 'LIST'
	TOOLBAR = 'TOOLBAR'
	TABS = 'TABS'
	ACCORDION = 'ACCORDION'
	MODAL = 'MODAL'
	CAROUSEL = 'CAROUSEL'
	CONTENT = 'CONTENT'
	FOOTER = 'FOOTER'
	HEADER = 'HEADER'
	SIDEBAR = 'SIDEBAR'


@dataclass(slots=True)
class CompressedElement:
	"""Compressed representation of an interactive element."""

	index: int
	element_type: str
	action_type: str  # click, input, select, etc.
	label: str
	target: Optional[str] = None  # href, action, etc.
	attributes: Dict[str, str] = field(default_factory=dict)
	context: Optional[str] = None  # parent context
	group_type: Optional[ElementGroup] = None
	children: List['CompressedElement'] = field(default_factory=list)


@dataclass(slots=True)
class SemanticGroup:
	"""A semantic group of related elements."""

	group_type: ElementGroup
	title: str
	elements: List[CompressedElement] = field(default_factory=list)
	context: Optional[str] = None


@dataclass(slots=True)
class ElementAnalysis:
	"""Comprehensive element analysis with scoring and reasoning."""

	primary_reason: str
	confidence: str
	confidence_description: str
	score: int
	element_type: str
	element_category: str
	evidence: List[str] = field(default_factory=list)
	warnings: List[str] = field(default_factory=list)
	context_info: List[str] = field(default_factory=list)
	interactive_indicators: Dict[str, bool] = field(default_factory=dict)
	# Enhanced data from DOM tree
	event_listeners: List[str] = field(default_factory=list)
	computed_styles_info: Dict[str, str] = field(default_factory=dict)
	accessibility_info: Dict[str, str] = field(default_factory=dict)
	positioning_info: Dict[str, str] = field(default_factory=dict)
	nested_conflict_parent: int | None = None  # Reference to parent that would trigger same action

	@classmethod
	def analyze_element_interactivity(cls, node: EnhancedDOMTreeNode) -> 'ElementAnalysis':
		"""Analyze element interactivity with ENHANCED scoring, event listeners, and comprehensive DOM data extraction."""
		element_name = node.node_name.upper()
		attributes = node.attributes or {}

		# Initialize scoring system
		score = 0
		evidence = []
		warnings = []
		element_category = 'unknown'
		event_listeners = []
		computed_styles_info = {}
		accessibility_info = {}
		positioning_info = {}

		# **EXTRACT COMPREHENSIVE DOM DATA**
		cls._extract_enhanced_dom_data(node, computed_styles_info, accessibility_info, positioning_info, event_listeners)

		# Enhanced button detection - be much more inclusive
		button_indicators = [
			'btn',
			'button',
			'click',
			'submit',
			'action',
			'trigger',
			'toggle',
			'press',
			'tap',
			'select',
			'choose',
			'confirm',
			'cancel',
			'ok',
			'yes',
			'no',
			'close',
			'open',
			'show',
			'hide',
			'expand',
			'collapse',
			'menu',
			'dropdown',
			'popup',
			'modal',
			'dialog',
			'tab',
			'nav',
			'link',
			'item',
			'option',
			'choice',
		]

		# **TIER 1: HIGHEST PRIORITY (90-100 points) - Core interactive elements**
		if element_name in ['INPUT', 'BUTTON', 'SELECT', 'TEXTAREA']:
			element_category = 'form_control'
			score += 120  # BOOSTED from 90 to 120
			evidence.append(f'HIGH PRIORITY: Core form element: {element_name}')

			if attributes.get('type'):
				input_type = attributes['type'].lower()
				evidence.append(f'Input type: {input_type}')
				if input_type in ['submit', 'button', 'reset']:
					score += 15  # BOOSTED from 10 to 15, Total: 135 points
				elif input_type in ['text', 'email', 'password', 'search', 'tel', 'url']:
					score += 12  # BOOSTED from 8 to 12, Total: 132 points
				elif input_type in ['checkbox', 'radio']:
					score += 10  # BOOSTED from 6 to 10, Total: 130 points

			# Don't exclude disabled elements, just score them lower
			if attributes.get('disabled') == 'true':
				score = max(40, score - 50)  # BOOSTED minimum from 25 to 40
				warnings.append('Element is disabled but still detectable')

		# **COLLECT ALL INTERACTIVE INDICATORS FIRST**
		interactive_indicators = cls._collect_all_interactive_indicators(
			node, attributes, computed_styles_info, accessibility_info, event_listeners, button_indicators
		)

		# **ASSIGN SINGLE SCORE BASED ON STRONGEST INDICATOR**
		primary_score, primary_reason_found, category_found = cls._calculate_primary_interactive_score(
			element_name, attributes, interactive_indicators, evidence
		)

		score += primary_score
		if element_category == 'unknown':
			element_category = category_found

		# **ENHANCED POSITIONING AND VISIBILITY ANALYSIS** - Only add minor boosts here
		positioning_boost = cls._analyze_positioning_and_visibility(
			node, positioning_info, computed_styles_info, evidence, warnings
		)
		score += positioning_boost

		# **DETERMINE FINAL CONFIDENCE** - Adjusted thresholds for boosted scoring
		if score >= 110:  # BOOSTED from 85 to 110
			confidence = 'DEFINITE'
			confidence_description = 'Very likely interactive (high confidence)'
		elif score >= 80:  # BOOSTED from 65 to 80
			confidence = 'LIKELY'
			confidence_description = 'Probably interactive (good confidence)'
		elif score >= 50:  # BOOSTED from 40 to 50
			confidence = 'POSSIBLE'
			confidence_description = 'Possibly interactive (moderate confidence)'
		elif score >= 25:  # BOOSTED from 20 to 25
			confidence = 'QUESTIONABLE'
			confidence_description = 'Questionable interactivity (low confidence)'
		else:
			confidence = 'MINIMAL'
			confidence_description = 'Minimal interactivity (very low confidence)'

		# **DETERMINE PRIMARY REASON**
		primary_reason = element_category if element_category != 'unknown' else 'mixed_indicators'

		# **ADD ENHANCED CONTEXT INFORMATION**
		context_info = []
		if attributes.get('id'):
			context_info.append(f'ID: {attributes["id"][:30]}')
		if attributes.get('class'):
			context_info.append(f'Class: {attributes["class"][:40]}')
		if event_listeners:
			context_info.append(f'Event Listeners: {len(event_listeners)} detected')
		if computed_styles_info.get('position'):
			context_info.append(f'Position: {computed_styles_info["position"]}')

		# **ENHANCED INTERACTIVE INDICATORS**
		# Get comprehensive cursor info for indicators
		indicator_has_cursor, indicator_cursor_type, indicator_cursor_score = cls._has_any_interactive_cursor(
			node, computed_styles_info
		)

		interactive_indicators = {
			'has_onclick': 'onclick' in attributes,
			'has_href': 'href' in attributes,
			'has_tabindex': 'tabindex' in attributes,
			'has_role': 'role' in attributes,
			'has_aria_label': 'aria-label' in attributes,
			'has_data_attrs': any(k.startswith('data-') for k in attributes.keys()),
			'has_button_classes': any(indicator in attributes.get('class', '').lower() for indicator in button_indicators),
			'has_pointer_cursor': cls._has_cursor_pointer(node, computed_styles_info),  # Keep for backwards compatibility
			'has_any_interactive_cursor': indicator_has_cursor,  # NEW: Comprehensive cursor detection
			'cursor_type': indicator_cursor_type if indicator_has_cursor else '',  # NEW: Specific cursor type
			'cursor_score': indicator_cursor_score if indicator_has_cursor else 0,  # NEW: Cursor-based score
			'has_event_handlers': any(k.startswith('on') for k in attributes.keys()),
			'has_event_listeners': len(event_listeners) > 0,
			'has_fixed_position': computed_styles_info.get('position') == 'fixed',
			'has_high_z_index': cls._has_high_z_index(computed_styles_info),
			'is_focusable': accessibility_info.get('focusable') == 'true',
		}

		return cls(
			primary_reason=primary_reason,
			confidence=confidence,
			confidence_description=confidence_description,
			score=score,
			element_type=element_name,
			element_category=element_category,
			evidence=evidence,
			warnings=warnings,
			context_info=context_info,
			interactive_indicators=interactive_indicators,
			event_listeners=event_listeners,
			computed_styles_info=computed_styles_info,
			accessibility_info=accessibility_info,
			positioning_info=positioning_info,
		)

	@classmethod
	def _collect_all_interactive_indicators(
		cls,
		node: EnhancedDOMTreeNode,
		attributes: Dict[str, str],
		computed_styles_info: Dict[str, str],
		accessibility_info: Dict[str, str],
		event_listeners: List[str],
		button_indicators: List[str],
	) -> Dict[str, Any]:
		"""Collect all interactive indicators without scoring to avoid double-counting."""
		indicators = {}

		# Check cursor styling
		has_cursor, cursor_type, cursor_score = cls._has_any_interactive_cursor(node, computed_styles_info)
		indicators['has_cursor'] = has_cursor
		indicators['cursor_type'] = cursor_type
		indicators['cursor_score'] = cursor_score

		# Check accessibility tree focusable
		indicators['is_focusable'] = accessibility_info.get('focusable') == 'true'

		# Check tabindex
		indicators['has_tabindex'] = 'tabindex' in attributes
		indicators['tabindex_value'] = None
		if indicators['has_tabindex']:
			try:
				indicators['tabindex_value'] = int(attributes['tabindex'])
			except ValueError:
				pass

		# Check event listeners
		indicators['has_event_listeners'] = len(event_listeners) > 0
		indicators['event_listeners'] = event_listeners

		# Check onclick
		indicators['has_onclick'] = 'onclick' in attributes

		# Check href
		indicators['has_href'] = 'href' in attributes
		indicators['href_value'] = attributes.get('href', '')

		# Check role
		indicators['has_role'] = 'role' in attributes
		indicators['role_value'] = attributes.get('role', '').lower()

		# Check button-like classes
		indicators['has_button_classes'] = False
		if attributes.get('class'):
			classes = attributes['class'].lower()
			indicators['has_button_classes'] = any(indicator in classes for indicator in button_indicators)

		# Check AX role
		indicators['ax_role'] = accessibility_info.get('role', '').lower()

		return indicators

	@classmethod
	def _calculate_primary_interactive_score(
		cls, element_name: str, attributes: Dict[str, str], indicators: Dict[str, Any], evidence: List[str]
	) -> tuple[int, str, str]:
		"""Calculate a single primary score based on the strongest interactive indicator."""
		max_score = 0
		primary_reason = 'unknown'
		category = 'unknown'

		# **TIER 1: HIGHEST PRIORITY (120-140 points) - Core form elements**
		if element_name in ['INPUT', 'BUTTON', 'SELECT', 'TEXTAREA']:
			max_score = 120  # BOOSTED from 90 to 120
			primary_reason = 'core_form_element'
			category = 'form_control'
			evidence.append(f'TIER 1: Core form element: {element_name} (+120)')

			# Additional scoring for input types
			if attributes.get('type'):
				input_type = attributes['type'].lower()
				if input_type in ['submit', 'button', 'reset']:
					max_score = 135  # BOOSTED from 100 to 135
					evidence.append(f'Enhanced form element: {input_type} (+15)')

		# **TIER 2: VERY HIGH PRIORITY (100-115 points) - Focusable elements**
		elif indicators['is_focusable']:
			max_score = 110  # BOOSTED from 85 to 110
			primary_reason = 'ax_focusable'
			category = 'focusable'
			evidence.append('TIER 2: Accessibility tree marked as focusable (+110)')

		# **TIER 3: HIGH PRIORITY (85-99 points) - Links and explicit handlers**
		elif element_name == 'A':
			max_score = 85  # BOOSTED from 70 to 85
			primary_reason = 'link_element'
			category = 'link'
			if indicators['has_href']:
				max_score = 95  # BOOSTED from 80 to 95
				evidence.append('TIER 3: Link with href (+95)')
			else:
				evidence.append('TIER 3: Link element without href (+85)')

		elif indicators['has_onclick']:
			max_score = 90  # BOOSTED from 75 to 90
			primary_reason = 'onclick_handler'
			category = 'onclick_handler'
			evidence.append('TIER 3: Has onclick event handler (+90)')

		elif indicators['has_event_listeners']:
			listener_score = cls._score_event_listeners_simple(indicators['event_listeners'])
			if listener_score >= 70:
				max_score = 90  # BOOSTED from 75 to 90
				primary_reason = 'strong_event_listeners'
				category = 'event_driven'
				evidence.append('TIER 3: Strong event listeners detected (+90)')
			elif listener_score >= 50:
				max_score = 80  # BOOSTED from 65 to 80
				primary_reason = 'event_listeners'
				category = 'event_driven'
				evidence.append('TIER 3: Event listeners detected (+80)')

		# **TIER 4: MEDIUM-HIGH PRIORITY (60-100 points) - ARIA roles and interactive cursors**
		elif indicators['has_role'] and indicators['role_value']:
			role = indicators['role_value']
			interactive_roles = {
				'button': 100,  # BOOSTED to 100 per user request
				'link': 78,  # BOOSTED from 65 to 78
				'menuitem': 72,  # BOOSTED from 60 to 72
				'tab': 72,  # BOOSTED from 60 to 72
				'option': 67,  # BOOSTED from 55 to 67
				'checkbox': 67,  # BOOSTED from 55 to 67
				'radio': 67,  # BOOSTED from 55 to 67
				'switch': 67,  # BOOSTED from 55 to 67
				'slider': 62,  # BOOSTED from 50 to 62
				'spinbutton': 62,  # BOOSTED from 50 to 62
				'combobox': 62,  # BOOSTED from 50 to 62
				'textbox': 62,  # BOOSTED from 50 to 62
			}
			if role in interactive_roles:
				max_score = interactive_roles[role]
				primary_reason = 'aria_role'
				category = 'aria_role'
				evidence.append(f'TIER 4: ARIA role: {role} (+{max_score})')

		elif indicators['has_cursor'] and indicators['cursor_score'] >= 50:
			# Special handling for pointer cursor to give it 100 points
			if indicators['cursor_type'] == 'pointer':
				max_score = 100  # BOOSTED to 100 per user request
			else:
				max_score = min(
					78, indicators['cursor_score'] + 15
				)  # BOOSTED from min(65, cursor_score) to min(78, cursor_score + 15)
			primary_reason = 'interactive_cursor'
			category = f'cursor_{indicators["cursor_type"].replace("-", "_")}'
			evidence.append(f'TIER 4: Interactive cursor: {indicators["cursor_type"]} (+{max_score})')

		# **TIER 5: MEDIUM PRIORITY (40-59 points) - Tabindex and weaker cursors**
		elif indicators['has_tabindex'] and indicators['tabindex_value'] is not None:
			if indicators['tabindex_value'] >= 0:
				max_score = 55  # BOOSTED from 45 to 55
				primary_reason = 'positive_tabindex'
				category = 'focusable'
				evidence.append(f'TIER 5: Focusable (tabindex: {indicators["tabindex_value"]}) (+55)')
			elif indicators['tabindex_value'] == -1:
				max_score = 45  # BOOSTED from 35 to 45
				primary_reason = 'programmatic_tabindex'
				category = 'focusable'
				evidence.append('TIER 5: Programmatically focusable (tabindex: -1) (+45)')

		elif indicators['has_cursor'] and indicators['cursor_score'] >= 30:
			max_score = min(
				55, indicators['cursor_score'] + 15
			)  # BOOSTED from min(45, cursor_score) to min(55, cursor_score + 15)
			primary_reason = 'weak_cursor'
			category = f'cursor_{indicators["cursor_type"].replace("-", "_")}'
			evidence.append(f'TIER 5: Weak interactive cursor: {indicators["cursor_type"]} (+{max_score})')

		# **TIER 6: LOW PRIORITY (15-39 points) - Container elements with hints**
		elif element_name in ['DIV', 'SPAN', 'LI', 'TD', 'TH', 'SECTION', 'ARTICLE']:
			container_score = 15  # BOOSTED from 10 to 15

			# Check for button-like classes
			if indicators['has_button_classes']:
				container_score += 25  # BOOSTED from 20 to 25
				evidence.append('Container with button-like classes (+25)')

			# Check for any cursor hint
			if indicators['has_cursor']:
				container_score += 15  # BOOSTED from 10 to 15
				evidence.append(f'Container with cursor hint: {indicators["cursor_type"]} (+15)')

			if container_score > 15:
				max_score = container_score
				primary_reason = 'interactive_container'
				category = 'container'

		return max_score, primary_reason, category

	@classmethod
	def _score_event_listeners_simple(cls, event_listeners: List[str]) -> int:
		"""Simple scoring for event listeners without adding to evidence."""
		score = 0
		high_value_events = ['onclick', 'onmousedown', 'onkeydown', '@click', '(click)']
		medium_value_events = ['onchange', 'oninput', 'onsubmit', 'onfocus', 'onblur']

		for listener in event_listeners:
			if any(high_event in listener.lower() for high_event in high_value_events):
				score += 70
			elif any(med_event in listener.lower() for med_event in medium_value_events):
				score += 40
			else:
				score += 20

		return min(score, 80)  # Cap at 80 points

	@classmethod
	def _extract_enhanced_dom_data(
		cls,
		node: EnhancedDOMTreeNode,
		computed_styles_info: Dict[str, str],
		accessibility_info: Dict[str, str],
		positioning_info: Dict[str, str],
		event_listeners: List[str],
	) -> None:
		"""Extract comprehensive data from enhanced DOM tree."""

		# **EXTRACT COMPUTED STYLES**
		if node.snapshot_node and hasattr(node.snapshot_node, 'computed_styles'):
			styles = node.snapshot_node.computed_styles or {}
			# Extract key style properties
			style_properties = [
				'cursor',
				'position',
				'z-index',
				'display',
				'visibility',
				'opacity',
				'pointer-events',
				'user-select',
				'background-color',
				'border',
				'outline',
			]
			for prop in style_properties:
				if prop in styles:
					computed_styles_info[prop] = styles[prop]

		# **EXTRACT ACCESSIBILITY INFORMATION**
		if node.ax_node:
			if node.ax_node.role:
				accessibility_info['role'] = node.ax_node.role
			if node.ax_node.name:
				accessibility_info['name'] = node.ax_node.name
			if node.ax_node.description:
				accessibility_info['description'] = node.ax_node.description

			# Extract AX properties
			if node.ax_node.properties:
				for prop in node.ax_node.properties:
					if prop.name == AXPropertyName.FOCUSABLE:
						accessibility_info['focusable'] = str(prop.value)
					elif prop.name == AXPropertyName.FOCUSED:
						accessibility_info['focused'] = str(prop.value)
					elif prop.name == AXPropertyName.DISABLED:
						accessibility_info['disabled'] = str(prop.value)

		# **EXTRACT POSITIONING INFORMATION**
		if node.snapshot_node and hasattr(node.snapshot_node, 'bounding_box'):
			bbox = node.snapshot_node.bounding_box
			if bbox:
				positioning_info['x'] = str(bbox.get('x', 0))
				positioning_info['y'] = str(bbox.get('y', 0))
				positioning_info['width'] = str(bbox.get('width', 0))
				positioning_info['height'] = str(bbox.get('height', 0))

		# **EXTRACT EVENT LISTENERS** (this would need CDP integration)
		# For now, we'll detect common event attributes
		if node.attributes:
			event_attrs = [k for k in node.attributes.keys() if k.startswith('on')]
			event_listeners.extend(event_attrs)

			# Detect framework-specific event attributes
			framework_events = ['@click', 'v-on:', '(click)', 'ng-click', 'data-action']
			for attr in node.attributes:
				if any(framework in attr.lower() for framework in framework_events):
					event_listeners.append(f'framework:{attr}')

	@classmethod
	def _has_cursor_pointer(cls, node: EnhancedDOMTreeNode, computed_styles_info: Dict[str, str]) -> bool:
		"""Enhanced cursor pointer detection."""
		# Check computed styles info first (cached)
		if computed_styles_info.get('cursor') == 'pointer':
			return True

		# Check snapshot node
		if node.snapshot_node:
			if getattr(node.snapshot_node, 'cursor_style', None) == 'pointer':
				return True
			if hasattr(node.snapshot_node, 'computed_styles'):
				styles = node.snapshot_node.computed_styles or {}
				if styles.get('cursor') == 'pointer':
					return True

		return False

	@classmethod
	def _has_any_interactive_cursor(
		cls, node: EnhancedDOMTreeNode, computed_styles_info: Dict[str, str]
	) -> tuple[bool, str, int]:
		"""Detect ANY cursor styling that indicates interactivity and return cursor type with score."""
		# Define all interactive cursor styles with their scores
		interactive_cursors = {
			# Highest priority cursors (100+ points)
			'pointer': 100,  # BOOSTED to 100 per user request
			'hand': 85,  # Legacy IE cursor for clickable elements
			# High priority cursors (70+ points)
			'grab': 75,  # For draggable elements
			'grabbing': 75,  # For elements being dragged
			'move': 70,  # For moveable elements
			'copy': 70,  # For elements that can be copied
			'alias': 70,  # For elements that create shortcuts/links
			# Medium-high priority cursors (50+ points)
			'crosshair': 60,  # For selection/drawing tools
			'cell': 55,  # For table cells (often clickable)
			'context-menu': 55,  # For elements that show context menu
			'zoom-in': 50,  # For zoomable elements
			'zoom-out': 50,  # For zoomable elements
			# Medium priority cursors (30+ points) - resizing cursors
			'col-resize': 35,  # Column resizing
			'row-resize': 35,  # Row resizing
			'n-resize': 30,  # North resizing
			's-resize': 30,  # South resizing
			'e-resize': 30,  # East resizing
			'w-resize': 30,  # West resizing
			'ne-resize': 30,  # Northeast resizing
			'nw-resize': 30,  # Northwest resizing
			'se-resize': 30,  # Southeast resizing
			'sw-resize': 30,  # Southwest resizing
			'ew-resize': 35,  # East-west resizing
			'ns-resize': 35,  # North-south resizing
			'nesw-resize': 35,  # Northeast-southwest resizing
			'nwse-resize': 35,  # Northwest-southeast resizing
			# Lower priority but still interactive cursors (20+ points)
			'all-scroll': 25,  # For scrollable areas
			'vertical-text': 20,  # For vertical text selection
			'no-drop': 20,  # For drop targets (still interactive)
			'not-allowed': 15,  # Disabled but still interactive context
			# Text cursors (15+ points) - still indicate some interactivity
			'text': 15,  # Text selection
			'vertical-text': 15,  # Vertical text selection
		}

		def get_cursor_from_source(cursor_value: str | None) -> tuple[bool, str, int]:
			"""Helper to check cursor value and return details."""
			if not cursor_value:
				return False, '', 0

			cursor_lower = cursor_value.lower().strip()

			# Check for exact matches first
			if cursor_lower in interactive_cursors:
				score = interactive_cursors[cursor_lower]
				return True, cursor_lower, score

			# Check for cursor values with fallbacks (e.g., "pointer, auto")
			for cursor_type, score in interactive_cursors.items():
				if cursor_type in cursor_lower:
					return True, cursor_type, score

			return False, cursor_lower, 0

		# Check computed styles info first (cached)
		cursor_value = computed_styles_info.get('cursor')
		if cursor_value:
			has_cursor, cursor_type, score = get_cursor_from_source(cursor_value)
			if has_cursor:
				return True, cursor_type, score

		# Check snapshot node cursor_style attribute
		if node.snapshot_node:
			cursor_style = getattr(node.snapshot_node, 'cursor_style', None)
			if cursor_style:
				has_cursor, cursor_type, score = get_cursor_from_source(cursor_style)
				if has_cursor:
					return True, cursor_type, score

			# Check snapshot node computed_styles
			if hasattr(node.snapshot_node, 'computed_styles'):
				styles = node.snapshot_node.computed_styles or {}
				cursor_value = styles.get('cursor')
				if cursor_value:
					has_cursor, cursor_type, score = get_cursor_from_source(cursor_value)
					if has_cursor:
						return True, cursor_type, score

		return False, '', 0

	@classmethod
	def _score_event_listeners(cls, event_listeners: List[str], evidence: List[str]) -> int:
		"""Score based on detected event listeners."""
		score = 0
		high_value_events = ['onclick', 'onmousedown', 'onkeydown', '@click', '(click)']
		medium_value_events = ['onchange', 'oninput', 'onsubmit', 'onfocus', 'onblur']

		for listener in event_listeners:
			if any(high_event in listener.lower() for high_event in high_value_events):
				score += 70
				evidence.append(f'High-value event listener: {listener}')
			elif any(med_event in listener.lower() for med_event in medium_value_events):
				score += 40
				evidence.append(f'Medium-value event listener: {listener}')
			else:
				score += 20
				evidence.append(f'Event listener: {listener}')

		return min(score, 80)  # Cap at 80 points

	@classmethod
	def _analyze_container_interactivity(
		cls,
		node: EnhancedDOMTreeNode,
		attributes: Dict[str, str],
		button_indicators: List[str],
		computed_styles_info: Dict[str, str],
		evidence: List[str],
	) -> int:
		"""Analyze container elements for interactivity with enhanced detection."""
		container_score = 10  # Base score

		# Enhanced CSS class analysis
		css_classes = attributes.get('class', '').lower()
		button_score_boost = 0
		for indicator in button_indicators:
			if indicator in css_classes:
				button_score_boost += 20  # INCREASED from 15
				evidence.append(f'Button-like class: {indicator}')

		container_score += button_score_boost

		# Check for ANY interactive cursor (high value for containers)
		has_cursor, cursor_type, cursor_score = cls._has_any_interactive_cursor(node, computed_styles_info)
		if has_cursor:
			# Scale the container boost based on cursor importance
			container_cursor_boost = min(60, cursor_score + 20)  # Add 20 for container context
			container_score += container_cursor_boost
			evidence.append(f'Container with {cursor_type} cursor (+{container_cursor_boost})')

		# Enhanced ARIA attribute detection
		interactive_aria = [
			'aria-label',
			'aria-expanded',
			'aria-selected',
			'aria-pressed',
			'aria-checked',
			'aria-controls',
			'aria-haspopup',
			'aria-live',
			'aria-hidden',
		]
		found_aria = [attr for attr in interactive_aria if attr in attributes]
		if found_aria:
			aria_boost = len(found_aria) * 8  # INCREASED from 5
			container_score += aria_boost
			evidence.append(f'Interactive ARIA attributes: {", ".join(found_aria)} (+{aria_boost})')

		return container_score

	@classmethod
	def _analyze_positioning_and_visibility(
		cls,
		node: EnhancedDOMTreeNode,
		positioning_info: Dict[str, str],
		computed_styles_info: Dict[str, str],
		evidence: List[str],
		warnings: List[str],
	) -> int:
		"""Analyze positioning and visibility for interactive likelihood."""
		score_boost = 0

		# Fixed/absolute positioned elements are often interactive overlays
		position = computed_styles_info.get('position', '')
		if position in ['fixed', 'absolute']:
			score_boost += 15
			evidence.append(f'Positioned element ({position}) likely interactive (+15)')

		# High z-index elements are often interactive overlays
		if cls._has_high_z_index(computed_styles_info):
			score_boost += 10
			evidence.append('High z-index element (+10)')

		# Check for interactive styling
		if computed_styles_info.get('pointer-events') == 'none':
			score_boost -= 20
			warnings.append('Element has pointer-events: none (-20)')

		return score_boost

	@classmethod
	def _analyze_accessibility_properties(
		cls, node: EnhancedDOMTreeNode, accessibility_info: Dict[str, str], evidence: List[str]
	) -> int:
		"""Analyze accessibility properties for enhanced scoring."""
		score_boost = 0

		if accessibility_info.get('focusable') == 'true':
			score_boost += 70  # MUCH HIGHER - focusable elements are definitely interactive
			evidence.append('Accessibility tree marked as focusable (+70)')

		if accessibility_info.get('role'):
			role = accessibility_info['role'].lower()
			interactive_ax_roles = {
				'button': 25,
				'link': 25,
				'menuitem': 20,
				'tab': 20,
				'checkbox': 20,
				'radio': 20,
				'slider': 15,
				'textbox': 15,
			}
			if role in interactive_ax_roles:
				boost = interactive_ax_roles[role]
				score_boost += boost
				evidence.append(f'Interactive AX role: {role} (+{boost})')

		return score_boost

	@classmethod
	def _has_high_z_index(cls, computed_styles_info: Dict[str, str]) -> bool:
		"""Check if element has a high z-index value."""
		z_index = computed_styles_info.get('z-index', '')
		if z_index and z_index.isdigit():
			return int(z_index) > 100
		return False

	@classmethod
	def detect_nested_conflicts(cls, analyses: List['ElementAnalysis'], nodes: List[EnhancedDOMTreeNode]) -> None:
		"""Detect and resolve conflicts where nested elements would trigger the same action."""
		# This would need to be called after analyzing all elements
		# Implementation would compare parent-child relationships and action targets
		for i, analysis in enumerate(analyses):
			node = nodes[i]

			# Check if this element has a parent that would trigger the same action
			parent_action = cls._get_element_action(node.parent_node) if hasattr(node, 'parent_node') else None
			current_action = cls._get_element_action(node)

			if parent_action and current_action and parent_action == current_action:
				# Parent and child would do the same thing
				# Prefer the parent (more semantic) and reduce child score
				analysis.score = max(10, analysis.score - 50)
				analysis.warnings.append('Nested element with same action as parent - score reduced')
				analysis.nested_conflict_parent = i  # Reference to parent

	@classmethod
	def _get_element_action(cls, node: EnhancedDOMTreeNode | None) -> str | None:
		"""Extract the action that an element would perform."""
		if not node or not node.attributes:
			return None

		# Check various action indicators
		if 'href' in node.attributes:
			return f'navigate:{node.attributes["href"]}'
		if 'onclick' in node.attributes:
			return f'onclick:{node.attributes["onclick"]}'
		if 'data-action' in node.attributes:
			return f'data-action:{node.attributes["data-action"]}'

		return None


@dataclass(slots=True)
class PerformanceMetrics:
	"""Track performance metrics for optimization analysis."""

	start_time: float = field(default_factory=time.time)
	ax_collection_time: float = 0.0
	filtering_time: float = 0.0
	tree_building_time: float = 0.0
	indexing_time: float = 0.0
	serialization_time: float = 0.0
	total_time: float = 0.0

	# Element counts
	total_dom_nodes: int = 0
	ax_candidates: int = 0
	dom_candidates: int = 0
	after_visibility_filter: int = 0
	after_viewport_filter: int = 0
	after_deduplication: int = 0
	final_interactive_count: int = 0

	# Filtering statistics
	skipped_structural: int = 0
	skipped_invisible: int = 0
	skipped_outside_viewport: int = 0
	skipped_duplicates: int = 0
	skipped_calendar_cells: int = 0

	def finish(self):
		"""Calculate total time."""
		self.total_time = time.time() - self.start_time

	def log_summary(self):
		"""Log comprehensive performance summary."""
		print('\n' + '=' * 80)
		print('🚀 DOM SERIALIZER PERFORMANCE REPORT')
		print('=' * 80)

		print('⏱️  TIMING BREAKDOWN:')
		print(f'   • Total Time:           {self.total_time:.3f}s')
		print(
			f'   • AX Collection:        {self.ax_collection_time:.3f}s ({self.ax_collection_time / self.total_time * 100:.1f}%)'
		)
		print(f'   • Filtering:            {self.filtering_time:.3f}s ({self.filtering_time / self.total_time * 100:.1f}%)')
		print(
			f'   • Tree Building:        {self.tree_building_time:.3f}s ({self.tree_building_time / self.total_time * 100:.1f}%)'
		)
		print(f'   • Indexing:             {self.indexing_time:.3f}s ({self.indexing_time / self.total_time * 100:.1f}%)')
		print(
			f'   • Serialization:        {self.serialization_time:.3f}s ({self.serialization_time / self.total_time * 100:.1f}%)'
		)

		print('\n📊 ELEMENT STATISTICS:')
		print(f'   • Total DOM Nodes:      {self.total_dom_nodes:,}')
		print(f'   • AX Candidates:        {self.ax_candidates:,}')
		print(f'   • DOM Candidates:       {self.dom_candidates:,}')
		print(f'   • After Visibility:     {self.after_visibility_filter:,}')
		print(f'   • After Viewport:       {self.after_viewport_filter:,}')
		print(f'   • After Deduplication:  {self.after_deduplication:,}')
		print(f'   • Final Interactive:    {self.final_interactive_count:,}')

		print('\n🗑️  FILTERING EFFICIENCY:')
		print(f'   • Skipped Structural:   {self.skipped_structural:,}')
		print(f'   • Skipped Invisible:    {self.skipped_invisible:,}')
		print(f'   • Skipped Viewport:     {self.skipped_outside_viewport:,}')
		print(f'   • Skipped Duplicates:   {self.skipped_duplicates:,}')
		print(f'   • Skipped Calendar:     {self.skipped_calendar_cells:,}')

		total_candidates = self.ax_candidates + self.dom_candidates
		if total_candidates > 0:
			reduction_rate = (1 - self.final_interactive_count / total_candidates) * 100
			print(f'\n📉 REDUCTION RATE: {reduction_rate:.1f}% ({total_candidates:,} → {self.final_interactive_count:,})')

		# Performance rating
		if self.total_time < 0.05:
			rating = '🔥 EXCELLENT'
		elif self.total_time < 0.1:
			rating = '✅ GOOD'
		elif self.total_time < 0.2:
			rating = '⚠️  MODERATE'
		else:
			rating = '🐌 SLOW'

		print(f'\n🎯 PERFORMANCE RATING: {rating}')
		print('=' * 80)


@dataclass(slots=True)
class SimplifiedNode:
	"""Simplified tree node for optimization."""

	original_node: EnhancedDOMTreeNode
	children: list['SimplifiedNode'] = field(default_factory=list)
	should_display: bool = True
	interactive_index: int | None = None
	group_type: str | None = None  # For grouping related elements
	group_parent: int | None = None  # Reference to parent group index
	interaction_priority: int = 0  # Higher = more important to keep
	is_consolidated: bool = False  # Flag to track if element was consolidated into parent

	def __str__(self) -> str:
		node_name = self.original_node.node_name
		attrs = self.original_node.attributes or {}

		# Basic element identification
		context_debug = ''

		# Build attribute display
		key_attrs = []
		if 'id' in attrs:
			key_attrs.append(f"id='{attrs['id'][:20]}{'...' if len(attrs['id']) > 20 else ''}'")
		if 'class' in attrs:
			key_attrs.append(f"class='{attrs['class'][:40]}{'...' if len(attrs['class']) > 40 else ''}'")

		attr_str = f' ({", ".join(key_attrs)})' if key_attrs else ''

		index_str = f' [{self.interactive_index}]' if self.interactive_index is not None else ''

		return f'{node_name}{attr_str}{index_str}{context_debug}'

	def is_clickable(self) -> bool:
		"""Enhanced clickability detection with comprehensive analysis."""
		if not self.original_node:
			return False

		node = self.original_node
		node_name = node.node_name.upper()

		# Standard form elements are always clickable
		if node_name in {'INPUT', 'BUTTON', 'SELECT', 'TEXTAREA', 'OPTION'}:
			return True

		# Links with href are clickable
		if node_name == 'A' and node.attributes and 'href' in node.attributes:
			return True

		# **ENHANCED SNAPSHOT DETECTION** - Check snapshot data for clickability
		if node.snapshot_node:
			# CDP snapshot indicates clickability
			if getattr(node.snapshot_node, 'is_clickable', False):
				return True

			# **COMPREHENSIVE CURSOR DETECTION** - Check for any interactive cursor
			computed_styles_info = {}
			if hasattr(node.snapshot_node, 'computed_styles'):
				computed_styles_info = node.snapshot_node.computed_styles or {}

			has_cursor, cursor_type, cursor_score = ElementAnalysis._has_any_interactive_cursor(node, computed_styles_info)
			if has_cursor:
				return True

		# **ENHANCED ATTRIBUTE DETECTION** - More comprehensive event handling checks
		if node.attributes:
			# Standard event handlers
			event_attrs = {'onclick', 'onmousedown', 'onkeydown', 'data-action', 'data-toggle', 'jsaction'}
			if any(attr in node.attributes for attr in event_attrs):
				return True

			# Framework-specific event attributes (Angular, Vue, React, etc.)
			framework_events = ['@click', 'v-on:', '(click)', 'ng-click', 'data-href', 'data-url']
			for attr in node.attributes:
				if any(framework in attr.lower() for framework in framework_events):
					return True

			# **ENHANCED ROLE DETECTION** - More comprehensive ARIA roles
			role = node.attributes.get('role', '').lower()
			interactive_roles = {
				'button',
				'link',
				'menuitem',
				'tab',
				'option',
				'checkbox',
				'radio',
				'slider',
				'spinbutton',
				'switch',
				'textbox',
				'combobox',
				'listbox',
				'tree',
				'grid',
				'gridcell',
				'searchbox',
				'menuitemradio',
				'menuitemcheckbox',
			}
			if role in interactive_roles:
				return True

			# **TABINDEX DETECTION** - Elements with positive tabindex
			tabindex = node.attributes.get('tabindex')
			if tabindex and tabindex.lstrip('-').isdigit() and int(tabindex) >= 0:
				return True

		# **ENHANCED AX TREE DETECTION** - Accessibility tree analysis
		if node.ax_node:
			# Check for focusable AX properties
			if node.ax_node.properties:
				for prop in node.ax_node.properties:
					if prop.name == AXPropertyName.FOCUSABLE and prop.value:
						return True

			# Check AX role for interactivity
			if node.ax_node.role:
				ax_interactive_roles = {
					'button',
					'link',
					'menuitem',
					'tab',
					'option',
					'checkbox',
					'radio',
					'slider',
					'spinbutton',
					'switch',
					'textbox',
					'combobox',
					'listbox',
				}
				if node.ax_node.role.lower() in ax_interactive_roles:
					return True

		# **ENHANCED CONTAINER ANALYSIS** - Deep analysis for containers (DIV, SPAN, etc.)
		if node_name in {'DIV', 'SPAN', 'SECTION', 'ARTICLE', 'LI', 'TD', 'TH'}:
			return self._is_container_truly_interactive(node)

		return False

	def _is_container_truly_interactive(self, node: EnhancedDOMTreeNode) -> bool:
		"""Enhanced container interactivity detection with sophisticated heuristics."""
		if not node.attributes:
			return False

		# **CHECK 1: Direct interaction attributes**
		interactive_attrs = {
			'onclick',
			'onmousedown',
			'onmouseup',
			'onkeydown',
			'onkeyup',
			'onfocus',
			'onblur',
			'data-action',
			'data-toggle',
			'data-href',
			'data-url',
			'data-target',
			'jsaction',
			'ng-click',
			'@click',
			'v-on:',
			'data-clickable',
		}

		# Direct attribute check
		for attr in node.attributes:
			if any(interactive in attr.lower() for interactive in interactive_attrs):
				return True

		# **CHECK 2: Class-based interaction patterns**
		if 'class' in node.attributes:
			classes = node.attributes['class'].lower()
			interactive_class_patterns = [
				'btn',
				'button',
				'clickable',
				'interactive',
				'link',
				'tab',
				'menu',
				'dropdown',
				'toggle',
				'accordion',
				'collapsible',
				'expandable',
				'modal',
				'popup',
				'overlay',
				'trigger',
				'action',
				'control',
				'widget',
				'component',
				'card-clickable',
				'list-item-clickable',
			]

			if any(pattern in classes for pattern in interactive_class_patterns):
				return True

		# **CHECK 3: Meaningful combination of attributes**
		meaningful_attrs = ['role', 'tabindex', 'aria-label', 'aria-labelledby', 'title']
		meaningful_count = sum(1 for attr in meaningful_attrs if attr in node.attributes)

		# If has multiple meaningful attributes, likely interactive
		if meaningful_count >= 2:
			return True

		# **CHECK 4: Specific role-based analysis**
		if 'role' in node.attributes:
			role = node.attributes['role'].lower()
			container_interactive_roles = {
				'button',
				'link',
				'menuitem',
				'tab',
				'option',
				'checkbox',
				'radio',
				'slider',
				'switch',
				'textbox',
				'combobox',
				'listbox',
				'tree',
				'grid',
				'gridcell',
				'searchbox',
				'menuitemradio',
				'menuitemcheckbox',
				'presentation',
				'application',
				'dialog',
				'alertdialog',
				'banner',
				'navigation',
				'main',
				'complementary',
				'contentinfo',
			}
			if role in container_interactive_roles:
				return True

		# **CHECK 5: Size and positioning heuristics**
		if node.snapshot_node and hasattr(node.snapshot_node, 'bounding_box'):
			bbox = node.snapshot_node.bounding_box
			if bbox:
				width = bbox.get('width', 0)
				height = bbox.get('height', 0)

				# Small elements with attributes are likely interactive (buttons, icons)
				if width > 0 and height > 0 and width <= 200 and height <= 100:
					if len(node.attributes) >= 2:  # Has meaningful attributes
						return True

		# **CHECK 6: Data attributes suggesting interactivity**
		data_attrs = [k for k in node.attributes.keys() if k.startswith('data-')]
		interactive_data_patterns = [
			'action',
			'click',
			'toggle',
			'href',
			'url',
			'target',
			'trigger',
			'modal',
			'popup',
			'dropdown',
			'tab',
			'accordion',
			'collapse',
		]

		for data_attr in data_attrs:
			if any(pattern in data_attr.lower() for pattern in interactive_data_patterns):
				return True

		return False

	def is_option_element(self) -> bool:
		"""Check if this is an option or list item element."""
		if not self.original_node:
			return False

		node_name = self.original_node.node_name.upper()
		if node_name == 'OPTION':
			return True

		# Check for role="option"
		if self.original_node.attributes and self.original_node.attributes.get('role') == 'option':
			return True

		# Check for list items that might be selectable
		if node_name in {'LI', 'DIV'} and self.original_node.attributes:
			classes = self.original_node.attributes.get('class', '').lower()
			if any(pattern in classes for pattern in ['option', 'item', 'choice', 'select']):
				return True

		return False

	def is_radio_or_checkbox(self) -> bool:
		"""Check if this is a radio button or checkbox."""
		if not self.original_node or not self.original_node.attributes:
			return False

		input_type = self.original_node.attributes.get('type', '').lower()
		return input_type in {'radio', 'checkbox'}

	def get_group_name(self) -> str:
		"""Get a semantic group name for this element."""
		if not self.original_node:
			return 'unknown'

		node_name = self.original_node.node_name.upper()
		attrs = self.original_node.attributes or {}

		# Form elements
		if node_name in {'INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'}:
			return 'form'

		# Navigation
		if node_name == 'A' or attrs.get('role') in {'navigation', 'menuitem'}:
			return 'navigation'

		# Lists
		if node_name in {'LI', 'UL', 'OL'} or attrs.get('role') in {'list', 'listitem'}:
			return 'list'

		return 'content'

	def count_direct_clickable_children(self) -> int:
		"""Count direct clickable children."""
		return sum(1 for child in self.children if child.is_clickable())

	def has_any_clickable_descendant(self) -> bool:
		"""Check if this node has any clickable descendants."""
		for child in self.children:
			if child.is_clickable() or child.has_any_clickable_descendant():
				return True
		return False

	def is_effectively_visible(self) -> bool:
		"""Enhanced visibility detection with comprehensive checks."""
		if not self.original_node or not self.original_node.snapshot_node:
			return False

		snapshot = self.original_node.snapshot_node

		# **CHECK 1: Bounding box analysis**
		bbox = getattr(snapshot, 'bounding_box', None)
		if not bbox:
			return False

		width = bbox.get('width', 0)
		height = bbox.get('height', 0)

		# Must have meaningful dimensions
		if width <= 0 or height <= 0:
			return False

		# **CHECK 2: Style-based visibility**
		if hasattr(snapshot, 'computed_styles'):
			styles = snapshot.computed_styles or {}

			# Check visibility styles
			if styles.get('visibility') == 'hidden':
				return False
			if styles.get('display') == 'none':
				return False

			# Check opacity
			opacity = styles.get('opacity', '1')
			try:
				if float(opacity) <= 0.01:  # Effectively invisible
					return False
			except (ValueError, TypeError):
				pass

		# **CHECK 3: Position analysis**
		x = bbox.get('x', 0)
		y = bbox.get('y', 0)

		# Element positioned way off-screen is likely hidden
		if x < -1000 or y < -1000 or x > 10000 or y > 10000:
			return False

		# **CHECK 4: Size reasonableness**
		# Very large elements (like body, html) or very tiny elements might not be interactive
		if width > 5000 or height > 5000:
			return False

		if width < 1 or height < 1:
			return False

		return True

	def has_meaningful_bounds(self) -> bool:
		"""Check if element has meaningful bounding box for interaction."""
		if not self.original_node or not self.original_node.snapshot_node:
			return False

		bbox = getattr(self.original_node.snapshot_node, 'bounding_box', None)
		if not bbox:
			return False

		width = bbox.get('width', 0)
		height = bbox.get('height', 0)

		# Must be large enough to interact with (but not too large)
		return 1 <= width <= 2000 and 1 <= height <= 2000


@dataclass(slots=True)
class DOMTreeSerializer:
	"""Optimized DOM tree serializer for LLM consumption with performance focus."""

	root_node: EnhancedDOMTreeNode
	viewport_info: dict = field(default_factory=dict)
	_interactive_counter: int = 1
	_selector_map: dict[int, EnhancedDOMTreeNode] = field(default_factory=dict)
	_visibility_cache: Dict[str, bool] = field(default_factory=dict)
	_compressed_elements: List[CompressedElement] = field(default_factory=list)
	_semantic_groups: List[SemanticGroup] = field(default_factory=list)
	metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
	_include_all_ax_elements: bool = False  # NEW: Flag to include ALL AX elements when threshold=0

	def __post_init__(self):
		# Initialize performance metrics
		if not hasattr(self, 'metrics') or self.metrics is None:
			self.metrics = PerformanceMetrics()

	def serialize_accessible_elements(
		self,
		include_attributes: list[str] | None = None,
	) -> tuple[str, dict[int, EnhancedDOMTreeNode]]:
		"""
		Main entry point for serialization using optimized AX tree method.

		Returns:
		- Serialized string representation
		- Selector map for element identification
		"""
		if include_attributes is None:
			include_attributes = DEFAULT_INCLUDE_ATTRIBUTES

		# Use only the optimized method
		serialized, selector_map = self._serialize_ax_tree_optimized(include_attributes)

		return serialized, selector_map

	def _serialize_ax_tree_optimized(self, include_attributes: list[str]) -> tuple[str, dict[int, EnhancedDOMTreeNode]]:
		"""OPTIMIZED serialization method using AX tree for speed with legacy enhancements."""
		# Reset state
		self._interactive_counter = 1
		self._selector_map = {}
		self._visibility_cache = {}
		self._compressed_elements = []
		self._semantic_groups = []

		self.metrics = PerformanceMetrics()
		ax_start = time.time()

		# **STEP 1: Fast AX + DOM candidate collection**
		candidates = self._collect_ax_interactive_candidates_fast(self.root_node)
		self.metrics.ax_collection_time = time.time() - ax_start
		self.metrics.ax_candidates = len([c for c in candidates if len(c) >= 2 and c[1] == 'ax'])
		self.metrics.dom_candidates = len([c for c in candidates if len(c) >= 2 and c[1] == 'dom'])

		filter_start = time.time()

		# **STEP 2: Fast conflict resolution**
		# Skip conflict resolution when including all AX elements (threshold = 0)
		if not getattr(self, '_include_all_ax_elements', False):
			candidates = self.detect_and_resolve_nested_conflicts(candidates)
		else:
			print(f'🎯 SKIPPING CONFLICT RESOLUTION: Including all {len(candidates)} AX elements')

		# **STEP 3: Fast viewport filtering and deduplication**
		filtered_nodes = self._filter_by_viewport_and_deduplicate_fast(candidates)
		self.metrics.filtering_time = time.time() - filter_start
		self.metrics.after_viewport_filter = len(filtered_nodes)

		tree_start = time.time()

		# **STEP 4: Build minimal simplified tree**
		simplified_elements = self._build_minimal_simplified_tree_fast(filtered_nodes)
		self.metrics.tree_building_time = time.time() - tree_start

		# **STEP 5: Apply legacy enhancements for sophisticated processing**
		simplified_elements = self._apply_legacy_enhancements_to_optimized_tree(simplified_elements)

		indexing_start = time.time()

		# **STEP 6: Assign indices**
		self._assign_indices_to_filtered_elements(simplified_elements)
		self.metrics.indexing_time = time.time() - indexing_start
		self.metrics.final_interactive_count = len(simplified_elements)

		serialization_start = time.time()

		# **STEP 7: Generate compressed text**
		serialized = self._serialize_minimal_tree_fast(simplified_elements, include_attributes)
		self.metrics.serialization_time = time.time() - serialization_start

		# Finalize metrics
		self.metrics.finish()

		return serialized, self._selector_map

	def _apply_legacy_enhancements_to_optimized_tree(self, simplified_elements: List[SimplifiedNode]) -> List[SimplifiedNode]:
		"""Apply sophisticated enhancements from legacy method to the optimized tree."""

		if not simplified_elements:
			return simplified_elements

		# Build temporary tree structure for analysis
		tree_structure = self._build_temporary_tree_structure(simplified_elements)

		# Apply sophisticated container filtering from legacy
		removed_wrappers = 0
		for root in tree_structure:
			removed_wrappers += self._detect_and_remove_wrapper_containers_optimized(root)

		# Apply same-action consolidation from legacy
		consolidated_elements = 0
		for root in tree_structure:
			consolidated_elements += self._apply_same_action_consolidation_optimized(root)

		# Apply smart parent-child consolidation from legacy
		smart_consolidated = 0
		for root in tree_structure:
			smart_consolidated += self._apply_smart_parent_child_consolidation_optimized(root)

		# Collect all non-consolidated elements
		final_elements = []
		for root in tree_structure:
			self._collect_non_consolidated_elements(root, final_elements)

		return final_elements

	def _build_temporary_tree_structure(self, simplified_elements: List[SimplifiedNode]) -> List[SimplifiedNode]:
		"""Build a temporary tree structure for legacy enhancement processing."""
		# For now, treat all elements as root elements (flat structure)
		# This can be enhanced later if true hierarchy is needed
		return simplified_elements

	def _detect_and_remove_wrapper_containers_optimized(self, root: SimplifiedNode) -> int:
		"""Remove wrapper containers that don't add interaction value (from legacy method)."""
		removed_count = 0

		children_to_remove = []
		for child in root.children:
			# Recursively process children
			removed_count += self._detect_and_remove_wrapper_containers_optimized(child)

			# Check if this child is a wrapper container
			if self._is_wrapper_container_optimized(child):
				children_to_remove.append(child)
				child.is_consolidated = True
				removed_count += 1

		# Remove wrapper containers
		for child in children_to_remove:
			root.children.remove(child)

		return removed_count

	def _is_wrapper_container_optimized(self, node: SimplifiedNode) -> bool:
		"""Enhanced wrapper container detection from legacy method."""
		if not node.original_node:
			return False

		original = node.original_node
		node_name = original.node_name.upper()

		# Only consider containers
		if node_name not in {'DIV', 'SPAN', 'SECTION', 'ARTICLE'}:
			return False

		# Has meaningful attributes - not a wrapper
		if original.attributes:
			meaningful_attrs = {'onclick', 'data-action', 'role', 'tabindex', 'aria-label', 'href'}
			if any(attr in original.attributes for attr in meaningful_attrs):
				return False

		# If has many clickable children, might be a wrapper
		clickable_children = node.count_direct_clickable_children()
		if clickable_children >= 3:  # Likely a wrapper around multiple interactive elements
			return True

		# If has exactly one clickable child and this element has no meaningful interaction, it's a wrapper
		if clickable_children == 1 and not node.is_clickable():
			return True

		# Check size - very large containers are likely layout wrappers
		if original.snapshot_node and hasattr(original.snapshot_node, 'bounding_box'):
			bbox = original.snapshot_node.bounding_box
			if bbox:
				width = bbox.get('width', 0)
				height = bbox.get('height', 0)
				if width > 1000 or height > 800:  # Very large, likely layout
					return True

		return False

	def _apply_same_action_consolidation_optimized(self, root: SimplifiedNode) -> int:
		"""Consolidate elements that would perform the same action (from legacy method)."""
		consolidated_count = 0

		children_to_remove = []
		for child in root.children:
			# Recursively process children
			consolidated_count += self._apply_same_action_consolidation_optimized(child)

			# Check if this child performs the same action as parent
			if self._elements_would_do_same_action_optimized(root, child):
				children_to_remove.append(child)
				child.is_consolidated = True
				consolidated_count += 1

		# Remove consolidated children
		for child in children_to_remove:
			root.children.remove(child)

		return consolidated_count

	def _elements_would_do_same_action_optimized(self, parent: SimplifiedNode, child: SimplifiedNode) -> bool:
		"""Check if parent and child would perform the same action (from legacy method)."""
		if not parent.original_node or not child.original_node:
			return False

		parent_node = parent.original_node
		child_node = child.original_node

		# Both are links with same href
		if (
			parent_node.node_name.upper() == 'A'
			and child_node.node_name.upper() == 'A'
			and parent_node.attributes
			and child_node.attributes
			and parent_node.attributes.get('href') == child_node.attributes.get('href')
		):
			return True

		# Both have same onclick handler
		if (
			parent_node.attributes
			and child_node.attributes
			and parent_node.attributes.get('onclick') == child_node.attributes.get('onclick')
			and parent_node.attributes.get('onclick')
		):
			return True

		# Both have same data-action
		if (
			parent_node.attributes
			and child_node.attributes
			and parent_node.attributes.get('data-action') == child_node.attributes.get('data-action')
			and parent_node.attributes.get('data-action')
		):
			return True

		# Parent wraps a single interactive child (common pattern)
		if (
			parent_node.node_name.upper() in {'DIV', 'SPAN'}
			and len(parent.children) == 1
			and child_node.node_name.upper() in {'A', 'BUTTON', 'INPUT'}
		):
			return True

		return False

	def _apply_smart_parent_child_consolidation_optimized(self, root: SimplifiedNode) -> int:
		"""Smart consolidation of parent-child relationships (from legacy method)."""
		consolidated_count = 0

		# Check each child
		children_to_process = list(root.children)  # Copy to avoid modification during iteration

		for child in children_to_process:
			# Recursively process children first
			consolidated_count += self._apply_smart_parent_child_consolidation_optimized(child)

			# Smart consolidation logic
			if child.original_node and root.original_node and not child.is_consolidated:
				child_node = child.original_node
				parent_node = root.original_node

				# If child is a text node inside a clickable parent, consolidate
				if (
					child_node.node_name == '#text'
					and parent_node.node_name.upper() in {'A', 'BUTTON', 'DIV', 'SPAN'}
					and root.is_clickable()
				):
					child.is_consolidated = True
					consolidated_count += 1
					continue

				# If parent and child have very similar bounding boxes, consolidate child
				if (
					child_node.snapshot_node
					and parent_node.snapshot_node
					and hasattr(child_node.snapshot_node, 'bounding_box')
					and hasattr(parent_node.snapshot_node, 'bounding_box')
				):
					child_bbox = child_node.snapshot_node.bounding_box
					parent_bbox = parent_node.snapshot_node.bounding_box

					if child_bbox and parent_bbox:
						# Check if bounding boxes are very similar (within 10 pixels)
						x_diff = abs(child_bbox.get('x', 0) - parent_bbox.get('x', 0))
						y_diff = abs(child_bbox.get('y', 0) - parent_bbox.get('y', 0))
						w_diff = abs(child_bbox.get('width', 0) - parent_bbox.get('width', 0))
						h_diff = abs(child_bbox.get('height', 0) - parent_bbox.get('height', 0))

						if x_diff <= 10 and y_diff <= 10 and w_diff <= 10 and h_diff <= 10:
							child.is_consolidated = True
							consolidated_count += 1

		return consolidated_count

	def _collect_non_consolidated_elements(self, node: SimplifiedNode, result_list: List[SimplifiedNode]):
		"""Collect all non-consolidated elements from the tree."""
		if not node.is_consolidated:
			result_list.append(node)

		# Process children
		for child in node.children:
			self._collect_non_consolidated_elements(child, result_list)

	def _collect_ax_interactive_candidates_fast(self, node: EnhancedDOMTreeNode) -> List:
		"""Fast collection of interactive candidates using both AX tree and DOM analysis."""
		candidates = []

		def collect_recursive_fast(current_node: EnhancedDOMTreeNode, depth: int = 0):
			if depth > 50:  # Prevent infinite recursion
				return

			self.metrics.total_dom_nodes += 1

			# **ENHANCED: Check if we should include ALL AX elements (when threshold = 0)**
			should_include_all_ax = getattr(self, '_include_all_ax_elements', False)

			if should_include_all_ax:
				# **SCORE THRESHOLD = 0 MODE: Include ALL elements with AX nodes, bypass ALL filtering**
				if current_node.ax_node:
					# Include EVERY element that has an AX node, no matter what
					candidates.append((current_node, 'ax_all'))
					print(
						f'🎯 INCLUDED AX ELEMENT: {current_node.node_name} (AX role: {current_node.ax_node.role if current_node.ax_node.role else "no role"})'
					)

				# Also include basic interactive elements even without AX nodes
				elif current_node.node_name.upper() in ['INPUT', 'BUTTON', 'SELECT', 'TEXTAREA', 'A']:
					candidates.append((current_node, 'dom_basic'))
					print(f'🎯 INCLUDED BASIC ELEMENT: {current_node.node_name}')

				# In this mode, ALWAYS traverse children regardless of element type
				if hasattr(current_node, 'children_nodes') and current_node.children_nodes:
					for child in current_node.children_nodes:
						collect_recursive_fast(child, depth + 1)
				return  # Exit early, don't do normal processing

			# **NORMAL MODE: Apply structural filtering**
			# Check if this is a structural element but still process its children for container elements
			is_structural = self._is_structural_element_fast(current_node)
			if is_structural:
				self.metrics.skipped_structural += 1

				# For container elements like HTML, BODY, HEAD, still process children
				container_elements = {'HTML', 'BODY', 'HEAD', 'MAIN', 'SECTION', 'ARTICLE', 'DIV', 'SPAN'}
				if current_node.node_name.upper() in container_elements:
					# Don't consider this element interactive, but process its children
					pass
				else:
					# For other structural elements, skip completely
					if hasattr(current_node, 'children_nodes') and current_node.children_nodes:
						for child in current_node.children_nodes:
							collect_recursive_fast(child, depth + 1)
					return

			# Only check for interactivity if not structural
			if not is_structural:
				# Normal mode: AX first, then DOM fallback
				is_ax_interactive = self._is_ax_interactive_fast(current_node, include_all=False)
				if is_ax_interactive:
					candidates.append((current_node, 'ax'))
				elif self._is_dom_interactive_fast(current_node):
					candidates.append((current_node, 'dom'))

			# Recurse to children
			if hasattr(current_node, 'children_nodes') and current_node.children_nodes:
				for child in current_node.children_nodes:
					collect_recursive_fast(child, depth + 1)

		collect_recursive_fast(node)

		if getattr(self, '_include_all_ax_elements', False):
			print(f'🎯 TOTAL AX ELEMENTS COLLECTED: {len([c for c in candidates if len(c) >= 2 and c[1] == "ax_all"])}')
			print(f'🎯 TOTAL BASIC ELEMENTS COLLECTED: {len([c for c in candidates if len(c) >= 2 and c[1] == "dom_basic"])}')

		return candidates

	def _is_dom_interactive_comprehensive(self, node: EnhancedDOMTreeNode) -> bool:
		"""Comprehensive DOM detection that includes ALL potentially interactive elements (for score=0)."""
		if node.node_type != NodeType.ELEMENT_NODE:
			return False

		node_name = node.node_name.upper()

		# **TIER 1: Always interactive elements**
		if node_name in {'INPUT', 'BUTTON', 'SELECT', 'TEXTAREA', 'OPTION', 'A'}:
			return True

		# **TIER 2: Elements with explicit interaction indicators**
		if node.attributes:
			# Event handlers
			interactive_attrs = {
				'onclick',
				'onmousedown',
				'onkeydown',
				'onchange',
				'oninput',
				'onsubmit',
				'onfocus',
				'onblur',
				'onhover',
				'data-action',
				'data-toggle',
				'jsaction',
				'ng-click',
				'@click',
				'v-on:',
				'(click)',
			}
			if any(attr in node.attributes for attr in interactive_attrs):
				return True

			# ARIA roles (comprehensive list)
			role = node.attributes.get('role', '').lower()
			if role in {
				'button',
				'link',
				'menuitem',
				'tab',
				'option',
				'checkbox',
				'radio',
				'slider',
				'spinbutton',
				'switch',
				'textbox',
				'combobox',
				'listbox',
				'tree',
				'grid',
				'gridcell',
				'searchbox',
				'menuitemradio',
				'menuitemcheckbox',
				'application',
				'dialog',
				'alertdialog',
				'banner',
				'navigation',
				'main',
				'complementary',
				'contentinfo',
				'toolbar',
				'tooltip',
			}:
				return True

			# Positive tabindex
			tabindex = node.attributes.get('tabindex')
			if tabindex and tabindex.lstrip('-').isdigit() and int(tabindex) >= 0:
				return True

		# **TIER 3: AX tree elements (if present)**
		if node.ax_node:
			# Any element with AX role
			if node.ax_node.role:
				return True

			# Any element with AX properties
			if node.ax_node.properties:
				return True

			# Any element with AX name (often interactive)
			if node.ax_node.name:
				return True

		# **TIER 4: CSS-based interaction indicators**
		if node.snapshot_node:
			# Comprehensive cursor check
			computed_styles_info = {}
			if hasattr(node.snapshot_node, 'computed_styles'):
				computed_styles_info = node.snapshot_node.computed_styles or {}

			# Use our comprehensive cursor detection
			has_cursor, _, _ = ElementAnalysis._has_any_interactive_cursor(node, computed_styles_info)
			if has_cursor:
				return True

			# Clickable from snapshot
			if getattr(node.snapshot_node, 'is_clickable', False):
				return True

		# **TIER 5: Container elements with meaningful attributes**
		if node_name in {'DIV', 'SPAN', 'SECTION', 'ARTICLE', 'LI', 'TD', 'TH', 'NAV'}:
			if node.attributes and len(node.attributes) > 0:
				# Has any attributes beyond basic structural ones
				meaningful_attrs = set(node.attributes.keys()) - {'class', 'id', 'style'}
				if meaningful_attrs:
					return True

				# Has interactive-looking classes
				classes = node.attributes.get('class', '').lower()
				interactive_class_patterns = [
					'btn',
					'button',
					'clickable',
					'interactive',
					'link',
					'tab',
					'menu',
					'dropdown',
					'toggle',
					'accordion',
					'modal',
					'popup',
					'trigger',
					'control',
					'widget',
					'component',
					'card',
					'item',
					'option',
				]
				if any(pattern in classes for pattern in interactive_class_patterns):
					return True

		return False

	async def get_element_event_listeners_via_cdp(self, browser_session, node: EnhancedDOMTreeNode) -> List[str]:
		"""Get actual event listeners attached to an element via CDP."""
		try:
			from browser_use.browser.session import BrowserSession

			if not isinstance(browser_session, BrowserSession):
				return []

			# Get the current page
			page = await browser_session.get_current_page()
			if not page:
				return []

			# Get the backend node ID for the element
			if not hasattr(node, 'backend_node_id') or not node.backend_node_id:
				return []

			# TODO: Use DOMDebugger.getEventListeners to get actual listeners
			# For now, fallback to enhanced attribute detection
			result = {'listeners': []}

			listeners = []
			if 'listeners' in result:
				for listener in result['listeners']:
					event_type = listener.get('type', 'unknown')
					use_capture = listener.get('useCapture', False)
					passive = listener.get('passive', False)
					once = listener.get('once', False)

					listener_info = f'{event_type}'
					if use_capture:
						listener_info += ' (capture)'
					if passive:
						listener_info += ' (passive)'
					if once:
						listener_info += ' (once)'

					listeners.append(listener_info)

			return listeners

		except Exception as e:
			# Enhanced fallback to attribute-based and style detection
			listeners = []

			if node.attributes:
				# Detect standard event attributes
				event_attrs = [k for k in node.attributes.keys() if k.startswith('on')]
				listeners.extend(event_attrs)

				# Detect framework-specific event attributes
				framework_events = ['@click', 'v-on:', '(click)', 'ng-click', 'data-action', 'jsaction']
				for attr in node.attributes:
					if any(framework in attr.lower() for framework in framework_events):
						listeners.append(f'framework:{attr}')

			# Detect computed event-related styles
			if node.snapshot_node and hasattr(node.snapshot_node, 'computed_styles'):
				styles = node.snapshot_node.computed_styles or {}
				if styles.get('cursor') == 'pointer':
					listeners.append('style:cursor-pointer')
				if styles.get('pointer-events') == 'auto':
					listeners.append('style:pointer-events-auto')

			return listeners

	def detect_and_resolve_nested_conflicts(self, candidates) -> List:
		"""Detect and resolve nested conflicts where elements would trigger the same action or are spatially overlapping."""
		# For simple candidates (node, 'ax') or (node, 'dom'), apply enhanced conflict resolution
		if not candidates:
			return candidates

		# Check if we have simple candidates (from fast collection) vs analyzed candidates
		first_candidate = candidates[0] if candidates else None
		if not first_candidate or len(first_candidate) < 3 or first_candidate[1] in ['ax', 'dom', 'ax_all', 'dom_basic']:
			# Apply enhanced conflict resolution for simple candidates
			return self._detect_and_resolve_same_action_conflicts_simple(candidates)

		# Original conflict resolution logic for analyzed candidates with ElementAnalysis
		analyses_map = {}
		nodes_map = {}

		for candidate_tuple in candidates:
			if len(candidate_tuple) >= 3 and candidate_tuple[1] == 'enhanced':
				node, _, analysis = candidate_tuple
				node_id = id(node)
				analyses_map[node_id] = analysis
				nodes_map[node_id] = node

		# If no analyzed candidates, return original list
		if not analyses_map:
			return candidates

		# Detect action-based conflicts
		conflict_groups = {}

		for node_id, analysis in analyses_map.items():
			node = nodes_map[node_id]
			current_action = ElementAnalysis._get_element_action(node)

			if current_action:
				if current_action not in conflict_groups:
					conflict_groups[current_action] = []
				conflict_groups[current_action].append((node_id, node, analysis))

		# Detect spatial overlaps
		spatial_groups = self._detect_spatial_overlaps(
			[(node_id, node, analysis) for node_id, analysis in analyses_map.items() for node in [nodes_map[node_id]]]
		)

		# Resolve conflicts - prefer parent elements or highest scoring
		resolved_candidates = []
		processed_nodes = set()

		# Handle action-based conflicts first
		for action, group in conflict_groups.items():
			if len(group) > 1:
				# Multiple elements would trigger the same action
				# Prefer the element with highest score, or if scores are close, prefer the parent
				group.sort(key=lambda x: (-x[2].score, self._get_element_depth(x[1])))

				# Keep the best element, reduce scores of others
				best_node_id, best_node, best_analysis = group[0]
				resolved_candidates.append((best_node, 'enhanced', best_analysis))
				processed_nodes.add(best_node_id)

				# Reduce scores of conflicting elements
				for node_id, node, analysis in group[1:]:
					analysis.score = max(10, analysis.score - 40)
					analysis.warnings.append(f'Nested conflict with same action: {action} - score reduced')
					analysis.nested_conflict_parent = best_node_id
					resolved_candidates.append((node, 'enhanced', analysis))
					processed_nodes.add(node_id)

		# Handle spatial conflicts
		for spatial_group in spatial_groups:
			if len(spatial_group) > 1:
				group_node_ids = [x[0] for x in spatial_group]
				unprocessed_in_group = [x for x in spatial_group if x[0] not in processed_nodes]

				if len(unprocessed_in_group) > 1:
					# Sort by score to keep the best one
					unprocessed_in_group.sort(key=lambda x: (-x[2].score, self._get_element_depth(x[1])))

					# Keep the best one
					best_node_id, best_node, best_analysis = unprocessed_in_group[0]
					resolved_candidates.append((best_node, 'enhanced', best_analysis))
					processed_nodes.add(best_node_id)

					# Mark others as spatially conflicted
					for node_id, node, analysis in unprocessed_in_group[1:]:
						analysis.score = max(5, analysis.score - 30)
						analysis.warnings.append('Spatially overlapping with higher-scoring element - score reduced')
						resolved_candidates.append((node, 'enhanced', analysis))
						processed_nodes.add(node_id)

		# Add non-conflicting elements
		for candidate_tuple in candidates:
			if len(candidate_tuple) >= 3 and candidate_tuple[1] == 'enhanced':
				node, _, analysis = candidate_tuple
				node_id = id(node)
				if node_id not in processed_nodes:
					resolved_candidates.append(candidate_tuple)

		return resolved_candidates

	def _detect_and_resolve_same_action_conflicts_simple(self, candidates) -> List:
		"""Enhanced conflict resolution for simple candidates that detects same-action conflicts and prioritizes largest elements."""
		if not candidates:
			return candidates

		print(f'🔍 CONFLICT RESOLUTION: Processing {len(candidates)} candidates')

		# First, detect same-action conflicts (much more important than spatial overlap)
		action_groups = {}
		processed_for_actions = set()

		for i, candidate in enumerate(candidates):
			if i in processed_for_actions:
				continue

			node = candidate[0]
			action = self._get_element_action_simple(node)

			if action:
				if action not in action_groups:
					action_groups[action] = []
				action_groups[action].append((i, candidate, node))

		# Resolve action-based conflicts by keeping the largest element and reducing scores of others
		conflict_resolved_candidates = []
		processed_indices = set()

		for action, group in action_groups.items():
			if len(group) > 1:
				print(f'🔗 Same-action conflict detected: {action} ({len(group)} elements)')

				# Sort by element size (largest first), then by element type priority
				group.sort(key=lambda x: (-self._get_element_size(x[2]), self._get_element_priority(x[2])))

				# Keep the largest/best element with full score
				best_idx, best_candidate, best_node = group[0]
				best_with_analysis = self._add_conflict_analysis(best_candidate, best_node, action, is_winner=True)
				conflict_resolved_candidates.append(best_with_analysis)
				processed_indices.add(best_idx)

				print(f'    🏆 Selected best for "{action}": {best_node.node_name} (size: {self._get_element_size(best_node)})')

				# Add other elements with reduced scores (so they appear when threshold=0)
				for idx, candidate, node in group[1:]:
					reduced_candidate = self._add_conflict_analysis(candidate, node, action, is_winner=False)
					conflict_resolved_candidates.append(reduced_candidate)
					processed_indices.add(idx)
					print(f'      {idx + 1}. {node.node_name} (size: {self._get_element_size(node)})')

				print(f'  🔗 Deduplicated {len(group)} → 1 for action: {action}')

				# Show kept vs removed
				print(f'    ✅ Kept: {best_node.node_name} (xpath: {best_node.x_path[:30]}...)')
				for idx, candidate, node in group[1:]:
					print(f'    ❌ Reduced score: {node.node_name} (xpath: {node.x_path[:30]}...)')

		# Add non-conflicting elements as-is
		for i, candidate in enumerate(candidates):
			if i not in processed_indices:
				# Still add conflict analysis with normal score
				node = candidate[0]
				analyzed_candidate = self._add_conflict_analysis(candidate, node, None, is_winner=True)
				conflict_resolved_candidates.append(analyzed_candidate)

		print(
			f'✅ Action-based conflict resolution complete: {len(candidates)} → {len([c for c in conflict_resolved_candidates if not c[2].warnings])} (-{len(candidates) - len([c for c in conflict_resolved_candidates if not c[2].warnings])} reduced scores)'
		)

		# Then apply spatial deduplication to the remaining elements
		return self._apply_spatial_deduplication_with_analysis(conflict_resolved_candidates)

	def _get_element_action_simple(self, node: EnhancedDOMTreeNode) -> str | None:
		"""Extract the action that an element would perform (simplified version for conflict detection)."""
		if not node or not node.attributes:
			return None

		attrs = node.attributes

		# Check various action indicators in priority order
		if 'href' in attrs and attrs['href']:
			href = attrs['href'].strip()
			if href and href != '#':
				return f'navigate:{href}'

		if 'onclick' in attrs and attrs['onclick']:
			# Normalize onclick content for comparison
			onclick = attrs['onclick'].strip()
			return f'onclick:{onclick[:50]}'  # Truncate for comparison

		if 'data-action' in attrs and attrs['data-action']:
			return f'data-action:{attrs["data-action"]}'

		if 'jsaction' in attrs and attrs['jsaction']:
			return f'jsaction:{attrs["jsaction"]}'

		# Framework-specific actions
		for attr in attrs:
			if attr.lower() in ['@click', 'ng-click', '(click)', 'v-on:click']:
				return f'framework:{attr}:{attrs[attr]}'

		# Check for elements that would likely have the same spatial action
		# (e.g., nested divs that all cover the same clickable area)
		if node.snapshot_node and hasattr(node.snapshot_node, 'bounding_box'):
			bbox = node.snapshot_node.bounding_box
			if bbox:
				x = int(bbox.get('x', 0))
				y = int(bbox.get('y', 0))
				w = int(bbox.get('width', 0))
				h = int(bbox.get('height', 0))

				# Create spatial action identifier for elements with similar classes or positions
				classes = attrs.get('class', '').strip()
				if classes:
					# Group by class patterns for common UI components
					class_tokens = classes.lower().split()
					significant_classes = [
						c
						for c in class_tokens
						if any(pattern in c for pattern in ['btn', 'button', 'card', 'item', 'cell', 'tile'])
					]
					if significant_classes:
						return f'element_classes:{" ".join(significant_classes)}'

				# Group by spatial location for generic containers
				if node.node_name.upper() in ['DIV', 'SPAN', 'SECTION']:
					return f'spatial:{node.node_name}:{x}:{y}:{w}:{h}'

		return None

	def _get_element_size(self, node: EnhancedDOMTreeNode) -> int:
		"""Calculate element size (area) for prioritization."""
		if not node.snapshot_node or not hasattr(node.snapshot_node, 'bounding_box'):
			return 0

		bbox = node.snapshot_node.bounding_box
		if not bbox:
			return 0

		width = bbox.get('width', 0)
		height = bbox.get('height', 0)
		return int(width * height)

	def _get_element_priority(self, node: EnhancedDOMTreeNode) -> int:
		"""Get element type priority (lower number = higher priority)."""
		element_type = node.node_name.upper()

		# Priority order: prefer actual interactive elements over containers
		priority_map = {
			'BUTTON': 1,
			'A': 2,
			'INPUT': 3,
			'SELECT': 4,
			'TEXTAREA': 5,
			'LABEL': 6,
			'SPAN': 10,
			'DIV': 11,
			'SECTION': 12,
			'ARTICLE': 13,
		}

		return priority_map.get(element_type, 15)

	def _add_conflict_analysis(self, candidate: tuple, node: EnhancedDOMTreeNode, action: str | None, is_winner: bool) -> tuple:
		"""Add ElementAnalysis to a simple candidate with appropriate scoring for conflict resolution."""
		# Create a basic ElementAnalysis for the candidate
		analysis = ElementAnalysis.analyze_element_interactivity(node)

		if not is_winner and action:
			# Reduce score for non-winning elements but keep them detectable at threshold 0
			original_score = analysis.score
			analysis.score = max(5, analysis.score - 40)  # Reduce significantly but keep above 0
			analysis.warnings.append(
				f'Same-action conflict with larger element (action: {action[:30]}) - score reduced from {original_score} to {analysis.score}'
			)
			analysis.context_info.append(f'Conflicting action: {action[:50]}')
		elif is_winner and action:
			# Winner gets a small boost and context info
			analysis.score += 5
			analysis.context_info.append(f'Preferred element for action: {action[:50]}')

		# Return enhanced candidate tuple
		return (node, 'enhanced', analysis)

	def _apply_spatial_deduplication_with_analysis(self, analyzed_candidates) -> List:
		"""Apply spatial deduplication to candidates that already have ElementAnalysis."""
		if not analyzed_candidates:
			return analyzed_candidates

		# Group by spatial overlap
		spatial_groups = []
		processed = set()

		for i, candidate_a in enumerate(analyzed_candidates):
			if i in processed:
				continue

			node_a = candidate_a[0]
			current_group = [candidate_a]
			processed.add(i)

			# Find spatially overlapping elements
			for j, candidate_b in enumerate(analyzed_candidates[i + 1 :], i + 1):
				if j in processed:
					continue

				node_b = candidate_b[0]
				if self._elements_spatially_overlap(node_a, node_b):
					current_group.append(candidate_b)
					processed.add(j)

			spatial_groups.append(current_group)

		# Resolve spatial conflicts by keeping highest scoring element
		final_candidates = []
		for group in spatial_groups:
			if len(group) == 1:
				final_candidates.append(group[0])
			else:
				# Sort by analysis score (highest first), then by element size
				group.sort(key=lambda x: (-x[2].score, -self._get_element_size(x[0])))

				# Keep the best element
				best_candidate = group[0]
				final_candidates.append(best_candidate)

				# Reduce scores of spatially overlapping elements but keep them
				for candidate in group[1:]:
					node, candidate_type, analysis = candidate
					analysis.score = max(3, analysis.score - 25)
					analysis.warnings.append('Spatially overlapping with higher-scoring element - score reduced')
					final_candidates.append(candidate)

		return final_candidates

	def _apply_spatial_deduplication_simple(self, candidates) -> List:
		"""Apply spatial deduplication for simple candidates."""
		if not candidates:
			return candidates

		# Group candidates by spatial overlap
		spatial_groups = []
		processed = set()

		for i, candidate_a in enumerate(candidates):
			if i in processed:
				continue

			node_a = candidate_a[0]
			current_group = [candidate_a]
			processed.add(i)

			# Find overlapping elements
			for j, candidate_b in enumerate(candidates[i + 1 :], i + 1):
				if j in processed:
					continue

				node_b = candidate_b[0]
				if self._elements_spatially_overlap(node_a, node_b):
					current_group.append(candidate_b)
					processed.add(j)

			spatial_groups.append(current_group)

		# Keep the best element from each spatial group
		deduplicated = []
		for group in spatial_groups:
			if len(group) == 1:
				deduplicated.append(group[0])
			else:
				# Choose the best element based on element type preference
				best = self._choose_best_spatial_candidate(group)
				deduplicated.append(best)

		return deduplicated

	def _detect_spatial_overlaps(self, analyzed_candidates) -> List[List]:
		"""Detect groups of spatially overlapping elements."""
		if not analyzed_candidates:
			return []

		spatial_groups = []
		processed = set()

		for i, (node_id_a, node_a, analysis_a) in enumerate(analyzed_candidates):
			if node_id_a in processed:
				continue

			current_group = [(node_id_a, node_a, analysis_a)]
			processed.add(node_id_a)

			# Find overlapping elements
			for j, (node_id_b, node_b, analysis_b) in enumerate(analyzed_candidates[i + 1 :], i + 1):
				if node_id_b in processed:
					continue

				if self._elements_spatially_overlap(node_a, node_b):
					current_group.append((node_id_b, node_b, analysis_b))
					processed.add(node_id_b)

			if len(current_group) > 1:  # Only add groups with conflicts
				spatial_groups.append(current_group)

		return spatial_groups

	def _elements_spatially_overlap(self, node_a: EnhancedDOMTreeNode, node_b: EnhancedDOMTreeNode) -> bool:
		"""Check if two elements spatially overlap (are positioned on top of each other)."""
		if not node_a.snapshot_node or not node_b.snapshot_node:
			return False

		bbox_a = getattr(node_a.snapshot_node, 'bounding_box', None)
		bbox_b = getattr(node_b.snapshot_node, 'bounding_box', None)

		if not bbox_a or not bbox_b:
			return False

		# Get coordinates and dimensions
		x1, y1 = bbox_a.get('x', 0), bbox_a.get('y', 0)
		w1, h1 = bbox_a.get('width', 0), bbox_a.get('height', 0)
		x2, y2 = bbox_b.get('x', 0), bbox_b.get('y', 0)
		w2, h2 = bbox_b.get('width', 0), bbox_b.get('height', 0)

		# Calculate overlap area
		left = max(x1, x2)
		right = min(x1 + w1, x2 + w2)
		top = max(y1, y2)
		bottom = min(y1 + h1, y2 + h2)

		if left >= right or top >= bottom:
			return False  # No overlap

		overlap_area = (right - left) * (bottom - top)
		area_a = w1 * h1
		area_b = w2 * h2

		if area_a == 0 or area_b == 0:
			return False

		# Consider elements overlapping if overlap is >70% of either element's area
		overlap_threshold = 0.7
		overlap_ratio_a = overlap_area / area_a
		overlap_ratio_b = overlap_area / area_b

		return overlap_ratio_a > overlap_threshold or overlap_ratio_b > overlap_threshold

	def _choose_best_spatial_candidate(self, candidates):
		"""Choose the best candidate from a group of spatially overlapping elements."""
		if len(candidates) == 1:
			return candidates[0]

		# Priority order: prefer actual interactive elements over containers
		priority_order = ['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA', 'DIV', 'SPAN']

		def get_priority(candidate):
			node = candidate[0]
			element_type = node.node_name.upper()
			try:
				return priority_order.index(element_type)
			except ValueError:
				return len(priority_order)  # Unknown elements go last

		# Sort by priority, then by clickability
		candidates.sort(key=lambda c: (get_priority(c), not self._is_likely_interactive(c[0])))
		return candidates[0]

	def _is_likely_interactive(self, node: EnhancedDOMTreeNode) -> bool:
		"""Quick check if a node is likely interactive."""
		element_type = node.node_name.upper()

		# Form elements are always interactive
		if element_type in ['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'A']:
			return True

		# Check for interactive attributes
		if node.attributes:
			interactive_attrs = ['onclick', 'role', 'tabindex', 'href']
			if any(attr in node.attributes for attr in interactive_attrs):
				return True

		return False

	def _get_element_depth(self, node: EnhancedDOMTreeNode) -> int:
		"""Get the depth of an element in the DOM tree (lower is closer to root)."""
		depth = 0
		current = node
		while hasattr(current, 'parent_node') and current.parent_node:
			depth += 1
			current = current.parent_node
			if depth > 50:  # Prevent infinite loops
				break
		return depth

	def _is_structural_element_fast(self, node: EnhancedDOMTreeNode) -> bool:
		"""ENHANCED structural element detection with legacy method insights for better filtering."""
		if node.node_type != NodeType.ELEMENT_NODE:
			return False

		node_name = node.node_name.upper()

		# Skip obvious structural elements (enhanced list from legacy)
		structural_elements = {
			'HTML',
			'HEAD',
			'BODY',
			'TITLE',
			'META',
			'STYLE',
			'SCRIPT',
			'LINK',
			'#DOCUMENT',
			'#COMMENT',
			'NOSCRIPT',
			'BASE',
			'TEMPLATE',
		}

		if node_name in structural_elements:
			return True

		# **ENHANCED CONTAINER ANALYSIS** from legacy method
		if node_name in {'DIV', 'SPAN', 'SECTION', 'ARTICLE', 'MAIN', 'HEADER', 'FOOTER', 'NAV', 'ASIDE'}:
			# Quick attribute check
			if not node.attributes:
				return True

			# **EXPANDED MEANINGFUL ATTRIBUTES** from legacy insights
			meaningful_attrs = {
				'onclick',
				'onmousedown',
				'onkeydown',
				'data-action',
				'data-toggle',
				'data-href',
				'role',
				'tabindex',
				'href',
				'aria-label',
				'aria-labelledby',
				'jsaction',
				'ng-click',
				'@click',
				'v-on:',
				'(click)',
			}

			# Check for any cursor styling (from enhanced cursor detection)
			has_interactive_cursor = False
			if node.snapshot_node and hasattr(node.snapshot_node, 'computed_styles'):
				computed_styles_info = node.snapshot_node.computed_styles or {}
				has_interactive_cursor, _, _ = ElementAnalysis._has_any_interactive_cursor(node, computed_styles_info)

			# Not structural if it has meaningful attributes OR interactive cursor
			if any(attr in node.attributes for attr in meaningful_attrs) or has_interactive_cursor:
				return False

			# **ENHANCED VISIBILITY CHECK** - don't skip potentially visible containers
			if node.snapshot_node:
				bbox = getattr(node.snapshot_node, 'bounding_box', None)
				if bbox and bbox.get('width', 0) > 0 and bbox.get('height', 0) > 0:
					# Has meaningful size, check if it might be interactive
					return False

			# If no meaningful attributes and no size, likely structural
			return True

		# **SVG ELEMENT HANDLING** - SVG elements can be interactive
		if node_name in {'SVG', 'PATH', 'CIRCLE', 'RECT', 'G', 'USE'}:
			# SVG elements with click handlers or roles are interactive
			if node.attributes:
				svg_interactive_attrs = {'onclick', 'role', 'tabindex', 'aria-label', 'data-action'}
				if any(attr in node.attributes for attr in svg_interactive_attrs):
					return False  # Not structural, potentially interactive
			return True  # Most SVG elements are decorative

		return False

	def _is_ax_interactive_fast(self, node: EnhancedDOMTreeNode, include_all: bool = False) -> bool:
		"""Fast check if node is interactive according to AX tree."""
		if not node.ax_node:
			return False

		# Check AX role
		if node.ax_node.role:
			interactive_roles = {
				'button',
				'link',
				'menuitem',
				'tab',
				'option',
				'checkbox',
				'radio',
				'slider',
				'spinbutton',
				'switch',
				'textbox',
				'combobox',
				'listbox',
				'tree',
				'grid',
				'gridcell',
				'searchbox',
				'menuitemradio',
				'menuitemcheckbox',
			}
			if node.ax_node.role.lower() in interactive_roles:
				# Special filtering for calendar/date picker elements
				if node.ax_node.role.lower() == 'gridcell' and node.node_name.upper() == 'DIV':
					if self._is_likely_calendar_cell_fast(node):
						self.metrics.skipped_calendar_cells += 1
						return False
				return True

		# Fast check AX properties for focusability
		if node.ax_node.properties:
			for prop in node.ax_node.properties:
				if prop.name == AXPropertyName.FOCUSABLE and prop.value:
					return True

		return False

	def _is_dom_interactive_fast(self, node: EnhancedDOMTreeNode) -> bool:
		"""Fast check if node is interactive according to DOM/snapshot data."""
		if node.node_type != NodeType.ELEMENT_NODE:
			return False

		node_name = node.node_name.upper()

		# Always interactive form elements
		if node_name in {'INPUT', 'BUTTON', 'SELECT', 'TEXTAREA', 'OPTION'}:
			return True

		# Links with href
		if node_name == 'A' and node.attributes and 'href' in node.attributes:
			return True

		# Fast snapshot-based clickability
		if node.snapshot_node and getattr(node.snapshot_node, 'is_clickable', False):
			return True

		# Fast comprehensive cursor check
		if node.snapshot_node:
			computed_styles_info = {}
			if hasattr(node.snapshot_node, 'computed_styles'):
				computed_styles_info = node.snapshot_node.computed_styles or {}

			has_cursor, _, _ = ElementAnalysis._has_any_interactive_cursor(node, computed_styles_info)
			if has_cursor:
				return True

		# Fast attribute checks
		if node.attributes:
			# Event handlers
			event_attrs = {'onclick', 'onmousedown', 'onkeydown', 'data-action', 'data-toggle', 'jsaction'}
			if any(attr in node.attributes for attr in event_attrs):
				return True

			# Role attributes
			role = node.attributes.get('role', '').lower()
			if role in {
				'button',
				'link',
				'menuitem',
				'tab',
				'option',
				'checkbox',
				'radio',
				'slider',
				'spinbutton',
				'switch',
				'textbox',
				'combobox',
				'listbox',
			}:
				return True

			# Positive tabindex
			tabindex = node.attributes.get('tabindex')
			if tabindex and tabindex.isdigit() and int(tabindex) >= 0:
				return True

		return False

	def _filter_by_viewport_and_deduplicate_fast(self, candidates) -> List[EnhancedDOMTreeNode]:
		"""Fast filter candidates by viewport and remove duplicates."""
		filtered = []
		seen_elements: Set[str] = set()  # Track unique elements by x_path

		# **ENHANCED: Check if we should include ALL AX elements (when threshold = 0)**
		should_include_all_ax = getattr(self, '_include_all_ax_elements', False)

		for candidate_tuple in candidates:
			candidate_node = candidate_tuple[0]  # First element is always the node
			# candidate_tuple could be (node, 'analyzed', analysis) or (node, 'type')

			if should_include_all_ax:
				# **SCORE THRESHOLD = 0 MODE: NO filtering - include EVERYTHING with AX nodes**
				print(
					f'🎯 PROCESSING AX ELEMENT: {candidate_node.node_name} (type: {candidate_tuple[1] if len(candidate_tuple) > 1 else "unknown"})'
				)

				# NO filtering whatsoever - include everything
				# NO text node filtering
				# NO visibility filtering
				# NO viewport filtering
				# NO spatial deduplication
				# NO xpath deduplication

				# Just add everything to filtered list
				print(f'🎯 ADDING TO FILTERED LIST: {candidate_node.node_name}')
				filtered.append(candidate_node)
				continue
			else:
				# **NORMAL MODE: Standard filtering**

				# Fast visibility check (cached)
				visibility_key = f'vis_{id(candidate_node)}'
				if visibility_key not in self._visibility_cache:
					self._visibility_cache[visibility_key] = self._is_element_visible_fast(candidate_node)

				if not self._visibility_cache[visibility_key]:
					self.metrics.skipped_invisible += 1
					continue

				# Fast viewport check
				if not self._is_in_viewport_or_special_context_fast(candidate_node):
					self.metrics.skipped_outside_viewport += 1
					continue

				# Fast deduplication
				element_key = candidate_node.x_path
				if element_key in seen_elements:
					self.metrics.skipped_duplicates += 1
					continue

			seen_elements.add(element_key)
			filtered.append(candidate_node)

		self.metrics.after_visibility_filter = len(filtered) + self.metrics.skipped_invisible
		self.metrics.after_deduplication = len(filtered)
		return filtered

	def _is_element_visible_fast(self, node: EnhancedDOMTreeNode) -> bool:
		"""Fast visibility check."""
		if not node.snapshot_node:
			return False

		# Fast visibility check
		is_visible = getattr(node.snapshot_node, 'is_visible', None)
		if is_visible is False:
			return False

		# Fast bounding box check
		bbox = getattr(node.snapshot_node, 'bounding_box', None)
		if not bbox:
			return False

		# Fast size check
		width, height = bbox.get('width', 0), bbox.get('height', 0)
		if width <= 0 or height <= 0:
			return False

		# Fast position check
		x, y = bbox.get('x', 0), bbox.get('y', 0)
		if x < -1000 or y < -1000:
			return False

		return True

	def _is_in_viewport_or_special_context_fast(self, node: EnhancedDOMTreeNode) -> bool:
		"""Fast check if element is in viewport."""
		# If no viewport info, assume visible
		if not self.viewport_info:
			return True

		# Fast viewport filtering for main page content
		if not node.snapshot_node:
			return True

		bbox = getattr(node.snapshot_node, 'bounding_box', None)
		if not bbox:
			return True

		# Fast viewport calculation
		viewport_width = self.viewport_info.get('width', 1920)
		viewport_height = self.viewport_info.get('height', 1080)
		scroll_x = self.viewport_info.get('scroll_x', 0)
		scroll_y = self.viewport_info.get('scroll_y', 0)

		# Fast intersection check with small buffer
		buffer = 50
		elem_left = bbox.get('x', 0)
		elem_top = bbox.get('y', 0)
		elem_right = elem_left + bbox.get('width', 0)
		elem_bottom = elem_top + bbox.get('height', 0)

		viewport_left = scroll_x - buffer
		viewport_top = scroll_y - buffer
		viewport_right = scroll_x + viewport_width + buffer
		viewport_bottom = scroll_y + viewport_height + buffer

		return (
			elem_right > viewport_left
			and elem_left < viewport_right
			and elem_bottom > viewport_top
			and elem_top < viewport_bottom
		)

	def _build_minimal_simplified_tree_fast(self, filtered_nodes: List[EnhancedDOMTreeNode]) -> List[SimplifiedNode]:
		"""Build minimal simplified tree structure for fast processing."""
		simplified_elements = []

		for node in filtered_nodes:
			simplified = SimplifiedNode(original_node=node)
			simplified_elements.append(simplified)

		return simplified_elements

	def _serialize_minimal_tree_fast(self, simplified_elements: List[SimplifiedNode], include_attributes: list[str]) -> str:
		"""Create highly compressed semantic representation for LLM consumption."""

		# Step 1: Convert to compressed elements
		self._convert_to_compressed_elements(simplified_elements)

		# Step 2: Detect and group semantic structures
		self._detect_semantic_groups()

		# Step 3: Generate compressed text representation
		return self._generate_compressed_text()

	def _convert_to_compressed_elements(self, simplified_elements: List[SimplifiedNode]) -> None:
		"""Convert simplified nodes to compressed element format."""
		self._compressed_elements = []

		for simplified in simplified_elements:
			if simplified.interactive_index is not None:
				compressed = self._create_compressed_element(simplified)
				if compressed:
					self._compressed_elements.append(compressed)

	def _create_compressed_element(self, simplified: SimplifiedNode) -> Optional[CompressedElement]:
		"""Create a compressed element from a simplified node."""
		node = simplified.original_node
		attrs = node.attributes or {}

		# Determine element type and action
		element_type, action_type = self._determine_element_type_and_action(node)

		# Extract meaningful label
		label = self._extract_element_label(node, attrs)

		# Extract target (href, action, etc.)
		target = self._extract_element_target(node, attrs)

		# Extract essential attributes only
		essential_attrs = self._extract_essential_attributes(node, attrs)

		# Determine context
		context = self._determine_element_context(simplified)

		# Ensure we have a valid index
		if simplified.interactive_index is None:
			return None

		return CompressedElement(
			index=simplified.interactive_index,
			element_type=element_type,
			action_type=action_type,
			label=label,
			target=target,
			attributes=essential_attrs,
			context=context,
		)

	def _determine_element_type_and_action(self, node: EnhancedDOMTreeNode) -> Tuple[str, str]:
		"""Determine compressed element type and action type."""
		element_name = node.node_name.upper()
		attrs = node.attributes or {}

		# Form elements
		if element_name == 'INPUT':
			input_type = attrs.get('type', 'text').lower()
			type_map = {
				'submit': ('SUBMIT', 'click'),
				'button': ('BUTTON', 'click'),
				'reset': ('RESET', 'click'),
				'checkbox': ('CHECKBOX', 'toggle'),
				'radio': ('RADIO', 'select'),
				'file': ('FILE', 'upload'),
				'search': ('SEARCH', 'input'),
				'email': ('EMAIL', 'input'),
				'password': ('PASSWORD', 'input'),
				'tel': ('PHONE', 'input'),
				'url': ('URL', 'input'),
				'number': ('NUMBER', 'input'),
				'range': ('SLIDER', 'slide'),
				'date': ('DATE', 'pick'),
				'time': ('TIME', 'pick'),
				'color': ('COLOR', 'pick'),
			}
			return type_map.get(input_type, ('INPUT', 'input'))

		elif element_name == 'BUTTON':
			button_type = attrs.get('type', 'button').lower()
			if button_type == 'submit':
				return ('SUBMIT', 'click')
			return ('BUTTON', 'click')

		elif element_name == 'SELECT':
			return ('SELECT', 'choose')

		elif element_name == 'TEXTAREA':
			return ('TEXTAREA', 'input')

		elif element_name == 'A':
			if attrs.get('href'):
				return ('LINK', 'navigate')
			return ('LINK', 'click')

		# Interactive containers
		elif element_name in ['DIV', 'SPAN']:
			role = attrs.get('role', '').lower()
			role_map = {
				'button': ('BUTTON', 'click'),
				'link': ('LINK', 'click'),
				'tab': ('TAB', 'click'),
				'menuitem': ('MENU_ITEM', 'click'),
				'option': ('OPTION', 'select'),
				'checkbox': ('CHECKBOX', 'toggle'),
				'radio': ('RADIO', 'select'),
				'slider': ('SLIDER', 'slide'),
			}
			if role in role_map:
				return role_map[role]

			# Check for common interactive classes
			classes = attrs.get('class', '').lower()
			if any(cls in classes for cls in ['btn', 'button']):
				return ('BUTTON', 'click')
			elif any(cls in classes for cls in ['link', 'nav']):
				return ('LINK', 'click')
			elif any(cls in classes for cls in ['tab']):
				return ('TAB', 'click')
			elif any(cls in classes for cls in ['dropdown', 'select']):
				return ('DROPDOWN', 'click')

			return ('CONTAINER', 'click')

		# Media and other elements
		elif element_name == 'IMG':
			return ('IMAGE', 'click')
		elif element_name in ['SVG', 'PATH', 'CIRCLE', 'RECT']:
			return ('ICON', 'click')
		elif element_name in ['LI', 'TD', 'TH']:
			return ('ITEM', 'click')

		return (element_name, 'click')

	def _extract_element_label(self, node: EnhancedDOMTreeNode, attrs: Dict[str, str]) -> str:
		"""Extract meaningful text content that an LLM can understand."""

		# Priority 1: Actual visible text content from the element
		visible_text = self._extract_visible_text_content(node)
		if visible_text and len(visible_text.strip()) > 1:
			return visible_text.strip()[:80]

		# Priority 2: ARIA label (accessibility text)
		if 'aria-label' in attrs and attrs['aria-label'].strip():
			return attrs['aria-label'].strip()[:80]

		# Priority 3: Text content from accessible name (screen reader text)
		if node.ax_node and node.ax_node.name and node.ax_node.name.strip():
			return node.ax_node.name.strip()[:80]

		# Priority 4: Title attribute (tooltip text)
		if 'title' in attrs and attrs['title'].strip():
			return f'tooltip: {attrs["title"].strip()[:60]}'

		# Priority 5: Alt text for images (describes what image shows)
		if 'alt' in attrs and attrs['alt'].strip():
			return f'image: {attrs["alt"].strip()[:60]}'

		# Priority 6: Placeholder for inputs (hint text)
		if 'placeholder' in attrs and attrs['placeholder'].strip():
			return f'placeholder: {attrs["placeholder"].strip()[:50]}'

		# Priority 7: Value for buttons/inputs (current value)
		if 'value' in attrs and attrs['value'].strip():
			return attrs['value'].strip()[:60]

		# Priority 8: Label reference (for form inputs)
		label_text = self._extract_label_text(node, attrs)
		if label_text:
			return f'label: {label_text[:60]}'

		# Priority 9: Link destination (for links)
		if 'href' in attrs and attrs['href'].strip():
			href = attrs['href'].strip()
			if href.startswith('#'):
				return f'link to section: {href[1:30]}'
			elif href.startswith('mailto:'):
				return f'email: {href[7:40]}'
			elif href.startswith('tel:'):
				return f'phone: {href[4:25]}'
			elif href.startswith('/') or 'http' in href:
				return f'link: {self._clean_url_for_display(href)[:40]}'

		# Priority 10: Descriptive attributes
		descriptive_text = self._extract_descriptive_attributes(node, attrs)
		if descriptive_text:
			return descriptive_text

		# Priority 11: Element type with context
		element_type = node.node_name.lower()
		if element_type == 'input' and 'type' in attrs:
			return f'{attrs["type"]} input'
		elif element_type in ['button', 'a', 'select', 'textarea']:
			return f'{element_type} element'
		else:
			return f'<{element_type}>'

	def _extract_visible_text_content(self, node: EnhancedDOMTreeNode) -> str:
		"""Extract actual visible text content from the element and its children."""
		text_parts = []

		# First try to get text from the node itself
		if node.node_type == NodeType.TEXT_NODE and node.node_value:
			text_parts.append(node.node_value.strip())

		# Get text from direct text children
		if hasattr(node, 'children_nodes') and node.children_nodes:
			for child in node.children_nodes:
				if child.node_type == NodeType.TEXT_NODE and child.node_value:
					child_text = child.node_value.strip()
					if child_text and len(child_text) > 1:
						text_parts.append(child_text)
				elif child.node_type == NodeType.ELEMENT_NODE:
					# Get text from simple child elements (span, strong, em, etc.)
					if child.node_name.upper() in ['SPAN', 'STRONG', 'EM', 'B', 'I', 'SMALL']:
						child_text = self._extract_visible_text_content(child)
						if child_text:
							text_parts.append(child_text)

		# Clean up and join text parts
		combined_text = ' '.join(text_parts).strip()
		# Remove excessive whitespace
		import re

		combined_text = re.sub(r'\s+', ' ', combined_text)

		return combined_text

	def _extract_label_text(self, node: EnhancedDOMTreeNode, attrs: Dict[str, str]) -> str:
		"""Extract text from associated label elements."""
		# Check if this input has a label via 'for' attribute
		if 'id' in attrs and attrs['id']:
			# In a real implementation, we'd search the DOM for label[for="id"]
			# For now, we'll use a simplified approach
			pass

		# Check for aria-labelledby reference
		if 'aria-labelledby' in attrs:
			# Would need to look up the referenced element
			pass

		# Check if this element is wrapped in a label
		# This is a simplified approach - in practice we'd traverse up the tree
		return ''

	def _clean_url_for_display(self, url: str) -> str:
		"""Clean URL for human-readable display."""
		if url.startswith('http://') or url.startswith('https://'):
			try:
				from urllib.parse import urlparse

				parsed = urlparse(url)
				# Return domain + path
				result = parsed.netloc
				if parsed.path and parsed.path != '/':
					result += parsed.path
				return result
			except:
				return url
		return url

	def _extract_descriptive_attributes(self, node: EnhancedDOMTreeNode, attrs: Dict[str, str]) -> str:
		"""Extract descriptive information from element attributes."""
		# Input type descriptions
		if node.node_name.upper() == 'INPUT' and 'type' in attrs:
			input_type = attrs['type'].lower()
			type_descriptions = {
				'text': 'text input field',
				'email': 'email input field',
				'password': 'password input field',
				'search': 'search input field',
				'tel': 'phone number input field',
				'url': 'URL input field',
				'number': 'number input field',
				'checkbox': 'checkbox',
				'radio': 'radio button',
				'submit': 'submit button',
				'button': 'button',
				'file': 'file upload button',
				'date': 'date picker',
				'time': 'time picker',
				'range': 'slider',
			}
			if input_type in type_descriptions:
				return type_descriptions[input_type]

		# Role descriptions
		if 'role' in attrs:
			role = attrs['role'].lower()
			role_descriptions = {
				'button': 'clickable button',
				'link': 'clickable link',
				'menuitem': 'menu option',
				'tab': 'tab button',
				'checkbox': 'checkbox',
				'radio': 'radio button',
				'slider': 'slider control',
				'textbox': 'text input',
				'combobox': 'dropdown selector',
			}
			if role in role_descriptions:
				return role_descriptions[role]

		# Check for required/disabled state
		state_info = []
		if 'required' in attrs:
			state_info.append('required')
		if 'disabled' in attrs:
			state_info.append('disabled')
		if 'checked' in attrs:
			state_info.append('checked')

		if state_info:
			return f'form field ({", ".join(state_info)})'

		return ''

	def _extract_element_target(self, node: EnhancedDOMTreeNode, attrs: Dict[str, str]) -> Optional[str]:
		"""Extract target URL, action, or other destination."""

		# Links
		if 'href' in attrs and attrs['href'].strip():
			href = attrs['href'].strip()
			# Compress common URL patterns
			if href.startswith('javascript:'):
				return 'javascript'
			elif href.startswith('mailto:'):
				return f'mailto:{href[7:30]}'
			elif href.startswith('tel:'):
				return f'tel:{href[4:20]}'
			elif href.startswith('#'):
				return f'#{href[1:20]}'
			elif href.startswith('/'):
				return href[:30]
			elif 'http' in href:
				# Extract domain
				try:
					from urllib.parse import urlparse

					parsed = urlparse(href)
					return f'{parsed.netloc}{parsed.path[:20]}'
				except:
					return href[:30]
			return href[:30]

		# Form actions
		if 'action' in attrs and attrs['action'].strip():
			return attrs['action'].strip()[:30]

		# Data attributes that indicate targets
		for attr in ['data-href', 'data-url', 'data-target', 'data-action']:
			if attr in attrs and attrs[attr].strip():
				return attrs[attr].strip()[:30]

		return None

	def _extract_essential_attributes(self, node: EnhancedDOMTreeNode, attrs: Dict[str, str]) -> Dict[str, str]:
		"""Extract only essential attributes for LLM understanding."""
		essential = {}

		# Essential for form elements
		if 'type' in attrs:
			essential['type'] = attrs['type']
		if 'required' in attrs:
			essential['required'] = 'true'
		if 'disabled' in attrs:
			essential['disabled'] = 'true'
		if 'readonly' in attrs:
			essential['readonly'] = 'true'

		# Essential for navigation understanding
		if 'role' in attrs and attrs['role'] not in ['button', 'link']:  # Don't duplicate obvious roles
			essential['role'] = attrs['role']

		# State information
		if 'checked' in attrs:
			essential['checked'] = 'true'
		if 'selected' in attrs:
			essential['selected'] = 'true'
		if 'aria-expanded' in attrs:
			essential['expanded'] = attrs['aria-expanded']
		if 'aria-pressed' in attrs:
			essential['pressed'] = attrs['aria-pressed']

		return essential

	def _determine_element_context(self, simplified: SimplifiedNode) -> Optional[str]:
		"""Determine the semantic context of the element."""
		# Context information removed - no iframe/shadow DOM processing
		return None

	def _detect_semantic_groups(self) -> None:
		"""Detect semantic groups of related elements."""
		self._semantic_groups = []

		# Group elements by their semantic relationships
		grouped_indices = set()

		# Detect forms
		self._detect_form_groups(grouped_indices)

		# Detect navigation
		self._detect_navigation_groups(grouped_indices)

		# Detect dropdowns and menus
		self._detect_dropdown_menu_groups(grouped_indices)

		# Detect tables
		self._detect_table_groups(grouped_indices)

		# Detect lists
		self._detect_list_groups(grouped_indices)

		# Detect tabs and accordions
		self._detect_tab_accordion_groups(grouped_indices)

		# Remaining ungrouped elements
		self._create_content_groups(grouped_indices)

	def _detect_form_groups(self, grouped_indices: Set[int]) -> None:
		"""Detect form-related element groups."""
		current_form = []

		for elem in self._compressed_elements:
			if elem.index in grouped_indices:
				continue

			# Form elements
			if elem.action_type in ['input', 'choose', 'toggle', 'select', 'click'] and elem.element_type in [
				'INPUT',
				'EMAIL',
				'PASSWORD',
				'PHONE',
				'URL',
				'NUMBER',
				'SEARCH',
				'TEXTAREA',
				'SELECT',
				'CHECKBOX',
				'RADIO',
				'SUBMIT',
				'BUTTON',
				'FILE',
				'DATE',
				'TIME',
			]:
				current_form.append(elem)
				grouped_indices.add(elem.index)

			# If we hit a non-form element and have form elements, create group
			elif current_form:
				self._create_form_group(current_form)
				current_form = []

		# Handle remaining form elements
		if current_form:
			self._create_form_group(current_form)

	def _create_form_group(self, form_elements: List[CompressedElement]) -> None:
		"""Create a form group from elements."""
		if not form_elements:
			return

		# Determine form title
		submit_elements = [e for e in form_elements if e.element_type in ['SUBMIT', 'BUTTON']]
		if submit_elements:
			title = f'Form: {submit_elements[0].label}'
		else:
			title = 'Form'

		group = SemanticGroup(group_type=ElementGroup.FORM, title=title, elements=form_elements)
		self._semantic_groups.append(group)

	def _detect_navigation_groups(self, grouped_indices: Set[int]) -> None:
		"""Detect navigation-related element groups."""
		nav_elements = []

		for elem in self._compressed_elements:
			if elem.index in grouped_indices:
				continue

			# Navigation elements
			if (
				elem.element_type == 'LINK'
				and elem.target
				and not elem.target.startswith(('mailto:', 'tel:', 'javascript:'))
				and elem.target != '#'
			):
				nav_elements.append(elem)
				grouped_indices.add(elem.index)

		# Group consecutive navigation elements
		if nav_elements:
			group = SemanticGroup(group_type=ElementGroup.NAVIGATION, title='Navigation', elements=nav_elements)
			self._semantic_groups.append(group)

	def _detect_dropdown_menu_groups(self, grouped_indices: Set[int]) -> None:
		"""Detect dropdown and menu groups."""
		dropdown_elements = []

		for elem in self._compressed_elements:
			if elem.index in grouped_indices:
				continue

			# Dropdown/menu elements
			if (
				elem.element_type in ['DROPDOWN', 'MENU_ITEM', 'OPTION', 'TAB']
				or 'dropdown' in elem.label.lower()
				or 'menu' in elem.label.lower()
			):
				dropdown_elements.append(elem)
				grouped_indices.add(elem.index)

		if dropdown_elements:
			group = SemanticGroup(group_type=ElementGroup.DROPDOWN, title='Menu/Dropdown', elements=dropdown_elements)
			self._semantic_groups.append(group)

	def _detect_table_groups(self, grouped_indices: Set[int]) -> None:
		"""Detect table-related groups."""
		table_elements = []

		for elem in self._compressed_elements:
			if elem.index in grouped_indices:
				continue

			if elem.element_type == 'ITEM' and elem.context and ('table' in elem.context or 'grid' in elem.context):
				table_elements.append(elem)
				grouped_indices.add(elem.index)

		if table_elements:
			group = SemanticGroup(group_type=ElementGroup.TABLE, title='Table/Grid', elements=table_elements)
			self._semantic_groups.append(group)

	def _detect_list_groups(self, grouped_indices: Set[int]) -> None:
		"""Detect list-related groups."""
		list_elements = []

		for elem in self._compressed_elements:
			if elem.index in grouped_indices:
				continue

			if elem.element_type == 'ITEM':
				list_elements.append(elem)
				grouped_indices.add(elem.index)

		if list_elements:
			group = SemanticGroup(group_type=ElementGroup.LIST, title='List Items', elements=list_elements)
			self._semantic_groups.append(group)

	def _detect_tab_accordion_groups(self, grouped_indices: Set[int]) -> None:
		"""Detect tab and accordion groups."""
		tab_elements = []

		for elem in self._compressed_elements:
			if elem.index in grouped_indices:
				continue

			if elem.element_type == 'TAB' or 'tab' in elem.label.lower():
				tab_elements.append(elem)
				grouped_indices.add(elem.index)

		if tab_elements:
			group = SemanticGroup(group_type=ElementGroup.TABS, title='Tabs', elements=tab_elements)
			self._semantic_groups.append(group)

	def _create_content_groups(self, grouped_indices: Set[int]) -> None:
		"""Create content groups for remaining ungrouped elements."""
		ungrouped = [elem for elem in self._compressed_elements if elem.index not in grouped_indices]

		if ungrouped:
			group = SemanticGroup(group_type=ElementGroup.CONTENT, title='Interactive Content', elements=ungrouped)
			self._semantic_groups.append(group)

	def _generate_compressed_text(self) -> str:
		"""Generate clean LLM-friendly text focused on user interactions."""
		lines = []

		# Generate semantic groups with clean formatting
		for group in self._semantic_groups:
			if not group.elements:
				continue

			# Create clean group title
			group_title = self._create_friendly_group_title(group)
			lines.append(f'{group_title}:')

			# Format elements cleanly
			for elem in group.elements:
				line = self._format_compressed_element(elem)
				lines.append(f'  {line}')

			lines.append('')  # Empty line between groups

		# Remove the last empty line if present
		if lines and lines[-1] == '':
			lines.pop()

		return '\n'.join(lines)

	def _create_friendly_group_title(self, group: SemanticGroup) -> str:
		"""Create clean, user-friendly group titles."""
		group_type = group.group_type.value
		element_count = len(group.elements)

		# Simple, clean titles without technical jargon
		friendly_titles = {
			'FORM': 'FORM ELEMENTS',
			'NAVIGATION': 'NAVIGATION',
			'DROPDOWN': 'MENUS & DROPDOWNS',
			'MENU': 'MENU OPTIONS',
			'TABLE': 'TABLE ELEMENTS',
			'LIST': 'LIST ITEMS',
			'TOOLBAR': 'BUTTONS & CONTROLS',
			'TABS': 'TABS',
			'ACCORDION': 'COLLAPSIBLE SECTIONS',
			'MODAL': 'DIALOGS & MODALS',
			'CAROUSEL': 'IMAGE CONTROLS',
			'CONTENT': 'INTERACTIVE CONTENT',
			'FOOTER': 'FOOTER LINKS',
			'HEADER': 'HEADER CONTROLS',
			'SIDEBAR': 'SIDEBAR OPTIONS',
		}

		title = friendly_titles.get(group_type, group_type)

		# Add position context if available
		position_context = self._get_group_position_context(group)
		if position_context:
			title = f'{title} ({position_context})'
		elif element_count > 1:
			title = f'{title} ({element_count})'

		return title

	def _get_group_position_context(self, group: SemanticGroup) -> str:
		"""Determine the position context for a group of elements."""
		if not group.elements:
			return ''

		# Analyze the positions of elements in the group to determine location
		y_positions = []
		x_positions = []

		# Get position info from the original DOM nodes if available
		for elem in group.elements:
			# This would need to be enhanced with actual position data
			# For now, we'll use simple heuristics based on element types and attributes
			pass

		# Use element types and attributes to infer position
		element_types = [elem.element_type.lower() for elem in group.elements]

		# Check for header indicators
		if group.group_type.value == 'NAVIGATION':
			# Look for header/nav indicators in attributes
			for elem in group.elements:
				if elem.attributes and any(
					attr in elem.attributes.get('class', '').lower() for attr in ['header', 'nav', 'top', 'main-nav']
				):
					return 'header'
			return 'navigation menu'

		# Check for footer indicators
		if any(attr in str(elem.attributes).lower() for elem in group.elements for attr in ['footer', 'bottom']):
			return 'footer'

		# Check for sidebar indicators
		if any(
			attr in str(elem.attributes).lower()
			for elem in group.elements
			for attr in ['sidebar', 'side', 'left-nav', 'right-nav']
		):
			return 'sidebar'

		# Check for main content indicators
		if group.group_type.value == 'FORM':
			return 'main content'

		return ''

	def _create_group_description(self, group: SemanticGroup) -> str:
		"""Create simple descriptions for element groups."""
		# Remove descriptions for cleaner output - the title is self-explanatory
		return ''

	def _include_element_text_content(self) -> None:
		"""Extract and include text content from elements for better LLM understanding."""
		# This method can be called to enhance element labels with nearby text content
		for elem in self._compressed_elements:
			# If label is generic, try to find better text content
			if elem.label.startswith('<') or len(elem.label) < 3:
				# Could enhance by looking at nearby text nodes or aria-describedby
				pass

	def _format_compressed_element(self, elem: CompressedElement) -> str:
		"""Format a compressed element for clean LLM consumption focused on user-visible content."""
		parts = []

		# Add index in brackets
		parts.append(f'[{elem.index}]')

		# Create clean description without technical jargon
		description = self._create_clean_description(elem)
		parts.append(description)

		# Add meaningful content - prioritize user-visible text
		content = self._extract_meaningful_content(elem)
		if content:
			parts.append(content)

		# Add navigation target for links
		if elem.target and elem.element_type.lower() in ['link']:
			target_desc = self._format_link_destination(elem.target)
			if target_desc:
				parts.append(target_desc)

		return ' '.join(parts)

	def _create_clean_description(self, elem: CompressedElement) -> str:
		"""Create a clean, user-focused description prioritizing role over element type."""
		element_type = elem.element_type.lower()
		action_type = elem.action_type.lower()

		# PRIORITY 1: Check for role attribute and use that instead of element type
		if elem.attributes and 'role' in elem.attributes:
			role = elem.attributes['role'].lower()
			role_descriptions = {
				'button': 'Button',
				'link': 'Link',
				'menuitem': 'Menu item',
				'tab': 'Tab',
				'checkbox': 'Checkbox',
				'radio': 'Radio button',
				'slider': 'Slider',
				'textbox': 'Text input',
				'combobox': 'Dropdown',
				'searchbox': 'Search',
				'switch': 'Switch',
				'option': 'Option',
				'menuitemcheckbox': 'Menu checkbox',
				'menuitemradio': 'Menu radio',
				'listbox': 'List selector',
				'tree': 'Tree view',
				'grid': 'Grid',
				'gridcell': 'Grid cell',
				'spinbutton': 'Number input',
				'progressbar': 'Progress bar',
				'scrollbar': 'Scrollbar',
				'separator': 'Separator',
				'toolbar': 'Toolbar',
				'tooltip': 'Tooltip',
				'dialog': 'Dialog',
				'alertdialog': 'Alert dialog',
				'application': 'Application',
				'banner': 'Banner',
				'complementary': 'Complementary',
				'contentinfo': 'Content info',
				'form': 'Form',
				'main': 'Main content',
				'navigation': 'Navigation',
				'region': 'Region',
				'search': 'Search',
			}
			if role in role_descriptions:
				return role_descriptions[role]
			else:
				# Capitalize the role name as fallback
				return role.replace('_', ' ').replace('-', ' ').title()

		# PRIORITY 2: Use element type only if no meaningful role
		if element_type in ['button', 'submit']:
			return 'Button'
		elif element_type == 'link':
			return 'Link'
		elif element_type in ['input', 'email', 'password', 'search', 'phone', 'url', 'number']:
			return 'Input'
		elif element_type == 'textarea':
			return 'Text area'
		elif element_type == 'select':
			return 'Dropdown'
		elif element_type == 'checkbox':
			return 'Checkbox'
		elif element_type == 'radio':
			return 'Radio button'
		elif element_type in ['file']:
			return 'File upload'
		elif element_type in ['date', 'time']:
			return 'Date/time picker'
		elif element_type == 'slider':
			return 'Slider'
		else:
			return 'Interactive element'

	def _extract_meaningful_content(self, elem: CompressedElement) -> str:
		"""Extract meaningful, user-visible content without technical scoring."""
		content_parts = []

		# For buttons, prioritize the text content
		if elem.element_type.lower() in ['button', 'submit'] and elem.label:
			if not elem.label.startswith('<') and elem.label.strip():
				content_parts.append(f'"{elem.label.strip()}"')

		# For inputs, show placeholder or current value
		elif elem.element_type.lower() in ['input', 'email', 'password', 'search', 'phone', 'url', 'number', 'textarea']:
			if elem.label and 'placeholder:' in elem.label:
				placeholder = elem.label.replace('placeholder:', '').strip()
				content_parts.append(f'placeholder: "{placeholder}"')
			elif elem.label and not elem.label.startswith('<'):
				content_parts.append(f'"{elem.label.strip()}"')

			# Add state information for inputs
			if 'required' in elem.attributes:
				content_parts.append('(required)')
			if 'disabled' in elem.attributes:
				content_parts.append('(disabled)')

		# For checkboxes and radio buttons, show state
		elif elem.element_type.lower() in ['checkbox', 'radio']:
			if elem.label and not elem.label.startswith('<'):
				content_parts.append(f'"{elem.label.strip()}"')

			if 'checked' in elem.attributes:
				content_parts.append('(checked)')
			else:
				content_parts.append('(unchecked)')

		# For dropdowns
		elif elem.element_type.lower() == 'select':
			if elem.label and not elem.label.startswith('<'):
				content_parts.append(f'"{elem.label.strip()}"')
			if 'selected' in elem.attributes:
				content_parts.append('(has selection)')

		# For links, just show the text
		elif elem.element_type.lower() == 'link':
			if elem.label and not elem.label.startswith('<'):
				content_parts.append(f'"{elem.label.strip()}"')

		# For other elements, show label if meaningful
		else:
			if elem.label and not elem.label.startswith('<') and len(elem.label.strip()) > 1:
				content_parts.append(f'"{elem.label.strip()}"')

		# Add enhanced context information
		enhanced_context = self._get_enhanced_element_context(elem)
		if enhanced_context:
			content_parts.append(enhanced_context)

		return ' '.join(content_parts)

	def _get_enhanced_element_context(self, elem: CompressedElement) -> str:
		"""Get enhanced context information for the element."""
		context_parts = []

		# Add interactive state information
		state_info = self._get_interactive_state_info(elem)
		if state_info:
			context_parts.append(state_info)

		# Add action hints
		action_hint = self._get_action_hint(elem)
		if action_hint:
			context_parts.append(action_hint)

		# Add accessibility descriptions
		accessibility_info = self._get_accessibility_context(elem)
		if accessibility_info:
			context_parts.append(accessibility_info)

		return ' '.join(context_parts) if context_parts else ''

	def _get_interactive_state_info(self, elem: CompressedElement) -> str:
		"""Get interactive state information for the element."""
		# Check for expanded/collapsed state
		if 'expanded' in elem.attributes:
			if elem.attributes['expanded'] == 'true':
				return '(expanded)'
			else:
				return '(collapsed)'

		# Check for pressed state
		if 'pressed' in elem.attributes:
			if elem.attributes['pressed'] == 'true':
				return '(pressed)'
			else:
				return '(not pressed)'

		# Check for loading state
		if 'aria-busy' in elem.attributes and elem.attributes['aria-busy'] == 'true':
			return '(loading)'

		return ''

	def _get_action_hint(self, elem: CompressedElement) -> str:
		"""Get hints about what the element does when interacted with."""
		element_type = elem.element_type.lower()

		# Button action hints
		if element_type in ['button', 'submit']:
			if elem.label:
				label_lower = elem.label.lower()
				if any(word in label_lower for word in ['submit', 'send', 'save']):
					return '(submits form)'
				elif any(word in label_lower for word in ['cancel', 'close', 'dismiss']):
					return '(closes dialog)'
				elif any(word in label_lower for word in ['menu', 'nav']):
					return '(opens menu)'
				elif any(word in label_lower for word in ['search', 'find']):
					return '(performs search)'
				elif any(word in label_lower for word in ['delete', 'remove']):
					return '(deletes item)'
				elif any(word in label_lower for word in ['edit', 'modify']):
					return '(opens editor)'

		# Link action hints
		elif element_type == 'link':
			if elem.target:
				if elem.target.startswith('#'):
					return '(jumps to section)'
				elif 'login' in elem.target or 'signin' in elem.target:
					return '(opens login page)'
				elif 'signup' in elem.target or 'register' in elem.target:
					return '(opens signup page)'

		return ''

	def _get_accessibility_context(self, elem: CompressedElement) -> str:
		"""Get accessibility context information."""
		# Check for aria-describedby or helpful descriptions
		if 'aria-describedby' in elem.attributes:
			return '(has help text)'

		# Check for error states
		if 'aria-invalid' in elem.attributes and elem.attributes['aria-invalid'] == 'true':
			return '(has error)'

		# Check for required fields
		if 'aria-required' in elem.attributes and elem.attributes['aria-required'] == 'true':
			return '(required field)'

		return ''

	def _format_link_destination(self, target: str) -> str:
		"""Format link destinations in a clean, user-friendly way."""
		if not target:
			return ''

		if target.startswith('mailto:'):
			return f'(email: {target[7:]})'
		elif target.startswith('tel:'):
			return f'(phone: {target[4:]})'
		elif target.startswith('#'):
			return f'(jumps to: {target[1:]})'
		elif target == 'javascript':
			return '(action)'
		else:
			# Clean up URLs for display
			if len(target) > 30:
				return f'(goes to: {target[:30]}...)'
			else:
				return f'(goes to: {target})'

	def _create_natural_description(self, elem: CompressedElement) -> str:
		"""Create a natural language description of the element."""
		element_type = elem.element_type.lower()
		action_type = elem.action_type.lower()

		# Create human-readable descriptions
		descriptions = {
			('button', 'click'): 'Button',
			('submit', 'click'): 'Submit Button',
			('link', 'navigate'): 'Link',
			('link', 'click'): 'Clickable Link',
			('input', 'input'): 'Text Input',
			('email', 'input'): 'Email Input',
			('password', 'input'): 'Password Input',
			('search', 'input'): 'Search Input',
			('phone', 'input'): 'Phone Input',
			('url', 'input'): 'URL Input',
			('number', 'input'): 'Number Input',
			('textarea', 'input'): 'Text Area',
			('select', 'choose'): 'Dropdown',
			('checkbox', 'toggle'): 'Checkbox',
			('radio', 'select'): 'Radio Button',
			('file', 'upload'): 'File Upload',
			('date', 'pick'): 'Date Picker',
			('time', 'pick'): 'Time Picker',
			('color', 'pick'): 'Color Picker',
			('slider', 'slide'): 'Slider',
			('tab', 'click'): 'Tab',
			('menu_item', 'click'): 'Menu Item',
			('option', 'select'): 'Option',
			('image', 'click'): 'Clickable Image',
			('icon', 'click'): 'Icon',
			('item', 'click'): 'List Item',
			('container', 'click'): 'Clickable Area',
			('dropdown', 'click'): 'Dropdown Menu',
		}

		key = (element_type, action_type)
		if key in descriptions:
			return descriptions[key]

		# Fallback descriptions
		if action_type == 'click':
			return f'Clickable {element_type.title()}'
		elif action_type == 'input':
			return f'{element_type.title()} Input'
		elif action_type == 'select' or action_type == 'choose':
			return f'{element_type.title()} Selector'
		else:
			return f'{element_type.title()}'

	def _format_target_naturally(self, target: str, element_type: str) -> str:
		"""Format target information in natural language."""
		if not target:
			return ''

		# For links
		if element_type.lower() in ['link']:
			if target.startswith('mailto:'):
				return f'(opens email to {target[7:]})'
			elif target.startswith('tel:'):
				return f'(calls {target[4:]})'
			elif target.startswith('#'):
				return f'(jumps to {target[1:]})'
			elif target == 'javascript':
				return '(runs script)'
			else:
				return f'(goes to {target})'

		# For forms
		elif 'submit' in element_type.lower():
			return f'(submits to {target})'

		# For other elements with actions
		else:
			return f'(target: {target})'

	def _format_state_naturally(self, attributes: Dict[str, str]) -> str:
		"""Format element state in natural language."""
		states = []

		if 'disabled' in attributes:
			states.append('disabled')
		if 'required' in attributes:
			states.append('required')
		if 'checked' in attributes:
			states.append('checked')
		if 'selected' in attributes:
			states.append('selected')

		# Format state information
		if 'expanded' in attributes:
			if attributes['expanded'] == 'true':
				states.append('expanded')
			else:
				states.append('collapsed')

		if 'pressed' in attributes:
			if attributes['pressed'] == 'true':
				states.append('pressed')
			else:
				states.append('not pressed')

		if states:
			return f'({", ".join(states)})'

		return ''

	def _assign_indices_to_filtered_elements(self, simplified_elements: List[SimplifiedNode]) -> None:
		"""Assign interactive indices to pre-filtered elements."""
		for simplified in simplified_elements:
			simplified.interactive_index = self._interactive_counter
			self._selector_map[self._interactive_counter] = simplified.original_node
			self._interactive_counter += 1

		# Legacy serialization method completely removed for performance
		# Only the optimized AX tree method is now available

	def _is_likely_calendar_cell_fast(self, node: EnhancedDOMTreeNode) -> bool:
		"""ENHANCED calendar cell detection with sophisticated patterns from legacy method."""
		# If it's a DIV with gridcell role, check if it's part of a large calendar
		if not node.attributes:
			return True  # No attributes, likely just a date cell

		# **ENHANCED CALENDAR PATTERN DETECTION** from legacy method
		if node.attributes:
			classes = node.attributes.get('class', '').lower()
			id_attr = node.attributes.get('id', '').lower()

			# Expanded calendar indicators from legacy method
			calendar_indicators = [
				'date',
				'day',
				'cell',
				'calendar',
				'picker',
				'grid',
				'datepicker',
				'monthview',
				'dayview',
				'weekview',
				'cal-',
				'dp-',
				'date-',
				'picker-',
				'month-',
				'week-',
				'flatpickr',
				'react-datepicker',
				'vue-datepicker',
				'mui-picker',
				'ant-picker',
				'bootstrap-datepicker',
			]

			# Check both class and id attributes for calendar patterns
			combined_attrs = f'{classes} {id_attr}'
			if any(indicator in combined_attrs for indicator in calendar_indicators):
				return True

			# **DATE CONTENT PATTERN DETECTION**: Check if content looks like a date
			if hasattr(node, 'node_value') and node.node_value:
				text_content = str(node.node_value).strip()
				# Simple date patterns: 1-31, day names, month names
				if text_content.isdigit() and 1 <= int(text_content) <= 31:
					return True

		# **ENHANCED STRUCTURAL CHECK** from legacy method
		if node.node_name.upper() == 'DIV':
			# More sophisticated attribute analysis
			attr_count = len(node.attributes)
			has_meaningful_attrs = any(
				attr in node.attributes for attr in ['onclick', 'data-action', 'href', 'role', 'aria-label', 'title']
			)

			# Likely calendar cell if: few attributes AND no meaningful interaction attributes
			if attr_count <= 3 and not has_meaningful_attrs:
				return True

			# Check for typical calendar cell attributes
			if node.attributes:
				data_attrs = [k for k in node.attributes.keys() if k.startswith('data-')]
				# Calendar cells often have data-date, data-day, etc.
				calendar_data_attrs = [
					attr
					for attr in data_attrs
					if any(indicator in attr for indicator in ['date', 'day', 'month', 'year', 'time'])
				]
				if calendar_data_attrs and attr_count <= 4:
					return True

		return False
