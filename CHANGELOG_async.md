# Changelog - Async Parallel Execution Update

## 2026-01-25: Major Feature Release - Async Parallel Agents

### 🎉 New Features

#### 1. **Async Parallel Execution**
- Multiple sub-agents can now run in parallel instead of sequentially
- Achieved through async/await architecture with `asyncio`
- Parent agents can launch multiple sub-agents and wait for completion
- Significant performance improvement for independent tasks

**New Action Types:**
- `launch_subagents` - Launch multiple agents at once (non-blocking)
- `wait_for_subagents` - Suspend parent and wait for sub-agents
- `finish` - Complete execution with result

#### 2. **Comprehensive Async Logging** (`agent/async_logger.py`)
- Color-coded console output with emojis (🚀, ✅, 🔧)
- Per-agent log files with millisecond timestamps
- Hierarchical indentation for sub-agents
- Async-safe file writing (non-blocking)
- Categories: AGENT, TOOL, LLM with different colors

**Features:**
- Real-time progress tracking
- Elapsed time from start
- Event tracking: start, finish, suspend, resume, tool calls
- Automatic agent hierarchy visualization

#### 3. **Production-Ready Example** (`examples/async_parallel_agents.py`)
- Real LLM integration (DeepSeek)
- Two sub-agents with sleep tools (3s and 8s)
- Demonstrates true parallel execution
- Includes timing verification
- Complete with detailed README

### 📊 Performance Improvement

**Before (Sequential):**
```
Agent1: 10 seconds
Agent2: 15 seconds
Total: 25 seconds
```

**After (Parallel):**
```
Agent1: 10 seconds ─┐
Agent2: 15 seconds ─┤ Running simultaneously
Total: 15 seconds   ─┘
```

### 🏗️ Architecture Changes

#### Core Components Added:
- **`AgentOrchestrator`** (`agent/orchestrator.py`)
  - Singleton coordinator for all agents
  - Manages async task creation and lifecycle
  - Message queue for inter-agent communication
  - State persistence and restoration

- **`AsyncLogger`** (`agent/async_logger.py`)
  - Non-blocking logging system
  - Console + file output
  - Hierarchical visualization

#### Modified Components:
- **`Agent`** (`agent/agent.py`)
  - Added `async def _internal_run()` for main loop
  - Added `async def _internal_resume()` for resumption
  - Tool execution wrapped in `run_in_executor()`
  - LLM calls wrapped in `run_in_executor()`
  - Integration with orchestrator and logger

- **`OutputParser`** (`agent/parser.py`)
  - Updated format instructions for new actions
  - Parsers for `launch_subagents` and `wait_for_subagents`

- **`Schemas`** (`agent/schemas.py`)
  - `AgentStatus` enum (IDLE, RUNNING, SUSPENDED, COMPLETED, FAILED)
  - `LaunchedSubagent` dataclass
  - `AgentState` dataclass (for serialization)
  - `AgentMessage` dataclass (inter-agent messages)
  - Updated `Action` class with new action types

### 🧪 Testing

- **`tests/test_async_basic.py`**
  - Tests parallel execution with mock LLMs
  - Verifies timing (10s parallel vs 11s sequential)
  - Validates agent suspension and resumption

### 📚 Documentation

- **`README_human.md`** - Updated with async features and example
- **`examples/README_async.md`** - Detailed async usage guide

### 🔧 API Changes

#### Backward Compatibility:
- ✅ Old `agent.run()` API still works (internally uses async)
- ✅ Existing tools and callbacks continue to work
- ✅ Sequential agent execution still supported

#### New APIs:
```python
# Async execution (for use in async context)
await agent._run_async(task="...")

# Logging
from agent import init_logger, close_logger
logger = await init_logger(log_dir="logs")
await close_logger()
```

### 📝 Migration Guide

**Old Code (still works):**
```python
agent = Agent(llm=llm, subagents={"helper": helper_agent})
result = agent.run("task")
```

**New Code (with async logging):**
```python
import asyncio

async def main():
    await init_logger()
    agent = Agent(llm=llm, subagents={"helper": helper_agent})
    result = await agent._run_async("task")
    await close_logger()

asyncio.run(main())
```

### 🚀 Future Enhancements

Potential areas for future work:
- [ ] Priority-based task scheduling
- [ ] Resource limits (max concurrent agents)
- [ ] Agent pooling and reuse
- [ ] Distributed execution across machines
- [ ] WebSocket streaming for real-time updates
- [ ] Graph visualization of agent execution

### 🙏 Credits

Built on top of the existing LLM agent framework with contributions to:
- Async architecture design
- Logging system implementation
- Test coverage for async features
- Documentation and examples
