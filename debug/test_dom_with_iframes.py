#!/usr/bin/env python3
"""Test DOM building with iframe hierarchy."""

import asyncio
import logging
from browser_use.browser.session import BrowserSession
from browser_use.dom.service import DomService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-8s [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)

async def test_dom_with_iframes():
    """Test DOM building with nested iframes."""
    
    logger.info("Creating browser session...")
    session = BrowserSession()
    
    try:
        logger.info("Starting browser...")
        from browser_use.browser.events import BrowserStartEvent, BrowserStopEvent
        
        # Start the browser
        event = session.event_bus.dispatch(BrowserStartEvent())
        await event
        logger.info("Browser started!")
        
        # Navigate to a page with iframes (Google typically has some)
        logger.info("Navigating to google.com...")
        await session._cdp_navigate("https://www.google.com")
        await asyncio.sleep(2)  # Wait for page to load
        
        # Try to build DOM tree
        logger.info("Building DOM tree...")
        dom_service = DomService(session)
        
        try:
            # Get the serialized DOM
            dom_state, dom_tree, timing = await dom_service.get_serialized_dom_tree()
            
            logger.info(f"DOM tree built successfully!")
            logger.info(f"  - Total elements: {len(dom_state.selector_map)}")
            logger.info(f"  - Visible elements: {sum(1 for e in dom_state.selector_map.values() if e.is_visible)}")
            logger.info(f"  - Timing: {timing}")
            
            # Check if we found any iframes
            iframe_count = sum(1 for e in dom_state.selector_map.values() if 'iframe' in e.node_name.lower())
            logger.info(f"  - Iframes found: {iframe_count}")
            
            # Print some sample elements
            for i, (idx, elem) in enumerate(list(dom_state.selector_map.items())[:5]):
                logger.info(f"  Element {idx}: <{elem.node_name}> visible={elem.is_visible}")
            
            return True
            
        except Exception as e:
            logger.error(f"DOM building failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        logger.info("Stopping browser...")
        stop_event = session.event_bus.dispatch(BrowserStopEvent())
        await asyncio.wait_for(stop_event, timeout=5.0)
        logger.info("Browser stopped")

if __name__ == "__main__":
    success = asyncio.run(test_dom_with_iframes())
    exit(0 if success else 1)