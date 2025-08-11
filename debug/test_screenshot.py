#!/usr/bin/env python3
"""Test screenshot functionality."""

import asyncio
from browser_use import Browser
from browser_use.browser.events import ScreenshotEvent


async def test_screenshot():
	"""Test that screenshots work correctly."""
	
	print("Creating browser...")
	browser = Browser()
	
	print("Getting browser session...")
	# This will create and attach the browser session
	session = await browser.get_session()
	
	print("Navigating to a page...")
	await browser.go_to_url("https://example.com")
	
	# Give page time to load
	await asyncio.sleep(2)
	
	print("Taking screenshot via event...")
	try:
		# Dispatch screenshot event directly
		screenshot_event = session.event_bus.dispatch(ScreenshotEvent())
		
		# Wait for result with timeout
		result = await asyncio.wait_for(screenshot_event.event_result(), timeout=5.0)
		
		if result and 'screenshot' in result:
			screenshot_b64 = result['screenshot']
			if screenshot_b64:
				print(f"✅ Screenshot successful! Size: {len(screenshot_b64)} bytes")
			else:
				print("❌ Screenshot returned but was empty")
		else:
			print(f"❌ Screenshot failed, result: {result}")
			
	except asyncio.TimeoutError:
		print("❌ Screenshot timed out - no handler registered?")
	except Exception as e:
		print(f"❌ Screenshot error: {e}")
	
	print("\nChecking if screenshot watchdog is attached...")
	if hasattr(session, '_screenshot_watchdog'):
		watchdog = session._screenshot_watchdog
		print(f"Screenshot watchdog: {watchdog}")
		if watchdog:
			print("✅ Screenshot watchdog is attached")
		else:
			print("❌ Screenshot watchdog is None")
	else:
		print("❌ No _screenshot_watchdog attribute")
	
	print("\nClosing browser...")
	from browser_use.browser.events import BrowserStopEvent
	stop_event = session.event_bus.dispatch(BrowserStopEvent(force=True))
	await asyncio.wait_for(stop_event, timeout=5.0)
	
	print("✅ Test complete")


if __name__ == "__main__":
	asyncio.run(test_screenshot())