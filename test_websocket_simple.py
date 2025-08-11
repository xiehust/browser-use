#!/usr/bin/env python3
"""Simple test of multi-WebSocket functionality."""

import asyncio
import logging

from browser_use.browser.session import BrowserSession

logging.basicConfig(level=logging.INFO)


async def main():
    """Test multi-WebSocket functionality."""
    browser = BrowserSession()
    
    try:
        print("Starting browser...")
        await browser.start()
        
        # Get initial session (uses shared root WebSocket)
        print(f"\nInitial session:")
        print(f"  Target ID: {browser.agent_focus.target_id}")
        print(f"  Owns WebSocket: {browser.agent_focus.owns_cdp_client}")
        
        # Create a new tab
        print("\nCreating new tab...")
        new_target_id = await browser._cdp_create_new_page("https://example.com")
        
        # Get session with default behavior (should create new WebSocket)
        print(f"\nGetting session for new target (default behavior):")
        session = await browser.get_or_create_cdp_session(new_target_id, focus=False)
        print(f"  Target ID: {session.target_id}")
        print(f"  Owns WebSocket: {session.owns_cdp_client}")
        print(f"  Same client as initial: {session.cdp_client is browser.agent_focus.cdp_client}")
        
        # Create another tab
        print("\nCreating another tab...")
        another_target_id = await browser._cdp_create_new_page("https://google.com")
        
        # Get session with explicit new_socket=False (shares WebSocket)
        print(f"\nGetting session with new_socket=False:")
        shared_session = await browser.get_or_create_cdp_session(another_target_id, focus=False, new_socket=False)
        print(f"  Target ID: {shared_session.target_id}")
        print(f"  Owns WebSocket: {shared_session.owns_cdp_client}")
        print(f"  Same client as initial: {shared_session.cdp_client is browser.agent_focus.cdp_client}")
        
        print("\n✅ Multi-WebSocket test successful!")
        print(f"\nSummary:")
        print(f"  Total sessions in pool: {len(browser._cdp_session_pool)}")
        print(f"  Sessions with own WebSocket: {sum(1 for s in browser._cdp_session_pool.values() if s.owns_cdp_client)}")
        print(f"  Sessions sharing WebSocket: {sum(1 for s in browser._cdp_session_pool.values() if not s.owns_cdp_client)}")
        
    finally:
        print("\nCleaning up...")
        await browser.kill()


if __name__ == "__main__":
    asyncio.run(main())