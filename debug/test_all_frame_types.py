#!/usr/bin/env python3
"""Test to show frame hierarchies for all three v0 test pages."""

import asyncio
import logging
from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.events import BrowserStartEvent

# Silence most logging
logging.basicConfig(level=logging.WARNING)

async def analyze_page(session, url):
    """Analyze frame hierarchy for a given URL."""
    
    print(f"\n{'='*80}")
    print(f"📍 ANALYZING: {url}")
    print('='*80)
    
    # Navigate to the page
    await session._cdp_navigate(url)
    await asyncio.sleep(3)
    
    # Get all targets to see if there are iframe targets (OOPIFs)
    targets = await session.cdp_client.send.Target.getTargets()
    all_targets = targets.get('targetInfos', [])
    
    # Separate targets by type
    page_targets = [t for t in all_targets if t.get('type') == 'page']
    iframe_targets = [t for t in all_targets if t.get('type') == 'iframe']
    
    print(f"\n📊 Target Summary:")
    print(f"  - Page targets: {len(page_targets)}")
    print(f"  - Iframe targets (OOPIFs): {len(iframe_targets)}")
    
    if iframe_targets:
        print(f"\n🔸 OOPIF Targets Found:")
        for t in iframe_targets:
            print(f"    URL: {t.get('url', 'none')}")
            print(f"    Target ID: {t.get('targetId', '')[:20]}...")
    
    # Get the main page's frame tree
    main_target = next((t for t in all_targets if t['type'] == 'page' and url in t.get('url', '')), None)
    if not main_target:
        main_target = page_targets[0] if page_targets else None
    
    if main_target:
        print(f"\n📐 Main Page Frame Tree:")
        print(f"  Target ID: {main_target['targetId'][:20]}...")
        
        # Attach to main target and get frame tree
        s = await session.cdp_client.send.Target.attachToTarget(
            params={'targetId': main_target['targetId'], 'flatten': True}
        )
        sid = s['sessionId']
        
        try:
            await session.cdp_client.send.Page.enable(session_id=sid)
            tree = await session.cdp_client.send.Page.getFrameTree(session_id=sid)
            
            # Track all frame IDs we see in the main tree
            main_tree_frame_ids = set()
            
            def print_tree(node, indent=0):
                frame = node['frame']
                frame_id = frame.get('id', 'unknown')
                frame_url = frame.get('url', 'none')
                
                main_tree_frame_ids.add(frame_id)
                
                # Check if this might be a cross-origin frame placeholder
                is_cross_origin = frame.get('crossOriginIsolatedContextType', '') != 'NotIsolated'
                
                print(f"{'  '*indent}{'└─ ' if indent > 0 else ''}Frame: {frame_url[:60]}")
                print(f"{'  '*indent}   ID: {frame_id[:30]}...")
                
                if is_cross_origin:
                    print(f"{'  '*indent}   ⚠️  Cross-origin context: {frame.get('crossOriginIsolatedContextType')}")
                
                # Check if there are NO child frames but we have an iframe target for this URL
                # This would indicate an OOPIF
                child_frames = node.get('childFrames', [])
                if not child_frames and iframe_targets:
                    # Check if any iframe target matches this frame's URL
                    for iframe_target in iframe_targets:
                        if frame_url in iframe_target.get('url', ''):
                            print(f"{'  '*indent}   🔴 OOPIF content in separate target!")
                
                # Process child frames
                for child in child_frames:
                    print_tree(child, indent + 1)
            
            print_tree(tree['frameTree'])
            
            # Now check iframe targets to see their frame trees
            if iframe_targets:
                print(f"\n🔸 OOPIF Target Frame Trees:")
                
                for iframe_target in iframe_targets:
                    print(f"\n  Iframe Target: {iframe_target.get('url', 'none')[:60]}")
                    print(f"    Target ID: {iframe_target['targetId'][:20]}...")
                    
                    # Attach to iframe target
                    iframe_s = await session.cdp_client.send.Target.attachToTarget(
                        params={'targetId': iframe_target['targetId'], 'flatten': True}
                    )
                    iframe_sid = iframe_s['sessionId']
                    
                    try:
                        await session.cdp_client.send.Page.enable(session_id=iframe_sid)
                        iframe_tree = await session.cdp_client.send.Page.getFrameTree(session_id=iframe_sid)
                        
                        iframe_frame = iframe_tree['frameTree']['frame']
                        print(f"    Frame ID in OOPIF: {iframe_frame.get('id', 'unknown')[:30]}...")
                        print(f"    ⚠️  This frame runs in a separate process!")
                        
                        # Check if this frame ID was NOT in the main tree
                        if iframe_frame.get('id') not in main_tree_frame_ids:
                            print(f"    ✅ Confirmed: Frame ID not in main tree (true OOPIF)")
                        else:
                            print(f"    ❓ Unexpected: Frame ID was in main tree")
                            
                    except Exception as e:
                        print(f"    Error getting iframe tree: {e}")
                    finally:
                        await session.cdp_client.send.Target.detachFromTarget(params={'sessionId': iframe_sid})
                        
        finally:
            await session.cdp_client.send.Target.detachFromTarget(params={'sessionId': sid})
    
    # Now use get_all_frames to see the unified view
    print(f"\n🔧 Unified Frame Hierarchy (from get_all_frames):")
    all_frames, target_sessions = await session.get_all_frames()
    
    # Clean up sessions
    for tid, sess_id in target_sessions.items():
        try:
            await session.cdp_client.send.Target.detachFromTarget(params={'sessionId': sess_id})
        except:
            pass
    
    # Group frames by whether they have parents
    root_frames = []
    child_frames = []
    
    for frame_id, frame_info in all_frames.items():
        if not frame_info.get('parentFrameId'):
            root_frames.append((frame_id, frame_info))
        else:
            child_frames.append((frame_id, frame_info))
    
    print(f"  Total frames: {len(all_frames)}")
    print(f"  Root frames: {len(root_frames)}")
    print(f"  Child frames: {len(child_frames)}")
    
    # Show problematic frames
    for frame_id, frame_info in all_frames.items():
        frame_url = frame_info.get('url', 'none')
        parent_id = frame_info.get('parentFrameId')
        
        # Check if this is a misclassified root frame
        if not parent_id and 'v0-simple-landing-page' in frame_url:
            print(f"\n  ❌ PROBLEM: Cross-origin frame incorrectly shown as root!")
            print(f"     URL: {frame_url}")
            print(f"     Frame ID: {frame_id[:30]}...")
            print(f"     Should be a child of the main page frame")

async def main():
    """Test all three page types."""
    
    test_cases = [
        {
            'url': "https://v0-website-with-clickable-elements.vercel.app/nested-iframe",
            'description': "Same-origin nested iframes (no OOPIFs expected)"
        },
        {
            'url': "https://v0-website-with-clickable-elements.vercel.app/cross-origin",
            'description': "Cross-origin iframe (OOPIF expected)"
        },
        {
            'url': "https://v0-website-with-clickable-elements.vercel.app/shadow-dom",
            'description': "Shadow DOM (no iframes, just shadow roots)"
        }
    ]
    
    profile = BrowserProfile(headless=True, user_data_dir=None)
    session = BrowserSession(browser_profile=profile)
    
    try:
        await session.on_BrowserStartEvent(BrowserStartEvent())
        print("🚀 Browser started\n")
        
        for test_case in test_cases:
            print(f"\n{'#'*80}")
            print(f"# TEST: {test_case['description']}")
            print(f"{'#'*80}")
            
            await analyze_page(session, test_case['url'])
            
        print(f"\n{'='*80}")
        print("✅ All tests completed!")
        print('='*80)
        
    finally:
        if session.cdp_client:
            await session.cdp_client.stop()

if __name__ == "__main__":
    asyncio.run(main())