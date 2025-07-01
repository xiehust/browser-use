# Multiple Screenshots Feature Implementation

## Overview

This implementation adds support for including multiple screenshots in the agent's input message instead of just the current screenshot. The agent can now provide better context by including the last N screenshots from its history.

## Changes Made

### 1. Added `num_screenshots` Parameter

**File: `browser_use/agent/views.py`**
- Added `num_screenshots: int = 2` to `AgentSettings` class
- This parameter controls how many screenshots to include in the input message

**File: `browser_use/agent/service.py`**
- Added `num_screenshots: int = 2` to Agent constructor parameters
- Pass the parameter to AgentSettings during initialization

### 2. Enhanced AgentMessagePrompt

**File: `browser_use/agent/prompts.py`**
- Added `additional_screenshots: list[str] | None = None` parameter to constructor
- Modified `get_user_message()` method to handle multiple screenshots
- Current screenshot is included first, followed by additional screenshots from history
- All screenshots are added as `ContentPartImageParam` objects in the vision message

### 3. Updated MessageManager

**File: `browser_use/agent/message_manager/service.py`**
- Added `num_screenshots: int = 2` parameter to constructor
- Added `additional_screenshots: list[str] | None = None` parameter to `add_state_message()`
- Pass additional screenshots to `AgentMessagePrompt`

### 4. Screenshot History Retrieval

**File: `browser_use/agent/service.py`**
- Added `_get_additional_screenshots()` method to Agent class
- Retrieves the last N-1 screenshots from agent history (current screenshot handled separately)
- Returns screenshots in reverse chronological order (oldest first, newest last)
- Integrated into the `step()` method to gather screenshots before calling message manager

## Usage

### Basic Usage (Default)

```python
from browser_use import Agent
from browser_use.llm import ChatOpenAI

# Agent will use 2 screenshots by default (current + 1 from history)
agent = Agent(
    task="Navigate and interact with websites",
    llm=ChatOpenAI(model="gpt-4o")
)
```

### Custom Screenshot Count

```python
# Use 3 screenshots (current + 2 from history)
agent = Agent(
    task="Navigate and interact with websites", 
    llm=ChatOpenAI(model="gpt-4o"),
    num_screenshots=3
)

# Use only current screenshot (original behavior)
agent = Agent(
    task="Navigate and interact with websites",
    llm=ChatOpenAI(model="gpt-4o"), 
    num_screenshots=1
)
```

## Technical Details

### Screenshot Order
1. **Current screenshot** - Always included first in the vision message
2. **Historical screenshots** - Added in chronological order (oldest to newest)

### Memory Management
- Screenshots are retrieved from the agent's existing history
- No additional storage overhead - uses already captured screenshots
- If history has fewer screenshots than requested, uses what's available

### Backward Compatibility
- Default value of `num_screenshots=2` provides enhanced context while maintaining compatibility
- Existing code will work without changes
- Setting `num_screenshots=1` restores original single-screenshot behavior

### Performance Considerations
- Additional screenshots increase token usage for vision models
- Cost scales roughly linearly with number of screenshots
- Consider model token limits when using many screenshots

## Files Modified

1. `browser_use/agent/views.py` - Added `num_screenshots` to AgentSettings
2. `browser_use/agent/service.py` - Added parameter, method, and integration
3. `browser_use/agent/prompts.py` - Enhanced to handle multiple screenshots
4. `browser_use/agent/message_manager/service.py` - Updated to pass additional screenshots

## Testing

The implementation includes:
- Syntax validation of all modified files
- Proper parameter passing through the call chain
- Graceful handling of cases with insufficient history
- Backward compatibility verification

## Benefits

1. **Better Context** - Agent can see progression of changes across steps
2. **Improved Decision Making** - Multiple visual references help with complex navigation
3. **Enhanced Debugging** - Multiple screenshots provide better insight into agent behavior
4. **Flexible Configuration** - Users can choose optimal screenshot count for their use case