#!/usr/bin/env python3
"""
Test script to verify the three-column CLI layout is working correctly.
Run with: python test_three_column_cli.py
"""

import os
import sys
import asyncio
import logging

# Enable debug logging to see all messages
os.environ['BROWSER_USE_LOGGING_LEVEL'] = 'debug'

# Run the CLI with a simple task
if __name__ == '__main__':
	print("Testing three-column CLI layout...")
	print("1. Main output should appear in left column")
	print("2. Browser events should appear in center column")
	print("3. CDP messages should appear in right column")
	print("\nStarting CLI in 3 seconds...")
	
	import time
	time.sleep(3)
	
	# Import and run the CLI
	from browser_use.cli import cli
	
	# Run with a simple task to test
	sys.argv = ['browser-use']
	cli()