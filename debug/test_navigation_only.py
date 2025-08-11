#!/usr/bin/env python3
"""Test navigation directly without agent."""

import asyncio
import logging
from browser_use.browser import BrowserSession

# Set up logging  
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_navigation():
    """Test basic navigation directly."""
    
    session = BrowserSession()
    
    try:
        # Start browser via event
        from browser_use.browser.events import BrowserStartEvent
        await session.on_BrowserStartEvent(BrowserStartEvent())
        logger.info("Browser started")
        
        # Wait a moment for browser to stabilize
        await asyncio.sleep(2)
        
        # Navigate to Amazon using CDP
        logger.info("Navigating to Amazon...")
        await session._cdp_navigate("https://www.amazon.com")
        
        # Wait for navigation
        await asyncio.sleep(3)
        
        # Get current page info
        url = await session.get_current_page_url()
        title = await session.get_current_page_title()
        
        logger.info(f"Current URL: {url}")
        logger.info(f"Current title: {title}")
        logger.info(f"Current target ID: {session.current_target_id}")
        
        # Get all targets
        if session.cdp_client:
            targets = await session.cdp_client.send.Target.getTargets()
            logger.info(f"All targets: {len(targets.get('targetInfos', []))} targets")
            for i, target in enumerate(targets.get('targetInfos', [])):
                is_current = " (CURRENT)" if target.get('targetId') == session.current_target_id else ""
                logger.info(f"  Target {i}: {target.get('url')[:50]}... (ID: {target.get('targetId')[:8]}...){is_current}")
        
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
    success = asyncio.run(test_navigation())
    exit(0 if success else 1)