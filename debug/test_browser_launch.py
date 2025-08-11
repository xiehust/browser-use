#!/usr/bin/env python3
"""Simple test to verify browser can launch."""

import asyncio
import logging
from browser_use.browser.session import BrowserSession

# Set up logging with debug level
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)-8s [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)

async def test_browser_launch():
    """Test basic browser launch."""
    
    logger.info("Creating browser session...")
    session = BrowserSession()
    
    try:
        logger.info("Starting browser via event...")
        from browser_use.browser.events import BrowserStartEvent, BrowserStopEvent
        
        # Start the browser
        event = session.event_bus.dispatch(BrowserStartEvent())
        await event
        logger.info("Browser started!")
        
        # Check CDP is connected
        try:
            cdp_client = session.cdp_client
            logger.info(f"CDP client connected: {session.cdp_url}")
            
            # Try to get targets
            targets = await cdp_client.send.Target.getTargets()
            logger.info(f"Found {len(targets.get('targetInfos', []))} targets")
            
            # Get current target
            logger.info(f"Current target ID: {session.current_target_id}")
            
            # Try navigation
            logger.info("Trying navigation to google.com...")
            await session._cdp_navigate("https://www.google.com")
            logger.info("Navigation completed!")
            
        except RuntimeError as e:
            logger.error(f"CDP client not connected: {e}")
            return False
            
        logger.info("Test passed!")
        return True
        
    except Exception as e:
        logger.error(f"Browser operation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        logger.info("Stopping browser...")
        stop_event = session.event_bus.dispatch(BrowserStopEvent())
        await stop_event
        logger.info("Browser stopped")

if __name__ == "__main__":
    success = asyncio.run(test_browser_launch())
    exit(0 if success else 1)