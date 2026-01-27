# LLM Agent Framework

> A type-safe, hierarchical LLM agent framework with **async parallel execution**, tool calling, and comprehensive logging.

> **🤖 For AI Assistants**: Need to set up GitHub Copilot? See [AI_COPILOT_SETUP.md](AI_COPILOT_SETUP.md) for detailed step-by-step instructions.

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
uv pip install openai pydantic pyyaml python-dotenv pytest requests Levenshtein

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

### GitHub Copilot Setup

**🤖 Era of AI Assistants!**: Use an AI assistant to set up Copilot automatically! Just share [AI_COPILOT_SETUP.md](AI_COPILOT_SETUP.md) with your AI assistant and it will guide you through the entire process.

**Manual Setup:**

1. Create GitHub OAuth App at https://github.com/settings/developers
2. Enable device flow in the OAuth App settings
3. Run authentication:
   ```bash
   cd auth/copilot
   python cli.py auth login
   ```
4. Test:
   ```bash
   python cli.py models
   python examples/copilot_example.py
   ```

For detailed instructions, see [auth/copilot/README.md](auth/copilot/README.md).

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

# Test real-time reporting behavior
pytest tests/test_realtime_reporting.py -v

# Test with specific LLM
pytest tests/test_realtime_reporting.py -k deepseek -v
pytest tests/test_realtime_reporting.py -k copilot -v

# Test Copilot authentication (requires Copilot setup)
pytest tests/test_copilot_auth.py -v
# Or run directly for detailed output:
python tests/test_copilot_auth.py

# Run fast tests only (skip LLM API calls)
pytest tests/ -v -m "not integration"
```

### Real-Time Reporting Test

The `test_realtime_reporting.py` is a critical test that ensures agents provide real-time feedback to users, not batch results at the end.

**Why it matters:**
Imagine you ask an agent to check weather (3 seconds) and stock prices (10 seconds). You don't want to wait 13 seconds for both results - you want to see the weather immediately when it's ready!

**What the test does:**
1. Parent agent receives: "查询北京天气和苹果股票价格" (Check Beijing weather and Apple stock)
2. Parent launches 2 sub-agents in parallel:
   - WeatherAgent (3s) - Fast task
   - StockAgent (10s) - Slow task
3. WeatherAgent finishes first → Parent IMMEDIATELY reports weather data (temperature, conditions, location)
4. Parent continues waiting for StockAgent (doesn't finish early)
5. StockAgent finishes → Parent reports stock data
6. Parent finishes with complete summary

**Key validation:**
- Checks for ACTUAL weather data (not just "WeatherAgent" name):
  - Weather conditions: 晴天, 阴天, cloudy, etc.
  - Temperature: 15°C, 气温：20度, etc.
  - Location: 北京, Beijing
- All 12 workflow steps must occur in correct order
- Parent must report results incrementally, not batch at end

**Run the test:**
```bash
# Test with both LLMs
pytest tests/test_realtime_reporting.py -v

# Test with specific LLM
pytest tests/test_realtime_reporting.py -k deepseek -v
pytest tests/test_realtime_reporting.py -k copilot -v
```

**Technical features demonstrated:**
- Async parallel execution (not sequential)
- Real-time incremental reporting
- Error handling for API failures (429 rate limits)
- Independent LLM instances per agent (prevents history contamination)
- Strict log validation

### Peer-to-Peer Communication Test (NEW)

`tests/test_communicate.py` ensures sibling agents can exchange data directly via `send_message`/`wait`, even when one agent is still running. AgentA knows the哈希前半部分, AgentB知道后半部分——他们必须互相同步、确认双方都掌握完整哈希码后再 finish。

```bash
# 默认使用真实 DeepSeek LLM（需要 DEEPSEEK_API_KEY）
pytest tests/test_communicate.py -s -k deepseek -v

# 如需离线/无 API 模式，使用脚本化 LLM
USE_SCRIPTED_LLM=1 pytest tests/test_communicate.py -s -k deepseek -v
```

日志会出现 `[AgentA -> AgentB]发送信息，对方状态是wait，信息内容：...` 等语句，便于在 `logs/AgentA_*.log`、`logs/AgentB_*.log`、`logs/ParentAgent_*.log` 中追踪整个通信过程。

### 并行猜数挑战 (NEW)

`tests/test_parallel_guess.py` 会并行启动 6 个子 Agent（三个提问者 + 三个回答者）以及一个父 Agent：

- 父 Agent 选择 3 个 1-10 的整数，并把它们分发给回答者
- 每个提问者只能问 “真实数字比 X 大/小/等于？”
- 回答者必须诚实回答（支持大/小/相等等三种情况）
- 提问者猜对后立刻 finish，父 Agent 需要根据完成先后给出排名
- 测试会解析 `logs/Questioner*_*.log` 的完成时间，确保父 Agent 报告的排名与真实完成顺序一致

```bash
# 默认使用真实 DeepSeek LLM（需要 DEEPSEEK_API_KEY）
pytest tests/test_parallel_guess.py -s -k deepseek -v

# 如需离线/无 API 模式，使用脚本化 LLM
USE_SCRIPTED_LLM=1 pytest tests/test_parallel_guess.py -v
```

该测试覆盖了多对等 Agent 同时通信、排队消息在 wait/运行状态之间切换、以及从日志提取时间戳做断言的完整流程。

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
│   ├── test_realtime_reporting.py  # Real-time reporting behavior tests
│   ├── test_tool.py           # Tool creation & validation
│   ├── test_llm.py            # LLM implementations tests
│   ├── test_llm_abstract.py   # Abstract LLM base class tests
│   ├── test_skill.py          # YAML skill loading tests
│   ├── test_copilot_auth.py   # Copilot authentication tests
│   ├── test_utils.py          # Utility functions tests
│   └── __init__.py
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
