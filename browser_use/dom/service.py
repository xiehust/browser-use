import asyncio
import time

from cdp_use import CDPClient
from cdp_use.cdp.accessibility.commands import GetFullAXTreeReturns
from cdp_use.cdp.accessibility.types import AXNode, AXPropertyName
from cdp_use.cdp.dom.commands import GetDocumentReturns
from cdp_use.cdp.dom.types import Node, ShadowRootType
from cdp_use.cdp.domsnapshot.commands import CaptureSnapshotReturns

from browser_use.browser.session import BrowserSession
from browser_use.dom.enhanced_snapshot import (
	REQUIRED_COMPUTED_STYLES,
	build_snapshot_lookup,
)
from browser_use.dom.serializer import DOMTreeSerializer
from browser_use.dom.views import EnhancedAXNode, EnhancedAXProperty, EnhancedDOMTreeNode, NodeType


class DOMService:
	def __init__(self, browser_session: BrowserSession):
		self.browser_session = browser_session
		self.cdp_client: CDPClient | None = None
		# Track CDP sessions per page GUID to handle multi-tab scenarios
		self.page_session_store: dict[str, str] = {}  # page_guid -> session_id
		# Track which page GUID we last processed to detect tab switches
		self._last_processed_page_guid: str | None = None

	async def _get_cdp_client(self) -> CDPClient:
		if self.cdp_client is None:
			# Get CDP URL from browser session
			cdp_url = self.browser_session.cdp_url
			if not cdp_url:
				raise ValueError('CDP URL is not set in browser session')

			# Get WebSocket URL from CDP version endpoint
			import httpx

			# Ensure HTTP URL has proper format
			if not cdp_url.endswith('/'):
				cdp_url += '/'

			print(f'🔗 Querying CDP version info from: {cdp_url}json/version')

			async with httpx.AsyncClient() as client:
				try:
					response = await client.get(f'{cdp_url}json/version')
					version_info = response.json()
					ws_url = version_info['webSocketDebuggerUrl']
					print(f'🔗 Got WebSocket URL: {ws_url}')
				except Exception as e:
					print(f'⚠️ Failed to get WebSocket URL from CDP: {e}')
					# Fallback: try to construct WebSocket URL manually
					if cdp_url.startswith('http://'):
						ws_url = cdp_url.replace('http://', 'ws://') + 'json'
					elif cdp_url.startswith('https://'):
						ws_url = cdp_url.replace('https://', 'wss://') + 'json'
					else:
						ws_url = cdp_url
					print(f'🔗 Using fallback WebSocket URL: {ws_url}')

			self.cdp_client = CDPClient(ws_url)
			await self.cdp_client.start()
		return self.cdp_client

	async def __del__(self):
		if self.cdp_client:
			await self.cdp_client.stop()
			self.cdp_client = None

	async def _get_current_page_session_id(self) -> str:
		"""Get or create a CDP session for the current active tab."""
		# Always get the current page from browser session to handle tab switches
		page = await self.browser_session.get_current_page()
		page_guid = page._impl_obj._guid

		# Clear cache if we've switched to a different tab
		if self._last_processed_page_guid != page_guid:
			print(f'🔄 Tab switch detected: {self._last_processed_page_guid} -> {page_guid}')
			self._last_processed_page_guid = page_guid

		# Check if we already have a cached session for this page
		if page_guid in self.page_session_store:
			cached_session_id = self.page_session_store[page_guid]
			print(f'🔄 Using cached session for tab {page_guid[:8]}...: {cached_session_id[:8]}...')

			# Verify the cached session is still valid
			try:
				cdp_client = await self._get_cdp_client()
				# Quick test to see if session is still alive
				await cdp_client.send.Runtime.evaluate(params={'expression': '1'}, session_id=cached_session_id)
				return cached_session_id
			except Exception as e:
				print(f'⚠️ Cached session invalid, will create new one: {e}')
				# Remove invalid cache entry
				del self.page_session_store[page_guid]

		# Create new CDP session for this tab
		cdp_client = await self._get_cdp_client()
		targets = await cdp_client.send.Target.getTargets()

		current_url = page.url
		print(f'🔍 Creating CDP session for tab: {current_url}')
		print(f'📋 Available CDP targets: {len([t for t in targets["targetInfos"] if t["type"] == "page"])} pages')

		target_candidates = []
		for target in targets['targetInfos']:
			if target['type'] == 'page':
				target_url = target['url']
				print(f'  - Target: {target["targetId"][:8]}... URL: {target_url}')

				# Collect potential matches with different URL matching strategies
				if target_url == current_url:
					target_candidates.append((target, 'exact_match', 0))
				elif self._urls_match_loosely(target_url, current_url):
					target_candidates.append((target, 'loose_match', 1))
				elif current_url in target_url or target_url in current_url:
					target_candidates.append((target, 'contains_match', 2))

		# Sort by match quality (lower priority number = better match)
		target_candidates.sort(key=lambda x: x[2])

		if not target_candidates:
			# Fallback: try to find any page target (in case URL matching completely fails)
			page_targets = [t for t in targets['targetInfos'] if t['type'] == 'page']
			if page_targets:
				print('⚠️ No URL match found, using first available page target')
				target_candidates = [(page_targets[0], 'fallback_match', 3)]

		if not target_candidates:
			raise ValueError(f'No CDP page targets found. Available targets: {[t["type"] for t in targets["targetInfos"]]}')

		# Use the best matching target
		best_target, match_type, _ = target_candidates[0]
		target_id = best_target['targetId']

		print(f'✅ Selected target {target_id[:8]}... (match type: {match_type}) for tab {page_guid[:8]}...')

		session = await cdp_client.send.Target.attachToTarget(params={'targetId': target_id, 'flatten': True})
		session_id = session['sessionId']

		# Enable domains for this session
		await cdp_client.send.Target.setAutoAttach(params={'autoAttach': True, 'waitForDebuggerOnStart': False, 'flatten': True})
		await cdp_client.send.DOM.enable(session_id=session_id)
		await cdp_client.send.Accessibility.enable(session_id=session_id)
		await cdp_client.send.DOMSnapshot.enable(session_id=session_id)
		await cdp_client.send.Page.enable(session_id=session_id)

		# Cache the session for this page
		self.page_session_store[page_guid] = session_id
		print(f'💾 Cached session {session_id[:8]}... for tab {page_guid[:8]}...')

		return session_id

	def _urls_match_loosely(self, url1: str, url2: str) -> bool:
		"""Check if two URLs match with common variations (www, trailing slash, protocol)."""
		import re

		def normalize_url(url: str) -> str:
			# Remove protocol
			url = re.sub(r'^https?://', '', url)
			# Remove www
			url = re.sub(r'^www\.', '', url)
			# Remove trailing slash
			url = url.rstrip('/')
			# Convert to lowercase
			return url.lower()

		return normalize_url(url1) == normalize_url(url2)

	def _build_enhanced_ax_node(self, ax_node: AXNode) -> EnhancedAXNode:
		properties: list[EnhancedAXProperty] | None = None
		if 'properties' in ax_node and ax_node['properties']:
			properties = []
			for property in ax_node['properties']:
				try:
					# test whether property name can go into the enum (sometimes Chrome returns some random properties)
					AXPropertyName(property['name'])
					properties.append(
						EnhancedAXProperty(
							name=property['name'],
							value=property.get('value', {}).get('value', None),
							# related_nodes=[],  # TODO: add related nodes
						)
					)
				except ValueError:
					pass

		enhanced_ax_node = EnhancedAXNode(
			ax_node_id=ax_node['nodeId'],
			ignored=ax_node['ignored'],
			role=ax_node.get('role', {}).get('value', None),
			name=ax_node.get('name', {}).get('value', None),
			description=ax_node.get('description', {}).get('value', None),
			properties=properties,
		)
		return enhanced_ax_node

	async def _get_viewport_size(self) -> tuple[float, float, float, float, float]:
		"""Get viewport dimensions, device pixel ratio, and scroll position using CDP."""
		try:
			cdp_client = await self._get_cdp_client()
			session_id = await self._get_current_page_session_id()

			# Get the layout metrics which includes the visual viewport
			metrics = await cdp_client.send.Page.getLayoutMetrics(session_id=session_id)

			# Debug: print all available metrics
			print('🔍 **CDP VIEWPORT DEBUG**:')
			print(f'  Full metrics: {metrics}')

			visual_viewport = metrics.get('visualViewport', {})
			layout_viewport = metrics.get('layoutViewport', {})
			content_size = metrics.get('contentSize', {})

			# IMPORTANT: Use CSS viewport instead of device pixel viewport
			# This fixes the coordinate mismatch on high-DPI displays
			css_visual_viewport = metrics.get('cssVisualViewport', {})
			css_layout_viewport = metrics.get('cssLayoutViewport', {})

			# Use CSS pixels (what JavaScript sees) instead of device pixels
			width = css_visual_viewport.get('clientWidth', css_layout_viewport.get('clientWidth', 1920.0))
			height = css_visual_viewport.get('clientHeight', css_layout_viewport.get('clientHeight', 1080.0))

			# Calculate device pixel ratio
			device_width = visual_viewport.get('clientWidth', width)
			css_width = css_visual_viewport.get('clientWidth', width)
			device_pixel_ratio = device_width / css_width if css_width > 0 else 1.0

			# Get current scroll position from the visual viewport
			scroll_x = css_visual_viewport.get('pageX', 0)
			scroll_y = css_visual_viewport.get('pageY', 0)

			print(f'  Visual Viewport (device pixels): {visual_viewport}')
			print(f'  CSS Visual Viewport (CSS pixels): {css_visual_viewport}')
			print(f'  Layout Viewport: {layout_viewport}')
			print(f'  Content Size: {content_size}')
			print(f'  🎯 Using CSS dimensions: {width}x{height}')
			print(f'  📱 Device Pixel Ratio: {device_pixel_ratio}')
			print(f'  📜 Scroll Position: ({scroll_x}, {scroll_y})')

			return float(width), float(height), float(device_pixel_ratio), float(scroll_x), float(scroll_y)
		except Exception as e:
			print(f'⚠️  Viewport size detection failed: {e}')
			# Fallback to default viewport size
			return 1920.0, 1080.0, 1.0, 0.0, 0.0

	async def _build_enhanced_dom_tree(
		self, dom_tree: GetDocumentReturns, ax_tree: GetFullAXTreeReturns, snapshot: CaptureSnapshotReturns
	) -> EnhancedDOMTreeNode:
		ax_tree_lookup: dict[int, AXNode] = {
			ax_node['backendDOMNodeId']: ax_node for ax_node in ax_tree['nodes'] if 'backendDOMNodeId' in ax_node
		}

		enhanced_dom_tree_node_lookup: dict[int, EnhancedDOMTreeNode] = {}
		""" NodeId (NOT backend node id) -> enhanced dom tree node"""  # way to get the parent/content node

		# Get viewport dimensions first for visibility calculation
		viewport_width, viewport_height, device_pixel_ratio, scroll_x, scroll_y = await self._get_viewport_size()

		print('📐 **DOM TREE BUILD DEBUG**:')
		print(f'  Viewport dimensions used: {viewport_width}x{viewport_height}')
		print(f'  Scroll position: ({scroll_x}, {scroll_y})')
		print(
			f'  Current viewport rectangle: ({scroll_x}, {scroll_y}) to ({scroll_x + viewport_width}, {scroll_y + viewport_height})'
		)
		print(f'  Snapshot documents count: {len(snapshot.get("documents", []))}')
		print(f'  DOM tree nodes count: {len(dom_tree.get("root", {}).get("children", []))}')

		# Parse snapshot data with everything calculated upfront
		snapshot_lookup = build_snapshot_lookup(snapshot, viewport_width, viewport_height, device_pixel_ratio, scroll_x, scroll_y)

		# Debug: check some sample coordinates from snapshot_lookup
		sample_coords = []
		for backend_id, snapshot_node in list(snapshot_lookup.items())[:5]:
			if snapshot_node.bounding_box:
				bbox = snapshot_node.bounding_box
				# Check if element is in current viewport
				in_viewport = (
					bbox['x'] + bbox['width'] > scroll_x
					and bbox['x'] < scroll_x + viewport_width
					and bbox['y'] + bbox['height'] > scroll_y
					and bbox['y'] < scroll_y + viewport_height
				)
				sample_coords.append(
					{
						'backend_id': backend_id,
						'x': bbox['x'],
						'y': bbox['y'],
						'width': bbox['width'],
						'height': bbox['height'],
						'is_visible': snapshot_node.is_visible,
						'is_clickable': snapshot_node.is_clickable,
						'in_current_viewport': in_viewport,
					}
				)

		if sample_coords:
			print('  Sample coordinates from snapshot_lookup (scroll-aware):')
			for coord in sample_coords:
				status = '✅ IN VIEWPORT' if coord['in_current_viewport'] else '❌ OUT OF VIEWPORT'
				print(
					f'    Backend {coord["backend_id"]}: ({coord["x"]:.1f}, {coord["y"]:.1f}) {coord["width"]:.1f}x{coord["height"]:.1f} visible={coord["is_visible"]} clickable={coord["is_clickable"]} {status}'
				)

		def _construct_enhanced_node(node: Node) -> EnhancedDOMTreeNode:
			# memoize the mf (I don't know if some nodes are duplicated)
			if node['nodeId'] in enhanced_dom_tree_node_lookup:
				return enhanced_dom_tree_node_lookup[node['nodeId']]

			ax_node = ax_tree_lookup.get(node['backendNodeId'])
			if ax_node:
				enhanced_ax_node = self._build_enhanced_ax_node(ax_node)
			else:
				enhanced_ax_node = None

			# To make attributes more readable
			attributes: dict[str, str] | None = None
			if 'attributes' in node and node['attributes']:
				attributes = {}
				for i in range(0, len(node['attributes']), 2):
					attributes[node['attributes'][i]] = node['attributes'][i + 1]

			shadow_root_type = None
			if 'shadowRootType' in node and node['shadowRootType']:
				try:
					shadow_root_type = ShadowRootType(node['shadowRootType'])
				except ValueError:
					pass

			dom_tree_node = EnhancedDOMTreeNode(
				node_id=node['nodeId'],
				backend_node_id=node['backendNodeId'],
				node_type=NodeType(node['nodeType']),
				node_name=node['nodeName'],
				node_value=node['nodeValue'],
				attributes=attributes,
				is_scrollable=node.get('isScrollable', None),
				frame_id=node.get('frameId', None),
				content_document=None,
				shadow_root_type=shadow_root_type,
				shadow_roots=None,
				parent_node=None,
				children_nodes=None,
				ax_node=enhanced_ax_node,
				snapshot_node=snapshot_lookup.get(node['backendNodeId'], None),
			)

			enhanced_dom_tree_node_lookup[node['nodeId']] = dom_tree_node

			if 'parentId' in node and node['parentId']:
				dom_tree_node.parent_node = enhanced_dom_tree_node_lookup[
					node['parentId']
				]  # parents should always be in the lookup

			if 'contentDocument' in node and node['contentDocument']:
				dom_tree_node.content_document = _construct_enhanced_node(node['contentDocument'])  # maybe new maybe not, idk

			if 'shadowRoots' in node and node['shadowRoots']:
				dom_tree_node.shadow_roots = []
				for shadow_root in node['shadowRoots']:
					dom_tree_node.shadow_roots.append(_construct_enhanced_node(shadow_root))

			if 'children' in node and node['children']:
				dom_tree_node.children_nodes = []
				for child in node['children']:
					dom_tree_node.children_nodes.append(_construct_enhanced_node(child))

			return dom_tree_node

		enhanced_dom_tree_node = _construct_enhanced_node(dom_tree['root'])

		return enhanced_dom_tree_node

	async def _get_all_trees(self) -> tuple[CaptureSnapshotReturns, GetDocumentReturns, GetFullAXTreeReturns]:
		session_id = await self._get_current_page_session_id()
		cdp_client = await self._get_cdp_client()

		# Enhanced iframe content loading - wait for all iframes to be fully loaded
		await self._ensure_iframe_content_loaded(cdp_client, session_id)

		snapshot_request = cdp_client.send.DOMSnapshot.captureSnapshot(
			params={
				'computedStyles': REQUIRED_COMPUTED_STYLES,
				'includePaintOrder': True,
				'includeDOMRects': True,
				'includeBlendedBackgroundColors': False,
				'includeTextColorOpacities': False,
			},
			session_id=session_id,
		)

		dom_tree_request = cdp_client.send.DOM.getDocument(params={'depth': -1, 'pierce': True}, session_id=session_id)

		ax_tree_request = cdp_client.send.Accessibility.getFullAXTree(session_id=session_id)

		start = time.time()
		snapshot, dom_tree, ax_tree = await asyncio.gather(snapshot_request, dom_tree_request, ax_tree_request)
		end = time.time()

		# Get current page info for better debugging
		current_page = await self.browser_session.get_current_page()
		page_info = f"tab '{current_page.url}'"

		print(f'Time taken to get DOM tree for {page_info}: {end - start:.2f} seconds')

		return snapshot, dom_tree, ax_tree

	async def _ensure_iframe_content_loaded(self, cdp_client: CDPClient, session_id: str) -> None:
		"""Ensure all iframe content is fully loaded before capturing DOM tree."""
		try:
			print('🔄 Ensuring iframe content is fully loaded...')

			# Step 1: Get full DOM to find iframes (use deeper traversal)
			initial_dom = await cdp_client.send.DOM.getDocument(params={'depth': -1, 'pierce': False}, session_id=session_id)

			# Step 2: Find all iframe elements
			iframe_nodes = []
			self._find_iframes_recursive_sync(initial_dom['root'], iframe_nodes)

			if iframe_nodes:
				print(f'📋 Found {len(iframe_nodes)} iframe(s) to load...')

				# Step 3: Wait for each iframe to load content
				for iframe_node in iframe_nodes:
					await self._wait_for_iframe_content(cdp_client, session_id, iframe_node)

				# Step 4: Additional wait for dynamic content to settle
				await asyncio.sleep(1.5)
				print('✅ All iframe content loaded')
			else:
				print('📋 No iframes found on page')

		except Exception as e:
			print(f'⚠️ Error ensuring iframe content loaded: {e}')
			# Continue anyway - don't fail the entire DOM capture

	def _find_iframes_recursive_sync(self, node: Node, iframe_nodes: list) -> None:
		"""Synchronously find all iframe elements in the DOM tree."""
		try:
			if node.get('nodeName', '').upper() == 'IFRAME':
				iframe_nodes.append(node)
				print(f'  🎯 Found iframe: {node.get("nodeName")} (nodeId: {node.get("nodeId")})')

			# Recursively check children
			if 'children' in node:
				for child in node['children']:
					self._find_iframes_recursive_sync(child, iframe_nodes)

		except Exception as e:
			print(f'⚠️ Error in iframe recursive search: {e}')

	async def _find_iframes_recursive(self, cdp_client: CDPClient, session_id: str, node: Node, iframe_nodes: list) -> None:
		"""Recursively find all iframe elements in the DOM."""
		try:
			if node.get('nodeName', '').upper() == 'IFRAME':
				iframe_nodes.append(node)

			# Get children of this node
			if 'children' in node:
				for child in node['children']:
					await self._find_iframes_recursive(cdp_client, session_id, child, iframe_nodes)
			else:
				# If no children in the current node, request them
				try:
					node_id = node.get('nodeId')
					if node_id:
						children_result = await cdp_client.send.DOM.requestChildNodes(
							params={'nodeId': node_id, 'depth': 1}, session_id=session_id
						)
						# Children are added to the node via events, so re-check
						if 'children' in node:
							for child in node['children']:
								await self._find_iframes_recursive(cdp_client, session_id, child, iframe_nodes)
				except Exception:
					pass  # Continue if we can't get children for this node

		except Exception as e:
			print(f'⚠️ Error finding iframes: {e}')

	async def _wait_for_iframe_content(self, cdp_client: CDPClient, session_id: str, iframe_node: Node) -> None:
		"""Wait for a specific iframe's content to be fully loaded."""
		try:
			iframe_src = ''
			if 'attributes' in iframe_node:
				# Extract src attribute
				attrs = iframe_node['attributes']
				for i in range(0, len(attrs), 2):
					if i + 1 < len(attrs) and attrs[i] == 'src':
						iframe_src = attrs[i + 1]
						break

			print(f'  🔄 Loading iframe: {iframe_src[:50]}{"..." if len(iframe_src) > 50 else ""}')

			# Step 1: Force request child nodes to ensure content is loaded
			node_id = iframe_node.get('nodeId')
			if not node_id:
				print('    ⚠️ No nodeId for iframe')
				return

			# Step 2: Multiple attempts to get iframe content
			max_retries = 8
			for attempt in range(max_retries):
				try:
					# Request child nodes first to trigger content loading
					await cdp_client.send.DOM.requestChildNodes(
						params={'nodeId': node_id, 'depth': -1, 'pierce': True}, session_id=session_id
					)

					# Small wait for content to load
					await asyncio.sleep(0.3)

					# Get the updated node with content document
					updated_node = await cdp_client.send.DOM.describeNode(params={'nodeId': node_id}, session_id=session_id)

					# Check if we now have content document
					content_doc = updated_node.get('node', {}).get('contentDocument')
					if content_doc:
						print(f'    ✅ Iframe content loaded (attempt {attempt + 1})')

						# Also request children of the content document to ensure full loading
						content_doc_id = content_doc.get('nodeId')
						if content_doc_id:
							await cdp_client.send.DOM.requestChildNodes(
								params={'nodeId': content_doc_id, 'depth': -1, 'pierce': True}, session_id=session_id
							)
							await asyncio.sleep(0.2)
						break

					# If no content document yet, wait and retry
					await asyncio.sleep(0.4)

				except Exception as retry_error:
					if attempt == max_retries - 1:
						print(f'    ⚠️ Failed to load iframe content after {max_retries} attempts: {retry_error}')
					else:
						await asyncio.sleep(0.4)

		except Exception as e:
			print(f'⚠️ Error waiting for iframe content: {e}')

	async def get_dom_tree(self) -> EnhancedDOMTreeNode:
		snapshot, dom_tree, ax_tree = await self._get_all_trees()

		start = time.time()
		enhanced_dom_tree = await self._build_enhanced_dom_tree(dom_tree, ax_tree, snapshot)
		end = time.time()

		# Get current page info for better debugging
		current_page = await self.browser_session.get_current_page()
		page_info = f"tab '{current_page.url}'"

		print(f'Time taken to build enhanced DOM tree for {page_info}: {end - start:.2f} seconds')

		return enhanced_dom_tree

	async def get_serialized_dom_tree(
		self,
		include_attributes: list[str] | None = None,
	) -> tuple[str, dict[int, EnhancedDOMTreeNode]]:
		"""Get the serialized DOM tree representation for LLM consumption.

		This method now automatically handles multi-tab scenarios by:
		- Always using the current active tab from the browser session
		- Caching CDP sessions per tab for efficiency
		- Detecting tab switches and updating accordingly

		Args:
			include_attributes: List of attributes to include

		Returns:
			- Serialized string representation including iframe and shadow content
			- Selector map mapping interactive indices to DOM nodes with context
		"""
		enhanced_dom_tree = await self.get_dom_tree()

		start = time.time()
		serialized, selector_map = DOMTreeSerializer(enhanced_dom_tree).serialize_accessible_elements(include_attributes)
		end = time.time()

		# Get current page info for better debugging
		current_page = await self.browser_session.get_current_page()
		page_info = f"tab '{current_page.url}'"

		print(f'Time taken to serialize DOM tree for {page_info}: {end - start:.2f} seconds')
		print(f'🎯 Detected {len(selector_map)} interactive elements in {page_info} (comprehensive mode)')

		return serialized, selector_map

	async def cleanup_closed_tabs(self) -> None:
		"""Clean up cached sessions for tabs that have been closed."""
		if not self.browser_session.browser_context:
			return

		# Get current active page GUIDs
		active_page_guids = set()
		for page in self.browser_session.browser_context.pages:
			if not page.is_closed():
				active_page_guids.add(page._impl_obj._guid)

		# Remove cached sessions for closed tabs
		cached_guids = set(self.page_session_store.keys())
		closed_guids = cached_guids - active_page_guids

		if closed_guids:
			print(f'🧹 Cleaning up {len(closed_guids)} cached sessions for closed tabs')
			for guid in closed_guids:
				del self.page_session_store[guid]
				print(f'  - Removed session cache for tab {guid[:8]}...')

		# Update last processed page if it was closed
		if self._last_processed_page_guid and self._last_processed_page_guid not in active_page_guids:
			self._last_processed_page_guid = None
			print('🔄 Reset last processed page due to tab closure')
