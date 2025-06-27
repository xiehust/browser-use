# Planner Support Removal - Summary

## Overview
This document summarizes the changes made to remove planner support from browser-use as of version 0.3.2. The agent's planning capabilities have been significantly improved and no longer require the separate planner system.

## Rationale
- **Simplified Configuration**: Removes complexity from agent setup
- **Improved Performance**: Eliminates overhead of separate planning calls
- **Enhanced Agent**: The main agent now handles planning more effectively
- **Reduced Maintenance**: Fewer components to maintain and debug

## Changes Made

### 1. Core Agent Components

#### `browser_use/agent/views.py`
- **AgentSettings class**: Added deprecation warnings for planner parameters
- **Deprecated parameters**: `planner_llm`, `planner_interval`, `use_vision_for_planner`, `is_planner_reasoning`, `extend_planner_system_message`
- **Behavior**: When users provide planner parameters, warnings are logged and parameters are reset to defaults

#### `browser_use/agent/service.py`
- **Agent constructor**: Moved planner parameters to deprecated section with warnings
- **Removed functionality**:
  - Planner LLM registration with token cost service
  - Planner-specific model warnings for DeepSeek/Grok
  - Planner execution in `step()` method
  - `_run_planner()` method completely removed
- **Updated logging**: Removed planner references from startup messages
- **Telemetry**: Set planner_llm to None in telemetry events

#### `browser_use/agent/prompts.py`
- **PlannerPrompt class**: Completely removed
- **Import cleanup**: Removed PlannerPrompt from service.py imports

### 2. User Interface Components

#### `browser_use/cli.py`
- **Model info display**: Removed "+ planner" indicator from TUI
- **Panel updates**: Cleaned up planner references

### 3. Documentation

#### `docs/customize/agent-settings.mdx`
- **Section replacement**: Replaced "Run with planner model" with "Planner Support Discontinued"
- **Migration guidance**: Added clear deprecation notice and benefits explanation
- **Parameter cleanup**: Removed all planner parameter documentation

#### `docs/customize/system-prompt.mdx`
- **Section replacement**: Replaced "Extend Planner System Prompt" with deprecation notice
- **Guidance**: Explained that built-in planning capabilities handle task decomposition

### 4. Examples

#### `examples/features/planner.py`
- **File removal**: Completely deleted the planner example
- **Reasoning**: No longer relevant since planner support is discontinued

### 5. Evaluation System

#### `eval/service.py`
- **Function signatures**: Removed planner parameters from all evaluation functions:
  - `run_agent_with_browser()`
  - `run_task_with_semaphore()`
  - `run_multiple_tasks()`
  - `run_evaluation_pipeline()`
- **Agent creation**: Removed planner parameters from Agent constructor calls
- **Metadata**: Removed planner tracking from Laminar metadata
- **CLI arguments**: Removed `--planner-model` and `--planner-interval` arguments
- **LLM initialization**: Removed planner LLM setup code
- **Logging**: Removed planner status logging

### 6. Telemetry

#### `browser_use/telemetry/views.py`
- **Data structure**: Kept `planner_llm` field for backward compatibility but always set to None
- **Migration**: Existing telemetry consumers won't break but will see None values

## Backward Compatibility

### What's Preserved
- **Parameter acceptance**: All planner parameters are still accepted to avoid breaking existing code
- **Graceful degradation**: Warning messages inform users about deprecation
- **Telemetry structure**: Field names remain the same (set to None/default values)

### What Users Need to Do
1. **Remove planner parameters** from Agent constructor calls:
   ```python
   # Before (deprecated)
   agent = Agent(
       task="task",
       llm=llm,
       planner_llm=planner_llm,           # Remove this
       planner_interval=4,                # Remove this
       use_vision_for_planner=False       # Remove this
   )
   
   # After (recommended)
   agent = Agent(
       task="task",
       llm=llm
   )
   ```

2. **Update documentation/examples** that reference planner functionality
3. **Remove planner-related configuration** from evaluation scripts

## Migration Guide

### For Basic Users
- Simply remove planner-related parameters from your Agent initialization
- The agent will automatically use its improved built-in planning capabilities

### For Advanced Users
- If you were using planner for cost optimization (smaller model for planning), consider:
  - Using the main LLM more efficiently
  - Implementing custom planning logic if needed
  - The improved agent planning often provides better results than separate planning

### For Evaluation/Testing
- Remove planner parameters from evaluation scripts
- Update any automated testing that relied on planner functionality
- Benchmarks may improve due to more integrated planning approach

## Benefits of Removal

1. **Simplified Setup**: Fewer parameters to configure
2. **Better Performance**: No separate LLM calls for planning
3. **Improved Quality**: Integrated planning with full context
4. **Reduced Costs**: No duplicate LLM invocations for planning
5. **Easier Debugging**: Fewer components to troubleshoot
6. **Better Context**: Planning happens with full browser state awareness

## Technical Implementation Notes

- **Deprecation Pattern**: Used logging warnings rather than raising exceptions
- **Parameter Reset**: Planner parameters are reset to safe defaults
- **Import Safety**: All imports remain functional to avoid import errors
- **Test Compatibility**: Core functionality compiles and runs without issues

## Files Modified

### Core Browser-Use Files
- `browser_use/agent/views.py`
- `browser_use/agent/service.py`
- `browser_use/agent/prompts.py`
- `browser_use/cli.py`
- `browser_use/telemetry/views.py`

### Documentation Files
- `docs/customize/agent-settings.mdx`
- `docs/customize/system-prompt.mdx`

### Example Files
- `examples/features/planner.py` (deleted)

### Evaluation Files
- `eval/service.py`

## Version Information
- **Removal Version**: 0.3.2
- **Deprecation Notice**: "Planner support has been removed as of version 0.3.2. The agent capability for planning is significantly improved and no longer requires the planner system."