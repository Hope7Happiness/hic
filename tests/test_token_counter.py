"""
Tests for token counter module.

This test suite covers:
1. SimpleTokenCounter - heuristic estimation
2. TiktokenCounter - accurate counting (if tiktoken installed)
3. create_counter() - factory function with fallback
4. Integration with LLM.count_tokens()
"""

import pytest
from agent.token_counter import (
    SimpleTokenCounter,
    TiktokenCounter,
    create_counter,
)


class TestSimpleTokenCounter:
    """Test SimpleTokenCounter (heuristic estimation)."""

    def test_empty_messages(self):
        """Test with empty message list."""
        counter = SimpleTokenCounter()
        assert counter.count_messages([]) == 0

    def test_single_message(self):
        """Test with a single message."""
        counter = SimpleTokenCounter()
        messages = [{"role": "user", "content": "Hello, world!"}]
        # "user" (4 chars) + "Hello, world!" (13 chars) + 20 overhead = 37 chars
        # 37 / 4 = 9 tokens (integer division)
        tokens = counter.count_messages(messages)
        assert tokens > 0
        assert tokens < 20  # Sanity check

    def test_multi_message(self):
        """Test with multiple messages."""
        counter = SimpleTokenCounter()
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France?"},
            {"role": "assistant", "content": "The capital of France is Paris."},
        ]
        tokens = counter.count_messages(messages)
        assert tokens > 0
        # Rough estimate: ~150 chars total -> ~37 tokens
        assert tokens > 20
        assert tokens < 100

    def test_count_text(self):
        """Test count_text() method."""
        counter = SimpleTokenCounter()
        text = "This is a test sentence with multiple words."
        # 46 chars / 4 = 11 tokens
        tokens = counter.count_text(text)
        assert tokens == 11

    def test_long_message(self):
        """Test with a very long message."""
        counter = SimpleTokenCounter()
        long_content = "word " * 1000  # 5000 chars
        messages = [{"role": "user", "content": long_content}]
        tokens = counter.count_messages(messages)
        # ~5000 chars / 4 = 1250 tokens (plus overhead)
        assert tokens > 1200
        assert tokens < 1300


class TestTiktokenCounter:
    """Test TiktokenCounter (accurate counting)."""

    def test_requires_tiktoken(self):
        """Test that TiktokenCounter requires tiktoken."""
        try:
            import tiktoken

            # If tiktoken is installed, this should work
            counter = TiktokenCounter()
            assert counter is not None
        except ImportError:
            # If tiktoken is not installed, this should raise ImportError
            with pytest.raises(ImportError):
                TiktokenCounter()

    def test_count_messages_accurate(self):
        """Test accurate token counting (if tiktoken available)."""
        try:
            import tiktoken
        except ImportError:
            pytest.skip("tiktoken not installed")

        counter = TiktokenCounter()
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France?"},
        ]
        tokens = counter.count_messages(messages, model="gpt-4")

        # Should be reasonably accurate
        assert tokens > 0
        assert tokens < 100

    def test_count_text_accurate(self):
        """Test accurate text counting (if tiktoken available)."""
        try:
            import tiktoken
        except ImportError:
            pytest.skip("tiktoken not installed")

        counter = TiktokenCounter()
        text = "Hello, world!"
        tokens = counter.count_text(text)

        # "Hello, world!" is typically 4 tokens in GPT-4
        assert tokens > 0
        assert tokens < 10

    def test_unknown_model_fallback(self):
        """Test fallback to default encoding for unknown models."""
        try:
            import tiktoken
        except ImportError:
            pytest.skip("tiktoken not installed")

        counter = TiktokenCounter()
        messages = [{"role": "user", "content": "test"}]

        # Should not raise error for unknown model
        tokens = counter.count_messages(messages, model="unknown-model-xyz")
        assert tokens > 0


class TestCreateCounter:
    """Test create_counter() factory function."""

    def test_create_simple(self):
        """Test creating simple counter."""
        counter = create_counter(strategy="simple")
        assert isinstance(counter, SimpleTokenCounter)

    def test_create_tiktoken(self):
        """Test creating tiktoken counter."""
        try:
            import tiktoken

            counter = create_counter(strategy="tiktoken")
            assert isinstance(counter, TiktokenCounter)
        except ImportError:
            # Should raise ImportError if tiktoken not installed
            with pytest.raises(ImportError):
                create_counter(strategy="tiktoken")

    def test_create_auto_fallback(self):
        """Test auto strategy with fallback."""
        counter = create_counter(strategy="auto")
        # Should return TiktokenCounter if available, else SimpleTokenCounter
        assert isinstance(counter, (SimpleTokenCounter, TiktokenCounter))

    def test_invalid_strategy(self):
        """Test invalid strategy raises ValueError."""
        with pytest.raises(ValueError):
            create_counter(strategy="invalid")


class TestLLMIntegration:
    """Test integration with LLM.count_tokens()."""

    def test_llm_count_tokens(self):
        """Test LLM.count_tokens() method."""
        from agent.llm import OpenAILLM

        # Create LLM (don't need real API key for this test)
        llm = OpenAILLM(model="gpt-4", api_key="dummy")

        # Add some messages to history
        llm.history = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        # Count tokens in history
        tokens = llm.count_tokens()
        assert tokens > 0
        assert tokens < 100

    def test_llm_count_custom_messages(self):
        """Test counting custom messages (not history)."""
        from agent.llm import OpenAILLM

        llm = OpenAILLM(model="gpt-4", api_key="dummy")

        custom_messages = [{"role": "user", "content": "Test message"}]

        tokens = llm.count_tokens(messages=custom_messages)
        assert tokens > 0
        assert tokens < 50


class TestCompactionConfigIntegration:
    """Test CompactionConfig integration with token counting."""

    def test_should_compact_decision(self):
        """Test compaction decision based on token count."""
        from agent.config import CompactionConfig

        config = CompactionConfig(
            enabled=True, threshold=0.75, context_limits={"gpt-4": 128_000}
        )

        # Should not compact at 50% of limit
        assert not config.should_compact(64_000, "gpt-4")

        # Should compact at 80% of limit
        assert config.should_compact(102_400, "gpt-4")

    def test_get_max_compacted_tokens(self):
        """Test max compacted tokens calculation."""
        from agent.config import CompactionConfig

        config = CompactionConfig(
            enabled=True, threshold=0.75, context_limits={"gpt-4": 128_000}
        )

        max_tokens = config.get_max_compacted_tokens("gpt-4")

        # Should be 50% of threshold (37.5% of limit)
        # 128000 * 0.75 * 0.5 = 48000
        assert max_tokens == 48_000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
