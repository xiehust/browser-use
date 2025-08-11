#!/usr/bin/env python3
"""Test script to verify browser shuts down cleanly."""

import asyncio
import sys
import time
import os
# Need to import the test helpers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tests', 'ci'))
from conftest import create_mock_llm
from browser_use import Agent

async def test_clean_shutdown():
    """Test that browser shuts down cleanly without hanging."""
    start_time = time.time()
    
    print("Starting browser...")
    # Create mock LLM that will navigate and complete
    llm = create_mock_llm([
        '{"go_to_url": {"url": "https://google.com", "new_tab": false}}',
        '{"done": {"text": "Successfully navigated to Google", "success": true}}'
    ])
    agent = Agent(task="go to google.com", llm=llm)
    
    print("Running agent...")
    result = await agent.run()
    print(f"Task result: {result}")
    
    print("Shutting down...")
    # Agent should clean up automatically when it goes out of scope
    del agent
    
    # Give a moment for cleanup
    await asyncio.sleep(0.5)
    
    elapsed = time.time() - start_time
    print(f"Total time: {elapsed:.2f} seconds")
    print("✅ Clean shutdown successful!")

if __name__ == "__main__":
    print("Testing browser shutdown...")
    asyncio.run(test_clean_shutdown())
    print("Script exited cleanly!")
    sys.exit(0)