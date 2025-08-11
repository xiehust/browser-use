import asyncio
from browser_use import BrowserSession, BrowserProfile
from browser_use.browser.events import *

async def test():
    print("Starting test...")
    session = BrowserSession(browser_profile=BrowserProfile(headless=False))
    
    # Start browser
    print("Starting browser...")
    session.event_bus.dispatch(BrowserStartEvent())
    await session.event_bus.expect(BrowserConnectedEvent, timeout=10.0)
    print("Browser connected")
    
    # Navigate
    print("Navigating to example.com...")
    session.event_bus.dispatch(NavigateToUrlEvent(url='https://www.example.com'))
    await asyncio.sleep(3)  # Give it time to navigate
    
    # Get state with DOM
    print("Requesting browser state with DOM...")
    event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
    
    try:
        state = await asyncio.wait_for(event.event_result(), timeout=10.0)
        if state and state.dom_state:
            print(f"✅ Success\! Got DOM with {len(state.dom_state.selector_map)} elements")
        else:
            print("❌ No DOM state returned")
    except asyncio.TimeoutError:
        print("❌ Timeout waiting for DOM state")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Stop
    print("Stopping browser...")
    session.event_bus.dispatch(BrowserStopEvent())
    await session.event_bus.expect(BrowserStoppedEvent, timeout=5.0)
    print("Test complete")

asyncio.run(test())
