"""
LLM wrapper for chat completion.

This module provides:
1. LLM abstract base class - defines the interface for all LLM implementations
2. OpenAILLM - concrete implementation using OpenAI API
3. Conversation history management
"""

import os
import copy
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from openai import OpenAI


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
