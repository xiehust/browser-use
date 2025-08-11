#!/usr/bin/env python3
"""Test simple browser session shutdown."""

import asyncio
import sys
import time

async def test_simple_shutdown():
    """Test that browser session shuts down cleanly."""
    from browser_use.browser.session import BrowserSession
    
    start_time = time.time()
    print("Creating browser session...")
    
    session = BrowserSession()
    
    print("Starting browser session...")
    await session.start()
    
    print("Browser started, waiting 2 seconds...")
    await asyncio.sleep(2)
    
    print("Stopping browser session...")
    await session.stop()
    
    print("Browser stopped!")
    elapsed = time.time() - start_time
    print(f"Total time: {elapsed:.2f} seconds")
    
    # Give a moment for any cleanup
    await asyncio.sleep(0.5)
    print("Done waiting for cleanup")

if __name__ == "__main__":
    print("Testing simple browser shutdown...")
    asyncio.run(test_simple_shutdown())
    print("Script exited cleanly!")
    sys.exit(0)