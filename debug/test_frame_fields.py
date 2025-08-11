#!/usr/bin/env python3
"""Debug script to check what fields are in frame objects."""

import asyncio
import json
from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.events import BrowserStartEvent

async def main():
    profile = BrowserProfile(headless=True, user_data_dir=None)
    session = BrowserSession(browser_profile=profile)
    
    try:
        await session.on_BrowserStartEvent(BrowserStartEvent())
        
        # Navigate to cross-origin page
        await session._cdp_navigate("https://v0-website-with-clickable-elements.vercel.app/cross-origin")
        await asyncio.sleep(3)
        
        # Get all targets
        targets = await session.cdp_client.send.Target.getTargets()
        all_targets = targets.get('targetInfos', [])
        
        print("="*80)
        print("CHECKING FRAME vs TARGET IDs")
        print("="*80)
        
        for target in all_targets:
            if target.get('type') not in ['page', 'iframe']:
                continue
            
            target_id = target['targetId']
            target_type = target['type']
            target_url = target.get('url', '')
            
            print(f"\n{'='*40}")
            print(f"Target Type: {target_type}")
            print(f"Target URL: {target_url[:60]}")
            print(f"Target ID: {target_id}")
            
            # Attach and get frame tree
            s = await session.cdp_client.send.Target.attachToTarget(
                params={'targetId': target_id, 'flatten': True}
            )
            sid = s['sessionId']
            
            try:
                await session.cdp_client.send.Page.enable(session_id=sid)
                tree = await session.cdp_client.send.Page.getFrameTree(session_id=sid)
                
                frame = tree['frameTree']['frame']
                
                print(f"\nFrame object keys: {list(frame.keys())}")
                print(f"Frame ID: {frame.get('id')}")
                print(f"Frame parentId: {frame.get('parentId', 'None')}")
                print(f"Frame URL: {frame.get('url', 'none')[:60]}")
                
                # Check if frame ID matches target ID
                if frame.get('id') == target_id:
                    print("❌ WARNING: Frame ID matches Target ID!")
                else:
                    print("✅ Frame ID and Target ID are different")
                
            except Exception as e:
                print(f"  Error: {e}")
            finally:
                await session.cdp_client.send.Target.detachFromTarget(params={'sessionId': sid})
                
    finally:
        if session.cdp_client:
            await session.cdp_client.stop()

if __name__ == "__main__":
    asyncio.run(main())