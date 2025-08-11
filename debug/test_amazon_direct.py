#!/usr/bin/env python3
"""Direct test of Amazon navigation."""

import asyncio
import logging
from browser_use import Agent
from browser_use.llm import ChatOpenAI

# Set up detailed logging  
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_amazon():
    """Test Amazon navigation directly."""
    
    # Initialize the LLM
    llm = ChatOpenAI(model="gpt-4o")
    
    # Create agent with Amazon task
    agent = Agent(
        task='Go to amazon.com, search for "laptop", and tell me the first product you see',
        llm=llm,
        max_steps=10,  # Allow more steps for Amazon
    )
    
    try:
        # Run the agent with a timeout
        result = await asyncio.wait_for(
            agent.run(),
            timeout=60.0  # 60 second timeout for Amazon
        )
        
        logger.info(f"Task completed successfully!")
        logger.info(f"Final result: {result}")
        return True
        
    except asyncio.TimeoutError:
        logger.error("Task timed out after 60 seconds")
        # Try to get the current state
        try:
            session = agent.browser_session
            url = await session.get_current_page_url()
            logger.info(f"Current URL: {url}")
            logger.info(f"Current target ID: {session.current_target_id}")
            
            # Get all targets
            if session.cdp_client:
                targets = await session.cdp_client.send.Target.getTargets()
                logger.info(f"All targets: {len(targets.get('targetInfos', []))} targets")
                for i, target in enumerate(targets.get('targetInfos', [])):
                    logger.info(f"  Target {i}: {target.get('url')} (ID: {target.get('targetId')[:8]}...)")
        except Exception as e:
            logger.error(f"Could not get browser state: {e}")
        return False
    
    except Exception as e:
        logger.error(f"Task failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_amazon())
    exit(0 if success else 1)