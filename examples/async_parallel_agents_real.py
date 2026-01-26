"""
Real-time reporting example with parallel subagents.

This example demonstrates:
1. Parent agent launches two subagents in parallel (WeatherAgent and StockAgent)
2. WeatherAgent fetches weather data (takes 3 seconds)
3. StockAgent fetches stock price (takes 10 seconds)
4. **KEY FEATURE**: Parent agent reports each result IMMEDIATELY when available,
   rather than waiting for all subagents to finish
5. This shows real-time streaming behavior where faster results are shown first

Expected behavior:
- Both agents start at t=0
- WeatherAgent finishes at ~3s -> Parent immediately reports weather
- StockAgent finishes at ~10s -> Parent immediately reports stock price
- Parent then provides final summary

Usage:
    # Use Copilot (default)
    python examples/async_parallel_agents_real.py

    # Use DeepSeek
    python examples/async_parallel_agents_real.py --llm deepseek
    # or
    LLM_PROVIDER=deepseek python examples/async_parallel_agents_real.py
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


def create_weather_tool() -> Tool:
    """Create a tool that fetches weather data (simulated with 3s delay)"""

    def get_weather(city: str) -> str:
        """
        Get weather information for a city.

        Args:
            city: City name (e.g., "Beijing", "Shanghai")

        Returns:
            Weather information
        """
        time.sleep(3)  # Simulate API call delay

        # Simulate weather data
        weather_data = {
            "Beijing": "晴天，气温 15°C，东北风 3级",
            "Shanghai": "多云，气温 18°C，东南风 2级",
            "Shenzhen": "小雨，气温 22°C，南风 4级",
        }

        result = weather_data.get(city, f"{city}：晴天，气温 20°C，微风")
        return f"✅ 天气查询成功：{result}"

    return Tool(get_weather)


def create_stock_tool() -> Tool:
    """Create a tool that fetches stock price (simulated with 10s delay)"""

    def get_stock_price(symbol: str) -> str:
        """
        Get current stock price for a symbol.

        Args:
            symbol: Stock symbol (e.g., "AAPL", "TSLA", "BABA")

        Returns:
            Stock price information
        """
        time.sleep(10)  # Simulate complex financial API call

        # Simulate stock data
        stock_data = {
            "AAPL": "苹果(AAPL): $182.45 ↑ +1.2%",
            "TSLA": "特斯拉(TSLA): $245.80 ↓ -0.8%",
            "BABA": "阿里巴巴(BABA): $88.90 ↑ +2.3%",
        }

        result = stock_data.get(symbol, f"{symbol}: $100.00 ↔ 0.0%")
        return f"✅ 股票查询成功：{result}"

    return Tool(get_stock_price)


def create_weather_agent(llm) -> Agent:
    """
    Create weather agent that fetches weather data for Beijing.

    This agent will:
    1. Use get_weather tool to fetch weather for Beijing
    2. Takes ~3 seconds to complete
    3. Return weather information

    Args:
        llm: LLM instance (independent from other agents)
    """
    weather_tool = create_weather_tool()

    system_prompt = """你是一个天气查询Agent。

你的任务：
1. 使用 get_weather 工具查询北京(Beijing)的天气
2. 返回天气信息

重要：必须先调用 get_weather(city="Beijing")，然后将结果返回给用户。"""

    agent = Agent(
        llm=llm,
        tools=[weather_tool],
        name="WeatherAgent",
        system_prompt=system_prompt,
        max_iterations=5,
    )

    return agent


def create_stock_agent(llm) -> Agent:
    """
    Create stock agent that fetches stock price for AAPL.

    This agent will:
    1. Use get_stock_price tool to fetch AAPL stock price
    2. Takes ~10 seconds to complete
    3. Return stock price information

    Args:
        llm: LLM instance (independent from other agents)
    """
    stock_tool = create_stock_tool()

    system_prompt = """你是一个股票查询Agent。

你的任务：
1. 使用 get_stock_price 工具查询苹果公司(AAPL)的股票价格
2. 返回股票信息

重要：必须先调用 get_stock_price(symbol="AAPL")，然后将结果返回给用户。"""

    agent = Agent(
        llm=llm,
        tools=[stock_tool],
        name="StockAgent",
        system_prompt=system_prompt,
        max_iterations=5,
    )

    return agent


def create_parent_agent() -> Agent:
    """
    Create parent agent that coordinates weather and stock queries.

    KEY BEHAVIOR:
    - Launches both agents in parallel
    - When WeatherAgent finishes (fast, ~3s), immediately reports weather to user
    - Continues waiting for StockAgent
    - When StockAgent finishes (slow, ~10s), immediately reports stock price
    - Finally provides a summary

    This demonstrates real-time streaming behavior where results are
    reported as soon as they're available, not all at once.

    IMPORTANT: Each agent (parent, weather, stock) gets its own independent LLM instance
    to prevent conversation history contamination.
    """
    parent_llm = create_llm()

    # Create independent LLM instances for each subagent
    # This prevents conversation history sharing between agents
    weather_llm = create_llm()
    stock_llm = create_llm()

    weather_agent = create_weather_agent(weather_llm)
    stock_agent = create_stock_agent(stock_llm)

    system_prompt = """你是一个信息查询协调Agent。

你有两个子Agent：
1. WeatherAgent - 查询北京天气（快速，约3秒）
2. StockAgent - 查询AAPL股票价格（慢速，约10秒）

**关键任务流程（实时汇报模式）**：

1. 首次启动：使用 launch_subagents 同时启动两个Agent
   格式：
   Action: launch_subagents
   Agents: ["WeatherAgent", "StockAgent"]
   Tasks: ["查询北京天气", "查询AAPL股票价格"]

2. 等待结果：使用 wait_for_subagents 等待

3. **每次被唤醒时（有Agent完成）**：
   - 在Thought中向用户实时汇报刚完成的Agent结果
   - 检查是否还有pending的Agent
   - 如果还有pending的，继续 wait_for_subagents
   - 如果所有都完成了，使用 finish 提供最终总结

**实时汇报策略**：
- 用Thought字段实时向用户汇报每个Agent的完成情况
- 例如：
  * 第一次被唤醒（WeatherAgent完成）：
    Thought: "【实时汇报】天气查询完成！北京：晴天，15°C。股票查询还在进行中..."
    Action: wait_for_subagents (继续等待StockAgent)
  
  * 第二次被唤醒（StockAgent完成）：
    Thought: "【实时汇报】股票查询完成！AAPL: $182.45 ↑+1.2%。所有查询已完成。"
    Action: finish (提供最终总结)

**重要**：
- 每次resume时，立即在Thought中汇报新完成的结果
- Thought是用户可见的，用它来实现实时汇报
- 不要等所有Agent都完成再一起汇报
- 最后finish时只需要简短总结即可
"""

    agent = Agent(
        parent_llm,
        subagents={
            "WeatherAgent": weather_agent,
            "StockAgent": stock_agent,
        },
        name="ParentAgent",
        system_prompt=system_prompt,
        max_iterations=20,
    )

    return agent


async def main():
    """Run the real-time reporting example"""
    # Load environment variables
    load_env()

    # Get LLM provider
    provider = get_llm_provider()

    # Initialize async logger
    print("=" * 70)
    print(f"Real-Time Reporting Example with Parallel Subagents ({provider.upper()})")
    print("=" * 70)
    print()
    print("Scenario:")
    print("  - Query Beijing weather (fast, ~3s)")
    print("  - Query AAPL stock price (slow, ~10s)")
    print()
    print("Expected behavior:")
    print("  - Both queries start at t=0 (parallel execution)")
    print("  - Weather result reported at ~3s (as soon as available)")
    print("  - Stock result reported at ~10s (as soon as available)")
    print("  - NOT waiting for all results before reporting")
    print()
    print("This demonstrates real-time streaming of results!")
    print("=" * 70)
    print()

    logger = await init_logger(log_dir="logs", console_output=True)

    try:
        # Create parent agent
        parent_agent = create_parent_agent()

        # Run the parent agent
        start_time = time.time()

        result = await parent_agent._run_async(
            task="请同时查询北京天气和AAPL股票价格。每获得一个结果就立即向我汇报，不要等所有结果都出来再一起告诉我。",
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
        print(f"Final Content:\n{result.content}")
        print()

        # Verify parallel execution
        if elapsed < 12:  # Should be ~10s (slower task), not 13s (sequential)
            print("✅ Parallel execution confirmed!")
            print(f"   Weather query: ~3s")
            print(f"   Stock query: ~10s")
            print(f"   Total time: {elapsed:.1f}s (parallel)")
            print(f"   If sequential: would be ~13s")
        else:
            print("⚠️  Execution took longer than expected")
            print(f"   Total time: {elapsed:.1f}s")

        print()
        print(f"Logs saved to: logs/")

    finally:
        # Close logger
        await close_logger()


if __name__ == "__main__":
    asyncio.run(main())
