#!/usr/bin/env python3

"""
Test script for multiple screenshots functionality.
"""

import asyncio
from browser_use import Agent
from browser_use.llm import ChatOpenAI


async def main():
    """Test the multiple screenshots feature"""
    
    # Create an agent with num_screenshots=2 (should include current + 1 from history)
    agent = Agent(
        task="Navigate to google.com and take a few steps to test multiple screenshots",
        llm=ChatOpenAI(model="gpt-4o"),
        num_screenshots=2,  # This should include 2 screenshots in the input message
        headless=True,
    )
    
    print("🧪 Testing multiple screenshots functionality...")
    print(f"📷 Configured to use {agent.settings.num_screenshots} screenshots")
    
    # Run the agent for just a few steps to test the functionality
    try:
        history = await agent.run(max_steps=3)
        print("✅ Test completed successfully!")
        print(f"📊 Total steps: {history.number_of_steps()}")
        print(f"📷 Screenshots captured: {len([s for s in history.screenshots() if s])}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())