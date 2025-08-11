#!/usr/bin/env python3
"""Test script to verify CDP navigation is working."""

import asyncio
import logging
from browser_use import Agent, Browser
from langchain_openai import ChatOpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_navigation():
    """Test that navigation works with pure CDP."""
    
    # Create browser and agent
    browser = Browser()
    
    # Simple LLM for testing
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    agent = Agent(
        task="Navigate to https://www.example.com and tell me the page title",
        llm=llm,
        browser=browser
    )
    
    # Run the agent
    result = await agent.run()
    
    logger.info(f"Agent result: {result}")
    
    # Also test direct navigation
    logger.info("Testing direct navigation...")
    await browser.session._cdp_navigate("https://www.google.com", browser.session.current_target_id)
    await asyncio.sleep(2)
    
    # Get current URL
    current_url = await browser.session.get_current_page_url()
    logger.info(f"Current URL after navigation: {current_url}")
    
    # Clean up
    await browser.close()
    
    return result

if __name__ == "__main__":
    asyncio.run(test_navigation())