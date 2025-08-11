#!/usr/bin/env python3
"""Debug script to verify screenshot functionality."""

import asyncio
import logging

from browser_use.browser.session import BrowserSession
from browser_use.browser.events import ScreenshotEvent

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def test_screenshot():
	"""Test screenshot functionality."""
	session = BrowserSession()
	
	try:
		# Start browser
		await session.start()
		
		# Navigate to a page
		await session.navigate("https://example.com")
		await asyncio.sleep(2)
		
		# Get browser state with screenshot (with vision disabled)
		logger.info("Getting browser state WITHOUT vision (but with cloud sync fix)...")
		state = await session.get_browser_state_summary(
			include_screenshot=True,  # Force screenshots for testing
			cached=False
		)
		
		if state.screenshot:
			logger.info(f"✅ Screenshot captured! Length: {len(state.screenshot)} chars")
			# Save first few chars for verification
			logger.info(f"   First 50 chars: {state.screenshot[:50]}...")
		else:
			logger.warning("❌ No screenshot in browser state")
		
		# Also test direct screenshot event
		logger.info("\nTesting direct ScreenshotEvent...")
		screenshot_event = session.event_bus.dispatch(ScreenshotEvent())
		result = await screenshot_event.event_result()
		
		if result and result.get('screenshot'):
			logger.info(f"✅ Direct screenshot event worked! Length: {len(result['screenshot'])} chars")
		else:
			logger.warning(f"❌ Direct screenshot event failed: {result}")
		
	finally:
		await session.stop()


if __name__ == "__main__":
	asyncio.run(test_screenshot())