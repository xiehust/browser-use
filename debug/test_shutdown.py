#!/usr/bin/env python3
"""Test browser shutdown cleanly."""

import asyncio
from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.events import BrowserStartEvent, BrowserStopEvent

async def test_shutdown():
    """Test browser starts and stops cleanly."""
    
    profile = BrowserProfile(headless=True, user_data_dir=None)
    session = BrowserSession(browser_profile=profile)
    
    try:
        print("Starting browser...")
        await session.on_BrowserStartEvent(BrowserStartEvent())
        
        print("Navigating to page...")
        await session._cdp_navigate("https://google.com")
        await asyncio.sleep(1)
        
        print("Browser started successfully")
        
    finally:
        print("Shutting down browser...")
        
        # Close CDP connection first
        if session._cdp_client_root:
            try:
                await session._cdp_client_root.stop()
            except:
                pass
        
        # Stop the browser
        stop_event = session.event_bus.dispatch(BrowserStopEvent())
        try:
            await asyncio.wait_for(stop_event, timeout=2.0)
            print("Browser stopped successfully")
        except asyncio.TimeoutError:
            print("Browser stop timed out")

async def main():
    await test_shutdown()
    print("Script completed cleanly")

if __name__ == "__main__":
    asyncio.run(main())
    print("Exited successfully")
