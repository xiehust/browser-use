#!/usr/bin/env python3
"""Test cdp_client_for_frame on v0 cross-origin website."""

import asyncio
from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.events import BrowserStartEvent

async def test_v0_cross_origin():
    """Test frame hierarchy discovery on v0 cross-origin page."""
    
    # Create headless browser profile
    profile = BrowserProfile(
        headless=True,
        user_data_dir=None,
    )
    session = BrowserSession(browser_profile=profile)
    
    try:
        # Start browser
        await session.on_BrowserStartEvent(BrowserStartEvent())
        print("Browser started")
        
        # Navigate to the cross-origin test page
        test_url = "https://v0-website-with-clickable-elements.vercel.app/cross-origin"
        await session._cdp_navigate(test_url)
        print(f"Navigated to: {test_url}\n")
        
        # Wait for page and iframes to load
        await asyncio.sleep(3)
        
        # Load the new cdp_client_for_frame implementation
        exec(open('new_cdp_client_for_frame.py').read(), session.__dict__)
        
        # Build unified frame hierarchy using the method
        print("="*80)
        print("TESTING cdp_client_for_frame")
        print("="*80)
        
        # Build the hierarchy (we'll call it with a dummy frame_id just to get the hierarchy)
        try:
            # First get the main frame ID
            cdp_client, session_id = await session.cdp_client_for_target(session.current_target_id)
            await cdp_client.send.Page.enable(session_id=session_id)
            frame_tree = await cdp_client.send.Page.getFrameTree(session_id=session_id)
            main_frame_id = frame_tree.get('frameTree', {}).get('frame', {}).get('id')
            await cdp_client.send.Target.detachFromTarget(params={'sessionId': session_id})
            
            print(f"\nMain frame ID: {main_frame_id}")
            
            # Now call cdp_client_for_frame which will build the hierarchy
            # We'll catch the error since we're just interested in the hierarchy
            try:
                await session.cdp_client_for_frame(main_frame_id)
            except Exception:
                pass  # Expected if we don't find the frame
                
        except Exception as e:
            print(f"Error getting frame hierarchy: {e}")
            
        # Now manually build and display the hierarchy
        all_frames = {}
        target_sessions = {}
        
        # Get all targets
        targets = await session.cdp_client.send.Target.getTargets()
        all_targets = targets.get('targetInfos', [])
        
        print(f"\nFound {len(all_targets)} targets total")
        
        # Collect frames from all targets
        for target in all_targets:
            target_id = target.get('targetId')
            target_type = target.get('type')
            target_url = target.get('url', '')
            
            if not target_id:
                continue
                
            if target_type not in ['page', 'iframe']:
                continue
                
            print(f"\nProcessing {target_type}: {target_url[:60]}...")
            
            # Attach to target
            session_result = await session.cdp_client.send.Target.attachToTarget(
                params={'targetId': target_id, 'flatten': True}
            )
            session_id = session_result['sessionId']
            target_sessions[target_id] = session_id
            
            try:
                await session.cdp_client.send.Page.enable(session_id=session_id)
                frame_tree_result = await session.cdp_client.send.Page.getFrameTree(session_id=session_id)
                
                def collect_frames(node):
                    frame = node.get('frame', {})
                    frame_id = frame.get('id')
                    frame_url = frame.get('url', '')
                    
                    if frame_id:
                        all_frames[frame_id] = {
                            'url': frame_url,
                            'targetType': target_type,
                            'targetId': target_id,
                            'crossOriginIsolated': frame.get('crossOriginIsolatedContextType', 'unknown')
                        }
                    
                    for child in node.get('childFrames', []):
                        collect_frames(child)
                
                collect_frames(frame_tree_result.get('frameTree', {}))
                
            except Exception as e:
                print(f"  Error: {e}")
        
        # Clean up sessions
        for tid, sid in target_sessions.items():
            try:
                await session.cdp_client.send.Target.detachFromTarget(params={'sessionId': sid})
            except Exception:
                pass
        
        # Display results
        print("\n" + "="*80)
        print("COMPLETE FRAME HIERARCHY")
        print("="*80)
        
        expected_url = "https://v0-simple-landing-page-seven-xi.vercel.app"
        cross_origin_found = False
        
        for frame_id, frame_info in all_frames.items():
            url = frame_info['url']
            if expected_url in url:
                cross_origin_found = True
                print(f"\n✅ FOUND EXPECTED CROSS-ORIGIN FRAME!")
                print(f"  Frame ID: {frame_id}")
                print(f"  URL: {url}")
                print(f"  Target Type: {frame_info['targetType']}")
                print(f"  Target ID: {frame_info['targetId'][:16]}...")
                print(f"  Cross-Origin Isolated: {frame_info['crossOriginIsolated']}")
        
        if not cross_origin_found:
            print(f"\n❌ Expected cross-origin frame NOT found!")
            print(f"   Expected URL: {expected_url}")
            print(f"\nAll frames found:")
            for frame_id, frame_info in all_frames.items():
                print(f"  - {frame_info['url'][:80]}")
        
        print(f"\nTotal frames: {len(all_frames)}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if session.cdp_client:
            await session.cdp_client.stop()

if __name__ == "__main__":
    asyncio.run(test_v0_cross_origin())