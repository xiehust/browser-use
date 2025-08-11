#!/usr/bin/env python3
"""Simple test to check what keeps the agent process alive."""

import asyncio
import threading
import signal
import sys
import os
from browser_use import Agent
from browser_use.llm.openai.chat import ChatOpenAI


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
	"""Print all pending asyncio tasks with details."""
	print("\n" + "="*80)
	print("PENDING ASYNCIO TASKS:")
	print("="*80)
	
	try:
		loop = asyncio.get_running_loop()
		all_tasks = asyncio.all_tasks(loop)
		
		for i, task in enumerate(all_tasks, 1):
			if not task.done():
				print(f"\n  Task #{i}: {task.get_name()}")
				
				# Get coroutine info
				coro = task.get_coro()
				print(f"    Coroutine: {coro}")
				print(f"    Done: {task.done()}, Cancelled: {task.cancelled()}")
				
				# Get stack trace
				stack = task.get_stack()
				if stack:
					print("    Stack trace:")
					for frame in stack[:3]:  # Show top 3 frames
						print(f"      {frame.f_code.co_filename}:{frame.f_lineno} in {frame.f_code.co_name}")
		
		pending_count = sum(1 for task in all_tasks if not task.done())
		print(f"\nTotal: {pending_count} pending / {len(all_tasks)} total tasks")
	except RuntimeError:
		print("No asyncio event loop running")
	
	print("="*80 + "\n")


async def run_agent_with_timeout():
	"""Run agent and interrupt after 30 seconds."""
	
	print("Starting agent...")
	
	# Create and run agent
	llm = ChatOpenAI(model="gpt-4o")
	agent = Agent(
		task="Immediately mark this task as done. Do not perform any other actions, just call done() right away.",
		llm=llm,
		max_steps=5,
	)
	
	# Run agent in background task
	agent_task = asyncio.create_task(agent.run())
	
	try:
		# Wait for agent to complete or timeout
		result = await asyncio.wait_for(agent_task, timeout=30)
		print(f"\n✅ Agent completed normally: {result}")
	except asyncio.TimeoutError:
		print("\n⏰ 30 second timeout reached - agent still running")
	
	# Wait a bit for any cleanup
	await asyncio.sleep(2)
	
	print("\n" + "="*80)
	print("ANALYZING WHAT'S STILL RUNNING AFTER AGENT COMPLETION/TIMEOUT:")
	print("="*80)
	
	print_active_threads()
	print_asyncio_tasks()
	
	# Try to cancel remaining tasks
	all_tasks = asyncio.all_tasks(asyncio.get_running_loop())
	current_task = asyncio.current_task()
	tasks_to_cancel = [task for task in all_tasks if task != current_task and not task.done()]
	
	if tasks_to_cancel:
		print(f"\n🚫 Cancelling {len(tasks_to_cancel)} remaining tasks...")
		for task in tasks_to_cancel:
			print(f"  Cancelling: {task.get_name()}")
			task.cancel()
		
		# Wait for cancellations
		results = await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
		for task, result in zip(tasks_to_cancel, results):
			if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
				print(f"  Task {task.get_name()} raised: {result}")
	
	print("\nFinal check after cancellation:")
	print_active_threads()
	print_asyncio_tasks()


def main():
	"""Main entry point."""
	if not os.environ.get('OPENAI_API_KEY'):
		print("Please set OPENAI_API_KEY environment variable")
		sys.exit(1)
	
	try:
		asyncio.run(run_agent_with_timeout())
		print("\n✅ asyncio.run() completed normally")
	except KeyboardInterrupt:
		print("\n⚠️ Interrupted by user")
	except Exception as e:
		print(f"\n❌ Error: {e}")
		import traceback
		traceback.print_exc()
	
	print("\n" + "="*80)
	print("FINAL CHECK BEFORE EXIT:")
	print("="*80)
	print_active_threads()
	
	# Exit immediately
	print("\n🔚 Forcing exit...")
	os._exit(0)


if __name__ == "__main__":
	main()