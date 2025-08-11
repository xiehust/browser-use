#!/usr/bin/env python3
"""Test that cdp_use logging is silenced."""

import asyncio
import logging
import sys

# Add the project to path
sys.path.insert(0, '/Users/squash/Local/Code/bu/browser-use')

# Import AFTER adding to path but BEFORE setting up logging
from browser_use import Agent
from tests.ci.conftest import create_mock_llm

# Now set up logging - this should silence cdp_use
logging.basicConfig(level=logging.INFO, format='%(levelname)-8s [%(name)s] %(message)s')

async def main():
    print("Creating agent...")
    agent = Agent(task="Test task", llm=create_mock_llm())
    
    print("Running agent...")
    await agent.run(max_steps=1)
    
    print("Closing agent...")
    await agent.close()
    
    print("✅ Agent closed successfully")

if __name__ == "__main__":
    asyncio.run(main())
    print("✅ Script exited cleanly")