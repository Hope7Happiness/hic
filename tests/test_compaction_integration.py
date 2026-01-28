"""
Integration tests for compaction functionality.

This test suite covers:
1. CompactionDetector - detection logic
2. CompactionAgent - summarization and compaction
3. check_and_compact() - end-to-end integration
4. Agent integration - compaction during agent execution
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from agent.llm import OpenAILLM
from agent.compaction import (
    CompactionDetector,
    CompactionAgent,
    check_and_compact,
)
from agent.config import CompactionConfig


class MockLLM:
    """Mock LLM for testing without real API calls."""

    def __init__(self, model="gpt-4"):
        self.model = model
        self.history = []
        self.chat_responses = []
        self.call_count = 0

    def chat(self, prompt, system_prompt=None):
        """Mock chat method."""
        if system_prompt and not self.history:
            self.history.append({"role": "system", "content": system_prompt})

        self.history.append({"role": "user", "content": prompt})

        # Return pre-configured response
        if self.call_count < len(self.chat_responses):
            response = self.chat_responses[self.call_count]
        else:
            response = "Mock summary of conversation"

        self.history.append({"role": "assistant", "content": response})
        self.call_count += 1

        return response

    def get_history(self):
        """Get conversation history."""
        import copy

        return copy.deepcopy(self.history)

    def set_history(self, history):
        """Set conversation history."""
        import copy

        self.history = copy.deepcopy(history)

    def reset_history(self):
        """Reset history."""
        self.history = []

    def count_tokens(self, messages=None):
        """Mock token counting."""
        from agent.token_counter import SimpleTokenCounter

        counter = SimpleTokenCounter()
        msgs = messages if messages is not None else self.history
        return counter.count_messages(msgs, self.model)


class TestCompactionDetector:
    """Test CompactionDetector."""

    def test_detector_should_not_compact_below_threshold(self):
        """Test that detector doesn't trigger below threshold."""
        llm = MockLLM(model="gpt-4")
        llm.history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        config = CompactionConfig(
            enabled=True, threshold=0.75, context_limits={"gpt-4": 128_000}
        )

        detector = CompactionDetector(llm, config)
        should_compact, current, threshold = detector.should_compact()

        assert not should_compact
        assert current < threshold

    def test_detector_should_compact_above_threshold(self):
        """Test that detector triggers above threshold."""
        llm = MockLLM(model="gpt-4")

        # Create large history (simulate 100k tokens)
        # Need at least 3 old messages after protecting recent, plus 1 protected = 4+ messages
        llm.history = [
            {"role": "user", "content": "x" * 100_000},  # ~25k tokens
            {"role": "assistant", "content": "y" * 100_000},  # ~25k tokens
            {"role": "user", "content": "z" * 100_000},  # ~25k tokens
            {"role": "assistant", "content": "w" * 100_000},  # ~25k tokens
            {"role": "user", "content": "Last"},  # Recent message to protect
        ]

        config = CompactionConfig(
            enabled=True,
            threshold=0.75,
            protect_recent_messages=1,  # Explicitly set
            context_limits={"gpt-4": 128_000},
        )

        detector = CompactionDetector(llm, config)
        should_compact, current, threshold = detector.should_compact()

        # With ~100k tokens, should trigger (threshold is 96k)
        assert should_compact
        assert current >= threshold

    def test_detector_disabled_never_compacts(self):
        """Test that disabled detector never triggers."""
        llm = MockLLM(model="gpt-4")
        llm.history = [{"role": "user", "content": "x" * 500_000}]

        config = CompactionConfig(enabled=False)
        detector = CompactionDetector(llm, config)
        should_compact, _, _ = detector.should_compact()

        assert not should_compact

    def test_get_compaction_info(self):
        """Test compaction info retrieval."""
        llm = MockLLM(model="gpt-4")
        llm.history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        config = CompactionConfig()
        detector = CompactionDetector(llm, config)
        info = detector.get_compaction_info()

        assert "enabled" in info
        assert "model" in info
        assert "current_tokens" in info
        assert "threshold_tokens" in info
        assert "should_compact" in info
        assert info["model"] == "gpt-4"


class TestCompactionAgent:
    """Test CompactionAgent."""

    @pytest.mark.asyncio
    async def test_compact_history_basic(self):
        """Test basic history compaction."""
        llm = MockLLM(model="gpt-4")
        llm.chat_responses = ["Summary: User asked questions, assistant answered."]

        history = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
            {"role": "user", "content": "What is 3+3?"},
            {"role": "assistant", "content": "6"},
            {"role": "user", "content": "What is 4+4?"},
            {"role": "assistant", "content": "8"},
        ]

        config = CompactionConfig(
            enabled=True,
            protect_recent_messages=2,  # Protect last 2 messages
        )

        compactor = CompactionAgent(llm, config)
        compacted = await compactor.compact_history(history)

        assert compacted is not None
        assert len(compacted) < len(history)

        # Should have: system + summary + recent (2 messages)
        assert len(compacted) == 4

        # First message should be original system
        assert compacted[0] == history[0]

        # Second message should be summary
        assert compacted[1]["role"] == "system"
        assert "summary" in compacted[1]["content"].lower()

        # Last 2 messages should be preserved
        assert compacted[2] == history[-2]
        assert compacted[3] == history[-1]

    @pytest.mark.asyncio
    async def test_compact_history_no_system(self):
        """Test compaction without system message."""
        llm = MockLLM(model="gpt-4")
        llm.chat_responses = ["Summary of conversation"]

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "Good"},
            {"role": "user", "content": "Bye"},
        ]

        config = CompactionConfig(protect_recent_messages=1)
        compactor = CompactionAgent(llm, config)
        compacted = await compactor.compact_history(history)

        assert compacted is not None
        # Should have: summary + recent (1 message)
        assert len(compacted) == 2
        assert compacted[0]["role"] == "system"
        assert compacted[1] == history[-1]

    @pytest.mark.asyncio
    async def test_compact_history_too_short(self):
        """Test that short history is not compacted."""
        llm = MockLLM(model="gpt-4")

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        config = CompactionConfig(protect_recent_messages=2)
        compactor = CompactionAgent(llm, config)
        compacted = await compactor.compact_history(history)

        # Should return original history unchanged
        assert compacted == history

    @pytest.mark.asyncio
    async def test_validate_compacted_history(self):
        """Test validation of compacted history."""
        llm = MockLLM(model="gpt-4")

        original = [
            {"role": "user", "content": "x" * 1000},
            {"role": "assistant", "content": "y" * 1000},
            {"role": "user", "content": "z" * 1000},
        ]

        compacted = [
            {"role": "system", "content": "Summary: conversation about xyz"},
            {"role": "user", "content": "z" * 1000},
        ]

        compactor = CompactionAgent(llm)
        is_valid = compactor.validate_compacted_history(original, compacted)

        # Compacted should have fewer tokens
        assert is_valid


class TestCheckAndCompact:
    """Test check_and_compact() integration function."""

    @pytest.mark.asyncio
    async def test_no_compaction_when_disabled(self):
        """Test that compaction doesn't run when disabled."""
        llm = MockLLM(model="gpt-4")
        llm.history = [{"role": "user", "content": "x" * 1_000_000}]

        config = CompactionConfig(enabled=False)
        result = await check_and_compact(llm, "test_agent", config)

        assert result is None

    @pytest.mark.asyncio
    async def test_no_compaction_below_threshold(self):
        """Test no compaction below threshold."""
        llm = MockLLM(model="gpt-4")
        llm.history = [{"role": "user", "content": "Hello"}]

        config = CompactionConfig(enabled=True, threshold=0.75)
        result = await check_and_compact(llm, "test_agent", config)

        assert result is None

    @pytest.mark.asyncio
    async def test_compaction_triggered_above_threshold(self):
        """Test compaction triggers above threshold."""
        llm = MockLLM(model="gpt-4")
        llm.chat_responses = ["Summary of large conversation"]

        # Create large history
        llm.history = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "a" * 100_000},
            {"role": "assistant", "content": "b" * 100_000},
            {"role": "user", "content": "c" * 100_000},
            {"role": "assistant", "content": "d" * 100_000},
            {"role": "user", "content": "Last message"},
        ]

        config = CompactionConfig(
            enabled=True,
            threshold=0.75,
            protect_recent_messages=1,
            context_limits={"gpt-4": 128_000},
        )

        result = await check_and_compact(llm, "test_agent", config)

        # Should return compacted history
        assert result is not None
        assert len(result) < len(llm.history)

        # Last message should be preserved
        assert result[-1] == llm.history[-1]


class TestAgentIntegration:
    """Test compaction integration with Agent."""

    @pytest.mark.asyncio
    async def test_check_and_compact_in_isolation(self):
        """Test check_and_compact works without full agent."""
        llm = MockLLM(model="gpt-4")
        llm.chat_responses = ["Short summary"]

        # Create large history that exceeds threshold
        # With 200k chars each, this is ~50k tokens per message (200k / 4)
        # Need at least 3 old messages + 1 protected = 4+ messages (after system)
        llm.history = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "a" * 200_000},
            {"role": "assistant", "content": "b" * 200_000},
            {"role": "user", "content": "c" * 200_000},
            {"role": "assistant", "content": "d" * 200_000},
            {"role": "user", "content": "Last"},
        ]

        config = CompactionConfig(
            enabled=True,
            threshold=0.50,  # Trigger at 50% of limit
            protect_recent_messages=1,
            context_limits={"gpt-4": 100_000},  # Lower limit to force trigger
        )

        result = await check_and_compact(llm, "test_agent", config)

        # Should successfully compact
        assert result is not None
        assert len(result) < len(llm.history)

    @pytest.mark.asyncio
    async def test_compaction_doesnt_break_agent(self):
        """Test that compaction can be called during agent execution without crashing."""
        # This is a simpler test that just verifies compaction can work
        # with agent-like history without running a full agent loop
        llm = MockLLM(model="gpt-4")
        llm.chat_responses = ["Summary of agent execution"]

        # Simulate agent history with actions and thoughts
        # Need at least 3 old messages + 2 protected = 5+ messages (with system = 6 total)
        llm.history = [
            {"role": "system", "content": "You are a helpful agent."},
            {"role": "user", "content": "Task: " + "x" * 50_000},
            {"role": "assistant", "content": "Thought: I will help. Action: tool_name"},
            {"role": "user", "content": "Result: success"},
            {"role": "assistant", "content": "Thought: Continue"},
            {"role": "user", "content": "More results"},
            {"role": "assistant", "content": "Final result"},
        ]

        config = CompactionConfig(
            enabled=True,
            threshold=0.1,  # Low threshold to trigger
            protect_recent_messages=2,
            context_limits={"gpt-4": 100_000},
        )

        # This should compact without errors
        result = await check_and_compact(llm, "test_agent", config)

        # Should successfully compact
        assert result is not None
        assert len(result) < len(llm.history)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
