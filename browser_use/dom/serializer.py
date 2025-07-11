# @file purpose: Serializes enhanced DOM trees to string format for LLM consumption

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

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
			score += 90  # INCREASED from 70
			evidence.append(f'HIGH PRIORITY: Core form element: {element_name}')

			if attributes.get('type'):
				input_type = attributes['type'].lower()
				evidence.append(f'Input type: {input_type}')
				if input_type in ['submit', 'button', 'reset']:
					score += 10  # Total: 100 points
				elif input_type in ['text', 'email', 'password', 'search', 'tel', 'url']:
					score += 8  # Total: 98 points
				elif input_type in ['checkbox', 'radio']:
					score += 6  # Total: 96 points

			# Don't exclude disabled elements, just score them lower
			if attributes.get('disabled') == 'true':
				score = max(25, score - 40)
				warnings.append('Element is disabled but still detectable')

		# **TIER 2: VERY HIGH PRIORITY (Variable points) - ANY CURSOR STYLING**
		# Check for cursor styling first before other elements
		has_cursor, cursor_type, cursor_score = cls._has_any_interactive_cursor(node, computed_styles_info)
		if has_cursor and element_category == 'unknown':
			element_category = f'cursor_{cursor_type.replace("-", "_")}'
			score += cursor_score
			evidence.append(f'CURSOR DETECTED: Element has cursor: {cursor_type} (+{cursor_score} points)')

			# Additional boost for meaningful elements with interactive cursors
			if element_name in ['DIV', 'SPAN', 'A', 'LI', 'TD', 'TH', 'SECTION', 'ARTICLE']:
				meaningful_boost = min(15, cursor_score // 4)  # Scale boost based on cursor score
				score += meaningful_boost
				evidence.append(f'Meaningful element with {cursor_type} cursor (+{meaningful_boost})')

			# Extra boost for highly interactive cursors on any element
			if cursor_score >= 70:  # For grab, move, copy, etc.
				score += 10
				evidence.append(f'High-interaction cursor type: {cursor_type} (+10)')
			elif cursor_score >= 50:  # For crosshair, zoom, etc.
				score += 5
				evidence.append(f'Medium-interaction cursor type: {cursor_type} (+5)')

		# **TIER 3: HIGH PRIORITY (70-79 points) - Links and strong event indicators**
		if element_name == 'A':
			element_category = 'link'
			score += 70  # INCREASED from 60
			if attributes.get('href'):
				href = attributes['href']
				score += 10  # Total: 80 points
				evidence.append(f'HIGH PRIORITY: Link with href: {href[:50]}...' if len(href) > 50 else f'Link with href: {href}')

				# Analyze href quality
				if href.startswith(('http://', 'https://')):
					score += 5  # Total: 85 points
					evidence.append('External link')
				elif href.startswith('/'):
					score += 4  # Total: 84 points
					evidence.append('Internal absolute link')
			else:
				score += 8  # Total: 78 points
				evidence.append('Link element without href (likely interactive)')

		# **ENHANCED EVENT LISTENER DETECTION** - TIER 2/3 priority
		elif event_listeners:
			element_category = 'event_driven'
			listener_score = cls._score_event_listeners(event_listeners, evidence)
			score += listener_score
			if listener_score >= 70:
				evidence.append('VERY HIGH PRIORITY: Strong event listeners detected')
			elif listener_score >= 50:
				evidence.append('HIGH PRIORITY: Event listeners detected')

		# **ENHANCED ONCLICK DETECTION** - TIER 3 priority
		elif 'onclick' in attributes:
			element_category = 'onclick_handler'
			score += 75  # INCREASED from 45
			evidence.append('HIGH PRIORITY: Has onclick event handler')

		# **TIER 4: MEDIUM-HIGH PRIORITY (50-69 points) - ARIA roles and containers**
		elif attributes.get('role'):
			if element_category == 'unknown':
				element_category = 'aria_role'
			role = attributes['role'].lower()
			interactive_roles = {
				'button': 65,
				'link': 65,
				'menuitem': 60,
				'tab': 60,
				'option': 55,
				'checkbox': 55,
				'radio': 55,
				'switch': 55,
				'slider': 50,
				'spinbutton': 50,
				'combobox': 50,
				'textbox': 50,
			}

			if role in interactive_roles:
				role_score = interactive_roles[role]
				score += role_score
				evidence.append(f'MEDIUM-HIGH PRIORITY: ARIA role: {role} (+{role_score})')

		# **ENHANCED BUTTON DETECTION IN CONTAINERS** - TIER 4-5 priority
		elif element_name in ['DIV', 'SPAN', 'LI', 'TD', 'TH', 'SECTION', 'ARTICLE']:
			if element_category == 'unknown':
				element_category = 'container'

			container_score = cls._analyze_container_interactivity(
				node, attributes, button_indicators, computed_styles_info, evidence
			)
			score += container_score

		# **ENHANCED POSITIONING AND VISIBILITY ANALYSIS**
		positioning_boost = cls._analyze_positioning_and_visibility(
			node, positioning_info, computed_styles_info, evidence, warnings
		)
		score += positioning_boost

		# **ENHANCED TABINDEX ANALYSIS**
		if 'tabindex' in attributes:
			try:
				tabindex = int(attributes['tabindex'])
				if tabindex >= 0:
					score += 25  # INCREASED from 20
					evidence.append(f'ENHANCED: Focusable (tabindex: {tabindex}) (+25)')
				elif tabindex == -1:
					score += 15
					evidence.append('Programmatically focusable (tabindex: -1) (+15)')
			except ValueError:
				warnings.append(f'Invalid tabindex: {attributes["tabindex"]}')

		# **ACCESSIBILITY TREE ENHANCEMENTS**
		accessibility_boost = cls._analyze_accessibility_properties(node, accessibility_info, evidence)
		score += accessibility_boost

		# **DETERMINE FINAL CONFIDENCE** - Adjusted thresholds for new scoring
		if score >= 85:
			confidence = 'DEFINITE'
			confidence_description = 'Very likely interactive (high confidence)'
		elif score >= 65:
			confidence = 'LIKELY'
			confidence_description = 'Probably interactive (good confidence)'
		elif score >= 40:
			confidence = 'POSSIBLE'
			confidence_description = 'Possibly interactive (moderate confidence)'
		elif score >= 20:
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
			# Highest priority cursors (90+ points)
			'pointer': 85,
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
			score_boost += 30  # INCREASED from implied 20
			evidence.append('Accessibility tree marked as focusable (+30)')

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
	iframe_context: str | None = None  # iframe context for selector map
	shadow_context: str | None = None  # Shadow DOM context
	is_consolidated: bool = False  # Flag to track if element was consolidated into parent

	def is_clickable(self) -> bool:
		"""Check if this node is clickable/interactive with comprehensive but conservative detection."""
		# If element was consolidated into parent, it's no longer independently clickable
		if self.is_consolidated:
			return False

		node = self.original_node
		node_name = node.node_name.upper()

		# Debug output for iframe/shadow elements
		is_iframe_or_shadow = self.iframe_context or self.shadow_context
		context_debug = ''
		if self.iframe_context:
			context_debug = f' (iframe: {self.iframe_context})'
		elif self.shadow_context:
			context_debug = f' (shadow: {self.shadow_context})'

		# **EXCLUDE STRUCTURAL CONTAINERS**: Never mark these as interactive
		if node_name in {'HTML', 'BODY', 'HEAD', 'TITLE', 'META', 'STYLE', 'SCRIPT'}:
			if is_iframe_or_shadow and node_name not in {'HEAD', 'TITLE', 'META', 'STYLE', 'SCRIPT'}:
				print(f'    🚫 Excluding structural {node_name}{context_debug}')
			return False

		# **EXCLUDE COMMON CONTAINER ELEMENTS**: Unless they have explicit interactive attributes
		if node_name in {'MAIN', 'SECTION', 'ARTICLE', 'ASIDE', 'NAV', 'HEADER', 'FOOTER', 'FIGURE', 'FIGCAPTION'}:
			# Only allow these if they have explicit interactive attributes
			if node.attributes:
				has_explicit_interaction = any(
					attr in node.attributes
					for attr in [
						'onclick',
						'onmousedown',
						'onkeydown',
						'data-action',
						'data-toggle',
						'data-href',
						'jsaction',
						'tabindex',
					]
				)
				if not has_explicit_interaction:
					if is_iframe_or_shadow:
						print(f'    🚫 Excluding container {node_name}{context_debug} (no explicit interaction)')
					return False
			else:
				if is_iframe_or_shadow:
					print(f'    🚫 Excluding container {node_name}{context_debug} (no attributes)')
				return False

		# **FORM ELEMENTS**: Always interactive if they're genuine form controls
		if node_name in {'INPUT', 'BUTTON', 'SELECT', 'TEXTAREA', 'OPTION'}:
			if is_iframe_or_shadow:
				print(f'    ✅ Form element {node_name}{context_debug} is clickable')
			self.interaction_priority += 10
			return True

		# **LINKS**: Always interactive if they have href
		if node_name == 'A' and node.attributes and 'href' in node.attributes:
			if is_iframe_or_shadow:
				print(f'    ✅ Link {node_name}{context_debug} with href is clickable')
			self.interaction_priority += 9
			return True

		# **TRADITIONAL CLICKABILITY**: From snapshot (high confidence)
		if node.snapshot_node and getattr(node.snapshot_node, 'is_clickable', False):
			if is_iframe_or_shadow:
				print(f'    ✅ Snapshot clickable {node_name}{context_debug}')
			self.interaction_priority += 10
			return True

		# **ANY INTERACTIVE CURSOR**: Include ALL elements with interactive cursor styling (user's request)
		computed_styles_info = {}
		if node.snapshot_node and hasattr(node.snapshot_node, 'computed_styles'):
			computed_styles_info = node.snapshot_node.computed_styles or {}

		has_cursor, cursor_type, cursor_score = ElementAnalysis._has_any_interactive_cursor(node, computed_styles_info)

		if has_cursor:
			# Exclude obvious containers/wrappers but include most cursor-styled elements
			if node_name not in {'HTML', 'BODY', 'MAIN', 'SECTION', 'ARTICLE', 'ASIDE', 'NAV', 'HEADER', 'FOOTER'}:
				if is_iframe_or_shadow:
					print(f'    ✅ Interactive cursor {cursor_type} {node_name}{context_debug} is clickable')
				# Higher priority for more interactive cursor types
				priority_boost = max(1, cursor_score // 25)  # Scale priority with cursor importance
				self.interaction_priority += priority_boost
				return True

		# **INTERACTIVE ARIA ROLES**: From both AX tree and role attribute
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

		# Check AX tree role
		if node.ax_node and node.ax_node.role and node.ax_node.role.lower() in interactive_roles:
			if is_iframe_or_shadow:
				print(f'    ✅ AX role {node.ax_node.role} {node_name}{context_debug} is clickable')
			self.interaction_priority += 9
			return True

		# Check role attribute
		if node.attributes and 'role' in node.attributes and node.attributes['role'].lower() in interactive_roles:
			if is_iframe_or_shadow:
				print(f'    ✅ Role attribute {node.attributes["role"]} {node_name}{context_debug} is clickable')
			self.interaction_priority += 9
			return True

		# **ACCESSIBILITY FOCUSABLE**: Elements marked as focusable by accessibility tree
		if node.ax_node and node.ax_node.properties:
			for prop in node.ax_node.properties:
				if prop.name == AXPropertyName.FOCUSABLE and prop.value:
					if is_iframe_or_shadow:
						print(f'    ✅ AX focusable {node_name}{context_debug} is clickable')
					self.interaction_priority += 7
					return True

		# **CONSERVATIVE CONTAINER HANDLING**: For remaining DIV/SPAN/LABEL elements
		if node_name in {'DIV', 'SPAN', 'LABEL'}:
			result = self._is_container_truly_interactive(node)
			if is_iframe_or_shadow and result:
				print(f'    ✅ Interactive container {node_name}{context_debug} is clickable')
			elif is_iframe_or_shadow and not result:
				print(f'    ❌ Non-interactive container {node_name}{context_debug}')
			elif not result and node_name == 'DIV':
				# Extra debug for non-iframe DIVs that are being filtered
				print(f'    🗑️  Filtered non-interactive DIV{context_debug}')
			return result

		# **EXPLICIT EVENT HANDLERS**: Elements with explicit event handlers
		if node.attributes:
			event_attributes = {
				'onclick',
				'onmousedown',
				'onmouseup',
				'onkeydown',
				'onkeyup',
				'onfocus',
				'onblur',
				'onchange',
				'onsubmit',
				'ondblclick',
			}
			if any(attr in node.attributes for attr in event_attributes):
				if is_iframe_or_shadow:
					print(f'    ✅ Event handler {node_name}{context_debug} is clickable')
				self.interaction_priority += 6
				return True

		# **INTERACTIVE DATA ATTRIBUTES**: Elements with explicit interactive data attributes
		if node.attributes:
			interactive_data_attrs = {
				'data-toggle',
				'data-dismiss',
				'data-action',
				'data-click',
				'data-href',
				'data-target',
				'data-trigger',
				'data-modal',
				'data-tab',
				'jsaction',
			}
			if any(attr in node.attributes for attr in interactive_data_attrs):
				if is_iframe_or_shadow:
					print(f'    ✅ Data attribute {node_name}{context_debug} is clickable')
				self.interaction_priority += 6
				return True

		# **POSITIVE TABINDEX**: Elements explicitly made focusable (excluding -1)
		if node.attributes and 'tabindex' in node.attributes:
			try:
				tabindex = int(node.attributes['tabindex'])
				if tabindex >= 0:
					if is_iframe_or_shadow:
						print(f'    ✅ Tabindex {tabindex} {node_name}{context_debug} is clickable')
					self.interaction_priority += 5
					return True
			except ValueError:
				pass

		# **DRAGGABLE/EDITABLE**: Special interactive capabilities
		if node.attributes:
			if node.attributes.get('draggable') == 'true':
				if is_iframe_or_shadow:
					print(f'    ✅ Draggable {node_name}{context_debug} is clickable')
				self.interaction_priority += 4
				return True
			if node.attributes.get('contenteditable') in {'true', ''}:
				if is_iframe_or_shadow:
					print(f'    ✅ Editable {node_name}{context_debug} is clickable')
				self.interaction_priority += 4
				return True

		# If we got here and it's an iframe/shadow element, show why it wasn't detected
		if is_iframe_or_shadow and node_name in {'BUTTON', 'A', 'INPUT', 'DIV', 'SPAN'}:
			print(f'    ❌ Not clickable: {node_name}{context_debug} (no interaction indicators)')

		return False

	def _is_container_truly_interactive(self, node: EnhancedDOMTreeNode) -> bool:
		"""Simplified check for whether a container element (DIV/SPAN/LABEL) is truly interactive."""
		node_name = node.node_name.upper()

		# **LABELS**: Interactive if they're for form controls or have explicit interaction
		if node_name == 'LABEL':
			if node.attributes:
				# Labels with 'for' attribute that click to focus form elements
				if 'for' in node.attributes:
					self.interaction_priority += 5
					return True
				# Labels with explicit click handlers
				if any(attr in node.attributes for attr in ['onclick', 'data-action', 'data-toggle']):
					self.interaction_priority += 5
					return True
			return False

		# **DIV/SPAN**: More conservative - require STRONG evidence of interactivity
		if node_name in {'DIV', 'SPAN'}:
			if not node.attributes:
				return False

			attrs = node.attributes

			# Require explicit event handlers (stronger evidence)
			explicit_handlers = ['onclick', 'onmousedown', 'onmouseup', 'onkeydown', 'onkeyup']
			if any(attr in attrs for attr in explicit_handlers):
				self.interaction_priority += 4
				return True

			# Require explicit interactive role (stronger evidence)
			role = attrs.get('role', '').lower()
			if role in {'button', 'link', 'menuitem', 'tab', 'option', 'combobox', 'textbox', 'searchbox'}:
				self.interaction_priority += 4
				return True

			# Require explicit interactive data attributes AND additional evidence
			interactive_data_attrs = ['data-action', 'data-toggle', 'data-href', 'jsaction']
			has_data_attr = any(attr in attrs for attr in interactive_data_attrs)

			if has_data_attr:
				# Additional requirements for DIV with data attributes
				if node_name == 'DIV':
					# Also need interactive cursor, tabindex, or role for DIVs
					computed_styles_info = {}
					if node.snapshot_node and hasattr(node.snapshot_node, 'computed_styles'):
						computed_styles_info = node.snapshot_node.computed_styles or {}
					has_cursor, _, _ = ElementAnalysis._has_any_interactive_cursor(node, computed_styles_info)

					has_tabindex = 'tabindex' in attrs and attrs['tabindex'] != '-1'
					has_role = 'role' in attrs

					if has_cursor or has_tabindex or has_role:
						self.interaction_priority += 3
						return True
					else:
						# DIV with only data attributes but no other evidence - likely not interactive
						return False
				else:
					# SPAN with data attributes - allow
					self.interaction_priority += 3
					return True

			# Require positive tabindex (explicitly focusable)
			if 'tabindex' in attrs:
				try:
					tabindex = int(attrs['tabindex'])
					if tabindex >= 0:
						self.interaction_priority += 2
						return True
				except ValueError:
					pass

		return False

	def is_option_element(self) -> bool:
		"""Check if this is an option element that should be grouped."""
		if self.original_node.node_name.upper() == 'OPTION':
			return True

		if (
			self.original_node.attributes
			and 'class' in self.original_node.attributes
			and any(cls in self.original_node.attributes['class'].lower() for cls in ['option', 'menu-item', 'dropdown-item'])
		):
			return True

		return False

	def is_radio_or_checkbox(self) -> bool:
		"""Check if this is a radio button or checkbox."""
		if self.original_node.node_name.upper() == 'INPUT' and self.original_node.attributes:
			input_type = self.original_node.attributes.get('type', '').lower()
			return input_type in {'radio', 'checkbox'}
		return False

	def get_group_name(self) -> str:
		"""Get the name for grouping radio buttons or checkboxes."""
		if self.original_node.attributes:
			return self.original_node.attributes.get('name', '')
		return ''

	def count_direct_clickable_children(self) -> int:
		"""Count how many direct children are clickable."""
		return sum(1 for child in self.children if child.is_clickable())

	def has_any_clickable_descendant(self) -> bool:
		"""Check if this node or any descendant is clickable."""
		if self.is_clickable():
			return True
		return any(child.has_any_clickable_descendant() for child in self.children)

	def is_effectively_visible(self) -> bool:
		"""Check if element is effectively visible considering z-index and other factors."""
		if not self.original_node.snapshot_node:
			return False

		snapshot = self.original_node.snapshot_node

		# Basic visibility checks - handle potential non-boolean type
		is_visible = getattr(snapshot, 'is_visible', None)
		if is_visible is False:
			return False

		# Check computed styles for more sophisticated visibility detection
		computed_styles = getattr(snapshot, 'computed_styles', None)
		if computed_styles:
			# Check display
			if computed_styles.get('display') == 'none':
				return False

			# Check visibility
			if computed_styles.get('visibility') == 'hidden':
				return False

			# Check opacity
			try:
				opacity = float(computed_styles.get('opacity', '1'))
				if opacity == 0:
					return False
			except (ValueError, TypeError):
				pass

			# Check if element is positioned off-screen
			bounding_box = getattr(snapshot, 'bounding_box', None)
			if bounding_box:
				if (
					bounding_box.get('x', 0) < -9000
					or bounding_box.get('y', 0) < -9000
					or bounding_box.get('width', 0) <= 0
					or bounding_box.get('height', 0) <= 0
				):
					return False

			# Check pointer-events
			if computed_styles.get('pointer-events') == 'none':
				return False

		return True

	def has_meaningful_bounds(self) -> bool:
		"""Check if element has meaningful size (not just a wrapper)."""
		if not self.original_node.snapshot_node:
			return False

		bounding_box = getattr(self.original_node.snapshot_node, 'bounding_box', None)
		if not bounding_box:
			return False

		width = bounding_box.get('width', 0)
		height = bounding_box.get('height', 0)

		# Element should have reasonable size
		return width > 10 and height > 10 and width < 2000 and height < 2000


@dataclass(slots=True)
class IFrameContextInfo:
	"""Information about iframe context for selector map."""

	iframe_xpath: str
	iframe_src: str | None
	is_cross_origin: bool
	context_id: str


class DOMTreeSerializer:
	"""Serializes enhanced DOM trees to string format with comprehensive interaction detection."""

	def __init__(self, root_node: EnhancedDOMTreeNode, viewport_info: dict | None = None):
		self.root_node = root_node
		self.viewport_info = viewport_info or {}
		self._interactive_counter = 1
		self._selector_map: dict[int, EnhancedDOMTreeNode] = {}
		self._iframe_contexts: Dict[str, IFrameContextInfo] = {}
		self._shadow_contexts: Dict[str, str] = {}  # shadow_id -> parent_xpath
		self._element_groups: Dict[str, List[SimplifiedNode]] = {}
		self._cross_origin_iframes: List[str] = []

		# Performance caches
		self._visibility_cache: Dict[str, bool] = {}
		self._interactivity_cache: Dict[str, bool] = {}
		self._structural_cache: Dict[str, bool] = {}
		self._analysis_cache: Dict[str, ElementAnalysis] = {}

		# Performance metrics
		self.metrics = PerformanceMetrics()

		# Compressed serialization data
		self._compressed_elements: List[CompressedElement] = []
		self._semantic_groups: List[SemanticGroup] = []

	def serialize_accessible_elements(
		self,
		include_attributes: list[str] | None = None,
	) -> tuple[str, dict[int, EnhancedDOMTreeNode]]:
		"""Convert the enhanced DOM tree to string format with comprehensive detection and aggressive consolidation.

		Args:
			include_attributes: List of attributes to include

		Returns:
			- Serialized string representation including iframe and shadow content
			- Selector map mapping interactive indices to DOM nodes with context
		"""
		if not include_attributes:
			include_attributes = DEFAULT_INCLUDE_ATTRIBUTES

		# Try optimized AX tree-driven approach first
		try:
			result = self._serialize_ax_tree_optimized(include_attributes)
			self.metrics.finish()
			self.metrics.log_summary()
			return result
		except Exception as e:
			print(f'⚠️  AX tree optimization failed ({e}), falling back to full tree traversal')
			# Fall back to original approach
			result = self._serialize_full_tree_legacy(include_attributes)
			self.metrics.finish()
			self.metrics.log_summary()
			return result

	def _serialize_ax_tree_optimized(self, include_attributes: list[str]) -> tuple[str, dict[int, EnhancedDOMTreeNode]]:
		"""OPTIMIZED: Use AX tree nodes directly for 10x speed improvement."""
		print('🚀 Starting AX tree-driven optimization')

		# Reset state
		self._interactive_counter = 1
		self._selector_map = {}
		self._iframe_contexts = {}
		self._shadow_contexts = {}
		self._element_groups = {}
		self._cross_origin_iframes = []

		# Clear caches
		self._visibility_cache.clear()
		self._interactivity_cache.clear()
		self._structural_cache.clear()
		self._analysis_cache.clear()

		# Step 1: Collect interactive candidates from AX tree
		step_start = time.time()
		interactive_candidates = self._collect_ax_interactive_candidates_fast(self.root_node)
		self.metrics.ax_collection_time = time.time() - step_start
		self.metrics.ax_candidates = len([c for c in interactive_candidates if c[1] == 'ax'])
		self.metrics.dom_candidates = len([c for c in interactive_candidates if c[1] == 'dom'])
		print(f'  📊 Found {len(interactive_candidates)} candidates in {self.metrics.ax_collection_time:.3f}s')
		print(f'     • AX candidates: {self.metrics.ax_candidates}')
		print(f'     • DOM candidates: {self.metrics.dom_candidates}')

		# Step 2: Resolve nested conflicts BEFORE filtering
		step_start = time.time()
		conflict_resolved = self.detect_and_resolve_nested_conflicts(interactive_candidates)
		conflict_time = time.time() - step_start
		print(f'  🔧 Resolved nested conflicts: {len(interactive_candidates)} → {len(conflict_resolved)} in {conflict_time:.3f}s')

		# Step 3: Filter by viewport and deduplicate
		step_start = time.time()
		viewport_filtered = self._filter_by_viewport_and_deduplicate_fast(conflict_resolved)
		self.metrics.filtering_time = time.time() - step_start + conflict_time
		self.metrics.after_viewport_filter = len(viewport_filtered)
		print(f'  🎯 Filtered to {len(viewport_filtered)} viewport-visible elements in {self.metrics.filtering_time:.3f}s')

		# Step 4: Build minimal simplified tree only for filtered elements
		step_start = time.time()
		simplified_elements = self._build_minimal_simplified_tree_fast(viewport_filtered)
		self.metrics.tree_building_time = time.time() - step_start
		print(f'  🔧 Built minimal tree with {len(simplified_elements)} elements in {self.metrics.tree_building_time:.3f}s')

		# Step 5: Assign interactive indices (no heavy consolidation needed)
		step_start = time.time()
		self._assign_indices_to_filtered_elements(simplified_elements)
		self.metrics.indexing_time = time.time() - step_start
		self.metrics.final_interactive_count = len(self._selector_map)
		print(f'  🏷️  Assigned {len(self._selector_map)} interactive indices in {self.metrics.indexing_time:.3f}s')

		# Step 6: Serialize minimal tree
		step_start = time.time()
		serialized = self._serialize_minimal_tree_fast(simplified_elements, include_attributes)
		self.metrics.serialization_time = time.time() - step_start
		print(f'  📝 Serialized {len(serialized)} characters in {self.metrics.serialization_time:.3f}s')

		return serialized, self._selector_map

	def _collect_ax_interactive_candidates_fast(self, node: EnhancedDOMTreeNode) -> List:
		"""Collect interactive candidates using optimized traversal with ENHANCED analysis and caching."""
		candidates = []
		node_count = 0

		def collect_recursive_fast(current_node: EnhancedDOMTreeNode, depth: int = 0):
			nonlocal node_count
			node_count += 1

			if depth > 50:  # Prevent infinite recursion
				return

			# Cache key for this node
			node_key = f'{current_node.node_name}_{id(current_node)}'

			# Skip obvious non-interactive structural elements immediately (cached)
			if node_key not in self._structural_cache:
				self._structural_cache[node_key] = self._is_structural_element_fast(current_node)

			if self._structural_cache[node_key]:
				self.metrics.skipped_structural += 1
				# Still process children, but don't consider this element
				if current_node.children_nodes:
					for child in current_node.children_nodes:
						collect_recursive_fast(child, depth + 1)
				return

			# Use ENHANCED element analysis with comprehensive scoring
			analysis_key = f'enhanced_analysis_{node_key}'

			if analysis_key not in self._analysis_cache:
				# Run the enhanced analysis
				analysis = ElementAnalysis.analyze_element_interactivity(current_node)
				self._analysis_cache[analysis_key] = analysis

				# Consider element interactive if score meets enhanced threshold
				is_interactive = analysis.score >= 20  # Slightly higher threshold for enhanced system
				self._interactivity_cache[f'interactive_{node_key}'] = is_interactive
			else:
				analysis = self._analysis_cache[analysis_key]
				is_interactive = self._interactivity_cache[f'interactive_{node_key}']

			if is_interactive:
				# Store enhanced analysis with the candidate
				candidates.append((current_node, 'enhanced', analysis))
				if depth <= 10:  # Only show debug for shallow elements to reduce noise
					confidence_emoji = {
						'DEFINITE': '🟢',
						'LIKELY': '🟡',
						'POSSIBLE': '🟠',
						'QUESTIONABLE': '🔴',
						'MINIMAL': '🟣',
					}.get(analysis.confidence, '❓')

					print(
						f'    ✅ Interactive: {current_node.node_name} {confidence_emoji} {analysis.confidence} ({analysis.score}pts) - {analysis.primary_reason}'
					)

			# Process children
			if current_node.children_nodes:
				for child in current_node.children_nodes:
					collect_recursive_fast(child, depth + 1)

			# Process iframe content
			if current_node.content_document and current_node.node_name.upper() == 'IFRAME':
				iframe_context_id = self._register_iframe_context(current_node)
				print(f'    🖼️  Processing iframe: {iframe_context_id}')
				collect_recursive_fast(current_node.content_document, depth + 1)

			# Process shadow DOM
			if current_node.shadow_roots:
				for i, shadow_root in enumerate(current_node.shadow_roots):
					shadow_context_id = self._register_shadow_context(current_node, i)
					print(f'    🌒 Processing shadow DOM: {shadow_context_id}')
					collect_recursive_fast(shadow_root, depth + 1)

		collect_recursive_fast(node)
		self.metrics.total_dom_nodes = node_count
		return candidates

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
		"""Detect and resolve nested conflicts where elements would trigger the same action."""
		# Build a map of analyses and nodes
		analyses_map = {}
		nodes_map = {}

		for candidate_tuple in candidates:
			if len(candidate_tuple) >= 3 and candidate_tuple[1] == 'enhanced':
				node, _, analysis = candidate_tuple
				node_id = id(node)
				analyses_map[node_id] = analysis
				nodes_map[node_id] = node

		# Detect conflicts
		conflict_groups = {}

		for node_id, analysis in analyses_map.items():
			node = nodes_map[node_id]
			current_action = ElementAnalysis._get_element_action(node)

			if current_action:
				if current_action not in conflict_groups:
					conflict_groups[current_action] = []
				conflict_groups[current_action].append((node_id, node, analysis))

		# Resolve conflicts - prefer parent elements or highest scoring
		resolved_candidates = []
		processed_nodes = set()

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

		# Add non-conflicting elements
		for candidate_tuple in candidates:
			if len(candidate_tuple) >= 3 and candidate_tuple[1] == 'enhanced':
				node, _, analysis = candidate_tuple
				node_id = id(node)
				if node_id not in processed_nodes:
					resolved_candidates.append(candidate_tuple)

		return resolved_candidates

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
		"""Fast check if element is a structural element that should be skipped."""
		if node.node_type != NodeType.ELEMENT_NODE:
			return False

		node_name = node.node_name.upper()

		# Skip obvious structural elements
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
		}

		if node_name in structural_elements:
			return True

		# Fast check for large empty containers
		if node_name in {'DIV', 'SECTION', 'ARTICLE', 'MAIN', 'HEADER', 'FOOTER', 'NAV', 'ASIDE'}:
			# Quick attribute check
			if not node.attributes:
				return True

			# Fast check for meaningful attributes
			meaningful_attrs = {'onclick', 'data-action', 'role', 'tabindex', 'href'}
			if not any(attr in node.attributes for attr in meaningful_attrs):
				return True

		return False

	def _is_ax_interactive_fast(self, node: EnhancedDOMTreeNode) -> bool:
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
					# This is likely a calendar date cell - check if it's part of a large grid
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

	def _is_likely_calendar_cell_fast(self, node: EnhancedDOMTreeNode) -> bool:
		"""Fast check if this is likely a calendar cell in a large date picker."""
		# If it's a DIV with gridcell role, check if it's part of a large calendar
		if not node.attributes:
			return True  # No attributes, likely just a date cell

		# Fast check for common calendar patterns
		if node.attributes:
			classes = node.attributes.get('class', '').lower()
			calendar_indicators = ['date', 'day', 'cell', 'calendar', 'picker', 'grid']

			# If it has calendar-related classes, it's likely a calendar cell
			if any(indicator in classes for indicator in calendar_indicators):
				return True

		# Fast structural check
		if (
			node.node_name.upper() == 'DIV'
			and len(node.attributes) <= 2  # Only a few attributes
			and not any(attr in node.attributes for attr in ['onclick', 'data-action', 'href', 'role'])
		):
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

		for candidate_tuple in candidates:
			candidate_node = candidate_tuple[0]  # First element is always the node
			# candidate_tuple could be (node, 'analyzed', analysis) or (node, 'type')

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
		"""Fast check if element is in viewport or is special context (iframe/shadow)."""
		# If no viewport info, assume visible
		if not self.viewport_info:
			return True

		# Fast check for iframe or shadow content (always include)
		if self._iframe_contexts or self._shadow_contexts:
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
		"""Fast build minimal simplified tree for filtered nodes only."""
		simplified_elements = []

		for node in filtered_nodes:
			simplified = SimplifiedNode(original_node=node)

			# Fast context info setting
			if self._iframe_contexts:
				simplified.iframe_context = None
			if self._shadow_contexts:
				simplified.shadow_context = None

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
		if simplified.iframe_context:
			return f'iframe:{simplified.iframe_context}'
		if simplified.shadow_context:
			return f'shadow:{simplified.shadow_context}'
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
		"""Generate LLM-friendly text representation focused on visible content and user interactions."""
		lines = []

		# Add page overview
		total_elements = len(self._compressed_elements)
		if total_elements > 0:
			lines.append('=== INTERACTIVE ELEMENTS FOUND ===')
			lines.append(f'Found {total_elements} interactive elements on this page:')
			lines.append('')

		# Add context summary if present (for iframe/shadow content)
		if self._iframe_contexts or self._shadow_contexts:
			lines.append('=== ADDITIONAL CONTENT CONTEXTS ===')
			for iframe_id, info in self._iframe_contexts.items():
				cross_origin = ' (cross-origin - limited access)' if info.is_cross_origin else ''
				src_info = f' from {info.iframe_src}' if info.iframe_src else ''
				lines.append(f'• Iframe content{src_info}{cross_origin}')
			for shadow_id, parent in self._shadow_contexts.items():
				lines.append(f'• Shadow DOM content in {parent.split("/")[-1] if "/" in parent else parent}')
			lines.append('')

		# Generate semantic groups with improved descriptions
		group_count = 0
		for group in self._semantic_groups:
			group_count += 1

			# Create user-friendly group titles
			group_title = self._create_friendly_group_title(group)
			lines.append(f'=== {group_title} ===')

			# Add group description if helpful
			group_desc = self._create_group_description(group)
			if group_desc:
				lines.append(group_desc)
				lines.append('')

			# Format elements with better context
			for i, elem in enumerate(group.elements, 1):
				line = self._format_compressed_element(elem)
				lines.append(f'  {line}')

			lines.append('')  # Empty line between groups

		# Add summary if multiple groups
		if group_count > 1:
			lines.append('=== SUMMARY ===')
			summary_info = []
			for group in self._semantic_groups:
				if group.elements:
					group_name = group.group_type.value.lower().replace('_', ' ')
					count = len(group.elements)
					summary_info.append(f'{count} {group_name} element{"s" if count != 1 else ""}')

			if summary_info:
				lines.append(f'This page contains: {", ".join(summary_info)}')

		return '\n'.join(lines)

	def _create_friendly_group_title(self, group: SemanticGroup) -> str:
		"""Create user-friendly group titles."""
		group_type = group.group_type.value
		element_count = len(group.elements)

		friendly_titles = {
			'FORM': f'FORM ELEMENTS ({element_count})',
			'NAVIGATION': f'NAVIGATION LINKS ({element_count})',
			'DROPDOWN': f'DROPDOWN/MENU OPTIONS ({element_count})',
			'MENU': f'MENU ITEMS ({element_count})',
			'TABLE': f'TABLE ELEMENTS ({element_count})',
			'LIST': f'LIST ITEMS ({element_count})',
			'TOOLBAR': f'TOOLBAR BUTTONS ({element_count})',
			'TABS': f'TAB CONTROLS ({element_count})',
			'ACCORDION': f'ACCORDION SECTIONS ({element_count})',
			'MODAL': f'MODAL/DIALOG ELEMENTS ({element_count})',
			'CAROUSEL': f'CAROUSEL CONTROLS ({element_count})',
			'CONTENT': f'OTHER INTERACTIVE CONTENT ({element_count})',
			'FOOTER': f'FOOTER ELEMENTS ({element_count})',
			'HEADER': f'HEADER ELEMENTS ({element_count})',
			'SIDEBAR': f'SIDEBAR ELEMENTS ({element_count})',
		}

		return friendly_titles.get(group_type, f'{group_type} ({element_count})')

	def _create_group_description(self, group: SemanticGroup) -> str:
		"""Create helpful descriptions for element groups."""
		group_type = group.group_type.value
		element_count = len(group.elements)

		descriptions = {
			'FORM': 'Form fields and controls for user input:',
			'NAVIGATION': 'Links for navigating to different pages:',
			'DROPDOWN': 'Dropdown menus and selectable options:',
			'MENU': 'Menu items and navigation options:',
			'TABLE': 'Interactive table elements:',
			'LIST': 'List items that can be selected or clicked:',
			'TOOLBAR': 'Action buttons and controls:',
			'TABS': 'Tab controls for switching content:',
			'CONTENT': 'Other clickable content on the page:',
		}

		return descriptions.get(group_type, '')

	def _include_element_text_content(self) -> None:
		"""Extract and include text content from elements for better LLM understanding."""
		# This method can be called to enhance element labels with nearby text content
		for elem in self._compressed_elements:
			# If label is generic, try to find better text content
			if elem.label.startswith('<') or len(elem.label) < 3:
				# Could enhance by looking at nearby text nodes or aria-describedby
				pass

	def _format_compressed_element(self, elem: CompressedElement) -> str:
		"""Format a compressed element for natural language LLM consumption."""
		# Start with the element index and a natural description
		parts = []

		# Add index in brackets
		parts.append(f'[{elem.index}]')

		# Create natural language description based on element type and action
		description = self._create_natural_description(elem)
		parts.append(description)

		# Add the text content/label in quotes - this is what the LLM will see
		if elem.label and not elem.label.startswith('<'):
			parts.append(f'"{elem.label}"')

		# Add target information in natural language
		if elem.target:
			target_desc = self._format_target_naturally(elem.target, elem.element_type)
			if target_desc:
				parts.append(target_desc)

		# Add state information naturally
		state_info = self._format_state_naturally(elem.attributes)
		if state_info:
			parts.append(state_info)

		# Add context if present (for iframe/shadow content)
		if elem.context:
			if 'iframe' in elem.context:
				parts.append('(in iframe)')
			elif 'shadow' in elem.context:
				parts.append('(in shadow DOM)')

		return ' '.join(parts)

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

	def _serialize_full_tree_legacy(self, include_attributes: list[str]) -> tuple[str, dict[int, EnhancedDOMTreeNode]]:
		"""Legacy full tree serialization approach (fallback)."""
		# Reset state
		self._interactive_counter = 1
		self._selector_map = {}
		self._iframe_contexts = {}
		self._shadow_contexts = {}
		self._element_groups = {}
		self._cross_origin_iframes = []

		# Step 1: Create simplified tree with enhanced detection (includes iframe and shadow traversal)
		simplified_tree = self._create_simplified_tree(self.root_node)

		# Step 2: Optimize tree (remove unnecessary parents)
		optimized_tree = self._optimize_tree(simplified_tree)

		# Step 3: Group related elements (radio buttons, select options, etc.)
		self._group_related_elements(optimized_tree)

		# Step 4: AGGRESSIVE parent-child consolidation to reduce redundancy
		self._aggressive_consolidate_parent_child(optimized_tree)

		# Step 5: Assign interactive indices to remaining clickable elements
		self._assign_interactive_indices(optimized_tree)

		# Step 6: Serialize optimized tree with grouping and iframe/shadow content
		serialized = self._serialize_tree(optimized_tree, include_attributes)

		# Step 7: Add iframe and shadow context summary
		context_summary = self._build_context_summary()
		if context_summary:
			serialized = context_summary + '\n\n' + serialized

		return serialized, self._selector_map

	def _build_context_summary(self) -> str:
		"""Build a summary of iframe and shadow contexts."""
		summary_lines = []

		if self._iframe_contexts:
			summary_lines.append('=== IFRAME CONTEXTS ===')
			for context_id, info in self._iframe_contexts.items():
				cross_origin_note = ' [CROSS-ORIGIN]' if info.is_cross_origin else ''
				src_info = f" src='{info.iframe_src}'" if info.iframe_src else ''
				summary_lines.append(f'IFRAME_{context_id}: {info.iframe_xpath}{src_info}{cross_origin_note}')

		if self._shadow_contexts:
			summary_lines.append('=== SHADOW DOM CONTEXTS ===')
			for shadow_id, parent_xpath in self._shadow_contexts.items():
				summary_lines.append(f'SHADOW_{shadow_id}: {parent_xpath}')

		if self._cross_origin_iframes:
			summary_lines.append('=== CROSS-ORIGIN IFRAMES (READ-ONLY) ===')
			for iframe_url in self._cross_origin_iframes:
				summary_lines.append(f'⚠️  {iframe_url}')

		return '\n'.join(summary_lines) if summary_lines else ''

	def _aggressive_consolidate_parent_child(self, node: SimplifiedNode | None) -> None:
		"""Aggressively consolidate parent-child relationships to reduce redundancy."""
		if not node:
			return

		# Process children first (bottom-up)
		for child in node.children:
			self._aggressive_consolidate_parent_child(child)

		# **WRAPPER DETECTION**: Check if this node is just a wrapper around interactive children
		if self._is_wrapper_container(node):
			self._consolidate_wrapper_container(node)
			return

		# **TRADITIONAL CONSOLIDATION**: If this node is interactive, check for redundant children
		if node.is_clickable():
			self._consolidate_redundant_children(node)

	def _is_wrapper_container(self, node: SimplifiedNode) -> bool:
		"""Check if this node is a wrapper container that should be consolidated."""
		node_name = node.original_node.node_name.upper()

		# Only consider common container elements as potential wrappers
		if node_name not in {'DIV', 'SPAN', 'SECTION', 'ARTICLE', 'HEADER', 'FOOTER', 'MAIN', 'NAV', 'ASIDE'}:
			return False

		# If the node itself is interactive, don't treat as wrapper
		if node.is_clickable():
			return False

		# Count interactive and non-interactive children
		interactive_children = [child for child in node.children if child.is_clickable()]
		total_children = len(node.children)

		# **AGGRESSIVE WRAPPER DETECTION**: If ALL children are interactive, this is likely a wrapper
		if len(interactive_children) > 0 and len(interactive_children) == total_children:
			print(f'  🗑️  Removing wrapper container {node_name} with {len(interactive_children)} interactive children')
			return True

		# **LARGE CONTAINER DETECTION**: If container has many interactive children, it's likely a calendar/menu container
		if len(interactive_children) >= 10:  # Calendar with many date buttons
			# This is likely a calendar, dropdown menu, or similar container
			# The container itself shouldn't be interactive, only the individual buttons
			print(f'  🗑️  Removing large container {node_name} with {len(interactive_children)} interactive children')
			return True

		# **MEDIUM CONTAINER DETECTION**: Container with moderate number of interactive children
		if len(interactive_children) >= 5 and total_children >= 8:
			# Check if it looks like a menu or calendar by class names
			if node.original_node.attributes and 'class' in node.original_node.attributes:
				classes = node.original_node.attributes['class'].lower()
				calendar_menu_indicators = [
					'calendar',
					'menu',
					'dropdown',
					'picker',
					'grid',
					'table',
					'list',
					'items',
					'options',
					'choices',
					'popup',
				]
				if any(indicator in classes for indicator in calendar_menu_indicators):
					print(f'  🗑️  Removing {node_name} container with class indicators: {classes[:50]}...')
					return True
			print(f'  🗑️  Removing medium container {node_name} with {len(interactive_children)} interactive children')
			return True

		# **TRADITIONAL WRAPPER DETECTION**: Single or few children
		# Case 1: Exactly one interactive child - likely a wrapper
		if len(interactive_children) == 1 and total_children <= 3:
			print(f'  🗑️  Removing wrapper {node_name} around single interactive child')
			return True

		# Case 2: Multiple children but mostly non-interactive text/styling
		if len(interactive_children) >= 1 and total_children <= 5:
			# Check if non-interactive children are just text/styling
			non_interactive_children = [child for child in node.children if not child.is_clickable()]
			mostly_styling = all(
				child.original_node.node_type == NodeType.TEXT_NODE
				or child.original_node.node_name.upper() in {'SPAN', 'I', 'B', 'STRONG', 'EM', 'IMG', 'SVG', 'PATH'}
				for child in non_interactive_children
			)
			if mostly_styling:
				print(f'  🗑️  Removing wrapper {node_name} with mostly styling children')
				return True

		# **HIGH RATIO WRAPPER DETECTION**: If >70% of children are interactive, likely a wrapper
		if total_children > 1 and (len(interactive_children) / total_children) > 0.7:
			print(f'  🗑️  Removing wrapper {node_name} with high interactive ratio ({len(interactive_children)}/{total_children})')
			return True

		return False

	def _consolidate_wrapper_container(self, wrapper_node: SimplifiedNode) -> None:
		"""Consolidate a wrapper container by removing its interactivity and keeping children."""
		# The wrapper itself should not be interactive
		wrapper_node.is_consolidated = True

		# But we don't consolidate the children - they keep their interactivity
		# This effectively "removes" the wrapper from being detected as interactive
		# while preserving the children's interactive status

	def _consolidate_redundant_children(self, parent_node: SimplifiedNode) -> None:
		"""Aggressively consolidate children when parent is more meaningful."""
		parent_name = parent_node.original_node.node_name.upper()

		# PRIMARY CONSOLIDATION: Elements that should always consolidate their children
		primary_consolidating_elements = {
			'A',  # Links - children are just styling/content
			'BUTTON',  # Buttons - children are just styling/content
			'INPUT',  # Input elements
			'SELECT',  # Select dropdowns
			'TEXTAREA',  # Text areas
		}

		if parent_name in primary_consolidating_elements:
			# Remove interactive status from ALL descendants
			self._remove_interactive_status_recursive(parent_node)
			return

		# SECONDARY CONSOLIDATION: DIV/SPAN with interactive attributes
		if parent_name in {'DIV', 'SPAN'} and parent_node.original_node.attributes:
			attrs = parent_node.original_node.attributes
			has_click_handler = any(attr in attrs for attr in ['onclick', 'data-action', 'data-toggle', 'data-href'])
			has_role = attrs.get('role', '').lower() in {'button', 'link', 'menuitem', 'tab', 'option'}

			# Check for any interactive cursor
			computed_styles_info = {}
			if parent_node.original_node.snapshot_node and hasattr(parent_node.original_node.snapshot_node, 'computed_styles'):
				computed_styles_info = parent_node.original_node.snapshot_node.computed_styles or {}
			has_interactive_cursor, _, _ = ElementAnalysis._has_any_interactive_cursor(
				parent_node.original_node, computed_styles_info
			)

			if has_click_handler or has_role or has_interactive_cursor:
				self._remove_interactive_status_recursive(parent_node)
				return

		# TERTIARY CONSOLIDATION: Parent-child with same action (href, onclick, etc.)
		clickable_children = [child for child in parent_node.children if child.is_clickable()]

		# If parent and single child would do the same action, consolidate
		if len(clickable_children) == 1:
			child = clickable_children[0]
			if self._elements_would_do_same_action(parent_node, child):
				# Keep parent, consolidate child
				child.is_consolidated = True
				self._remove_interactive_status_recursive(child)

	def _elements_would_do_same_action(self, parent: SimplifiedNode, child: SimplifiedNode) -> bool:
		"""Check if parent and child elements would perform the same action."""
		parent_node = parent.original_node
		child_node = child.original_node

		# Check if both have the same href
		parent_href = parent_node.attributes.get('href') if parent_node.attributes else None
		child_href = child_node.attributes.get('href') if child_node.attributes else None
		if parent_href and child_href and parent_href == child_href:
			return True

		# Check if both have the same onclick handler
		parent_onclick = parent_node.attributes.get('onclick') if parent_node.attributes else None
		child_onclick = child_node.attributes.get('onclick') if child_node.attributes else None
		if parent_onclick and child_onclick and parent_onclick == child_onclick:
			return True

		# Check if both have the same data-action
		parent_action = parent_node.attributes.get('data-action') if parent_node.attributes else None
		child_action = child_node.attributes.get('data-action') if child_node.attributes else None
		if parent_action and child_action and parent_action == child_action:
			return True

		# If parent is wrapper around single interactive child of meaningful type
		if (
			parent_node.node_name.upper() == 'DIV'
			and child_node.node_name.upper() in {'BUTTON', 'A', 'INPUT'}
			and len(parent.children) == 1
		):
			return True

		return False

	def _remove_interactive_status_recursive(self, node: SimplifiedNode) -> None:
		"""Recursively remove interactive status from all children but keep the parent."""
		for child in node.children:
			# Remove interactive status from child elements
			child_name = child.original_node.node_name.upper()

			# Remove interactivity from most elements except truly independent ones
			elements_to_consolidate = {
				'#TEXT',
				'SPAN',
				'DIV',
				'IMG',
				'SVG',
				'PATH',
				'CIRCLE',
				'RECT',
				'LINE',
				'POLYGON',
				'POLYLINE',
				'ELLIPSE',
				'G',
				'USE',
				'DEFS',
				'CLIPPATH',
				'MASK',
				'PATTERN',
				'MARKER',
				'SYMBOL',
				'TEXT',
				'TSPAN',
				'I',
				'B',
				'STRONG',
				'EM',
				'SMALL',
				'MARK',
				'DEL',
				'INS',
				'SUB',
				'SUP',
			}

			if child_name in elements_to_consolidate or child.original_node.node_type == NodeType.TEXT_NODE:
				# Mark as consolidated
				child.is_consolidated = True
				# Recursively process grandchildren
				self._remove_interactive_status_recursive(child)
			else:
				# For form elements and other meaningful elements, only consolidate if they don't have independent interactivity
				if not self._has_independent_interactivity(child):
					child.is_consolidated = True
					self._remove_interactive_status_recursive(child)

	def _has_independent_interactivity(self, node: SimplifiedNode) -> bool:
		"""Check if a node has meaningful independent interactivity that shouldn't be consolidated."""
		node_name = node.original_node.node_name.upper()

		# Form elements should generally keep their independence if they have meaningful attributes
		independent_elements = {'INPUT', 'BUTTON', 'SELECT', 'TEXTAREA', 'A'}
		if node_name in independent_elements:
			if node.original_node.attributes:
				# If it has meaningful attributes, it's probably independent
				meaningful_attrs = {'href', 'type', 'name', 'value', 'action', 'method'}
				if any(attr in node.original_node.attributes for attr in meaningful_attrs):
					return True

		return False

	def _create_simplified_tree(
		self, node: EnhancedDOMTreeNode, iframe_context: str | None = None, shadow_context: str | None = None
	) -> SimplifiedNode | None:
		"""Step 1: Create a simplified tree with ENHANCED iframe/shadow traversal and recursive DOM extraction."""

		if node.node_type == NodeType.DOCUMENT_NODE:
			# Document nodes - process children directly and return the first meaningful child
			if node.children_nodes:
				for child in node.children_nodes:
					simplified_child = self._create_simplified_tree(child, iframe_context, shadow_context)
					if simplified_child:
						return simplified_child
			return None

		elif node.node_type == NodeType.ELEMENT_NODE:
			# Skip #document nodes entirely - process children directly
			if node.node_name == '#document':
				if node.children_nodes:
					for child in node.children_nodes:
						simplified_child = self._create_simplified_tree(child, iframe_context, shadow_context)
						if simplified_child:
							return simplified_child
				return None

			# Skip elements that contain non-content
			if node.node_name.lower() in ['style', 'script', 'head', 'meta', 'link', 'title']:
				return None

			# Create simplified node to test interactivity
			simplified = SimplifiedNode(original_node=node, iframe_context=iframe_context, shadow_context=shadow_context)

			# Enhanced interactivity detection
			is_interactive = simplified.is_clickable()
			is_effectively_visible = simplified.is_effectively_visible()
			is_scrollable = getattr(node, 'is_scrollable', False)
			is_iframe = node.node_name.upper() == 'IFRAME'

			# More inclusive criteria - include if interactive and visible, or scrollable, or structural
			should_include = (is_interactive and is_effectively_visible) or is_scrollable or is_iframe or node.children_nodes

			if should_include:
				# Process regular children first
				if node.children_nodes:
					for child in node.children_nodes:
						simplified_child = self._create_simplified_tree(child, iframe_context, shadow_context)
						if simplified_child:
							simplified.children.append(simplified_child)

				# **ENHANCED IFRAME PROCESSING**: Run full algorithm inside iframe content
				if node.content_document and is_iframe:
					iframe_context_id = self._register_iframe_context(node)
					print(f'🔍 Processing iframe content: {iframe_context_id}')

					# Run the FULL DOM extraction algorithm recursively inside the iframe
					iframe_content = self._extract_iframe_content_recursively(
						node.content_document, iframe_context_id, shadow_context
					)

					if iframe_content:
						simplified.children.extend(iframe_content)

				# **ENHANCED SHADOW DOM PROCESSING**: Process shadow roots
				if node.shadow_roots:
					for i, shadow_root in enumerate(node.shadow_roots):
						shadow_context_id = self._register_shadow_context(node, i)
						print(f'🔍 Processing shadow DOM: {shadow_context_id}')

						shadow_content = self._extract_shadow_content_recursively(shadow_root, iframe_context, shadow_context_id)

						if shadow_content:
							simplified.children.extend(shadow_content)

				# Only return this node if it's meaningful OR has meaningful children
				if (is_interactive and is_effectively_visible) or is_scrollable or is_iframe or simplified.children:
					return simplified

		elif node.node_type == NodeType.TEXT_NODE:
			# Include text nodes only if visible and meaningful
			is_visible = getattr(node.snapshot_node, 'is_visible', False) if node.snapshot_node else False
			if is_visible and node.node_value and node.node_value.strip() and len(node.node_value.strip()) > 1:
				simplified = SimplifiedNode(original_node=node, iframe_context=iframe_context, shadow_context=shadow_context)
				return simplified

		return None

	def _count_interactive_elements(self, node: SimplifiedNode | None) -> int:
		"""Recursively count interactive elements in a tree."""
		if not node:
			return 0

		count = 1 if node.is_clickable() else 0

		for child in node.children:
			count += self._count_interactive_elements(child)

		return count

	def _extract_iframe_content_recursively(
		self, content_document: EnhancedDOMTreeNode, iframe_context_id: str, parent_shadow_context: str | None
	) -> list[SimplifiedNode]:
		"""Extract iframe content by running the full DOM extraction algorithm recursively."""
		try:
			print(f'  🔄 Running full DOM extraction inside iframe: {iframe_context_id}')

			# Recursively process the entire iframe content document
			iframe_tree = self._create_simplified_tree(content_document, iframe_context_id, parent_shadow_context)

			if iframe_tree:
				print(f'    📊 Initial iframe tree created for {iframe_context_id}')

				# Run optimization and consolidation on iframe content
				optimized_iframe_tree = self._optimize_tree(iframe_tree)

				if optimized_iframe_tree:
					print(f'    🔧 Iframe tree optimized for {iframe_context_id}')

					# Group elements within the iframe
					self._group_related_elements(optimized_iframe_tree)
					print(f'    🔗 Elements grouped in {iframe_context_id}')

					# Apply consolidation within the iframe
					self._aggressive_consolidate_parent_child(optimized_iframe_tree)
					print(f'    🗜️  Consolidation applied in {iframe_context_id}')

					# Count interactive elements before returning
					interactive_count = self._count_interactive_elements(optimized_iframe_tree)
					print(f'    🎯 Found {interactive_count} interactive elements in {iframe_context_id}')

					# Return as a list of children for integration
					return [optimized_iframe_tree]
				else:
					print(f'    ⚠️ No optimized tree for {iframe_context_id}')
			else:
				print(f'    ⚠️ No initial tree created for {iframe_context_id}')

			return []

		except Exception as e:
			print(f'  ⚠️ Error processing iframe content {iframe_context_id}: {e}')
			return []

	def _extract_shadow_content_recursively(
		self, shadow_root: EnhancedDOMTreeNode, parent_iframe_context: str | None, shadow_context_id: str
	) -> list[SimplifiedNode]:
		"""Extract shadow DOM content by running the full DOM extraction algorithm recursively."""
		try:
			print(f'  🔄 Running full DOM extraction inside shadow DOM: {shadow_context_id}')

			# Recursively process the entire shadow root
			shadow_tree = self._create_simplified_tree(shadow_root, parent_iframe_context, shadow_context_id)

			if shadow_tree:
				# Run optimization and consolidation on shadow content
				optimized_shadow_tree = self._optimize_tree(shadow_tree)

				if optimized_shadow_tree:
					# Group elements within the shadow DOM
					self._group_related_elements(optimized_shadow_tree)

					# Apply consolidation within the shadow DOM
					self._aggressive_consolidate_parent_child(optimized_shadow_tree)

					# Return as a list of children for integration
					return [optimized_shadow_tree]

			return []

		except Exception as e:
			print(f'  ⚠️ Error processing shadow DOM content {shadow_context_id}: {e}')
			return []

	def _register_iframe_context(self, iframe_node: EnhancedDOMTreeNode) -> str:
		"""Register an iframe context and return its ID with enhanced cross-origin detection."""
		iframe_src = iframe_node.attributes.get('src') if iframe_node.attributes else None
		iframe_xpath = iframe_node.x_path

		# Enhanced cross-origin detection
		is_cross_origin = self._is_cross_origin_iframe_enhanced(iframe_node)
		if is_cross_origin and iframe_src:
			self._cross_origin_iframes.append(iframe_src)
			print(f'  🌐 Detected cross-origin iframe: {iframe_src}')

		context_id = f'iframe_{len(self._iframe_contexts)}'
		self._iframe_contexts[context_id] = IFrameContextInfo(
			iframe_xpath=iframe_xpath, iframe_src=iframe_src, is_cross_origin=is_cross_origin, context_id=context_id
		)
		return context_id

	def _is_cross_origin_iframe_enhanced(self, iframe_node: EnhancedDOMTreeNode) -> bool:
		"""Enhanced check if an iframe is cross-origin by examining content and src."""
		# Primary check: If we don't have content_document, it's likely cross-origin
		if not iframe_node.content_document:
			return True

		# Secondary check: Analyze the src URL for cross-origin indicators
		if iframe_node.attributes and 'src' in iframe_node.attributes:
			src = iframe_node.attributes['src']

			# Check for obvious cross-origin patterns
			cross_origin_patterns = [
				'https://',  # Different protocol
				'http://',  # Different protocol
				'www.',  # Different subdomain
				'.com/',
				'.org/',
				'.net/',
				'.io/',  # Different domains
				'google.com',
				'facebook.com',
				'twitter.com',
				'youtube.com',
				'mailerlite.com',
				'typeform.com',
				'hubspot.com',
				'stripe.com',
				'paypal.com',
				'gravatar.com',
			]

			src_lower = src.lower()
			if any(pattern in src_lower for pattern in cross_origin_patterns):
				# Additional check: if it's a relative URL, it's same-origin
				if not src.startswith(('http://', 'https://', '//')):
					return False  # Relative URL = same origin
				return True

		# If we have content_document and no suspicious src, assume same-origin
		return False

	def _register_shadow_context(self, parent_node: EnhancedDOMTreeNode, shadow_index: int) -> str:
		"""Register a shadow DOM context and return its ID."""
		shadow_id = f'shadow_{len(self._shadow_contexts)}_{shadow_index}'
		self._shadow_contexts[shadow_id] = parent_node.x_path
		return shadow_id

	def _optimize_tree(self, node: SimplifiedNode | None) -> SimplifiedNode | None:
		"""Step 2: Optimize tree structure while preserving interactive elements."""
		if not node:
			return None

		# Process all children first
		optimized_children = []
		for child in node.children:
			optimized_child = self._optimize_tree(child)
			if optimized_child:
				optimized_children.append(optimized_child)

		# Update children with optimized versions
		node.children = optimized_children

		# Determine if this node should be kept
		is_interactive = node.is_clickable()
		is_scrollable = getattr(node.original_node, 'is_scrollable', False)
		is_text = node.original_node.node_type == NodeType.TEXT_NODE
		has_children = len(node.children) > 0
		is_iframe = node.original_node.node_name.upper() == 'IFRAME'

		# Keep nodes that are:
		# 1. Interactive elements
		# 2. Scrollable elements
		# 3. Text nodes
		# 4. Containers with interactive children
		# 5. Form elements (even if not directly interactive)
		# 6. Structural elements that group interactive elements
		# 7. Iframe elements (always keep)

		form_elements = {'FORM', 'FIELDSET', 'LEGEND', 'LABEL'}
		is_form_element = node.original_node.node_name.upper() in form_elements

		# Check if this is a container for grouped elements (like a select or radio group)
		is_grouping_container = self._is_grouping_container(node)

		if is_interactive or is_scrollable or is_text or has_children or is_form_element or is_grouping_container or is_iframe:
			return node

		return None

	def _is_grouping_container(self, node: SimplifiedNode) -> bool:
		"""Check if this node is a container that groups related interactive elements."""
		node_name = node.original_node.node_name.upper()

		# Select elements contain options
		if node_name == 'SELECT':
			return True

		# Fieldsets often contain radio button groups
		if node_name == 'FIELDSET':
			return True

		# Check for common dropdown/menu containers by class
		if node.original_node.attributes and 'class' in node.original_node.attributes:
			classes = node.original_node.attributes['class'].lower()
			grouping_classes = {
				'dropdown',
				'menu',
				'nav',
				'tab',
				'accordion',
				'select',
				'radio-group',
				'checkbox-group',
				'button-group',
			}
			if any(cls in classes for cls in grouping_classes):
				return True

		return False

	def _group_related_elements(self, node: SimplifiedNode | None) -> None:
		"""Step 3: Identify and group related interactive elements."""
		if not node:
			return

		# Process children first to build up groups
		for child in node.children:
			self._group_related_elements(child)

		# Group radio buttons and checkboxes by name
		if node.is_radio_or_checkbox():
			group_name = node.get_group_name()
			if group_name:
				group_key = f'radio_checkbox_{group_name}'
				if group_key not in self._element_groups:
					self._element_groups[group_key] = []
				self._element_groups[group_key].append(node)
				node.group_type = 'radio_checkbox'

		# Group select options
		if node.is_option_element():
			# Find parent select or custom dropdown
			parent = self._find_select_parent(node)
			if parent:
				group_key = f'select_options_{id(parent)}'
				if group_key not in self._element_groups:
					self._element_groups[group_key] = []
				self._element_groups[group_key].append(node)
				node.group_type = 'select_option'

	def _find_select_parent(self, node: SimplifiedNode) -> SimplifiedNode | None:
		"""Find the parent SELECT element or custom dropdown container."""
		# This is a simplified approach - in a full implementation,
		# we'd traverse up the tree to find the parent
		# For now, we'll just group options that appear together
		return None

	def _assign_interactive_indices(self, node: SimplifiedNode | None) -> None:
		"""Step 5: Assign interactive indices to remaining clickable elements that are in the current viewport."""
		if not node:
			return

		# Handle grouped elements specially
		if node.group_type:
			if node.group_type == 'select_option':
				if node.is_clickable() and self._is_element_in_current_viewport(node):
					node.interactive_index = self._interactive_counter
					self._selector_map[self._interactive_counter] = self._create_contextual_node(node)
					self._interactive_counter += 1
			elif node.group_type == 'radio_checkbox':
				if node.is_clickable() and self._is_element_in_current_viewport(node):
					node.interactive_index = self._interactive_counter
					self._selector_map[self._interactive_counter] = self._create_contextual_node(node)
					self._interactive_counter += 1
		else:
			# Regular interactive elements - only assign if still clickable after consolidation AND in viewport
			if node.is_clickable():
				is_in_viewport = self._is_element_in_current_viewport(node)

				# Debug output for iframe/shadow elements
				context_info = ''
				if node.iframe_context:
					context_info = f' (iframe: {node.iframe_context})'
				elif node.shadow_context:
					context_info = f' (shadow: {node.shadow_context})'

				if is_in_viewport:
					if context_info:
						print(f'  🎯 Assigning index {self._interactive_counter} to {node.original_node.node_name}{context_info}')

					node.interactive_index = self._interactive_counter
					self._selector_map[self._interactive_counter] = self._create_contextual_node(node)
					self._interactive_counter += 1
				else:
					if context_info:
						print(f'  ❌ Skipping {node.original_node.node_name}{context_info} - outside viewport')
					elif node.original_node.node_name.upper() in {'BUTTON', 'A', 'INPUT'}:
						print(f'  ❌ Skipping {node.original_node.node_name} - outside viewport')
			else:
				# Debug for non-clickable elements in iframe/shadow
				if node.iframe_context or node.shadow_context:
					context_info = (
						f' (iframe: {node.iframe_context})' if node.iframe_context else f' (shadow: {node.shadow_context})'
					)
					if node.original_node.node_name.upper() in {'BUTTON', 'A', 'INPUT', 'DIV'}:
						print(f'  ⚪ Not clickable: {node.original_node.node_name}{context_info}')

		# Process children
		for child in node.children:
			self._assign_interactive_indices(child)

	def _create_contextual_node(self, simplified_node: SimplifiedNode) -> EnhancedDOMTreeNode:
		"""Create a contextual version of the DOM node with iframe/shadow context."""
		original_node = simplified_node.original_node

		# If we have iframe or shadow context, we need to store this information
		# For now, we'll use the original node but could extend this to store context
		# The context tracking will be handled via the serializer's context tracking

		# TODO: In the future, we could create a wrapper class that includes context
		# For now, we rely on the iframe_context and shadow_context being tracked separately

		return original_node

	def _serialize_tree(self, node: SimplifiedNode | None, include_attributes: list[str], depth: int = 0) -> str:
		"""Step 6: Serialize the optimized tree with ENHANCED iframe/shadow display."""
		if not node:
			return ''

		formatted_text = []
		depth_str = depth * '\t'
		next_depth = depth

		if node.original_node.node_type == NodeType.ELEMENT_NODE:
			# **ENHANCED IFRAME/SHADOW CONTEXT DISPLAY**
			context_prefix = ''
			context_suffix = ''

			if node.iframe_context:
				iframe_info = self._iframe_contexts.get(node.iframe_context)
				if iframe_info:
					iframe_src = iframe_info.iframe_src or 'unknown'
					is_cross_origin = iframe_info.is_cross_origin
					cross_origin_marker = ' [CROSS-ORIGIN]' if is_cross_origin else ''

					context_prefix = f'{depth_str}🖼️  === IFRAME CONTENT [{node.iframe_context}]{cross_origin_marker} ==='
					if iframe_src and iframe_src != 'unknown':
						context_prefix += f'\n{depth_str}📍 Source: {iframe_src}'
					context_suffix = f'{depth_str}🖼️  === END IFRAME [{node.iframe_context}] ==='
				else:
					# Fallback if iframe info not found
					context_prefix = f'{depth_str}🖼️  === IFRAME CONTENT [{node.iframe_context}] ==='
					context_suffix = f'{depth_str}🖼️  === END IFRAME [{node.iframe_context}] ==='
				next_depth += 1

			elif node.shadow_context:
				context_prefix = f'{depth_str}🌒 === SHADOW DOM [{node.shadow_context}] ==='
				context_suffix = f'{depth_str}🌒 === END SHADOW [{node.shadow_context}] ==='
				next_depth += 1

			# Add context markers if this is iframe/shadow content
			if context_prefix:
				formatted_text.append(context_prefix)

			# Enhanced element display with iframe/shadow context
			if (
				node.interactive_index is not None
				or getattr(node.original_node, 'is_scrollable', False)
				or self._should_show_element(node)
			):
				next_depth_for_element = next_depth if context_prefix else depth + 1

				# Build attributes string with enhanced information
				attributes_html_str = self._build_enhanced_attributes_string(node.original_node, include_attributes, node)

				# Build the line with enhanced prefixes
				line = self._build_element_line_with_context(
					node, depth_str if not context_prefix else depth_str + '\t', attributes_html_str
				)

				if line:
					formatted_text.append(line)

		elif node.original_node.node_type == NodeType.TEXT_NODE:
			# Include meaningful text content with context
			if self._should_include_text(node):
				clean_text = node.original_node.node_value.strip()
				# Limit text length for readability
				if len(clean_text) > 100:
					clean_text = clean_text[:97] + '...'

				# Enhanced context prefix for iframe/shadow text
				context_prefix = ''
				if node.iframe_context:
					context_prefix = f'[{node.iframe_context}] '
				elif node.shadow_context:
					context_prefix = f'[{node.shadow_context}] '

				text_depth = depth_str if not (node.iframe_context or node.shadow_context) else depth_str + '\t'
				formatted_text.append(f'{text_depth}{context_prefix}{clean_text}')

		# Process children with proper depth
		for child in node.children:
			child_text = self._serialize_tree(child, include_attributes, next_depth)
			if child_text:
				formatted_text.append(child_text)

		# Add context suffix if this was iframe/shadow content
		if node.original_node.node_type == NodeType.ELEMENT_NODE and context_suffix:
			formatted_text.append(context_suffix)

		return '\n'.join(formatted_text)

	def _should_show_element(self, node: SimplifiedNode) -> bool:
		"""Determine if an element should be shown even if not interactive."""
		# Show form elements and structural elements
		node_name = node.original_node.node_name.upper()
		structural_elements = {'FORM', 'FIELDSET', 'LEGEND', 'LABEL', 'SELECT', 'IFRAME'}

		if node_name in structural_elements:
			return True

		# Show elements with important roles
		if (
			node.original_node.ax_node
			and node.original_node.ax_node.role
			and node.original_node.ax_node.role.lower() in {'navigation', 'main', 'banner', 'complementary'}
		):
			return True

		# Show elements that contain grouped interactive elements
		if self._contains_grouped_elements(node):
			return True

		return False

	def _contains_grouped_elements(self, node: SimplifiedNode) -> bool:
		"""Check if this node contains grouped interactive elements."""
		for child in node.children:
			if child.group_type or child.interactive_index is not None:
				return True
			if self._contains_grouped_elements(child):
				return True
		return False

	def _build_element_line(self, node: SimplifiedNode, depth_str: str, attributes_html_str: str) -> str:
		"""Build the formatted line for an element - SIMPLIFIED to show only numbers."""
		prefixes = []

		# Scrollable prefix
		if getattr(node.original_node, 'is_scrollable', False):
			prefixes.append('SCROLL')

		# Interactive index - SIMPLIFIED to show only number
		if node.interactive_index is not None:
			prefixes.append(str(node.interactive_index))

		# Build prefix string - SIMPLIFIED
		if prefixes:
			if 'SCROLL' in prefixes and any(p.isdigit() for p in prefixes):
				prefix_str = '|SCROLL+' + '+'.join(p for p in prefixes if p != 'SCROLL') + ']'
			elif any(p.isdigit() for p in prefixes):
				prefix_str = '[' + '+'.join(prefixes) + ']'
			else:
				prefix_str = '|' + '+'.join(prefixes) + '|'
		else:
			return ''  # Don't show elements without any interactive features

		# Build the complete line - SIMPLIFIED
		line = f'{depth_str}{prefix_str}<{node.original_node.node_name}'

		if attributes_html_str:
			line += f' {attributes_html_str}'

		line += ' />'
		return line

	def _should_include_text(self, node: SimplifiedNode) -> bool:
		"""Determine if text content should be included."""
		if not node.original_node.snapshot_node:
			return False

		is_visible = getattr(node.original_node.snapshot_node, 'is_visible', False)
		if not is_visible:
			return False

		text = node.original_node.node_value
		if not text or not text.strip() or len(text.strip()) <= 1:
			return False

		# Skip very long text that's not useful
		if len(text.strip()) > 200:
			return False

		return True

	def _build_enhanced_attributes_string(
		self, node: EnhancedDOMTreeNode, include_attributes: list[str], simplified_node: SimplifiedNode | None
	) -> str:
		"""Build enhanced attributes string with interaction-relevant information."""
		if not node.attributes:
			return ''

		# Start with standard attributes
		attributes_to_include = {
			key: str(value).strip()
			for key, value in node.attributes.items()
			if key in include_attributes and str(value).strip() != ''
		}

		# Add interaction-specific attributes
		interaction_attributes = {'type', 'onclick', 'role', 'tabindex', 'data-action', 'data-toggle', 'src'}

		for attr in interaction_attributes:
			if attr in node.attributes and attr not in attributes_to_include:
				attributes_to_include[attr] = str(node.attributes[attr]).strip()

		# Add cursor style if interactive
		computed_styles_info = {}
		if node.snapshot_node and hasattr(node.snapshot_node, 'computed_styles'):
			computed_styles_info = node.snapshot_node.computed_styles or {}

		has_cursor, cursor_type, _ = ElementAnalysis._has_any_interactive_cursor(node, computed_styles_info)
		if has_cursor and 'cursor' not in attributes_to_include:
			attributes_to_include['cursor'] = cursor_type

		# Remove duplicate values (but be more selective)
		ordered_keys = []
		seen_values = set()

		# Prioritize certain attributes
		priority_attrs = ['type', 'href', 'role', 'onclick', 'data-action', 'src']
		for attr in priority_attrs:
			if attr in attributes_to_include:
				ordered_keys.append(attr)
				seen_values.add(attributes_to_include[attr])

		# Add remaining attributes, removing duplicates
		for key in include_attributes:
			if key in attributes_to_include and key not in ordered_keys:
				value = attributes_to_include[key]
				if len(value) <= 5 or value not in seen_values:
					ordered_keys.append(key)
					seen_values.add(value)

		# Build final attributes string
		final_attributes = {key: attributes_to_include[key] for key in ordered_keys}

		if final_attributes:
			return ' '.join(f'{key}="{self._cap_text_length(value, 25)}"' for key, value in final_attributes.items())

		return ''

	def _build_attributes_string(self, node: EnhancedDOMTreeNode, include_attributes: list[str], text: str) -> str:
		"""Build the attributes string for an element (legacy method for compatibility)."""
		return self._build_enhanced_attributes_string(node, include_attributes, None)

	def _get_accessibility_role(self, node: EnhancedDOMTreeNode) -> str | None:
		"""Get the accessibility role from the AX node."""
		if node.ax_node:
			return node.ax_node.role
		return None

	def _cap_text_length(self, text: str, max_length: int) -> str:
		"""Cap text length for display."""
		if len(text) <= max_length:
			return text
		return text[:max_length] + '...'

	def _build_element_line_with_context(self, node: SimplifiedNode, depth_str: str, attributes_html_str: str) -> str:
		"""Build the formatted line for an element with enhanced context information."""
		prefixes = []

		# Context prefix for iframe/shadow
		context_info = ''
		if node.iframe_context:
			context_info = f'[{node.iframe_context}]'
		elif node.shadow_context:
			context_info = f'[{node.shadow_context}]'

		# Scrollable prefix
		if getattr(node.original_node, 'is_scrollable', False):
			prefixes.append('SCROLL')

		# Interactive index - show number
		if node.interactive_index is not None:
			prefixes.append(str(node.interactive_index))

		# Build prefix string
		if prefixes:
			if 'SCROLL' in prefixes and any(p.isdigit() for p in prefixes):
				prefix_str = '[SCROLL+' + '+'.join(p for p in prefixes if p != 'SCROLL') + ']'
			elif any(p.isdigit() for p in prefixes):
				prefix_str = '[' + '+'.join(prefixes) + ']'
			else:
				prefix_str = '[' + '+'.join(prefixes) + ']'
		else:
			return ''  # Don't show elements without any interactive features

		# Build the complete line with context
		line = f'{depth_str}{context_info}{prefix_str}<{node.original_node.node_name}'

		if attributes_html_str:
			line += f' {attributes_html_str}'

		line += ' />'
		return line

	def _assign_indices_to_filtered_elements(self, simplified_elements: List[SimplifiedNode]) -> None:
		"""Assign interactive indices to pre-filtered elements."""
		for simplified in simplified_elements:
			simplified.interactive_index = self._interactive_counter
			self._selector_map[self._interactive_counter] = simplified.original_node
			self._interactive_counter += 1

	def _is_element_in_current_viewport(self, node: SimplifiedNode) -> bool:
		"""Check if element is within the current viewport bounds."""
		# **IFRAME/SHADOW DOM EXEMPTION**: Skip viewport filtering for iframe and shadow DOM elements
		# These elements have coordinates relative to their own context, not the main page
		if node.iframe_context or node.shadow_context:
			return True  # If iframe/shadow content is loaded, consider it visible

		if not self.viewport_info or not node.original_node.snapshot_node:
			return True  # If no viewport info, assume visible

		snapshot = node.original_node.snapshot_node
		bounding_box = getattr(snapshot, 'bounding_box', None)
		if not bounding_box:
			return True

		# Get viewport dimensions
		viewport_width = self.viewport_info.get('width', 1920)
		viewport_height = self.viewport_info.get('height', 1080)
		scroll_x = self.viewport_info.get('scroll_x', 0)
		scroll_y = self.viewport_info.get('scroll_y', 0)

		# Calculate viewport bounds
		viewport_left = scroll_x
		viewport_top = scroll_y
		viewport_right = scroll_x + viewport_width
		viewport_bottom = scroll_y + viewport_height

		# Element bounds
		elem_left = bounding_box.get('x', 0)
		elem_top = bounding_box.get('y', 0)
		elem_right = elem_left + bounding_box.get('width', 0)
		elem_bottom = elem_top + bounding_box.get('height', 0)

		# Add small buffer for elements just outside viewport (useful for scrolling)
		buffer = 100  # pixels

		# Check if element intersects with viewport (with buffer)
		intersects = (
			elem_right > (viewport_left - buffer)
			and elem_left < (viewport_right + buffer)
			and elem_bottom > (viewport_top - buffer)
			and elem_top < (viewport_bottom + buffer)
		)

		return intersects
