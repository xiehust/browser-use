#!/usr/bin/env python3
"""Debug navigation issue."""

import asyncio
import logging
from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.events import BrowserStartEvent, NavigateToUrlEvent

logging.basicConfig(level=logging.DEBUG)

async def test():
	profile = BrowserProfile(headless=False, user_data_dir=None) 
	session = BrowserSession(browser_profile=profile)
	
	print('Starting browser...')
	await session.on_BrowserStartEvent(BrowserStartEvent())
	print('Browser started')
	
	# Wait for browser to be ready
	await asyncio.sleep(2)
	
	print('Navigating to google.com...')
	nav_event = session.event_bus.dispatch(NavigateToUrlEvent(url='https://www.google.com'))
	await nav_event
	print('Navigation event completed')
	
	# Wait to see if navigation actually happened
	await asyncio.sleep(5)
	
	# Check current URL
	targets = await session._cdp_get_all_pages()
	if targets:
		print(f'Current URL: {targets[0].get("url")}')
	
	# Try direct CDP navigation
	print('\nTrying direct CDP navigation...')
	await session._cdp_navigate('https://www.example.com')
	
	await asyncio.sleep(5)
	
	# Check URL again
	targets = await session._cdp_get_all_pages()
	if targets:
		print(f'Current URL after direct navigation: {targets[0].get("url")}')
	
	print('Stopping browser...')
	await session.on_BrowserStopEvent(BrowserStopEvent())
	print('Done')

asyncio.run(test())