#!/usr/bin/env python3
"""Simple test to show frame hierarchies for v0 test pages."""

import asyncio
import logging
from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.events import BrowserStartEvent

# Silence all logging
logging.basicConfig(level=logging.CRITICAL)

async def show_frame_hierarchy(url):
    """Show frame hierarchy for a URL."""
    
    profile = BrowserProfile(headless=True, user_data_dir=None)
    session = BrowserSession(browser_profile=profile)
    
    try:
        await session.on_BrowserStartEvent(BrowserStartEvent())
        await session._cdp_navigate(url)
        await asyncio.sleep(2)
        
        # Get all frames using the method in session.py
        all_frames, target_sessions = await session.get_all_frames()
        
        # Clean up sessions
        for tid, sid in target_sessions.items():
            try:
                await session.cdp_client.send.Target.detachFromTarget(params={'sessionId': sid})
            except:
                pass
        
        return all_frames
        
    finally:
        if session.cdp_client:
            await session.cdp_client.stop()

async def main():
    """Test all three URLs."""
    
    test_urls = [
        "https://v0-website-with-clickable-elements.vercel.app/nested-iframe",
        "https://v0-website-with-clickable-elements.vercel.app/cross-origin", 
        "https://v0-website-with-clickable-elements.vercel.app/shadow-dom"
    ]
    
    for url in test_urls:
        print(f"\n{'='*80}")
        print(f"URL: {url}")
        print('='*80)
        
        try:
            all_frames = await show_frame_hierarchy(url)
            
            print(f"\nTotal frames: {len(all_frames)}")
            
            # Sort by parent relationship
            root_frames = []
            child_frames = []
            
            for frame_id, frame_info in all_frames.items():
                if not frame_info.get('parentFrameId'):
                    root_frames.append((frame_id, frame_info))
                else:
                    child_frames.append((frame_id, frame_info))
            
            # Display root frames first
            for frame_id, frame_info in root_frames:
                print(f"\n📍 Root Frame:")
                print(f"   URL: {frame_info.get('url', 'none')}")
                print(f"   Frame ID: {frame_id[:30]}...")
                print(f"   Target Type: {frame_info.get('frameTargetId', 'unknown')[:20]}...")
                print(f"   Cross-Origin: {frame_info.get('crossOriginIsolatedContextType', 'unknown')}")
            
            # Display child frames
            for frame_id, frame_info in child_frames:
                print(f"\n   └─ Child Frame:")
                print(f"      URL: {frame_info.get('url', 'none')}")
                print(f"      Frame ID: {frame_id[:30]}...")
                print(f"      Parent ID: {frame_info.get('parentFrameId', 'none')[:30]}...")
                print(f"      Target Type: {frame_info.get('frameTargetId', 'unknown')[:20]}...")
                print(f"      Cross-Origin: {frame_info.get('crossOriginIsolatedContextType', 'unknown')}")
                if frame_info.get('isCrossOrigin'):
                    print(f"      ⚠️  Cross-Origin iframe (OOPIF)")
                    
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())