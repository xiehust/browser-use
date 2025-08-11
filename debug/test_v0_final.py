#!/usr/bin/env python3
"""Test cdp_client_for_frame on v0 cross-origin website."""

import asyncio
import logging
from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.events import BrowserStartEvent

# Reduce logging noise
logging.getLogger('browser_use').setLevel(logging.WARNING)
logging.getLogger('cdp_use').setLevel(logging.WARNING)
logging.getLogger('websockets').setLevel(logging.WARNING)

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
        
        # Build complete frame hierarchy
        all_frames = {}
        target_sessions = {}
        
        # Get all targets
        targets = await session.cdp_client.send.Target.getTargets()
        all_targets = targets.get('targetInfos', [])
        
        print(f"Found {len(all_targets)} targets total")
        
        # Collect frames from all targets
        for target in all_targets:
            target_id = target.get('targetId')
            target_type = target.get('type')
            target_url = target.get('url', '')
            
            if not target_id or target_type not in ['page', 'iframe']:
                continue
                
            print(f"Processing {target_type}: {target_url[:60]}...")
            
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
                
                def collect_frames(node, parent_id=None):
                    frame = node.get('frame', {})
                    frame_id = frame.get('id')
                    frame_url = frame.get('url', '')
                    
                    if frame_id:
                        all_frames[frame_id] = {
                            'url': frame_url,
                            'targetType': target_type,
                            'targetId': target_id,
                            'parentFrameId': parent_id,
                            'crossOriginIsolated': frame.get('crossOriginIsolatedContextType', 'unknown'),
                            'secureContext': frame.get('secureContextType', 'unknown')
                        }
                    
                    for child in node.get('childFrames', []):
                        collect_frames(child, frame_id)
                
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
        cross_origin_frame = None
        
        print(f"\nTotal frames discovered: {len(all_frames)}")
        
        for frame_id, frame_info in all_frames.items():
            url = frame_info['url']
            parent = frame_info.get('parentFrameId')
            
            print(f"\nFrame: {url[:80]}")
            print(f"  ID: {frame_id[:16]}...")
            print(f"  Parent: {parent[:16] + '...' if parent else 'ROOT'}")
            print(f"  Target Type: {frame_info['targetType']}")
            print(f"  Cross-Origin Isolated: {frame_info['crossOriginIsolated']}")
            
            if expected_url in url:
                cross_origin_frame = frame_info
                cross_origin_frame['id'] = frame_id
                print("  *** THIS IS THE EXPECTED CROSS-ORIGIN FRAME! ***")
        
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        
        if cross_origin_frame:
            print(f"\n✅ Successfully found the expected cross-origin frame!")
            print(f"   URL: {cross_origin_frame['url']}")
            print(f"   Frame ID: {cross_origin_frame['id']}")
            print(f"   Target Type: {cross_origin_frame['targetType']}")
            print(f"   Target ID: {cross_origin_frame['targetId'][:16]}...")
            
            # Test cdp_client_for_frame with this frame
            print(f"\nTesting cdp_client_for_frame method...")
            try:
                client, sid, tid = await session.cdp_client_for_frame(cross_origin_frame['id'])
                print(f"✅ cdp_client_for_frame SUCCESS!")
                print(f"   Session ID: {sid[:16]}...")
                print(f"   Target ID: {tid[:16]}...")
                
                # Verify we can execute in the frame
                result = await client.send.Runtime.evaluate(
                    params={'expression': 'window.location.href'},
                    session_id=sid
                )
                frame_url = result.get('result', {}).get('value', 'unknown')
                print(f"   Verified frame URL: {frame_url}")
                
                # Clean up
                await client.send.Target.detachFromTarget(params={'sessionId': sid})
                
            except Exception as e:
                print(f"❌ cdp_client_for_frame failed: {e}")
        else:
            print(f"\n❌ Expected cross-origin frame NOT found!")
            print(f"   Expected URL containing: {expected_url}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if session.cdp_client:
            await session.cdp_client.stop()

if __name__ == "__main__":
    asyncio.run(test_v0_cross_origin())