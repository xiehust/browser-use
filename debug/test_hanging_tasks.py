#!/usr/bin/env python3
"""Debug script to find hanging tasks."""

import asyncio
import sys
import traceback
import logging

# Add the project to path
sys.path.insert(0, '/Users/squash/Local/Code/bu/browser-use')

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)-8s [%(name)s] %(message)s')
logger = logging.getLogger(__name__)

async def main():
    from browser_use import Agent
    from tests.ci.conftest import create_mock_llm
    
    logger.info("Creating agent...")
    agent = Agent(task="Test task", llm=create_mock_llm())
    
    try:
        logger.info("Running agent for 1 step...")
        await agent.run(max_steps=1)
        logger.info("Agent run completed")
    except Exception as e:
        logger.error(f"Error: {e}")
        traceback.print_exc()
    
    # Get all tasks before we start cleanup
    logger.info("\n=== Tasks BEFORE cleanup: ===")
    all_tasks = asyncio.all_tasks()
    for task in all_tasks:
        if task != asyncio.current_task():
            logger.info(f"Task: {task.get_name()}")
            # Get the coroutine info
            coro = task.get_coro()
            logger.info(f"  Coroutine: {coro}")
            # Get stack trace for the task
            stack = task.get_stack()
            if stack:
                logger.info(f"  Stack trace:")
                for frame in stack[:3]:  # First 3 frames
                    logger.info(f"    {frame.f_code.co_filename}:{frame.f_lineno} in {frame.f_code.co_name}")

if __name__ == "__main__":
    logger.info("=== Starting hanging task debug ===")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    finally:
        # Get remaining tasks
        pending = asyncio.all_tasks(loop)
        logger.info(f"\n=== {len(pending)} tasks still pending after main(): ===")
        for task in pending:
            logger.info(f"Pending task: {task.get_name()}: {task.get_coro()}")
            stack = task.get_stack()
            if stack:
                frame = stack[0]
                logger.info(f"  Blocked at: {frame.f_code.co_filename}:{frame.f_lineno} in {frame.f_code.co_name}")
        
        # Cancel all pending tasks
        for task in pending:
            task.cancel()
        
        # Wait for tasks to be cancelled
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        
        loop.close()
    
    logger.info("Script finished")