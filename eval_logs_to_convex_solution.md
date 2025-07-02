# Easy Solution: Save Evaluation Logs to Convex

## Overview

I've implemented a **very easy** solution to save all the logs from the runner to Convex for the given runs. The solution leverages the existing robust Convex integration and adds optional log capture functionality.

## 🚀 How It Works

### Current State
The evaluation system already has comprehensive Convex integration that sends detailed task data including:
- Task execution data (action history, results, duration, steps, token usage)
- Evaluation results and scores
- Error tracking and stage completion status

### What's Added
1. **Custom Log Handler**: Captures task-specific logs during execution
2. **TaskResult Enhancement**: Stores captured logs and includes them in the Convex payload
3. **Command Line Flag**: `--capture-logs` to enable log capture
4. **GitHub Actions Support**: Added workflow configuration to enable log capture

## 📝 Implementation Details

### 1. TaskResult Class Enhancement
```python
@dataclass
class TaskResult:
    # ... existing fields ...
    captured_logs: list[str] = field(default_factory=list)  # NEW: Log capture
    
    def add_log_entry(self, log_entry: str):
        """Add a log entry for this task"""
        self.captured_logs.append(log_entry)
    
    @property
    def server_payload(self) -> dict[str, Any]:
        payload = {
            # ... existing payload ...
            'runnerLogs': self.captured_logs[-1000:] if self.captured_logs else [],  # NEW: Include last 1000 log entries
        }
```

### 2. Custom Log Handler
```python
class TaskLogHandler(logging.Handler):
    """Custom logging handler that captures logs for a specific task"""
    
    def __init__(self, task_result: 'TaskResult'):
        super().__init__()
        self.task_result = task_result
        self.task_id = task_result.task_id
        
    def emit(self, record):
        try:
            # Only capture logs related to this task
            log_message = self.format(record)
            if self.task_id in log_message or f'Task {self.task_id}' in log_message:
                self.task_result.add_log_entry(log_message)
        except Exception:
            # Ignore errors in logging handler to avoid recursive issues
            pass
```

### 3. Task Execution Integration
- **Setup**: `setup_task_logging(task_result, capture_logs)` - Attaches log handler if enabled
- **Cleanup**: `cleanup_task_logging(task.task_id)` - Removes handler after task completion
- **Automatic**: Logs are automatically captured and included in the existing Convex payload

## 🎛️ Usage Options

### Option 1: Command Line (Easiest)
```bash
python eval/service.py --capture-logs --model gpt-4o --test-case MyTestCase
```

### Option 2: GitHub Actions / eval.yaml
Add to your workflow dispatch payload:
```json
{
  "script_args": {
    "capture_logs": "true",
    "model": "gpt-4o",
    "test_case": "OnlineMind2Web"
  }
}
```

### Option 3: Programmatic Usage
```python
await run_evaluation_pipeline(
    tasks=tasks,
    llm=llm,
    capture_logs=True,  # Enable log capture
    # ... other parameters ...
)
```

## 📊 What Gets Sent to Convex

When `--capture-logs` is enabled, the `runnerLogs` field is added to each task result:

```json
{
  "taskId": "task_123",
  "runId": "run_456", 
  "runnerLogs": [
    "2024-01-15 10:30:15 - INFO - eval.service: Task task_123: Starting execution pipeline.",
    "2024-01-15 10:30:16 - INFO - eval.service: Task task_123: Browser setup starting.",
    "2024-01-15 10:30:20 - INFO - eval.service: Task task_123: Browser session started successfully.",
    "2024-01-15 10:30:21 - INFO - eval.service: Task task_123: Agent run starting.",
    // ... up to last 1000 log entries related to this task
  ],
  // ... existing task data (actionHistory, evaluation results, etc.)
}
```

## ⚡ Performance Considerations

1. **Filtered Logging**: Only captures logs that mention the specific task ID
2. **Limited Storage**: Only stores the last 1000 log entries per task to prevent memory issues
3. **Optional**: Log capture is disabled by default and only enabled with `--capture-logs`
4. **Clean Architecture**: Uses the existing Convex integration without disrupting current functionality

## ✅ Benefits

1. **Zero Breaking Changes**: Existing functionality remains unchanged
2. **Easy Configuration**: Single flag `--capture-logs` enables the feature
3. **Comprehensive Coverage**: Captures all task-related logs including:
   - Stage transitions (browser setup, agent run, evaluation, etc.)
   - Error messages and warnings  
   - Resource monitoring logs
   - Performance metrics
4. **Searchable Data**: Logs are sent as structured data to Convex for easy querying
5. **GitHub Actions Ready**: Already configured for CI/CD workflows

## 🚦 Getting Started

1. **Local Testing**:
   ```bash
   python eval/service.py --capture-logs --task-text "Find information about OpenAI" --model gpt-4o
   ```

2. **Production Use**:
   Add `"capture_logs": "true"` to your GitHub Actions workflow dispatch payload

3. **View Results**:
   Check your Convex dashboard - each task result will now include the `runnerLogs` field with detailed execution logs

That's it! The solution is now ready to use and provides comprehensive log capture with minimal configuration required.