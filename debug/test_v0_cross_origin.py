#!/usr/bin/env python3
"""Test cdp_client_for_frame on v0 cross-origin website."""

import asyncio
import json
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
        print(f"Navigated to: {test_url}")
        
        # Wait for page and iframes to load
        await asyncio.sleep(3)
        
        print("\n" + "="*80)
        print("BUILDING UNIFIED FRAME HIERARCHY")
        print("="*80)
        
        # Build unified frame hierarchy (similar to cdp_client_for_frame)
        all_frames = {}  # frame_id -> FrameInfo dict
        target_sessions = {}  # target_id -> session_id
        
        # Get all targets
        targets = await session.cdp_client.send.Target.getTargets()
        all_targets = targets.get('targetInfos', [])
        
        print(f"\nFound {len(all_targets)} total targets:")
        for target in all_targets:
            t_type = target.get('type')
            t_url = target.get('url', 'none')
            t_id = target.get('targetId', 'unknown')
            if t_type in ['page', 'iframe']:
                print(f"  [{t_type}] {t_url[:80]}...")
                print(f"         ID: {t_id[:16]}...")
        
        # First pass: collect frame trees from ALL targets
        print("\n" + "-"*80)
        print("COLLECTING FRAME TREES FROM ALL TARGETS")
        print("-"*80)
        
        for target in all_targets:
            target_id = target.get('targetId')
            target_type = target.get('type')
            target_url = target.get('url', '')
            
            if not target_id:
                continue
            
            print(f"\nProcessing target: {target_type} - {target_url[:50]}...")
            
            # Attach to target
            session_result = await session.cdp_client.send.Target.attachToTarget(
                params={'targetId': target_id, 'flatten': True}
            )
            session_id = session_result['sessionId']
            target_sessions[target_id] = session_id
            
            try:
                # Set auto-attach to get related targets
                await session.cdp_client.send.Target.setAutoAttach(
                    params={
                        'autoAttach': True,
                        'waitForDebuggerOnStart': False,
                        'flatten': True
                    },
                    session_id=session_id
                )
                
                # Try to get frame tree (not all target types support this)
                try:
                    await session.cdp_client.send.Page.enable(session_id=session_id)
                    frame_tree_result = await session.cdp_client.send.Page.getFrameTree(session_id=session_id)
                    
                    # Process the frame tree recursively
                    def process_frame_tree(node, parent_frame_id=None, depth=0):
                        """Recursively process frame tree and add to all_frames."""
                        frame = node.get('frame', {})
                        current_frame_id = frame.get('id')
                        
                        if current_frame_id:
                            # Create frame info with all CDP response data plus our additions
                            frame_info = {
                                **frame,  # Include all original frame data
                                'frameTargetId': target_id,  # Target that can access this frame
                                'parentFrameId': parent_frame_id,  # Parent frame ID if any
                                'childFrameIds': [],  # Will be populated below
                                'isCrossOrigin': False,  # Will be determined based on context
                                'targetType': target_type,
                                'targetUrl': target_url,
                            }
                            
                            # Check if frame is cross-origin based on crossOriginIsolatedContextType
                            cross_origin_type = frame.get('crossOriginIsolatedContextType')
                            if cross_origin_type and cross_origin_type != 'NotIsolated':
                                frame_info['isCrossOrigin'] = True
                            
                            # For iframe targets, the frame itself is likely cross-origin
                            if target.get('type') == 'iframe':
                                frame_info['isCrossOrigin'] = True
                            
                            # Add child frame IDs (note: OOPIFs won't appear here)
                            child_frames = node.get('childFrames', [])
                            for child in child_frames:
                                child_frame = child.get('frame', {})
                                child_frame_id = child_frame.get('id')
                                if child_frame_id:
                                    frame_info['childFrameIds'].append(child_frame_id)
                            
                            # Store or merge frame info
                            if current_frame_id in all_frames:
                                # Frame already seen from another target, merge info
                                existing = all_frames[current_frame_id]
                                # If this is an iframe target, it has direct access to the frame
                                if target.get('type') == 'iframe':
                                    existing['frameTargetId'] = target_id
                                    existing['isCrossOrigin'] = True
                                    existing['targetType'] = target_type
                                    existing['targetUrl'] = target_url
                            else:
                                all_frames[current_frame_id] = frame_info
                                print(f"  {'  '*depth}Found frame: {frame.get('url', 'none')[:60]}...")
                                print(f"  {'  '*depth}  Frame ID: {current_frame_id[:16]}...")
                                if frame_info['isCrossOrigin']:
                                    print(f"  {'  '*depth}  *** CROSS-ORIGIN ***")
                            
                            # Process child frames recursively
                            for child in child_frames:
                                process_frame_tree(child, current_frame_id, depth+1)
                    
                    # Process the entire frame tree
                    process_frame_tree(frame_tree_result.get('frameTree', {}))
                    
                except Exception as e:
                    # Target doesn't support Page domain or has no frames
                    print(f"  (No frame tree available: {str(e)[:50]})")
                    
            except Exception as e:
                # Error processing this target
                print(f"  Error processing target: {e}")
        
        # Print the complete unified frame hierarchy
        print("\n" + "="*80)
        print("COMPLETE UNIFIED FRAME HIERARCHY")
        print("="*80)
        
        print(f"\nTotal frames discovered: {len(all_frames)}")
        print("\nFrame Details:")
        print("-"*80)
        
        # Find the expected cross-origin frame
        cross_origin_frame_found = False
        expected_url = "https://v0-simple-landing-page-seven-xi.vercel.app"
        
        for frame_id, frame_info in all_frames.items():
            url = frame_info.get('url', 'none')
            parent_id = frame_info.get('parentFrameId', 'ROOT')
            is_cross = frame_info.get('isCrossOrigin', False)
            target_type = frame_info.get('targetType', 'unknown')
            
            print(f"\nFrame ID: {frame_id[:16]}...")
            print(f"  URL: {url}")
            print(f"  Parent Frame ID: {parent_id[:16] if parent_id != 'ROOT' else 'ROOT'}...")
            print(f"  Is Cross-Origin: {is_cross}")
            print(f"  Target Type: {target_type}")
            print(f"  Target ID: {frame_info.get('frameTargetId', 'unknown')[:16]}...")
            
            if expected_url in url:
                cross_origin_frame_found = True
                print(f"  *** THIS IS THE EXPECTED CROSS-ORIGIN FRAME! ***")
                
                # Test cdp_client_for_frame on this frame
                print(f"\n  Testing cdp_client_for_frame on this frame...")
                try:
                    client, sid, tid = await session.cdp_client_for_frame(frame_id)
                    print(f"  ✅ SUCCESS! Got CDP client")
                    print(f"    Session ID: {sid[:16]}...")
                    print(f"    Target ID: {tid[:16]}...")
                    
                    # Test execution in the frame
                    result = await client.send.Runtime.evaluate(
                        params={'expression': 'window.location.href'},
                        session_id=sid
                    )
                    frame_url = result.get('result', {}).get('value', 'unknown')
                    print(f"    Verified frame URL: {frame_url}")
                    
                    # Clean up
                    await client.send.Target.detachFromTarget(params={'sessionId': sid})
                    
                except Exception as e:
                    print(f"  ❌ Failed to get CDP client: {e}")
        
        # Clean up all sessions
        for target_id, session_id in target_sessions.items():
            try:
                await session.cdp_client.send.Target.detachFromTarget(
                    params={'sessionId': session_id}
                )
            except Exception:
                pass
        
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        
        if cross_origin_frame_found:
            print(f"✅ Successfully found the expected cross-origin frame!")
            print(f"   URL: {expected_url}")
        else:
            print(f"❌ Expected cross-origin frame NOT found!")
            print(f"   Expected URL: {expected_url}")
        
        # Count frame types
        cross_origin_count = sum(1 for f in all_frames.values() if f.get('isCrossOrigin'))
        same_origin_count = len(all_frames) - cross_origin_count
        
        print(f"\nFrame Statistics:")
        print(f"  Total frames: {len(all_frames)}")
        print(f"  Cross-origin frames: {cross_origin_count}")
        print(f"  Same-origin frames: {same_origin_count}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        if session.cdp_client:
            await session.cdp_client.stop()

if __name__ == "__main__":
    asyncio.run(test_v0_cross_origin())