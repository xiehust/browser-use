#!/usr/bin/env python3
"""Test script to verify DOM building works."""

import asyncio
import logging
from browser_use import Browser

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_dom_building():
    """Test that DOM building works with pure CDP."""
    
    # Create browser
    browser = Browser()
    await browser.start()
    
    try:
        # Navigate to a simple page
        logger.info("Navigating to example.com...")
        await browser.session._cdp_navigate("https://www.example.com", browser.session.current_target_id)
        await asyncio.sleep(2)
        
        # Try to get the DOM state
        logger.info("Getting browser state...")
        state = await browser.session.get_browser_state_with_recovery()
        
        if state.dom_state and state.dom_state.selector_map:
            logger.info(f"✅ DOM built successfully! Found {len(state.dom_state.selector_map)} elements")
            # Print first few elements
            for idx, element in list(state.dom_state.selector_map.items())[:5]:
                logger.info(f"  Element {idx}: {element.node_name} - {element.xpath}")
        else:
            logger.error("❌ DOM state is empty!")
            
        logger.info(f"Page URL: {state.url}")
        logger.info(f"Page title: {state.title}")
        
    finally:
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_dom_building())