# LLM Agent Framework

> A type-safe, hierarchical LLM agent framework with **async parallel execution**, tool calling, and comprehensive logging.

## TL;DR

Build AI agents that can use tools, delegate to sub-agents, and **run sub-agents in parallel** for maximum efficiency.

```python
from agent import DeepSeekLLM, Tool, Agent, get_deepseek_api_key

def calculator(expr: str) -> float:
    """Calculate a math expression."""
    return eval(expr)

# Get API key from .env file
api_key = get_deepseek_api_key()

# Create agent with tools
llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")
agent = Agent(llm=llm, tools=[Tool(calculator)])

# Run - logs automatically appear in console and files
response = agent.run("What is 25 * 4?")
```

**Key Features:**
- ⚡ **Async Parallel Execution** - Sub-agents run concurrently, not sequentially
- 🎨 **Color-Coded Logging** - Hierarchical, indented output with timestamps
- 🔧 **Type-Safe Tools** - Python functions with type hints become tools
- 🤖 **Multi-LLM Support** - DeepSeek, OpenAI, or custom implementations
- 📊 **Comprehensive Logging** - Console + per-agent log files

## Setup

```bash
# Install uv if you haven't
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install openai pydantic pyyaml python-dotenv pytest

# Configure API keys using .env (recommended)
cp .env.example .env
# Edit .env and add your API keys
```

### API Key Configuration

**Recommended: Use .env file**

```bash
# Create .env file from template
cp .env.example .env

# Edit .env and add your keys
nano .env  # or use any text editor
```

Your `.env` file should look like:
```bash
# DeepSeek API Key (recommended - cheaper and faster)
DEEPSEEK_API_KEY=sk-your_deepseek_key_here

# OpenAI API Key (optional)
OPENAI_API_KEY=sk-your_openai_key_here
```

**In Your Code:**

```python
from agent import get_deepseek_api_key, get_openai_api_key

# Automatically loads from .env or environment variables
deepseek_key = get_deepseek_api_key()
openai_key = get_openai_api_key()

if not deepseek_key:
    print("❌ Please set DEEPSEEK_API_KEY in .env file")
```

## Run Examples

### 🌟 Async Parallel Agents (NEW!)

**The killer feature**: Multiple sub-agents running in parallel with real-time logging.

```bash
python examples/async_parallel_agents.py

# or: for a more realistic example, run 
# python examples/async_parallel_agents_real.py
```

**What it demonstrates:**
- ⚡ **Parallel Execution**: FastAgent (3s) and SlowAgent (8s) run simultaneously
- 📊 **Real-time Logging**: See agents start, execute, and complete with timestamps
- 🎯 **Efficiency**: Total time ~15s (parallel) instead of ~25s (sequential)
- 🔄 **State Management**: Parent agent suspends, waits, and resumes correctly

**Example Output:**
```
  0.052s [INFO] [ParentAgent] [AGENT] 🚀 Started with task: ...
  2.407s [INFO] [FastAgent] [AGENT] 🚀 Started with task: 睡眠3秒
  2.410s [INFO] [SlowAgent] [AGENT] 🚀 Started with task: 睡眠8秒
 11.618s [INFO] [FastAgent] [AGENT] ✅ Finished: 已完成3秒睡眠任务
 18.357s [INFO] [SlowAgent] [AGENT] ✅ Finished: 已完成8秒睡眠任务
 28.412s [INFO] [ParentAgent] [AGENT] ✅ Finished: 所有子Agent任务执行完毕

✅ Both agents started at nearly the same time - parallel execution confirmed!
   FastAgent: 3s sleep + ~7s LLM calls = ~10s total
   SlowAgent: 8s sleep + ~7s LLM calls = ~15s total
   Parallel execution means total = max(10s, 15s) = ~15s
   If sequential: 10s + 15s = 25s
```

**How it works:**
1. Parent agent uses `launch_subagents` to start multiple agents at once
2. Sub-agents execute in parallel (asyncio tasks)
3. Parent uses `wait_for_subagents` to suspend and wait
4. When a sub-agent completes, parent is notified and resumes
5. Parent checks remaining agents and continues or finishes

See detailed documentation: [`examples/README_async.md`](examples/README_async.md)

## Run Tests

```bash
# Run all tests (including async tests)
pytest tests/ -v

# Run async-specific tests
pytest tests/test_async_basic.py -v

# Run fast tests only (skip LLM API calls)
pytest tests/ -v -m "not integration"
```

## Key Features Explained

### 1. Async Parallel Execution

**Problem:** Traditional agent frameworks run sub-agents sequentially, wasting time when tasks are independent.

**Solution:** Our async framework allows sub-agents to run in parallel:

```python
# Parent agent can launch multiple sub-agents at once
Action: launch_subagents
Agents: ["DataFetcher", "CacheChecker", "Validator"]
Tasks: ["Fetch from API", "Check cache", "Validate input"]

# All three run in parallel!
# Total time = max(task1, task2, task3), not sum(task1, task2, task3)
```

### 2. Comprehensive Logging

**By default, logs automatically appear in console and files.** The AsyncLogger is automatically initialized when you run an agent.

**Console Output** (color-coded, hierarchical):
```
  0.052s [INFO] [ParentAgent] [AGENT] 🚀 Started
  2.407s [INFO]   [FastAgent] [AGENT] 🚀 Started  ← Indented for hierarchy
  2.410s [INFO]   [SlowAgent] [AGENT] 🚀 Started
```

**Log Files** (per-agent, timestamped):
```
logs/
├── ParentAgent_20260125_224241_*.log
├── FastAgent_20260125_224243_*.log
└── SlowAgent_20260125_224243_*.log
```

**Disable Console Logging** (keep file logs only):
```python
from agent.async_logger import init_logger

# Initialize logger with console output disabled
await init_logger(console_output=False)

# Now run your agent - logs go to files only
agent = Agent(llm=llm, tools=[tools])
result = await agent._run_async("Your task")
```

### 3. Type-Safe Tools

Tools are just Python functions with type hints:

```python
def search_database(query: str, limit: int = 10) -> list[dict]:
    """Search the database with a query string."""
    # Implementation here
    return results

# Automatically becomes a tool
tool = Tool(search_database)

# Agent can call it with validated arguments
agent = Agent(llm=llm, tools=[tool])
```

### 4. Hierarchical Agents

Agents can delegate to specialized sub-agents:

```python
# Parent coordinates, sub-agents specialize
parent = Agent(
    llm=llm,
    subagents={
        "researcher": research_agent,
        "writer": writing_agent,
        "reviewer": review_agent,
    }
)
```

## Architecture

### Core Components

1. **Agent** (`agent/agent.py`)
   - Main execution loop with async support
   - Parses LLM output into actions
   - Executes tools and manages sub-agents
   - Handles suspension and resumption

2. **AgentOrchestrator** (`agent/orchestrator.py`)
   - Singleton coordinator for all agents
   - Manages async tasks and message queue
   - Handles agent registration and lifecycle
   - Tracks parent-child relationships

3. **AsyncLogger** (`agent/async_logger.py`)
   - Non-blocking file I/O
   - Color-coded console output
   - Per-agent log files
   - Hierarchical indentation

4. **Tools** (`agent/tool.py`)
   - Wraps Python functions
   - Validates arguments with Pydantic
   - Generates tool descriptions for LLM

5. **Schemas** (`agent/schemas.py`)
   - `Action`: Parsed LLM output (tool, launch_subagents, wait_for_subagents, finish)
   - `AgentState`: Serializable state for suspension/resumption
   - `AgentMessage`: Inter-agent communication
   - `LaunchedSubagent`: Tracks sub-agent execution

### Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│                        Parent Agent                          │
│  1. LLM returns: launch_subagents ["AgentA", "AgentB"]      │
│  2. Launch both agents (non-blocking)                        │
│  3. LLM returns: wait_for_subagents                          │
│  4. Save state and SUSPEND                                   │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        ▼                                       ▼
┌──────────────────┐                   ┌──────────────────┐
│    Agent A       │                   │    Agent B       │
│  (running...)    │                   │  (running...)    │
│                  │                   │                  │
│  ✅ Completes    │                   │  (still running) │
└──────────────────┘                   └──────────────────┘
        │                                       │
        │ Send "completed" message              │
        ▼                                       │
┌─────────────────────────────────────────────────────────────┐
│                    Parent Agent (RESUMED)                    │
│  Receives: AgentA completed                                  │
│  Status: AgentA ✅, AgentB 🔄                               │
│  Decision: Continue waiting                                  │
│  LLM returns: wait_for_subagents                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Wait for AgentB...
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Parent Agent (RESUMED AGAIN)              │
│  Receives: AgentB completed                                  │
│  Status: AgentA ✅, AgentB ✅                               │
│  Decision: All done!                                         │
│  LLM returns: finish                                         │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
hic/
├── agent/                      # Core framework
│   ├── llm.py                 # LLM abstract class + OpenAI implementation
│   ├── deepseek_llm.py        # DeepSeek LLM implementation
│   ├── tool.py                # Tool system (Python functions → tools)
│   ├── agent.py               # Agent execution logic (async support)
│   ├── orchestrator.py        # Async coordinator singleton
│   ├── async_logger.py        # Async-safe logging system
│   ├── parser.py              # LLM output parser (supports new actions)
│   ├── schemas.py             # Pydantic data models
│   ├── callbacks.py           # Callback system for observability
│   ├── config.py              # API key configuration with .env support
│   └── __init__.py
│
├── tests/                      # Test suite
│   ├── test_async_basic.py    # Async parallel execution tests
│   ├── test_tool.py           # Tool creation & validation
│   ├── test_agent.py          # Agent execution tests
│   └── ...
│
├── examples/                   # Usage examples
│   ├── async_parallel_agents.py    # 🌟 Async parallel execution demo
│   ├── README_async.md             # Detailed async documentation
│   ├── simple_agent.py             # Basic agent (best for beginners)
│   ├── zoo_director.py             # Hierarchical agents
│   ├── deepseek_agent.py           # Agent with DeepSeek LLM
│   └── custom_llm.py               # Custom LLM implementation
│
├── logs/                       # Generated log files (per-agent)
├── .env.example               # API key configuration template
└── pyproject.toml             # Project config
```

## Advanced Usage

### Custom Tools

```python
from agent import Tool

def fetch_data(url: str, timeout: int = 30) -> dict:
    """Fetch data from a URL with optional timeout."""
    import requests
    response = requests.get(url, timeout=timeout)
    return response.json()

tool = Tool(fetch_data)
agent = Agent(llm=llm, tools=[tool])
```

### Custom LLM

```python
from agent import LLM

class MyCustomLLM(LLM):
    def chat(self, prompt: str, system_prompt: str | None = None) -> str:
        # Your implementation
        return response
    
    def reset_history(self):
        self.history = []
    
    def get_history(self):
        return self.history
    
    def set_history(self, history):
        self.history = history

llm = MyCustomLLM()
agent = Agent(llm=llm)
```

### Async API

```python
import asyncio
from agent import Agent, init_logger, close_logger

async def main():
    # Initialize logger
    logger = await init_logger(log_dir="logs")
    
    # Create agent
    agent = Agent(llm=llm, tools=[tool1, tool2])
    
    # Run async (use this inside async context)
    result = await agent._run_async(task="Your task here")
    
    # Close logger
    await close_logger()

asyncio.run(main())
```

## Contributing

Contributions are welcome! Areas for improvement:
- Additional LLM providers (Anthropic, Cohere, etc.)
- More sophisticated planning algorithms
- Enhanced error recovery
- Performance optimizations
- Additional examples and tutorials

## License

MIT License - see LICENSE file for details.
