import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from browser_use import Agent
from browser_use.llm.openai.chat import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize the model
llm = ChatOpenAI(model='gpt-4o-mini')

# Simple navigation task  
task = 'Go to google.com, search for "fish", then end the task'
agent = Agent(task=task, llm=llm, verbose=True)


async def main():
	try:
		await agent.run()
	except Exception as e:
		print(f"Error: {e}")
		import traceback
		traceback.print_exc()


if __name__ == '__main__':
	asyncio.run(main())