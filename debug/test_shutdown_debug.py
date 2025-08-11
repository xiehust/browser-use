#!/usr/bin/env python3
"""Test browser shutdown with debug info."""

import asyncio
import sys
import signal

# Set up a signal handler to exit cleanly
def signal_handler(sig, frame):
    print('Script received signal', sig)
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

async def test():
    from browser_use.browser import BrowserSession
    from browser_use.browser.profile import BrowserProfile
    from browser_use.browser.events import BrowserStartEvent, BrowserStopEvent
    
    profile = BrowserProfile(headless=True, user_data_dir=None)
    session = BrowserSession(browser_profile=profile)
    
    print('Starting browser...')
    await session.on_BrowserStartEvent(BrowserStartEvent())
    
    print('Navigating...')
    await session._cdp_navigate('https://google.com')
    await asyncio.sleep(1)
    
    print('Dispatching BrowserStopEvent...')
    stop_event = session.event_bus.dispatch(BrowserStopEvent())
    try:
        await asyncio.wait_for(stop_event, timeout=2.0)
    except asyncio.TimeoutError:
        print('BrowserStopEvent timed out')
    
    print('Stopping CDP client...')
    if session._cdp_client_root:
        await session._cdp_client_root.stop()
    
    print('Browser stopped')
    
    # Get all tasks
    tasks = asyncio.all_tasks()
    print(f'Active tasks after stop: {len(tasks)}')
    for task in tasks:
        if not task.done() and task != asyncio.current_task():
            print(f'  - Task: {task.get_name()}, coro: {task.get_coro()}')
    
    # Cancel all remaining tasks
    for task in tasks:
        if not task.done() and task != asyncio.current_task():
            print(f'Cancelling task: {task.get_name()}')
            task.cancel()
    
    # Wait for tasks to complete cancellation
    if len([t for t in tasks if not t.done() and t != asyncio.current_task()]) > 0:
        await asyncio.gather(*[t for t in tasks if not t.done() and t != asyncio.current_task()], return_exceptions=True)
    
    print('All tasks cancelled')

# Run with debug to see what's happening
if __name__ == "__main__":
    asyncio.run(test(), debug=True)
    print('Exited cleanly')
