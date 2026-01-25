"""
Tests for LLM functionality.

Test 1: test_llm_basic_response
- Makes a real call to OpenAI API (or DeepSeek API with OpenAI-compatible interface)
- Verifies LLM can return text
- Verifies history is maintained correctly
"""

import os
import pytest
from agent.llm import OpenAILLM


def get_api_key():
    """
    Get API key from environment or file.

    Prioritizes DeepSeek key from file, then falls back to OpenAI env variable.

    Returns:
        Tuple of (api_key, is_deepseek) where is_deepseek indicates if using DeepSeek API
    """
    # First try reading DeepSeek API key from file
    key_file = "/home/zhh/看你妈呢"
    if os.path.exists(key_file):
        try:
            with open(key_file, "r") as f:
                api_key = f.read().strip()
                if api_key:
                    return api_key, True  # Using DeepSeek
        except Exception:
            pass

    # Fall back to OpenAI API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        # Check if this looks like a DeepSeek key (starts with sk-)
        # If the file exists, assume the env var is also DeepSeek key
        if os.path.exists(key_file):
            return api_key, True
        return api_key, False  # Using OpenAI

    return None, False


def test_llm_basic_response():
    """
    Test that LLM can make a basic API call and return a response.

    This test requires API key to be available either:
    - In the file /home/zhh/看你妈呢 (uses DeepSeek)
    - In OPENAI_API_KEY environment variable (uses OpenAI if file doesn't exist)
    """
    # Check if API key is available
    api_key, is_deepseek = get_api_key()
    if not api_key:
        pytest.skip("API key not available - skipping real API test")

    # Use appropriate LLM based on which key we got
    if is_deepseek:
        # Use DeepSeek API
        from agent.deepseek_llm import DeepSeekLLM

        llm = DeepSeekLLM(
            api_key=api_key, model="deepseek-chat", base_url="https://api.deepseek.com"
        )
    else:
        # Use OpenAI API
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
