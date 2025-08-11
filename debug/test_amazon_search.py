#!/usr/bin/env python3
"""Test script to search for laptops on Amazon and find the cheapest one."""

import asyncio
import logging
from browser_use import Agent
from browser_use.browser import BrowserSession, BrowserConfig
from langchain_openai import ChatOpenAI

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_amazon_search():
    """Test searching for laptops on Amazon."""
    
    # Initialize the LLM
    llm = ChatOpenAI(model="gpt-4o")
    
    # Create browser config with headful mode for debugging
    browser_config = BrowserConfig(
        headless=False,  # Show browser for debugging
    )
    
    # Create browser session
    browser_session = BrowserSession(browser_config=browser_config)
    
    # Create agent
    agent = Agent(
        task="Go to amazon.com, search for 'laptop', and find the cheapest listing that isn't an ad. Open it in a new tab.",
        llm=llm,
        browser_session=browser_session,
        max_steps=20,  # Limit steps to avoid infinite loops
    )
    
    try:
        # Run the agent with a timeout
        result = await asyncio.wait_for(
            agent.run(),
            timeout=120.0  # 2 minute timeout
        )
        
        logger.info(f"Task completed successfully!")
        logger.info(f"Final result: {result}")
        
    except asyncio.TimeoutError:
        logger.error("Task timed out after 120 seconds")
        # Try to get current state
        try:
            state = await browser_session.get_browser_state_summary()
            logger.info(f"Current URL: {state.url}")
            logger.info(f"Current page has {len(state.dom.tree) if state.dom else 0} elements")
        except Exception as e:
            logger.error(f"Could not get browser state: {e}")
    
    except Exception as e:
        logger.error(f"Task failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        await browser_session.close()

if __name__ == "__main__":
    asyncio.run(test_amazon_search())
