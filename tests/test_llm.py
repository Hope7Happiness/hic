"""
Tests for LLM functionality.

Test 1: test_llm_basic_response
- Makes a real call to Copilot API (or falls back to OpenAI/DeepSeek if token file exists)
- Verifies LLM can return text
- Verifies history is maintained correctly
"""

import os
import pytest
from agent.llm import OpenAILLM


def get_api_key():
    """
    Get API key from environment or file.

    Prioritizes Copilot (no key needed), then DeepSeek key from file, then OpenAI env variable.

    Returns:
        Tuple of (api_key, llm_type) where llm_type is "copilot", "deepseek", or "openai"
    """
    # First try Copilot (check if token file exists)
    from pathlib import Path

    copilot_token = Path.home() / ".config" / "mycopilot" / "github_token.json"
    if copilot_token.exists():
        return None, "copilot"  # No API key needed for Copilot

    # Then try reading DeepSeek API key from file (for backward compatibility with existing tests)
    key_file = "/home/zhh/看你妈呢"
    if os.path.exists(key_file):
        try:
            with open(key_file, "r") as f:
                api_key = f.read().strip()
                if api_key:
                    return api_key, "deepseek"
        except Exception:
            pass

    # Fall back to OpenAI API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return api_key, "openai"

    return None, None


def test_llm_basic_response():
    """
    Test that LLM can make a basic API call and return a response.

    This test requires either:
    - Copilot authentication (token at ~/.config/mycopilot/github_token.json)
    - DeepSeek API key in file /home/zhh/看你妈呢
    - OpenAI API key in OPENAI_API_KEY environment variable
    """
    # Check if API key is available
    api_key, llm_type = get_api_key()
    if not llm_type:
        pytest.skip("No LLM available - skipping real API test")

    # Use appropriate LLM based on what's available
    if llm_type == "copilot":
        # Use Copilot API
        from agent.llm import CopilotLLM

        llm = CopilotLLM(model="claude-haiku-4.5", temperature=0.7)
    elif llm_type == "deepseek":
        # Use DeepSeek API (for backward compatibility)
        from agent.llm import DeepSeekLLM

        assert api_key is not None, "DeepSeek requires API key"
        llm = DeepSeekLLM(
            api_key=api_key, model="deepseek-chat", base_url="https://api.deepseek.com"
        )
    else:
        # Use OpenAI API
        assert api_key is not None, "OpenAI requires API key"
        llm = OpenAILLM(model="gpt-3.5-turbo", temperature=0.7, api_key=api_key)

    # Test basic chat
    system_prompt = "You are a helpful assistant."
    response = llm.chat(
        "What is 2+2? Answer with just the number.", system_prompt=system_prompt
    )

    # Verify response exists and is a string
    assert response is not None
    assert isinstance(response, str)
    assert len(response) > 0

    # Verify history is maintained
    history = llm.get_history()
    assert len(history) == 3  # system + user + assistant
    assert history[0]["role"] == "system"
    assert history[0]["content"] == system_prompt
    assert history[1]["role"] == "user"
    assert history[1]["content"] == "What is 2+2? Answer with just the number."
    assert history[2]["role"] == "assistant"
    assert history[2]["content"] == response

    # Test follow-up message (history should be maintained)
    response2 = llm.chat("What about 3+3?")
    history2 = llm.get_history()
    assert len(history2) == 5  # system + user + assistant + user + assistant

    # Test history reset
    llm.reset_history()
    assert len(llm.get_history()) == 0


def test_llm_history_management():
    """
    Test LLM history management functions.

    This test doesn't require API key as it only tests history operations.
    """
    llm = OpenAILLM(model="gpt-3.5-turbo")

    # Initial history should be empty
    assert len(llm.get_history()) == 0

    # Manually set history
    test_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    llm.set_history(test_history)

    # Verify history was set
    history = llm.get_history()
    assert len(history) == 2
    assert history[0]["content"] == "Hello"
    assert history[1]["content"] == "Hi there!"

    # Verify get_history returns a copy
    history[0]["content"] = "Modified"
    assert llm.get_history()[0]["content"] == "Hello"

    # Test reset
    llm.reset_history()
    assert len(llm.get_history()) == 0

    # Manually set history
    test_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    llm.set_history(test_history)

    # Verify history was set
    history = llm.get_history()
    assert len(history) == 2
    assert history[0]["content"] == "Hello"
    assert history[1]["content"] == "Hi there!"

    # Verify get_history returns a copy
    history[0]["content"] = "Modified"
    assert llm.get_history()[0]["content"] == "Hello"

    # Test reset
    llm.reset_history()
    assert len(llm.get_history()) == 0
