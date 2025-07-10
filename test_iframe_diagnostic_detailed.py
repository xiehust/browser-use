#!/usr/bin/env python3
"""
Detailed diagnostic test to examine raw CDP data for iframe content.
"""

import asyncio
import tempfile
from pathlib import Path

from browser_use.browser.profile import BrowserProfile
from browser_use.browser.session import BrowserSession
from browser_use.dom.service import DOMService


async def create_simple_iframe_test():
	"""Create a simple test page with iframe content."""
	html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Simple Iframe Test</title>
</head>
<body>
    <h1>Main Page</h1>
    <button onclick="alert('main button')">Main Button</button>
    
    <h2>Iframe Content Below:</h2>
    <iframe src="data:text/html,
        <html>
        <body style='padding: 20px; font-family: Arial;'>
            <h3>Inside Iframe</h3>
            <button onclick='alert(\"iframe button\")'>Iframe Button</button>
            <input type='text' placeholder='Name' id='nameInput'>
            <input type='email' placeholder='Email' id='emailInput'>
            <button type='submit'>Submit Form</button>
        </body>
        </html>
    " width="400" height="200"></iframe>
    
    <button onclick="alert('after iframe')">After Iframe Button</button>
</body>
</html>
    """

	# Create temporary HTML file
	temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8')
	temp_file.write(html_content)
	temp_file.close()

	return Path(temp_file.name).as_uri()


async def diagnose_cdp_data():
	"""Diagnose CDP data to understand iframe content capture."""

	# Create browser session
	profile = BrowserProfile(headless=False, keep_alive=True)
	browser_session = BrowserSession(browser_profile=profile)

	try:
		await browser_session.start()

		# Create and navigate to simple test page
		test_url = await create_simple_iframe_test()
		print(f'🌐 Created test page: {test_url}')

		await browser_session.navigate_to(test_url)
		await asyncio.sleep(3)  # Wait for page to load completely

		# Create DOM service
		dom_service = DOMService(browser_session)

		print('\n' + '=' * 80)
		print('🔍 DETAILED CDP DATA ANALYSIS')
		print('=' * 80)

		# Step 1: Get raw CDP data
		print('\n📋 Step 1: Getting raw CDP data...')
		snapshot, dom_tree, ax_tree = await dom_service._get_all_trees()

		# Step 2: Analyze snapshot documents
		print('\n📄 Step 2: Analyzing snapshot documents...')
		documents = snapshot.get('documents', [])
		print(f'Found {len(documents)} documents in snapshot:')

		for i, doc in enumerate(documents):
			url = doc.get('documentURL', 'NO_URL')
			print(f'  Document {i}: {url}')

			# Check for nodes in this document
			if 'nodes' in snapshot and 'documentIndex' in snapshot['nodes']:
				doc_nodes = [idx for idx, doc_idx in enumerate(snapshot['nodes']['documentIndex']) if doc_idx == i]
				print(f'    Nodes in this document: {len(doc_nodes)}')

				# Show some sample nodes
				if doc_nodes and 'nodeName' in snapshot['nodes']:
					for j, node_idx in enumerate(doc_nodes[:10]):  # Show first 10 nodes
						node_name = (
							snapshot['nodes']['nodeName'][node_idx]
							if node_idx < len(snapshot['nodes']['nodeName'])
							else 'UNKNOWN'
						)
						print(f'      Node {j}: {node_name}')
					if len(doc_nodes) > 10:
						print(f'      ... and {len(doc_nodes) - 10} more nodes')

		# Step 3: Analyze DOM tree structure
		print('\n🌳 Step 3: Analyzing DOM tree structure...')

		def analyze_dom_tree_detailed(node, depth=0, path='', doc_context='main'):
			indent = '  ' * depth
			node_info = f'{indent}[{doc_context}] {node.get("nodeName", "UNKNOWN")}'

			# Add attributes info
			if 'attributes' in node and node['attributes']:
				attrs = []
				for i in range(0, len(node['attributes']), 2):
					if i + 1 < len(node['attributes']):
						key = node['attributes'][i]
						value = node['attributes'][i + 1]
						if key in ['id', 'placeholder', 'type', 'onclick']:
							if len(value) > 30:
								value = value[:27] + '...'
							attrs.append(f'{key}="{value}"')
						elif key == 'src' and len(value) > 50:
							attrs.append(f'src="{value[:47]}..."')

				if attrs:
					node_info += f' {" ".join(attrs)}'

			# Check node type and IDs
			node_info += f' (nodeId: {node.get("nodeId", "N/A")}, backendId: {node.get("backendNodeId", "N/A")})'

			print(node_info)

			# Recursively analyze children
			if 'children' in node and node['children']:
				for child in node['children']:
					analyze_dom_tree_detailed(child, depth + 1, path + f'/{node.get("nodeName", "UNKNOWN")}', doc_context)

			# Analyze content document (iframe content)
			if 'contentDocument' in node and node['contentDocument']:
				print(f'{indent}  📄 IFRAME CONTENT DOCUMENT:')
				analyze_dom_tree_detailed(
					node['contentDocument'], depth + 2, path + f'/{node.get("nodeName", "UNKNOWN")}/iframe', 'iframe'
				)

			# Analyze shadow roots
			if 'shadowRoots' in node and node['shadowRoots']:
				for i, shadow_root in enumerate(node['shadowRoots']):
					print(f'{indent}  🌑 SHADOW ROOT {i}:')
					analyze_dom_tree_detailed(
						shadow_root, depth + 2, path + f'/{node.get("nodeName", "UNKNOWN")}/shadow{i}', f'shadow{i}'
					)

		analyze_dom_tree_detailed(dom_tree['root'])

		# Step 4: Check accessibility tree
		print('\n♿ Step 4: Analyzing accessibility tree...')
		ax_nodes = ax_tree.get('nodes', [])
		print(f'Found {len(ax_nodes)} accessibility nodes')

		# Look for iframe-related nodes
		iframe_ax_nodes = []
		for ax_node in ax_nodes:
			if 'role' in ax_node and ax_node['role'].get('value', '') == 'iframe':
				iframe_ax_nodes.append(ax_node)
			elif 'name' in ax_node and 'iframe' in str(ax_node['name'].get('value', '')).lower():
				iframe_ax_nodes.append(ax_node)

		print(f'Found {len(iframe_ax_nodes)} iframe-related accessibility nodes')
		for ax_node in iframe_ax_nodes:
			role = ax_node.get('role', {}).get('value', 'UNKNOWN')
			name = ax_node.get('name', {}).get('value', 'NO_NAME')
			print(f'  AX Node: role={role}, name={name}')

		# Step 5: Build enhanced DOM tree and analyze
		print('\n🏗️ Step 5: Building enhanced DOM tree...')
		enhanced_dom_tree = await dom_service._build_enhanced_dom_tree(dom_tree, ax_tree, snapshot)

		def count_nodes_recursive(node):
			count = 1
			if hasattr(node, 'children_nodes') and node.children_nodes:
				for child in node.children_nodes:
					count += count_nodes_recursive(child)
			if hasattr(node, 'content_document') and node.content_document:
				count += count_nodes_recursive(node.content_document)
			if hasattr(node, 'shadow_roots') and node.shadow_roots:
				for shadow_root in node.shadow_roots:
					count += count_nodes_recursive(shadow_root)
			return count

		total_enhanced_nodes = count_nodes_recursive(enhanced_dom_tree)
		print(f'Enhanced DOM tree contains {total_enhanced_nodes} total nodes')

		# Step 6: Test serialization
		print('\n📝 Step 6: Testing serialization...')
		from browser_use.dom.serializer import DOMTreeSerializer

		serializer = DOMTreeSerializer(enhanced_dom_tree)
		serialized, selector_map = serializer.serialize_accessible_elements(filter_mode='comprehensive')

		print('Serialization results:')
		print(f'  - Interactive elements found: {len(selector_map)}')
		print(f'  - Serialized length: {len(serialized)} characters')
		print(f'  - Iframe contexts: {len(serializer._iframe_contexts)}')

		# Show detailed selector map
		print('\n🎯 Detailed selector map:')
		for idx, node in selector_map.items():
			node_desc = f'[{idx}] {node.node_name.upper()}'
			if node.attributes:
				relevant_attrs = []
				for attr in ['id', 'placeholder', 'type', 'onclick']:
					if attr in node.attributes:
						value = node.attributes[attr]
						if len(value) > 30:
							value = value[:27] + '...'
						relevant_attrs.append(f'{attr}="{value}"')
				if relevant_attrs:
					node_desc += f' {" ".join(relevant_attrs)}'
			print(f'  {node_desc}')

		# Show first part of serialized output
		print('\n📄 Serialized output (first 1500 characters):')
		print(serialized[:1500])
		if len(serialized) > 1500:
			print('...[TRUNCATED]')

		print('\n✅ Detailed diagnostic test completed!')

	except Exception as e:
		print(f'❌ Error during detailed diagnostic test: {e}')
		import traceback

		traceback.print_exc()
	finally:
		await browser_session.stop()


if __name__ == '__main__':
	asyncio.run(diagnose_cdp_data())
