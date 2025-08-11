#!/usr/bin/env python3
"""Debug script to see all target information."""

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
        
        # Navigate to nested iframe page
        await session._cdp_navigate("https://v0-website-with-clickable-elements.vercel.app/nested-iframe")
        await asyncio.sleep(3)
        
        # Get all targets with full info
        targets = await session.cdp_client.send.Target.getTargets()
        
        print("ALL TARGETS:")
        print("="*80)
        for target in targets.get('targetInfos', []):
            print(f"\nTarget Type: {target.get('type')}")
            print(f"URL: {target.get('url', 'none')[:60]}")
            print(f"Target ID: {target.get('targetId')[:20]}...")
            print(f"Opener ID: {target.get('openerId', 'none')}")
            print(f"Browser Context ID: {target.get('browserContextId', 'none')}")
            print(f"Attached: {target.get('attached')}")
            
            # For iframe targets, check if they have additional info
            if target.get('type') == 'iframe':
                print("  ^ This is an IFRAME target")
                
                # Attach and get frame tree
                s = await session.cdp_client.send.Target.attachToTarget(
                    params={'targetId': target['targetId'], 'flatten': True}
                )
                sid = s['sessionId']
                
                try:
                    await session.cdp_client.send.Page.enable(session_id=sid)
                    tree = await session.cdp_client.send.Page.getFrameTree(session_id=sid)
                    frame = tree['frameTree']['frame']
                    print(f"  Frame ID from tree: {frame.get('id')[:20]}...")
                    print(f"  Parent Frame ID: {frame.get('parentId', 'NONE')}")
                except:
                    pass
                    
                await session.cdp_client.send.Target.detachFromTarget(params={'sessionId': sid})
        
        print("\n" + "="*80)
        print("FRAME RELATIONSHIPS:")
        print("="*80)
        
        # Now check main page frame tree
        main_target = next((t for t in targets['targetInfos'] if t['type'] == 'page'), None)
        if main_target:
            s = await session.cdp_client.send.Target.attachToTarget(
                params={'targetId': main_target['targetId'], 'flatten': True}
            )
            sid = s['sessionId']
            
            await session.cdp_client.send.Page.enable(session_id=sid)
            tree = await session.cdp_client.send.Page.getFrameTree(session_id=sid)
            
            def print_tree(node, indent=0):
                frame = node['frame']
                print(f"{'  '*indent}Frame: {frame.get('url', 'none')[:50]}")
                print(f"{'  '*indent}  ID: {frame.get('id')[:20]}...")
                
                # Check for child frames that might be OOPIFs
                for child in node.get('childFrames', []):
                    print_tree(child, indent+1)
            
            print("\nMain page frame tree:")
            print_tree(tree['frameTree'])
            
            await session.cdp_client.send.Target.detachFromTarget(params={'sessionId': sid})
            
    finally:
        if session.cdp_client:
            await session.cdp_client.stop()

if __name__ == "__main__":
    asyncio.run(main())