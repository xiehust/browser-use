#!/usr/bin/env python3
"""
Test runner for DOM serializer improvements.
Loads test HTML files and validates that interactive elements are properly detected.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List

from playwright.async_api import async_playwright

from browser_use.browser import Browser
from browser_use.dom.service import DOMService


class SerializerTestRunner:
	def __init__(self):
		self.test_files = [
			'test_interactive_elements.html',
			'test_dropdown_complex.html',
			'test_modern_ui.html',
			'test_edge_cases.html',
		]
		self.results = {}

	async def run_all_tests(self):
		"""Run all test files and collect results."""
		print('🧪 Starting DOM Serializer Tests')
		print('=' * 50)

		for test_file in self.test_files:
			print(f'\n📄 Testing: {test_file}')
			result = await self.test_file(test_file)
			self.results[test_file] = result

			# Print summary for this file
			self.print_test_summary(test_file, result)

		# Print overall summary
		self.print_overall_summary()

	async def test_file(self, test_file: str) -> Dict:
		"""Test a single HTML file."""
		test_path = Path(__file__).parent / test_file

		if not test_path.exists():
			return {'error': f'Test file {test_file} not found'}

		async with async_playwright() as p:
			browser = await p.chromium.launch(headless=True)
			page = await browser.new_page()

			try:
				# Load the test file
				await page.goto(f'file://{test_path.absolute()}')
				await page.wait_for_load_state('networkidle')

				# Create browser wrapper and DOM service
				browser_wrapper = Browser(config=None)
				browser_wrapper._playwright_browser = browser
				browser_wrapper._current_page = page
				browser_wrapper.cdp_url = page.context._browser._browser_type._impl_obj._connection._transport._url.replace(
					'ws://', 'http://'
				).replace('/devtools/browser', '')

				dom_service = DOMService(browser_wrapper)

				# Get serialized DOM
				serialized, selector_map = await dom_service.get_serialized_dom_tree()

				# Analyze results
				analysis = self.analyze_serialized_output(serialized, selector_map, test_file)

				return {
					'serialized': serialized,
					'selector_map': selector_map,
					'analysis': analysis,
					'interactive_count': len(selector_map),
					'success': True,
				}

			except Exception as e:
				return {'error': str(e), 'success': False}
			finally:
				await browser.close()

	def analyze_serialized_output(self, serialized: str, selector_map: Dict, test_file: str) -> Dict:
		"""Analyze the serialized output for expected patterns."""
		analysis = {
			'interactive_elements_found': len(selector_map),
			'patterns_detected': [],
			'missing_patterns': [],
			'issues': [],
		}

		lines = serialized.split('\n')

		# Define expected patterns for each test file
		expected_patterns = self.get_expected_patterns(test_file)

		# Check for expected patterns
		for pattern_name, pattern_info in expected_patterns.items():
			found = False
			for line in lines:
				if any(keyword in line.lower() for keyword in pattern_info.get('keywords', [])):
					found = True
					break

			if found:
				analysis['patterns_detected'].append(pattern_name)
			else:
				analysis['missing_patterns'].append(pattern_name)

		# Check for common issues
		self.check_common_issues(lines, analysis)

		return analysis

	def get_expected_patterns(self, test_file: str) -> Dict:
		"""Get expected patterns for each test file."""
		patterns = {
			'test_interactive_elements.html': {
				'form_inputs': {'keywords': ['input', 'type='], 'min_count': 5},
				'buttons': {'keywords': ['button', 'submit'], 'min_count': 3},
				'select_dropdowns': {'keywords': ['select', 'option'], 'min_count': 1},
				'links': {'keywords': ['href='], 'min_count': 5},
				'radio_buttons': {'keywords': ['radio'], 'min_count': 3},
				'checkboxes': {'keywords': ['checkbox'], 'min_count': 3},
			},
			'test_dropdown_complex.html': {
				'custom_dropdowns': {'keywords': ['select-trigger', 'select-option'], 'min_count': 1},
				'nested_menus': {'keywords': ['dropdown-menu', 'submenu'], 'min_count': 1},
				'searchable_elements': {'keywords': ['search-input', 'country-option'], 'min_count': 1},
			},
			'test_modern_ui.html': {
				'modal_triggers': {'keywords': ['modal'], 'min_count': 1},
				'toggle_switches': {'keywords': ['toggle', 'slider'], 'min_count': 1},
				'card_actions': {'keywords': ['btn', 'card'], 'min_count': 1},
				'tooltips': {'keywords': ['tooltip'], 'min_count': 1},
			},
			'test_edge_cases.html': {
				'pointer_cursor': {'keywords': ['cursor'], 'min_count': 1},
				'data_attributes': {'keywords': ['data-'], 'min_count': 1},
				'aria_elements': {'keywords': ['role=', 'aria-'], 'min_count': 1},
				'svg_elements': {'keywords': ['svg'], 'min_count': 1},
			},
		}
		return patterns.get(test_file, {})

	def check_common_issues(self, lines: List[str], analysis: Dict):
		"""Check for common serialization issues."""
		interactive_lines = [line for line in lines if '[' in line and ']' in line]

		# Check if we have any interactive elements at all
		if len(interactive_lines) == 0:
			analysis['issues'].append('No interactive elements detected')

		# Check for missing cursor pointer elements
		cursor_pointer_found = any('cursor' in line.lower() for line in lines)
		if not cursor_pointer_found:
			analysis['issues'].append('No cursor:pointer elements detected')

		# Check for proper indexing
		indices = []
		for line in interactive_lines:
			try:
				start = line.find('[') + 1
				end = line.find(']')
				if start > 0 and end > start:
					index = int(line[start:end])
					indices.append(index)
			except ValueError:
				continue

		if indices:
			if min(indices) != 1:
				analysis['issues'].append("Interactive indices don't start at 1")
			if max(indices) != len(set(indices)):
				analysis['issues'].append('Interactive indices are not sequential')
			if len(indices) != len(set(indices)):
				analysis['issues'].append('Duplicate interactive indices found')

	def print_test_summary(self, test_file: str, result: Dict):
		"""Print summary for a single test file."""
		if not result.get('success'):
			print(f'❌ FAILED: {result.get("error", "Unknown error")}')
			return

		analysis = result['analysis']
		interactive_count = result['interactive_count']

		print(f'✅ Interactive elements found: {interactive_count}')

		if analysis['patterns_detected']:
			print(f'✅ Detected patterns: {", ".join(analysis["patterns_detected"])}')

		if analysis['missing_patterns']:
			print(f'⚠️  Missing patterns: {", ".join(analysis["missing_patterns"])}')

		if analysis['issues']:
			print(f'🐛 Issues: {", ".join(analysis["issues"])}')

		# Show sample interactive elements
		lines = result['serialized'].split('\n')
		interactive_lines = [line.strip() for line in lines if '[' in line and ']' in line][:5]
		if interactive_lines:
			print('📋 Sample interactive elements:')
			for line in interactive_lines:
				print(f'   {line}')

	def print_overall_summary(self):
		"""Print overall test summary."""
		print('\n' + '=' * 50)
		print('📊 OVERALL TEST SUMMARY')
		print('=' * 50)

		total_files = len(self.test_files)
		successful_files = sum(1 for result in self.results.values() if result.get('success'))
		total_interactive_elements = sum(
			result.get('interactive_count', 0) for result in self.results.values() if result.get('success')
		)

		print(f'Files tested: {successful_files}/{total_files}')
		print(f'Total interactive elements detected: {total_interactive_elements}')

		# Collect all issues
		all_issues = []
		for test_file, result in self.results.items():
			if result.get('success') and result.get('analysis', {}).get('issues'):
				for issue in result['analysis']['issues']:
					all_issues.append(f'{test_file}: {issue}')

		if all_issues:
			print('\n🐛 Issues found:')
			for issue in all_issues:
				print(f'   - {issue}')
		else:
			print('\n✅ No issues found!')

		# Save detailed results
		results_file = Path(__file__).parent / 'test_results.json'
		with open(results_file, 'w') as f:
			json.dump(self.results, f, indent=2, default=str)
		print(f'\n💾 Detailed results saved to: {results_file}')


async def main():
	"""Main test runner entry point."""
	runner = SerializerTestRunner()
	await runner.run_all_tests()


if __name__ == '__main__':
	asyncio.run(main())
