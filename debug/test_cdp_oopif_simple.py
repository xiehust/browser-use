#!/usr/bin/env python3
"""Test cdp_client_for_frame with cross-origin iframes (OOPIFs)."""

import asyncio
from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.events import BrowserStartEvent
from pytest_httpserver import HTTPServer

async def test_oopif():
    """Test that we can find the correct target for an OOPIF."""
    
    # Create two HTTP servers on different ports for cross-origin testing
    server1 = HTTPServer(host="localhost", port=2344)
    server1.start()
    
    server2 = HTTPServer(host="localhost", port=2345)
    server2.start()
    
    try:
        # Set up main page on first server (abc.localhost:2344)
        main_page_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Main Page</title></head>
        <body>
            <h1>Main Page on abc.localhost</h1>
            <iframe id="cross-origin-frame" 
                    src="http://xyz.localhost:2345/iframe.html" 
                    width="600" 
                    height="400">
            </iframe>
        </body>
        </html>
        """
        server1.expect_request("/").respond_with_data(main_page_html, content_type="text/html")
        
        # Set up iframe page on second server (xyz.localhost:2345)
        iframe_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Iframe Page</title></head>
        <body>
            <h1>Cross-Origin Iframe on xyz.localhost</h1>
            <p>This is a cross-origin iframe that should create an OOPIF.</p>
        </body>
        </html>
        """
        server2.expect_request("/iframe.html").respond_with_data(iframe_html, content_type="text/html")
        
        # Create headless browser profile
        profile = BrowserProfile(
            headless=True,
            user_data_dir=None,
            # Disable web security to allow cross-origin iframes in test
            extra_args=["--disable-web-security", "--disable-site-isolation-trials"]
        )
        session = BrowserSession(browser_profile=profile)
        
        try:
            # Start browser
            await session.on_BrowserStartEvent(BrowserStartEvent())
            print("Browser started")
            
            # Navigate to main page
            main_url = f"http://abc.localhost:2344/"
            await session._cdp_navigate(main_url)
            print(f"Navigated to main page: {main_url}")
            
            # Wait for iframe to load
            await asyncio.sleep(3)
            
            # Get all targets to see if we have an OOPIF
            targets = await session.cdp_client.send.Target.getTargets()
            target_infos = targets.get('targetInfos', [])
            print(f"\nFound {len(target_infos)} targets:")
            
            iframe_targets = []
            for t in target_infos:
                t_type = t.get('type')
                t_url = t.get('url', 'none')
                t_id = t.get('targetId', 'unknown')
                print(f"  - Type: {t_type}, URL: {t_url}")
                
                # Check if this is our cross-origin iframe
                if t_type == 'iframe' and 'xyz.localhost' in t_url:
                    iframe_targets.append(t)
                    print(f"    ^ This is our OOPIF target! ID: {t_id[:8]}...")
            
            # If we have an OOPIF target, get its frame ID directly
            if iframe_targets:
                # For OOPIF, the frame exists in its own target
                iframe_target = iframe_targets[0]
                iframe_target_id = iframe_target['targetId']
                
                # Attach to the iframe target to get its frame ID
                cdp_client, session_id = await session.cdp_client_for_target(iframe_target_id)
                try:
                    await cdp_client.send.Page.enable(session_id=session_id)
                    iframe_tree = await cdp_client.send.Page.getFrameTree(session_id=session_id)
                    iframe_frame_id = iframe_tree.get('frameTree', {}).get('frame', {}).get('id')
                    print(f"\nIframe target's frame ID: {iframe_frame_id}")
                finally:
                    await cdp_client.send.Target.detachFromTarget(params={'sessionId': session_id})
            else:
                # Fall back to checking main page's frame tree
                cdp_client, session_id = await session.cdp_client_for_target(session.current_target_id)
                try:
                    await cdp_client.send.Page.enable(session_id=session_id)
                    frame_tree = await cdp_client.send.Page.getFrameTree(session_id=session_id)
                    
                    # Find the iframe frame ID
                    iframe_frame_id = None
                    child_frames = frame_tree.get('frameTree', {}).get('childFrames', [])
                    
                    print(f"\nMain page has {len(child_frames)} child frames")
                    for child in child_frames:
                        frame = child.get('frame', {})
                        frame_id = frame.get('id')
                        frame_url = frame.get('url', '')
                        print(f"  Frame ID: {frame_id}")
                        print(f"    URL: {frame_url}")
                        
                        if 'xyz.localhost' in frame_url:
                            iframe_frame_id = frame_id
                            print(f"    ^ This is our cross-origin iframe frame!")
                finally:
                    await cdp_client.send.Target.detachFromTarget(params={'sessionId': session_id})
            
            if iframe_frame_id:
                    print(f"\nTesting cdp_client_for_frame with frame ID: {iframe_frame_id}")
                    
                    # Test our implementation
                    try:
                        client, sid, tid = await session.cdp_client_for_frame(iframe_frame_id)
                        print(f"✅ SUCCESS! Got CDP client for OOPIF")
                        print(f"  Target ID: {tid}")
                        print(f"  Session ID: {sid}")
                        
                        # Verify we're connected to the right frame
                        result = await client.send.Runtime.evaluate(
                            params={'expression': 'document.title'},
                            session_id=sid
                        )
                        title = result.get('result', {}).get('value', 'unknown')
                        print(f"  Frame document title: {title}")
                        
                        # Also check the URL
                        url_result = await client.send.Runtime.evaluate(
                            params={'expression': 'window.location.href'},
                            session_id=sid
                        )
                        url = url_result.get('result', {}).get('value', 'unknown')
                        print(f"  Frame URL: {url}")
                        
                        # Verify this is the cross-origin iframe
                        assert 'xyz.localhost' in url, f"Expected xyz.localhost in URL, got: {url}"
                        assert title == "Iframe Page", f"Expected 'Iframe Page' title, got: {title}"
                        
                        print("\n✅ Test PASSED! Successfully found and connected to OOPIF target.")
                        
                        # Clean up
                        await client.send.Target.detachFromTarget(params={'sessionId': sid})
                        
                    except Exception as e:
                        print(f"❌ Failed to get client for iframe: {e}")
                        raise
            else:
                print("❌ Could not find cross-origin iframe in frame tree")
                raise AssertionError("Cross-origin iframe not found in frame tree")
                
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            if session.cdp_client:
                await session.cdp_client.stop()
    finally:
        server1.stop()
        server2.stop()

if __name__ == "__main__":
    asyncio.run(test_oopif())