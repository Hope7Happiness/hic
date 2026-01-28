"""
LLM wrapper for chat completion.

This module provides:
1. LLM abstract base class - defines the interface for all LLM implementations
2. OpenAILLM - concrete implementation using OpenAI API
3. Conversation history management
"""

import os
import copy
import time
import subprocess
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from openai import OpenAI
import requests
from pathlib import Path
import json


class LLM(ABC):
    """
    Abstract base class for LLM implementations.

    All LLM implementations must:
    - Maintain conversation history
    - Implement the chat() method for generating responses
    - Support system prompts
    """

    def __init__(self):
        """Initialize the LLM with empty history."""
        self.history: List[Dict[str, str]] = []

    @abstractmethod
    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Send a message and get a response.

        Args:
            prompt: User message to send
            system_prompt: Optional system prompt (only used if history is empty)

        Returns:
            The assistant's response text
        """
        pass

    def reset_history(self):
        """Clear the conversation history."""
        self.history = []

    def get_history(self) -> List[Dict[str, str]]:
        """Get a copy of the conversation history."""
        return copy.deepcopy(self.history)

    def set_history(self, history: List[Dict[str, str]]):
        """Set the conversation history."""
        self.history = copy.deepcopy(history)

    def count_tokens(self, messages: Optional[List[Dict[str, str]]] = None) -> int:
        """
        Count tokens in messages using the token counter.

        Args:
            messages: Messages to count (defaults to current history)

        Returns:
            Token count

        Note:
            Uses SimpleTokenCounter by default. Subclasses can override
            to use model-specific counting (e.g., tiktoken).
        """
        from agent.token_counter import SimpleTokenCounter

        counter = SimpleTokenCounter()
        messages_to_count = messages if messages is not None else self.history
        model = getattr(self, "model", "gpt-4")

        return counter.count_messages(messages_to_count, model)


class OpenAILLM(LLM):
    """
    OpenAI implementation of LLM.

    This is the primary implementation that uses OpenAI's chat completion API.
    It maintains conversation history and provides a simple chat interface.
    """

    def __init__(
        self,
        model: str = "gpt-4",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ):
        """
        Initialize the OpenAI LLM.

        Args:
            model: OpenAI model name (e.g., "gpt-4", "gpt-3.5-turbo")
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters for OpenAI API
        """
        super().__init__()
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.config = kwargs

        # Initialize OpenAI client
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key)

    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Send a message and get a response from OpenAI.

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

        # Call OpenAI API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.history,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **self.config,
        )

        # Extract response text
        assistant_message = response.choices[0].message.content

        # Add assistant response to history
        self.history.append({"role": "assistant", "content": assistant_message})

        return assistant_message


class DeepSeekLLM(LLM):
    """
    DeepSeek LLM implementation.

    Compatible with DeepSeek API (and other OpenAI-compatible APIs).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
        **kwargs,
    ):
        """
        Initialize DeepSeek LLM.

        Args:
            api_key: DeepSeek API key
            model: Model name (default: deepseek-chat)
            base_url: API base URL
            **kwargs: Additional parameters for the API (e.g., temperature, max_tokens)
        """
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        # Only store valid API parameters (not initialization parameters)
        self.config = kwargs

    def chat(
        self, prompt: str, system_prompt: Optional[str] = None, max_retries: int = 5
    ) -> str:
        """
        Send a message and get a response from DeepSeek.

        Args:
            prompt: User message to send
            system_prompt: Optional system prompt (only used if history is empty)
            max_retries: Maximum number of retries for rate limit errors (default: 5)

        Returns:
            The assistant's response text

        Raises:
            RuntimeError: If the request fails after all retries
        """
        # Add system prompt if this is the first message
        if not self.history and system_prompt:
            self.history.append({"role": "system", "content": system_prompt})

        # Add user message to history
        self.history.append({"role": "user", "content": prompt})

        # Call DeepSeek API with retry logic
        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model, messages=self.history, stream=False, **self.config
                )

                # Extract response text
                assistant_message = response.choices[0].message.content

                # Add assistant response to history
                self.history.append({"role": "assistant", "content": assistant_message})

                return assistant_message

            except Exception as e:
                last_error = e

                # Check if this is a rate limit error
                error_str = str(e).lower()
                if (
                    "429" in error_str
                    or "rate limit" in error_str
                    or "too many requests" in error_str
                ):
                    # Rate limit error - retry with exponential backoff
                    if attempt < max_retries - 1:
                        wait_time = 2**attempt  # 1s, 2s, 4s, 8s, 16s
                        print(
                            f"⚠️  Rate limit hit. Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        # Last attempt failed
                        raise RuntimeError(
                            f"DeepSeek API rate limit exceeded after {max_retries} retries: {e}"
                        )
                else:
                    # Non-rate-limit error - fail immediately
                    raise RuntimeError(f"DeepSeek API request failed: {e}")

        # Should not reach here, but just in case
        raise RuntimeError(
            f"DeepSeek API request failed after {max_retries} retries: {last_error}"
        )


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
        timeout: int = 60,
        token_file: Optional[Path] = None,
        **kwargs,
    ):
        """
        Initialize GitHub Copilot LLM.

        Args:
            model: Copilot model name (default: claude-sonnet-4.5)
            temperature: Sampling temperature (0-2)
            timeout: Request timeout in seconds (default: 60)
            token_file: Custom token file path (default: ~/.config/mycopilot/github_token.json)
            **kwargs: Additional parameters for Copilot API
        """
        super().__init__()
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
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

    def chat(
        self, prompt: str, system_prompt: Optional[str] = None, max_retries: int = 5
    ) -> str:
        """
        Send a message and get a response from GitHub Copilot.

        Args:
            prompt: User message to send
            system_prompt: Optional system prompt (only used if history is empty)
            max_retries: Maximum number of retries for rate limit errors (default: 5)

        Returns:
            The assistant's response text

        Raises:
            RuntimeError: If the request fails after all retries
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

        # Call Copilot API with retry logic
        last_error = None
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.COPILOT_CHAT_ENDPOINT,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()

                # Success - extract and return response
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

            except requests.exceptions.RequestException as e:
                last_error = e

                # Check if this is a timeout error
                is_timeout = isinstance(
                    e, (requests.exceptions.Timeout, requests.exceptions.ReadTimeout)
                )

                # Check if this is a rate limit error (429)
                is_rate_limit = False
                if hasattr(e, "response") and e.response is not None:
                    status_code = e.response.status_code
                    is_rate_limit = status_code == 429

                # Retry on timeout or rate limit
                if is_timeout or is_rate_limit:
                    if attempt < max_retries - 1:
                        wait_time = 2**attempt  # 1s, 2s, 4s, 8s, 16s
                        error_type = "Timeout" if is_timeout else "Rate limit (429)"
                        print(
                            f"⚠️  {error_type} hit. Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        # Last attempt failed
                        if is_timeout:
                            raise RuntimeError(
                                f"GitHub Copilot API request timed out after {max_retries} retries.\n"
                                f"Timeout: {self.timeout}s\n"
                                f"Consider increasing timeout for long-running tasks."
                            )
                        else:
                            raise RuntimeError(
                                f"GitHub Copilot API rate limit exceeded after {max_retries} retries.\n"
                                f"Status: 429\n"
                                f"Response: {e.response.text if hasattr(e.response, 'text') else 'N/A'}"
                            )

                # Non-retryable error - fail immediately
                if hasattr(e, "response") and e.response is not None:
                    raise RuntimeError(
                        f"GitHub Copilot API request failed: {e}\n"
                        f"Status: {e.response.status_code}\n"
                        f"Response: {e.response.text if hasattr(e.response, 'text') else 'N/A'}"
                    )
                else:
                    # No response object - fail immediately
                    raise RuntimeError(
                        f"GitHub Copilot API request failed: {e}\nNo response received"
                    )

        # Should not reach here, but just in case
        raise RuntimeError(
            f"GitHub Copilot API request failed after {max_retries} retries: {last_error}"
        )

class CodexLLM(LLM):
    """
    Codex LLM implementation that talks to the **Codex CLI** (`codex exec`),
    not directly to the OpenAI Platform API.

    This matches the desired workflow:

    - 你在终端里先 `codex login`（或在 CI 里用 `CODEX_API_KEY`）
    - Python 这边只调用 `codex exec`，完全复用 Codex 的认证与订阅配额

    这样就不会再走 `openai.RateLimitError: insufficient_quota` 的 Platform 额度，
    而是使用 Codex CLI 自己的计费与限流。
    """

    def __init__(
        self,
        model: str = "gpt-5.2",
        *,
        token: Optional[str] = None,  # 保留参数以兼容旧调用，不再使用
        token_env_vars: Optional[list[str]] = None,  # 同上
        token_command: Optional[list[str]] = None,  # 同上
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ):
        """
        Initialize CodexLLM.

        Args:
            model: Codex CLI 使用的模型名，对应 `codex --model` 选项。
            token, token_env_vars, token_command:
                为了兼容旧代码而保留，但当前基于 Codex CLI，不再使用这些参数。
            temperature, max_tokens, **kwargs:
                目前不直接映射到 Codex CLI 选项，只保存在实例上备用。
        """
        super().__init__()
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.config = kwargs

    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Send a message and get a response using the Codex CLI (`codex exec`).

        为了更接近 Codex 交互式 CLI 的体验，这里使用：

            codex exec --json --model <model> "<prompt>"

        然后从 JSONL 事件流中提取**最后一条 assistant 文本消息**，
        避免把内部日志、工具调用等噪音混进回复里。

        注意：由于 codex exec 每次调用都是独立进程，为了支持多轮对话，
        我们会把完整的 history 格式化成一个长 prompt 一起传给 Codex。
        """
        # 维护本地对话历史
        if not self.history and system_prompt:
            self.history.append({"role": "system", "content": system_prompt})

        self.history.append({"role": "user", "content": prompt})

        # 把完整 history 格式化成一个 prompt，让 Codex 能理解上下文
        # 这样多轮对话时 Codex 也能知道之前发生了什么
        def _format_history_as_prompt(history: List[Dict[str, str]]) -> str:
            parts = []
            for msg in history:
                role = msg["role"]
                content = msg["content"]
                if role == "system":
                    parts.append(f"[System]\n{content}")
                elif role == "user":
                    parts.append(f"[User]\n{content}")
                elif role == "assistant":
                    parts.append(f"[Assistant]\n{content}")
                elif role == "tool":
                    parts.append(f"[Tool Result]\n{content}")
            return "\n\n".join(parts)

        cli_prompt = _format_history_as_prompt(self.history)

        cmd = ["codex", "exec", "--json"]
        if self.model:
            cmd += ["--model", self.model]
        cmd.append(cli_prompt)

        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,  # hard cap to avoid hanging indefinitely
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                "Codex CLI not found. Please ensure `codex` is installed and in PATH."
            ) from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                "Codex CLI call timed out after 120 seconds. "
                "The task may be too complex or waiting on approvals; "
                "try simplifying the prompt or running Codex directly to debug."
            ) from e
        except Exception as e:
            raise RuntimeError(f"Failed to invoke Codex CLI: {e}") from e

        if result.returncode != 0:
            raise RuntimeError(
                f"Codex CLI returned non-zero exit code {result.returncode}.\n"
                f"Command: {' '.join(cmd)}\n"
                f"stderr:\n{result.stderr}"
            )

        # 解析 JSONL，尽量找到“最后一条 assistant 文本消息”
        def _extract_last_assistant_text(jsonl: str) -> str:
            last_text = ""
            if not jsonl:
                return last_text

            for line in jsonl.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except Exception:
                    continue

                if not isinstance(evt, dict):
                    continue

                # Codex CLI 实际格式：
                # {"type": "item.completed", "item": {"type": "agent_message", "text": "..."}}
                if evt.get("type") == "item.completed":
                    item = evt.get("item")
                    if isinstance(item, dict) and item.get("type") == "agent_message":
                        text = item.get("text")
                        if isinstance(text, str) and text.strip():
                            last_text = text.strip()

                # 兼容其他可能的格式
                # {"type": "...", "message": {"role": "assistant", "content": "..."}}
                msg = evt.get("message")
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    content = msg.get("content")
                    if isinstance(content, str) and content.strip():
                        last_text = content.strip()

                # {"type": "assistant_message", "content": "..."}
                if evt.get("type") in ("assistant_message", "message"):
                    content = evt.get("content")
                    if isinstance(content, str) and content.strip():
                        last_text = content.strip()

            return last_text

        assistant_message = _extract_last_assistant_text(result.stdout)
        if not assistant_message:
            assistant_message = "[Codex returned empty response]"

        self.history.append({"role": "assistant", "content": assistant_message})
        return assistant_message

