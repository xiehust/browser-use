#!/usr/bin/env python3
"""Simple test to check if highlighting injection works."""

import asyncio
from browser_use.browser.session import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.events import BrowserStartEvent, BrowserStopEvent

async def main():
    profile = BrowserProfile(headless=False)
    session = BrowserSession(browser_profile=profile)
    
    try:
        # Start browser by dispatching event
        event = session.event_bus.dispatch(BrowserStartEvent())
        await event
        await session.go_to_url("https://example.com")
        await asyncio.sleep(2)
        
        # Get state - this should trigger highlighting
        print("Getting state (should inject highlighting)...")
        state = await session.get_state()
        
        if state.dom_state and state.dom_state.selector_map:
            print(f"✅ Found {len(state.dom_state.selector_map)} elements")
        else:
            print("❌ No elements found")
        
        print("\n🔍 Check browser for blue outlines with numbers.")
        print("Press Enter to close...")
        input()
        
    finally:
        # Stop browser by dispatching event
        stop_event = session.event_bus.dispatch(BrowserStopEvent())
        await stop_event

if __name__ == "__main__":
    asyncio.run(main())