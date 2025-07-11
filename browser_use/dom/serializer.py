# @file purpose: Serializes enhanced DOM trees to string format for LLM consumption

import time
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from cdp_use.cdp.accessibility.types import AXPropertyName

from browser_use.dom.views import DEFAULT_INCLUDE_ATTRIBUTES, EnhancedDOMTreeNode, NodeType


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
				if is_iframe_or_shadow:
					print(f'    ✅ Cursor pointer {node_name}{context_debug} is clickable')
				self.interaction_priority += 3  # Fixed: back to positive priority
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
					# Also need cursor pointer, tabindex, or role for DIVs
					has_cursor = node.snapshot_node and (
						getattr(node.snapshot_node, 'cursor_style', None) == 'pointer'
						or (node.snapshot_node.computed_styles and node.snapshot_node.computed_styles.get('cursor') == 'pointer')
					)
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

		# Performance metrics
		self.metrics = PerformanceMetrics()

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

		# Step 1: Collect interactive candidates from AX tree
		step_start = time.time()
		interactive_candidates = self._collect_ax_interactive_candidates_fast(self.root_node)
		self.metrics.ax_collection_time = time.time() - step_start
		self.metrics.ax_candidates = len([c for c in interactive_candidates if c[1] == 'ax'])
		self.metrics.dom_candidates = len([c for c in interactive_candidates if c[1] == 'dom'])
		print(f'  📊 Found {len(interactive_candidates)} candidates in {self.metrics.ax_collection_time:.3f}s')
		print(f'     • AX candidates: {self.metrics.ax_candidates}')
		print(f'     • DOM candidates: {self.metrics.dom_candidates}')

		# Step 2: Filter by viewport and deduplicate
		step_start = time.time()
		viewport_filtered = self._filter_by_viewport_and_deduplicate_fast(interactive_candidates)
		self.metrics.filtering_time = time.time() - step_start
		self.metrics.after_viewport_filter = len(viewport_filtered)
		print(f'  🎯 Filtered to {len(viewport_filtered)} viewport-visible elements in {self.metrics.filtering_time:.3f}s')

		# Step 3: Build minimal simplified tree only for filtered elements
		step_start = time.time()
		simplified_elements = self._build_minimal_simplified_tree_fast(viewport_filtered)
		self.metrics.tree_building_time = time.time() - step_start
		print(f'  🔧 Built minimal tree with {len(simplified_elements)} elements in {self.metrics.tree_building_time:.3f}s')

		# Step 4: Assign interactive indices (no heavy consolidation needed)
		step_start = time.time()
		self._assign_indices_to_filtered_elements(simplified_elements)
		self.metrics.indexing_time = time.time() - step_start
		self.metrics.final_interactive_count = len(self._selector_map)
		print(f'  🏷️  Assigned {len(self._selector_map)} interactive indices in {self.metrics.indexing_time:.3f}s')

		# Step 5: Serialize minimal tree
		step_start = time.time()
		serialized = self._serialize_minimal_tree_fast(simplified_elements, include_attributes)
		self.metrics.serialization_time = time.time() - step_start
		print(f'  📝 Serialized {len(serialized)} characters in {self.metrics.serialization_time:.3f}s')

		return serialized, self._selector_map

	def _collect_ax_interactive_candidates_fast(self, node: EnhancedDOMTreeNode) -> List[Tuple[EnhancedDOMTreeNode, str]]:
		"""Collect interactive candidates using optimized traversal with caching."""
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

			# Check if this node is interactive via AX tree (cached)
			ax_interactive_key = f'ax_{node_key}'
			if ax_interactive_key not in self._interactivity_cache:
				self._interactivity_cache[ax_interactive_key] = self._is_ax_interactive_fast(current_node)

			if self._interactivity_cache[ax_interactive_key]:
				candidates.append((current_node, 'ax'))
				if depth <= 10:  # Only show debug for shallow elements to reduce noise
					print(f'    ✅ AX interactive: {current_node.node_name} (depth {depth})')

			# Check if this node is interactive via DOM attributes/snapshot (cached)
			else:
				dom_interactive_key = f'dom_{node_key}'
				if dom_interactive_key not in self._interactivity_cache:
					self._interactivity_cache[dom_interactive_key] = self._is_dom_interactive_fast(current_node)

				if self._interactivity_cache[dom_interactive_key]:
					candidates.append((current_node, 'dom'))
					if depth <= 10:  # Only show debug for shallow elements to reduce noise
						print(f'    ✅ DOM interactive: {current_node.node_name} (depth {depth})')

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

		# Fast cursor pointer check
		if node.snapshot_node:
			if getattr(node.snapshot_node, 'cursor_style', None) == 'pointer':
				return True
			if node.snapshot_node.computed_styles and node.snapshot_node.computed_styles.get('cursor') == 'pointer':
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

	def _filter_by_viewport_and_deduplicate_fast(
		self, candidates: List[Tuple[EnhancedDOMTreeNode, str]]
	) -> List[EnhancedDOMTreeNode]:
		"""Fast filter candidates by viewport and remove duplicates."""
		filtered = []
		seen_elements: Set[str] = set()  # Track unique elements by x_path

		for candidate_node, candidate_type in candidates:
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
		"""Fast serialize minimal tree with only interactive elements."""
		lines = []

		# Fast context summary
		context_summary = self._build_context_summary()
		if context_summary:
			lines.append(context_summary)
			lines.append('')

		# Fast serialize each interactive element
		for simplified in simplified_elements:
			node = simplified.original_node

			# Fast attributes string building
			attrs_str = self._build_enhanced_attributes_string_fast(node, include_attributes, simplified)

			# Fast line building
			line = f'[{simplified.interactive_index}]<{node.node_name}'
			if attrs_str:
				line += f' {attrs_str}'
			line += ' />'

			lines.append(line)

		return '\n'.join(lines)

	def _build_enhanced_attributes_string_fast(
		self, node: EnhancedDOMTreeNode, include_attributes: list[str], simplified_node: SimplifiedNode | None
	) -> str:
		"""Fast build enhanced attributes string with interaction-relevant information."""
		if not node.attributes:
			return ''

		# Fast attribute filtering
		important_attrs = ['id', 'class', 'type', 'href', 'role', 'aria-label']
		result_attrs = {}

		for attr in important_attrs:
			if attr in node.attributes and attr in include_attributes:
				value = str(node.attributes[attr]).strip()
				if value and len(value) <= 50:  # Fast length check
					result_attrs[attr] = value

		# Fast cursor style addition
		if node.snapshot_node and getattr(node.snapshot_node, 'cursor_style', None) == 'pointer' and 'cursor' not in result_attrs:
			result_attrs['cursor'] = 'pointer'

		# Fast result building
		if result_attrs:
			return ' '.join(f'{key}="{value[:25]}"' for key, value in result_attrs.items())

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
