# Optional Thinking Field Deactivation Feature

## Summary
This PR implements an optional `disable_thinking` parameter for the browser-use Agent that allows users to deactivate the thinking field in agent responses. This can be useful for faster responses, reduced token usage, or when using models that work better without explicit reasoning steps.

## Changes Made

### 1. Agent Class (`browser_use/agent/service.py`)
- Added `disable_thinking: bool = False` parameter to Agent constructor
- Parameter is passed through to AgentSettings and SystemPrompt initialization
- Maintains backward compatibility by defaulting to `False` (thinking enabled)

### 2. System Prompt Generation (`browser_use/agent/prompts.py`)
- Added `disable_thinking` parameter to `SystemPrompt` class
- Implemented `_remove_thinking_requirements()` method that:
  - Removes the entire `<reasoning_rules>` section from system prompt
  - Removes thinking field from JSON output format specification
  - Updates reasoning instructions to be action-focused instead of thinking-focused

### 3. Agent Output Models (`browser_use/agent/views.py`)
- Made `thinking` field optional (`str | None = None`) in both:
  - `AgentBrain` model
  - `AgentOutput` model
- Updated serialization to conditionally include thinking field only when present
- Maintains backward compatibility for existing code

### 4. Agent Settings (`browser_use/agent/views.py`)
- Added `disable_thinking: bool = False` to `AgentSettings` model

### 5. Message Manager (`browser_use/agent/message_manager/service.py`)
- Added `disable_thinking` parameter to `MessageManagerSettings`
- Updated example initialization to conditionally include thinking in examples:
  - Changes example description from "thinking and tool call" to "tool call" when thinking disabled
  - Conditionally adds thinking field to example tool calls

### 6. Logging Updates (`browser_use/agent/service.py`)
- Updated logging to handle optional thinking field gracefully
- Only logs thinking content when it's present and not None

## Usage Example

```python
from browser_use import Agent
from langchain.chat_models import ChatOpenAI

# Agent with thinking enabled (default behavior)
agent_with_thinking = Agent(
    task="Navigate to example.com",
    llm=ChatOpenAI(model="gpt-4o"),
    disable_thinking=False  # or omit this parameter
)

# Agent with thinking disabled
agent_without_thinking = Agent(
    task="Navigate to example.com", 
    llm=ChatOpenAI(model="gpt-4o"),
    disable_thinking=True
)
```

## System Prompt Changes

### With Thinking Enabled (Default)
- Includes `<reasoning_rules>` section requiring explicit reasoning
- JSON output format includes `"thinking"` field
- Examples demonstrate thinking process

### With Thinking Disabled
- Removes `<reasoning_rules>` section completely
- JSON output format excludes `"thinking"` field
- Examples focus on direct action execution
- Instructions emphasize situation analysis rather than step-by-step reasoning

## Benefits

1. **Performance**: Reduced token usage and faster response times
2. **Flexibility**: Works better with some models that prefer direct action without explicit reasoning
3. **Compatibility**: Maintains full backward compatibility
4. **Customization**: Allows users to choose the reasoning approach that works best for their use case

## Testing

The implementation has been tested with:
- System prompt generation with and without thinking
- Agent output model creation and serialization
- Conditional field inclusion logic
- Message manager example generation

All tests pass and the feature works as expected while maintaining backward compatibility.

## Migration Notes

This is a non-breaking change:
- Existing code continues to work without modification
- Default behavior remains unchanged (thinking enabled)
- Only affects behavior when explicitly setting `disable_thinking=True`