"""
Working compaction demonstration that guarantees successful compaction.

This example creates a controlled scenario where compaction will definitely work.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.llm import CopilotLLM
from agent.config import CompactionConfig, set_compaction_config
from agent.compaction import check_and_compact
from agent.async_logger import init_logger
from agent.token_counter import SimpleTokenCounter


async def main():
    print("=" * 80)
    print("Working Compaction Test - Guaranteed Success")
    print("=" * 80)
    print()

    # Initialize logger for beautiful output
    await init_logger(log_dir="logs", console_output=True)

    # Configure VERY aggressive compaction to ensure trigger
    config = CompactionConfig(
        enabled=True,
        threshold=0.05,  # Trigger at just 5% of limit (very aggressive!)
        protect_recent_messages=2,  # Keep last 2 messages
        counter_strategy="simple",
        context_limits={
            "claude-sonnet-4.5": 5000,  # Very low limit to force trigger
            "default": 5000,
        },
    )
    set_compaction_config(config)

    trigger_at = int(config.context_limits["default"] * config.threshold)
    print(f"📋 Configuration:")
    print(f"   - Context limit: {config.context_limits['default']:,} tokens")
    print(f"   - Threshold: {config.threshold * 100}%")
    print(f"   - Will trigger at: {trigger_at:,} tokens")
    print(f"   - Protect recent: {config.protect_recent_messages} messages")
    print()

    # Create LLM
    print("🔧 Initializing CopilotLLM...")
    llm = CopilotLLM(model="claude-sonnet-4.5", timeout=180)
    print("✅ LLM ready")
    print()

    # Build a conversation history with LOTS of tokens
    # Goal: Create >250 tokens (5% of 5000) to trigger compaction
    print("📝 Building conversation history...")

    # Each message with ~300 chars = ~75 tokens
    # We'll create 10 messages = ~750 tokens (way over 250 threshold)
    llm.history = [
        {
            "role": "system",
            "content": "You are a helpful assistant that provides detailed explanations.",
        },
    ]

    # Add old messages that should be compacted
    for i in range(5):
        llm.history.append(
            {
                "role": "user",
                "content": f"Question {i + 1}: Can you explain topic {i + 1}? "
                + "This is additional context. " * 20,
            }
        )
        llm.history.append(
            {
                "role": "assistant",
                "content": f"Answer {i + 1}: Here is a detailed explanation about topic {i + 1}. "
                + "More details here. " * 20,
            }
        )

    # Add recent messages that should be protected
    llm.history.append({"role": "user", "content": "What's the final answer?"})
    llm.history.append({"role": "assistant", "content": "The final answer is 42."})

    # Count tokens
    counter = SimpleTokenCounter()
    before_tokens = counter.count_messages(llm.history, llm.model)
    before_messages = len(llm.history)

    print(f"✅ History built:")
    print(f"   - Messages: {before_messages}")
    print(f"   - Estimated tokens: {before_tokens:,}")
    print(f"   - Exceeds threshold ({trigger_at:,}): {before_tokens >= trigger_at}")
    print()

    if before_tokens < trigger_at:
        print(f"⚠️  WARNING: History doesn't exceed threshold!")
        print(f"   Need {trigger_at - before_tokens:,} more tokens")
        print()

    # Show sample of history before compaction
    print("📜 History before compaction (first 3 messages):")
    for i, msg in enumerate(llm.history[:3]):
        preview = (
            msg["content"][:60] + "..." if len(msg["content"]) > 60 else msg["content"]
        )
        print(f"   {i + 1}. [{msg['role']}] {preview}")
    print(f"   ... ({before_messages - 3} more messages)")
    print()

    # Trigger compaction
    print("🔄 Calling check_and_compact()...")
    print()

    compacted = await check_and_compact(llm, "demo_agent", config)

    print()
    print("=" * 80)

    if compacted:
        after_tokens = counter.count_messages(compacted, llm.model)
        after_messages = len(compacted)

        print("✅ COMPACTION SUCCESSFUL!")
        print("=" * 80)
        print()
        print(f"📊 Statistics:")
        print(f"   Before:")
        print(f"     - Messages: {before_messages}")
        print(f"     - Tokens: {before_tokens:,}")
        print()
        print(f"   After:")
        print(f"     - Messages: {after_messages}")
        print(f"     - Tokens: {after_tokens:,}")
        print()
        print(f"   Savings:")
        print(f"     - Messages removed: {before_messages - after_messages}")
        print(
            f"     - Tokens saved: {before_tokens - after_tokens:,} ({(before_tokens - after_tokens) / before_tokens * 100:.1f}%)"
        )
        print()
        print(f"📜 Compacted history:")
        for i, msg in enumerate(compacted):
            content_preview = (
                msg["content"][:80] + "..."
                if len(msg["content"]) > 80
                else msg["content"]
            )
            print(f"   {i + 1}. [{msg['role']}]")
            print(f"      {content_preview}")
        print()
        print("=" * 80)
        print("🎉 SUCCESS! Compaction reduced token usage effectively!")
    else:
        print("❌ COMPACTION FAILED")
        print("=" * 80)
        print()
        print(f"Possible reasons:")
        print(
            f"   1. Current tokens ({before_tokens:,}) below threshold ({trigger_at:,})"
        )
        print(f"   2. Summary generation failed")
        print(f"   3. Compacted history not smaller than original")
        print()
        print("💡 Tip: Check logs above for detailed error messages")

    print()


if __name__ == "__main__":
    asyncio.run(main())
