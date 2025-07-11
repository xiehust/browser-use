# @file purpose: Enhanced DOM serializer with aggressive non-interactive container filtering

from dataclasses import dataclass, field
from typing import List

from cdp_use.cdp.accessibility.types import AXPropertyName

from browser_use.dom.views import DEFAULT_INCLUDE_ATTRIBUTES, EnhancedDOMTreeNode, NodeType


@dataclass(slots=True)
class EnhancedSimplifiedNode:
	"""Enhanced simplified tree node with aggressive container filtering."""

	original_node: EnhancedDOMTreeNode
	children: list['EnhancedSimplifiedNode'] = field(default_factory=list)
	interactive_index: int | None = None
	group_type: str | None = None
	interaction_reason: str | None = None
	is_pure_container: bool = False  # True if this is just a container wrapper

	def is_truly_interactive(self) -> bool:
		"""Check if this node is truly interactive (not just a container)."""
		if self.is_pure_container:
			return False

		node = self.original_node
		node_name = node.node_name.upper()
		reasons = []

		# STEP 1: Immediately exclude structural/semantic containers
		PURE_CONTAINER_ELEMENTS = {
			'HTML',
			'BODY',
			'HEAD',
			'MAIN',
			'SECTION',
			'ARTICLE',
			'ASIDE',
			'NAV',
			'HEADER',
			'FOOTER',
			'FIGURE',
			'FIGCAPTION',
			'HGROUP',
			'ADDRESS',
			'BLOCKQUOTE',
			'PRE',
			'CODE',
			'SAMP',
			'KBD',
			'VAR',
			'DETAILS',
			'SUMMARY',
			'DIALOG',
			'MENU',
			'MENUITEM',
		}

		if node_name in PURE_CONTAINER_ELEMENTS:
			# Only allow these if they have explicit interactive attributes
			if not self._has_explicit_interactive_attributes():
				return False

		# STEP 2: Check for truly interactive elements
		# Form elements are always interactive
		FORM_ELEMENTS = {'INPUT', 'BUTTON', 'SELECT', 'TEXTAREA', 'OPTION', 'OPTGROUP'}
		if node_name in FORM_ELEMENTS:
			reasons.append(f'form_element_{node_name.lower()}')

		# Links with href are interactive
		if node_name == 'A' and node.attributes and 'href' in node.attributes:
			reasons.append('link_with_href')

		# Elements with explicit event handlers
		if self._has_explicit_interactive_attributes():
			reasons.append('explicit_handlers')

		# Interactive ARIA roles
		if self._has_interactive_aria_role():
			reasons.append('interactive_aria')

		# Focusable elements from accessibility tree
		if self._is_accessibility_focusable():
			reasons.append('accessibility_focusable')

		# Cursor pointer style
		if self._has_pointer_cursor():
			reasons.append('pointer_cursor')

		# Contenteditable elements
		if node.attributes and node.attributes.get('contenteditable') in {'true', ''}:
			reasons.append('contenteditable')

		# Draggable elements
		if node.attributes and node.attributes.get('draggable') == 'true':
			reasons.append('draggable')

		# Elements with tabindex (except -1)
		if self._has_positive_tabindex():
			reasons.append('positive_tabindex')

		# STEP 3: Special handling for DIV/SPAN - be very conservative
		if node_name in {'DIV', 'SPAN'}:
			# Only allow DIV/SPAN if they have strong interactive indicators
			if not reasons:
				return False

			# Even with indicators, check if it's likely a wrapper
			if self._is_likely_wrapper():
				return False

		# STEP 4: If we have reasons, it's interactive
		if reasons:
			self.interaction_reason = ','.join(reasons[:2])
			return True

		return False

	def _has_explicit_interactive_attributes(self) -> bool:
		"""Check for explicit interactive attributes."""
		if not self.original_node.attributes:
			return False

		attrs = self.original_node.attributes
		interactive_attrs = {
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
			'data-action',
			'data-toggle',
			'data-dismiss',
			'data-click',
			'data-href',
			'data-target',
			'data-trigger',
			'data-modal',
			'data-tab',
			'jsaction',
			'ng-click',
			'v-on:click',
			'@click',
		}

		return any(attr in attrs for attr in interactive_attrs)

	def _has_interactive_aria_role(self) -> bool:
		"""Check for interactive ARIA roles."""
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

		# Check AX node role
		if self.original_node.ax_node and self.original_node.ax_node.role:
			if self.original_node.ax_node.role.lower() in interactive_roles:
				return True

		# Check role attribute
		if self.original_node.attributes and 'role' in self.original_node.attributes:
			if self.original_node.attributes['role'].lower() in interactive_roles:
				return True

		return False

	def _is_accessibility_focusable(self) -> bool:
		"""Check if element is focusable according to accessibility tree."""
		if not self.original_node.ax_node or not self.original_node.ax_node.properties:
			return False

		for prop in self.original_node.ax_node.properties:
			if prop.name == AXPropertyName.FOCUSABLE and prop.value:
				return True

		return False

	def _has_pointer_cursor(self) -> bool:
		"""Check if element has pointer cursor style."""
		if not self.original_node.snapshot_node:
			return False

		# Check cursor style
		if getattr(self.original_node.snapshot_node, 'cursor_style', None) == 'pointer':
			return True

		# Check computed styles
		computed_styles = getattr(self.original_node.snapshot_node, 'computed_styles', None)
		if computed_styles and computed_styles.get('cursor') == 'pointer':
			return True

		return False

	def _has_positive_tabindex(self) -> bool:
		"""Check if element has positive tabindex."""
		if not self.original_node.attributes or 'tabindex' not in self.original_node.attributes:
			return False

		try:
			tabindex = int(self.original_node.attributes['tabindex'])
			return tabindex >= 0
		except (ValueError, TypeError):
			return False

	def _is_likely_wrapper(self) -> bool:
		"""Check if this DIV/SPAN is likely just a wrapper around other content."""
		# If it has many interactive children, it's likely a wrapper
		interactive_children = sum(1 for child in self.children if child.is_truly_interactive())

		# If all or most children are interactive, this is likely a wrapper
		if len(self.children) > 0:
			interactive_ratio = interactive_children / len(self.children)
			if interactive_ratio > 0.7:  # 70% of children are interactive
				return True

		# If it has many children and significant interactive content, it's a wrapper
		if len(self.children) >= 5 and interactive_children >= 3:
			return True

		# Check for wrapper-like class names
		if self.original_node.attributes and 'class' in self.original_node.attributes:
			classes = self.original_node.attributes['class'].lower()
			wrapper_indicators = {
				'container',
				'wrapper',
				'grid',
				'row',
				'col',
				'flex',
				'layout',
				'content',
				'inner',
				'outer',
				'group',
				'list',
				'items',
				'collection',
				'set',
				'bundle',
				'package',
			}
			if any(indicator in classes for indicator in wrapper_indicators):
				return True

		return False

	def is_effectively_visible(self) -> bool:
		"""Check if element is effectively visible."""
		if not self.original_node.snapshot_node:
			return False

		snapshot = self.original_node.snapshot_node

		# Basic visibility
		is_visible = getattr(snapshot, 'is_visible', None)
		if is_visible is False:
			return False

		# Check computed styles
		computed_styles = getattr(snapshot, 'computed_styles', None)
		if computed_styles:
			if computed_styles.get('display') == 'none':
				return False
			if computed_styles.get('visibility') == 'hidden':
				return False
			if computed_styles.get('pointer-events') == 'none':
				return False

			# Check opacity
			try:
				opacity = float(computed_styles.get('opacity', '1'))
				if opacity == 0:
					return False
			except (ValueError, TypeError):
				pass

			# Check bounding box
			bounding_box = getattr(snapshot, 'bounding_box', None)
			if bounding_box:
				if (
					bounding_box.get('width', 0) <= 0
					or bounding_box.get('height', 0) <= 0
					or bounding_box.get('x', 0) < -9000
					or bounding_box.get('y', 0) < -9000
				):
					return False

		return True

	def should_be_displayed(self) -> bool:
		"""Determine if this element should be displayed in the output."""
		# Always display text nodes if they exist
		if self.original_node.node_type == NodeType.TEXT_NODE:
			return True

		# Only display if it's truly interactive
		if self.is_truly_interactive():
			return True

		# Or if it's scrollable
		if getattr(self.original_node, 'is_scrollable', False):
			return True

		# Or if it's a structural element that contains interactive children
		if self.original_node.node_name.upper() in {'FORM', 'FIELDSET', 'SELECT', 'LABEL'}:
			return True

		# Or if it has interactive children and is not a pure container
		if not self.is_pure_container and any(child.is_truly_interactive() for child in self.children):
			return True

		return False


class EnhancedDOMTreeSerializer:
	"""Enhanced DOM tree serializer with aggressive container filtering."""

	def __init__(self, root_node: EnhancedDOMTreeNode):
		self.root_node = root_node
		self._interactive_counter = 1
		self._selector_map: dict[int, EnhancedDOMTreeNode] = {}
		self._debug_info: List[str] = []

	def serialize_accessible_elements(
		self, include_attributes: list[str] | None = None
	) -> tuple[str, dict[int, EnhancedDOMTreeNode]]:
		"""Serialize DOM tree with aggressive container filtering."""
		if not include_attributes:
			include_attributes = DEFAULT_INCLUDE_ATTRIBUTES

		# Reset state
		self._interactive_counter = 1
		self._selector_map = {}
		self._debug_info = []

		# Processing pipeline
		simplified_tree = self._create_simplified_tree(self.root_node)
		if simplified_tree:
			self._mark_pure_containers(simplified_tree)
			self._assign_interactive_indices(simplified_tree)
			serialized = self._serialize_tree(simplified_tree, include_attributes)
			return serialized, self._selector_map

		return '', {}

	def _create_simplified_tree(self, node: EnhancedDOMTreeNode) -> EnhancedSimplifiedNode | None:
		"""Create simplified tree structure."""
		if node.node_type == NodeType.DOCUMENT_NODE:
			# Process document children
			for child in node.children_nodes or []:
				result = self._create_simplified_tree(child)
				if result:
					return result
			return None

		elif node.node_type == NodeType.ELEMENT_NODE:
			# Skip non-content elements
			if node.node_name.lower() in {'style', 'script', 'head', 'meta', 'link', 'title', '#document'}:
				return None

			simplified = EnhancedSimplifiedNode(original_node=node)

			# Process children
			for child in node.children_nodes or []:
				child_simplified = self._create_simplified_tree(child)
				if child_simplified:
					simplified.children.append(child_simplified)

			# Include if interactive, visible, scrollable, or has children
			is_interactive = simplified.is_truly_interactive()
			is_visible = simplified.is_effectively_visible()
			is_scrollable = getattr(node, 'is_scrollable', False)
			has_children = len(simplified.children) > 0

			if (is_interactive and is_visible) or is_scrollable or has_children:
				return simplified

		elif node.node_type == NodeType.TEXT_NODE:
			# Include meaningful text
			if (
				node.node_value
				and node.node_value.strip()
				and len(node.node_value.strip()) > 1
				and node.snapshot_node
				and getattr(node.snapshot_node, 'is_visible', True)
			):
				return EnhancedSimplifiedNode(original_node=node)

		return None

	def _mark_pure_containers(self, node: EnhancedSimplifiedNode) -> None:
		"""Mark nodes that are pure containers (wrappers)."""
		# Process children first
		for child in node.children:
			self._mark_pure_containers(child)

		# Check if this node is a pure container
		if not node.is_truly_interactive():
			interactive_children = [child for child in node.children if child.is_truly_interactive()]
			total_children = len(node.children)

			# Mark as pure container if:
			# 1. It has many interactive children (likely a grid/list container)
			# 2. All its children are interactive (likely a wrapper)
			# 3. It's a common container element with no interactive attributes

			if (
				len(interactive_children) >= 5  # Many interactive children
				or (total_children > 0 and len(interactive_children) == total_children)  # All children interactive
				or (len(interactive_children) >= 3 and len(interactive_children) / total_children > 0.8)
			):  # High ratio
				node.is_pure_container = True
				self._debug_info.append(
					f'Marked {node.original_node.node_name} as pure container ({len(interactive_children)} interactive children)'
				)

	def _assign_interactive_indices(self, node: EnhancedSimplifiedNode) -> None:
		"""Assign indices only to truly interactive elements."""
		if node.is_truly_interactive() and not node.is_pure_container:
			node.interactive_index = self._interactive_counter
			self._selector_map[self._interactive_counter] = node.original_node
			self._interactive_counter += 1

			# Log the interaction reason
			if node.interaction_reason:
				self._debug_info.append(f'[{node.interactive_index}] {node.original_node.node_name}: {node.interaction_reason}')

		# Process children
		for child in node.children:
			self._assign_interactive_indices(child)

	def _serialize_tree(self, node: EnhancedSimplifiedNode, include_attributes: list[str], depth: int = 0) -> str:
		"""Serialize tree showing only interactive elements and necessary structure."""
		if not node.should_be_displayed():
			# Don't display this node, but still process children
			child_content = []
			for child in node.children:
				child_serialized = self._serialize_tree(child, include_attributes, depth)
				if child_serialized:
					child_content.append(child_serialized)
			return '\n'.join(child_content)

		lines = []
		indent = '\t' * depth

		if node.original_node.node_type == NodeType.ELEMENT_NODE:
			# Build element line
			line = self._build_element_line(node, indent, include_attributes)
			if line:
				lines.append(line)
				depth += 1

		elif node.original_node.node_type == NodeType.TEXT_NODE:
			# Include meaningful text
			text = node.original_node.node_value.strip()
			if text and len(text) <= 100:
				lines.append(f'{indent}{text}')

		# Process children
		for child in node.children:
			child_content = self._serialize_tree(child, include_attributes, depth)
			if child_content:
				lines.append(child_content)

		return '\n'.join(lines)

	def _build_element_line(self, node: EnhancedSimplifiedNode, indent: str, include_attributes: list[str]) -> str:
		"""Build element line with interactive information."""
		prefixes = []

		# Interactive index
		if node.interactive_index is not None:
			prefixes.append(str(node.interactive_index))

		# Scrollable
		if getattr(node.original_node, 'is_scrollable', False):
			prefixes.append('SCROLL')

		# Build prefix
		if prefixes:
			prefix = '[' + '+'.join(prefixes) + ']'
		else:
			# Don't show non-interactive elements unless they're structural
			if node.original_node.node_name.upper() not in {'FORM', 'FIELDSET', 'SELECT', 'LABEL'}:
				return ''
			prefix = ''

		# Build attributes
		attrs = self._build_attributes(node, include_attributes)

		# Complete line
		line = f'{indent}{prefix}<{node.original_node.node_name}'
		if attrs:
			line += f' {attrs}'
		line += ' />'

		return line

	def _build_attributes(self, node: EnhancedSimplifiedNode, include_attributes: list[str]) -> str:
		"""Build attributes string."""
		if not node.original_node.attributes:
			return ''

		attrs = {}

		# Include important attributes
		for attr in include_attributes:
			if attr in node.original_node.attributes:
				value = str(node.original_node.attributes[attr]).strip()
				if value:
					attrs[attr] = value

		# Add interaction-specific attributes
		interaction_attrs = ['type', 'onclick', 'role', 'tabindex', 'data-action', 'href']
		for attr in interaction_attrs:
			if attr in node.original_node.attributes and attr not in attrs:
				attrs[attr] = str(node.original_node.attributes[attr]).strip()

		# Add cursor style if pointer
		if node._has_pointer_cursor():
			attrs['cursor'] = 'pointer'

		# Format attributes (limit to avoid clutter)
		formatted_attrs = []
		for key, value in list(attrs.items())[:4]:  # Limit to 4 attributes
			if len(value) > 25:
				value = value[:22] + '...'
			formatted_attrs.append(f'{key}="{value}"')

		return ' '.join(formatted_attrs)

	def get_debug_info(self) -> List[str]:
		"""Get debug information about the serialization process."""
		return self._debug_info


# Integration function to use the enhanced serializer
def serialize_with_enhanced_filtering(
	root_node: EnhancedDOMTreeNode, include_attributes: list[str] | None = None
) -> tuple[str, dict[int, EnhancedDOMTreeNode]]:
	"""Use the enhanced serializer with aggressive container filtering."""
	serializer = EnhancedDOMTreeSerializer(root_node)
	return serializer.serialize_accessible_elements(include_attributes)
