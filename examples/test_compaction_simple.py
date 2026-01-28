"""
SIMPLIFIED Compaction Test - Guaranteed to show compaction in action!

This test manually builds up history to ensure compaction triggers.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.agent import Agent
from agent.llm import CopilotLLM
from agent.config import CompactionConfig, set_compaction_config
from agent.tool import Tool
from agent.async_logger import init_logger
from agent.token_counter import SimpleTokenCounter


def simple_tool(text: str) -> str:
    """A simple tool that returns the text."""
    return f"Tool received: {text[:50]}..."


async def main():
    print("=" * 80)
    print("SIMPLIFIED Compaction Test - With Token Tracking")
    print("=" * 80)
    print()

    # Initialize logger
    await init_logger(log_dir="logs", console_output=True)

    # Very aggressive config to guarantee trigger
    config = CompactionConfig(
        enabled=True,
        threshold=0.05,  # 5% - extremely aggressive
        protect_recent_messages=1,  # Only protect last 1 message
        counter_strategy="simple",
        context_limits={
            "claude-sonnet-4.5": 1_500,  # Very low limit
            "default": 1_500,
        },
    )
    set_compaction_config(config)

    trigger_at = int(config.context_limits["default"] * config.threshold)
    print("📋 Configuration:")
    print(f"   - Context limit: {config.context_limits['default']:,} tokens")
    print(f"   - Threshold: {config.threshold * 100}%")
    print(f"   - Will trigger at: {trigger_at:,} tokens")
    print(f"   - Protect recent: {config.protect_recent_messages} messages")
    print()

    # Create LLM
    llm = CopilotLLM(model="claude-sonnet-4.5", timeout=120)
    counter = SimpleTokenCounter()
    print("✅ LLM initialized")
    print()

    # Create agent with simple tool
    tools = [Tool(simple_tool)]
    agent = Agent(
        llm=llm,
        tools=tools,
        max_iterations=10,
        system_prompt="You are a helpful assistant.",
    )

    # Task that generates multiple interactions
    task = """Please help me with this:
1. Use the simple_tool with text: "First test message to build up conversation history"
2. Use the simple_tool again with text: "Second test message to add more content to history"  
3. Use the simple_tool again with text: "Third test message continuing to build context"
4. Then summarize what you did in detail (write at least 100 words)"""

    print("🎯 Task:")
    print(task)
    print()
    print("=" * 80)
    print()

    # Track iterations
    iteration_count = [0]
    original_chat = llm.chat

    def logged_chat(prompt, system_prompt=None, max_retries=5):
        # Call original
        result = original_chat(prompt, system_prompt, max_retries)
        iteration_count[0] += 1

        # Log history size
        tokens = counter.count_messages(llm.history, llm.model)
        msgs = len(llm.history)
        exceeded = tokens >= trigger_at

        # Check compaction eligibility
        history = llm.history
        protected_count = config.protect_recent_messages
        start_idx = 1 if (history and history[0].get("role") == "system") else 0
        split_point = len(history) - protected_count
        num_old_messages = max(0, split_point - start_idx)

        print()
        print("🔍" + "=" * 59)
        print(f"   LLM CALL #{iteration_count[0]} COMPLETED")
        print("=" * 60)
        print(f"   📨 Messages: {msgs}")
        print(f"   🔢 Tokens: {tokens:,}")
        print(f"   🎯 Threshold: {trigger_at:,} ({config.threshold * 100}%)")
        print(
            f"   ⚖️  Status: {tokens:,} / {trigger_at:,} = {(tokens / trigger_at * 100):.0f}%"
        )
        print(
            f"   {'✅ EXCEEDED - Compaction should trigger!' if exceeded else '❌ Not exceeded yet'}"
        )
        print(f"   🗂️  Old messages available: {num_old_messages} (need 3+)")
        print("=" * 60)
        print()

        return result

    llm.chat = logged_chat  # type: ignore

    print("🚀 Starting agent execution...")
    print("👀 Watch for:")
    print("   - Token count after each LLM call")
    print("   - '🔄 Context compaction triggered' message")
    print("   - '✅ Compaction successful' message")
    print()
    print("=" * 80)
    print()

    # Run the agent
    response = await agent._run_async(task)

    print()
    print("=" * 80)
    print("📊 FINAL SUMMARY")
    print("=" * 80)
    print()
    print(f"✅ Agent finished: {response.success}")
    print(f"📝 Iterations: {response.iterations}")
    print(f"💬 LLM calls made: {iteration_count[0]}")
    print()

    final_tokens = counter.count_messages(llm.history, llm.model)
    final_msgs = len(llm.history)
    print(f"📈 Final History:")
    print(f"   - Messages: {final_msgs}")
    print(f"   - Tokens: {final_tokens:,}")
    print()

    print("💡 Look back in the logs above for:")
    print("   🔄 'Context compaction triggered' - Shows compaction started")
    print("   ✅ 'Compaction successful' - Shows tokens saved")
    print()

    if final_msgs < 6:
        print("🎉 History was likely compacted! (Few messages remaining)")
    else:
        print("⚠️  Compaction may not have triggered. Check logs above.")

    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
