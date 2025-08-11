#!/usr/bin/env python3
"""Debug test to see what's running after agent completion."""

import asyncio
import threading
import sys
import os
import psutil
from browser_use import Agent
from browser_use.llm.openai.chat import ChatOpenAI


def show_process_info():
	"""Show current process and children."""
	print("\n" + "="*80)
	print("PROCESS TREE:")
	print("="*80)
	
	current = psutil.Process()
	print(f"Main process: PID={current.pid}, name={current.name()}")
	
	children = current.children(recursive=True)
	if children:
		print("Child processes:")
		for child in children:
			try:
				print(f"  - PID={child.pid}, name={child.name()}, status={child.status()}")
			except (psutil.NoSuchProcess, psutil.AccessDenied):
				pass
	else:
		print("No child processes")
	print("="*80 + "\n")


def show_threads():
	"""Show all threads."""
	print("\n" + "="*80)
	print("THREADS:")
	print("="*80)
	for thread in threading.enumerate():
		print(f"  - {thread.name} (daemon={thread.daemon})")
	print(f"Total: {threading.active_count()} threads")
	print("="*80 + "\n")


def show_tasks():
	"""Show asyncio tasks."""
	print("\n" + "="*80)
	print("ASYNCIO TASKS:")
	print("="*80)
	
	try:
		loop = asyncio.get_running_loop()
		all_tasks = asyncio.all_tasks(loop)
		
		pending = []
		for task in all_tasks:
			if not task.done():
				pending.append(task)
				print(f"  - {task.get_name()}")
				# Show coroutine details
				coro = task.get_coro()
				if hasattr(coro, '__qualname__'):
					print(f"    Coroutine: {coro.__qualname__}")
				elif hasattr(coro, '__name__'):
					print(f"    Coroutine: {coro.__name__}")
				else:
					print(f"    Coroutine: {coro}")
		
		print(f"Total: {len(pending)} pending / {len(all_tasks)} total")
	except RuntimeError:
		print("No event loop")
	
	print("="*80 + "\n")


async def main():
	"""Run agent and check what's left running."""
	
	print("Creating agent...")
	llm = ChatOpenAI(model="gpt-4o")
	agent = Agent(
		task="Immediately mark this task as done. No other actions.",
		llm=llm,
		max_steps=2,
	)
	
	print("Running agent...")
	try:
		result = await agent.run()
		print(f"\n✅ Agent completed: {result}\n")
	except Exception as e:
		print(f"\n❌ Agent failed: {e}\n")
	
	# Check what's running immediately after completion
	print("\n" + "="*80)
	print("IMMEDIATELY AFTER AGENT COMPLETION:")
	print("="*80)
	
	show_process_info()
	show_threads()
	show_tasks()
	
	# Try to access browser session
	if hasattr(agent, 'browser') and agent.browser:
		browser = agent.browser
		print("\nBrowser object exists")
		
		if hasattr(browser, '_browser_session'):
			session = browser._browser_session
			print(f"Browser session: {session}")
			
			# Check CDP client
			if hasattr(session, 'cdp_client'):
				print(f"CDP client: {session.cdp_client}")
				if session.cdp_client:
					print(f"  Connected: {session.cdp_client.connected if hasattr(session.cdp_client, 'connected') else 'unknown'}")
			
			# Check for subprocess
			if hasattr(session, '_browser_process'):
				print(f"Browser process: {session._browser_process}")
		
		# Try to close browser
		print("\nAttempting to close browser...")
		try:
			if hasattr(browser, 'close'):
				await browser.close()
				print("Browser closed")
			else:
				print("No close method on browser")
		except Exception as e:
			print(f"Error closing browser: {e}")
	
	# Wait a moment
	await asyncio.sleep(2)
	
	print("\n" + "="*80)
	print("AFTER ATTEMPTING CLEANUP:")
	print("="*80)
	
	show_process_info()
	show_threads()
	show_tasks()
	
	# Force cleanup of remaining tasks
	all_tasks = asyncio.all_tasks(asyncio.get_running_loop())
	current_task = asyncio.current_task()
	to_cancel = [t for t in all_tasks if t != current_task and not t.done()]
	
	if to_cancel:
		print(f"\nCancelling {len(to_cancel)} tasks...")
		for t in to_cancel:
			t.cancel()
		await asyncio.gather(*to_cancel, return_exceptions=True)
	
	print("\n✅ Done")


if __name__ == "__main__":
	if not os.environ.get('OPENAI_API_KEY'):
		print("Set OPENAI_API_KEY")
		sys.exit(1)
	
	try:
		asyncio.run(main())
		print("\nasyncio.run() returned")
	except Exception as e:
		print(f"\nError: {e}")
	
	print("\nFinal state:")
	show_threads()
	
	# Force exit
	print("\nForcing exit...")
	os._exit(0)