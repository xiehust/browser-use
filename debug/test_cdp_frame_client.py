#!/usr/bin/env python3
"""Test cdp_client_for_frame implementation."""

import asyncio
import logging
from browser_use.browser import BrowserSession
from browser_use.browser.events import BrowserStartEvent

# Set up logging  
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_frame_client():
    """Test getting CDP client for frames."""
    
    from browser_use.browser.profile import BrowserProfile
    
    # Create headless profile with no user data dir
    profile = BrowserProfile(
        headless=True,
        user_data_dir=None
    )
    
    session = BrowserSession(browser_profile=profile)
    
    try:
        # Start browser
        await session.on_BrowserStartEvent(BrowserStartEvent())
        logger.info("Browser started")
        
        # Navigate to a page with iframes (e.g., a test page)
        logger.info("Navigating to test page...")
        await session._cdp_navigate("https://www.w3schools.com/html/html_iframe.asp")
        
        # Wait for page to load
        await asyncio.sleep(3)
        
        # Get all targets to see what's available
        targets = await session.cdp_client.send.Target.getTargets()
        logger.info(f"Found {len(targets.get('targetInfos', []))} targets")
        
        # Get the frame tree of the current target
        if session.current_target_id:
            cdp_client, session_id = await session.cdp_client_for_target(session.current_target_id)
            try:
                frame_tree = await cdp_client.send.Page.getFrameTree(session_id=session_id)
                
                def print_frame_tree(node, indent=0):
                    """Recursively print the frame tree."""
                    frame = node.get('frame', {})
                    logger.info(f"{'  ' * indent}Frame ID: {frame.get('id', 'unknown')}")
                    logger.info(f"{'  ' * indent}  URL: {frame.get('url', 'none')}")
                    
                    # Print child frames
                    for child in node.get('childFrames', []):
                        print_frame_tree(child, indent + 1)
                
                logger.info("Frame tree structure:")
                print_frame_tree(frame_tree.get('frameTree', {}))
                
                # Try to get a client for a specific frame if there are child frames
                frame_tree_node = frame_tree.get('frameTree', {})
                child_frames = frame_tree_node.get('childFrames', [])
                
                if child_frames:
                    # Get the first child frame ID
                    first_child_frame = child_frames[0].get('frame', {})
                    child_frame_id = first_child_frame.get('id')
                    
                    if child_frame_id:
                        logger.info(f"\nTesting cdp_client_for_frame with frame ID: {child_frame_id}")
                        
                        try:
                            frame_client, frame_session_id, frame_target_id = await session.cdp_client_for_frame(child_frame_id)
                            logger.info(f"Successfully got CDP client for frame!")
                            logger.info(f"  Target ID: {frame_target_id}")
                            logger.info(f"  Session ID: {frame_session_id}")
                            
                            # Clean up the session
                            await frame_client.send.Target.detachFromTarget(
                                params={'sessionId': frame_session_id}
                            )
                        except Exception as e:
                            logger.error(f"Failed to get client for frame: {e}")
                else:
                    logger.info("No child frames found on this page")
                    
            finally:
                # Detach from the target
                await cdp_client.send.Target.detachFromTarget(
                    params={'sessionId': session_id}
                )
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        try:
            if session.cdp_client:
                await session.cdp_client.stop()
        except:
            pass

if __name__ == "__main__":
    success = asyncio.run(test_frame_client())
    exit(0 if success else 1)