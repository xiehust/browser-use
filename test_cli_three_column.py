#!/usr/bin/env python3
"""
Test the three-column CLI layout to verify:
1. Agent output appears in left column
2. Browser events appear in center column without duplicates
3. CDP messages appear in right column with debug messages

Run with: python test_cli_three_column.py
"""

import asyncio
import logging
import os
import sys

# Enable debug logging
os.environ['BROWSER_USE_LOGGING_LEVEL'] = 'debug'
# CDP debug is now enabled at module import time in cli.py

async def test_cli():
	"""Test the CLI with a simple task"""
	from browser_use.cli import BrowserUseApp
	from browser_use.config import Config
	
	print("Testing three-column CLI layout...")
	print("Expected behavior:")
	print("1. Left column: Agent output and logs")
	print("2. Center column: Browser events (no duplicates)")
	print("3. Right column: CDP debug messages")
	print("\nLaunching CLI...")
	
	# Create and run the app
	config = Config()
	app = BrowserUseApp(config)
	
	# Run the app
	await app.run_async()

if __name__ == '__main__':
	# Run the test
	try:
		asyncio.run(test_cli())
	except KeyboardInterrupt:
		print("\nTest interrupted by user")
		sys.exit(0)