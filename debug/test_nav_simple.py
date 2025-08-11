#!/usr/bin/env python3
"""Simple navigation test."""

import asyncio
from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.events import BrowserStartEvent

async def test():
	profile = BrowserProfile(headless=False, user_data_dir=None) 
	session = BrowserSession(browser_profile=profile)
	
	print('Starting browser...')
	await session.on_BrowserStartEvent(BrowserStartEvent())
	print('Browser started')
	
	# Wait for browser to be ready
	await asyncio.sleep(2)
	
	# Try direct CDP navigation
	print('\nTrying direct CDP navigation to google.com...')
	await session._cdp_navigate('https://www.google.com')
	print('Navigation command sent')
	
	await asyncio.sleep(3)
	
	# Check URL
	targets = await session._cdp_get_all_pages()
	if targets:
		print(f'Current URL: {targets[0].get("url")}')
	
	print('Stopping browser...')
	await session.on_BrowserStopEvent(BrowserStopEvent())
	print('Done')

asyncio.run(test())