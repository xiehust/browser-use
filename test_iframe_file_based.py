#!/usr/bin/env python3
"""
Test script using a file-based iframe instead of data URI to test iframe content extraction.
"""

import asyncio
import tempfile
from pathlib import Path

from browser_use.browser.profile import BrowserProfile
from browser_use.browser.session import BrowserSession
from browser_use.dom.service import DOMService


async def create_iframe_files():
	"""Create main HTML file and separate iframe HTML file."""

	# Create iframe content file
	iframe_content = """<!DOCTYPE html>
<html>
<head>
    <title>Iframe Content</title>
    <style>
        body { 
            padding: 20px; 
            font-family: Arial, sans-serif; 
            background: #f9f9f9;
        }
        .form-group { 
            margin: 10px 0; 
        }
        button { 
            background: #007bff; 
            color: white; 
            border: none; 
            padding: 10px 15px; 
            cursor: pointer; 
            margin: 5px;
        }
        input { 
            padding: 8px; 
            border: 1px solid #ccc; 
            border-radius: 4px; 
            width: 200px;
        }
    </style>
</head>
<body>
    <h3>Inside Iframe Content</h3>
    <div class="form-group">
        <button onclick="alert('iframe button clicked!')">Iframe Button</button>
    </div>
    <div class="form-group">
        <input type="text" placeholder="Enter your name" id="nameInput">
    </div>
    <div class="form-group">
        <input type="email" placeholder="Enter your email" id="emailInput">
    </div>
    <div class="form-group">
        <button type="submit" onclick="alert('form submitted!')">Submit Form</button>
    </div>
    <div class="form-group">
        <select id="countrySelect">
            <option value="">Select Country</option>
            <option value="us">United States</option>
            <option value="uk">United Kingdom</option>
            <option value="ca">Canada</option>
        </select>
    </div>
    <div class="form-group">
        <textarea placeholder="Additional comments..." id="commentsArea" rows="3" cols="30"></textarea>
    </div>
</body>
</html>"""

	# Create iframe file
	iframe_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8')
	iframe_file.write(iframe_content)
	iframe_file.close()
	iframe_path = Path(iframe_file.name)

	# Create main HTML file that references the iframe file
	main_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>File-Based Iframe Test</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            padding: 20px;
            background: #ffffff;
        }}
        .container {{ 
            max-width: 800px; 
            margin: 0 auto; 
        }}
        iframe {{ 
            width: 100%; 
            height: 400px; 
            border: 2px solid #007bff; 
            border-radius: 8px;
            background: white;
        }}
        .main-button {{ 
            background: #28a745; 
            color: white; 
            border: none; 
            padding: 12px 20px; 
            cursor: pointer; 
            margin: 10px 5px;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Main Page Content</h1>
        <button class="main-button" onclick="alert('main page button')">Main Page Button</button>
        
        <h2>Iframe Content Section:</h2>
        <iframe src="file://{iframe_path.as_posix()}" title="Test Iframe Content"></iframe>
        
        <h2>After Iframe Section:</h2>
        <button class="main-button" onclick="alert('after iframe button')">After Iframe Button</button>
        
        <div style="margin-top: 20px;">
            <input type="text" placeholder="Main page input" id="mainInput">
            <button class="main-button" onclick="alert('main input: ' + document.getElementById('mainInput').value)">
                Use Main Input
            </button>
        </div>
    </div>
</body>
</html>"""

	# Create main file
	main_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8')
	main_file.write(main_content)
	main_file.close()
	main_path = Path(main_file.name)

	return main_path.as_uri(), iframe_path.as_uri()


async def test_file_based_iframe():
	"""Test iframe content extraction with file-based iframe."""

	# Create browser session
	profile = BrowserProfile(headless=False, keep_alive=True)
	browser_session = BrowserSession(browser_profile=profile)

	try:
		await browser_session.start()

		# Create test files
		main_url, iframe_url = await create_iframe_files()
		print(f'🌐 Created main page: {main_url}')
		print(f'📄 Created iframe page: {iframe_url}')

		await browser_session.navigate_to(main_url)
		await asyncio.sleep(4)  # Wait for page and iframe to load completely

		# Create DOM service
		dom_service = DOMService(browser_session)

		print('\n' + '=' * 80)
		print('🧪 FILE-BASED IFRAME TEST')
		print('=' * 80)

		# Test DOM extraction
		print('\n📝 Testing DOM extraction...')
		serialized, selector_map = await dom_service.get_serialized_dom_tree(filter_mode='comprehensive')

		print('\n📊 Results:')
		print(f'  - Total interactive elements: {len(selector_map)}')
		print(f'  - Serialized output length: {len(serialized)} characters')

		# Analyze results
		print('\n🎯 Interactive elements found:')
		main_elements = 0
		iframe_elements = 0

		for idx, node in selector_map.items():
			node_desc = f'[{idx}] {node.node_name.upper()}'
			if node.attributes:
				relevant_attrs = []
				for attr in ['id', 'placeholder', 'type', 'onclick', 'title']:
					if attr in node.attributes:
						value = node.attributes[attr]
						if len(value) > 30:
							value = value[:27] + '...'
						relevant_attrs.append(f'{attr}="{value}"')
				if relevant_attrs:
					node_desc += f' {" ".join(relevant_attrs)}'

			# Try to determine if this is from iframe
			is_iframe_element = False
			if hasattr(node, 'frame_id') and node.frame_id:
				is_iframe_element = True
				iframe_elements += 1
			else:
				main_elements += 1

			context = '[IFRAME]' if is_iframe_element else '[MAIN]'
			print(f'  {context} {node_desc}')

		print('\n📈 Element Breakdown:')
		print(f'  - Main page elements: {main_elements}')
		print(f'  - Iframe elements: {iframe_elements}')
		print(f'  - Total elements: {len(selector_map)}')

		# Show serialized output
		print('\n📄 Serialized output (first 2000 characters):')
		print(serialized[:2000])
		if len(serialized) > 2000:
			print('...[TRUNCATED]')

		# Test expectations
		expected_elements = 8  # 3 main + 5 iframe (2 buttons + 2 inputs + 1 select + 1 textarea)
		if len(selector_map) >= expected_elements:
			print(f'\n✅ SUCCESS: Found {len(selector_map)} elements (expected ~{expected_elements})')
			if iframe_elements > 0:
				print(f'✅ IFRAME SUCCESS: Found {iframe_elements} iframe elements')
			else:
				print('⚠️ IFRAME ISSUE: No iframe elements detected')
		else:
			print(f'\n❌ ISSUE: Found {len(selector_map)} elements (expected ~{expected_elements})')
			print(f'Missing {expected_elements - len(selector_map)} elements')

		print('\n✅ File-based iframe test completed!')

	except Exception as e:
		print(f'❌ Error during file-based iframe test: {e}')
		import traceback

		traceback.print_exc()
	finally:
		await browser_session.stop()


if __name__ == '__main__':
	asyncio.run(test_file_based_iframe())
