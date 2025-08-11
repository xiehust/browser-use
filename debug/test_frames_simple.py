#!/usr/bin/env python3
"""Simple test of frame hierarchy."""

import asyncio
import logging
from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.events import BrowserStartEvent

# Silence debug logging
logging.getLogger().setLevel(logging.ERROR)

async def main():
	profile = BrowserProfile(headless=True, user_data_dir=None)
	session = BrowserSession(browser_profile=profile)
	
	try:
		await session.on_BrowserStartEvent(BrowserStartEvent())
		
		# Test 1: Nested iframe page
		print("\n" + "="*60)
		print("TEST 1: NESTED IFRAME PAGE")
		print("="*60)
		await session._cdp_navigate("https://v0-website-with-clickable-elements.vercel.app/nested-iframe")
		await asyncio.sleep(2)
		
		frames = await session.get_all_frames()
		print(f"Total frames: {len(frames)}")
		
		for fid, frame in frames.items():
			url = frame.get('url', '')[:50]
			parent = frame.get('parentFrameId')
			print(f"  Frame: {url}")
			print(f"    Parent: {parent[:20] if parent else 'ROOT'}")
		
		# Test 2: Cross-origin page
		print("\n" + "="*60)
		print("TEST 2: CROSS-ORIGIN PAGE")
		print("="*60)
		await session._cdp_navigate("https://v0-website-with-clickable-elements.vercel.app/cross-origin")
		await asyncio.sleep(2)
		
		frames = await session.get_all_frames()
		print(f"Total frames: {len(frames)}")
		
		for fid, frame in frames.items():
			url = frame.get('url', '')[:50]
			parent = frame.get('parentFrameId')
			is_oopif = 'v0-simple-landing' in frame.get('url', '')
			
			print(f"  Frame: {url}")
			print(f"    Parent: {parent[:20] if parent else 'ROOT'}")
			if is_oopif:
				if parent:
					print(f"    ✅ OOPIF has parent!")
				else:
					print(f"    ❌ OOPIF missing parent!")
		
		# Test 3: Shadow DOM page
		print("\n" + "="*60)
		print("TEST 3: SHADOW DOM PAGE")
		print("="*60)
		await session._cdp_navigate("https://v0-website-with-clickable-elements.vercel.app/shadow-dom")
		await asyncio.sleep(2)
		
		frames = await session.get_all_frames()
		print(f"Total frames: {len(frames)}")
		
		for fid, frame in frames.items():
			url = frame.get('url', '')[:50]
			parent = frame.get('parentFrameId')
			print(f"  Frame: {url}")
			print(f"    Parent: {parent[:20] if parent else 'ROOT'}")
			
	finally:
		if session.cdp_client:
			await session.cdp_client.stop()

if __name__ == "__main__":
	asyncio.run(main())