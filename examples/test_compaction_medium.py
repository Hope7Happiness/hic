"""
Medium complexity compaction test with real agent task.
WITH DETAILED TOKEN LOGGING to track compaction behavior.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.agent import Agent
from agent.llm import CopilotLLM, DeepSeekLLM
from agent.config import CompactionConfig, set_compaction_config
from agent.tool import Tool
from agent.async_logger import init_logger
from agent.token_counter import SimpleTokenCounter


def save_text(filename: str, content: str) -> str:
    """Save text to a file."""
    path = Path("examples/output") / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return f"✅ Saved to {path}"


async def main():
    print("=" * 80)
    print("Medium Complexity Compaction Test")
    print("=" * 80)
    print()

    # Initialize logger
    await init_logger(log_dir="logs", console_output=True)

    # Configure aggressive compaction
    config = CompactionConfig(
        enabled=True,
        threshold=0.50,
        protect_recent_messages=2,
        counter_strategy="simple",
        context_limits={
            "claude-sonnet-4.5": 2_000,  # Very low to force trigger
            "deepseek-chat": 2_000,
            "default": 2_000,
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

    # Create LLM with longer timeout
    # > if using CopilotLLM
    llm = CopilotLLM(model="claude-sonnet-4.5", timeout=120)
    # > if using DeepSeekLLM (uncomment below)
    # from agent.config import get_deepseek_api_key
    # api_key = get_deepseek_api_key()
    # if api_key:
    #     llm = DeepSeekLLM(api_key=api_key)
    # else:
    #     print("❌ DeepSeek API key not found")
    #     return
    print("✅ LLM initialized")
    print()

    # Setup counter for monitoring
    counter = SimpleTokenCounter()
    iteration_count = [0]  # Use list to allow modification in closure

    # Monkey patch the LLM to log history size after each call
    original_chat = llm.chat

    def logged_chat(prompt, system_prompt=None, max_retries=5):
        result = original_chat(prompt, system_prompt, max_retries)
        iteration_count[0] += 1

        # Log current history size
        current_tokens = counter.count_messages(llm.history, llm.model)
        msg_count = len(llm.history)

        print()
        print("=" * 60)
        print(f"📊 AFTER LLM CALL #{iteration_count[0]}")
        print("=" * 60)
        print(f"   Messages in history: {msg_count}")
        print(f"   Current tokens: {current_tokens:,}")
        print(f"   Threshold: {trigger_at:,}")
        print(
            f"   Exceeded: {'✅ YES - Should trigger compaction!' if current_tokens >= trigger_at else '❌ NO'}"
        )
        print(f"   Percentage: {(current_tokens / trigger_at * 100):.1f}% of threshold")
        print("=" * 60)
        print()

        return result

    # Apply the patch
    llm.chat = logged_chat  # type: ignore

    # Create tools
    tools = [Tool(save_text)]

    # Create agent with simple task
    agent = Agent(
        llm=llm,
        tools=tools,
        max_iterations=15,
        system_prompt="""You are a helpful assistant. Complete the requested task efficiently.""",
    )

    # Simpler task that generates enough tokens
    task = """Please complete these tasks:

1. Write a detailed explanation (200+ words) about "Why Python is popular"
2. Save it to "python_intro.txt" using save_text
3. Write another explanation (200+ words) about "Python's key features"  
4. Save it to "python_features.txt" using save_text
5. Write a third explanation (200+ words) about "Python use cases"
6. Save it to "python_uses.txt" using save_text

Be thorough and detailed in each explanation to help demonstrate the concepts clearly."""

    print("🎯 Task:")
    print(task)
    print()
    print("=" * 80)
    print()
    print("🚀 Starting agent...")
    print()
    print("⚠️  WATCH FOR:")
    print("   📊 Token count after each LLM call")
    print("   🔄 Context compaction triggered (when tokens exceed threshold)")
    print("   ✅ Compaction successful")
    print()
    print("=" * 80)
    print()

    # Run agent
    response = await agent._run_async(task)

    print()
    print("=" * 80)
    print()
    print("📊 FINAL Results:")
    print(f"   - Success: {response.success}")
    print(f"   - Iterations: {response.iterations}")
    print(f"   - Response length: {len(response.content)} chars")
    print()

    # Final history stats
    final_tokens = counter.count_messages(llm.history, llm.model)
    final_msgs = len(llm.history)
    print(f"📈 Final History Stats:")
    print(f"   - Messages: {final_msgs}")
    print(f"   - Tokens: {final_tokens:,}")
    print(f"   - Threshold: {trigger_at:,}")
    print(f"   - Exceeded: {'YES' if final_tokens >= trigger_at else 'NO'}")
    print()

    # Check if files were created
    output_dir = Path("examples/output")
    if output_dir.exists():
        files = sorted(output_dir.glob("python*.txt"))
        if files:
            print(f"📄 Generated files ({len(files)}):")
            for f in files:
                size = f.stat().st_size
                print(f"   - {f.name} ({size} bytes)")
        else:
            print("📄 No python*.txt files created")
    else:
        print("📄 Output directory doesn't exist")

    print()
    print("=" * 80)
    print("✅ Test complete!")
    print()


if __name__ == "__main__":
    asyncio.run(main())
