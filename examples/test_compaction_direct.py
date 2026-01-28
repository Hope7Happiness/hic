"""
Minimal compaction demonstration that WILL trigger compaction.

This example uses a mock scenario to guarantee compaction happens.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.llm import CopilotLLM
from agent.config import CompactionConfig, set_compaction_config
from agent.compaction import check_and_compact
from agent.async_logger import init_logger


async def main():
    print("=" * 80)
    print("Direct Compaction Test")
    print("=" * 80)
    print()

    # Initialize logger
    await init_logger(log_dir="logs", console_output=True)

    # Configure very aggressive compaction
    config = CompactionConfig(
        enabled=True,
        threshold=0.1,  # Trigger at 10%
        protect_recent_messages=2,
        context_limits={"claude-sonnet-4.5": 2000, "default": 2000},
    )
    set_compaction_config(config)

    trigger_at = int(config.context_limits["default"] * config.threshold)
    print(f"Configuration:")
    print(f"  - Context limit: {config.context_limits['default']} tokens")
    print(f"  - Threshold: {config.threshold * 100}%")
    print(f"  - Will trigger at: {trigger_at} tokens")
    print(f"  - Protect recent: {config.protect_recent_messages} messages")
    print()

    # Create LLM and manually build a large history
    llm = CopilotLLM(model="claude-sonnet-4.5")

    # Build a history that will exceed the threshold
    # Each message with ~300 chars = ~75 tokens
    # We need > 200 tokens, so 5-6 messages should do it
    print("Building conversation history...")
    llm.history = [
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": "Please write a story about a robot. "
            + "The robot was very interesting and had many adventures in the digital world. "
            * 10,
        },
        {
            "role": "assistant",
            "content": "Once upon a time, there was a robot... "
            + "The robot explored many places and learned many things. " * 10,
        },
        {
            "role": "user",
            "content": "Continue the story. "
            + "Tell me more about what happened next in the story. " * 10,
        },
        {
            "role": "assistant",
            "content": "And then something happened... "
            + "The robot discovered something amazing and continued its journey. " * 10,
        },
        {"role": "user", "content": "What happened next?"},
        {"role": "assistant", "content": "The end."},
    ]

    # Count tokens
    from agent.token_counter import SimpleTokenCounter

    counter = SimpleTokenCounter()
    before_tokens = counter.count_messages(llm.history, llm.model)
    before_messages = len(llm.history)

    print(f"Current conversation:")
    print(f"  - Messages: {before_messages}")
    print(f"  - Estimated tokens: {before_tokens}")
    print(f"  - Exceeds threshold: {before_tokens >= trigger_at}")
    print()

    if before_tokens < trigger_at:
        print("⚠️  WARNING: History doesn't exceed threshold!")
        print(f"   Need {trigger_at - before_tokens} more tokens to trigger")
        print()

    # Trigger compaction
    print("Calling check_and_compact()...")
    print()

    compacted = await check_and_compact(llm, "test_agent", config)

    print()

    if compacted:
        after_tokens = counter.count_messages(compacted, llm.model)
        after_messages = len(compacted)

        print("=" * 80)
        print("Compaction Results:")
        print("=" * 80)
        print(f"Before:")
        print(f"  - Messages: {before_messages}")
        print(f"  - Tokens: {before_tokens}")
        print()
        print(f"After:")
        print(f"  - Messages: {after_messages}")
        print(f"  - Tokens: {after_tokens}")
        print()
        print(f"Savings:")
        print(f"  - Messages removed: {before_messages - after_messages}")
        print(
            f"  - Tokens saved: {before_tokens - after_tokens} ({(before_tokens - after_tokens) / before_tokens * 100:.1f}%)"
        )
        print()
        print("Compacted history:")
        for i, msg in enumerate(compacted):
            # content_preview = (
            #     msg["content"][:60] + "..."
            #     if len(msg["content"]) > 60
            #     else msg["content"]
            # )
            content_preview = msg["content"]
            print(f"  {i + 1}. [{msg['role']}] {content_preview}")
    else:
        print("❌ Compaction did not trigger or failed")
        print(f"   Current tokens: {before_tokens}")
        print(f"   Threshold: {trigger_at}")
        print(f"   Enabled: {config.enabled}")


if __name__ == "__main__":
    asyncio.run(main())
