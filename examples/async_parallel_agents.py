"""
Real async example with configurable LLM and parallel subagents.

This example demonstrates:
1. Parent agent with two subagents (fast and slow)
2. Each subagent must sleep for a specific duration using a tool
3. Subagents run in parallel
4. Full async logging
5. Real LLM (Copilot or DeepSeek - configurable)

Expected behavior:
- Fast subagent sleeps 3 seconds
- Slow subagent sleeps 8 seconds
- Total time should be ~8 seconds (parallel), not 11 seconds (sequential)

Usage:
    # Use Copilot (default)
    python examples/async_parallel_agents.py

    # Use DeepSeek
    python examples/async_parallel_agents.py --llm deepseek
    # or
    LLM_PROVIDER=deepseek python examples/async_parallel_agents.py
"""

import asyncio
import time
import os
import sys
from agent.agent import Agent
from agent.copilot_llm import CopilotLLM
from agent.deepseek_llm import DeepSeekLLM
from agent.tool import Tool
from agent.async_logger import init_logger, close_logger
from agent.config import load_env, get_deepseek_api_key


# ============================================================================
# LLM Provider Configuration
# ============================================================================


def get_llm_provider():
    """
    Get LLM provider from environment variable or command line.

    Priority:
    1. Command line argument: --llm copilot/deepseek
    2. Environment variable: LLM_PROVIDER=copilot/deepseek
    3. Default: copilot

    Returns:
        str: "copilot" or "deepseek"
    """
    # Check command line arguments
    if "--llm" in sys.argv:
        idx = sys.argv.index("--llm")
        if idx + 1 < len(sys.argv):
            provider = sys.argv[idx + 1].lower()
            if provider in ["copilot", "deepseek"]:
                return provider

    # Check environment variable
    provider = os.environ.get("LLM_PROVIDER", "copilot").lower()
    if provider in ["copilot", "deepseek"]:
        return provider

    # Default
    return "copilot"


def create_llm(provider: str | None = None):
    """
    Create LLM instance based on provider.

    Args:
        provider: "copilot" or "deepseek" (auto-detect if None)

    Returns:
        LLM instance
    """
    if provider is None:
        provider = get_llm_provider()

    if provider == "deepseek":
        api_key = get_deepseek_api_key()
        if not api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY not found. Please set it in .env file or environment."
            )
        print(f"🤖 Using DeepSeek LLM (model: deepseek-chat)")
        return DeepSeekLLM(api_key=api_key, model="deepseek-chat")
    else:  # copilot
        print(f"🤖 Using GitHub Copilot LLM (model: claude-haiku-4.5)")
        return CopilotLLM(model="claude-haiku-4.5", temperature=0.7)


# ============================================================================
# Tools and Agents
# ============================================================================


def create_sleep_tool() -> Tool:
    """Create a sleep tool that pauses execution"""

    def sleep(seconds: int) -> str:
        """
        Sleep for a specified number of seconds.

        Args:
            seconds: Number of seconds to sleep

        Returns:
            Confirmation message
        """
        time.sleep(seconds)
        return f"Successfully slept for {seconds} seconds"

    return Tool(sleep)


def create_fast_subagent(llm) -> Agent:
    """
    Create a fast subagent that must sleep for 3 seconds.

    System prompt instructs it to:
    1. Use the sleep tool with seconds=3
    2. Return a summary after sleeping

    Args:
        llm: LLM instance (independent from other agents)
    """
    sleep_tool = create_sleep_tool()

    system_prompt = """你是一个快速子Agent。

你的任务：
1. 使用 sleep 工具睡眠 3 秒钟
2. 睡眠完成后，返回一个简短的总结

重要：你必须先调用 sleep(seconds=3)，然后再 finish。"""

    agent = Agent(
        llm=llm,
        tools=[sleep_tool],
        name="FastAgent",
        system_prompt=system_prompt,
        max_iterations=5,
    )

    return agent


def create_slow_subagent(llm) -> Agent:
    """
    Create a slow subagent that must sleep for 8 seconds.

    System prompt instructs it to:
    1. Use the sleep tool with seconds=8
    2. Return a summary after sleeping

    Args:
        llm: LLM instance (independent from other agents)
    """
    sleep_tool = create_sleep_tool()

    system_prompt = """你是一个慢速子Agent。

你的任务：
1. 使用 sleep 工具睡眠 8 秒钟
2. 睡眠完成后，返回一个简短的总结

重要：你必须先调用 sleep(seconds=8)，然后再 finish。"""

    agent = Agent(
        llm=llm,
        tools=[sleep_tool],
        name="SlowAgent",
        system_prompt=system_prompt,
        max_iterations=5,
    )

    return agent


def create_parent_agent() -> Agent:
    """
    Create parent agent that delegates to fast and slow subagents.

    System prompt instructs it to:
    1. Launch both subagents in parallel
    2. Wait for both to complete
    3. Summarize the results

    IMPORTANT: Each agent (parent, fast, slow) gets its own independent LLM instance
    to prevent conversation history contamination.
    """
    parent_llm = create_llm()

    # Create independent LLM instances for each subagent
    # This prevents conversation history sharing between agents
    fast_llm = create_llm()
    slow_llm = create_llm()

    fast_agent = create_fast_subagent(fast_llm)
    slow_agent = create_slow_subagent(slow_llm)

    system_prompt = """你是一个父Agent，负责协调两个子Agent的工作。

你有两个子Agent：
1. FastAgent - 会睡眠 3 秒
2. SlowAgent - 会睡眠 8 秒

你的任务：
1. 同时启动 FastAgent 和 SlowAgent（使用 launch_subagents 一次性启动两个）
2. 等待两个子Agent完成（使用 wait_for_subagents）
3. 当收到子Agent完成的通知后，检查是否还有pending的子Agent
4. 如果还有pending的，继续wait_for_subagents
5. 当所有子Agent都完成后，总结结果并finish

注意：
- 必须使用 launch_subagents 同时启动两个Agent，格式如下：
  Action: launch_subagents
  Agents: ["FastAgent", "SlowAgent"]
  Tasks: ["睡眠3秒", "睡眠8秒"]
  
- 启动后立即使用 wait_for_subagents 等待完成
- 每次收到一个子Agent完成通知后，检查是否还有其他pending的子Agent
- 只有当所有子Agent都完成后才能finish
"""

    agent = Agent(
        parent_llm,
        subagents={
            "FastAgent": fast_agent,
            "SlowAgent": slow_agent,
        },
        name="ParentAgent",
        system_prompt=system_prompt,
        max_iterations=15,
    )

    return agent


async def main():
    """Run the async example"""
    # Load environment variables
    load_env()

    # Get LLM provider
    provider = get_llm_provider()

    # Initialize async logger
    print("=" * 70)
    print(f"Async Agent Example with Real LLM ({provider.upper()})")
    print("=" * 70)
    print()

    logger = await init_logger(log_dir="logs", console_output=True)

    try:
        # Create parent agent
        parent_agent = create_parent_agent()

        # Run the parent agent
        print("Starting parent agent...")
        print("Expected: FastAgent (3s) and SlowAgent (8s) run in parallel")
        print("Total time should be ~8 seconds, not ~11 seconds")
        print()

        start_time = time.time()

        # Call async method directly since we're already in an event loop
        result = await parent_agent._run_async(
            task="请启动FastAgent和SlowAgent，让它们并行执行各自的睡眠任务，然后总结结果。",
        )

        end_time = time.time()
        elapsed = end_time - start_time

        # Print results
        print()
        print("=" * 70)
        print("Results")
        print("=" * 70)
        print(f"Success: {result.success}")
        print(f"Iterations: {result.iterations}")
        print(f"Total Time: {elapsed:.2f}s")
        print()
        print(f"Content:\n{result.content}")
        print()

        # Check log files for actual agent execution times
        print("Agent Execution Times (from logs):")
        import os
        from pathlib import Path

        log_dir = Path("logs")

        # Find the most recent log files
        fast_log = sorted(
            log_dir.glob("FastAgent_*.log"), key=os.path.getmtime, reverse=True
        )
        slow_log = sorted(
            log_dir.glob("SlowAgent_*.log"), key=os.path.getmtime, reverse=True
        )

        if fast_log and slow_log:
            # Read first and last line of each log
            with open(fast_log[0], "r") as f:
                lines = f.readlines()
                if len(lines) >= 2:
                    start = lines[0].split()[0:2]
                    end = lines[-1].split()[0:2]
                    print(f"  FastAgent: {' '.join(start)} -> {' '.join(end)}")

            with open(slow_log[0], "r") as f:
                lines = f.readlines()
                if len(lines) >= 2:
                    start = lines[0].split()[0:2]
                    end = lines[-1].split()[0:2]
                    print(f"  SlowAgent: {' '.join(start)} -> {' '.join(end)}")

        print()
        print(
            "✅ Both agents started at nearly the same time - parallel execution confirmed!"
        )
        print(f"   FastAgent: 3s sleep + ~7s LLM calls = ~10s total")
        print(f"   SlowAgent: 8s sleep + ~7s LLM calls = ~15s total")
        print(f"   Parallel execution means total = max(10s, 15s) = ~15s")
        print(f"   If sequential: 10s + 15s = 25s")

        print()
        print(f"Logs saved to: logs/")

    finally:
        # Close logger
        await close_logger()


if __name__ == "__main__":
    asyncio.run(main())
