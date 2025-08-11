#!/usr/bin/env python3
"""Test cdp_client_for_frame with truly cross-origin iframes."""

import asyncio
from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.events import BrowserStartEvent
from pytest_httpserver import HTTPServer

async def test_cross_origin():
    """Test that getFrameTree shows cross-origin iframes."""
    
    # Create two HTTP servers on different ports
    server1 = HTTPServer(host="127.0.0.1", port=8881)
    server1.start()
    
    server2 = HTTPServer(host="127.0.0.1", port=8882)
    server2.start()
    
    try:
        # Set up main page on first server (127.0.0.1:8881)
        main_page_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Main Page</title></head>
        <body>
            <h1>Main Page on 127.0.0.1:8881</h1>
            <iframe id="cross-origin-frame" 
                    src="http://localhost:8882/iframe.html" 
                    width="600" 
                    height="400">
            </iframe>
            <iframe id="same-origin-frame"
                    src="http://127.0.0.1:8881/same.html"
                    width="600"
                    height="200">
            </iframe>
        </body>
        </html>
        """
        server1.expect_request("/").respond_with_data(main_page_html, content_type="text/html")
        
        # Same-origin iframe
        same_origin_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Same Origin Frame</title></head>
        <body>
            <h1>Same Origin Iframe</h1>
        </body>
        </html>
        """
        server1.expect_request("/same.html").respond_with_data(same_origin_html, content_type="text/html")
        
        # Set up iframe page on second server (localhost:8882 - different origin!)
        iframe_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Cross Origin Frame</title></head>
        <body>
            <h1>Cross-Origin Iframe on localhost:8882</h1>
            <p>This is a cross-origin iframe that should be marked as such.</p>
        </body>
        </html>
        """
        server2.expect_request("/iframe.html").respond_with_data(iframe_html, content_type="text/html")
        
        # Create headless browser profile
        profile = BrowserProfile(
            headless=True,
            user_data_dir=None,
        )
        session = BrowserSession(browser_profile=profile)
        
        try:
            # Start browser
            await session.on_BrowserStartEvent(BrowserStartEvent())
            print("Browser started")
            
            # Navigate to main page
            main_url = f"http://127.0.0.1:8881/"
            await session._cdp_navigate(main_url)
            print(f"Navigated to main page: {main_url}")
            
            # Wait for iframes to load
            await asyncio.sleep(3)
            
            # Get all targets
            targets = await session.cdp_client.send.Target.getTargets()
            target_infos = targets.get('targetInfos', [])
            print(f"\n=== Found {len(target_infos)} targets ===")
            
            for t in target_infos:
                t_type = t.get('type')
                t_url = t.get('url', 'none')
                t_id = t.get('targetId', 'unknown')
                if t_type in ['page', 'iframe']:
                    print(f"  {t_type}: {t_url}")
                    print(f"    Target ID: {t_id[:16]}...")
            
            # Get the main page's frame tree
            print("\n=== Main Page Frame Tree ===")
            cdp_client, session_id = await session.cdp_client_for_target(session.current_target_id)
            try:
                await cdp_client.send.Page.enable(session_id=session_id)
                frame_tree = await cdp_client.send.Page.getFrameTree(session_id=session_id)
                
                def print_frame_tree(node, indent=0):
                    """Recursively print the frame tree with all details."""
                    frame = node.get('frame', {})
                    frame_id = frame.get('id', 'unknown')
                    frame_url = frame.get('url', 'none')
                    secure_context = frame.get('secureContextType', 'unknown')
                    cross_origin = frame.get('crossOriginIsolatedContextType', 'unknown')
                    gated_api = frame.get('gatedAPIFeatures', [])
                    
                    print(f"{'  ' * indent}Frame ID: {frame_id}")
                    print(f"{'  ' * indent}  URL: {frame_url}")
                    print(f"{'  ' * indent}  Secure Context: {secure_context}")
                    print(f"{'  ' * indent}  Cross-Origin Isolated: {cross_origin}")
                    if gated_api:
                        print(f"{'  ' * indent}  Gated APIs: {gated_api}")
                    
                    # Print child frames
                    child_frames = node.get('childFrames', [])
                    if child_frames:
                        print(f"{'  ' * indent}  Has {len(child_frames)} child frame(s):")
                        for child in child_frames:
                            print_frame_tree(child, indent + 2)
                
                print_frame_tree(frame_tree.get('frameTree', {}))
                
                # Find cross-origin frames
                cross_origin_frames = []
                
                def find_cross_origin_frames(node):
                    """Find all frames marked as cross-origin."""
                    frame = node.get('frame', {})
                    
                    # Check if this frame is cross-origin
                    if 'localhost' in frame.get('url', ''):
                        cross_origin_frames.append({
                            'id': frame.get('id'),
                            'url': frame.get('url'),
                            'cross_origin': frame.get('crossOriginIsolatedContextType', 'unknown')
                        })
                    
                    # Check child frames
                    for child in node.get('childFrames', []):
                        find_cross_origin_frames(child)
                
                find_cross_origin_frames(frame_tree.get('frameTree', {}))
                
                if cross_origin_frames:
                    print(f"\n=== Testing cdp_client_for_frame ===")
                    for frame_info in cross_origin_frames:
                        frame_id = frame_info['id']
                        frame_url = frame_info['url']
                        print(f"\nTesting frame: {frame_url}")
                        print(f"  Frame ID: {frame_id}")
                        
                        try:
                            client, sid, tid = await session.cdp_client_for_frame(frame_id)
                            print(f"  ✅ SUCCESS! Got CDP client")
                            print(f"    Target ID: {tid[:16]}...")
                            print(f"    Session ID: {sid[:16]}...")
                            
                            # Test we can execute in the frame
                            result = await client.send.Runtime.evaluate(
                                params={'expression': 'document.title'},
                                session_id=sid
                            )
                            title = result.get('result', {}).get('value', 'unknown')
                            print(f"    Document title: {title}")
                            
                            # Check origin
                            origin_result = await client.send.Runtime.evaluate(
                                params={'expression': 'window.origin'},
                                session_id=sid
                            )
                            origin = origin_result.get('result', {}).get('value', 'unknown')
                            print(f"    Frame origin: {origin}")
                            
                            # Clean up
                            await client.send.Target.detachFromTarget(params={'sessionId': sid})
                            
                        except Exception as e:
                            print(f"  ❌ Failed: {e}")
                
            finally:
                await cdp_client.send.Target.detachFromTarget(params={'sessionId': session_id})
                
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
    asyncio.run(test_cross_origin())