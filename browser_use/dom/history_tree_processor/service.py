import hashlib
from typing import TYPE_CHECKING, Optional

from browser_use.dom.history_tree_processor.view import DOMHistoryElement, HashedDomElement
from browser_use.dom.views import DOMElementNode

if TYPE_CHECKING:
	pass


class HistoryTreeProcessor:
	""" "
	Operations on the DOM elements

	@dev be careful - text nodes can change even if elements stay the same
	"""

	@staticmethod
	def convert_dom_element_to_history_element(dom_element: DOMElementNode) -> DOMHistoryElement:
		parent_branch_path = HistoryTreeProcessor._get_parent_branch_path(dom_element)
		from browser_use.browser.context import BrowserContext  # Import here to avoid circular dependency

		css_selector = BrowserContext._enhanced_css_selector_for_element(dom_element)
		return DOMHistoryElement(
			dom_element.tag_name,
			dom_element.xpath,
			dom_element.highlight_index,
			parent_branch_path,
			dom_element.attributes,
			dom_element.shadow_root,
			css_selector=css_selector,
			page_coordinates=dom_element.page_coordinates,
			viewport_coordinates=dom_element.viewport_coordinates,
			viewport_info=dom_element.viewport_info,
		)

	@staticmethod
	def find_history_element_in_tree(
		dom_history_element: DOMHistoryElement,
		tree: DOMElementNode,
		match_criteria: list[str] = ['branch_path', 'attributes', 'xpath', 'css_selector'],
	) -> Optional[DOMElementNode]:
		hashed_dom_history_element = HistoryTreeProcessor._hash_dom_history_element(dom_history_element)
		if match_criteria == []:
			raise ValueError(
				'match_criteria cannot be empty - at least one criteria must be provided (branch_path, attributes, xpath)'
			)

		all_matches = []

		def process_node(node: DOMElementNode):
			if node.highlight_index is not None:
				hashed_node = HistoryTreeProcessor._hash_dom_element(node)

				matches = []
				if 'branch_path' in match_criteria:
					matches.append(hashed_node.branch_path_hash == hashed_dom_history_element.branch_path_hash)
				if 'attributes' in match_criteria:
					matches.append(hashed_node.attributes_hash == hashed_dom_history_element.attributes_hash)
				if 'xpath' in match_criteria:
					matches.append(hashed_node.xpath_hash == hashed_dom_history_element.xpath_hash)
				if 'css_selector' in match_criteria:
					matches.append(hashed_node.css_selector == hashed_dom_history_element.css_selector)

				if all(matches):
					# return the first match
					# return node
					all_matches.append(node)

			for child in node.children:
				if isinstance(child, DOMElementNode):
					result = process_node(child)
					if result is not None:
						return result
			return None

		process_node(tree)
		count_matches = len(all_matches)
		print(f'count_matches: {count_matches}')
		if count_matches == 0:
			return None
		elif count_matches == 1:
			return all_matches[0]
		else:
			return all_matches[0]

	@staticmethod
	def compare_history_element_and_dom_element(dom_history_element: DOMHistoryElement, dom_element: DOMElementNode) -> bool:
		hashed_dom_history_element = HistoryTreeProcessor._hash_dom_history_element(dom_history_element)
		hashed_dom_element = HistoryTreeProcessor._hash_dom_element(dom_element)

		return hashed_dom_history_element == hashed_dom_element

	@staticmethod
	def _hash_dom_history_element(dom_history_element: DOMHistoryElement) -> HashedDomElement:
		branch_path_hash = HistoryTreeProcessor._parent_branch_path_hash(dom_history_element.entire_parent_branch_path)
		attributes_hash = HistoryTreeProcessor._attributes_hash(dom_history_element.attributes)
		xpath_hash = HistoryTreeProcessor._xpath_hash(dom_history_element.xpath)

		return HashedDomElement(branch_path_hash, attributes_hash, xpath_hash, dom_history_element.css_selector)

	@staticmethod
	def _hash_dom_element(dom_element: DOMElementNode) -> HashedDomElement:
		parent_branch_path = HistoryTreeProcessor._get_parent_branch_path(dom_element)
		branch_path_hash = HistoryTreeProcessor._parent_branch_path_hash(parent_branch_path)
		attributes_hash = HistoryTreeProcessor._attributes_hash(dom_element.attributes)
		xpath_hash = HistoryTreeProcessor._xpath_hash(dom_element.xpath)
		from browser_use.browser.context import BrowserContext  # Import here to avoid circular dependency

		css_selector = BrowserContext._enhanced_css_selector_for_element(dom_element)

		# text_hash = DomTreeProcessor._text_hash(dom_element)

		return HashedDomElement(branch_path_hash, attributes_hash, xpath_hash, css_selector)

	@staticmethod
	def _get_parent_branch_path(dom_element: DOMElementNode) -> list[str]:
		parents: list[DOMElementNode] = []
		current_element: DOMElementNode = dom_element
		while current_element.parent is not None:
			parents.append(current_element)
			current_element = current_element.parent

		parents.reverse()

		return [parent.tag_name for parent in parents]

	@staticmethod
	def _parent_branch_path_hash(parent_branch_path: list[str]) -> str:
		parent_branch_path_string = '/'.join(parent_branch_path)
		return hashlib.sha256(parent_branch_path_string.encode()).hexdigest()

	@staticmethod
	def _attributes_hash(
		attributes: dict[str, str],
		exclude_attributes: list[str] = [
			# Analytics and Tracking
			'data-ved',
			'data-hveid',  # Google tracking/analytics
			'jsname',
			'ping',
			'data-ga',
			'data-analytics',
			'data-gtm',
			'data-click-id',
			'data-tracking',
			# Dynamic/Generated IDs and State
			'data-reactid',
			'data-hydrated',
			'data-rendered',
			'data-timestamp',
			'data-random',
			'data-unique',
			# Framework-specific
			'data-testid',
			'data-cy',
			'data-test',
			'data-e2e',
			# State and Session
			'data-state',
			'data-status',
			'data-loading',
			'data-expanded',
			'data-selected',
			'data-session',
			# Additional dynamic attributes
			'data-v',
			'ng-version',
			'data-rendered-timestamp',
		],
	) -> str:
		# Filter out attributes that start with excluded prefixes
		excluded_prefixes = ['ng-', 'v-', 'data-v-']
		attributes_string = ''.join(
			f'{key}={value}'
			for key, value in attributes.items()
			if key not in exclude_attributes and not any(key.startswith(prefix) for prefix in excluded_prefixes)
		)
		return hashlib.sha256(attributes_string.encode()).hexdigest()

	@staticmethod
	def _xpath_hash(xpath: str) -> str:
		return hashlib.sha256(xpath.encode()).hexdigest()

	@staticmethod
	def _text_hash(dom_element: DOMElementNode) -> str:
		""" """
		text_string = dom_element.get_all_text_till_next_clickable_element()
		return hashlib.sha256(text_string.encode()).hexdigest()
