# Parallel Browser Execution Fixes

This document explains the fixes implemented to resolve TargetClosedError when running multiple browser sessions in parallel (up to 20+ browsers).

## Problem

When running evaluation tasks with high parallelism (20+ browsers), the system encountered:
- `TargetClosedError` exceptions
- Browser sessions interfering with each other
- Resource conflicts and port collisions
- Inadequate cleanup causing resource exhaustion

## Root Causes

1. **Global Playwright instance conflicts**: Multiple sessions sharing global objects
2. **Port conflicts**: Browsers trying to use the same debug ports  
3. **Inadequate resource isolation**: Browser processes interfering with each other
4. **Insufficient cleanup**: Browsers not cleaning up properly under load
5. **Temp directory conflicts**: Shared temporary directories causing state pollution

## Fixes Implemented

### 1. Isolated Browser Profiles (`create_isolated_browser_profile`)

**Location**: `eval/service.py`

```python
def create_isolated_browser_profile(task_id: str, headless: bool, highlight_elements: bool = True) -> BrowserProfile:
```

**Key Features**:
- Unique debug ports per browser (9222 + random range)
- Isolated temporary directories with task-specific prefixes  
- Enhanced Chrome CLI arguments for maximum isolation
- Separate environment variables per browser
- Optimized timeouts for parallel execution

### 2. Improved Browser Session Setup (`setup_browser_session`)

**Location**: `eval/service.py`

**Improvements**:
- Uses isolated browser profiles
- Retry logic for browser startup (up to 3 attempts)
- Better error handling with timeouts
- Graceful navigation failure handling

### 3. Robust Cleanup Process (`cleanup_browser_safe`)

**Location**: `eval/service.py`

**Features**:
- Multiple cleanup strategies (graceful → force kill → direct process termination)
- Shorter timeouts optimized for parallel execution (15s)
- Automatic temp directory cleanup
- Comprehensive error handling

### 4. Playwright Instance Isolation

**Location**: `browser_use/browser/session.py`

**Changes**:
- Evaluation tasks get isolated Playwright instances
- Prevents global object conflicts during parallel execution
- Maintains global instances for non-evaluation tasks

## Usage

### Running Evaluations with High Parallelism

```python
# Example: Run 20 tasks in parallel
from eval.service import run_multiple_tasks

results = await run_multiple_tasks(
    tasks=tasks,
    llm=llm,
    run_id=run_id,
    # ... other parameters
    max_parallel_runs=20,  # Now supports up to 20+ browsers
    headless=True,
    highlight_elements=False,  # Disable for performance
)
```

### Testing the Fixes

Run the provided test script to validate parallel browser execution:

```bash
cd /workspace
python eval/test_parallel_browsers.py
```

This script will:
- Test 5, 10, and 20 browsers in parallel
- Validate browser startup, navigation, and cleanup
- Report success rates and performance metrics
- Identify any remaining issues

## Performance Optimizations

### Browser Configuration
- Reduced timeouts for faster execution
- Disabled unnecessary Chrome features
- Enhanced isolation flags
- Optimized wait times

### Resource Management
- Automatic temp directory cleanup
- Aggressive process termination
- Memory-efficient browser arguments
- Process isolation improvements

## Monitoring

The fixes include enhanced logging for:
- Browser startup and cleanup phases
- Resource usage monitoring
- Error detection and recovery
- Performance metrics

Look for these log patterns:
```
Browser setup: Starting browser session for task task_001
✅ Browser started successfully for task task_001
🧹 Cleaning up browser for task task_001
✅ Cleanup completed for task task_001
```

## Troubleshooting

### Still Experiencing Issues?

1. **Reduce parallelism**: Start with `max_parallel_runs=10` and increase gradually
2. **Check system resources**: Monitor CPU, memory, and open file descriptors
3. **Enable debug logging**: Set `logging.level=DEBUG` for detailed output
4. **Run the test script**: Use `eval/test_parallel_browsers.py` to diagnose issues

### Common Issues

- **Resource exhaustion**: Reduce `max_parallel_runs` or increase system limits
- **Port conflicts**: The system automatically handles port allocation, but firewall rules might interfere
- **Temp directory permissions**: Ensure `/tmp` is writable and has sufficient space

## Configuration Recommendations

### For Docker Environments
```python
# Recommended settings for Docker
max_parallel_runs = min(20, cpu_count * 2)
headless = True
highlight_elements = False
```

### For Local Development  
```python
# Recommended settings for local development
max_parallel_runs = min(10, cpu_count)
headless = False  # For debugging
highlight_elements = True
```

## Validation

After implementing these fixes, you should be able to:
- ✅ Run 20+ browsers in parallel without TargetClosedError
- ✅ Achieve 90%+ success rates in parallel execution
- ✅ Proper resource cleanup and isolation
- ✅ Improved performance and stability

Run the test script to validate your setup works correctly.