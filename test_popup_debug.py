#!/usr/bin/env python
import asyncio
import logging
from browser_use import BrowserSession
from browser_use.browser.profile import BrowserProfile

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s [%(name)s] %(message)s')

async def test_popup():
    session = BrowserSession(browser_profile=BrowserProfile(headless=False))
    await session.start()
    
    # Navigate to a test page
    from browser_use.browser.events import NavigateToUrlEvent
    await session.event_bus.dispatch(NavigateToUrlEvent(url="data:text/html,<button onclick='alert(\"test\")'>Click me</button>"))
    await asyncio.sleep(2)
    
    print("Popups watchdog registered:", session._popups_watchdog._dialog_listeners_registered)
    
    # Try to click the button
    try:
        cdp_session = await session.get_or_create_cdp_session()
        
        # Click the button using JavaScript
        await cdp_session.cdp_client.send.Runtime.evaluate(
            params={'expression': 'document.querySelector("button").click()'},
            session_id=cdp_session.session_id
        )
        
        await asyncio.sleep(2)
        print("Click succeeded!")
    except Exception as e:
        print(f"Click failed: {e}")
    
    await asyncio.sleep(5)
    await session.kill()

asyncio.run(test_popup())