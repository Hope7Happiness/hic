"""
Configuration utilities for loading API keys and environment variables.

This module provides a centralized way to load configuration from:
1. .env file (using python-dotenv)
2. Environment variables
3. Custom file paths (legacy support)
"""

import os
from typing import Optional
from pathlib import Path


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


# Auto-load .env file when module is imported
load_env()
