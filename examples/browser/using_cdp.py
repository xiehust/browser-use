"""
Simple demonstration of the CDP feature.

To test this locally, follow these steps:
1. Create a shortcut for the executable Chrome file.
2. Add the following argument to the shortcut:
   - On Windows: `--remote-debugging-port=9222`
3. Open a web browser and navigate to `http://localhost:9222/json/version` to verify that the Remote Debugging Protocol (CDP) is running.
4. Launch this example.

@dev You need to set the `OPENAI_API_KEY` environment variable before proceeding.
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()

from browser_use import Agent, Controller
from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.llm import ChatOpenAI

browser_session = BrowserSession(
	browser_profile=BrowserProfile(
		headless=False,
	),
	cdp_url='https://9223-5dee1fd4-903a-4b1c-8d46-5e3cc10513e0.proxy.daytona.works/',
	is_local=False,  # set to False if you want to use a remote browser
)
controller = Controller()


async def main():
	agent = Agent(
		task='Go to https://gitlab.com/login',
		lllm=ChatOpenAI(model='gpt-4.1-mini'),
		controller=controller,
		browser_session=browser_session,
	)

	await agent.run()
	await browser_session.kill()

	input('Press Enter to close...')


if __name__ == '__main__':
	asyncio.run(main())
