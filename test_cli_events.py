#!/usr/bin/env python3
"""
Test the CLI event handling to check for duplicate events.
"""

import asyncio
import os
import sys

# Set environment for CDP debug logging
os.environ['BROWSER_USE_CDP_DEBUG'] = 'true'
os.environ['BROWSER_USE_LOGGING_LEVEL'] = 'debug'

from browser_use.browser import BrowserSession
from browser_use.browser.events import BrowserStateRequestEvent, NavigateToUrlEvent
from browser_use.agent.service import Agent
from browser_use.controller.service import Controller
from browser_use.llm.openai.chat import ChatOpenAI
from browser_use.config import Config

async def test_event_duplication():
    """Test if events are being duplicated when using Agent with browser_session."""
    print("Testing event duplication with Agent...")
    
    # Create a browser session
    browser_session = BrowserSession()
    
    # Track events
    event_count = {}
    
    def count_event(event):
        event_name = event.__class__.__name__
        event_count[event_name] = event_count.get(event_name, 0) + 1
        print(f"  → {event_name} (count: {event_count[event_name]})")
    
    # Register event counter
    browser_session.event_bus.on('*', count_event)
    print("Registered event counter on browser_session.event_bus")
    
    # Check initial handler count
    handler_count = len(browser_session.event_bus.handlers.get('*', []))
    print(f"Initial handlers on '*': {handler_count}")
    
    # Create agent with the browser session (simulating what CLI does)
    try:
        # Create config
        config = Config()
        
        # Create a mock LLM (won't actually use it)
        llm = ChatOpenAI(model='gpt-4', api_key='dummy')
        
        # Create controller
        controller = Controller()
        
        # Create agent with existing browser_session
        agent = Agent(
            task="Test task",
            llm=llm,
            controller=controller,
            browser_session=browser_session,
        )
        
        # Check if Agent created its own event bus
        print(f"\nAgent browser_session is same object: {agent.browser_session is browser_session}")
        print(f"Agent has own eventbus: {hasattr(agent, 'eventbus')}")
        
        # Check handler count after agent creation
        handler_count = len(browser_session.event_bus.handlers.get('*', []))
        print(f"Handlers after Agent creation: {handler_count}")
        
        # Dispatch a test event
        print("\nDispatching test NavigateToUrlEvent...")
        event_count.clear()
        test_event = browser_session.event_bus.dispatch(NavigateToUrlEvent(url="https://example.com"))
        
        # Wait a bit for async handlers
        await asyncio.sleep(0.1)
        
        # Check counts
        print(f"\nEvent counts after dispatch:")
        for event_name, count in event_count.items():
            if count > 1:
                print(f"  ❌ {event_name}: {count} (DUPLICATE!)")
            else:
                print(f"  ✅ {event_name}: {count}")
        
        # Check if NavigateToUrlEvent was duplicated
        nav_count = event_count.get('NavigateToUrlEvent', 0)
        if nav_count > 1:
            print(f"\n❌ FAILURE: NavigateToUrlEvent seen {nav_count} times (duplicated)")
            return False
        else:
            print(f"\n✅ SUCCESS: No event duplication detected")
            return True
            
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = asyncio.run(test_event_duplication())
    sys.exit(0 if success else 1)