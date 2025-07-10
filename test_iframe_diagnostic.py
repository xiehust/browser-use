#!/usr/bin/env python3
"""
Diagnostic test to debug iframe content extraction issues.
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


async def diagnose_iframe_extraction():
	"""Diagnose iframe content extraction step by step."""

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
		print('🔍 IFRAME DIAGNOSTIC TEST')
		print('=' * 80)

		# Step 1: Get raw DOM tree
		print('\n📋 Step 1: Getting enhanced DOM tree...')
		enhanced_dom_tree = await dom_service.get_dom_tree()

		# Step 2: Analyze the DOM tree structure recursively
		print('\n🌳 Step 2: Analyzing DOM tree structure...')

		def analyze_dom_node(node, depth=0, path=''):
			indent = '  ' * depth
			node_info = f'{indent}{node.node_name}'

			if node.attributes:
				if 'id' in node.attributes:
					node_info += f" id='{node.attributes['id']}'"
				if 'placeholder' in node.attributes:
					node_info += f" placeholder='{node.attributes['placeholder']}'"
				if 'src' in node.attributes and node.node_name.upper() == 'IFRAME':
					src = node.attributes['src'][:50] + '...' if len(node.attributes['src']) > 50 else node.attributes['src']
					node_info += f" src='{src}'"

			# Check if this node has content_document (iframe content)
			if hasattr(node, 'content_document') and node.content_document:
				node_info += ' [HAS IFRAME CONTENT]'

			# Check if this node has shadow roots
			if hasattr(node, 'shadow_roots') and node.shadow_roots:
				node_info += f' [HAS {len(node.shadow_roots)} SHADOW ROOTS]'

			print(node_info)

			# Recursively analyze children
			if hasattr(node, 'children_nodes') and node.children_nodes:
				for child in node.children_nodes:
					analyze_dom_node(child, depth + 1, path + f'/{node.node_name}')

			# Analyze iframe content
			if hasattr(node, 'content_document') and node.content_document:
				print(f'{indent}  📄 IFRAME CONTENT:')
				analyze_dom_node(node.content_document, depth + 2, path + f'/{node.node_name}/iframe')

			# Analyze shadow roots
			if hasattr(node, 'shadow_roots') and node.shadow_roots:
				for i, shadow_root in enumerate(node.shadow_roots):
					print(f'{indent}  🌑 SHADOW ROOT {i}:')
					analyze_dom_node(shadow_root, depth + 2, path + f'/{node.node_name}/shadow{i}')

		analyze_dom_node(enhanced_dom_tree)

		# Step 3: Get serialized output
		print('\n📝 Step 3: Getting serialized output...')
		serialized, selector_map = await dom_service.get_serialized_dom_tree(filter_mode='comprehensive')

		print('\n📊 Results:')
		print(f'  - Total interactive elements: {len(selector_map)}')
		print(f'  - Serialized output length: {len(serialized)} characters')

		# Step 4: Analyze selector map
		print('\n🎯 Step 4: Analyzing selector map...')
		print('Interactive elements found:')

		for idx, node in selector_map.items():
			node_desc = f'[{idx}] {node.node_name.upper()}'
			if node.attributes:
				if 'id' in node.attributes:
					node_desc += f" id='{node.attributes['id']}'"
				if 'placeholder' in node.attributes:
					node_desc += f" placeholder='{node.attributes['placeholder']}'"
				if 'onclick' in node.attributes:
					onclick = (
						node.attributes['onclick'][:30] + '...'
						if len(node.attributes['onclick']) > 30
						else node.attributes['onclick']
					)
					node_desc += f" onclick='{onclick}'"
			print(f'  {node_desc}')

		# Step 5: Check iframe context information
		print('\n🖼️ Step 5: Checking iframe contexts...')

		# Access the serializer to check iframe contexts
		from browser_use.dom.serializer import DOMTreeSerializer

		serializer = DOMTreeSerializer(enhanced_dom_tree)

		# Manually serialize to get iframe contexts
		serialized_manual, selector_map_manual = serializer.serialize_accessible_elements(filter_mode='comprehensive')

		print(f'Iframe contexts detected: {len(serializer._iframe_contexts)}')
		for context_id, info in serializer._iframe_contexts.items():
			print(f'  - {context_id}: {info.iframe_xpath}')
			print(f'    src: {info.iframe_src}')
			print(f'    cross-origin: {info.is_cross_origin}')

		print(f'Cross-origin iframes: {len(serializer._cross_origin_iframes)}')
		for iframe_url in serializer._cross_origin_iframes:
			print(f'  - {iframe_url}')

		# Show a portion of the serialized output
		print('\n📄 Serialized output (first 1000 chars):')
		print(serialized[:1000])
		if len(serialized) > 1000:
			print('...[TRUNCATED]')

		print('\n✅ Diagnostic test completed!')

	except Exception as e:
		print(f'❌ Error during diagnostic test: {e}')
		import traceback

		traceback.print_exc()
	finally:
		await browser_session.stop()


if __name__ == '__main__':
	asyncio.run(diagnose_iframe_extraction())
