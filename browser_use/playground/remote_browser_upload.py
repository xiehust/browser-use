import asyncio

from anchorbrowser import AsyncAnchorbrowser

from browser_use import Agent, BrowserSession
from browser_use.agent.views import AgentState
from browser_use.llm.openai.chat import ChatOpenAI

llm = ChatOpenAI(model='o4-mini')

TASK = """
download and upload the file in https://v0-download-and-upload-text.vercel.app, then call done
"""


async def main():
	anchor_browser = AsyncAnchorbrowser()
	DOWNLOADS_PATH = '/downloads/'
	session = await anchor_browser.sessions.create()
	if not session.data or not session.data.id:
		raise ValueError('Failed to create session')

	cdp_url = session.data.cdp_url
	print(session.data.live_view_url)

	browser_session = BrowserSession(
		cdp_url=cdp_url,
	)
	await browser_session.start()

	agent_state = AgentState()
	try:
		for _ in range(10):
			file_download_paths = await anchor_browser.sessions.retrieve_downloads(session.data.id)

			items = (file_download_paths.data.items if file_download_paths.data else []) or []

			file_downloads = [DOWNLOADS_PATH + download.suggested_file_name for download in items if download.suggested_file_name]

			agent = Agent(
				llm=llm,
				browser_session=browser_session,
				task=TASK,
				injected_agent_state=agent_state,
				available_file_paths=file_downloads,
			)

			await agent.take_step()

		print(session.data.live_view_url)
		await asyncio.sleep(10)

		await browser_session.stop()

	finally:
		await anchor_browser.sessions.delete(session.data.id)


if __name__ == '__main__':
	asyncio.run(main())
