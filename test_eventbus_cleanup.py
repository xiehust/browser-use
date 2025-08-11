#!/usr/bin/env python3
"""
Test the event bus handler cleanup logic to ensure no duplicate handlers.
"""

import os
import sys

# Set environment for CDP debug logging
os.environ['BROWSER_USE_CDP_DEBUG'] = 'true'
os.environ['BROWSER_USE_LOGGING_LEVEL'] = 'debug'

from browser_use.browser import BrowserSession
from bubus import EventBus

def test_handler_cleanup():
    """Test that handler cleanup works correctly."""
    print("Testing event bus handler cleanup...")
    
    # Create a browser session with event bus
    browser_session = BrowserSession()
    
    # Keep track of handler functions
    handler_funcs = []
    handler_ids = []
    
    # Simulate what the CLI does - register handlers and clean up old ones
    for i in range(3):
        # Clean up old handler if exists
        if handler_funcs:
            old_handler = handler_funcs[-1]
            # Find and remove old handler
            if '*' in browser_session.event_bus.handlers:
                handler_list = browser_session.event_bus.handlers['*']
                if old_handler in handler_list:
                    handler_list.remove(old_handler)
                    print(f"  Removed old handler {i-1}")
        
        # Create new handler
        def log_event(event):
            print(f"Handler {i}: {event.__class__.__name__}")
        
        # Register new handler
        browser_session.event_bus.on('*', log_event)
        handler_funcs.append(log_event)
        handler_ids.append(id(log_event))
        
        # Check how many handlers are registered
        handler_count = len(browser_session.event_bus.handlers.get('*', []))
        print(f"Round {i+1}: {handler_count} handlers registered")
    
    # Final check
    final_count = len(browser_session.event_bus.handlers.get('*', []))
    print(f"\nFinal state: {final_count} handlers registered")
    
    if final_count == 1:
        print("✅ SUCCESS: Handler cleanup working correctly (only 1 handler)")
    else:
        print(f"❌ FAILURE: Expected 1 handler, but found {final_count}")
        print(f"Handler IDs: {[id(h) for h in browser_session.event_bus.handlers.get('*', [])]}")
    
    return final_count == 1

if __name__ == '__main__':
    success = test_handler_cleanup()
    sys.exit(0 if success else 1)