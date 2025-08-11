#!/usr/bin/env python3
"""
Test to verify that two separate CDP connections to the same browser
see the same backendNodeIds, frameIds, and targetIds.
"""

import asyncio
import subprocess
import time
from typing import Any, Dict, List

import httpx
import pytest
from cdp_use import CDPClient
from pytest_httpserver import HTTPServer


@pytest.fixture
async def chrome_browser():
    """Launch a Chrome browser instance and return its CDP URL."""
    # Launch Chrome with remote debugging
    chrome_process = subprocess.Popen([
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--remote-debugging-port=9222',
        '--headless=new',  # Run headless for testing
        '--disable-gpu',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-web-security',
        '--disable-features=IsolateOrigins,site-per-process',
        '--user-data-dir=/tmp/chrome_test_profile',
    ])
    
    # Wait for Chrome to start
    time.sleep(2)
    
    # Get the WebSocket URL
    async with httpx.AsyncClient() as client:
        for _ in range(10):  # Retry up to 10 times
            try:
                version_info = await client.get('http://localhost:9222/json/version')
                ws_url = version_info.json()['webSocketDebuggerUrl']
                break
            except:
                time.sleep(0.5)
        else:
            chrome_process.kill()
            raise RuntimeError("Failed to connect to Chrome")
    
    yield ws_url
    
    # Cleanup
    chrome_process.kill()
    chrome_process.wait()


@pytest.fixture
def test_html_server(httpserver: HTTPServer):
    """Set up a test HTML page with nested elements and iframes."""
    
    # Main page HTML
    main_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
    </head>
    <body>
        <h1 id="main-title">Main Page</h1>
        <div id="content">
            <p>This is a test paragraph with <span id="nested-span">nested content</span></p>
            <button id="test-button" onclick="console.log('clicked')">Click Me</button>
            <input id="test-input" type="text" placeholder="Enter text">
            <iframe id="test-iframe" src="/iframe.html" width="400" height="200"></iframe>
        </div>
        <div id="shadow-host"></div>
        <script>
            // Create shadow DOM
            const host = document.getElementById('shadow-host');
            const shadow = host.attachShadow({mode: 'open'});
            shadow.innerHTML = '<div id="shadow-content">Shadow DOM Content</div>';
        </script>
    </body>
    </html>
    """
    
    # Iframe HTML
    iframe_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Iframe Page</title>
    </head>
    <body>
        <h2 id="iframe-title">Iframe Content</h2>
        <p id="iframe-text">This is content inside an iframe</p>
    </body>
    </html>
    """
    
    httpserver.expect_request("/").respond_with_data(main_html, content_type="text/html")
    httpserver.expect_request("/iframe.html").respond_with_data(iframe_html, content_type="text/html")
    
    return httpserver.url_for("/")


async def get_dom_info(cdp_client: CDPClient, session_id: str = None) -> Dict[str, Any]:
    """Get comprehensive DOM information from a CDP client."""
    
    # Get DOM tree
    dom_tree = await cdp_client.send.DOM.getDocument(
        params={'depth': -1, 'pierce': True},
        session_id=session_id
    )
    
    # Get frame tree
    frame_tree = await cdp_client.send.Page.getFrameTree(session_id=session_id)
    
    # Get all targets
    targets = await cdp_client.send.Target.getTargets()
    
    # Get accessibility tree
    ax_tree = await cdp_client.send.Accessibility.getFullAXTree(session_id=session_id)
    
    # Collect all backend node IDs from DOM tree
    backend_node_ids = set()
    node_ids = set()
    frame_ids = set()
    
    def collect_node_info(node):
        if 'backendNodeId' in node:
            backend_node_ids.add(node['backendNodeId'])
        if 'nodeId' in node:
            node_ids.add(node['nodeId'])
        if 'frameId' in node:
            frame_ids.add(node['frameId'])
        
        # Recurse through children
        if 'children' in node:
            for child in node['children']:
                collect_node_info(child)
        
        # Check content document (for iframes)
        if 'contentDocument' in node:
            collect_node_info(node['contentDocument'])
        
        # Check shadow roots
        if 'shadowRoots' in node:
            for shadow in node['shadowRoots']:
                collect_node_info(shadow)
    
    collect_node_info(dom_tree['root'])
    
    # Collect frame IDs from frame tree
    def collect_frame_ids(frame_node):
        frame_ids.add(frame_node['frame']['id'])
        if 'childFrames' in frame_node:
            for child in frame_node['childFrames']:
                collect_frame_ids(child)
    
    collect_frame_ids(frame_tree['frameTree'])
    
    # Collect target IDs
    target_ids = {t['targetId'] for t in targets['targetInfos']}
    
    # Collect accessibility node IDs
    ax_node_ids = set()
    ax_backend_ids = set()
    for ax_node in ax_tree.get('nodes', []):
        if 'nodeId' in ax_node:
            ax_node_ids.add(ax_node['nodeId'])
        if 'backendDOMNodeId' in ax_node:
            ax_backend_ids.add(ax_node['backendDOMNodeId'])
    
    return {
        'backend_node_ids': backend_node_ids,
        'node_ids': node_ids,
        'frame_ids': frame_ids,
        'target_ids': target_ids,
        'ax_node_ids': ax_node_ids,
        'ax_backend_ids': ax_backend_ids,
        'dom_root': dom_tree['root'],
        'frame_tree': frame_tree['frameTree'],
    }


async def compare_cdp_connections(ws_url: str, test_url: str):
    """Create two CDP connections and compare what they see."""
    
    # Create first CDP client
    client1 = CDPClient(ws_url)
    await client1.start()
    
    # Create second CDP client (separate connection)
    client2 = CDPClient(ws_url)
    await client2.start()
    
    try:
        # Navigate to test page using first client
        targets1 = await client1.send.Target.getTargets()
        page_target = next((t for t in targets1['targetInfos'] if t['type'] == 'page'), None)
        
        if not page_target:
            # Create a new page
            new_target = await client1.send.Target.createTarget(params={'url': test_url})
            target_id = new_target['targetId']
        else:
            target_id = page_target['targetId']
            # Navigate existing page
            session1 = await client1.send.Target.attachToTarget(
                params={'targetId': target_id, 'flatten': True}
            )
            session_id1 = session1['sessionId']
            await client1.send.Page.enable(session_id=session_id1)
            await client1.send.Page.navigate(params={'url': test_url}, session_id=session_id1)
        
        # Wait for page to load
        await asyncio.sleep(2)
        
        # Attach both clients to the same target
        session1 = await client1.send.Target.attachToTarget(
            params={'targetId': target_id, 'flatten': True}
        )
        session_id1 = session1['sessionId']
        
        session2 = await client2.send.Target.attachToTarget(
            params={'targetId': target_id, 'flatten': True}
        )
        session_id2 = session2['sessionId']
        
        # Enable necessary domains on both sessions
        for session_id, client in [(session_id1, client1), (session_id2, client2)]:
            await client.send.DOM.enable(session_id=session_id)
            await client.send.Page.enable(session_id=session_id)
            await client.send.Accessibility.enable(session_id=session_id)
        
        # Get DOM info from both clients
        info1 = await get_dom_info(client1, session_id1)
        info2 = await get_dom_info(client2, session_id2)
        
        # Compare results
        print("\n" + "="*60)
        print("CDP CONNECTION COMPARISON RESULTS")
        print("="*60)
        
        # Compare backend node IDs
        print(f"\nBackend Node IDs:")
        print(f"  Client 1: {len(info1['backend_node_ids'])} nodes")
        print(f"  Client 2: {len(info2['backend_node_ids'])} nodes")
        print(f"  Same IDs: {info1['backend_node_ids'] == info2['backend_node_ids']}")
        if info1['backend_node_ids'] != info2['backend_node_ids']:
            diff1 = info1['backend_node_ids'] - info2['backend_node_ids']
            diff2 = info2['backend_node_ids'] - info1['backend_node_ids']
            if diff1:
                print(f"  Only in Client 1: {diff1}")
            if diff2:
                print(f"  Only in Client 2: {diff2}")
        
        # Compare node IDs (these are session-specific)
        print(f"\nNode IDs (session-specific):")
        print(f"  Client 1: {len(info1['node_ids'])} nodes")
        print(f"  Client 2: {len(info2['node_ids'])} nodes")
        print(f"  Same IDs: {info1['node_ids'] == info2['node_ids']}")
        
        # Compare frame IDs
        print(f"\nFrame IDs:")
        print(f"  Client 1: {info1['frame_ids']}")
        print(f"  Client 2: {info2['frame_ids']}")
        print(f"  Same IDs: {info1['frame_ids'] == info2['frame_ids']}")
        
        # Compare target IDs
        print(f"\nTarget IDs:")
        print(f"  Client 1: {len(info1['target_ids'])} targets")
        print(f"  Client 2: {len(info2['target_ids'])} targets")
        print(f"  Same IDs: {info1['target_ids'] == info2['target_ids']}")
        
        # Compare accessibility backend IDs
        print(f"\nAccessibility Backend DOM Node IDs:")
        print(f"  Client 1: {len(info1['ax_backend_ids'])} nodes")
        print(f"  Client 2: {len(info2['ax_backend_ids'])} nodes")
        print(f"  Same IDs: {info1['ax_backend_ids'] == info2['ax_backend_ids']}")
        
        # Test specific element lookup
        print(f"\n" + "="*60)
        print("SPECIFIC ELEMENT LOOKUP TEST")
        print("="*60)
        
        # Query for specific elements using both clients
        for selector in ['#main-title', '#test-button', '#test-input', '#test-iframe']:
            result1 = await client1.send.DOM.querySelector(
                params={'nodeId': info1['dom_root']['nodeId'], 'selector': selector},
                session_id=session_id1
            )
            
            result2 = await client2.send.DOM.querySelector(
                params={'nodeId': info2['dom_root']['nodeId'], 'selector': selector},
                session_id=session_id2
            )
            
            # Get backend node IDs for the queried elements
            if result1['nodeId'] > 0:
                node1 = await client1.send.DOM.describeNode(
                    params={'nodeId': result1['nodeId']},
                    session_id=session_id1
                )
                backend_id1 = node1['node']['backendNodeId']
            else:
                backend_id1 = None
            
            if result2['nodeId'] > 0:
                node2 = await client2.send.DOM.describeNode(
                    params={'nodeId': result2['nodeId']},
                    session_id=session_id2
                )
                backend_id2 = node2['node']['backendNodeId']
            else:
                backend_id2 = None
            
            print(f"\nElement: {selector}")
            print(f"  Client 1 - NodeId: {result1['nodeId']}, BackendId: {backend_id1}")
            print(f"  Client 2 - NodeId: {result2['nodeId']}, BackendId: {backend_id2}")
            print(f"  Same Backend IDs: {backend_id1 == backend_id2}")
        
        # Summary
        print(f"\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"✓ BackendNodeIds are {'CONSISTENT' if info1['backend_node_ids'] == info2['backend_node_ids'] else 'DIFFERENT'} across connections")
        print(f"✓ FrameIds are {'CONSISTENT' if info1['frame_ids'] == info2['frame_ids'] else 'DIFFERENT'} across connections")
        print(f"✓ TargetIds are {'CONSISTENT' if info1['target_ids'] == info2['target_ids'] else 'DIFFERENT'} across connections")
        print(f"✓ NodeIds are {'CONSISTENT' if info1['node_ids'] == info2['node_ids'] else 'DIFFERENT'} (expected to be different - session-specific)")
        
    finally:
        # Cleanup
        await client1.stop()
        await client2.stop()


@pytest.mark.asyncio
async def test_dual_cdp_connections(chrome_browser, test_html_server):
    """Test that two CDP connections see the same IDs."""
    await compare_cdp_connections(chrome_browser, test_html_server)


if __name__ == "__main__":
    # Run the test
    pytest.main([__file__, "-v", "-s"])