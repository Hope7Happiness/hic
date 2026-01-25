"""
DeepSeek LLM implementation.

This module provides a DeepSeek-compatible LLM implementation.
"""

import json
from typing import Optional
from openai import OpenAI
from agent.llm import LLM


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

    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Send a message and get a response from DeepSeek.

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

        # Call DeepSeek API
        response = self.client.chat.completions.create(
            model=self.model, messages=self.history, stream=False, **self.config
        )

        # Extract response text
        assistant_message = response.choices[0].message.content

        # Add assistant response to history
        self.history.append({"role": "assistant", "content": assistant_message})

        return assistant_message
