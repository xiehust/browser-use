#!/usr/bin/env python3
"""Test script to verify visual highlighting works with CDP."""

import asyncio
import logging
from browser_use import Browser

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_highlighting():
    """Test that visual highlighting works with pure CDP."""
    
    # Create browser
    browser = Browser()
    await browser.start()
    
    try:
        # Navigate to a page with interactive elements
        logger.info("Navigating to example.com...")
        await browser.session._cdp_navigate("https://www.example.com", browser.session.current_target_id)
        await asyncio.sleep(3)
        
        # Get the browser state - this should trigger highlighting
        logger.info("Getting browser state (should inject highlights)...")
        state = await browser.session.get_browser_state_with_recovery()
        
        if state.dom_state and state.dom_state.selector_map:
            logger.info(f"✅ DOM built with {len(state.dom_state.selector_map)} elements")
            logger.info("✨ Visual highlights should now be visible on the page!")
            
            # Print some highlighted elements
            for idx, element in list(state.dom_state.selector_map.items())[:5]:
                logger.info(f"  Highlighted [{idx}]: {element.node_name} - {element.xpath}")
        else:
            logger.error("❌ DOM state is empty!")
            
        logger.info(f"Page URL: {state.url}")
        logger.info(f"Page title: {state.title}")
        
        # Wait to see the highlights
        logger.info("Waiting 10 seconds to observe highlights...")
        await asyncio.sleep(10)
        
        # Test removing highlights
        logger.info("Removing highlights...")
        await browser.session.remove_highlights()
        
        logger.info("Waiting 5 seconds to observe removal...")
        await asyncio.sleep(5)
        
    finally:
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_highlighting())