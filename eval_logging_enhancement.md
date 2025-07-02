# Enhanced Logging System for Browser-Use Evaluations

## Overview

The enhanced logging system provides comprehensive log collection during evaluation runs, capturing all console output, system logs, and runtime information for both local storage and Convex upload.

## Features

### 1. Complete Log Collection
- **Console Output**: Captures all stdout and stderr during task execution
- **System Logs**: Records all logging messages from all loggers (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Metadata**: Includes timestamps, elapsed time, and log statistics
- **Non-intrusive**: Uses "tee" approach - logs are captured but still display normally

### 2. Local Storage
- Saves complete logs to `saved_trajectories/{task_id}/complete_logs.json`
- Includes structured data with:
  - Individual log entries with timestamps
  - Console output streams
  - Error output streams
  - Log statistics and summary

### 3. Convex Integration
- Automatically uploads complete logs to Convex when enabled
- Includes log summary with key metrics:
  - Total log entries
  - Duration
  - Error/warning counts
  - Statistics breakdown by log level

## Usage

### Command Line

Enable complete log collection with the `--collect-complete-logs` flag:

```bash
python eval/service.py --collect-complete-logs --parallel-runs 2 --max-steps 25
```

### GitHub Actions Workflow

Add the parameter to your workflow dispatch:

```yaml
# In eval.yaml workflow
script_args:
  collect_complete_logs: true
```

Or via API call:
```json
{
  "event_type": "run-eval", 
  "client_payload": {
    "script_args": {
      "collect_complete_logs": true,
      "model": "gpt-4o",
      "max_steps": 25
    }
  }
}
```

## Implementation Details

### LogCollector Class

```python
class LogCollector:
    """Collects all logs and output during task execution"""
    
    def __init__(self, task_id: str)
    def start_capture()     # Begin capturing logs
    def stop_capture()      # Stop capturing and process logs
    def get_all_logs()      # Return structured log data
    def save_logs_to_file() # Save to local JSON file
```

### Data Structure

The complete logs are stored with the following structure:

```json
{
  "task_id": "task_123",
  "start_time": 1735000000.123,
  "end_time": 1735000060.456,
  "duration": 60.333,
  "total_log_entries": 542,
  "log_entries": [
    {
      "timestamp": 1735000001.234,
      "level": "INFO",
      "logger": "browser_use.agent",
      "message": "Agent starting task...",
      "elapsed_time": 1.111
    }
  ],
  "console_output": [
    {
      "type": "stdout",
      "content": "Task execution output...",
      "timestamp": 1735000002.345,
      "size_bytes": 1024
    }
  ],
  "error_output": [
    {
      "type": "stderr",
      "content": "Error message...",
      "timestamp": 1735000003.456,
      "size_bytes": 256
    }
  ],
  "log_stats": {
    "debug_logs": 123,
    "info_logs": 234,
    "warning_logs": 12,
    "error_logs": 3,
    "critical_logs": 0
  }
}
```

### Convex Payload Enhancement

When logs are collected, the Convex payload includes:

```json
{
  "taskId": "task_123",
  "completeLogs": { /* full log structure above */ },
  "logSummary": {
    "total_log_entries": 542,
    "duration": 60.333,
    "log_stats": { /* stats breakdown */ },
    "has_errors": true,
    "has_warnings": true
  }
}
```

## Performance Considerations

### Resource Usage
- **Memory**: Log collection uses in-memory buffers - monitor for long-running tasks
- **Storage**: Complete logs can be large (1-10MB per task depending on verbosity)
- **CPU**: Minimal overhead due to efficient tee-style capture

### When to Enable
- **Development**: Always recommended for debugging
- **CI/CD**: Enable for failing tests or performance analysis
- **Production**: Use selectively due to storage/bandwidth costs

## Configuration Options

### Environment Variables
- `EVALUATION_TOOL_URL`: Convex endpoint URL
- `EVALUATION_TOOL_SECRET_KEY`: Authentication key

### Command Line Arguments
- `--collect-complete-logs`: Enable complete log collection
- `--parallel-runs N`: Number of parallel tasks (affects log volume)
- `--max-steps N`: Maximum steps per task (affects log volume)

## Troubleshooting

### Common Issues

1. **High Memory Usage**
   - Solution: Reduce parallel runs or use for shorter evaluations
   - Monitor: Check system resources during execution

2. **Large Log Files**
   - Solution: Filter log levels or reduce verbosity in dependencies
   - Optimization: Consider log compression for storage

3. **Upload Failures**
   - Check Convex credentials and network connectivity
   - Logs are still saved locally even if upload fails

### Log Location
- Local files: `saved_trajectories/{task_id}/complete_logs.json`
- Convex: Available in task result payload under `completeLogs`

## Benefits

1. **Complete Debugging Information**: No more missing context when issues occur
2. **Performance Analysis**: Detailed timing and resource usage data
3. **Error Tracking**: Comprehensive error logs with full context
4. **Compliance**: Complete audit trail for evaluation runs
5. **Remote Analysis**: Logs available in Convex for team collaboration

## Example Usage Scenarios

### Debugging Failed Tasks
```bash
# Run with complete logging for failed task investigation
python eval/service.py --task-text "Navigate to example.com" --collect-complete-logs
```

### Performance Benchmarking
```bash
# Collect detailed performance data
python eval/service.py --parallel-runs 5 --max-steps 50 --collect-complete-logs
```

### CI/CD Integration
```yaml
# GitHub Actions workflow with logging
- name: Run Evaluation
  run: |
    python eval/service.py \
      --test-case "OnlineMind2Web" \
      --parallel-runs 3 \
      --collect-complete-logs \
      --developer-id "${{ github.actor }}"
```

This enhanced logging system provides comprehensive observability for browser-use evaluations while maintaining backward compatibility with existing workflows.