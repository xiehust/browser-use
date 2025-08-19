# PR Title:
feat: set default reasoning_effort to high for ChatOpenAI

# PR Body:

## Description

This PR changes the default value of the `reasoning_effort` parameter in the `ChatOpenAI` class from `'low'` to `'high'`.

## Why this change?

The `reasoning_effort` parameter controls the depth and complexity of responses from OpenAI's reasoning models (o1, o3, etc.). Setting it to `'high'` by default ensures:

- **Better reasoning quality**: Higher reasoning effort leads to more detailed and thoughtful responses
- **Improved reliability**: For browser automation tasks, we want the most accurate and well-reasoned decisions  
- **Consistency with browser-use goals**: As noted in the codebase, browser-use aims to be "more reliable and deterministic"

## What changed?

- Modified `browser_use/llm/openai/chat.py` line 52
- Changed default from `reasoning_effort: ReasoningEffort = 'low'` to `reasoning_effort: ReasoningEffort = 'high'`

## Impact

- This change only affects reasoning models (o1, o3, o4, gpt-5, etc.) as defined in the `ReasoningModels` list
- Users can still override this default by explicitly setting `reasoning_effort` when instantiating `ChatOpenAI`
- May result in slightly higher token usage for reasoning models, but with better quality outputs

## Testing

- The change maintains backward compatibility
- Users who want lower reasoning effort can still set it explicitly
- Existing tests should continue to pass as this is a default value change

## Code Example

```python
# Before (default was 'low')
chat = ChatOpenAI(model='o1')  # Uses reasoning_effort='low'

# After this PR (default is 'high')
chat = ChatOpenAI(model='o1')  # Uses reasoning_effort='high'

# Users can still override
chat = ChatOpenAI(model='o1', reasoning_effort='low')  # Explicitly set to 'low'
```