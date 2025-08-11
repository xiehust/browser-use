#!/usr/bin/env python3
"""Test script to debug shutdown issues with thread tracking."""

import asyncio
import sys
import threading
import logging

# Add the project to path
sys.path.insert(0, '/Users/squash/Local/Code/bu/browser-use')

from browser_use.browser.session import BrowserSession

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)-8s [%(name)s] %(message)s')
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting browser session...")
    
    # Create browser session
    session = BrowserSession()
    
    try:
        # Start the browser
        await session.start()
        logger.info("Browser started successfully")
        
        # Wait a moment for everything to initialize
        await asyncio.sleep(2)
        
        logger.info("Closing browser session...")
        # Close the session
        await session.kill()
        logger.info("Browser session closed")
        
    except Exception as e:
        logger.error(f"Error during browser session: {e}")
        import traceback
        traceback.print_exc()
    
    # List remaining threads
    threads = threading.enumerate()
    logger.info(f"\n=== Remaining threads after close ({len(threads)}): ===")
    for t in threads:
        logger.info(f"  - {t.name} (daemon={t.daemon}, alive={t.is_alive()})")
    
    # List remaining asyncio tasks
    tasks = asyncio.all_tasks(asyncio.get_event_loop())
    other_tasks = [t for t in tasks if t != asyncio.current_task()]
    logger.info(f"\n=== Remaining asyncio tasks ({len(other_tasks)}): ===")
    for task in other_tasks[:10]:
        logger.info(f"  - {task.get_name()}: {task}")
    
    logger.info("\nShutdown complete")

if __name__ == "__main__":
    logger.info("=== Browser Session Shutdown Test ===")
    asyncio.run(main())
    logger.info("Script finished")