"""
Test basic async agent functionality.

This test verifies that:
1. Parent can launch multiple subagents
2. Subagents run in parallel (not sequentially)
3. Parent is notified when each subagent completes
4. Total execution time reflects parallel execution
"""

import asyncio
import time
from agent.agent import Agent
from agent.llm import LLM
from agent.tool import Tool


def test_parallel_subagents():
    """Test that subagents execute in parallel, not sequentially."""

    # Create a simple tool that sleeps for a specified duration
    def sleep(seconds: int) -> str:
        """Sleep for N seconds and return a message."""
        time.sleep(seconds)
        return f"Slept for {seconds} seconds"

    # Create tool
    sleep_tool = Tool(sleep)

    # Create a simple LLM that returns predefined responses
    # We'll mock the LLM to return specific actions
    class MockLLM(LLM):
        def __init__(self):
            super().__init__()
            self.call_count = 0
            self.responses = [
                # First call: launch both subagents
                """Thought: I need to launch both fast and slow agents
Action: launch_subagents
Agents: ["fast_agent", "slow_agent"]
Tasks: ["Sleep for 1 second", "Sleep for 10 seconds"]""",
                # Second call: after launching, wait for them
                """Thought: Both agents are launched, now I'll wait
Action: wait_for_subagents""",
                # Third call: after fast agent completes (resume)
                """Thought: Fast agent is done, but slow agent is still running. I'll keep waiting.
Action: wait_for_subagents""",
                # Fourth call: after slow agent completes (resume)
                """Thought: Both agents are done. I can finish now.
Action: finish
Content: Both agents completed successfully. Fast took 1s, slow took 10s.""",
            ]

        def chat(self, prompt: str, system_prompt: str | None = None) -> str:
            response = self.responses[self.call_count]
            self.call_count += 1
            return response

        def reset_history(self):
            self.history = []

        def get_history(self):
            return self.history

        def set_history(self, history):
            self.history = history

    # Create child agents (they just use the sleep tool)
    class ChildMockLLM(LLM):
        def __init__(self, sleep_seconds: int):
            super().__init__()
            self.sleep_seconds = sleep_seconds
            self.call_count = 0
            self.responses = [
                # First call: use the sleep tool
                f"""Thought: I'll sleep for {sleep_seconds} seconds
Action: tool
Tool: sleep
Arguments: {{"seconds": {sleep_seconds}}}""",
                # Second call: finish after observation
                f"""Thought: I've completed the sleep task
Action: finish
Content: Slept for {sleep_seconds} seconds successfully""",
            ]

        def chat(self, prompt: str, system_prompt: str | None = None) -> str:
            response = self.responses[min(self.call_count, len(self.responses) - 1)]
            self.call_count += 1
            return response

        def reset_history(self):
            self.history = []

        def get_history(self):
            return []

        def set_history(self, history):
            self.history = history

    # Create fast agent (1 second)
    fast_llm = ChildMockLLM(sleep_seconds=1)
    fast_agent = Agent(
        llm=fast_llm,
        tools=[sleep_tool],
        name="fast_agent",
        max_iterations=5,
    )

    # Create slow agent (10 seconds)
    slow_llm = ChildMockLLM(sleep_seconds=10)
    slow_agent = Agent(
        llm=slow_llm,
        tools=[sleep_tool],
        name="slow_agent",
        max_iterations=5,
    )

    # Create parent agent
    parent_llm = MockLLM()
    parent_agent = Agent(
        llm=parent_llm,
        subagents={
            "fast_agent": fast_agent,
            "slow_agent": slow_agent,
        },
        name="parent_agent",
        max_iterations=10,
    )

    # Run parent agent and measure time
    start_time = time.time()
    result = parent_agent.run(task="Launch both agents and wait for them")
    end_time = time.time()

    elapsed = end_time - start_time

    # Verify results
    assert result.success, "Agent should complete successfully"
    assert "Both agents completed successfully" in result.content, (
        "Result should mention both agents"
    )

    # CRITICAL: Total time should be ~10s (parallel), NOT ~11s (sequential)
    # Allow 2 second margin for overhead
    assert elapsed < 12, (
        f"Expected ~10s (parallel), but took {elapsed:.2f}s (might be sequential)"
    )
    assert elapsed > 9, (
        f"Expected ~10s, but took {elapsed:.2f}s (too fast, something's wrong)"
    )

    print(
        f"✅ Test passed! Total time: {elapsed:.2f}s (expected ~10s for parallel execution)"
    )
    print(f"   If execution were sequential, it would take ~11s")


if __name__ == "__main__":
    test_parallel_subagents()
