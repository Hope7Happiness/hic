"""
Token counting utilities for context management.

This module provides token counting functionality to support compaction:
1. SimpleTokenCounter - Fast heuristic estimation (chars / 4)
2. TiktokenCounter - Accurate token counting using tiktoken (optional)
3. create_counter() - Factory function with fallback logic

Design principles:
- Fast and efficient for frequent checks
- Graceful fallback when tiktoken is unavailable
- Compatible with OpenAI, DeepSeek, and Copilot models
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class TokenCounter(ABC):
    """
    Abstract base class for token counting.

    All implementations must provide:
    - count_messages(): Count tokens in a message list
    - count_text(): Count tokens in a single text string
    """

    @abstractmethod
    def count_messages(
        self, messages: List[Dict[str, str]], model: str = "gpt-4"
    ) -> int:
        """
        Count tokens in a list of messages.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            model: Model name (for model-specific token counting)

        Returns:
            Estimated token count
        """
        pass

    @abstractmethod
    def count_text(self, text: str) -> int:
        """
        Count tokens in a single text string.

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        pass


class SimpleTokenCounter(TokenCounter):
    """
    Fast token counter using heuristic estimation.

    Estimation method: chars / 4
    - Fast and efficient
    - Model-agnostic
    - Reasonable accuracy for English text (~25% error margin)

    This is the default counter when tiktoken is unavailable.
    """

    def count_messages(
        self, messages: List[Dict[str, str]], model: str = "gpt-4"
    ) -> int:
        """
        Count tokens in a list of messages using chars/4 heuristic.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            model: Model name (ignored, but kept for interface compatibility)

        Returns:
            Estimated token count
        """
        total_chars = 0

        for message in messages:
            # Count role (usually "user", "assistant", "system")
            total_chars += len(message.get("role", ""))

            # Count content
            total_chars += len(message.get("content", ""))

            # Add overhead for message formatting (rough estimate)
            # OpenAI format adds: {"role": "...", "content": "..."}
            total_chars += 20  # ~20 chars overhead per message

        # Convert chars to tokens using 4:1 ratio
        return total_chars // 4

    def count_text(self, text: str) -> int:
        """
        Count tokens in a single text string using chars/4 heuristic.

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        return len(text) // 4


class TiktokenCounter(TokenCounter):
    """
    Accurate token counter using tiktoken library.

    This counter provides accurate token counts for:
    - OpenAI models (gpt-4, gpt-3.5-turbo, etc.)
    - DeepSeek models (compatible with OpenAI tokenizer)
    - Claude models (approximate, uses cl100k_base)

    Note: Requires tiktoken to be installed (optional dependency).
    """

    def __init__(self):
        """
        Initialize tiktoken counter.

        Raises:
            ImportError: If tiktoken is not installed
        """
        try:
            import tiktoken

            self.tiktoken = tiktoken

            # Pre-load common encodings
            self._encodings = {}

        except ImportError:
            raise ImportError(
                "tiktoken is not installed. Install it with: pip install tiktoken\n"
                "Or use SimpleTokenCounter for heuristic estimation."
            )

    def _get_encoding(self, model: str):
        """
        Get tiktoken encoding for a model.

        Args:
            model: Model name

        Returns:
            tiktoken Encoding object
        """
        # Check cache first
        if model in self._encodings:
            return self._encodings[model]

        try:
            # Try to get encoding by model name
            encoding = self.tiktoken.encoding_for_model(model)
        except KeyError:
            # Model not recognized - use default encoding
            # cl100k_base is used by gpt-4, gpt-3.5-turbo, and text-embedding-ada-002
            encoding = self.tiktoken.get_encoding("cl100k_base")

        # Cache and return
        self._encodings[model] = encoding
        return encoding

    def count_messages(
        self, messages: List[Dict[str, str]], model: str = "gpt-4"
    ) -> int:
        """
        Count tokens in a list of messages using tiktoken.

        This follows OpenAI's official token counting logic:
        https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            model: Model name

        Returns:
            Accurate token count
        """
        encoding = self._get_encoding(model)

        # Determine tokens per message and per name based on model
        if model.startswith("gpt-3.5-turbo"):
            tokens_per_message = (
                4  # Every message follows <|start|>{role/name}\n{content}<|end|>\n
            )
            tokens_per_name = -1  # If there's a name, the role is omitted
        elif model.startswith("gpt-4"):
            tokens_per_message = 3
            tokens_per_name = 1
        else:
            # Default to gpt-3.5-turbo behavior for unknown models
            tokens_per_message = 4
            tokens_per_name = -1

        num_tokens = 0

        for message in messages:
            num_tokens += tokens_per_message

            for key, value in message.items():
                num_tokens += len(encoding.encode(value))

                if key == "name":
                    num_tokens += tokens_per_name

        # Every reply is primed with <|start|>assistant<|message|>
        num_tokens += 3

        return num_tokens

    def count_text(self, text: str) -> int:
        """
        Count tokens in a single text string using tiktoken.

        Args:
            text: Input text

        Returns:
            Accurate token count
        """
        # Use cl100k_base encoding for general text
        encoding = self._get_encoding("gpt-4")
        return len(encoding.encode(text))


def create_counter(strategy: str = "simple") -> TokenCounter:
    """
    Create a token counter with the specified strategy.

    Args:
        strategy: Counter strategy:
            - "simple": Fast heuristic (chars/4)
            - "tiktoken": Accurate counting with tiktoken
            - "auto": Try tiktoken, fallback to simple

    Returns:
        TokenCounter instance

    Raises:
        ValueError: If strategy is invalid
        ImportError: If tiktoken is requested but not installed
    """
    if strategy == "simple":
        return SimpleTokenCounter()

    elif strategy == "tiktoken":
        return TiktokenCounter()

    elif strategy == "auto":
        # Try tiktoken first, fallback to simple
        try:
            return TiktokenCounter()
        except ImportError:
            return SimpleTokenCounter()

    else:
        raise ValueError(
            f"Invalid token counter strategy: {strategy}\n"
            f"Valid options: 'simple', 'tiktoken', 'auto'"
        )
