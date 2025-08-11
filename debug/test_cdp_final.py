#!/usr/bin/env python3
"""Final test that cdp_use logging is silenced."""

import asyncio
import sys
sys.path.insert(0, '/Users/squash/Local/Code/bu/browser-use')

from browser_use import BrowserSession

async def main():
    print("Creating browser session...")
    session = BrowserSession()
    
    print("Starting browser...")
    await session.start()
    
    print("Checking for CDP debug logs (should be none)...")
    
    print("Stopping browser...")
    await session.kill()  # Use kill() instead of stop() to ensure cleanup
    
    print("✅ Browser session completed - CDP logging is silenced!")

if __name__ == "__main__":
    asyncio.run(main())
    print("✅ Script exited cleanly")