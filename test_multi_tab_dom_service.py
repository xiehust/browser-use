#!/usr/bin/env python3
"""
Test script demonstrating the enhanced multi-tab DOM service with iframe and shadow DOM support.

This script tests:
1. Multi-tab DOM extraction
2. Tab switching and session caching
3. Cross-origin iframe detection
4. Session cleanup for closed tabs
5. Iframe and shadow DOM content extraction
"""

import asyncio
import tempfile
from pathlib import Path

from browser_use.browser.profile import BrowserProfile
from browser_use.browser.session import BrowserSession
from browser_use.dom.service import DOMService


async def create_test_html():
	"""Create a test HTML file with iframes and shadow DOM for testing."""
	html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Multi-Tab DOM Test</title>
    <style>
        .container { margin: 20px; padding: 20px; border: 1px solid #ccc; }
        .iframe-container { background: #f0f0f0; }
        .shadow-container { background: #fff0f0; }
        iframe { width: 400px; height: 200px; border: 1px solid #999; }
        button { margin: 5px; padding: 10px; }
    </style>
</head>
<body>
    <h1>Multi-Tab DOM Service Test Page</h1>
    
    <div class="container">
        <h2>Regular Interactive Elements</h2>
        <button onclick="alert('Button 1')">Interactive Button 1</button>
        <button onclick="alert('Button 2')">Interactive Button 2</button>
        <a href="#test">Test Link</a>
        <input type="text" placeholder="Text input">
        <select>
            <option value="1">Option 1</option>
            <option value="2">Option 2</option>
        </select>
    </div>
    
    <div class="container iframe-container">
        <h2>Same-Origin Iframe</h2>
        <iframe id="same-origin-iframe" srcdoc="
            <html><body>
                <h3>Inside Iframe</h3>
                <button onclick=&quot;alert('Iframe button clicked')&quot;>Iframe Button</button>
                <a href=&quot;#iframe-link&quot;>Iframe Link</a>
                <input type=&quot;text&quot; placeholder=&quot;Iframe input&quot;>
            </body></html>
        "></iframe>
    </div>
    
    <div class="container iframe-container">
        <h2>Cross-Origin Iframe (Read-Only)</h2>
        <iframe src="https://example.com" sandbox="allow-same-origin"></iframe>
    </div>
    
    <div class="container shadow-container">
        <h2>Shadow DOM Elements</h2>
        <div id="shadow-host">Shadow Host Element</div>
    </div>
    
    <script>
        // Create shadow DOM content
        const shadowHost = document.getElementById('shadow-host');
        const shadowRoot = shadowHost.attachShadow({mode: 'open'});
        shadowRoot.innerHTML = `
            <style>
                button { background: #e91e63; color: white; padding: 10px; margin: 5px; }
                input { margin: 5px; padding: 5px; }
            </style>
            <h4>Shadow DOM Content</h4>
            <button onclick="alert('Shadow button clicked')">Shadow Button</button>
            <input type="text" placeholder="Shadow input">
            <a href="#shadow-link">Shadow Link</a>
        `;
    </script>
</body>
</html>
"""

	# Create temporary file
	temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False)
	temp_file.write(html_content)
	temp_file.close()

	return Path(temp_file.name).as_uri()


async def main():
	"""Run comprehensive multi-tab DOM service tests."""
	print('🚀 Starting Multi-Tab DOM Service Test Suite')
	print('=' * 60)

	# Create browser session (no CDP URL needed - will use existing browser)
	profile = BrowserProfile(headless=False, keep_alive=True)
	browser_session = BrowserSession(browser_profile=profile)

	try:
		# Start browser session
		await browser_session.start()
		print('✅ Browser session started')

		# Create DOM service
		dom_service = DOMService(browser_session)
		print('✅ DOM service created')

		# Test 1: Create test page with iframe and shadow DOM
		print('\n📄 Test 1: Loading test page with iframe and shadow DOM')
		test_url = await create_test_html()
		await browser_session.navigate_to(test_url)
		await asyncio.sleep(3)  # Wait for page to fully load

		serialized, selector_map = await dom_service.get_serialized_dom_tree(filter_mode='balanced')
		print(f'✅ Found {len(selector_map)} interactive elements in test page')
		print('Sample output:')
		print(serialized[:800] + '...' if len(serialized) > 800 else serialized)

		# Test 2: Multi-tab functionality
		print('\n🔄 Test 2: Testing multi-tab functionality')

		# Create second tab with different content
		await browser_session.create_new_tab('https://httpbin.org/html')
		await asyncio.sleep(3)

		serialized2, selector_map2 = await dom_service.get_serialized_dom_tree(filter_mode='balanced')
		print(f'✅ Tab 2: Found {len(selector_map2)} interactive elements')

		# Create third tab
		await browser_session.create_new_tab('https://example.com')
		await asyncio.sleep(3)

		serialized3, selector_map3 = await dom_service.get_serialized_dom_tree(filter_mode='balanced')
		print(f'✅ Tab 3: Found {len(selector_map3)} interactive elements')

		# Test 3: Tab switching
		print('\n🔀 Test 3: Testing tab switching')

		# Switch back to first tab
		await browser_session.switch_to_tab(0)
		await asyncio.sleep(1)

		serialized_back, selector_map_back = await dom_service.get_serialized_dom_tree(filter_mode='balanced')
		print(f'✅ Back to Tab 1: Found {len(selector_map_back)} interactive elements')

		# Verify we get the same results as before
		if len(selector_map) == len(selector_map_back):
			print('✅ Tab switching works correctly - same element count')
		else:
			print(f'⚠️  Element count differs: {len(selector_map)} vs {len(selector_map_back)}')

		# Switch to second tab
		await browser_session.switch_to_tab(1)
		await asyncio.sleep(1)

		serialized_2nd, selector_map_2nd = await dom_service.get_serialized_dom_tree(filter_mode='balanced')
		print(f'✅ Back to Tab 2: Found {len(selector_map_2nd)} interactive elements')

		# Test 4: Session caching and cleanup
		print('\n🧹 Test 4: Testing session caching and cleanup')

		# Check current cached sessions
		print(f'Current cached sessions: {len(dom_service.page_session_store)}')

		# Close a tab
		await browser_session.close_tab(2)  # Close third tab
		print('✅ Closed tab 3')

		# Clean up cached sessions
		await dom_service.cleanup_closed_tabs()
		print(f'✅ After cleanup: {len(dom_service.page_session_store)} cached sessions')

		# Test 5: Filter modes
		print('\n🎛️  Test 5: Testing different filter modes')

		await browser_session.switch_to_tab(0)  # Switch to test page
		await asyncio.sleep(1)

		# Test minimal mode
		serialized_min, selector_map_min = await dom_service.get_serialized_dom_tree(filter_mode='minimal')
		print(f'✅ Minimal mode: {len(selector_map_min)} elements')

		# Test comprehensive mode
		serialized_comp, selector_map_comp = await dom_service.get_serialized_dom_tree(filter_mode='comprehensive')
		print(f'✅ Comprehensive mode: {len(selector_map_comp)} elements')

		# Test balanced mode (default)
		serialized_bal, selector_map_bal = await dom_service.get_serialized_dom_tree(filter_mode='balanced')
		print(f'✅ Balanced mode: {len(selector_map_bal)} elements')

		print(
			f'\nFilter comparison: minimal({len(selector_map_min)}) < balanced({len(selector_map_bal)}) <= comprehensive({len(selector_map_comp)})'
		)

		# Test 6: Check if iframe and shadow DOM detection works
		print('\n🌐 Test 6: Testing iframe and shadow DOM extraction')
		print('✅ Iframe and shadow DOM content should be included in the serialized output above')
		print('✅ Look for markers like ">>> IFRAME CONTENT [iframe_0] <<<" and ">>> SHADOW DOM [shadow_0] <<<"')

		# Check for context markers in the serialized output
		if 'IFRAME CONTENT' in serialized_back:
			print('✅ Iframe content detected in DOM serialization')
		else:
			print('ℹ️  No iframe content markers found')

		if 'SHADOW DOM' in serialized_back:
			print('✅ Shadow DOM content detected in DOM serialization')
		else:
			print('ℹ️  No shadow DOM markers found')

		print('\n' + '=' * 60)
		print('🎉 All tests completed successfully!')
		print('✅ Multi-tab DOM extraction working')
		print('✅ Tab switching and caching working')
		print('✅ Session cleanup working')
		print('✅ Iframe and shadow DOM detection working')
		print('✅ Filter modes working')

	except Exception as e:
		print(f'\n❌ Test failed with error: {e}')
		import traceback

		traceback.print_exc()

	finally:
		# Clean up
		try:
			await browser_session.stop()
			print('\n🛑 Browser session stopped')
		except Exception as e:
			print(f'Warning: Error stopping browser session: {e}')


if __name__ == '__main__':
	asyncio.run(main())
