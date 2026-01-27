"""
Tests for GitHub Copilot authentication and basic functionality.

This test verifies that:
1. Copilot authentication is configured correctly
2. The access token can be loaded
3. A simple API call succeeds
4. Response format is correct
"""

import pytest
from pathlib import Path
from agent.llm import CopilotLLM


def test_copilot_token_file_exists():
    """
    Test that the Copilot token file exists.

    This test checks if authentication has been completed.
    If it fails, run: cd auth/copilot && python cli.py auth login
    """
    token_file = Path.home() / ".config" / "mycopilot" / "github_token.json"

    if not token_file.exists():
        pytest.skip(
            f"Copilot not authenticated. Token file not found: {token_file}\n"
            f"To authenticate, run: cd auth/copilot && python cli.py auth login"
        )

    assert token_file.exists(), "Token file should exist after authentication"


def test_copilot_llm_initialization():
    """
    Test that CopilotLLM can be initialized successfully.

    This verifies:
    - Token file exists and is readable
    - Token has the correct format
    - LLM object is created without errors
    """
    token_file = Path.home() / ".config" / "mycopilot" / "github_token.json"

    if not token_file.exists():
        pytest.skip(
            f"Copilot not authenticated. Run: cd auth/copilot && python cli.py auth login"
        )

    # Should not raise any exceptions
    llm = CopilotLLM(model="claude-haiku-4.5", temperature=0.7)

    assert llm is not None
    assert llm.model == "claude-haiku-4.5"
    assert llm.temperature == 0.7
    assert hasattr(llm, "access_token")
    assert len(llm.access_token) > 0


def test_copilot_simple_question():
    """
    Test Copilot authentication by asking a simple question.

    This is the main authentication test. It:
    1. Creates a CopilotLLM instance
    2. Asks a simple math question
    3. Verifies the response is valid

    If this test passes, Copilot authentication is working correctly.
    """
    token_file = Path.home() / ".config" / "mycopilot" / "github_token.json"

    if not token_file.exists():
        pytest.skip(
            f"Copilot not authenticated. Run: cd auth/copilot && python cli.py auth login"
        )

    # Create Copilot LLM instance
    llm = CopilotLLM(model="claude-haiku-4.5", temperature=0.7)

    # Ask a simple question
    response = llm.chat(
        "What is 2+2? Answer with just the number, nothing else.",
        system_prompt="You are a helpful assistant that answers questions concisely.",
    )

    # Verify response
    assert response is not None, "Response should not be None"
    assert isinstance(response, str), "Response should be a string"
    assert len(response) > 0, "Response should not be empty"

    # The response should contain "4" somewhere
    assert "4" in response, f"Response should contain '4', got: {response}"

    print(f"✅ Copilot authentication successful! Response: {response}")


def test_copilot_history_management():
    """
    Test that Copilot LLM maintains conversation history correctly.
    """
    token_file = Path.home() / ".config" / "mycopilot" / "github_token.json"

    if not token_file.exists():
        pytest.skip(
            f"Copilot not authenticated. Run: cd auth/copilot && python cli.py auth login"
        )

    llm = CopilotLLM(model="claude-haiku-4.5")

    # Initial history should be empty
    assert len(llm.get_history()) == 0

    # First message with system prompt
    response1 = llm.chat("What is 2+2?", system_prompt="You are a helpful assistant.")

    # History should have: system + user + assistant
    history = llm.get_history()
    assert len(history) == 3
    assert history[0]["role"] == "system"
    assert history[1]["role"] == "user"
    assert history[1]["content"] == "What is 2+2?"
    assert history[2]["role"] == "assistant"
    assert history[2]["content"] == response1

    # Follow-up message
    response2 = llm.chat("What about 3+3?")

    # History should have 5 messages now
    history2 = llm.get_history()
    assert len(history2) == 5
    assert history2[3]["role"] == "user"
    assert history2[4]["role"] == "assistant"

    # Test reset
    llm.reset_history()
    assert len(llm.get_history()) == 0


def test_copilot_different_models():
    """
    Test that different Copilot models can be initialized.

    Note: This only tests initialization, not actual API calls with all models.
    """
    token_file = Path.home() / ".config" / "mycopilot" / "github_token.json"

    if not token_file.exists():
        pytest.skip(
            f"Copilot not authenticated. Run: cd auth/copilot && python cli.py auth login"
        )

    # Test various model names
    models = [
        "claude-haiku-4.5",
        "claude-sonnet-4.5",
        "gpt-4o",
        "gpt-4o-mini",
    ]

    for model in models:
        llm = CopilotLLM(model=model)
        assert llm.model == model
        print(f"✅ Successfully initialized CopilotLLM with model: {model}")


def test_copilot_custom_token_file():
    """
    Test that CopilotLLM can use a custom token file path.
    """
    default_token_file = Path.home() / ".config" / "mycopilot" / "github_token.json"

    if not default_token_file.exists():
        pytest.skip(
            f"Copilot not authenticated. Run: cd auth/copilot && python cli.py auth login"
        )

    # Create LLM with custom token file path (using the default path for testing)
    llm = CopilotLLM(model="claude-haiku-4.5", token_file=default_token_file)

    assert llm.token_file == default_token_file
    assert hasattr(llm, "access_token")
    assert len(llm.access_token) > 0


def test_copilot_error_handling_no_token():
    """
    Test that CopilotLLM raises appropriate error when token file is missing.
    """
    non_existent_token = Path("/tmp/nonexistent_copilot_token.json")

    with pytest.raises(RuntimeError) as exc_info:
        CopilotLLM(model="claude-haiku-4.5", token_file=non_existent_token)

    assert "Not authenticated" in str(exc_info.value)
    assert "Token file not found" in str(exc_info.value)


if __name__ == "__main__":
    # Allow running tests directly for quick verification
    print("Testing Copilot authentication...")
    print("\n1. Checking token file...")
    test_copilot_token_file_exists()
    print("✅ Token file exists\n")

    print("2. Testing LLM initialization...")
    test_copilot_llm_initialization()
    print("✅ LLM initialized successfully\n")

    print("3. Testing simple question...")
    test_copilot_simple_question()
    print("✅ Simple question test passed\n")

    print("4. Testing history management...")
    test_copilot_history_management()
    print("✅ History management test passed\n")

    print("5. Testing different models...")
    test_copilot_different_models()
    print("✅ Different models test passed\n")

    print("🎉 All Copilot authentication tests passed!")
