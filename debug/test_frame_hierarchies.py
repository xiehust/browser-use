#!/usr/bin/env python3
"""Test frame hierarchy discovery on various v0 test pages."""

import asyncio
import logging
from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.events import BrowserStartEvent

# Reduce logging noise
logging.getLogger('browser_use').setLevel(logging.WARNING)
logging.getLogger('cdp_use').setLevel(logging.WARNING)
logging.getLogger('websockets').setLevel(logging.WARNING)

async def get_frame_hierarchy(session, url):
    """Get complete frame hierarchy for a given URL."""
    
    print(f"\n{'='*80}")
    print(f"Testing: {url}")
    print('='*80)
    
    # Navigate to the page
    await session._cdp_navigate(url)
    print(f"Navigated to page")
    
    # Wait for page and iframes to load
    await asyncio.sleep(3)
    
    # Build complete frame hierarchy
    all_frames = {}
    target_sessions = {}
    
    # Get all targets
    targets = await session.cdp_client.send.Target.getTargets()
    all_targets = targets.get('targetInfos', [])
    
    print(f"\n📊 Found {len(all_targets)} total targets")
    
    # Show all targets first
    print("\n📋 All targets:")
    for target in all_targets:
        t_type = target.get('type')
        t_url = target.get('url', 'none')
        t_id = target.get('targetId', 'unknown')
        if t_type in ['page', 'iframe']:
            print(f"  [{t_type:6}] {t_url[:70]}")
            print(f"           ID: {t_id[:20]}...")
    
    # Collect frames from all targets
    print("\n🔍 Collecting frame trees from targets...")
    for target in all_targets:
        target_id = target.get('targetId')
        target_type = target.get('type')
        target_url = target.get('url', '')
        
        if not target_id or target_type not in ['page', 'iframe']:
            continue
        
        # Attach to target
        session_result = await session.cdp_client.send.Target.attachToTarget(
            params={'targetId': target_id, 'flatten': True}
        )
        session_id = session_result['sessionId']
        target_sessions[target_id] = session_id
        
        try:
            # Set auto-attach for this target
            await session.cdp_client.send.Target.setAutoAttach(
                params={
                    'autoAttach': True,
                    'waitForDebuggerOnStart': False,
                    'flatten': True
                },
                session_id=session_id
            )
            
            # Get frame tree
            await session.cdp_client.send.Page.enable(session_id=session_id)
            frame_tree_result = await session.cdp_client.send.Page.getFrameTree(session_id=session_id)
            
            def collect_frames(node, parent_id=None, depth=0):
                frame = node.get('frame', {})
                frame_id = frame.get('id')
                frame_url = frame.get('url', '')
                
                if frame_id:
                    frame_info = {
                        'url': frame_url,
                        'targetType': target_type,
                        'targetId': target_id,
                        'parentFrameId': parent_id,
                        'depth': depth,
                        'crossOriginIsolated': frame.get('crossOriginIsolatedContextType', 'unknown'),
                        'secureContext': frame.get('secureContextType', 'unknown'),
                        'domainAndRegistry': frame.get('domainAndRegistry', 'unknown'),
                        'adFrameStatus': frame.get('adFrameStatus', {}),
                    }
                    
                    # Store or update frame info
                    if frame_id in all_frames:
                        # Frame seen from another target - likely OOPIF
                        frame_info['isOOPIF'] = True
                        # Keep the iframe target as primary
                        if target_type == 'iframe':
                            all_frames[frame_id] = frame_info
                    else:
                        all_frames[frame_id] = frame_info
                
                # Process child frames
                for child in node.get('childFrames', []):
                    collect_frames(child, frame_id, depth + 1)
            
            collect_frames(frame_tree_result.get('frameTree', {}))
            
        except Exception as e:
            if "'Page.enable' wasn't found" not in str(e):
                print(f"  Error processing target: {e}")
    
    # Clean up sessions
    for tid, sid in target_sessions.items():
        try:
            await session.cdp_client.send.Target.detachFromTarget(params={'sessionId': sid})
        except Exception:
            pass
    
    # Display frame hierarchy
    print("\n📐 FRAME HIERARCHY:")
    print("-" * 80)
    
    # Sort frames by depth for better visualization
    sorted_frames = sorted(all_frames.items(), key=lambda x: (x[1]['depth'], x[0]))
    
    for frame_id, frame_info in sorted_frames:
        indent = "  " * frame_info['depth']
        url = frame_info['url']
        parent = frame_info.get('parentFrameId')
        
        print(f"\n{indent}{'└─ ' if frame_info['depth'] > 0 else ''}Frame: {url[:70]}")
        print(f"{indent}   ID: {frame_id[:30]}...")
        print(f"{indent}   Parent: {parent[:30] + '...' if parent else 'ROOT'}")
        print(f"{indent}   Target Type: {frame_info['targetType']}")
        print(f"{indent}   Cross-Origin: {frame_info['crossOriginIsolated']}")
        
        if frame_info.get('isOOPIF'):
            print(f"{indent}   ⚠️  OOPIF (Out-of-Process iframe)")
        
        if frame_info.get('domainAndRegistry') != 'unknown':
            print(f"{indent}   Domain: {frame_info['domainAndRegistry']}")
    
    print(f"\n📈 Summary:")
    print(f"  Total frames: {len(all_frames)}")
    print(f"  Max depth: {max((f['depth'] for f in all_frames.values()), default=0)}")
    
    # Count frame types
    cross_origin_count = sum(1 for f in all_frames.values() if 'NotIsolated' not in str(f.get('crossOriginIsolated', '')))
    oopif_count = sum(1 for f in all_frames.values() if f.get('isOOPIF'))
    
    if cross_origin_count > 0:
        print(f"  Cross-origin frames: {cross_origin_count}")
    if oopif_count > 0:
        print(f"  OOPIFs: {oopif_count}")
    
    return all_frames

async def main():
    """Test frame hierarchies on different pages."""
    
    # Test URLs
    test_urls = [
        "https://v0-website-with-clickable-elements.vercel.app/nested-iframe",
        "https://v0-website-with-clickable-elements.vercel.app/cross-origin", 
        "https://v0-website-with-clickable-elements.vercel.app/shadow-dom"
    ]
    
    # Create headless browser profile
    profile = BrowserProfile(
        headless=True,
        user_data_dir=None,
    )
    session = BrowserSession(browser_profile=profile)
    
    try:
        # Start browser
        await session.on_BrowserStartEvent(BrowserStartEvent())
        print("🚀 Browser started")
        
        # Test each URL
        for url in test_urls:
            await get_frame_hierarchy(session, url)
            
        print("\n" + "="*80)
        print("✅ All tests completed!")
        print("="*80)
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if session.cdp_client:
            await session.cdp_client.stop()

if __name__ == "__main__":
    asyncio.run(main())