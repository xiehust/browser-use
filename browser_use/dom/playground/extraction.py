import asyncio
import json
import os
import time

import anyio
import pyperclip
import tiktoken

from browser_use.agent.prompts import AgentMessagePrompt
from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.browser.types import ViewportSize
from browser_use.dom.debug.highlights import inject_highlighting_script, remove_highlighting_script
from browser_use.dom.service import DomService
from browser_use.dom.views import DEFAULT_INCLUDE_ATTRIBUTES
from browser_use.filesystem.file_system import FileSystem

TIMEOUT = 60


async def test_focus_vs_all_elements():
	# async with async_patchright() as patchright:
	browser_session = BrowserSession(
		browser_profile=BrowserProfile(
			# executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
			window_size=ViewportSize(width=1100, height=1000),
			disable_security=True,
			wait_for_network_idle_page_load_time=1,
			headless=False,
		),
	)

	# Unified website list with descriptions
	websites = [
		# Standard websites with various interactive elements
		('https://csreis.github.io/tests/cross-site-iframe.html', '🔸 IFRAME: Cross-site iframe'),
		# ('https://www.linkedin.com/robots.txt', 'Professional network'),
		# ('https://www.rent.com/', 'Rental listings'),
		# ('https://www.espn.com', 'Sports news site'),
		# ('https://www.eatsure.com/', 'Food delivery platform'),
		# ('https://www.kayak.com/', 'Travel booking site'),
		# ('https://web.archive.org/web/20200228210807/https://www.base-search.net/Search/Advanced', 'Archive search'),
		# ('https://www.va.gov/find-locations', 'VA locations finder'),
		('https://www.bbcgoodfood.com', 'Recipe website'),
		# ('https://www.napaonline.com/', 'Auto parts store'),
		# ('https://v0-simple-landing-page-seven-xi.vercel.app/', 'Simple landing page'),
		# ('https://www.google.com/travel/flights', 'Flight search'),
		# ('https://www.amazon.com/s?k=laptop', 'E-commerce search'),
		# ('https://github.com/trending', 'Code repository'),
		('https://www.reddit.com', 'Social platform'),
		# ('https://www.ycombinator.com/companies', 'Startup directory'),
		# ('https://www.kayak.com/flights', 'Flight booking'),
		('https://www.booking.com', 'Hotel booking'),
		('https://www.airbnb.com', 'Accommodation platform'),
		('https://www.linkedin.com/jobs', 'Job listings'),
		('https://stackoverflow.com/questions', 'Developer Q&A'),
		# Complex/difficult websites with iframes
		('https://www.w3schools.com/html/tryit.asp?filename=tryhtml_iframe', '🔸 IFRAME: W3Schools tryit editor'),
		('https://semantic-ui.com/modules/dropdown.html', '🔸 COMPLEX DROPDOWNS'),
		('https://www.dezlearn.com/nested-iframes-example/', '🔸 NESTED IFRAMES'),
		('https://jqueryui.com/accordion/', '🔸 ACCORDION WIDGETS'),
		('https://codepen.io/towc/pen/mJzOWJ', '🔸 CANVAS ELEMENTS'),
		('https://www.unesco.org/en', '🔸 COMPLEX LAYOUT'),
		# Additional iframe test cases
		('https://www.w3schools.com/html/html_iframe.asp', '🔸 IFRAME: Basic iframe examples'),
		('https://developer.mozilla.org/en-US/docs/Web/HTML/Element/iframe', '🔸 IFRAME: MDN iframe documentation'),
	]

	current_website_index = 0

	def get_website_list_for_prompt() -> str:
		"""Get a compact website list for the input prompt."""
		lines = []
		lines.append('📋 Websites:')

		for i, (url, description) in enumerate(websites):
			current_marker = ' ←' if i == current_website_index else ''
			domain = url.replace('https://', '').split('/')[0]
			# Truncate domain and description for clean display
			domain_short = domain[:20]
			desc_short = description[:25] if len(description) > 25 else description
			lines.append(f'  {i + 1:2d}. {domain_short:<20} ({desc_short}){current_marker}')

		return '\n'.join(lines)

	await browser_session.start()
	page = await browser_session.get_current_page()

	# Show startup info
	print('\n🌐 BROWSER-USE DOM EXTRACTION TESTER')
	print(f'📊 {len(websites)} websites total')
	print(f'🔧 Controls: Type 1-{len(websites)} to jump | Enter to re-run | "n" next | "p" previous | "q" quit')
	print('💾 Outputs: tmp/user_message.txt & tmp/element_tree.json\n')

	while True:
		# Cycle through websites
		if current_website_index >= len(websites):
			current_website_index = 0
			print('🔄 Cycled back to first website!')
		elif current_website_index < 0:
			current_website_index = len(websites) - 1
			print('🔄 Cycled to last website!')

		website_url, website_description = websites[current_website_index]
		# sleep 2
		await page.goto(website_url)
		await asyncio.sleep(1)

		last_clicked_index = None  # Track the index for text input
		while True:
			try:
				page = await browser_session.get_current_page()
				async with DomService(browser_session, page) as dom_service:
					await remove_highlighting_script(dom_service)

				print(f'\n{"=" * 60}')
				print(f'[{current_website_index + 1}/{len(websites)}] Testing: {website_url}')
				print(f'📝 {website_description}')
				print(f'{"=" * 60}')

				# Get/refresh the state (includes removing old highlights)
				print('\nGetting page state...')

				start_time = time.time()
				all_elements_state = await browser_session.get_state_summary(True)
				end_time = time.time()
				get_state_time = end_time - start_time
				print(f'get_state_summary took {get_state_time:.2f} seconds')

				# Get detailed timing info from DOM service
				print('\nGetting detailed DOM timing...')
				async with DomService(browser_session, page) as dom_service:
					serialized_state, timing_info = await dom_service.get_serialized_dom_tree()

				# Combine all timing info
				all_timing = {'get_state_summary_total': get_state_time, **timing_info}

				async with DomService(browser_session, page) as dom_service:
					await inject_highlighting_script(dom_service, all_elements_state.dom_state.selector_map)

				selector_map = all_elements_state.dom_state.selector_map
				total_elements = len(selector_map.keys())
				print(f'Total number of elements: {total_elements}')

				# print(all_elements_state.element_tree.clickable_elements_to_string())
				prompt = AgentMessagePrompt(
					browser_state_summary=all_elements_state,
					file_system=FileSystem(base_dir='./tmp'),
					include_attributes=DEFAULT_INCLUDE_ATTRIBUTES,
					step_info=None,
				)
				# Write the user message to a file for analysis
				user_message = prompt.get_user_message(use_vision=False).text

				# clickable_elements_str = all_elements_state.element_tree.clickable_elements_to_string()

				text_to_save = user_message

				os.makedirs('./tmp', exist_ok=True)
				async with await anyio.open_file('./tmp/user_message.txt', 'w', encoding='utf-8') as f:
					await f.write(text_to_save)

				# save pure clickable elements to a file
				if all_elements_state.dom_state._root:
					async with await anyio.open_file('./tmp/element_tree.json', 'w', encoding='utf-8') as f:
						await f.write(json.dumps(all_elements_state.dom_state._root.__json__(), indent=2))

				# copy the user message to the clipboard
				# pyperclip.copy(text_to_save)

				encoding = tiktoken.encoding_for_model('gpt-4o')
				token_count = len(encoding.encode(text_to_save))
				print(f'Token count: {token_count}')

				print('User message written to ./tmp/user_message.txt')
				print('Element tree written to ./tmp/element_tree.json')

				# Save timing information
				timing_text = '🔍 DOM EXTRACTION PERFORMANCE ANALYSIS\n'
				timing_text += f'{"=" * 50}\n\n'
				timing_text += f'📄 Website: {website_url}\n'
				timing_text += f'📊 Total Elements: {total_elements}\n'
				timing_text += f'🎯 Token Count: {token_count}\n\n'

				timing_text += '⏱️  TIMING BREAKDOWN:\n'
				timing_text += f'{"─" * 30}\n'
				for key, value in all_timing.items():
					timing_text += f'{key:<35}: {value * 1000:>8.2f} ms\n'

				# Calculate percentages
				total_time = all_timing.get('get_state_summary_total', 0)
				if total_time > 0:
					timing_text += '\n📈 PERCENTAGE BREAKDOWN:\n'
					timing_text += f'{"─" * 30}\n'
					for key, value in all_timing.items():
						if key != 'get_state_summary_total':
							percentage = (value / total_time) * 100
							timing_text += f'{key:<35}: {percentage:>7.1f}%\n'

				timing_text += '\n🎯 CLICKABLE DETECTION ANALYSIS:\n'
				timing_text += f'{"─" * 35}\n'
				clickable_time = all_timing.get('clickable_detection_time', 0)
				if clickable_time > 0 and total_elements > 0:
					avg_per_element = (clickable_time / total_elements) * 1000000  # microseconds
					timing_text += f'Total clickable detection time: {clickable_time * 1000:.2f} ms\n'
					timing_text += f'Average per element: {avg_per_element:.2f} μs\n'
					timing_text += f'Clickable detection calls: ~{total_elements} (approx)\n'
				elif total_elements == 0:
					timing_text += 'No interactive elements found on this page\n'
					timing_text += f'Total clickable detection time: {clickable_time * 1000:.2f} ms\n'

				async with await anyio.open_file('./tmp/timing_analysis.txt', 'w', encoding='utf-8') as f:
					await f.write(timing_text)

				print('Timing analysis written to ./tmp/timing_analysis.txt')

				website_list = get_website_list_for_prompt()
				answer = input(
					f"\n{website_list}\n\n🎮 Enter: element index | 'index,text' input | 'c,index' copy | 1-{len(websites)} jump | Enter re-run | 'n' next | 'p' previous | 'q' quit: "
				)

				if answer.lower() == 'q':
					return  # Exit completely
				elif answer.lower() == 'n':
					print('➡️ Moving to next website...')
					current_website_index += 1
					break  # Break inner loop to go to next website
				elif answer.lower() == 'p':
					print('⬅️ Moving to previous website...')
					current_website_index -= 1
					break  # Break inner loop to go to previous website
				elif answer.strip() == '':
					print('🔄 Re-running extraction on current page state...')
					continue  # Continue inner loop to re-extract DOM without reloading page
				elif answer.strip().isdigit():
					# Jump to specific website (1-N)
					try:
						target_website = int(answer.strip())
						if 1 <= target_website <= len(websites):
							current_website_index = target_website - 1  # Convert to 0-based index
							target_url, target_desc = websites[current_website_index]
							print(f'🎯 Jumping to website {target_website}: {target_url}')
							print(f'📝 {target_desc}')
							break  # Break inner loop to go to new website
						else:
							print(f'❌ Invalid website number. Enter 1-{len(websites)}.')
					except ValueError:
						print(f'❌ Invalid input: {answer}')
					continue

				try:
					if answer.lower().startswith('c,'):
						# Copy element JSON format: c,index
						parts = answer.split(',', 1)
						if len(parts) == 2:
							try:
								target_index = int(parts[1].strip())
								if target_index in selector_map:
									element_node = selector_map[target_index]
									element_json = json.dumps(element_node.__json__(), indent=2, default=str)
									pyperclip.copy(element_json)
									print(f'📋 Copied element {target_index} JSON to clipboard: {element_node.tag_name}')
								else:
									print(f'❌ Invalid index: {target_index}')
							except ValueError:
								print(f'❌ Invalid index format: {parts[1]}')
						else:
							print("❌ Invalid input format. Use 'c,index'.")
					elif ',' in answer:
						# Input text format: index,text
						parts = answer.split(',', 1)
						if len(parts) == 2:
							try:
								target_index = int(parts[0].strip())
								text_to_input = parts[1]
								if target_index in selector_map:
									element_node = selector_map[target_index]
									print(
										f"⌨️ Inputting text '{text_to_input}' into element {target_index}: {element_node.tag_name}"
									)
									await browser_session._input_text_element_node(element_node, text_to_input)
									print('✅ Input successful.')
								else:
									print(f'❌ Invalid index: {target_index}')
							except ValueError:
								print(f'❌ Invalid index format: {parts[0]}')
						else:
							print("❌ Invalid input format. Use 'index,text'.")
					else:
						# Click element format: index
						try:
							clicked_index = int(answer)
							if clicked_index in selector_map:
								element_node = selector_map[clicked_index]
								print(f'👆 Clicking element {clicked_index}: {element_node.tag_name}')
								await browser_session._click_element_node(element_node)
								print('✅ Click successful.')
							else:
								print(f'❌ Invalid index: {clicked_index}')
						except ValueError:
							print(f"❌ Invalid input: '{answer}'. Enter an index, 'index,text', 'c,index', or 'q'.")

				except Exception as action_e:
					print(f'❌ Action failed: {action_e}')

			# No explicit highlight removal here, get_state handles it at the start of the loop

			except Exception as e:
				print(f'❌ Error in loop: {e}')
				# Optionally add a small delay before retrying
				await asyncio.sleep(1)


if __name__ == '__main__':
	asyncio.run(test_focus_vs_all_elements())
	# asyncio.run(test_process_html_file()) # Commented out the other test
