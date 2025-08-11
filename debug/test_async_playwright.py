#!/usr/bin/env python3
"""Test if async playwright starts properly."""

import asyncio
from playwright.async_api import async_playwright

async def test_async_playwright():
    print("Starting async playwright...")
    try:
        playwright = await asyncio.wait_for(
            async_playwright().start(),
            timeout=5.0
        )
        print(f"Playwright started successfully")
        print(f"Chromium path: {playwright.chromium.executable_path}")
        await playwright.stop()
        print("Playwright stopped")
        return True
    except asyncio.TimeoutError:
        print("ERROR: Playwright start timed out after 5 seconds")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_async_playwright())
    exit(0 if success else 1)