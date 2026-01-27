# AI Assistant Instructions: GitHub Copilot Setup

> **For AI Assistants**: This document provides step-by-step instructions for helping a user set up GitHub Copilot authentication for use with the LLM Agent Framework.

## Your Task

Help the user authenticate with GitHub Copilot and integrate it into the agent framework. Follow these steps sequentially.

---

## Step 1: Verify Prerequisites

Before starting, check with the user:

```bash
# Verify they have GitHub Copilot subscription
# Ask: "Do you have an active GitHub Copilot subscription?"

# Check if dependencies are installed
cd /home/zhh/Documents/Github/hic
source .venv/bin/activate
python -c "import requests; print('✅ requests installed')"
```

**If `requests` is not installed:**
```bash
pip install requests urllib3
# or: uv pip install requests urllib3
```

---

## Step 2: Create GitHub OAuth App

**Guide the user through OAuth App creation:**

1. **Navigate**: Ask user to visit https://github.com/settings/developers
2. **Create**: Click "OAuth Apps" → "New OAuth App"
3. **Configure**:
   - **Application name**: Any name (e.g., "My Copilot Agent")
   - **Homepage URL**: `http://localhost`
   - **Authorization callback URL**: `http://localhost`
4. **Enable Device Flow**: ⚠️ **CRITICAL** - Check "Enable device flow" checkbox
5. **Register**: Click "Register application"
6. **Copy Client ID**: Save the Client ID shown on the page

---

## Step 3: Configure Client ID

**Edit the auth.py file with the Client ID:**

```bash
# Read the current file
cat auth/copilot/auth.py | head -10
```

**Update CLIENT_ID:**

```python
# Use the Edit tool to replace:
# OLD: CLIENT_ID = "YOUR_ID"
# NEW: CLIENT_ID = "<actual_client_id_from_github>"
```

**Example Edit:**
```python
# In auth/copilot/auth.py, line 7
CLIENT_ID = "Iv1.a1b2c3d4e5f6g7h8"  # User's actual Client ID
```

---

## Step 4: Run Authentication Flow

**Execute the authentication:**

```bash
cd auth/copilot
python cli.py auth login
```

**What happens:**
1. CLI displays a URL (e.g., `https://github.com/login/device`)
2. CLI displays a user code (e.g., `ABCD-1234`)
3. Browser opens automatically (or user can manually visit the URL)
4. User enters the code on GitHub
5. User authorizes the application
6. Token is saved to `~/.config/mycopilot/github_token.json`

**Guide the user:**
- "Please follow the URL displayed in your terminal"
- "Enter the user code when prompted"
- "Click 'Authorize' to grant access"

---

## Step 5: Verify Authentication

**Test the setup:**

```bash
# List available models
python cli.py models

# Expected output:
# Available models:
# - claude-sonnet-4.5
# - claude-haiku-4.5
# - gpt-4o
# - gpt-4o-mini
# - o1-preview
# - o1-mini
```

**Test a simple chat:**

```bash
python cli.py run "Hello, what's 2+2?" claude-haiku-4.5
```

**Run unit tests (RECOMMENDED):**

```bash
cd /home/zhh/Documents/Github/hic
pytest tests/test_copilot_auth.py -v

# Or run directly for detailed output:
python tests/test_copilot_auth.py
```

**Expected test output:**
```
Testing Copilot authentication...
1. Checking token file...
✅ Token file exists
2. Testing LLM initialization...
✅ LLM initialized successfully
3. Testing simple question...
✅ Copilot authentication successful! Response: 4
✅ Simple question test passed
4. Testing history management...
✅ History management test passed
5. Testing different models...
✅ Successfully initialized CopilotLLM with model: claude-haiku-4.5
...
🎉 All Copilot authentication tests passed!
```

**If authentication fails:**
- Check that `~/.config/mycopilot/github_token.json` exists
- Verify the user has an active Copilot subscription
- Ensure OAuth App has "Enable device flow" checked
- Try re-running `python cli.py auth login`

---

## Step 6: Test with Agent Framework

**Run the example:**

```bash
cd /home/zhh/Documents/Github/hic
python examples/copilot_example.py
```

**Expected output:**
```
🚀 Agent started with task: Calculate 25 * 4 and tell me the result
🤔 Thought: I need to use the calculator tool...
🔧 Calling calculator({'expression': '25 * 4'})
✓ calculator → 100.0
✅ Finished: The result of 25 * 4 is 100.0
```

**If errors occur:**
- `FileNotFoundError: github_token.json` → Re-run authentication (Step 4)
- `401 Unauthorized` → Check Copilot subscription is active
- `ImportError` → Install dependencies: `pip install requests urllib3`

---

## Step 7: Integration in User's Code

**Show the user how to use Copilot in their own code:**

```python
from agent.agent import Agent
from agent.llm import CopilotLLM
from agent.tool import Tool

# Create Copilot LLM instance
llm = CopilotLLM(
    model="claude-haiku-4.5",  # Fast and cost-effective
    # model="claude-sonnet-4.5",  # Balanced performance
    # model="gpt-4o",  # Latest GPT-4
    temperature=0.7,
)

# Create agent with your tools
agent = Agent(
    llm=llm,
    tools=[your_tools_here],
    name="MyAgent",
    system_prompt="You are a helpful assistant.",
)

# Run agent
result = agent.run("Your task here")
print(result)
```

**Custom token location (optional):**

```python
from pathlib import Path

llm = CopilotLLM(
    model="claude-haiku-4.5",
    token_file=Path("/custom/path/to/token.json"),
)
```

---

## Available Models

**Guide the user on model selection:**

| Model | Speed | Cost | Use Case |
|-------|-------|------|----------|
| `claude-haiku-4.5` | ⚡⚡⚡ Fast | 💰 Cheap | Quick tasks, high volume |
| `claude-sonnet-4.5` | ⚡⚡ Medium | 💰💰 Medium | Balanced (recommended) |
| `gpt-4o` | ⚡⚡ Medium | 💰💰 Medium | Latest GPT-4 features |
| `gpt-4o-mini` | ⚡⚡⚡ Fast | 💰 Cheap | Smaller GPT-4 |
| `o1-preview` | ⚡ Slow | 💰💰💰 Expensive | Advanced reasoning |
| `o1-mini` | ⚡⚡ Medium | 💰💰 Medium | Compact reasoning |

**List all available models:**
```bash
cd auth/copilot
python cli.py models
```

---

## Troubleshooting Guide

### Error: "Not logged in"

**Diagnosis:**
```bash
ls ~/.config/mycopilot/github_token.json
# If file doesn't exist → Need to authenticate
```

**Solution:**
```bash
cd auth/copilot
python cli.py auth login
```

---

### Error: "401 Unauthorized"

**Possible causes:**
1. Token expired → Re-authenticate
2. No Copilot subscription → Verify at https://github.com/settings/copilot
3. Invalid Client ID → Check `auth/copilot/auth.py`

**Solution:**
```bash
# Re-authenticate
python cli.py auth login

# Test immediately
python cli.py models
```

---

### Error: "OAuth App not found"

**Diagnosis:**
- Client ID is incorrect in `auth/copilot/auth.py`
- OAuth App was deleted from GitHub

**Solution:**
1. Go to https://github.com/settings/developers
2. Verify OAuth App exists
3. Copy the correct Client ID
4. Update `auth/copilot/auth.py` with correct Client ID
5. Re-run authentication

---

### Error: "Device flow not enabled"

**Diagnosis:**
- OAuth App doesn't have "Enable device flow" checked

**Solution:**
1. Go to https://github.com/settings/developers
2. Click on your OAuth App
3. Scroll to "Device Flow" section
4. ✅ Check "Enable device flow"
5. Click "Update application"
6. Re-run authentication

---

## Quick Commands Reference

```bash
# Navigate to project
cd /home/zhh/Documents/Github/hic
source .venv/bin/activate

# Authenticate (first time)
cd auth/copilot
python cli.py auth login

# List available models
python cli.py models

# Test CLI chat
python cli.py run "Your prompt" claude-haiku-4.5

# Run authentication tests (RECOMMENDED)
cd /home/zhh/Documents/Github/hic
pytest tests/test_copilot_auth.py -v
# Or: python tests/test_copilot_auth.py

# Test agent example
cd /home/zhh/Documents/Github/hic
python examples/copilot_example.py

# Check token file
cat ~/.config/mycopilot/github_token.json
```

---

## Success Criteria

**Authentication is successful when:**

1. ✅ `python cli.py models` shows list of models
2. ✅ `python cli.py run "hello" claude-haiku-4.5` returns a response
3. ✅ `pytest tests/test_copilot_auth.py -v` all tests pass (BEST verification!)
4. ✅ `python examples/copilot_example.py` runs without errors
5. ✅ `~/.config/mycopilot/github_token.json` exists

**User is ready to use Copilot when:**

1. ✅ They can create `CopilotLLM()` instances without errors
2. ✅ They can run agents with Copilot models
3. ✅ All unit tests pass (`python tests/test_copilot_auth.py`)
4. ✅ They understand how to choose appropriate models
5. ✅ They know where to find documentation (`auth/copilot/README.md`)

---

## Additional Resources

**For the user:**
- Detailed setup guide: `auth/copilot/README.md`
- Working example: `examples/copilot_example.py`
- Main README: Section "Using Different LLM Models" → "GitHub Copilot Models"
- GitHub Copilot docs: https://docs.github.com/copilot

**For debugging:**
- Log files: `logs/` directory
- Token location: `~/.config/mycopilot/github_token.json`
- OAuth Apps: https://github.com/settings/developers

---

## Notes for AI Assistants

1. **Always verify prerequisites first** - Don't skip dependency checks
2. **Guide through OAuth App creation carefully** - The "Enable device flow" checkbox is critical
3. **Test after each major step** - Don't wait until the end to discover issues
4. **Be patient with OAuth flow** - Users may need time to navigate GitHub UI
5. **Provide clear error messages** - If something fails, diagnose before suggesting solutions
6. **Suggest appropriate models** - `claude-haiku-4.5` for speed, `claude-sonnet-4.5` for balance
7. **Use code examples** - Show working code, not just instructions
8. **Document custom configurations** - If user needs non-default settings, add comments

---

## End Goal

After following this guide, the user should be able to:

```python
# Write code like this without any errors:
from agent import Agent, CopilotLLM, Tool

llm = CopilotLLM(model="claude-haiku-4.5")
agent = Agent(llm=llm, tools=[my_tools])
result = agent.run("My task")
print(result)  # ✅ Works!
```

**That's success!** 🎉
