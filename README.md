# For humans, go to [README_human.md](README_human.md)

# Human Is Cheap (HIC)

> Human is cheap, time is valuable.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
  - [API Keys with .env](#api-keys-with-env)
  - [GitHub Copilot Authentication](#github-copilot-authentication)
- [Quick Start](#quick-start)
  - [1. Create Tools](#1-create-tools)
  - [2. Set Up LLM and Agent](#2-set-up-llm-and-agent)
  - [3. Run the Agent](#3-run-the-agent)
  - [Verbose Mode](#verbose-mode)
- [Using Different LLM Models](#using-different-llm-models)
  - [OpenAI Models](#openai-models)
  - [DeepSeek Models](#deepseek-models)
  - [GitHub Copilot Models](#github-copilot-models)
  - [Custom LLM Implementation](#custom-llm-implementation)
- [Using Skills (YAML Configuration)](#using-skills-yaml-configuration)
- [Hierarchical Agents](#hierarchical-agents)
- [Agent Observability with Callbacks](#agent-observability-with-callbacks)
  - [AsyncLogger (Recommended)](#asynclogger-recommended-for-modern-applications)
  - [Quick Verbose Mode](#quick-verbose-mode-using-callbacks)
  - [Built-in Callbacks](#built-in-callbacks)
  - [Custom Callbacks](#custom-callbacks)
- [LLM Output Format](#llm-output-format)
- [Running Tests](#running-tests)
- [Project Structure](#project-structure)
- [Examples](#examples)
- [Key Concepts](#key-concepts)
  - [Tool Creation](#tool-creation)
  - [Tool Infrastructure](#tool-infrastructure)
    - [ToolResult - Structured Return Format](#toolresult---structured-return-format)
    - [Context - Execution Environment](#context---execution-environment)
    - [Permission System](#permission-system)
    - [Output Truncation](#output-truncation)
  - [Built-in Tools](#built-in-tools)
  - [Error Handling](#error-handling)
  - [Subagent Communication](#subagent-communication)
- [Example: File Analysis Agent](#example-file-analysis-agent)
- [Advanced Usage](#advanced-usage)
- [License](#license)
- [Contributing](#contributing)
- [Troubleshooting](#troubleshooting)

## Features

- **Extensible LLM Support**: Abstract base class for implementing any LLM provider
  - OpenAI (GPT-3.5, GPT-4)
  - DeepSeek (deepseek-chat)
  - **GitHub Copilot** (claude-sonnet-4.5, claude-haiku-4.5, gpt-4o, o1-preview, and more)
  - Easy to add custom providers
- **Type-Safe Tool System**: Create tools from Python functions with automatic type validation
  - **Structured Tool Results**: ToolResult with title, output, metadata, attachments, and timestamps
  - **Context Injection**: Automatic execution context (session, permissions, abort signals)
  - **Permission System**: Request/approve flow with pattern-based auto-approval
  - **Output Truncation**: Automatic truncation of large outputs (2000 lines / 50KB)
- **Built-in Tools**:
  - **Enhanced Bash Tool**: Async shell execution with permissions, timeouts, and structured results
  - **Calculator**: Safe mathematical expression evaluation
- **Hierarchical Agents**: Agents can delegate tasks to specialized subagents
- **Async Execution**: Full async support with parallel subagent execution
  - **Agent Orchestrator**: Message-based coordination and state management
  - **Real-Time Reporting**: Incremental result streaming during long operations
- **Modern Logging System**: AsyncLogger with color-coded output and per-agent file logging
- **YAML Configuration**: Define complex agent structures using YAML files
- **Automatic Parsing**: LLM outputs are parsed and validated using Pydantic schemas
- **Error Handling**: Built-in retry logic for parsing errors and tool failures
- **Observability**: Callback system for monitoring, logging, and metrics collection
- **Security Features**: 
  - Dangerous command detection
  - Path safety validation
  - Command whitelisting for restricted mode
  - Abort signals for cancellation

## Architecture

The framework has eight core abstractions:

1. **LLM**: Abstract base class for LLM implementations (with OpenAILLM as default)
2. **Tool**: Python functions with type annotations that agents can use
3. **ToolResult**: Structured return format with output, metadata, and attachments
4. **Context**: Execution context with permissions, abort signals, and session management
5. **Skill**: YAML-configured combinations of tools for complex tasks
6. **Agent**: The core element that uses tools and delegates to subagents
7. **AgentOrchestrator**: Message-based coordinator for async agent execution and state management
8. **AsyncLogger**: Modern async-safe logging with color-coded output and per-agent files
9. **Callbacks**: Event hooks for observability, monitoring, and custom integrations

## Installation

```bash
# Install dependencies
pip install openai pydantic pyyaml python-dotenv requests

# For development
pip install pytest pytest-asyncio

# Or install from pyproject.toml
pip install -e .
pip install -e ".[dev]"  # with dev dependencies
```

## Configuration

### API Keys with .env

The framework supports loading API keys from a `.env` file for better security:

```bash
# Create a .env file in your project root
cp .env.example .env

# Edit .env and add your API keys
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

The framework automatically loads `.env` on import. You can use the built-in helper functions:

```python
from agent import get_deepseek_api_key, get_openai_api_key

# Get API keys (priority: .env > environment variables > legacy file)
deepseek_key = get_deepseek_api_key()
openai_key = get_openai_api_key()

if not deepseek_key:
    print("Please set DEEPSEEK_API_KEY in .env file")
```

### GitHub Copilot Authentication

GitHub Copilot uses OAuth device flow authentication (no API key needed in `.env`):

```bash
# First-time setup
cd auth/copilot
python cli.py auth login
```

The token is stored at `~/.config/mycopilot/github_token.json` and is automatically loaded by `CopilotLLM`.

See the [GitHub Copilot section](#github-copilot-models) for detailed setup instructions.

## Quick Start

### 1. Create Tools

Tools can return simple strings or structured ToolResult objects:

```python
from agent import Tool
from agent.tool_result import ToolResult

# Simple tool returning a string
def calculator(expression: str) -> float:
    """Evaluate a mathematical expression."""
    return eval(expression)

# Advanced tool returning ToolResult with metadata
def file_writer(path: str, content: str) -> ToolResult:
    """Write content to a file."""
    with open(path, 'w') as f:
        f.write(content)
    return ToolResult.success(
        title=f"File written: {path}",
        output=f"Successfully wrote {len(content)} bytes to {path}",
        metadata={"path": path, "size": len(content)}
    )

calc_tool = Tool(calculator)
file_tool = Tool(file_writer)
```

**Using Built-in Tools:**

```python
from agent.tools.bash import bash
from agent.builtin_tools import calculator

# Modern bash tool with permissions and structured results
bash_tool = Tool(bash)

# Calculator tool (safe mathematical evaluation)
calc_tool = Tool(calculator)
```

**Context Injection:**

Tools can receive execution context automatically by adding a `ctx` parameter:

```python
from agent.context import Context
from agent.tool_result import ToolResult

def interactive_tool(question: str, ctx: Context) -> ToolResult:
    """Ask user for approval before executing."""
    # Request permission from user
    approved = ctx.ask("bash", patterns=["ls *"], description=f"Execute: ls")
    
    if approved:
        return ToolResult.success(output="Approved and executed")
    else:
        return ToolResult.from_error("User denied permission")

# Context is automatically injected by Agent
tool = Tool(interactive_tool)
```

### 2. Set Up LLM and Agent

```python
from agent import DeepSeekLLM, Agent, get_deepseek_api_key

# Get API key from .env
api_key = get_deepseek_api_key()

# Initialize LLM
llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")

# Create agent with tools
agent = Agent(
    llm=llm,
    tools=[calc_tool, file_tool],
    max_iterations=10
)
```

### 3. Run the Agent

```python
# Run with verbose mode for detailed logging
response = agent.run(
    "Calculate 25 * 4 and save the result to result.txt",
    verbose=True  # Shows detailed execution steps
)

print(f"Success: {response.success}")
print(f"Result: {response.content}")
print(f"Iterations: {response.iterations}")
```

### Verbose Mode

The `verbose=True` parameter enables detailed console logging automatically:

```python
# Detailed logging shows:
# - Each iteration's thought process
# - Tool calls with arguments
# - Tool execution results
# - LLM responses
# - Performance metrics

agent.run("Your task here", verbose=True)
```

Output example:
```
================================================================================
🚀 Agent 'MyAgent' Starting
================================================================================
📋 Task: Calculate 25 * 4 and save the result to result.txt
🕐 Started: 14:32:01

🧠 LLM Response:
   Thought: I need to calculate 25 * 4 first using the calculator tool
   Action: tool
   Tool: calculator
   Arguments: {"expression": "25 * 4"}

────────────────────────────────────────────────────────────────────────────────
🔄 Iteration 1
────────────────────────────────────────────────────────────────────────────────
✅ Parsed action: tool

🔧 Calling tool: calculator
   Arguments: {
  "expression": "25 * 4"
}
✅ Tool result: 100.0
...
```

## Using Different LLM Models

The framework uses an abstract `LLM` base class, making it easy to use different models:

### OpenAI Models

```python
from agent import OpenAILLM

# Use GPT-4
llm = OpenAILLM(model="gpt-4", temperature=0.7)

# Use GPT-3.5 Turbo
llm = OpenAILLM(model="gpt-3.5-turbo", temperature=0.2)

# With custom parameters
llm = OpenAILLM(
    model="gpt-4",
    temperature=0.5,
    max_tokens=2000,
    top_p=0.9
)
```

### DeepSeek Models

```python
from agent import DeepSeekLLM, get_deepseek_api_key

# Use DeepSeek
api_key = get_deepseek_api_key()
llm = DeepSeekLLM(
    api_key=api_key,
    model="deepseek-chat",
    temperature=0.7
)
```

### GitHub Copilot Models

GitHub Copilot provides access to multiple high-quality models through a single API.

#### Setup (First Time Only)

1. **Create GitHub OAuth App**:
   - Go to https://github.com/settings/developers
   - Click "OAuth Apps" → "New OAuth App"
   - Fill in:
     - Application name: Any name (e.g., "My Copilot CLI")
     - Homepage URL: `http://localhost`
     - Authorization callback URL: `http://localhost`
   - **Enable device flow** (important!)
   - Copy the **Client ID**

2. **Configure Client ID**:
   ```bash
   # Edit auth/copilot/auth.py
   # Replace: CLIENT_ID = "YOUR_ID"
   # With your actual Client ID
   ```

3. **Authenticate**:
   ```bash
   cd auth/copilot
   python cli.py auth login
   ```
   Follow the prompts to complete OAuth authentication.

4. **Verify**:
   ```bash
   # List available models
   python cli.py models
   
   # Test a simple chat
   python cli.py run "Hello" claude-haiku-4.5
   ```

#### Using Copilot in Code

```python
from agent import Agent, CopilotLLM, Tool

# Create Copilot LLM (uses token from ~/.config/mycopilot/github_token.json)
llm = CopilotLLM(
    model="claude-haiku-4.5",  # Fast and cost-effective
    temperature=0.7,
)

# Create agent with tools
agent = Agent(
    llm=llm,
    tools=[your_tools],
    name="MyAgent",
    system_prompt="Your system prompt",
)

# Run agent
result = await agent._run_async(task="Your task")
```

**Available Copilot Models**:
- `claude-sonnet-4.5` - Balanced performance (recommended)
- `claude-haiku-4.5` - Fast and cost-effective
- `gpt-4o` - Latest GPT-4 optimized
- `gpt-4o-mini` - Smaller, faster GPT-4
- `o1-preview` - Advanced reasoning
- `o1-mini` - Compact reasoning model

**See full example**: `examples/copilot_example.py`

**Documentation**: See `auth/copilot/README.md` for detailed setup and troubleshooting.

### Custom LLM Implementation

You can implement your own LLM provider by extending the `LLM` abstract class:

```python
from agent import LLM
from typing import Optional

class CustomLLM(LLM):
    def __init__(self, model: str, **kwargs):
        super().__init__()
        self.model = model
        # Initialize your custom LLM client here
    
    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        # Add system prompt if needed
        if not self.history and system_prompt:
            self.history.append({"role": "system", "content": system_prompt})
        
        # Add user message
        self.history.append({"role": "user", "content": prompt})
        
        # Call your LLM API here
        response = your_llm_api_call(self.history)
        
        # Add assistant response
        self.history.append({"role": "assistant", "content": response})
        
        return response

# Use your custom LLM
llm = CustomLLM(model="your-model")
agent = Agent(llm=llm, tools=tools)
```

## Using Skills (YAML Configuration)

Create a skill YAML file:

```yaml
# skill.yaml
name: "file_assistant"
description: "An assistant that works with files"
tools:
  - file_write
  - file_search
max_iterations: 10
system_prompt: "You can write and search for files efficiently."
```

Load the skill:

```python
from agent import Skill, OpenAILLM, Tool

# Define available tools
tools = {
    "file_write": Tool(file_writer),
    "file_search": Tool(file_searcher)
}

llm = OpenAILLM(model="gpt-3.5-turbo")
agent = Skill.from_yaml("skill.yaml", tools, llm)

response = agent.run("Create a test file and find all .txt files")
```

## Hierarchical Agents

Create agents with subagents for complex task delegation:

```yaml
# parent_agent.yaml
name: "research_assistant"
description: "Main research assistant"
tools:
  - calculator
subagents:
  file_helper: "file_assistant.yaml"
max_iterations: 15
```

The parent agent can delegate file operations to its subagent:

```python
agent = Skill.from_yaml("parent_agent.yaml", tools, llm)
response = agent.run("Calculate 100/5 and save it to result.txt")
```

### Example: Multi-Layer Research System

See `examples/multi_layer_research_system.py` for a complete example of a 3-layer agent hierarchy:

```python
from agent import Agent, DeepSeekLLM, Tool

# Layer 3: Specialized workers (DataCollector, PaperFinder, etc.)
data_collector = Agent(llm=llm, tools=tools, name="DataCollector")
paper_finder = Agent(llm=llm, tools=tools, name="PaperFinder")

# Layer 2: Coordinators (DataAnalyst, LiteratureResearcher)
data_analyst = Agent(
    llm=llm,
    tools=tools,
    subagents={"DataCollector": data_collector, "DataProcessor": data_processor},
    name="DataAnalyst"
)

literature_researcher = Agent(
    llm=llm,
    tools=tools,
    subagents={"PaperFinder": paper_finder, "SummaryGenerator": summary_gen},
    name="LiteratureResearcher"
)

# Layer 1: Director
director = Agent(
    llm=llm,
    tools=tools,
    subagents={
        "DataAnalyst": data_analyst,
        "LiteratureResearcher": literature_researcher
    },
    name="ResearchDirector"
)

# Run with automatic AsyncLogger
response = await director._run_async("研究任务：分析数据并查找相关文献")
```

This example demonstrates:
- **3-layer hierarchy**: Director → Coordinators → Workers
- **Async parallel execution**: Multiple subagents run concurrently
- **Real-time reporting**: Results reported as they complete
- **Recursive delegation**: Each layer can delegate to the next
- **Full observability**: AsyncLogger tracks all agent interactions

## Agent Observability with Callbacks

The framework provides multiple ways to monitor and log agent execution.

### AsyncLogger (Recommended for Modern Applications)

The modern `AsyncLogger` provides async-safe logging with color-coded output and per-agent file logging:

```python
from agent import Agent, DeepSeekLLM, init_logger, close_logger, get_deepseek_api_key

# Initialize global logger
init_logger(log_dir="logs", console_enabled=True)

# Set up agent
llm = DeepSeekLLM(api_key=get_deepseek_api_key(), model="deepseek-chat")
agent = Agent(llm=llm, tools=tools, name="MyAgent")

# Run agent - logging happens automatically
response = await agent._run_async("Your task here")

# Clean up
await close_logger()
```

**AsyncLogger Features:**
- **Color-coded console output** with automatic agent color assignment
- **Per-agent log files** with timestamps (e.g., `logs/MyAgent_20250126_143201.log`)
- **Async file writing** (non-blocking queue for performance)
- **Hierarchical indentation** for subagents
- **Elapsed time tracking** for operations
- **Log levels**: DEBUG, INFO, WARNING, ERROR

**Logging Methods:**
```python
from agent.async_logger import get_logger

logger = get_logger()
await logger.log("Custom message", level="INFO", agent_name="MyAgent")
await logger.agent_start("MyAgent", "Task description")
await logger.agent_thought("MyAgent", "Thinking...")
await logger.tool_call("MyAgent", "bash", {"command": "ls"})
await logger.agent_finish("MyAgent", success=True, elapsed=1.5)
```

### Quick Verbose Mode (Using Callbacks)

For simple use cases, the `verbose` parameter enables detailed console logging:

```python
from agent import Agent, DeepSeekLLM, get_deepseek_api_key

# Set up agent
llm = DeepSeekLLM(api_key=get_deepseek_api_key(), model="deepseek-chat")
agent = Agent(llm=llm, tools=tools)

# Run with verbose mode - automatically shows detailed logs with colors
response = agent.run("Your task here", verbose=True)
```

This automatically adds a `ColorfulConsoleCallback` (⚠️ DEPRECATED, use AsyncLogger instead) that provides:
- **Color-coded output** for different agents
- **Automatic indentation** based on agent nesting level
- Agent start/finish events with timestamps
- Each iteration's thought process
- Tool calls with arguments and results

**For hierarchical agents**, each agent in the execution stack gets its own color:

```python
from agent import ColorfulConsoleCallback

# Custom color mapping for your agents (DEPRECATED - use AsyncLogger)
color_map = {
    "MainAgent": "\033[35m",    # Purple
    "Helper": "\033[33m",       # Yellow
    "Analyzer": "\033[34m",     # Blue
}

callback = ColorfulConsoleCallback(verbose=True, color_map=color_map)
agent = Agent(llm=llm, tools=tools, callbacks=[callback])
```

### Built-in Callbacks

For more control, you can use callbacks directly:

```python
from agent import Agent, ConsoleCallback, MetricsCallback, FileLoggerCallback

# Console logging callback
console = ConsoleCallback(
    verbose=True,          # Show all events
    show_prompts=False,    # Hide full prompts
    show_responses=True,   # Show LLM responses
    color=True            # Use colored output
)

# Metrics collection callback
metrics = MetricsCallback()

# File logging callback
file_logger = FileLoggerCallback("agent.log", format="json")

# Use callbacks with agent
agent = Agent(
    llm=llm,
    tools=tools,
    callbacks=[console, metrics, file_logger]
)

response = agent.run("Your task here")

# Print metrics
metrics.print_summary()
```

### Custom Callbacks

Implement your own callbacks for custom monitoring:

```python
from agent import AgentCallback

class CustomCallback(AgentCallback):
    """Track specific events for your needs."""
    
    def on_agent_start(self, task: str, agent_name: str):
        print(f"Agent {agent_name} started: {task}")
    
    def on_tool_call(self, iteration: int, tool_name: str, arguments: dict):
        print(f"Calling {tool_name} with {arguments}")
    
    def on_agent_finish(self, success: bool, iterations: int, content: str):
        print(f"Finished in {iterations} iterations")

# Use your custom callback
agent = Agent(llm=llm, tools=tools, callbacks=[CustomCallback()])
```

### Available Callback Events

- `on_agent_start` - Agent begins execution
- `on_iteration_start` - New iteration begins
- `on_llm_request` - Before LLM call
- `on_llm_response` - After LLM response
- `on_parse_success` - LLM output parsed successfully
- `on_parse_error` - Parse error occurred
- `on_tool_call` - Before tool execution
- `on_tool_result` - After tool completes
- `on_subagent_call` - Before subagent delegation
- `on_subagent_result` - After subagent completes
- `on_iteration_end` - Iteration completes
- `on_agent_finish` - Agent completes execution

See `examples/async_parallel_agents.py` and `examples/multi_layer_research_system.py` for comprehensive examples of callbacks and AsyncLogger usage.

## LLM Output Format

The LLM is instructed to use this format:

```
Thought: <reasoning>
Action: tool
Tool: <tool_name>
Arguments: {"arg1": "value1", ...}
```

Or to finish:

```
Thought: <reasoning>
Action: finish
Response: <final answer>
```

## Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_tool.py

# Run with verbose output
pytest -v

# Run specific test categories
pytest tests/test_tool_infrastructure.py -v  # Tool infrastructure tests
pytest tests/test_bash_tool.py -v           # Enhanced bash tool tests
pytest tests/test_builtin_tools.py -v       # Built-in tools tests
pytest tests/test_agent_tool_integration.py -v  # Integration tests
pytest tests/test_restricted_bash.py -v     # Command restriction tests

# Test Copilot authentication (requires Copilot setup)
pytest tests/test_copilot_auth.py -v
# Or run directly for detailed output:
python tests/test_copilot_auth.py

# Test real-time reporting behavior
pytest tests/test_realtime_reporting.py -v

# Test with specific LLM
pytest tests/test_realtime_reporting.py -k deepseek -v
pytest tests/test_realtime_reporting.py -k copilot -v

# Note: test_llm.py requires OPENAI_API_KEY to be set
export OPENAI_API_KEY=your_key_here
pytest tests/test_llm.py
```

### Real-Time Reporting Test

The `test_realtime_reporting.py` validates that agents report results incrementally (in real-time) rather than batching all results at the end. This is crucial for user experience in long-running agent tasks.

**What it tests:**
- Parent agent launches 2 sub-agents in parallel:
  - WeatherAgent (3 seconds) - Queries weather for Beijing
  - StockAgent (10 seconds) - Queries stock price for Apple
- When WeatherAgent finishes first, parent IMMEDIATELY reports the weather data in its Thought
- Parent continues waiting for StockAgent (doesn't finish early)
- When StockAgent finishes, parent reports the stock data
- All workflow steps must occur in the correct order

**Key features demonstrated:**
- **Async Parallel Execution**: Both sub-agents run concurrently, not sequentially
- **Real-Time Incremental Reporting**: Results reported as they arrive, not batched at end
- **Error Handling**: Properly handles LLM API failures (e.g., 429 rate limits)
- **Independent LLM Instances**: Each agent gets its own LLM instance to prevent history contamination
- **Strict Validation**: Validates actual weather/stock data content, not just agent names

**Run the test:**
```bash
# Run with both DeepSeek and Copilot LLMs
pytest tests/test_realtime_reporting.py -v

# Run with specific LLM only
pytest tests/test_realtime_reporting.py -k deepseek -v
pytest tests/test_realtime_reporting.py -k copilot -v
```

**Expected behavior:**
1. Parent receives task: "查询北京天气和苹果股票价格"
2. Parent launches WeatherAgent and StockAgent in parallel
3. Parent suspends and waits
4. WeatherAgent completes (~3s) → Parent resumes
5. Parent's Thought mentions actual weather data (temperature, condition, location)
6. Parent continues waiting for StockAgent
7. StockAgent completes (~10s) → Parent resumes again
8. Parent's Thought mentions actual stock data
9. Parent finishes with complete summary

This test ensures the framework provides responsive, real-time feedback to users even when some sub-tasks take much longer than others.

## Project Structure

```
hic/
├── agent/
│   ├── __init__.py
│   ├── llm.py              # LLM abstract base class
│   ├── deepseek_llm.py     # DeepSeek implementation
│   ├── copilot_llm.py      # GitHub Copilot implementation
│   ├── tool.py             # Tool system
│   ├── tool_result.py      # ToolResult with metadata and attachments
│   ├── context.py          # Execution context with permissions
│   ├── permissions.py      # Permission system and security
│   ├── truncation.py       # Output truncation for large results
│   ├── builtin_tools.py    # Built-in tools (calculator, deprecated bash)
│   ├── tools/
│   │   ├── __init__.py
│   │   └── bash.py         # Modern async bash tool
│   ├── agent.py            # Agent logic
│   ├── orchestrator.py     # Async orchestration
│   ├── skill.py            # YAML loading
│   ├── schemas.py          # Pydantic models
│   ├── parser.py           # Output parser
│   ├── callbacks.py        # Callback system
│   ├── async_logger.py     # Modern async logging
│   └── config.py           # Configuration and API keys
├── auth/
│   └── copilot/            # GitHub Copilot authentication
│       ├── auth.py         # OAuth device flow
│       ├── chat.py         # Chat API client
│       ├── cli.py          # CLI tool
│       ├── config.py       # Token management
│       ├── models.py       # Model listing
│       └── README.md       # Setup guide
├── tests/
│   ├── test_llm.py                 # LLM implementations tests
│   ├── test_llm_abstract.py        # Abstract LLM base class tests
│   ├── test_tool.py                # Tool creation & validation tests
│   ├── test_tool_infrastructure.py # Context, permissions, truncation tests
│   ├── test_bash_tool.py           # Enhanced bash tool tests
│   ├── test_restricted_bash.py     # Command restriction tests
│   ├── test_builtin_tools.py       # Built-in tools tests
│   ├── test_agent_tool_integration.py # Integration tests
│   ├── test_skill.py               # YAML skill loading tests
│   ├── test_async_basic.py         # Async parallel execution tests
│   ├── test_realtime_reporting.py  # Real-time reporting behavior tests
│   ├── test_copilot_auth.py        # Copilot authentication tests
│   ├── test_role.py                # Message role support tests
│   └── test_utils.py               # Utility functions tests
├── examples/
│   ├── copilot_example.py              # Copilot usage example
│   ├── builtin_tool_call.py            # Built-in tools example
│   ├── tool_infrastructure_example.py  # Advanced tool features
│   ├── new_enhanced_bash_tool.py       # Enhanced bash tool example
│   ├── async_parallel_agents.py        # Async parallel execution
│   ├── async_parallel_agents_real.py   # Real-time reporting
│   └── multi_layer_research_system.py  # 3-layer hierarchy (Chinese)
├── pyproject.toml
└── README.md
```

## Examples

The framework includes several examples demonstrating different features:

### Basic Examples
- **`copilot_example.py`** - Using GitHub Copilot LLM (requires authentication)
- **`builtin_tool_call.py`** - Using built-in tools (bash, calculator)
- **`tool_infrastructure_example.py`** - Advanced tool features (Context, ToolResult, permissions)
- **`new_enhanced_bash_tool.py`** - Enhanced bash tool with permissions and structured results

### Advanced Examples
- **`async_parallel_agents.py`** - Async parallel agent execution with configurable LLM
- **`async_parallel_agents_real.py`** - Real LLM with timing verification
- **`multi_layer_research_system.py`** - 3-layer agent hierarchy (Chinese)
  - L1 (Top): ResearchDirector - 研究总监
  - L2 (Middle): DataAnalyst, LiteratureResearcher - 数据分析师、文献研究员
  - L3 (Bottom): DataCollector, DataProcessor, PaperFinder, SummaryGenerator - 数据采集/处理员、论文查找/摘要员
  - Demonstrates recursive agent calls and parallel execution
  - Full async orchestration with real-time reporting

Run any example:
```bash
python examples/copilot_example.py  # Requires GitHub Copilot authentication
python examples/tool_infrastructure_example.py
python examples/multi_layer_research_system.py
```

## Key Concepts

### Tool Creation

Tools are created from Python functions with type annotations:

```python
def my_tool(x: int, y: str = "default") -> str:
    """Tool description shown to LLM."""
    return f"x={x}, y={y}"

tool = Tool(my_tool)
```

The framework automatically:
- Extracts parameter types
- Validates arguments using Pydantic
- Generates schema descriptions for the LLM

### Tool Infrastructure

The framework provides a comprehensive tool infrastructure for building robust, secure tools:

#### ToolResult - Structured Return Format

Tools can return rich, structured results instead of plain strings:

```python
from agent.tool_result import ToolResult, Attachment

def advanced_tool(query: str) -> ToolResult:
    """Tool with structured output."""
    return ToolResult.success(
        title="Query Results",
        output="Found 3 matches:\n1. Result A\n2. Result B\n3. Result C",
        metadata={
            "count": 3,
            "query": query,
            "timestamp": "2025-01-26T14:32:01"
        },
        attachments=[
            Attachment.from_file("report.pdf", attachment_type="file")
        ]
    )
```

**ToolResult features:**
- `title`: Short summary
- `output`: Detailed text output
- `metadata`: Structured data (dict)
- `attachments`: Files, images, or data
- `error_message`: Error information
- `timestamp`: ISO format timestamp
- `is_success` / `is_error`: Status properties

#### Context - Execution Environment

Tools can receive execution context for permissions, abort signals, and session management:

```python
from agent.context import Context
from agent.tool_result import ToolResult

def interactive_tool(command: str, ctx: Context) -> ToolResult:
    """Tool that requests permission before execution."""
    # Check if aborted
    if ctx.is_aborted:
        return ToolResult.from_error("Operation aborted by user")
    
    # Request permission
    approved = ctx.ask(
        permission_type="bash",
        patterns=[command],
        description=f"Execute command: {command}"
    )
    
    if not approved:
        return ToolResult.from_error("Permission denied")
    
    # Execute command...
    return ToolResult.success(output="Command executed")
```

**Context features:**
- `session_id`, `message_id`, `call_id`: Unique identifiers
- `agent_name`: Current agent name
- `ask()`: Request permission from user
- `abort()`, `check_abort()`, `is_aborted`: Abort signals
- `get_metadata()`, `set_metadata()`, `update_metadata()`: Session storage
- `workdir`: Current working directory

#### Permission System

Fine-grained control over tool execution:

```python
from agent.permissions import (
    AutoApproveHandler,
    InteractiveHandler,
    PermissionType
)
from agent.context import create_context

# Auto-approve specific patterns
auto_approve = AutoApproveHandler({
    PermissionType.BASH: ["ls *", "cat *.txt"],
    PermissionType.READ: ["*.md", "docs/*"]
})

# Create context with permission handler
ctx = create_context(
    permission_handler=auto_approve,
    session_id="session_123"
)
```

**Permission types:**
- `BASH`: Shell command execution
- `READ`: File reading
- `WRITE`: File writing
- `DELETE`: File deletion
- `NETWORK`: Network requests
- `WEBFETCH`: Web content fetching
- `QUESTION`: User questions
- `EXECUTE`: Code execution

**Permission handlers:**
- `AutoApproveHandler`: Pattern-based auto-approval (glob wildcards)
- `InteractiveHandler`: CLI prompts for approval
- `AlwaysAllowHandler`: Approve everything (testing only)
- `AlwaysDenyHandler`: Deny everything (read-only mode)

**Security features:**
- `is_path_safe()`: Prevent directory escape attacks
- `is_command_dangerous()`: Detect dangerous shell commands
- Dangerous command patterns: `rm -rf`, `dd`, `chmod 777`, `curl|bash`, etc.

#### Output Truncation

Automatic truncation of large outputs to prevent token overflow:

```python
from agent.truncation import OutputTruncator

truncator = OutputTruncator(max_lines=2000, max_bytes=51200)  # 50KB
result, metadata = truncator.truncate(large_output)

if metadata.is_truncated:
    print(f"Output truncated at line {metadata.truncated_at_line}")
    print(f"Full output saved to: {metadata.full_output_file}")
```

**Features:**
- Default limits: 2000 lines or 50KB
- Saves full output to temp file
- Returns truncation metadata
- Automatic cleanup of old files

### Built-in Tools

#### Enhanced Bash Tool (Recommended)

```python
from agent.tools.bash import bash
from agent.tool import Tool

bash_tool = Tool(bash)
agent = Agent(llm=llm, tools=[bash_tool])
```

**Features:**
- Async execution with timeouts (default 120s)
- Permission system integration
- Automatic output truncation
- Dangerous command detection
- Working directory validation
- Structured ToolResult with exit codes and duration
- Abort signal handling

#### Calculator Tool

```python
from agent.builtin_tools import calculator
from agent.tool import Tool

calc_tool = Tool(calculator)
```

**Safe mathematical evaluation:**
- Basic arithmetic: `+`, `-`, `*`, `/`, `//`, `%`, `**`
- Functions: `abs`, `round`, `min`, `max`, `sum`
- Math functions: `sqrt`, `sin`, `cos`, `tan`, `log`, `log10`, `exp`, `pi`, `e`
- No arbitrary code execution

#### Deprecated Tools

⚠️ **WARNING**: The following tools in `agent.builtin_tools` are DEPRECATED:
- `bash()` - Use `agent.tools.bash.bash()` instead
- `restricted_bash()` - Use `agent.tools.bash.bash()` with `allowed_commands` instead

**Migration:**
```python
# OLD (deprecated)
from agent.builtin_tools import bash, restricted_bash

# NEW (recommended)
from agent.tools.bash import bash
from agent.tool import Tool

bash_tool = Tool(bash)  # Context auto-injected by Agent
```

### Error Handling

The framework includes robust error handling:

- **Parse errors**: Retries up to 3 times with feedback to LLM
- **Tool errors**: Returns error message to LLM for recovery
- **Max iterations**: Forces a summary when limit is reached
- **Permission denied**: ToolResult with error message
- **Abort signals**: Graceful cancellation of operations

### Subagent Communication

When a subagent completes a task, it:
1. Generates a summary of its work
2. Returns the summary to the parent agent
3. Parent agent uses the summary to continue its task

Subagents cannot call their parent agents, preventing infinite recursion.

## Example: File Analysis Agent

```python
from agent import OpenAILLM, Tool, Agent

def read_file(path: str) -> str:
    """Read content from a file."""
    with open(path, 'r') as f:
        return f.read()

def count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())

# Create tools
read_tool = Tool(read_file)
count_tool = Tool(count_words)

# Create agent with OpenAI
llm = OpenAILLM(model="gpt-3.5-turbo")
agent = Agent(llm=llm, tools=[read_tool, count_tool])

# Run analysis
response = agent.run("Read README.md and count how many words it has")
print(response.content)
```

## Advanced Usage

### Custom System Prompts

```python
custom_prompt = "You are a Python expert. Always write clean, efficient code."
agent = Agent(llm=llm, tools=tools, system_prompt=custom_prompt)
```

### Configuring OpenAI LLM

```python
llm = OpenAILLM(
    model="gpt-4",
    temperature=0.2,
    max_tokens=1000,
    top_p=0.9
)
```

### Accessing Agent History

```python
response = agent.run("Some task")
history = agent.llm.get_history()
for msg in history:
    print(f"{msg['role']}: {msg['content']}")
```

## License

MIT License

## Contributing

Contributions are welcome! Please ensure:
- Type annotations on all functions
- Docstrings for tools and public methods
- Tests for new features
- Code follows existing style

## Troubleshooting

### Tests failing with "OPENAI_API_KEY not set"

Set your API key:
```bash
export OPENAI_API_KEY=your_key_here
```

### Import errors

Make sure you're running from the project root:
```bash
cd hic
python -m pytest tests/
```

### Pydantic validation errors

Ensure your tool functions have proper type annotations:
```python
# Good
def my_tool(x: int, y: str) -> str:
    ...

# Bad - missing type annotations
def my_tool(x, y):
    ...
```
