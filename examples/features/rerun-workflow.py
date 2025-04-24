import os
import sys

from browser_use.browser.context import BrowserContextConfig
from browser_use.workflow.views import Workflow

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from browser_use import Agent, Browser, BrowserConfig

load_dotenv()

browser = Browser(
	config=BrowserConfig(
		new_context_config=BrowserContextConfig(minimum_wait_page_load_time=2),
		# NOTE: you need to close your chrome browser - so that this can open your browser in debug mode
		browser_binary_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
	)
)


# Example usage
async def main():
	# Initialize agent and LLM
	llm = ChatOpenAI(model='gpt-4o', temperature=0.0)

	# Create and run workflow
	workflow = Workflow('workflow.yaml', company_name='Browser Use', year='2024')
	agent = Agent(
		workflow=workflow,
		llm=llm,
		browser=browser,
		save_workflow_yaml=None,
		enable_memory=False,
	)  # , save_workflow_yaml=None

	task = "go to https://www.linkedin.com/search/results/people/, search for sandra müller send a message 'Hi, wie gehts?'"
	agent = Agent(llm=llm, task=task, browser=browser, enable_memory=False)
	history = await agent.run()


if __name__ == '__main__':
	asyncio.run(main())
