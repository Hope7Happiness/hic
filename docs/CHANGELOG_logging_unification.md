# Changelog: Logging System Unification

**Date:** January 25, 2026  
**Purpose:** Simplify the logging system by making AsyncLogger the default and deprecating the verbose parameter.

## Summary

Unified the logging system to use AsyncLogger exclusively, removing confusion about when and how terminal output appears.

## Changes Made

### 1. Agent Core (`agent/agent.py`)

**Removed:**
- `verbose` parameter from `Agent.run()` and `Agent._run_async()`
- Automatic ColorfulConsoleCallback addition based on verbose flag
- Callback restoration logic in `_run_async()`

**Added:**
- Auto-initialization of AsyncLogger if not already initialized
- Default console output enabled (`console_output=True`)

**Before:**
```python
def run(self, task: str, verbose: bool = False) -> AgentResponse:
    return asyncio.run(self._run_async(task, verbose))

async def _run_async(self, task: str, verbose: bool = False) -> AgentResponse:
    # Add verbose callback if requested
    if verbose:
        self.callbacks = self.callbacks + [ColorfulConsoleCallback(verbose=True)]
    # ... execution code
```

**After:**
```python
def run(self, task: str) -> AgentResponse:
    return asyncio.run(self._run_async(task))

async def _run_async(self, task: str) -> AgentResponse:
    # Auto-initialize AsyncLogger if not already initialized
    try:
        from agent.async_logger import get_logger, init_logger
        try:
            get_logger()
        except RuntimeError:
            await init_logger(console_output=True)
    except Exception:
        pass
    # ... execution code
```

### 2. README Updates (`README_human.md`)

**Line 19-24:** Removed verbose parameter from quick start example

**Before:**
```python
# Create agent with verbose mode for detailed color-coded logging
agent = Agent(llm=llm, tools=[Tool(calculator)])
# Run with verbose=True to see detailed execution steps with colors
response = agent.run("What is 25 * 4?", verbose=True)
```

**After:**
```python
# Create agent with tools
agent = Agent(llm=llm, tools=[Tool(calculator)])
# Run - logs automatically appear in console and files
response = agent.run("What is 25 * 4?")
```

**Line 164-179:** Added section explaining logging behavior

**Added:**
```markdown
### 2. Comprehensive Logging

**By default, logs automatically appear in console and files.** The AsyncLogger is automatically initialized when you run an agent.

**Disable Console Logging** (keep file logs only):
```python
from agent.async_logger import init_logger

# Initialize logger with console output disabled
await init_logger(console_output=False)
```

### 3. Deprecation Warnings (`agent/callbacks.py`)

**ColorfulConsoleCallback:**
- Added deprecation warning in docstring
- Added runtime DeprecationWarning when initialized
- Recommended AsyncLogger as replacement

**Changes:**
```python
class ColorfulConsoleCallback(AgentCallback):
    """
    [DEPRECATED] Enhanced console callback with color support for hierarchical agents.
    
    ⚠️ WARNING: This callback is deprecated. Use AsyncLogger instead.
    ...
    """
    
    def __init__(self, verbose: bool = True, color_map: Optional[Dict[str, str]] = None):
        import warnings
        warnings.warn(
            "ColorfulConsoleCallback is deprecated. Use AsyncLogger instead...",
            DeprecationWarning,
            stacklevel=2
        )
        # ... rest of initialization
```

## Behavior Changes

### Before This Change

**Two separate logging systems existed:**

1. **ColorfulConsoleCallback** (via `verbose=True`)
   - Added automatically when `agent.run(task, verbose=True)`
   - Detailed iteration-by-iteration debug info
   - User confusion: "When does output appear?"

2. **AsyncLogger** (manual initialization)
   - Required explicit `await init_logger()`
   - Only used in async examples
   - Color-coded, structured output

**User Experience Issues:**
- Unclear when terminal output would appear
- Two different styles of output
- Needed to know which system to use when

### After This Change

**Single unified logging system:**

1. **AsyncLogger (Default)**
   - Automatically initialized by `agent.run()`
   - Console output enabled by default
   - Consistent color-coded output
   - Per-agent log files

**User Experience:**
- Clear: Logs always appear unless disabled
- Consistent output style
- Simple mental model

### Migration Guide

**Old Code:**
```python
# With verbose output
agent = Agent(llm=llm, tools=[tools])
result = agent.run(task="...", verbose=True)

# Without output (but this was confusing)
result = agent.run(task="...")
```

**New Code:**
```python
# Default: logs appear in console + files
agent = Agent(llm=llm, tools=[tools])
result = agent.run(task="...")

# Disable console output (file-only logging)
from agent.async_logger import init_logger
await init_logger(console_output=False)
result = await agent._run_async(task="...")
```

## Testing

**Test Results:**
```bash
$ python tests/test_async_basic.py
  0.000s [INFO] [parent] [AGENT] 🚀 Started with task: Launch both agents and wait for them
  0.002s [INFO] [fast] [AGENT] 🚀 Started with task: Sleep for 1 second
  0.002s [INFO] [slow] [AGENT] 🚀 Started with task: Sleep for 10 seconds
  1.004s [INFO] [fast] [AGENT] ✅ Finished: Slept for 1 seconds successfully
 10.005s [INFO] [slow] [AGENT] ✅ Finished: Slept for 10 seconds successfully
 10.006s [INFO] [parent] [AGENT] ✅ Finished: Both agents completed successfully
✅ Test passed! Total time: 10.01s (expected ~10s for parallel execution)
```

All tests pass with automatic AsyncLogger initialization.

## Benefits

1. **Simplified API:** No more `verbose` parameter
2. **Clear behavior:** Logs always appear by default
3. **Better async support:** AsyncLogger is async-native
4. **Consistent output:** Single logging style throughout
5. **Better UX:** Users don't need to guess when output appears

## Backward Compatibility

- **Breaking Change:** `verbose` parameter removed from `agent.run()`
- **Deprecated:** ColorfulConsoleCallback (still works but warns)
- **Migration:** Remove `verbose=True` calls - logging now automatic

## Files Modified

1. `agent/agent.py` - Removed verbose, added auto-init
2. `README_human.md` - Updated examples and documentation
3. `agent/callbacks.py` - Added deprecation warnings
4. `CHANGELOG_logging_unification.md` - This file

## Next Steps

Users should:
1. Remove `verbose=True` from all `agent.run()` calls
2. Use `init_logger(console_output=False)` if they want file-only logging
3. Stop using ColorfulConsoleCallback (if any custom code uses it)

## Questions & Answers

**Q: How do I disable all logging?**  
A: Initialize logger with `await init_logger(console_output=False)` and ignore log files

**Q: Can I use custom callbacks?**  
A: Yes! The callbacks system still works - just add to `Agent(..., callbacks=[...])`

**Q: What if I don't want AsyncLogger at all?**  
A: The framework handles it gracefully if logger init fails - no errors

**Q: Will this work with sync `agent.run()`?**  
A: Yes! `agent.run()` internally calls `_run_async()` which auto-initializes the logger
