#!/usr/bin/env python3
"""Test to check if OOPIF frames have parentId field."""

import asyncio
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
        print("CHECKING FRAME PARENT IDs")
        print("="*80)
        
        # Process each target
        for target in all_targets:
            if target.get('type') not in ['page', 'iframe']:
                continue
            
            target_id = target['targetId']
            target_type = target['type']
            target_url = target.get('url', '')
            
            print(f"\nTarget Type: {target_type}")
            print(f"Target URL: {target_url[:60]}")
            print(f"Target ID: {target_id[:30]}...")
            
            # Attach and get frame tree
            s = await session.cdp_client.send.Target.attachToTarget(
                params={'targetId': target_id, 'flatten': True}
            )
            sid = s['sessionId']
            
            try:
                await session.cdp_client.send.Page.enable(session_id=sid)
                tree = await session.cdp_client.send.Page.getFrameTree(session_id=sid)
                
                frame = tree['frameTree']['frame']
                frame_id = frame.get('id')
                parent_id = frame.get('parentId')  # <-- This is the key field!
                
                print(f"  Frame ID: {frame_id[:30]}...")
                print(f"  Parent ID: {parent_id[:30] + '...' if parent_id else 'None (ROOT)'}")
                
                if parent_id and target_type == 'iframe':
                    print(f"  ✅ OOPIF has parentId! This points to parent frame.")
                
            except Exception as e:
                print(f"  Error: {e}")
            finally:
                await session.cdp_client.send.Target.detachFromTarget(params={'sessionId': sid})
                
    finally:
        if session.cdp_client:
            await session.cdp_client.stop()

if __name__ == "__main__":
    asyncio.run(main())