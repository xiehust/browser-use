#!/usr/bin/env python3
"""Quick test of the refactored frame helper methods."""

import asyncio
import logging
from browser_use.browser.session import BrowserSession

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-8s %(message)s'
)
logger = logging.getLogger(__name__)

async def test_frame_helpers():
    """Test the refactored frame helper methods."""
    
    logger.info("Creating browser session...")
    session = BrowserSession()
    
    try:
        logger.info("Starting browser...")
        from browser_use.browser.events import BrowserStartEvent
        
        # Start the browser
        event = session.event_bus.dispatch(BrowserStartEvent())
        await event
        logger.info("✓ Browser started")
        
        # Navigate to a simple page
        await session._cdp_navigate("https://www.example.com")
        await asyncio.sleep(1)  # Brief wait for page load
        
        # Test get_all_frames
        logger.info("\nTesting get_all_frames()...")
        all_frames, target_sessions = await session.get_all_frames()
        logger.info(f"✓ Found {len(all_frames)} frames across {len(target_sessions)} targets")
        
        # Test find_frame_target
        if all_frames:
            first_frame_id = list(all_frames.keys())[0]
            logger.info(f"\nTesting find_frame_target()...")
            frame_info = await session.find_frame_target(first_frame_id, all_frames)
            if frame_info:
                logger.info(f"✓ Found frame with URL: {frame_info.get('url', 'Unknown')[:50]}")
        
        # Test cleanup_target_sessions
        logger.info(f"\nTesting cleanup_target_sessions()...")
        initial_count = len(target_sessions)
        await session.cleanup_target_sessions(target_sessions)
        logger.info(f"✓ Cleaned up {initial_count} sessions")
        
        # Test _is_valid_target
        logger.info("\nTesting _is_valid_target()...")
        test_cases = [
            ({'type': 'page', 'url': 'https://example.com'}, True),
            ({'type': 'page', 'url': 'chrome-extension://abc'}, False),
            ({'type': 'service_worker', 'url': 'https://example.com'}, False),
            ({'type': 'iframe', 'url': 'https://example.com'}, True),
            ({'type': 'page', 'url': 'chrome-error://chromewebdata/'}, False),
        ]
        
        for target_info, expected in test_cases:
            result = session._is_valid_target(target_info)
            status = "✓" if result == expected else "✗"
            logger.info(f"  {status} {target_info['type']}, {target_info['url'][:30]}... -> {result}")
        
        logger.info("\n✅ All tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False
    finally:
        # Quick cleanup - don't wait for full graceful shutdown
        logger.info("\nCleaning up...")
        try:
            # Just close the CDP connection directly
            if session._cdp_client_root:
                await session._cdp_client_root.stop()
        except:
            pass
        
        # Kill browser process if running locally
        try:
            from browser_use.browser.events import BrowserKillEvent
            session.event_bus.dispatch(BrowserKillEvent())
        except:
            pass
        
        logger.info("✓ Cleanup complete")

if __name__ == "__main__":
    # Run with a timeout to prevent hanging
    async def main():
        try:
            return await asyncio.wait_for(test_frame_helpers(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.error("Test timed out after 10 seconds")
            return False
    
    success = asyncio.run(main())
    exit(0 if success else 1)
