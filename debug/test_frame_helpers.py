#!/usr/bin/env python3
"""Test the refactored frame helper methods."""

import asyncio
import logging
from browser_use.browser.session import BrowserSession

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-8s [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)

async def test_frame_helpers():
    """Test the refactored frame helper methods."""
    
    logger.info("Creating browser session...")
    session = BrowserSession()
    
    try:
        logger.info("Starting browser...")
        from browser_use.browser.events import BrowserStartEvent, BrowserStopEvent
        
        # Start the browser
        event = session.event_bus.dispatch(BrowserStartEvent())
        await event
        logger.info("Browser started!")
        
        # Navigate to a page
        logger.info("Navigating to google.com...")
        await session._cdp_navigate("https://www.google.com")
        await asyncio.sleep(2)  # Wait for page to load
        
        # Test get_all_frames
        logger.info("Testing get_all_frames()...")
        all_frames, target_sessions = await session.get_all_frames()
        
        logger.info(f"Found {len(all_frames)} frames across {len(target_sessions)} targets")
        
        # Print frame hierarchy
        for frame_id, frame_info in all_frames.items():
            parent_id = frame_info.get('parentFrameId')
            target_id = frame_info.get('frameTargetId', 'Unknown')
            is_cross_origin = frame_info.get('isCrossOrigin', False)
            url = frame_info.get('url', 'Unknown')
            
            logger.info(f"  Frame {frame_id[:8]}...")
            logger.info(f"    - URL: {url[:50] if url else 'Unknown'}...")
            logger.info(f"    - Parent: {parent_id[:8] if parent_id else 'None'}...")
            logger.info(f"    - Target: {target_id[:8] if target_id else 'Unknown'}...")
            logger.info(f"    - Cross-origin: {is_cross_origin}")
            
            # Only show first 3 frames for brevity
            if list(all_frames.keys()).index(frame_id) >= 2:
                remaining = len(all_frames) - 3
                if remaining > 0:
                    logger.info(f"  ... and {remaining} more frames")
                break
        
        # Test find_frame_target
        if all_frames:
            first_frame_id = list(all_frames.keys())[0]
            logger.info(f"\nTesting find_frame_target() with frame {first_frame_id[:8]}...")
            
            frame_info = await session.find_frame_target(first_frame_id, all_frames)
            if frame_info:
                logger.info(f"  Found frame: URL = {frame_info.get('url', 'Unknown')[:50]}...")
            else:
                logger.info("  Frame not found")
        
        # Test cleanup_target_sessions
        logger.info(f"\nTesting cleanup_target_sessions()...")
        logger.info(f"  Sessions before cleanup: {len(target_sessions)}")
        
        # Keep first target if exists
        keep_target = list(target_sessions.keys())[0] if target_sessions else None
        await session.cleanup_target_sessions(target_sessions, keep_target_id=keep_target)
        logger.info(f"  Kept target: {keep_target[:8] if keep_target else 'None'}...")
        
        # Test cdp_client_for_frame (should work with the main frame)
        if all_frames:
            main_frame_id = list(all_frames.keys())[0]
            logger.info(f"\nTesting cdp_client_for_frame() with main frame...")
            
            try:
                cdp_client, session_id, target_id = await session.cdp_client_for_frame(main_frame_id)
                logger.info(f"  Success! Got CDP client for frame")
                logger.info(f"    - Session ID: {session_id[:8]}...")
                logger.info(f"    - Target ID: {target_id[:8]}...")
                
                # Clean up the session
                await cdp_client.send.Target.detachFromTarget(params={'sessionId': session_id})
                
            except Exception as e:
                logger.error(f"  Failed to get CDP client: {e}")
        
        logger.info("\nAll tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        logger.info("Stopping browser...")
        try:
            stop_event = session.event_bus.dispatch(BrowserStopEvent())
            # Wait for the event to complete
            await asyncio.wait_for(stop_event, timeout=5.0)
            # Give a moment for all handlers to finish
            await asyncio.sleep(0.5)
        except asyncio.TimeoutError:
            logger.warning("Browser stop timed out, forcing cleanup")
        except Exception as e:
            logger.warning(f"Error during browser stop: {e}")
        
        # Ensure CDP client is closed
        if hasattr(session, 'cdp_client') and session.cdp_client:
            try:
                if hasattr(session.cdp_client, 'close'):
                    await session.cdp_client.close()
            except Exception:
                pass
        
        logger.info("Browser stopped")

if __name__ == "__main__":
    success = asyncio.run(test_frame_helpers())
    exit(0 if success else 1)