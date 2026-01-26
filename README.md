# For humans, go to [README_human.md](README_human.md)

# LLM Agent Framework

A type-safe, hierarchical LLM agent framework built with Python, Pydantic, and extensible LLM support.

## Features

- **Extensible LLM Support**: Abstract base class for implementing any LLM provider
  - OpenAI (GPT-3.5, GPT-4)
  - DeepSeek (deepseek-chat)
  - **GitHub Copilot** (claude-sonnet-4.5, claude-haiku-4.5, gpt-4o, o1-preview, and more)
  - Easy to add custom providers
- **Type-Safe Tool System**: Create tools from Python functions with automatic type validation
- **Hierarchical Agents**: Agents can delegate tasks to specialized subagents
- **Async Execution**: Full async support with parallel subagent execution
- **Real-Time Logging**: Hierarchical logging with incremental result reporting
- **YAML Configuration**: Define complex agent structures using YAML files
- **Automatic Parsing**: LLM outputs are parsed and validated using Pydantic schemas
- **Error Handling**: Built-in retry logic for parsing errors and tool failures
- **Observability**: Callback system for monitoring, logging, and metrics collection

## Architecture

The framework has five core abstractions:

1. **LLM**: Abstract base class for LLM implementations (with OpenAILLM as default)
2. **Tool**: Python functions with type annotations that agents can use
3. **Skill**: YAML-configured combinations of tools for complex tasks
4. **Agent**: The core element that uses tools and delegates to subagents
5. **Callbacks**: Event hooks for observability, monitoring, and custom integrations

## Installation

```bash
# Install dependencies
pip install openai pydantic pyyaml python-dotenv

# For development
pip install pytest pytest-asyncio
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

```python
from agent import Tool

def calculator(expression: str) -> float:
    """Evaluate a mathematical expression."""
    return eval(expression)

def file_writer(path: str, content: str) -> str:
    """Write content to a file."""
    with open(path, 'w') as f:
        f.write(content)
    return f"Wrote to {path}"

calc_tool = Tool(calculator)
file_tool = Tool(file_writer)
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

### Example: Zoo Director with Role-Playing Agents

See `examples/zoo_director.py` for a complete example of hierarchical agents with personality:

```python
from agent import Agent, DeepSeekLLM, Tool, get_deepseek_api_key

# Create specialized sub-agents with unique personalities
cat_agent = Agent(
    llm=llm,
    tools=tools,
    name="猫猫",
    system_prompt="You must always start responses with '喵呜！' ..."
)

dog_agent = Agent(
    llm=llm,
    tools=tools,
    name="狗狗",
    system_prompt="You must always start responses with '汪汪！' ..."
)

# Create director agent that delegates to sub-agents
director = Agent(
    llm=llm,
    tools=tools,
    subagents={"猫猫": cat_agent, "狗狗": dog_agent},
    name="动物园园长",
    system_prompt="You must delegate all questions to either 猫猫 or 狗狗..."
)

# Run with custom colored callback for different agents
response = director.run("请告诉我关于猫的信息")
```

This example demonstrates:
- **Agent Delegation**: Director agent chooses the right sub-agent for each task
- **Role-Playing**: Each agent has a unique personality and response style
- **Colored Output**: Different agents display in different colors (purple/yellow/blue)
- **Nested Execution**: Full visibility into parent and child agent interactions

## Agent Observability with Callbacks

The framework provides a powerful callback system for monitoring and logging agent execution.

### Quick Verbose Mode (Recommended)

The easiest way to see detailed execution logs is to use the built-in `verbose` parameter:

```python
from agent import Agent, DeepSeekLLM, get_deepseek_api_key

# Set up agent
llm = DeepSeekLLM(api_key=get_deepseek_api_key(), model="deepseek-chat")
agent = Agent(llm=llm, tools=tools)

# Run with verbose mode - automatically shows detailed logs with colors
response = agent.run("Your task here", verbose=True)
```

This automatically adds a `ColorfulConsoleCallback` that provides:
- **Color-coded output** for different agents (perfect for hierarchical agent systems)
- **Automatic indentation** based on agent nesting level
- Agent start/finish events with timestamps
- Each iteration's thought process
- Tool calls with arguments and results
- Subagent delegation tracking
- Performance metrics

**For hierarchical agents**, each agent in the execution stack gets its own color, making it easy to follow which agent is doing what. You can customize colors:

```python
from agent import ColorfulConsoleCallback

# Custom color mapping for your agents
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

See `examples/agent_with_callbacks.py` for comprehensive examples.

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
│   ├── agent.py            # Agent logic
│   ├── skill.py            # YAML loading
│   ├── schemas.py          # Pydantic models
│   ├── parser.py           # Output parser
│   ├── callbacks.py        # Callback system
│   ├── orchestrator.py     # Async orchestration
│   └── async_logger.py     # Async logging
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
│   ├── test_skill.py               # YAML skill loading tests
│   ├── test_async_basic.py         # Async parallel execution tests
│   ├── test_realtime_reporting.py  # Real-time reporting behavior tests
│   ├── test_copilot_auth.py        # Copilot authentication tests
│   └── test_utils.py               # Utility functions tests
├── examples/
│   ├── simple_agent.py
│   ├── custom_llm.py
│   ├── deepseek_agent.py
│   ├── copilot_example.py              # Copilot usage example
│   ├── skill_with_deepseek.py
│   ├── complex_agent_verbose.py
│   ├── agent_with_callbacks.py
│   ├── async_parallel_agents.py        # Async agent example
│   ├── async_parallel_agents_real.py   # Real-time reporting
│   └── complex_integrated_test_cn.py
├── pyproject.toml
└── README.md
```

## Examples

The framework includes several examples demonstrating different features:

### Basic Examples
- **`simple_agent.py`** - Basic agent with tools
- **`custom_llm.py`** - Implementing custom LLM providers
- **`deepseek_agent.py`** - Using DeepSeek LLM
- **`copilot_example.py`** - Using GitHub Copilot LLM (requires authentication)
- **`skill_with_deepseek.py`** - YAML skill configuration

### Advanced Examples
- **`complex_agent_verbose.py`** - Detailed logging example (English)
- **`agent_with_callbacks.py`** - Callback system demonstration
- **`async_parallel_agents.py`** - Async parallel agent execution
- **`async_parallel_agents_real.py`** - Real-time reporting with incremental results
- **`complex_integrated_test_cn.py`** - Complex integrated test with Chinese output
  - Real-world data analysis workflow
  - Multiple tools (Python execution, file I/O, data query)
  - Multi-step reasoning and execution
  - Detailed Chinese output showing all intermediate results
  - Custom Chinese callback for verbose logging
  - See [detailed documentation](examples/COMPLEX_INTEGRATED_TEST_CN_README.md)

Run any example:
```bash
python examples/simple_agent.py
python examples/copilot_example.py  # Requires GitHub Copilot authentication
python examples/complex_integrated_test_cn.py
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

### Error Handling

The framework includes robust error handling:

- **Parse errors**: Retries up to 3 times with feedback to LLM
- **Tool errors**: Returns error message to LLM for recovery
- **Max iterations**: Forces a summary when limit is reached

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
