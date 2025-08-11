#!/usr/bin/env python3
"""Simple test for cdp_client_for_frame."""

import asyncio
from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.events import BrowserStartEvent

async def test():
    # Create headless profile
    profile = BrowserProfile(headless=True, user_data_dir=None)
    session = BrowserSession(browser_profile=profile)
    
    try:
        # Start browser
        await session.on_BrowserStartEvent(BrowserStartEvent())
        print("Browser started")
        
        # Navigate to about:blank (fast)
        await session._cdp_navigate("about:blank")
        print("Navigated to about:blank")
        
        # Get the main frame ID
        cdp_client, session_id = await session.cdp_client_for_target(session.current_target_id)
        try:
            # Enable Page domain
            await cdp_client.send.Page.enable(session_id=session_id)
            
            # Get frame tree
            frame_tree = await cdp_client.send.Page.getFrameTree(session_id=session_id)
            main_frame_id = frame_tree.get('frameTree', {}).get('frame', {}).get('id')
            print(f"Main frame ID: {main_frame_id}")
            
            if main_frame_id:
                # Test getting client for the main frame
                print(f"Testing cdp_client_for_frame with main frame...")
                client, sid, tid = await session.cdp_client_for_frame(main_frame_id)
                print(f"SUCCESS! Got CDP client for frame")
                print(f"  Target ID: {tid}")
                print(f"  Session ID: {sid}")
                
                # Clean up
                await client.send.Target.detachFromTarget(params={'sessionId': sid})
                
        finally:
            await cdp_client.send.Target.detachFromTarget(params={'sessionId': session_id})
            
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if session.cdp_client:
            await session.cdp_client.stop()

if __name__ == "__main__":
    success = asyncio.run(test())
    exit(0 if success else 1)