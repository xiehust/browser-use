"""Test to verify download detection timing issue"""

import asyncio
import os
import tempfile
import time
from pathlib import Path

import pytest
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from browser_use.browser import BrowserSession


@pytest.fixture(scope='module')
async def httpserver():
	"""Create and provide a test HTTP server that serves static content."""
	server = HTTPServer()
	server.start()
	yield server
	server.stop()


@pytest.fixture(scope='module')
async def test_server(httpserver) -> HTTPServer:
	"""Setup test HTTP server with a simple page."""
	html_content = """
	<!DOCTYPE html>
	<html>
	<head>
		<title>Test Page</title>
	</head>
	<body>
		<h1>Test Page</h1>
		<button id="test-button" onclick="document.getElementById('result').innerText = 'Clicked!'">
			Click Me
		</button>
		<p id="result"></p>
		<a href="/download/test.pdf" download>Download PDF</a>
	</body>
	</html>
	"""
	httpserver.expect_request('/', handler_type=HandlerType.PERMANENT).respond_with_data(html_content, content_type='text/html')

	# Create a minimal PDF file content
	pdf_content = b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n203\n%%EOF'

	httpserver.expect_request('/download/test.pdf', handler_type=HandlerType.PERMANENT).respond_with_data(
		pdf_content,
		content_type='application/pdf',
		headers={'Content-Disposition': 'attachment; filename="test.pdf"', 'Content-Length': str(len(pdf_content))},
	)
	return httpserver


@pytest.fixture(scope='module')
async def browser_session():
	"""Setup browser with downloads_path set."""
	downloads_dir = Path(tempfile.mkdtemp()) / 'downloads'
	downloads_dir.mkdir(parents=True, exist_ok=True)
	browser = BrowserSession(
		headless=True,
		downloads_path=str(downloads_dir),
		user_data_dir=None,
	)
	await browser.start()
	yield browser
	await browser.close()
	del browser


@pytest.fixture(scope='module')
async def browser_session_without_downloads():
	"""Setup browser without downloads_path set."""
	browser = BrowserSession(
		headless=True,
		downloads_path=None,
		user_data_dir=None,
	)
	await browser.start()
	yield browser
	await browser.close()
	del browser


async def test_download_detection_timing(
	test_server: HTTPServer, browser_session: BrowserSession, browser_session_without_downloads: BrowserSession
):
	"""Test that download detection adds 5 second delay to clicks when downloads_path is set."""

	page = await browser_session.get_current_page()
	await page.goto(test_server.url_for('/'))

	# Get the actual DOM state to find the button
	state = await browser_session.get_state_summary(cache_clickable_elements_hashes=False)

	# Find the button element
	button_node = None
	for elem in state.selector_map.values():
		if elem.tag_name == 'button' and elem.attributes.get('id') == 'test-button':
			button_node = elem
			break

	assert button_node is not None, 'Could not find button element'

	# Time the click
	start_time = time.time()
	result = await browser_session._click_element_node(button_node)
	duration_with_downloads = time.time() - start_time

	# Verify click worked
	result_text = await page.locator('#result').text_content()
	assert result_text == 'Clicked!'
	assert result is None  # No download happened

	await browser_session.close()

	# Test 2: With downloads_path set to None (disables download detection)
	page = await browser_session_without_downloads.get_current_page()
	await page.goto(test_server.url_for('/'))

	# Clear previous result
	await page.evaluate('document.getElementById("result").innerText = ""')

	# Get the DOM state again for the new browser session
	state = await browser_session_without_downloads.get_state_summary(cache_clickable_elements_hashes=False)

	# Find the button element again
	button_node = None
	for elem in state.selector_map.values():
		if elem.tag_name == 'button' and elem.attributes.get('id') == 'test-button':
			button_node = elem
			break

	assert button_node is not None, 'Could not find button element'

	# Time the click
	start_time = time.time()
	result = await browser_session_without_downloads._click_element_node(button_node)
	duration_no_downloads = time.time() - start_time

	# Verify click worked
	result_text = await page.locator('#result').text_content()
	assert result_text == 'Clicked!'

	# Check timing differences
	print(f'Click with downloads_path: {duration_with_downloads:.2f}s')
	print(f'Click without downloads_path: {duration_no_downloads:.2f}s')
	print(f'Difference: {duration_with_downloads - duration_no_downloads:.2f}s')

	# Both should be fast now since we're clicking a button (not a download link)
	assert duration_with_downloads < 8, f'Expected <8s with downloads_dir, got {duration_with_downloads:.2f}s'
	assert duration_no_downloads < 3, f'Expected <3s without downloads_dir, got {duration_no_downloads:.2f}s'


async def test_actual_download_detection(test_server, browser_session):
	"""Test that actual downloads are detected correctly using playwright directly."""

	# Debug: Check if downloads_path is set
	print(f'browser_session.browser_profile.downloads_path = {browser_session.browser_profile.downloads_path}')
	print(f'browser_session.browser_profile.accept_downloads = {browser_session.browser_profile.accept_downloads}')

	page = await browser_session.get_current_page()
	await page.goto(test_server.url_for('/'))

	# Wait a bit for page to fully load
	await asyncio.sleep(0.5)

	# Set up download handler directly with playwright
	download_promise = asyncio.create_task(page.wait_for_event('download', timeout=5000))

	# Click the download link using playwright directly
	await page.click('a[download]')

	try:
		# Wait for download event
		download = await download_promise

		# Save the download
		download_path = os.path.join(browser_session.browser_profile.downloads_path, download.suggested_filename)
		await download.save_as(download_path)

		print(f'Downloaded file to: {download_path}')
		assert os.path.exists(download_path)
		assert 'test.pdf' in download_path

		# Clean up
		os.unlink(download_path)
	except TimeoutError:
		print('Download event not triggered within timeout')

		# Check if file was downloaded anyway
		downloads_dir = Path(browser_session.browser_profile.downloads_path)
		downloaded_files = list(downloads_dir.glob('*'))
		print(f'Files in downloads dir: {downloaded_files}')

		assert False, 'Download was not detected'


async def test_download_via_click_element_node(test_server, browser_session):
	"""Test that downloads work through browser_use's _click_element_node method."""

	page = await browser_session.get_current_page()
	await page.goto(test_server.url_for('/'))

	# Get the DOM state to find the download link
	state = await browser_session.get_state_summary(cache_clickable_elements_hashes=False)

	# Find the download link element
	download_node = None
	for elem in state.selector_map.values():
		if elem.tag_name == 'a' and 'download' in elem.attributes:
			download_node = elem
			break

	assert download_node is not None, 'Could not find download link element'

	# Click the download link using browser_use method
	print(f'About to click download link: {download_node}')
	start_time = time.time()
	download_path = await browser_session._click_element_node(download_node)
	duration = time.time() - start_time
	print(f'Click completed in {duration:.2f}s, download_path = {download_path}')

	# Should return the download path
	assert download_path is not None, 'Expected download path, got None'
	assert 'test.pdf' in download_path
	assert os.path.exists(download_path)

	# Verify it's a PDF file
	import anyio

	content = await anyio.Path(download_path).read_bytes()
	assert content.startswith(b'%PDF'), 'Downloaded file is not a valid PDF'

	# Clean up
	os.unlink(download_path)

	# Should be relatively fast since download is detected
	assert duration < 6.0, f'Download detection took {duration:.2f}s, expected <6s'
