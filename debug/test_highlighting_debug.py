#!/usr/bin/env python3
"""Debug script to test DOM highlighting functionality."""

import asyncio
import logging
from browser_use.browser.session import BrowserSession
from browser_use.browser.profile import BrowserProfile

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def main():
    """Test highlighting on a simple page."""
    profile = BrowserProfile(headless=False)
    session = BrowserSession(browser_profile=profile)
    
    try:
        # Start the browser session
        await session.start()
        
        # Navigate to a simple page
        await session.go_to_url("https://example.com")
        await asyncio.sleep(2)
        
        # Get browser state (this should trigger highlighting)
        logger.info("Getting browser state (should trigger highlighting)...")
        state = await session.get_state()
        
        # Log info about the DOM
        if state.dom_state and state.dom_state.selector_map:
            logger.info(f"Found {len(state.dom_state.selector_map)} interactive elements")
            # Log first few elements
            for idx, (key, node) in enumerate(list(state.dom_state.selector_map.items())[:5]):
                logger.info(f"  [{key}] {node.node_name}: {node.get_all_children_text()[:50] if hasattr(node, 'get_all_children_text') else 'N/A'}")
        else:
            logger.warning("No interactive elements found!")
        
        # Keep browser open to visually inspect
        logger.info("Browser is open. Check if highlighting is visible (blue outlines with numbers).")
        logger.info("Press Enter to close...")
        input()
        
    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(main())