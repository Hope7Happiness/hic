# GitHub Copilot API Authentication & Integration

Authentication module for using GitHub Copilot with the agent framework. Provides OAuth device flow authentication and token management.

## Features

- 🔐 OAuth device flow authentication with GitHub
- 💬 Chat with GitHub Copilot models via API
- 📋 List available Copilot models
- 🤖 **Integrated with agent framework via `CopilotLLM`**
- 🚀 Simple command-line interface

## Quick Start

### 1. Setup OAuth App

First, create a GitHub OAuth App:

1. Go to https://github.com/settings/developers
2. Click "OAuth Apps" → "New OAuth App"
3. Fill in:
   - **Application name**: Any name (e.g., "My Copilot CLI")
   - **Homepage URL**: `http://localhost`
   - **Authorization callback URL**: `http://localhost`
4. **Enable device flow** (important!)
5. Click "Register application"
6. Copy the **Client ID**
7. Edit `auth.py` and replace `CLIENT_ID = "YOUR_ID"` with your Client ID

### 2. Authenticate

Run the authentication flow:

```bash
cd auth/copilot
python cli.py auth login
```

This will:
- Display a URL and user code
- Open the URL in your browser (or copy it manually)
- Prompt you to enter the user code on GitHub
- Save the access token to `~/.config/mycopilot/github_token.json`

### 3. Test Authentication

List available models to verify authentication:

```bash
python cli.py models
```

Test a simple chat:

```bash
python cli.py run "Hello" claude-haiku-4.5
```

Run unit tests (recommended for comprehensive verification):

```bash
cd ../..  # Go back to project root
pytest tests/test_copilot_auth.py -v
# Or run directly: python tests/test_copilot_auth.py
```

## Using with Agent Framework

Once authenticated, you can use `CopilotLLM` in your agent code:

```python
from agent.agent import Agent
from agent.copilot_llm import CopilotLLM
from agent.tool import Tool

# Create Copilot LLM
llm = CopilotLLM(
    model="claude-haiku-4.5",  # or claude-sonnet-4.5, gpt-4o, etc.
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

**Example:** See `examples/copilot_example.py` for a complete working example.

## Available Models

Common models available through GitHub Copilot:

- **Claude Models**:
  - `claude-sonnet-4.5` - Balanced performance (default)
  - `claude-haiku-4.5` - Fast and cost-effective
  
- **GPT Models**:
  - `gpt-4o` - Latest GPT-4 optimized
  - `gpt-4o-mini` - Smaller, faster GPT-4
  
- **O1 Models**:
  - `o1-preview` - Advanced reasoning
  - `o1-mini` - Compact reasoning model

Run `python cli.py models` to see all available models.

## CLI Usage

### Authenticate
```bash
python cli.py auth login
```

### List Models
```bash
python cli.py models
```

### Chat with Copilot
```bash
python cli.py run "Your prompt here" [model]
```

Examples:
```bash
# Default model (claude-sonnet-4.5)
python cli.py run "Write a Python function to calculate fibonacci"

# Specify model
python cli.py run "Explain quantum computing" claude-haiku-4.5
python cli.py run "Debug this code: ..." gpt-4o
```

## Project Structure

- `auth.py` - OAuth device flow authentication
- `chat.py` - Copilot chat API client
- `cli.py` - Command-line interface
- `config.py` - Token storage and configuration
- `models.py` - Model listing functionality

## Configuration

**Token Storage:**
```
~/.config/mycopilot/github_token.json
```

The token file contains the OAuth access token and is created automatically after successful authentication.

**Custom Token Location:**

You can specify a custom token file in your code:

```python
from pathlib import Path

llm = CopilotLLM(
    model="claude-haiku-4.5",
    token_file=Path("/custom/path/to/token.json"),
)
```

## Requirements

- Python 3.9+
- `requests>=2.31.0`
- `urllib3<2.0.0`
- Active GitHub Copilot subscription

## Troubleshooting

**"Not logged in" error:**
- Run `python cli.py auth login` to authenticate
- Check that `~/.config/mycopilot/github_token.json` exists

**Authentication fails:**
- Make sure you have an active GitHub Copilot subscription
- Check that you're entering the correct user code
- Ensure the verification URL is accessible
- Verify your OAuth App has "Enable device flow" checked

**API errors:**
- Verify your GitHub Copilot subscription is active
- Check that your token hasn't expired (re-authenticate if needed)
- Try listing models to test connectivity: `python cli.py models`

**Import errors:**
- Make sure you've installed the main project: `pip install -e .`
- Check that `requests` is installed: `pip install requests`

## Notes

- Authentication uses OAuth device flow (no client secret required)
- The token is stored locally in your home directory
- SSL warnings are disabled for LibreSSL compatibility
- The integration automatically handles token loading and API communication

