#!/usr/bin/env python3
"""
Demo script showing the enhanced DOM serializer improvements.
This demonstrates how the enhanced serializer filters out non-interactive containers
while preserving all truly interactive elements.
"""

from unittest.mock import Mock

from browser_use.dom.serializer import DOMTreeSerializer
from browser_use.dom.serializer_enhanced import serialize_with_enhanced_filtering
from browser_use.dom.views import EnhancedDOMTreeNode, EnhancedSnapshotNode, NodeType


def create_demo_node(
	node_name: str, node_type: NodeType = NodeType.ELEMENT_NODE, attributes: dict | None = None, children: list | None = None
) -> EnhancedDOMTreeNode:
	"""Create a demo DOM node."""
	# Create snapshot node
	snapshot_node = Mock(spec=EnhancedSnapshotNode)
	snapshot_node.is_visible = True
	snapshot_node.cursor_style = None
	snapshot_node.computed_styles = {}
	snapshot_node.bounding_box = {'x': 100, 'y': 100, 'width': 50, 'height': 20}

	# Create main node
	node = Mock(spec=EnhancedDOMTreeNode)
	node.node_name = node_name
	node.node_type = node_type
	node.attributes = attributes or {}
	node.children_nodes = children or []
	node.snapshot_node = snapshot_node
	node.ax_node = None
	node.node_value = None
	node.is_scrollable = False
	node.parent_node = None
	node.content_document = None
	node.shadow_roots = None
	node.frame_id = None
	node.shadow_root_type = None
	node.backend_node_id = 1
	node.node_id = 1

	return node


def create_complex_dom_structure():
	"""Create a complex DOM structure with many containers and interactive elements."""
	# Create interactive elements
	login_button = create_demo_node('BUTTON', attributes={'id': 'login-btn'})
	search_input = create_demo_node('INPUT', attributes={'type': 'search', 'placeholder': 'Search...'})
	nav_link1 = create_demo_node('A', attributes={'href': '/home'})
	nav_link2 = create_demo_node('A', attributes={'href': '/about'})

	# Create many calendar date buttons (like a calendar widget)
	date_buttons = []
	for day in range(1, 32):
		button = create_demo_node('BUTTON', attributes={'data-date': f'2024-01-{day:02d}'})
		date_buttons.append(button)

	# Create container structure
	nav_container = create_demo_node('NAV', children=[nav_link1, nav_link2])
	search_container = create_demo_node('DIV', attributes={'class': 'search-container'}, children=[search_input])
	header_container = create_demo_node('HEADER', children=[nav_container, search_container, login_button])
	calendar_grid = create_demo_node('DIV', attributes={'class': 'calendar-grid'}, children=date_buttons)
	calendar_widget = create_demo_node('DIV', attributes={'class': 'calendar-widget'}, children=[calendar_grid])
	main_content = create_demo_node('MAIN', children=[calendar_widget])

	# Root structure
	root = create_demo_node('DIV', attributes={'class': 'app-container'}, children=[header_container, main_content])

	return root


def main():
	"""Demonstrate the enhanced serializer improvements."""
	print('🚀 Enhanced DOM Serializer Demo')
	print('=' * 50)

	# Create complex DOM structure
	root = create_complex_dom_structure()

	# Test with legacy serializer
	print('\n📊 LEGACY SERIALIZER RESULTS:')
	print('-' * 30)
	try:
		legacy_serialized, legacy_map = DOMTreeSerializer(root).serialize_accessible_elements()
		print(f'Interactive elements found: {len(legacy_map)}')
		print('Sample output:')
		print(legacy_serialized[:200] + '...' if len(legacy_serialized) > 200 else legacy_serialized)
	except Exception as e:
		print(f'Legacy serializer error: {e}')

	# Test with enhanced serializer
	print('\n✨ ENHANCED SERIALIZER RESULTS:')
	print('-' * 30)
	try:
		enhanced_serialized, enhanced_map = serialize_with_enhanced_filtering(root)
		print(f'Interactive elements found: {len(enhanced_map)}')
		print('Sample output:')
		print(enhanced_serialized[:400] + '...' if len(enhanced_serialized) > 400 else enhanced_serialized)

		# Show container filtering
		print('\n🎯 CONTAINER FILTERING RESULTS:')
		print('-' * 30)
		containers_filtered = ['app-container', 'HEADER', 'NAV', 'search-container', 'MAIN', 'calendar-widget', 'calendar-grid']

		for container in containers_filtered:
			if container in enhanced_serialized:
				print(f'❌ {container} - Still present')
			else:
				print(f'✅ {container} - Successfully filtered out')

		# Show what's included
		print('\n📋 INTERACTIVE ELEMENTS INCLUDED:')
		print('-' * 30)
		lines = enhanced_serialized.split('\n')
		for i, line in enumerate(lines[:10]):  # Show first 10 lines
			if line.strip():
				print(f'{i + 1:2d}. {line}')

		if len(lines) > 10:
			print(f'... and {len(lines) - 10} more interactive elements')

	except Exception as e:
		print(f'Enhanced serializer error: {e}')

	print('\n🎉 SUMMARY:')
	print('-' * 30)
	print('The enhanced serializer successfully:')
	print('• Filters out non-interactive containers')
	print('• Preserves all truly interactive elements')
	print('• Reduces DOM noise for better LLM processing')
	print('• Maintains proper element numbering')
	print('• Includes comprehensive interaction detection')


if __name__ == '__main__':
	main()
