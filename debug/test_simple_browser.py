#!/usr/bin/env python3
"""Simple test to verify browser can launch and navigate."""

import asyncio
import logging
import os
from browser_use import Agent
from browser_use.llm import ChatOpenAI

# Set up logging  
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_simple_navigation():
    """Test basic navigation to Google."""
    
    # Initialize the LLM
    llm = ChatOpenAI(model="gpt-4o")
    
    # Create agent with simple task
    agent = Agent(
        task="Go to google.com and tell me what's on the page",
        llm=llm,
        max_steps=5,  # Limit steps
    )
    
    try:
        # Run the agent with a timeout
        result = await asyncio.wait_for(
            agent.run(),
            timeout=30.0  # 30 second timeout
        )
        
        logger.info(f"Task completed successfully!")
        logger.info(f"Final result: {result}")
        return True
        
    except asyncio.TimeoutError:
        logger.error("Task timed out after 30 seconds")
        return False
    
    except Exception as e:
        logger.error(f"Task failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_simple_navigation())
    exit(0 if success else 1)