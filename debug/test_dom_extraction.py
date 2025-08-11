#!/usr/bin/env python3
"""Test DOM extraction directly."""

import asyncio
import logging
from browser_use.browser import BrowserSession
from browser_use.browser.events import BrowserStartEvent

# Set up logging  
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_dom_extraction():
    """Test DOM extraction on Amazon."""
    
    session = BrowserSession()
    
    try:
        # Start browser via event
        await session.on_BrowserStartEvent(BrowserStartEvent())
        logger.info("Browser started")
        
        # Wait a moment for browser to stabilize
        await asyncio.sleep(2)
        
        # Navigate to Amazon using CDP
        logger.info("Navigating to Amazon...")
        await session._cdp_navigate("https://www.amazon.com")
        
        # Wait for navigation
        await asyncio.sleep(5)
        
        # Get current page info
        url = await session.get_current_page_url()
        title = await session.get_current_page_title()
        
        logger.info(f"Current URL: {url}")
        logger.info(f"Current title: {title}")
        
        # Try to get DOM
        logger.info("Getting DOM tree...")
        from browser_use.dom.service import DomService
        dom_service = DomService(session)
        
        # Get DOM with timeout
        try:
            dom_result = await asyncio.wait_for(
                dom_service.get_dom_tree_state(),
                timeout=10.0
            )
            logger.info(f"Got DOM result: {len(dom_result[0].text) if dom_result else 0} chars")
        except asyncio.TimeoutError:
            logger.error("DOM extraction timed out after 10 seconds")
            return False
        
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
    success = asyncio.run(test_dom_extraction())
    exit(0 if success else 1)