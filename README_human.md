# LLM Agent Framework

> A type-safe, hierarchical LLM agent framework with tool calling and YAML configuration.

## TL;DR

Build AI agents that can use tools and delegate to sub-agents, with full type safety via Pydantic.

```python
from agent import DeepSeekLLM, Tool, Agent, get_deepseek_api_key

def calculator(expr: str) -> float:
    """Calculate a math expression."""
    return eval(expr)

# Get API key from .env file
api_key = get_deepseek_api_key()

# Create agent with verbose mode for detailed logging
llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")
agent = Agent(llm=llm, tools=[Tool(calculator)])

# Run with verbose=True to see detailed execution steps
response = agent.run("What is 25 * 4?", verbose=True)
```

**Supports Multiple LLM Providers:**
- DeepSeek (deepseek-chat) - Recommended: cheaper and faster
- OpenAI (GPT-4, GPT-3.5-turbo)
- Custom implementations (extend `LLM` abstract class)

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

**Alternative: Environment Variables**

```bash
# Linux/Mac
export DEEPSEEK_API_KEY=your_deepseek_key_here
export OPENAI_API_KEY=your_openai_key_here

# Windows PowerShell
$env:DEEPSEEK_API_KEY="your_deepseek_key_here"
$env:OPENAI_API_KEY="your_openai_key_here"
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

## Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run fast tests only (skip LLM API calls)
pytest tests/ -v -m "not integration"

# Run specific test file
pytest tests/test_tool.py -v
```

## Run Examples

All examples now support `.env` configuration and verbose mode for detailed logging.

```bash
# Simple agent example (best for beginners)
python examples/simple_agent.py

# 🌟 Zoo Director - Hierarchical agents with colored output (recommended)
# Shows parent-child agent delegation with role-playing agents
python examples/zoo_director.py

# Complex integrated test with Chinese output
# Shows real-world data analysis workflow with detailed logging
python examples/complex_integrated_test_cn.py

# Callback system demonstration
python examples/agent_with_callbacks.py

# DeepSeek example
python examples/deepseek_agent.py

# Custom LLM implementation example
python examples/custom_llm.py
```

**Verbose Mode:** All examples now use `agent.run(task, verbose=True)` which shows:
- 🚀 Agent start/finish with timestamps
- 🔄 Each iteration's progress
- 💭 LLM's thought process
- 🔧 Tool calls with arguments
- ✅ Tool execution results
- ⏱️ Performance metrics

**Featured Demos:**

1. **`zoo_director.py`** 🌟 NEW! - Hierarchical agent system with role-playing:
   - 🦁 Director agent delegates to specialized sub-agents
   - 🐱 Cat agent (always starts with "喵呜！")
   - 🐶 Dog agent (always starts with "汪汪！")
   - Each agent displayed in different colors (purple/yellow/blue)
   - Perfect example of agent delegation and personality

2. **`complex_integrated_test_cn.py`** - Complete data analysis workflow:
   - 5 tools (Python execution, file I/O, data queries, calculator)
   - Multi-step reasoning and planning
   - Full Chinese output with detailed step-by-step logging
   - Real business scenario simulation
   - ~90 seconds to complete

## Project Structure

```
hic/
├── agent/                      # Core framework
│   ├── llm.py                 # LLM abstract class + OpenAI implementation
│   ├── deepseek_llm.py        # DeepSeek LLM implementation
│   ├── tool.py                # Tool system (Python functions → tools)
│   ├── agent.py               # Agent execution logic
│   ├── skill.py               # YAML configuration loader
│   ├── parser.py              # LLM output parser
│   ├── schemas.py             # Pydantic data models
│   ├── callbacks.py           # Callback system for observability
│   ├── config.py              # API key configuration with .env support
│   └── __init__.py
│
├── tests/                      # Test suite (37 tests, all passing)
│   ├── test_llm.py            # OpenAI LLM tests (requires API key)
│   ├── test_deepseek.py       # DeepSeek LLM tests (requires API key)
│   ├── test_llm_abstract.py   # Abstract class tests
│   ├── test_tool.py           # Tool creation & validation
│   ├── test_agent.py          # Agent execution tests
│   ├── test_skill.py          # YAML skill loading
│   ├── test_callbacks.py      # Callback system tests
│   ├── test_utils.py          # Test tools (python_exec, file_write, etc)
│   └── fixtures/skills/       # Test YAML configs
│
├── examples/                   # Usage examples (all updated with .env + verbose)
│   ├── simple_agent.py        # Basic agent (best for beginners)
│   ├── zoo_director.py        # 🌟 Hierarchical agents with role-playing
│   ├── deepseek_agent.py      # Agent with DeepSeek LLM
│   ├── custom_llm.py          # Custom LLM implementation
│   ├── skill_with_deepseek.py # YAML-configured agent
│   ├── agent_with_callbacks.py           # Callback system demo
│   └── complex_integrated_test_cn.py     # Complex test (Chinese)
│
├── .env.example               # API key configuration template
└── pyproject.toml             # Project config
```