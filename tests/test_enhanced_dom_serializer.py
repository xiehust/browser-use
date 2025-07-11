"""
Comprehensive tests for the enhanced DOM serializer.
Tests verify that all intended interactive elements are detected while non-interactive containers are filtered out.
"""

from unittest.mock import Mock

import pytest
from cdp_use.cdp.accessibility.types import AXPropertyName

from browser_use.dom.serializer_enhanced import (
	EnhancedDOMTreeSerializer,
	EnhancedSimplifiedNode,
	serialize_with_enhanced_filtering,
)
from browser_use.dom.views import EnhancedAXNode, EnhancedDOMTreeNode, EnhancedSnapshotNode, NodeType


def create_mock_node(
	node_name: str,
	node_type: NodeType = NodeType.ELEMENT_NODE,
	attributes: dict | None = None,
	children: list | None = None,
	is_visible: bool = True,
	cursor_style: str | None = None,
	ax_role: str | None = None,
	is_focusable: bool = False,
	computed_styles: dict | None = None,
	bounding_box: dict | None = None,
	node_value: str | None = None,
	is_scrollable: bool = False,
) -> EnhancedDOMTreeNode:
	"""Create a mock DOM node for testing."""

	# Create snapshot node
	snapshot_node = Mock(spec=EnhancedSnapshotNode)
	snapshot_node.is_visible = is_visible
	snapshot_node.cursor_style = cursor_style
	snapshot_node.computed_styles = computed_styles or {}
	snapshot_node.bounding_box = bounding_box or {'x': 100, 'y': 100, 'width': 50, 'height': 20}

	# Create AX node
	ax_node = None
	if ax_role or is_focusable:
		ax_node = Mock(spec=EnhancedAXNode)
		ax_node.role = ax_role
		ax_node.properties = []
		if is_focusable:
			focusable_prop = Mock()
			focusable_prop.name = AXPropertyName.FOCUSABLE
			focusable_prop.value = True
			ax_node.properties.append(focusable_prop)

	# Create main node
	node = Mock(spec=EnhancedDOMTreeNode)
	node.node_name = node_name
	node.node_type = node_type
	node.attributes = attributes or {}
	node.children_nodes = children or []
	node.snapshot_node = snapshot_node
	node.ax_node = ax_node
	node.node_value = node_value
	node.is_scrollable = is_scrollable
	node.parent_node = None
	node.content_document = None
	node.shadow_roots = None
	node.frame_id = None
	node.shadow_root_type = None
	node.backend_node_id = 1
	node.node_id = 1

	return node


class TestEnhancedSimplifiedNode:
	"""Test the enhanced simplified node logic."""

	def test_form_elements_are_interactive(self):
		"""Test that form elements are correctly identified as interactive."""
		form_elements = ['INPUT', 'BUTTON', 'SELECT', 'TEXTAREA', 'OPTION']

		for element in form_elements:
			node = create_mock_node(element)
			simplified = EnhancedSimplifiedNode(original_node=node)

			assert simplified.is_truly_interactive(), f'{element} should be interactive'
			assert simplified.interaction_reason is not None and 'form_element' in simplified.interaction_reason

	def test_links_with_href_are_interactive(self):
		"""Test that links with href are interactive."""
		node = create_mock_node('A', attributes={'href': 'https://example.com'})
		simplified = EnhancedSimplifiedNode(original_node=node)

		assert simplified.is_truly_interactive()
		assert simplified.interaction_reason is not None and 'link_with_href' in simplified.interaction_reason

	def test_links_without_href_are_not_interactive(self):
		"""Test that links without href are not interactive."""
		node = create_mock_node('A')
		simplified = EnhancedSimplifiedNode(original_node=node)

		assert not simplified.is_truly_interactive()

	def test_elements_with_onclick_are_interactive(self):
		"""Test that elements with onclick handlers are interactive."""
		node = create_mock_node('DIV', attributes={'onclick': 'doSomething()'})
		simplified = EnhancedSimplifiedNode(original_node=node)

		assert simplified.is_truly_interactive()
		assert simplified.interaction_reason is not None and 'explicit_handlers' in simplified.interaction_reason

	def test_elements_with_data_action_are_interactive(self):
		"""Test that elements with data-action are interactive."""
		node = create_mock_node('DIV', attributes={'data-action': 'submit'})
		simplified = EnhancedSimplifiedNode(original_node=node)

		assert simplified.is_truly_interactive()
		assert simplified.interaction_reason is not None and 'explicit_handlers' in simplified.interaction_reason

	def test_elements_with_pointer_cursor_are_interactive(self):
		"""Test that elements with pointer cursor are interactive."""
		node = create_mock_node('DIV', cursor_style='pointer')
		simplified = EnhancedSimplifiedNode(original_node=node)

		assert simplified.is_truly_interactive()
		assert simplified.interaction_reason is not None and 'pointer_cursor' in simplified.interaction_reason

	def test_focusable_elements_are_interactive(self):
		"""Test that accessibility focusable elements are interactive."""
		node = create_mock_node('DIV', is_focusable=True)
		simplified = EnhancedSimplifiedNode(original_node=node)

		assert simplified.is_truly_interactive()
		assert simplified.interaction_reason is not None and 'accessibility_focusable' in simplified.interaction_reason

	def test_elements_with_interactive_aria_roles_are_interactive(self):
		"""Test that elements with interactive ARIA roles are interactive."""
		interactive_roles = ['button', 'link', 'menuitem', 'tab', 'checkbox']

		for role in interactive_roles:
			# Test AX node role
			node = create_mock_node('DIV', ax_role=role)
			simplified = EnhancedSimplifiedNode(original_node=node)
			assert simplified.is_truly_interactive(), f'Element with AX role {role} should be interactive'

			# Test role attribute
			node = create_mock_node('DIV', attributes={'role': role})
			simplified = EnhancedSimplifiedNode(original_node=node)
			assert simplified.is_truly_interactive(), f'Element with role attribute {role} should be interactive'

	def test_contenteditable_elements_are_interactive(self):
		"""Test that contenteditable elements are interactive."""
		node = create_mock_node('DIV', attributes={'contenteditable': 'true'})
		simplified = EnhancedSimplifiedNode(original_node=node)

		assert simplified.is_truly_interactive()
		assert simplified.interaction_reason is not None and 'contenteditable' in simplified.interaction_reason

	def test_draggable_elements_are_interactive(self):
		"""Test that draggable elements are interactive."""
		node = create_mock_node('DIV', attributes={'draggable': 'true'})
		simplified = EnhancedSimplifiedNode(original_node=node)

		assert simplified.is_truly_interactive()
		assert simplified.interaction_reason is not None and 'draggable' in simplified.interaction_reason

	def test_elements_with_positive_tabindex_are_interactive(self):
		"""Test that elements with positive tabindex are interactive."""
		node = create_mock_node('DIV', attributes={'tabindex': '0'})
		simplified = EnhancedSimplifiedNode(original_node=node)

		assert simplified.is_truly_interactive()
		assert simplified.interaction_reason is not None and 'positive_tabindex' in simplified.interaction_reason

	def test_elements_with_negative_tabindex_are_not_interactive(self):
		"""Test that elements with negative tabindex are not interactive."""
		node = create_mock_node('DIV', attributes={'tabindex': '-1'})
		simplified = EnhancedSimplifiedNode(original_node=node)

		assert not simplified.is_truly_interactive()

	def test_pure_container_elements_are_not_interactive(self):
		"""Test that pure container elements are not interactive by default."""
		container_elements = ['HTML', 'BODY', 'MAIN', 'SECTION', 'ARTICLE', 'ASIDE', 'NAV', 'HEADER', 'FOOTER']

		for element in container_elements:
			node = create_mock_node(element)
			simplified = EnhancedSimplifiedNode(original_node=node)

			assert not simplified.is_truly_interactive(), f'{element} should not be interactive by default'

	def test_container_elements_with_onclick_are_interactive(self):
		"""Test that container elements with onclick are interactive."""
		node = create_mock_node('SECTION', attributes={'onclick': 'doSomething()'})
		simplified = EnhancedSimplifiedNode(original_node=node)

		assert simplified.is_truly_interactive()

	def test_div_without_indicators_is_not_interactive(self):
		"""Test that plain DIVs are not interactive."""
		node = create_mock_node('DIV')
		simplified = EnhancedSimplifiedNode(original_node=node)

		assert not simplified.is_truly_interactive()

	def test_span_without_indicators_is_not_interactive(self):
		"""Test that plain SPANs are not interactive."""
		node = create_mock_node('SPAN')
		simplified = EnhancedSimplifiedNode(original_node=node)

		assert not simplified.is_truly_interactive()

	def test_wrapper_detection_with_many_interactive_children(self):
		"""Test that DIVs with many interactive children are considered wrappers."""
		# Create interactive children
		interactive_children = []
		for i in range(5):
			child_node = create_mock_node('BUTTON')
			child_simplified = EnhancedSimplifiedNode(original_node=child_node)
			interactive_children.append(child_simplified)

		# Create wrapper DIV with onclick
		node = create_mock_node('DIV', attributes={'onclick': 'doSomething()'})
		simplified = EnhancedSimplifiedNode(original_node=node)
		simplified.children = interactive_children

		assert simplified._is_likely_wrapper()

	def test_wrapper_detection_with_wrapper_class(self):
		"""Test that DIVs with wrapper-like classes are considered wrappers."""
		wrapper_classes = ['container', 'wrapper', 'grid', 'layout', 'content']

		for class_name in wrapper_classes:
			node = create_mock_node('DIV', attributes={'class': class_name, 'onclick': 'doSomething()'})
			simplified = EnhancedSimplifiedNode(original_node=node)

			assert simplified._is_likely_wrapper(), f"DIV with class '{class_name}' should be detected as wrapper"

	def test_invisible_elements_are_not_visible(self):
		"""Test that invisible elements are correctly detected."""
		# Test display: none
		node = create_mock_node('BUTTON', computed_styles={'display': 'none'})
		simplified = EnhancedSimplifiedNode(original_node=node)
		assert not simplified.is_effectively_visible()

		# Test visibility: hidden
		node = create_mock_node('BUTTON', computed_styles={'visibility': 'hidden'})
		simplified = EnhancedSimplifiedNode(original_node=node)
		assert not simplified.is_effectively_visible()

		# Test opacity: 0
		node = create_mock_node('BUTTON', computed_styles={'opacity': '0'})
		simplified = EnhancedSimplifiedNode(original_node=node)
		assert not simplified.is_effectively_visible()

		# Test off-screen positioning
		node = create_mock_node('BUTTON', bounding_box={'x': -10000, 'y': 100, 'width': 50, 'height': 20})
		simplified = EnhancedSimplifiedNode(original_node=node)
		assert not simplified.is_effectively_visible()

		# Test is_visible = False
		node = create_mock_node('BUTTON', is_visible=False)
		simplified = EnhancedSimplifiedNode(original_node=node)
		assert not simplified.is_effectively_visible()

		# Test zero width/height
		node = create_mock_node('BUTTON', bounding_box={'x': 100, 'y': 100, 'width': 0, 'height': 20})
		simplified = EnhancedSimplifiedNode(original_node=node)
		assert not simplified.is_effectively_visible()

		# Test pointer-events: none
		node = create_mock_node('BUTTON', computed_styles={'pointer-events': 'none'})
		simplified = EnhancedSimplifiedNode(original_node=node)
		assert not simplified.is_effectively_visible()


class TestEnhancedDOMTreeSerializer:
	"""Test the enhanced DOM tree serializer."""

	def test_basic_interactive_elements_are_detected(self):
		"""Test that basic interactive elements are detected and numbered."""
		# Create a simple DOM with interactive elements
		button_node = create_mock_node('BUTTON')
		link_node = create_mock_node('A', attributes={'href': 'https://example.com'})
		input_node = create_mock_node('INPUT', attributes={'type': 'text'})

		root_node = create_mock_node('DIV', children=[button_node, link_node, input_node])

		serializer = EnhancedDOMTreeSerializer(root_node)
		serialized, selector_map = serializer.serialize_accessible_elements()

		# Should have 3 interactive elements
		assert len(selector_map) == 3

		# Check that each element is properly numbered
		assert '[1]<BUTTON' in serialized
		assert '[2]<A' in serialized
		assert '[3]<INPUT' in serialized

	def test_non_interactive_containers_are_filtered(self):
		"""Test that non-interactive containers are filtered out."""
		# Create interactive elements inside containers
		button_node = create_mock_node('BUTTON')
		link_node = create_mock_node('A', attributes={'href': 'https://example.com'})

		# Wrap in various containers
		section_node = create_mock_node('SECTION', children=[button_node])
		div_node = create_mock_node('DIV', children=[link_node])
		main_node = create_mock_node('MAIN', children=[section_node, div_node])

		serializer = EnhancedDOMTreeSerializer(main_node)
		serialized, selector_map = serializer.serialize_accessible_elements()

		# Should only have 2 interactive elements
		assert len(selector_map) == 2

		# Should not contain container elements
		assert 'MAIN' not in serialized
		assert 'SECTION' not in serialized
		assert 'DIV' not in serialized

		# Should contain interactive elements
		assert '[1]<BUTTON' in serialized
		assert '[2]<A' in serialized

	def test_calendar_like_structure_filters_container(self):
		"""Test that calendar-like structures filter out the container."""
		# Create many date buttons (like a calendar)
		date_buttons = []
		for i in range(15):  # Many buttons like a calendar
			button_node = create_mock_node('BUTTON', attributes={'data-date': f'2024-01-{i + 1:02d}'})
			date_buttons.append(button_node)

		# Wrap in calendar container
		calendar_div = create_mock_node('DIV', attributes={'class': 'calendar-grid'}, children=date_buttons)

		serializer = EnhancedDOMTreeSerializer(calendar_div)
		serialized, selector_map = serializer.serialize_accessible_elements()

		# Should have 15 interactive date buttons
		assert len(selector_map) == 15

		# Should not contain the calendar container itself
		assert 'calendar-grid' not in serialized

		# Should contain numbered buttons
		assert '[1]<BUTTON' in serialized
		assert '[15]<BUTTON' in serialized

	def test_form_structure_is_preserved(self):
		"""Test that form structures are preserved while filtering containers."""
		# Create form elements
		name_input = create_mock_node('INPUT', attributes={'type': 'text', 'name': 'name'})
		email_input = create_mock_node('INPUT', attributes={'type': 'email', 'name': 'email'})
		submit_button = create_mock_node('BUTTON', attributes={'type': 'submit'})

		# Wrap in form and fieldset
		fieldset_node = create_mock_node('FIELDSET', children=[name_input, email_input])
		form_node = create_mock_node('FORM', children=[fieldset_node, submit_button])

		serializer = EnhancedDOMTreeSerializer(form_node)
		serialized, selector_map = serializer.serialize_accessible_elements()

		# Should have 3 interactive elements
		assert len(selector_map) == 3

		# Should preserve form structure
		assert '<FORM' in serialized
		assert '<FIELDSET' in serialized

		# Should contain interactive elements
		assert '[1]<INPUT' in serialized
		assert '[2]<INPUT' in serialized
		assert '[3]<BUTTON' in serialized

	def test_mixed_interactive_and_container_elements(self):
		"""Test complex structures with mixed interactive and container elements."""
		# Create a complex structure
		nav_link = create_mock_node('A', attributes={'href': '/about'})
		nav_div = create_mock_node('DIV', children=[nav_link])  # Should be filtered

		search_input = create_mock_node('INPUT', attributes={'type': 'search'})
		search_button = create_mock_node('BUTTON')
		search_form = create_mock_node('FORM', children=[search_input, search_button])  # Should be preserved

		content_button = create_mock_node('BUTTON', attributes={'data-action': 'expand'})
		content_section = create_mock_node('SECTION', children=[content_button])  # Should be filtered

		root_node = create_mock_node('DIV', children=[nav_div, search_form, content_section])

		serializer = EnhancedDOMTreeSerializer(root_node)
		serialized, selector_map = serializer.serialize_accessible_elements()

		# Should have 4 interactive elements
		assert len(selector_map) == 4

		# Should contain form structure
		assert '<FORM' in serialized

		# Should not contain non-interactive containers
		assert 'nav_div' not in serialized
		assert 'SECTION' not in serialized

		# Should contain interactive elements
		assert '[1]<A' in serialized  # nav link
		assert '[2]<INPUT' in serialized  # search input
		assert '[3]<BUTTON' in serialized  # search button
		assert '[4]<BUTTON' in serialized  # content button

	def test_wrapper_consolidation(self):
		"""Test that wrapper DIVs with interactive children are consolidated."""
		# Create button inside wrapper DIV
		button_node = create_mock_node('BUTTON')
		wrapper_div = create_mock_node('DIV', attributes={'class': 'wrapper'}, children=[button_node])

		serializer = EnhancedDOMTreeSerializer(wrapper_div)
		serialized, selector_map = serializer.serialize_accessible_elements()

		# Should have 1 interactive element
		assert len(selector_map) == 1

		# Should not show wrapper DIV
		assert 'wrapper' not in serialized

		# Should show button
		assert '[1]<BUTTON' in serialized

	def test_debug_info_is_helpful(self):
		"""Test that debug information is helpful for understanding decisions."""
		# Create elements with different interaction reasons
		button_node = create_mock_node('BUTTON')
		pointer_div = create_mock_node('DIV', cursor_style='pointer')
		onclick_span = create_mock_node('SPAN', attributes={'onclick': 'doSomething()'})

		# Create container with many children
		container_children = [create_mock_node('BUTTON') for _ in range(6)]
		container_div = create_mock_node('DIV', attributes={'class': 'container'}, children=container_children)

		root_node = create_mock_node('DIV', children=[button_node, pointer_div, onclick_span, container_div])

		serializer = EnhancedDOMTreeSerializer(root_node)
		serialized, selector_map = serializer.serialize_accessible_elements()

		debug_info = serializer.get_debug_info()

		# Should have helpful debug messages
		assert any('pure container' in msg for msg in debug_info)
		assert any('form_element' in msg for msg in debug_info)
		assert any('pointer_cursor' in msg for msg in debug_info)
		assert any('explicit_handlers' in msg for msg in debug_info)

	def test_scrollable_elements_are_preserved(self):
		"""Test that scrollable elements are preserved even if not interactive."""
		scrollable_div = create_mock_node('DIV', is_scrollable=True)

		serializer = EnhancedDOMTreeSerializer(scrollable_div)
		serialized, selector_map = serializer.serialize_accessible_elements()

		# Should show scrollable element
		assert '[SCROLL]<DIV' in serialized

	def test_text_content_is_included(self):
		"""Test that meaningful text content is included."""
		text_node = create_mock_node('text', NodeType.TEXT_NODE, node_value='Click here to continue')
		button_node = create_mock_node('BUTTON', children=[text_node])

		serializer = EnhancedDOMTreeSerializer(button_node)
		serialized, selector_map = serializer.serialize_accessible_elements()

		# Should contain text content
		assert 'Click here to continue' in serialized

	def test_integration_function_works(self):
		"""Test that the integration function works correctly."""
		button_node = create_mock_node('BUTTON')
		root_node = create_mock_node('DIV', children=[button_node])

		serialized, selector_map = serialize_with_enhanced_filtering(root_node)

		# Should work the same as direct serializer usage
		assert len(selector_map) == 1
		assert '[1]<BUTTON' in serialized

	def test_attributes_are_included_appropriately(self):
		"""Test that important attributes are included in output."""
		button_node = create_mock_node(
			'BUTTON',
			attributes={'type': 'submit', 'class': 'btn btn-primary', 'data-action': 'submit', 'onclick': 'submitForm()'},
		)

		serializer = EnhancedDOMTreeSerializer(button_node)
		serialized, selector_map = serializer.serialize_accessible_elements(['class'])

		# Should include important attributes
		assert 'type="submit"' in serialized
		assert 'class="btn btn-primary"' in serialized
		assert 'data-action="submit"' in serialized

	def test_empty_dom_tree_handled_gracefully(self):
		"""Test that empty DOM trees are handled gracefully."""
		empty_node = create_mock_node('DIV')

		serializer = EnhancedDOMTreeSerializer(empty_node)
		serialized, selector_map = serializer.serialize_accessible_elements()

		# Should return empty results
		assert len(selector_map) == 0
		assert serialized == ''

	def test_deeply_nested_structure(self):
		"""Test that deeply nested structures are handled correctly."""
		# Create deeply nested structure
		button_node = create_mock_node('BUTTON')
		level3_div = create_mock_node('DIV', children=[button_node])
		level2_section = create_mock_node('SECTION', children=[level3_div])
		level1_main = create_mock_node('MAIN', children=[level2_section])
		root_div = create_mock_node('DIV', children=[level1_main])

		serializer = EnhancedDOMTreeSerializer(root_div)
		serialized, selector_map = serializer.serialize_accessible_elements()

		# Should find the button despite deep nesting
		assert len(selector_map) == 1
		assert '[1]<BUTTON' in serialized

		# Should not show container elements
		assert 'MAIN' not in serialized
		assert 'SECTION' not in serialized


def test_real_world_scenario_e_commerce_page():
	"""Test a real-world scenario: e-commerce product page."""
	# Create product page structure

	# Navigation
	nav_link1 = create_mock_node('A', attributes={'href': '/home'})
	nav_link2 = create_mock_node('A', attributes={'href': '/products'})
	nav_div = create_mock_node('NAV', children=[nav_link1, nav_link2])

	# Product details
	add_to_cart_button = create_mock_node('BUTTON', attributes={'data-action': 'add-to-cart'})
	quantity_input = create_mock_node('INPUT', attributes={'type': 'number', 'value': '1'})

	# Reviews section
	review_buttons = [create_mock_node('BUTTON', attributes={'data-rating': str(i)}) for i in range(1, 6)]
	review_div = create_mock_node('DIV', attributes={'class': 'review-stars'}, children=review_buttons)

	# Related products (many product cards)
	related_products = [create_mock_node('A', attributes={'href': f'/product/{i}'}) for i in range(1, 8)]
	related_div = create_mock_node('DIV', attributes={'class': 'related-products'}, children=related_products)

	# Assemble page
	root_node = create_mock_node('DIV', children=[nav_div, add_to_cart_button, quantity_input, review_div, related_div])

	serializer = EnhancedDOMTreeSerializer(root_node)
	serialized, selector_map = serializer.serialize_accessible_elements()

	# Should detect:
	# - 2 navigation links
	# - 1 add to cart button
	# - 1 quantity input
	# - 5 review buttons
	# - 7 related product links
	# Total: 16 interactive elements
	assert len(selector_map) == 16

	# Should not show container divs (enhanced filtering behavior)
	assert 'related-products' not in serialized
	assert 'review-stars' not in serialized
	assert 'NAV' not in serialized  # NAV is filtered out as non-interactive container

	# Should show all interactive elements
	assert '[1]<A' in serialized
	assert '[16]<A' in serialized


def test_real_world_scenario_calendar_widget():
	"""Test a real-world scenario: calendar widget."""
	# Create calendar structure

	# Navigation buttons
	prev_button = create_mock_node('BUTTON', attributes={'data-action': 'prev-month'})
	next_button = create_mock_node('BUTTON', attributes={'data-action': 'next-month'})
	nav_div = create_mock_node('DIV', attributes={'class': 'calendar-nav'}, children=[prev_button, next_button])

	# Date buttons (30 days)
	date_buttons = []
	for day in range(1, 31):
		button = create_mock_node('BUTTON', attributes={'data-date': f'2024-01-{day:02d}'})
		date_buttons.append(button)

	calendar_grid = create_mock_node('DIV', attributes={'class': 'calendar-grid'}, children=date_buttons)

	# Assemble calendar
	calendar_widget = create_mock_node('DIV', attributes={'class': 'calendar-widget'}, children=[nav_div, calendar_grid])

	serializer = EnhancedDOMTreeSerializer(calendar_widget)
	serialized, selector_map = serializer.serialize_accessible_elements()

	# Should detect:
	# - 2 navigation buttons
	# - 30 date buttons
	# Total: 32 interactive elements
	assert len(selector_map) == 32

	# Should not show container divs (enhanced filtering behavior)
	assert 'calendar-widget' not in serialized
	assert 'calendar-nav' not in serialized
	assert 'calendar-grid' not in serialized

	# Should show all buttons
	assert '[1]<BUTTON' in serialized
	assert '[32]<BUTTON' in serialized


if __name__ == '__main__':
	pytest.main([__file__, '-v'])
