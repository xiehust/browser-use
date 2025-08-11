#!/usr/bin/env python3
"""Test frame hierarchy for all three test URLs."""

import asyncio
from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.events import BrowserStartEvent

async def main():
	profile = BrowserProfile(headless=True, user_data_dir=None)
	session = BrowserSession(browser_profile=profile)
	
	urls = [
		"https://v0-website-with-clickable-elements.vercel.app/nested-iframe",
		"https://v0-website-with-clickable-elements.vercel.app/cross-origin",
		"https://v0-website-with-clickable-elements.vercel.app/shadow-dom"
	]
	
	try:
		await session.on_BrowserStartEvent(BrowserStartEvent())
		
		for url in urls:
			print("\n" + "="*80)
			print(f"Testing: {url}")
			print("="*80)
			
			# Navigate to URL
			await session._cdp_navigate(url)
			await asyncio.sleep(3)
			
			# Get all frames using the new method
			all_frames = await session.get_all_frames()
			
			print(f"\nTotal frames found: {len(all_frames)}")
			
			# Separate root and child frames
			root_frames = []
			child_frames = []
			
			for frame_id, frame_info in all_frames.items():
				if not frame_info.get('parentFrameId'):
					root_frames.append((frame_id, frame_info))
				else:
					child_frames.append((frame_id, frame_info))
			
			print(f"Root frames: {len(root_frames)}")
			print(f"Child frames: {len(child_frames)}")
			
			# Display frame hierarchy
			print("\n📋 Frame Hierarchy:")
			
			def print_frame_tree(frame_id, frame_info, indent=0, visited=None):
				if visited is None:
					visited = set()
				
				if frame_id in visited:
					return
				visited.add(frame_id)
				
				url = frame_info.get('url', 'none')
				parent_id = frame_info.get('parentFrameId')
				target_id = frame_info.get('frameTargetId')
				is_cross = frame_info.get('isCrossOrigin', False)
				
				prefix = "  " * indent + ("└─ " if indent > 0 else "")
				
				# Show frame details
				print(f"{prefix}Frame: {url[:60]}")
				print(f"{'  ' * (indent+1)}ID: {frame_id[:30]}...")
				if parent_id:
					print(f"{'  ' * (indent+1)}Parent: {parent_id[:30]}...")
				print(f"{'  ' * (indent+1)}Target: {target_id[:30]}...")
				if is_cross:
					print(f"{'  ' * (indent+1)}🔸 Cross-Origin (OOPIF)")
				
				# Find and print children
				children = frame_info.get('childFrameIds', [])
				for child_id in children:
					if child_id in all_frames:
						print_frame_tree(child_id, all_frames[child_id], indent + 1, visited)
			
			# Print from root frames
			for frame_id, frame_info in root_frames:
				print_frame_tree(frame_id, frame_info)
			
			# Check for orphan frames
			orphans = []
			for frame_id, frame_info in child_frames:
				parent_id = frame_info.get('parentFrameId')
				if parent_id and parent_id not in all_frames:
					orphans.append((frame_id, frame_info))
			
			if orphans:
				print(f"\n⚠️  Orphan frames (parent not in frame list):")
				for frame_id, frame_info in orphans:
					url = frame_info.get('url', 'none')
					parent_id = frame_info.get('parentFrameId')
					print(f"  - {url[:60]}")
					print(f"    Frame ID: {frame_id[:30]}...")
					print(f"    Missing Parent: {parent_id[:30]}...")
			
			# Summary for cross-origin page
			if 'cross-origin' in url:
				cross_origin_frames = [f for f in all_frames.values() if f.get('isCrossOrigin')]
				oopif_frames = [f for f in all_frames.values() if 'v0-simple-landing' in f.get('url', '')]
				
				print(f"\n📊 Cross-Origin Summary:")
				print(f"  Frames marked as cross-origin: {len(cross_origin_frames)}")
				print(f"  OOPIF frames (v0-simple-landing): {len(oopif_frames)}")
				
				for f in oopif_frames:
					parent_id = f.get('parentFrameId')
					if parent_id:
						print(f"  ✅ OOPIF frame correctly has parent: {parent_id[:30]}...")
					else:
						print(f"  ❌ OOPIF frame missing parent!")
	
	finally:
		if session.cdp_client:
			await session.cdp_client.stop()

if __name__ == "__main__":
	asyncio.run(main())