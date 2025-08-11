#!/usr/bin/env python3
"""Minimal test for browser shutdown."""

import asyncio
from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.events import BrowserStartEvent, BrowserStopEvent

async def test():
    profile = BrowserProfile(headless=True, user_data_dir=None) 
    session = BrowserSession(browser_profile=profile)
    
    print('Starting browser...')
    await session.on_BrowserStartEvent(BrowserStartEvent())
    print('Browser started')
    
    print('Dispatching BrowserStopEvent...')
    stop_event = session.event_bus.dispatch(BrowserStopEvent())
    
    # Wait with timeout
    try:
        await asyncio.wait_for(stop_event, timeout=3.0)
        print('BrowserStopEvent completed')
    except asyncio.TimeoutError:
        print('BrowserStopEvent timed out after 3 seconds')
        
        # Get all tasks to see what's blocking
        tasks = [t for t in asyncio.all_tasks() if not t.done() and t != asyncio.current_task()]
        print(f'Active tasks: {len(tasks)}')
        for task in tasks:
            print(f'  - {task}')
    
    # Clean up CDP client
    if session._cdp_client:
        await session._cdp_client.stop()
    
    print('Done')

asyncio.run(test())
print('Script exited')