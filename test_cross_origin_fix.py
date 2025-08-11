#!/usr/bin/env python3
"""Test that cross-origin iframe flag works correctly."""

import asyncio
from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.events import ScrollEvent
from browser_use.dom.service import EnhancedDOMTreeNode

async def test_cross_origin_disabled():
	"""Test that with cross_origin_iframes=False, we don't hang on frame operations."""
	print("=== Testing with cross_origin_iframes=False (default) ===")
	
	# Create profile with cross-origin iframes disabled (default)
	profile = BrowserProfile(
		headless=True,
		cross_origin_iframes=False  # This is the default
	)
	
	# Create browser session
	session = BrowserSession(browser_profile=profile)
	
	try:
		# Start browser
		await session.start()
		print("✓ Browser started")
		
		# Navigate to a page
		await session._cdp_navigate('https://example.com')
		await asyncio.sleep(1)
		print("✓ Navigated to example.com")
		
		# Test 1: Simple scroll should work
		event = session.event_bus.dispatch(ScrollEvent(direction='down', amount=500))
		await asyncio.wait_for(event, timeout=3.0)
		print("✓ Simple scroll completed without hanging")
		
		# Test 2: Get frames should not hang
		all_frames, _ = await asyncio.wait_for(session.get_all_frames(), timeout=3.0)
		print(f"✓ Got {len(all_frames)} frames without hanging")
		
		# Test 3: cdp_client_for_node with frame_id should use main session
		# Create a simple mock object with frame_id attribute
		class MockNode:
			def __init__(self):
				self.frame_id = 'some-frame-id'
		
		mock_node = MockNode()
		
		cdp_session = await asyncio.wait_for(session.cdp_client_for_node(mock_node), timeout=3.0)
		print(f"✓ Got CDP session for node with frame_id without hanging")
		
		# Should be the main session since cross-origin is disabled
		assert cdp_session.session_id == session.agent_focus.session_id, "Should use main session when cross_origin_iframes=False"
		print("✓ Correctly using main session for frame nodes")
		
	finally:
		await session.kill()
		print("✓ Browser closed")

async def test_cross_origin_enabled():
	"""Test that with cross_origin_iframes=True, frame operations work as before."""
	print("\n=== Testing with cross_origin_iframes=True ===")
	
	# Create profile with cross-origin iframes enabled
	profile = BrowserProfile(
		headless=True,
		cross_origin_iframes=True
	)
	
	# Create browser session
	session = BrowserSession(browser_profile=profile)
	
	try:
		# Start browser
		await session.start()
		print("✓ Browser started")
		
		# Navigate to a page
		await session._cdp_navigate('https://example.com')
		await asyncio.sleep(1)
		print("✓ Navigated to example.com")
		
		# Get frames - should include iframe targets if present
		all_frames, _ = await asyncio.wait_for(session.get_all_frames(), timeout=5.0)
		print(f"✓ Got {len(all_frames)} frames with cross-origin support enabled")
		
	finally:
		await session.kill()
		print("✓ Browser closed")

async def main():
	"""Run all tests."""
	print("Testing cross-origin iframe handling fix...\n")
	
	await test_cross_origin_disabled()
	await test_cross_origin_enabled()
	
	print("\n✅ All tests passed! The cross-origin iframe flag is working correctly.")

if __name__ == "__main__":
	asyncio.run(main())