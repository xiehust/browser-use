# @file purpose: Serializes enhanced DOM trees to string format for LLM consumption

from dataclasses import dataclass, field
from typing import Dict, List

from cdp_use.cdp.accessibility.types import AXPropertyName

from browser_use.dom.views import DEFAULT_INCLUDE_ATTRIBUTES, EnhancedDOMTreeNode, NodeType


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

		# **EXCLUDE STRUCTURAL CONTAINERS**: Never mark these as interactive
		if node_name in {'HTML', 'BODY', 'HEAD', 'TITLE', 'META', 'STYLE', 'SCRIPT'}:
			return False

		# **FORM ELEMENTS**: Always interactive if they're genuine form controls
		if node_name in {'INPUT', 'BUTTON', 'SELECT', 'TEXTAREA', 'OPTION'}:
			self.interaction_priority += 10
			return True

		# **LINKS**: Always interactive if they have href
		if node_name == 'A' and node.attributes and 'href' in node.attributes:
			self.interaction_priority += 9
			return True

		# **TRADITIONAL CLICKABILITY**: From snapshot (high confidence)
		if node.snapshot_node and getattr(node.snapshot_node, 'is_clickable', False):
			self.interaction_priority += 10
			return True

		# **CURSOR POINTER**: Include ALL elements with cursor pointer (user's request)
		has_cursor_pointer = False
		if node.snapshot_node:
			if getattr(node.snapshot_node, 'cursor_style', None) == 'pointer':
				has_cursor_pointer = True
			elif node.snapshot_node.computed_styles and node.snapshot_node.computed_styles.get('cursor') == 'pointer':
				has_cursor_pointer = True

		if has_cursor_pointer:
			# Exclude obvious containers/wrappers but include most cursor pointer elements
			if node_name not in {'HTML', 'BODY', 'MAIN', 'SECTION', 'ARTICLE', 'ASIDE', 'NAV', 'HEADER', 'FOOTER'}:
				self.interaction_priority += 3
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
			self.interaction_priority += 9
			return True

		# Check role attribute
		if node.attributes and 'role' in node.attributes and node.attributes['role'].lower() in interactive_roles:
			self.interaction_priority += 9
			return True

		# **ACCESSIBILITY FOCUSABLE**: Elements marked as focusable by accessibility tree
		if node.ax_node and node.ax_node.properties:
			for prop in node.ax_node.properties:
				if prop.name == AXPropertyName.FOCUSABLE and prop.value:
					self.interaction_priority += 7
					return True

		# **CONSERVATIVE CONTAINER HANDLING**: For remaining DIV/SPAN/LABEL elements
		if node_name in {'DIV', 'SPAN', 'LABEL'}:
			return self._is_container_truly_interactive(node)

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
				self.interaction_priority += 6
				return True

		# **POSITIVE TABINDEX**: Elements explicitly made focusable (excluding -1)
		if node.attributes and 'tabindex' in node.attributes:
			try:
				tabindex = int(node.attributes['tabindex'])
				if tabindex >= 0:
					self.interaction_priority += 5
					return True
			except ValueError:
				pass

		# **DRAGGABLE/EDITABLE**: Special interactive capabilities
		if node.attributes:
			if node.attributes.get('draggable') == 'true':
				self.interaction_priority += 4
				return True
			if node.attributes.get('contenteditable') in {'true', ''}:
				self.interaction_priority += 4
				return True

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

		# **DIV/SPAN**: More permissive - check for any interactive indicators
		if node_name in {'DIV', 'SPAN'}:
			if not node.attributes:
				return False

			attrs = node.attributes

			# Has explicit event handlers
			if any(attr in attrs for attr in ['onclick', 'onmousedown', 'onmouseup', 'onkeydown']):
				self.interaction_priority += 4
				return True

			# Has interactive role
			if attrs.get('role', '').lower() in {'button', 'link', 'menuitem', 'tab', 'option', 'combobox'}:
				self.interaction_priority += 4
				return True

			# Has interactive data attributes (Google Material Design, etc.)
			if any(attr in attrs for attr in ['data-action', 'data-toggle', 'data-href', 'jsaction']):
				self.interaction_priority += 3
				return True

			# Has tabindex >= 0 (explicitly focusable)
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

	def _is_element_in_current_viewport(self, node: SimplifiedNode) -> bool:
		"""Check if element is within the current viewport bounds."""
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

		# Only consider DIV and SPAN as potential wrappers
		if node_name not in {'DIV', 'SPAN'}:
			return False

		# If the node itself is interactive, don't treat as wrapper
		if node.is_clickable():
			return False

		# Count interactive and non-interactive children
		interactive_children = [child for child in node.children if child.is_clickable()]
		total_children = len(node.children)

		# **LARGE CONTAINER DETECTION**: If container has many interactive children, it's likely a calendar/menu container
		if len(interactive_children) >= 10:  # Calendar with many date buttons
			# This is likely a calendar, dropdown menu, or similar container
			# The container itself shouldn't be interactive, only the individual buttons
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
					return True
			return True

		# **TRADITIONAL WRAPPER DETECTION**: Single or few children
		# Case 1: Exactly one interactive child - likely a wrapper
		if len(interactive_children) == 1 and total_children <= 3:
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
			has_cursor_pointer = parent_node.original_node.snapshot_node and (
				getattr(parent_node.original_node.snapshot_node, 'cursor_style', None) == 'pointer'
				or (
					parent_node.original_node.snapshot_node.computed_styles
					and parent_node.original_node.snapshot_node.computed_styles.get('cursor') == 'pointer'
				)
			)

			if has_click_handler or has_role or has_cursor_pointer:
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
		"""Step 1: Create a simplified tree with enhanced interactive element detection and iframe/shadow traversal."""

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
			should_include = (
				(is_interactive and is_effectively_visible) or is_scrollable or is_iframe or node.children_nodes
			)  # Include containers that might have interactive children

			if should_include:
				# Process regular children
				if node.children_nodes:
					for child in node.children_nodes:
						simplified_child = self._create_simplified_tree(child, iframe_context, shadow_context)
						if simplified_child:
							simplified.children.append(simplified_child)

				# Process iframe content if present
				if node.content_document and is_iframe:
					iframe_context_id = self._register_iframe_context(node)
					iframe_child = self._create_simplified_tree(node.content_document, iframe_context_id, shadow_context)
					if iframe_child:
						# Wrap iframe content with special marker
						iframe_wrapper = SimplifiedNode(
							original_node=node.content_document, iframe_context=iframe_context_id, shadow_context=shadow_context
						)
						iframe_wrapper.children = [iframe_child]
						iframe_wrapper.should_display = False  # Don't show wrapper itself
						simplified.children.append(iframe_wrapper)

				# Process shadow roots if present
				if node.shadow_roots:
					for i, shadow_root in enumerate(node.shadow_roots):
						shadow_context_id = self._register_shadow_context(node, i)
						shadow_child = self._create_simplified_tree(shadow_root, iframe_context, shadow_context_id)
						if shadow_child:
							# Wrap shadow content with special marker
							shadow_wrapper = SimplifiedNode(
								original_node=shadow_root, iframe_context=iframe_context, shadow_context=shadow_context_id
							)
							shadow_wrapper.children = [shadow_child]
							shadow_wrapper.should_display = False  # Don't show wrapper itself
							simplified.children.append(shadow_wrapper)

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

	def _register_iframe_context(self, iframe_node: EnhancedDOMTreeNode) -> str:
		"""Register an iframe context and return its ID."""
		iframe_src = iframe_node.attributes.get('src') if iframe_node.attributes else None
		iframe_xpath = iframe_node.x_path

		# Check if iframe is cross-origin
		is_cross_origin = self._is_cross_origin_iframe(iframe_node)
		if is_cross_origin and iframe_src:
			self._cross_origin_iframes.append(iframe_src)

		context_id = f'iframe_{len(self._iframe_contexts)}'
		self._iframe_contexts[context_id] = IFrameContextInfo(
			iframe_xpath=iframe_xpath, iframe_src=iframe_src, is_cross_origin=is_cross_origin, context_id=context_id
		)
		return context_id

	def _register_shadow_context(self, parent_node: EnhancedDOMTreeNode, shadow_index: int) -> str:
		"""Register a shadow DOM context and return its ID."""
		shadow_id = f'shadow_{len(self._shadow_contexts)}_{shadow_index}'
		self._shadow_contexts[shadow_id] = parent_node.x_path
		return shadow_id

	def _is_cross_origin_iframe(self, iframe_node: EnhancedDOMTreeNode) -> bool:
		"""Check if an iframe is cross-origin by examining its content availability."""
		# If we have content_document, it's likely same-origin
		# If we don't have content_document but have an iframe, it might be cross-origin
		if not iframe_node.content_document:
			return True

		# Additional heuristics could be added here based on src URL comparison
		return False

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
			if node.is_clickable() and self._is_element_in_current_viewport(node):
				node.interactive_index = self._interactive_counter
				self._selector_map[self._interactive_counter] = self._create_contextual_node(node)
				self._interactive_counter += 1

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
		"""Step 6: Serialize the optimized tree with enhanced grouping and iframe/shadow information."""
		if not node:
			return ''

		formatted_text = []
		depth_str = depth * '\t'
		next_depth = depth

		if node.original_node.node_type == NodeType.ELEMENT_NODE:
			# Skip displaying nodes marked as should_display=False (iframe/shadow wrappers)
			if not node.should_display:
				# Special handling for iframe and shadow wrappers
				if node.iframe_context:
					formatted_text.append(f'{depth_str}>>> IFRAME CONTENT [{node.iframe_context}] <<<')
					next_depth += 1
				elif node.shadow_context:
					formatted_text.append(f'{depth_str}>>> SHADOW DOM [{node.shadow_context}] <<<')
					next_depth += 1

				for child in node.children:
					child_text = self._serialize_tree(child, include_attributes, next_depth)
					if child_text:
						formatted_text.append(child_text)

				if node.iframe_context or node.shadow_context:
					formatted_text.append(f'{depth_str}>>> END <<<')

				return '\n'.join(formatted_text)

			# Enhanced element display with more information
			if (
				node.interactive_index is not None
				or getattr(node.original_node, 'is_scrollable', False)
				or self._should_show_element(node)
			):
				next_depth += 1

				# Build attributes string with enhanced information
				attributes_html_str = self._build_enhanced_attributes_string(node.original_node, include_attributes, node)

				# Build the line with enhanced prefixes - SIMPLIFIED FORMAT
				line = self._build_element_line(node, depth_str, attributes_html_str)

				if line:
					formatted_text.append(line)

		elif node.original_node.node_type == NodeType.TEXT_NODE:
			# Include meaningful text content
			if self._should_include_text(node):
				clean_text = node.original_node.node_value.strip()
				# Limit text length for readability
				if len(clean_text) > 100:
					clean_text = clean_text[:97] + '...'

				# Add context prefix for iframe/shadow text
				context_prefix = ''
				if node.iframe_context:
					context_prefix = f'[{node.iframe_context}] '
				elif node.shadow_context:
					context_prefix = f'[{node.shadow_context}] '

				formatted_text.append(f'{depth_str}{context_prefix}{clean_text}')

		# Process children
		for child in node.children:
			child_text = self._serialize_tree(child, include_attributes, next_depth)
			if child_text:
				formatted_text.append(child_text)

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
		interaction_attributes = {'type', 'href', 'onclick', 'role', 'tabindex', 'data-action', 'data-toggle', 'src'}

		for attr in interaction_attributes:
			if attr in node.attributes and attr not in attributes_to_include:
				attributes_to_include[attr] = str(node.attributes[attr]).strip()

		# Add cursor style if pointer
		if (
			node.snapshot_node
			and getattr(node.snapshot_node, 'cursor_style', None) == 'pointer'
			and 'cursor' not in attributes_to_include
		):
			attributes_to_include['cursor'] = 'pointer'

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
