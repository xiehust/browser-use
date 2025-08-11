#!/usr/bin/env python3
"""Debug script to understand how to match iframe targets to their placeholder frames."""

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
        print("UNDERSTANDING FRAME-TARGET RELATIONSHIPS")
        print("="*80)
        
        # Find page and iframe targets
        page_target = next((t for t in all_targets if t['type'] == 'page' and 'cross-origin' in t.get('url', '')), None)
        iframe_targets = [t for t in all_targets if t['type'] == 'iframe']
        
        if page_target:
            print("\n1. MAIN PAGE TARGET:")
            print(f"   Target ID: {page_target['targetId'][:30]}...")
            print(f"   URL: {page_target['url']}")
            
            # Get frame tree from main page
            s = await session.cdp_client.send.Target.attachToTarget(
                params={'targetId': page_target['targetId'], 'flatten': True}
            )
            sid = s['sessionId']
            
            await session.cdp_client.send.Page.enable(session_id=sid)
            tree = await session.cdp_client.send.Page.getFrameTree(session_id=sid)
            
            print("\n2. MAIN PAGE FRAME TREE:")
            
            def print_tree(node, indent=0):
                frame = node['frame']
                frame_id = frame.get('id')
                frame_url = frame.get('url', 'none')
                
                print(f"{'  '*indent}Frame ID: {frame_id[:30]}...")
                print(f"{'  '*indent}  URL: {frame_url[:60]}")
                
                # Check if this frame has NO children but is an iframe URL
                # This would be a placeholder for an OOPIF
                child_frames = node.get('childFrames', [])
                if not child_frames and 'v0-simple-landing' in frame_url:
                    print(f"{'  '*indent}  🔸 PLACEHOLDER FRAME (no children, cross-origin URL)")
                    print(f"{'  '*indent}     This frame's content is in a separate target")
                
                for child in child_frames:
                    print_tree(child, indent+1)
            
            print_tree(tree['frameTree'])
            
            await session.cdp_client.send.Target.detachFromTarget(params={'sessionId': sid})
        
        if iframe_targets:
            print("\n3. IFRAME TARGETS:")
            
            for iframe_target in iframe_targets:
                print(f"\n   Iframe Target:")
                print(f"     Target ID: {iframe_target['targetId'][:30]}...")
                print(f"     URL: {iframe_target['url']}")
                print(f"     Opener ID: {iframe_target.get('openerId', 'none')}")
                
                # Get frame tree from iframe target
                s = await session.cdp_client.send.Target.attachToTarget(
                    params={'targetId': iframe_target['targetId'], 'flatten': True}
                )
                sid = s['sessionId']
                
                await session.cdp_client.send.Page.enable(session_id=sid)
                tree = await session.cdp_client.send.Page.getFrameTree(session_id=sid)
                
                iframe_frame = tree['frameTree']['frame']
                print(f"     Frame ID: {iframe_frame['id'][:30]}...")
                print(f"     Frame URL: {iframe_frame['url']}")
                
                await session.cdp_client.send.Target.detachFromTarget(params={'sessionId': sid})
        
        print("\n4. THE PROBLEM:")
        print("   - Main page shows placeholder frame with one ID")
        print("   - Iframe target shows its own frame with a DIFFERENT ID")
        print("   - We need to match them to establish parent-child relationship")
        
        print("\n5. POTENTIAL SOLUTIONS:")
        print("   - Match by URL (unreliable)")
        print("   - Check if placeholder frame ID matches iframe's targetId")
        print("   - Use DOM.getFrameOwner to get backend node ID")
        print("   - Check Target.getTargetInfo for additional metadata")
            
    finally:
        if session.cdp_client:
            await session.cdp_client.stop()

if __name__ == "__main__":
    asyncio.run(main())