"""
Configuration utilities for loading API keys and environment variables.

This module provides a centralized way to load configuration from:
1. .env file (using python-dotenv)
2. Environment variables
3. Custom file paths (legacy support)
4. Compaction configuration
"""

import os
from typing import Optional
from pathlib import Path
from dataclasses import dataclass, field


def load_env():
    """
    Load environment variables from .env file if it exists.

    This function should be called at the start of your application.
    """
    try:
        from dotenv import load_dotenv

        # Look for .env file in current directory and parent directories
        env_path = Path(".env")
        if env_path.exists():
            load_dotenv(env_path)
            return True

        # Try project root
        project_root = Path(__file__).parent.parent
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            return True

        return False
    except ImportError:
        # python-dotenv not installed, skip
        return False


def get_api_key(
    provider: str = "deepseek", custom_path: Optional[str] = None
) -> Optional[str]:
    """
    Get API key for the specified provider.

    Priority order:
    1. Custom file path (if provided)
    2. Environment variable
    3. Legacy file location (for backward compatibility)

    Args:
        provider: LLM provider name ("openai", "deepseek")
        custom_path: Optional custom file path to read API key from

    Returns:
        API key string or None if not found
    """
    provider = provider.lower()

    # 1. Try custom file path first
    if custom_path and os.path.exists(custom_path):
        try:
            with open(custom_path, "r") as f:
                key = f.read().strip()
                if key:
                    return key
        except Exception:
            pass

    # 2. Try environment variable
    env_var_map = {
        "openai": "OPENAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
    }

    env_var = env_var_map.get(provider)
    if env_var:
        key = os.environ.get(env_var)
        if key:
            return key

    # 3. Legacy support: try default file location
    legacy_path = "/home/zhh/看你妈呢"
    if provider == "deepseek" and os.path.exists(legacy_path):
        try:
            with open(legacy_path, "r") as f:
                key = f.read().strip()
                if key:
                    return key
        except Exception:
            pass

    return None


def get_openai_api_key(custom_path: Optional[str] = None) -> Optional[str]:
    """
    Get OpenAI API key.

    Args:
        custom_path: Optional custom file path to read API key from

    Returns:
        API key string or None if not found
    """
    return get_api_key("openai", custom_path)


def get_deepseek_api_key(custom_path: Optional[str] = None) -> Optional[str]:
    """
    Get DeepSeek API key.

    Args:
        custom_path: Optional custom file path to read API key from

    Returns:
        API key string or None if not found
    """
    return get_api_key("deepseek", custom_path)


def check_api_keys() -> dict:
    """
    Check which API keys are available.

    Returns:
        Dictionary with provider names as keys and boolean availability as values
    """
    return {
        "openai": get_openai_api_key() is not None,
        "deepseek": get_deepseek_api_key() is not None,
    }


# ============================================================================
# Compaction Configuration
# ============================================================================


@dataclass
class CompactionConfig:
    """
    Configuration for context compaction.

    Compaction is triggered when the conversation history grows too large,
    preventing context overflow errors. It summarizes older messages while
    preserving recent context.

    Attributes:
        enabled: Enable/disable compaction (default: True)
        threshold: Trigger compaction at this ratio of context limit (default: 0.75)
        protect_recent_messages: Number of recent messages to preserve (default: 2)
        reserved_output_tokens: Tokens reserved for LLM output (default: 2000)
        counter_strategy: Token counter strategy - "simple", "tiktoken", or "auto" (default: "simple")
        debug_log: Enable compaction debug logs (default: False)
        context_limits: Model-specific context limits (default: see below)

    Default context limits:
        - gpt-4: 128,000 tokens
        - gpt-3.5-turbo: 16,384 tokens
        - deepseek-chat: 128,000 tokens
        - claude-sonnet-4.5: 200,000 tokens
        - claude-haiku-4.5: 200,000 tokens
        - o1-preview: 128,000 tokens
        - o1-mini: 128,000 tokens
        - default: 100,000 tokens (fallback)

    Example:
        >>> config = CompactionConfig(enabled=True, threshold=0.75)
        >>> config.get_context_limit("gpt-4")  # Returns 128000
        >>> config.should_compact(100000, "gpt-4")  # Returns True if > 96000 tokens
    """

    enabled: bool = True
    threshold: float = 0.75
    protect_recent_messages: int = 2
    reserved_output_tokens: int = 2000
    counter_strategy: str = "simple"
    debug_log: bool = False

    # Model-specific context limits (in tokens)
    context_limits: dict = field(
        default_factory=lambda: {
            # OpenAI models
            "gpt-4": 128_000,
            "gpt-4o": 128_000,
            "gpt-4o-mini": 128_000,
            "gpt-3.5-turbo": 16_384,
            "o1-preview": 128_000,
            "o1-mini": 128_000,
            # DeepSeek models
            "deepseek-chat": 128_000,
            # Claude models (via Copilot)
            "claude-sonnet-4.5": 200_000,
            "claude-haiku-4.5": 200_000,
            # Default fallback
            "default": 100_000,
        }
    )

    def get_context_limit(self, model: str) -> int:
        """
        Get context limit for a specific model.

        Args:
            model: Model name (e.g., "gpt-4", "claude-sonnet-4.5")

        Returns:
            Context limit in tokens
        """
        # Try exact match first
        if model in self.context_limits:
            return self.context_limits[model]

        # Try prefix match (e.g., "gpt-4-0125-preview" -> "gpt-4")
        for key in self.context_limits:
            if model.startswith(key):
                return self.context_limits[key]

        # Return default
        return self.context_limits["default"]

    def should_compact(self, current_tokens: int, model: str) -> bool:
        """
        Check if compaction should be triggered.

        Args:
            current_tokens: Current token count in history
            model: Model name

        Returns:
            True if compaction should be triggered
        """
        if not self.enabled:
            return False

        limit = self.get_context_limit(model)
        threshold_tokens = int(limit * self.threshold)

        return current_tokens >= threshold_tokens

    def get_max_compacted_tokens(self, model: str) -> int:
        """
        Get maximum tokens after compaction.

        This ensures compacted history stays well below the threshold
        to avoid repeated compaction cycles.

        Args:
            model: Model name

        Returns:
            Maximum tokens for compacted history
        """
        limit = self.get_context_limit(model)
        # Target 50% of threshold (or 37.5% of total limit)
        return int(limit * self.threshold * 0.5)


# Global compaction config instance
_compaction_config: Optional[CompactionConfig] = None


def get_compaction_config() -> CompactionConfig:
    """
    Get the global compaction configuration.

    Returns:
        CompactionConfig instance (creates default if not set)
    """
    global _compaction_config
    if _compaction_config is None:
        _compaction_config = CompactionConfig()
    return _compaction_config


def set_compaction_config(config: CompactionConfig):
    """
    Set the global compaction configuration.

    Args:
        config: CompactionConfig instance
    """
    global _compaction_config
    _compaction_config = config


def reset_compaction_config():
    """
    Reset compaction configuration to default.
    """
    global _compaction_config
    _compaction_config = CompactionConfig()


# Auto-load .env file when module is imported
load_env()
