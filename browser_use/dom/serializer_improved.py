# @file purpose: Improved DOM serializer with comprehensive interactive element detection

from dataclasses import dataclass, field
from typing import Dict, List

from cdp_use.cdp.accessibility.types import AXPropertyName

from browser_use.dom.views import DEFAULT_INCLUDE_ATTRIBUTES, EnhancedDOMTreeNode, NodeType


@dataclass(slots=True)
class ImprovedSimplifiedNode:
	"""Enhanced simplified tree node with comprehensive interactivity detection."""

	original_node: EnhancedDOMTreeNode
	children: list['ImprovedSimplifiedNode'] = field(default_factory=list)
	should_display: bool = True
	interactive_index: int | None = None
	group_type: str | None = None
	interaction_reason: str | None = None  # Why this element is considered interactive

	def is_comprehensively_interactive(self) -> bool:
		"""Check if this node is interactive using comprehensive detection."""
		node = self.original_node
		reasons = []

		# 1. Traditional clickability from snapshot
		if node.snapshot_node and getattr(node.snapshot_node, 'is_clickable', False):
			reasons.append('snapshot_clickable')

		# 2. Cursor style indicates interactivity
		if node.snapshot_node and getattr(node.snapshot_node, 'cursor_style', None) == 'pointer':
			reasons.append('cursor_pointer')

		# 3. Focusable elements from accessibility tree
		if node.ax_node and node.ax_node.properties:
			for prop in node.ax_node.properties:
				if prop.name == AXPropertyName.FOCUSABLE and prop.value:
					reasons.append('focusable')
					break

		# 4. Interactive ARIA roles
		if node.ax_node and node.ax_node.role:
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
			}
			if node.ax_node.role.lower() in interactive_roles:
				reasons.append(f'aria_role_{node.ax_node.role}')

		# 5. Form elements
		if node.node_name.upper() in {'INPUT', 'BUTTON', 'SELECT', 'TEXTAREA', 'OPTION'}:
			reasons.append(f'form_element_{node.node_name.lower()}')

		# 6. Links with href
		if node.node_name.upper() == 'A' and node.attributes and 'href' in node.attributes:
			reasons.append('link_with_href')

		# 7. Elements with event handlers
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
			found_events = [attr for attr in event_attributes if attr in node.attributes]
			if found_events:
				reasons.append(f'event_handlers_{",".join(found_events)}')

			# Interactive data attributes
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
				'data-role',
			}
			found_data = [attr for attr in interactive_data_attrs if attr in node.attributes]
			if found_data:
				reasons.append(f'data_attrs_{",".join(found_data)}')

		# 8. Tabindex (except -1)
		if node.attributes and 'tabindex' in node.attributes:
			try:
				tabindex = int(node.attributes['tabindex'])
				if tabindex >= 0:
					reasons.append(f'tabindex_{tabindex}')
			except ValueError:
				pass

		# 9. Role attribute
		if node.attributes and 'role' in node.attributes:
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
			}
			if node.attributes['role'].lower() in interactive_roles:
				reasons.append(f'role_attr_{node.attributes["role"]}')

		# 10. Draggable elements
		if node.attributes and node.attributes.get('draggable') == 'true':
			reasons.append('draggable')

		# 11. Contenteditable elements
		if node.attributes and node.attributes.get('contenteditable') in {'true', ''}:
			reasons.append('contenteditable')

		# Store the interaction reason for debugging
		if reasons:
			self.interaction_reason = ','.join(reasons[:3])  # Limit to first 3 reasons
			return True

		return False

	def is_effectively_visible(self) -> bool:
		"""Check visibility with comprehensive detection."""
		if not self.original_node.snapshot_node:
			return False

		snapshot = self.original_node.snapshot_node

		# Handle different snapshot node structures
		is_visible = getattr(snapshot, 'is_visible', None)
		if is_visible is False:
			return False

		# Check computed styles if available
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

			# Check if positioned off-screen
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

	def is_groupable_element(self) -> str | None:
		"""Determine if this element should be grouped and return group type."""
		node = self.original_node

		# Radio buttons and checkboxes
		if (
			node.node_name.upper() == 'INPUT'
			and node.attributes
			and node.attributes.get('type', '').lower() in {'radio', 'checkbox'}
		):
			return f'input_group_{node.attributes.get("name", "unnamed")}'

		# Select options
		if node.node_name.upper() == 'OPTION':
			return 'select_options'

		# Custom dropdown options by class
		if node.attributes and 'class' in node.attributes:
			classes = node.attributes['class'].lower()
			if any(cls in classes for cls in ['option', 'menu-item', 'dropdown-item']):
				return 'custom_dropdown_options'

		return None


class ImprovedDOMTreeSerializer:
	"""Enhanced DOM tree serializer with comprehensive interactive element detection."""

	def __init__(self, root_node: EnhancedDOMTreeNode):
		self.root_node = root_node
		self._interactive_counter = 1
		self._selector_map: dict[int, EnhancedDOMTreeNode] = {}
		self._element_groups: Dict[str, List[ImprovedSimplifiedNode]] = {}
		self._debug_info: List[str] = []

	def serialize_accessible_elements(
		self, include_attributes: list[str] | None = None
	) -> tuple[str, dict[int, EnhancedDOMTreeNode]]:
		"""Enhanced serialization with comprehensive interactive element detection."""
		if not include_attributes:
			include_attributes = DEFAULT_INCLUDE_ATTRIBUTES

		# Reset state
		self._interactive_counter = 1
		self._selector_map = {}
		self._element_groups = {}
		self._debug_info = []

		# Enhanced processing pipeline
		simplified_tree = self._create_enhanced_tree(self.root_node)
		optimized_tree = self._optimize_tree(simplified_tree)
		self._group_elements(optimized_tree)
		self._assign_indices(optimized_tree)
		serialized = self._serialize_enhanced(optimized_tree, include_attributes)

		return serialized, self._selector_map

	def _create_enhanced_tree(self, node: EnhancedDOMTreeNode) -> ImprovedSimplifiedNode | None:
		"""Create simplified tree with enhanced detection."""

		if node.node_type == NodeType.DOCUMENT_NODE:
			if node.children_nodes:
				for child in node.children_nodes:
					result = self._create_enhanced_tree(child)
					if result:
						return result
			return None

		elif node.node_type == NodeType.ELEMENT_NODE:
			if node.node_name in ['#document', 'style', 'script', 'head', 'meta', 'link', 'title']:
				return None

			simplified = ImprovedSimplifiedNode(original_node=node)

			# Enhanced interactivity detection
			is_interactive = simplified.is_comprehensively_interactive()
			is_visible = simplified.is_effectively_visible()
			is_scrollable = getattr(node, 'is_scrollable', False)

			# Process children
			children = []
			if node.children_nodes:
				for child in node.children_nodes:
					child_node = self._create_enhanced_tree(child)
					if child_node:
						children.append(child_node)

			simplified.children = children

			# Include if interactive and visible, or has interactive children, or is structural
			has_interactive_children = any(c.is_comprehensively_interactive() for c in children)
			is_structural = node.node_name.upper() in {'FORM', 'FIELDSET', 'SELECT', 'NAV', 'UL', 'OL'}

			if (is_interactive and is_visible) or has_interactive_children or is_scrollable or is_structural:
				return simplified

		elif node.node_type == NodeType.TEXT_NODE:
			if (
				node.node_value
				and node.node_value.strip()
				and len(node.node_value.strip()) > 1
				and node.snapshot_node
				and getattr(node.snapshot_node, 'is_visible', True)
			):
				return ImprovedSimplifiedNode(original_node=node)

		return None

	def _optimize_tree(self, node: ImprovedSimplifiedNode | None) -> ImprovedSimplifiedNode | None:
		"""Optimize tree while preserving all interactive elements."""
		if not node:
			return None

		# Process children
		optimized_children = []
		for child in node.children:
			optimized_child = self._optimize_tree(child)
			if optimized_child:
				optimized_children.append(optimized_child)

		node.children = optimized_children

		# Keep interactive elements, text nodes, structural elements, or nodes with children
		if (
			node.is_comprehensively_interactive()
			or node.original_node.node_type == NodeType.TEXT_NODE
			or node.original_node.node_name.upper() in {'FORM', 'FIELDSET', 'SELECT', 'LABEL'}
			or node.children
		):
			return node

		return None

	def _group_elements(self, node: ImprovedSimplifiedNode | None) -> None:
		"""Group related interactive elements."""
		if not node:
			return

		# Process children first
		for child in node.children:
			self._group_elements(child)

		# Group this element if applicable
		group_type = node.is_groupable_element()
		if group_type:
			node.group_type = group_type
			if group_type not in self._element_groups:
				self._element_groups[group_type] = []
			self._element_groups[group_type].append(node)

	def _assign_indices(self, node: ImprovedSimplifiedNode | None) -> None:
		"""Assign interactive indices to elements."""
		if not node:
			return

		# Assign index if interactive
		if node.is_comprehensively_interactive():
			node.interactive_index = self._interactive_counter
			self._selector_map[self._interactive_counter] = node.original_node
			self._interactive_counter += 1

			# Log what made this element interactive
			if node.interaction_reason:
				self._debug_info.append(f'[{node.interactive_index}] {node.original_node.node_name}: {node.interaction_reason}')

		# Process children
		for child in node.children:
			self._assign_indices(child)

	def _serialize_enhanced(self, node: ImprovedSimplifiedNode | None, include_attributes: list[str], depth: int = 0) -> str:
		"""Enhanced serialization with grouping and detailed information."""
		if not node:
			return ''

		lines = []
		indent = '\t' * depth

		if node.original_node.node_type == NodeType.ELEMENT_NODE:
			if self._should_display_element(node):
				# Build enhanced element line
				line = self._build_enhanced_line(node, indent, include_attributes)
				if line:
					lines.append(line)
					depth += 1

		elif node.original_node.node_type == NodeType.TEXT_NODE:
			text = node.original_node.node_value.strip()
			if text and len(text) <= 100:
				lines.append(f'{indent}{text}')

		# Process children
		for child in node.children:
			child_content = self._serialize_enhanced(child, include_attributes, depth)
			if child_content:
				lines.append(child_content)

		return '\n'.join(lines)

	def _should_display_element(self, node: ImprovedSimplifiedNode) -> bool:
		"""Determine if element should be displayed."""
		return (
			node.interactive_index is not None
			or getattr(node.original_node, 'is_scrollable', False)
			or node.original_node.node_name.upper() in {'FORM', 'FIELDSET', 'SELECT', 'LABEL'}
			or any(child.interactive_index is not None for child in node.children)
		)

	def _build_enhanced_line(self, node: ImprovedSimplifiedNode, indent: str, include_attributes: list[str]) -> str:
		"""Build enhanced element line with comprehensive information."""
		prefixes = []

		# Interactive index
		if node.interactive_index is not None:
			prefixes.append(str(node.interactive_index))

		# Scrollable
		if getattr(node.original_node, 'is_scrollable', False):
			prefixes.append('SCROLL')

		# Group information
		if node.group_type:
			if 'input_group' in node.group_type:
				input_type = node.original_node.attributes.get('type', 'input').upper()
				prefixes.append(f'GROUP_{input_type}')
			elif 'options' in node.group_type:
				prefixes.append('OPT')

		# Build prefix
		if prefixes:
			if any(p.isdigit() for p in prefixes):
				prefix = '[' + '+'.join(prefixes) + ']'
			else:
				prefix = '|' + '+'.join(prefixes) + '|'
		else:
			prefix = ''

		if not prefix:
			return ''

		# Build attributes
		attrs = self._build_enhanced_attributes(node, include_attributes)

		# Complete line
		line = f'{indent}{prefix}<{node.original_node.node_name}'
		if attrs:
			line += f' {attrs}'
		line += ' />'

		return line

	def _build_enhanced_attributes(self, node: ImprovedSimplifiedNode, include_attributes: list[str]) -> str:
		"""Build enhanced attributes string."""
		if not node.original_node.attributes:
			return ''

		attrs = {}

		# Include standard attributes
		for attr in include_attributes:
			if attr in node.original_node.attributes:
				value = str(node.original_node.attributes[attr]).strip()
				if value:
					attrs[attr] = value

		# Add interaction-specific attributes
		interaction_attrs = ['type', 'href', 'onclick', 'role', 'tabindex', 'data-action', 'data-toggle']
		for attr in interaction_attrs:
			if attr in node.original_node.attributes and attr not in attrs:
				attrs[attr] = str(node.original_node.attributes[attr]).strip()

		# Add cursor style if pointer
		if node.original_node.snapshot_node and getattr(node.original_node.snapshot_node, 'cursor_style', None) == 'pointer':
			attrs['cursor'] = 'pointer'

		# Add interaction reason for debugging
		if node.interaction_reason and len(attrs) < 3:
			attrs['_debug'] = node.interaction_reason[:20]

		# Format attributes
		formatted_attrs = []
		for key, value in list(attrs.items())[:5]:  # Limit to 5 attributes
			if len(value) > 30:
				value = value[:27] + '...'
			formatted_attrs.append(f'{key}="{value}"')

		return ' '.join(formatted_attrs)

	def get_debug_info(self) -> List[str]:
		"""Get debug information about detected interactive elements."""
		return self._debug_info


# Wrapper function to use the improved serializer
def serialize_with_improved_detection(
	root_node: EnhancedDOMTreeNode, include_attributes: list[str] | None = None
) -> tuple[str, dict[int, EnhancedDOMTreeNode]]:
	"""Use the improved serializer for better interactive element detection."""
	serializer = ImprovedDOMTreeSerializer(root_node)
	return serializer.serialize_accessible_elements(include_attributes)
