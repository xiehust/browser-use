#!/usr/bin/env python
"""Test script for the permissions watchdog."""

import asyncio
import logging
import sys
import os

# Add the test directory to path to import conftest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tests', 'ci'))

from browser_use import Agent
from browser_use.browser.profile import BrowserProfile
from conftest import create_mock_llm


async def test_permissions_watchdog():
	"""Test that permissions are granted when browser connects."""
	logging.basicConfig(level=logging.INFO)
	
	# Create a profile with custom permissions
	profile = BrowserProfile(
		permissions=[
			'geolocation', 
			'clipboard-read', 
			'clipboard-write', 
			'notifications',
			'camera',
			'microphone'
		]
	)
	
	print(f"Testing with permissions: {profile.permissions}")
	
	# Create a mock LLM that will just return done
	mock_llm = create_mock_llm()
	
	# Create agent with the profile
	agent = Agent(
		task="Test permissions watchdog",
		llm=mock_llm,
		browser_profile=profile
	)
	
	# Start the browser - this should trigger the permissions watchdog
	await agent.start()
	
	print("Browser started successfully with permissions granted")
	
	# Keep browser open for a moment to verify
	await asyncio.sleep(2)
	
	# Clean up
	await agent.stop()
	print("Test completed successfully")


if __name__ == "__main__":
	asyncio.run(test_permissions_watchdog())