#!/usr/bin/env python3
"""Test script to verify screenshot capturing in agent steps."""

import asyncio
import logging
from pathlib import Path

from browser_use import Agent
from browser_use.browser import Browser
from langchain_openai import ChatOpenAI

# Configure logging to see debug output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_screenshot_capture():
	"""Test that screenshots are captured even without vision enabled."""
	
	# Create a temporary directory for output
	output_dir = Path("test_output")
	output_dir.mkdir(exist_ok=True)
	
	# Initialize browser
	browser = Browser(headless=False)
	
	# Initialize LLM (you can use a mock LLM here for testing)
	llm = ChatOpenAI(model="gpt-4o-mini")
	
	# Create agent with cloud sync but without vision
	agent = Agent(
		task="Navigate to example.com and take a screenshot",
		llm=llm,
		browser=browser,
		use_vision=False,  # Explicitly disable vision
		generate_gif=str(output_dir / "test.gif"),  # Enable GIF generation
		max_steps=3,
	)
	
	# Run the agent
	history = await agent.run()
	
	# Check if screenshots were captured
	logger.info(f"History has {len(history)} steps")
	
	# Check screenshot paths
	screenshot_paths = history.screenshot_paths()
	logger.info(f"Screenshot paths: {screenshot_paths}")
	
	# Check if screenshots exist as base64
	screenshots = history.screenshots()
	screenshots_found = sum(1 for s in screenshots if s is not None)
	logger.info(f"Found {screenshots_found} screenshots out of {len(screenshots)} steps")
	
	# Check if GIF was created
	gif_path = output_dir / "test.gif"
	if gif_path.exists():
		logger.info(f"✅ GIF created successfully at {gif_path}")
		logger.info(f"   GIF size: {gif_path.stat().st_size / 1024:.2f} KB")
	else:
		logger.warning(f"❌ GIF not created at {gif_path}")
	
	# Check agent directory for stored screenshots
	agent_dir = Path(agent.agent_directory)
	screenshots_dir = agent_dir / "screenshots"
	if screenshots_dir.exists():
		screenshot_files = list(screenshots_dir.glob("*.png"))
		logger.info(f"Found {len(screenshot_files)} screenshot files in {screenshots_dir}")
		for f in screenshot_files:
			logger.info(f"  - {f.name}: {f.stat().st_size / 1024:.2f} KB")
	
	# Check cloud sync
	if hasattr(agent, 'cloud_sync') and agent.cloud_sync:
		logger.info("✅ Cloud sync is enabled")
	else:
		logger.info("❌ Cloud sync is not enabled")
	
	return history


if __name__ == "__main__":
	asyncio.run(test_screenshot_capture())