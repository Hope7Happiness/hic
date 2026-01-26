# GitHub Copilot API Test Client

A simple Python CLI tool to interact with GitHub Copilot's chat API using OAuth device flow authentication.

## Features

- 🔐 OAuth device flow authentication with GitHub
- 💬 Chat with GitHub Copilot models via API
- 📋 List available Copilot models
- 🚀 Simple command-line interface

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

Or using `uv`:
```bash
uv pip install -r requirements.txt
```

## Usage

### 0. Get an Auth app:

First, open https://github.com/settings/developers and go to "OAuth Apps -> New OAuth App". Create a new app, with arbitary name, and both url set to "http://localhost". Select "Enable device flow".

Then, click in this app and get the "Client ID", and copy that to the beginning of auth.py: `CLIENT_ID = "YOUR_ID"  # The ID you get from the OAuth App`

### 1. Authenticate

First, you need to authenticate with GitHub:

```bash
python cli.py auth login
```

This will:
- Display a URL and user code
- Open the URL in your browser (or copy it manually)
- Enter the user code on GitHub
- Save the access token to `~/.config/mycopilot/github_token.json`

### 2. List Available Models

View all available Copilot models:

```bash
python cli.py models
```

### 3. Chat with Copilot

Send a prompt to Copilot:

```bash
python cli.py run "Your prompt here"
```

Specify a model (optional, defaults to `claude-sonnet-4.5`):

```bash
python cli.py run "Your prompt here" claude-sonnet-4.5
```

## Examples

```bash
# Authenticate
python cli.py auth login

# List models
python cli.py models

# Simple chat
python cli.py run "Write a Python function to calculate fibonacci numbers"

# Chat with specific model
python cli.py run "Explain quantum computing" gpt-4
```

## Project Structure

- `auth.py` - OAuth device flow authentication
- `chat.py` - Copilot chat API client
- `cli.py` - Command-line interface
- `config.py` - Token storage and configuration
- `models.py` - Model listing functionality

## Configuration

Authentication tokens are stored in:
```
~/.config/mycopilot/github_token.json
```

The token file contains the OAuth access token and is created automatically after successful authentication.

## Requirements

- Python 3.7+
- `requests>=2.31.0`
- `urllib3<2.0.0`

## Notes

- The tool uses GitHub's public Copilot CLI client ID (not a secret)
- Authentication uses OAuth device flow (no client secret required)
- The token is stored locally in your home directory
- SSL warnings are disabled for LibreSSL compatibility

## Troubleshooting

**"Not logged in" error:**
- Run `python cli.py auth login` to authenticate

**Authentication fails:**
- Make sure you have an active GitHub Copilot subscription
- Check that you're entering the correct user code
- Ensure the verification URL is accessible

**API errors:**
- Verify your GitHub Copilot subscription is active
- Check that your token hasn't expired (re-authenticate if needed)
