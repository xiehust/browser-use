#!/usr/bin/env python3
"""Test script to investigate why agent process hangs after completion."""

import asyncio
import threading
import sys
import os
from pathlib import Path

# Add browser-use to path
sys.path.insert(0, str(Path(__file__).parent))

from browser_use import Agent, Browser
from browser_use.llm.openai.chat import ChatOpenAI
import time


def print_active_threads():
	"""Print all active threads."""
	print("\n" + "="*80)
	print("ACTIVE THREADS:")
	print("="*80)
	for thread in threading.enumerate():
		print(f"  - {thread.name} (daemon={thread.daemon}, alive={thread.is_alive()})")
		if hasattr(thread, '_target') and thread._target:
			print(f"    Target: {thread._target}")
	print(f"Total active threads: {threading.active_count()}")
	print("="*80 + "\n")


def print_asyncio_tasks():
	"""Print all pending asyncio tasks."""
	print("\n" + "="*80)
	print("PENDING ASYNCIO TASKS:")
	print("="*80)
	
	try:
		loop = asyncio.get_running_loop()
		all_tasks = asyncio.all_tasks(loop)
		
		for task in all_tasks:
			if not task.done():
				print(f"  - Task: {task.get_name()}")
				print(f"    State: {task._state}")
				if hasattr(task, 'get_coro'):
					coro = task.get_coro()
					print(f"    Coroutine: {coro}")
				if hasattr(task, 'get_stack'):
					stack = task.get_stack()
					if stack:
						frame = stack[0]
						print(f"    Location: {frame.f_code.co_filename}:{frame.f_lineno} in {frame.f_code.co_name}")
		
		pending_count = sum(1 for task in all_tasks if not task.done())
		print(f"Total pending tasks: {pending_count}/{len(all_tasks)}")
	except RuntimeError:
		print("No asyncio event loop running")
	
	print("="*80 + "\n")


async def test_agent_immediate_done():
	"""Test an agent that immediately marks the task as done."""
	
	print("\n" + "="*80)
	print("STARTING AGENT TEST")
	print("="*80 + "\n")
	
	# Print initial state
	print("Initial state:")
	print_active_threads()
	print_asyncio_tasks()
	
	# Create browser and agent
	browser = Browser()
	
	# Use OpenAI model
	llm = ChatOpenAI(model="gpt-4o")
	
	agent = Agent(
		task="Immediately mark this task as done. Do not perform any other actions, just call done() right away.",
		llm=llm,
		browser=browser,
		max_steps=5,  # Limit steps to be safe
	)
	
	print("\nRunning agent...")
	start_time = time.time()
	
	# Run the agent
	try:
		result = await agent.run()
		print(f"\nAgent completed in {time.time() - start_time:.2f} seconds")
		print(f"Result: {result}")
	except Exception as e:
		print(f"Agent failed with error: {e}")
		import traceback
		traceback.print_exc()
	
	print("\n" + "="*80)
	print("AFTER AGENT RUN - CHECKING WHAT'S STILL ACTIVE")
	print("="*80 + "\n")
	
	# Check what's still running
	print_active_threads()
	print_asyncio_tasks()
	
	# Try to close the browser
	print("\nClosing browser...")
	try:
		await browser.close()
		print("Browser closed successfully")
	except Exception as e:
		print(f"Error closing browser: {e}")
	
	# Give a moment for cleanup
	await asyncio.sleep(1)
	
	print("\n" + "="*80)
	print("AFTER BROWSER CLOSE - FINAL STATE")
	print("="*80 + "\n")
	
	print_active_threads()
	print_asyncio_tasks()
	
	# Check if there are any browser service instances
	if hasattr(browser, '_browser_service'):
		service = browser._browser_service
		print(f"\nBrowser service state:")
		print(f"  - Service exists: {service is not None}")
		if service:
			if hasattr(service, '_playwright'):
				print(f"  - Playwright: {service._playwright}")
			if hasattr(service, '_browser'):
				print(f"  - Browser: {service._browser}")
			if hasattr(service, '_context'):
				print(f"  - Context: {service._context}")
	
	print("\n" + "="*80)
	print("TEST COMPLETE - Process should exit now...")
	print("="*80 + "\n")
	
	# Try to cancel any remaining tasks
	all_tasks = asyncio.all_tasks(asyncio.get_running_loop())
	current_task = asyncio.current_task()
	tasks_to_cancel = [task for task in all_tasks if task != current_task and not task.done()]
	
	if tasks_to_cancel:
		print(f"\nCancelling {len(tasks_to_cancel)} remaining tasks...")
		for task in tasks_to_cancel:
			task.cancel()
		
		# Wait for cancellations to complete
		await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
		print("Tasks cancelled")


def main():
	"""Main entry point."""
	# Set up API key if needed
	if not os.environ.get('OPENAI_API_KEY'):
		print("Please set OPENAI_API_KEY environment variable")
		sys.exit(1)
	
	try:
		# Run the async test
		asyncio.run(test_agent_immediate_done())
		print("\nasyncio.run() completed")
	except KeyboardInterrupt:
		print("\n\nInterrupted by user")
	except Exception as e:
		print(f"\n\nUnexpected error: {e}")
		import traceback
		traceback.print_exc()
	
	# Final check of threads before exit
	print("\nFinal thread check before exit:")
	print_active_threads()
	
	print("\nExiting main()...")
	
	# Force exit if needed
	import time
	time.sleep(2)
	if threading.active_count() > 1:
		print(f"\n⚠️  WARNING: {threading.active_count()} threads still active, forcing exit")
		os._exit(0)


if __name__ == "__main__":
	main()