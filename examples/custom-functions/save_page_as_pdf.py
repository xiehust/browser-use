import asyncio
import os
import re
import sys
from pathlib import Path
from typing import List

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Optional: Load environment variables if dotenv is available
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass

from browser_use import ActionResult, Agent, Controller
from browser_use.browser.types import Page
from browser_use.browser import BrowserSession, BrowserProfile
from browser_use.controller.views import NoParamsAction
from browser_use.llm import ChatOpenAI

# Initialize controller
controller = Controller()


@controller.action('Save the current page as a PDF file to downloads directory', param_model=NoParamsAction)
async def save_page_as_pdf(params: NoParamsAction, page: Page, browser_session: BrowserSession, available_file_paths: List[str]):
	"""
	Save the current page as PDF to the browser's downloads directory.
	This function takes no parameters and saves the current page as PDF.
	The PDF will be automatically added to the model's available_file_paths.
	"""
	# Get the downloads path from browser session
	downloads_path = browser_session.browser_profile.downloads_path
	if not downloads_path:
		return ActionResult(
			extracted_content="No downloads directory configured in browser profile",
			include_in_memory=True,
			error="Downloads path not set"
		)
	
	# Ensure downloads directory exists
	downloads_dir = Path(downloads_path)
	downloads_dir.mkdir(parents=True, exist_ok=True)
	
	# Create a sanitized filename from the current URL
	short_url = re.sub(r'^https?://(?:www\.)?|/$', '', page.url)
	slug = re.sub(r'[^a-zA-Z0-9]+', '-', short_url).strip('-').lower()
	
	# Add timestamp to make filename unique
	from datetime import datetime
	timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
	sanitized_filename = f'{slug}_{timestamp}.pdf'
	
	pdf_path = downloads_dir / sanitized_filename
	
	try:
		# Set media emulation for better PDF output
		await page.emulate_media(media='screen')
		
		# Save the page as PDF
		await page.pdf(
			path=str(pdf_path), 
			format='A4', 
			print_background=True,
			margin={'top': '1cm', 'bottom': '1cm', 'left': '1cm', 'right': '1cm'}
		)
		
		# Add the PDF path to browser session's downloaded files for tracking
		if hasattr(browser_session, '_downloaded_files'):
			browser_session._downloaded_files.append(str(pdf_path))
		
		msg = f'Saved page "{page.url}" as PDF to {pdf_path}'
		
		return ActionResult(
			extracted_content=msg,
			include_in_memory=True,
			long_term_memory=f'Saved PDF: {sanitized_filename}',
			attachments=[str(pdf_path)]  # This will be included in available_file_paths
		)
		
	except Exception as e:
		error_msg = f'Failed to save PDF: {str(e)}'
		return ActionResult(
			extracted_content=error_msg,
			include_in_memory=True,
			error=error_msg
		)


async def main():
	"""
	Example task: Navigate to a recipe page and save it as a PDF.
	The PDF will be saved to the browser's downloads directory and 
	automatically made available to the model via available_file_paths.
	"""
	task = """
	Go to https://www.thepioneerwoman.com/food-cooking/recipes/a65254855/chocolate-almond-sheet-cake-recipe/ 
	and save the page as PDF using the save_page_as_pdf function.
	"""

	# Configure browser with downloads directory
	downloads_dir = Path.cwd() / 'downloads'
	browser_profile = BrowserProfile(
		downloads_path=str(downloads_dir),
		headless=False,  # Set to True for headless operation
		user_data_dir=None  # Use temporary profile
	)

	# Initialize the language model
	model = ChatOpenAI(model='gpt-4o-mini')

	# Create and run the agent
	agent = Agent(
		task=task, 
		llm=model, 
		controller=controller,
		browser_profile=browser_profile
	)

	result = await agent.run()
	print(f'🎯 Task completed: {result}')


if __name__ == '__main__':
	asyncio.run(main())