#!/usr/bin/env python3
"""Test script to verify agent shutdown is clean."""

import asyncio
import sys
import threading
import logging

# Add the project to path
sys.path.insert(0, '/Users/squash/Local/Code/bu/browser-use')

from browser_use import Agent
from tests.ci.conftest import create_mock_llm

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)-8s [%(name)s] %(message)s')
logger = logging.getLogger(__name__)

async def main():
    logger.info("Creating agent...")
    
    # Create agent with mock LLM
    llm = create_mock_llm()
    agent = Agent(task="Navigate to example.com", llm=llm)
    
    try:
        logger.info("Running simple task...")
        # Run the task
        await agent.run()
        
        logger.info("Agent task completed")
        
    except Exception as e:
        logger.error(f"Error during agent task: {e}")
        import traceback
        traceback.print_exc()
    finally:
        logger.info("Closing agent...")
        await agent.close()
        logger.info("Agent closed")
    
    # List remaining threads
    threads = threading.enumerate()
    logger.info(f"\n=== Remaining threads after agent.close() ({len(threads)}): ===")
    for t in threads:
        logger.info(f"  - {t.name} (daemon={t.daemon}, alive={t.is_alive()})")
    
    # List remaining asyncio tasks
    tasks = asyncio.all_tasks(asyncio.get_event_loop())
    other_tasks = [t for t in tasks if t != asyncio.current_task()]
    logger.info(f"\n=== Remaining asyncio tasks ({len(other_tasks)}): ===")
    for task in other_tasks[:10]:
        logger.info(f"  - {task.get_name()}: {task}")
    
    logger.info("\nShutdown complete")

if __name__ == "__main__":
    logger.info("=== Agent Shutdown Test ===")
    asyncio.run(main())
    logger.info("Script finished")