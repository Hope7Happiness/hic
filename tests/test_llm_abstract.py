"""
Test for LLM abstract base class and custom implementations.
"""

from agent.llm import LLM, OpenAILLM
from typing import Optional


def test_llm_is_abstract():
    """Test that LLM cannot be instantiated directly."""
    try:
        llm = LLM()
        # If we get here, the test should fail
        assert False, "LLM should not be instantiable"
    except TypeError:
        # Expected - LLM is abstract
        pass


def test_custom_llm_implementation():
    """Test creating a custom LLM implementation."""

    class MockLLM(LLM):
        """Mock LLM for testing."""

        def __init__(self, responses=None):
            super().__init__()
            self.responses = responses or []
            self.call_count = 0

        def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
            # Add system prompt if provided
            if not self.history and system_prompt:
                self.history.append({"role": "system", "content": system_prompt})

            # Add user message
            self.history.append({"role": "user", "content": prompt})

            # Get mock response
            response = (
                self.responses[self.call_count]
                if self.call_count < len(self.responses)
                else "Mock response"
            )
            self.call_count += 1

            # Add assistant message
            self.history.append({"role": "assistant", "content": response})

            return response

    # Test the mock LLM
    mock_llm = MockLLM(responses=["Response 1", "Response 2"])

    # Test first call with system prompt
    response1 = mock_llm.chat("Hello", system_prompt="You are helpful")
    assert response1 == "Response 1"
    assert len(mock_llm.get_history()) == 3  # system + user + assistant

    # Test second call
    response2 = mock_llm.chat("How are you?")
    assert response2 == "Response 2"
    assert len(mock_llm.get_history()) == 5  # previous + user + assistant

    # Test history management
    mock_llm.reset_history()
    assert len(mock_llm.get_history()) == 0


def test_openai_llm_initialization():
    """Test that OpenAILLM can be initialized with different models."""

    # Test with different models (don't call chat to avoid API calls)
    llm1 = OpenAILLM(model="gpt-3.5-turbo")
    assert llm1.model == "gpt-3.5-turbo"

    llm2 = OpenAILLM(model="gpt-4", temperature=0.5, max_tokens=1000)
    assert llm2.model == "gpt-4"
    assert llm2.temperature == 0.5
    assert llm2.max_tokens == 1000

    # Test that history is initialized
    assert len(llm1.get_history()) == 0
    assert len(llm2.get_history()) == 0


def test_llm_inheritance():
    """Test that OpenAILLM properly inherits from LLM."""

    llm = OpenAILLM(model="gpt-3.5-turbo")

    # Verify it's an instance of both OpenAILLM and LLM
    assert isinstance(llm, OpenAILLM)
    assert isinstance(llm, LLM)

    # Verify it has the required methods
    assert hasattr(llm, "chat")
    assert hasattr(llm, "reset_history")
    assert hasattr(llm, "get_history")
    assert hasattr(llm, "set_history")
