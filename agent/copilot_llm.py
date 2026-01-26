"""
GitHub Copilot LLM implementation.

This module provides a GitHub Copilot-compatible LLM implementation
using the Copilot API with OAuth authentication.
"""

import json
import requests
from pathlib import Path
from typing import Optional
from agent.llm import LLM


class CopilotLLM(LLM):
    """
    GitHub Copilot LLM implementation.

    Uses GitHub Copilot's chat completion API. Requires OAuth authentication
    via the auth/copilot module.

    Authentication:
        Run the authentication flow first:
        ```bash
        cd auth/copilot
        python cli.py auth login
        ```

    Available models:
        - claude-sonnet-4.5 (default)
        - claude-haiku-4.5
        - gpt-4o
        - gpt-4o-mini
        - o1-preview
        - o1-mini
        And more...
    """

    COPILOT_CHAT_ENDPOINT = "https://api.githubcopilot.com/chat/completions"
    CONFIG_DIR = Path.home() / ".config" / "mycopilot"
    TOKEN_FILE = CONFIG_DIR / "github_token.json"

    def __init__(
        self,
        model: str = "claude-sonnet-4.5",
        temperature: float = 0.7,
        token_file: Optional[Path] = None,
        **kwargs,
    ):
        """
        Initialize GitHub Copilot LLM.

        Args:
            model: Copilot model name (default: claude-sonnet-4.5)
            temperature: Sampling temperature (0-2)
            token_file: Custom token file path (default: ~/.config/mycopilot/github_token.json)
            **kwargs: Additional parameters for Copilot API
        """
        super().__init__()
        self.model = model
        self.temperature = temperature
        self.config = kwargs

        # Use custom token file if provided, otherwise use default
        self.token_file = token_file or self.TOKEN_FILE

        # Load access token
        self._load_token()

    def _load_token(self):
        """Load OAuth access token from config file."""
        if not self.token_file.exists():
            raise RuntimeError(
                f"Not authenticated with GitHub Copilot.\n"
                f"Please run: cd auth/copilot && python cli.py auth login\n"
                f"Token file not found: {self.token_file}"
            )

        try:
            token_data = json.loads(self.token_file.read_text())
            self.access_token = token_data["access_token"]
        except (json.JSONDecodeError, KeyError) as e:
            raise RuntimeError(
                f"Invalid token file: {self.token_file}\n"
                f"Error: {e}\n"
                f"Please re-authenticate: cd auth/copilot && python cli.py auth login"
            )

    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Send a message and get a response from GitHub Copilot.

        Args:
            prompt: User message to send
            system_prompt: Optional system prompt (only used if history is empty)

        Returns:
            The assistant's response text
        """
        # Add system prompt if this is the first message
        if not self.history and system_prompt:
            self.history.append({"role": "system", "content": system_prompt})

        # Add user message to history
        self.history.append({"role": "user", "content": prompt})

        # Prepare API request
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Copilot-Integration-Id": "vscode-chat",
            "User-Agent": "VSCode/1.86.0 (Copilot)",
        }

        payload = {
            "model": self.model,
            "messages": self.history,
            "temperature": self.temperature,
            "stream": False,
            **self.config,
        }

        # Call Copilot API
        try:
            response = requests.post(
                self.COPILOT_CHAT_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(
                f"GitHub Copilot API request failed: {e}\n"
                f"Status: {response.status_code if hasattr(response, 'status_code') else 'N/A'}\n"
                f"Response: {response.text if hasattr(response, 'text') else 'N/A'}"
            )

        # Extract response
        try:
            data = response.json()
            assistant_message = data["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            raise RuntimeError(
                f"Failed to parse Copilot API response: {e}\nResponse: {response.text}"
            )

        # Add assistant response to history
        self.history.append({"role": "assistant", "content": assistant_message})

        return assistant_message
