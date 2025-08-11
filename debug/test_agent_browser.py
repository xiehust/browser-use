#!/usr/bin/env python3
"""Test browser launch with Agent."""

import asyncio
import logging
from browser_use import Agent
from browser_use.llm import ChatOpenAI

# Set up logging with debug level
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)-8s [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)

async def test_agent_browser():
    """Test browser launch via Agent."""
    
    logger.info("Creating agent...")
    
    # Use a simple model
    llm = ChatOpenAI(model="gpt-4o-mini")
    
    agent = Agent(
        task="Go to google.com",
        llm=llm,
    )
    
    try:
        logger.info("Running agent...")
        result = await agent.run()
        logger.info(f"Agent result: {result}")
        return True
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_agent_browser())
    exit(0 if success else 1)