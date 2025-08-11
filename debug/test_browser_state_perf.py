#!/usr/bin/env python3
"""Test browser state calculation performance."""

import asyncio
import logging
import time
from browser_use.browser.session import BrowserSession
from browser_use.browser.events import BrowserStartEvent, BrowserStopEvent, BrowserStateRequestEvent

logging.basicConfig(level=logging.INFO, format='%(levelname)-8s %(message)s')
logger = logging.getLogger(__name__)

async def test_browser_state_performance():
    """Test browser state calculation performance."""
    
    session = BrowserSession()
    
    try:
        # Start browser
        logger.info("Starting browser...")
        start_event = session.event_bus.dispatch(BrowserStartEvent())
        await asyncio.wait_for(start_event, timeout=10.0)
        logger.info("✓ Browser started")
        
        # Wait for initial setup
        await asyncio.sleep(1)
        
        # Test browser state calculation
        logger.info("\nTesting browser state calculation...")
        start_time = time.time()
        
        # Request browser state
        state_event = session.event_bus.dispatch(BrowserStateRequestEvent(
            include_dom=True,
            include_screenshot=False
        ))
        
        # Wait for state with timeout
        try:
            result = await asyncio.wait_for(state_event.event_result(), timeout=5.0)
            elapsed = time.time() - start_time
            logger.info(f"✓ Browser state calculated in {elapsed:.2f} seconds")
            
            if result:
                logger.info(f"  - URL: {result.url}")
                logger.info(f"  - Tabs: {len(result.tabs)}")
                logger.info(f"  - DOM elements: {len(result.dom_state.selector_map) if result.dom_state else 0}")
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            logger.error(f"✗ Browser state calculation timed out after {elapsed:.2f} seconds")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Stop browser
        logger.info("\nStopping browser...")
        try:
            # Use BrowserKillEvent for immediate termination
            from browser_use.browser.events import BrowserKillEvent
            kill_event = session.event_bus.dispatch(BrowserKillEvent())
            await asyncio.wait_for(kill_event, timeout=2.0)
            logger.info("✓ Browser stopped")
        except asyncio.TimeoutError:
            logger.warning("Browser stop timed out")
        except Exception as e:
            logger.warning(f"Error stopping browser: {e}")

async def main():
    """Main function with proper cleanup."""
    success = await test_browser_state_performance()
    
    # Give time for cleanup
    await asyncio.sleep(0.5)
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)