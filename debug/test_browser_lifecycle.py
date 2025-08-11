#!/usr/bin/env python3
"""Test browser lifecycle - start, verify CDP, and stop."""

import asyncio
import logging
from browser_use.browser.session import BrowserSession
from browser_use.browser.events import BrowserStartEvent, BrowserStopEvent

logging.basicConfig(level=logging.INFO, format='%(levelname)-8s %(message)s')
logger = logging.getLogger(__name__)

async def test_browser_lifecycle():
    """Test browser start, CDP initialization, and stop."""
    
    session = BrowserSession()
    
    try:
        # Start browser
        logger.info("Starting browser...")
        start_event = session.event_bus.dispatch(BrowserStartEvent())
        await asyncio.wait_for(start_event, timeout=10.0)
        
        # Verify CDP client is initialized
        logger.info(f"✓ Browser started, CDP URL: {session.cdp_url}")
        logger.info(f"✓ CDP client initialized: {session._cdp_client_root is not None}")
        
        # Test CDP client property access
        try:
            cdp_client = session.cdp_client
            logger.info(f"✓ CDP client property accessible: {cdp_client is not None}")
        except RuntimeError as e:
            logger.error(f"✗ CDP client property error: {e}")
            return False
        
        # Test navigation
        logger.info("\nTesting navigation...")
        try:
            await session._cdp_navigate("https://www.example.com")
            logger.info("✓ Navigation successful")
        except Exception as e:
            logger.error(f"✗ Navigation failed: {e}")
        
        return True
        
    except asyncio.TimeoutError:
        logger.error("✗ Browser start timed out")
        return False
    except Exception as e:
        logger.error(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Stop browser
        logger.info("\nStopping browser...")
        try:
            stop_event = session.event_bus.dispatch(BrowserStopEvent())
            await asyncio.wait_for(stop_event, timeout=5.0)
            logger.info("✓ Browser stopped")
        except asyncio.TimeoutError:
            logger.warning("Browser stop timed out")
        except Exception as e:
            logger.warning(f"Error stopping browser: {e}")

async def main():
    """Main function with proper cleanup."""
    success = await test_browser_lifecycle()
    
    # Give time for cleanup
    await asyncio.sleep(0.5)
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
