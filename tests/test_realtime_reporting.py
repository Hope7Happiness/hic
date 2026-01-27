"""
Test for real-time reporting behavior in async parallel agents.

This test verifies that the parent agent reports subagent results IMMEDIATELY
when they complete, rather than waiting for all subagents to finish.

Expected behavior:
1. Parent launches WeatherAgent (3s) and StockAgent (10s) in parallel
2. WeatherAgent completes at ~3s
3. Parent is RESUMED and should report weather in Thought field BEFORE continuing to wait
4. Parent continues waiting for StockAgent
5. StockAgent completes at ~10s
6. Parent reports stock price and finishes

Key verification:
- After first resume (WeatherAgent done), parent should output a Thought
- This Thought should happen BEFORE the next wait_for_subagents action
- Log should show: Resume → Thought → wait_for_subagents (not Resume → wait_for_subagents)

Usage:
    # Run all real-time reporting tests
    pytest tests/test_realtime_reporting.py -v

    # Run only DeepSeek tests
    pytest tests/test_realtime_reporting.py -v -k "deepseek"

    # Run with detailed output (show print statements)
    pytest tests/test_realtime_reporting.py -v -s

    # Skip slow tests
    pytest tests/test_realtime_reporting.py -v -m "not slow"
"""

import pytest
import asyncio
import time
import re
from pathlib import Path
from datetime import datetime
from typing import Literal
from agent.agent import Agent
from agent.llm import CopilotLLM, DeepSeekLLM
from agent.tool import Tool
from agent.async_logger import init_logger, close_logger
from agent.config import get_deepseek_api_key


# ============================================================================
# Pytest Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def test_run_id():
    """Generate unique ID for this test session."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


@pytest.fixture(autouse=True)
async def reset_orchestrator():
    """
    Reset orchestrator state between tests to avoid event loop issues.

    This fixture runs automatically before each test and recreates
    the asyncio.Queue in the current event loop.
    """
    from agent.orchestrator import AgentOrchestrator

    # Get the orchestrator instance
    orchestrator = AgentOrchestrator()

    # Recreate the message queue in the current event loop
    orchestrator.message_queue = asyncio.Queue()

    # Recreate completion events in the current event loop
    for agent_id in orchestrator.completion_events:
        orchestrator.completion_events[agent_id] = asyncio.Event()

    yield

    # Cleanup after test (optional)
    # Can add cleanup logic here if needed


@pytest.fixture
def log_dir(test_run_id, request):
    """
    Create unique log directory for each test.

    Structure: test_logs/run_<timestamp>/<provider>/

    This ensures:
    - Each test run has its own directory
    - Logs from different providers are separated
    - Repeated test runs don't overwrite each other
    """
    # Get the provider from test parameter if it exists
    provider = "unknown"
    if hasattr(request, "param"):
        provider = request.param
    elif "llm_provider" in request.fixturenames:
        provider = request.getfixturevalue("llm_provider")

    log_path = Path(f"test_logs/run_{test_run_id}/{provider}")
    log_path.mkdir(parents=True, exist_ok=True)

    yield str(log_path)

    # Optional: Cleanup logic could go here
    # For debugging, we keep the logs by default


@pytest.fixture
def llm_instance(llm_provider):
    """Create LLM instance based on provider name."""
    if llm_provider == "deepseek":
        api_key = get_deepseek_api_key()
        if not api_key:
            pytest.skip("DEEPSEEK_API_KEY not found in environment")
        return DeepSeekLLM(api_key=api_key, model="deepseek-chat")
    elif llm_provider == "copilot":
        token_file = Path.home() / ".config" / "mycopilot" / "github_token.json"
        if not token_file.exists():
            pytest.skip(
                f"Copilot not authenticated. Run: cd auth/copilot && python cli.py auth login"
            )
        return CopilotLLM(model="claude-haiku-4.5", temperature=0.7)
    else:
        raise ValueError(f"Unknown LLM provider: {llm_provider}")


# ============================================================================
# Tool and Agent Creation Functions
# ============================================================================


def create_weather_tool() -> Tool:
    """Create a tool that simulates weather query (3s delay)"""

    def get_weather(city: str) -> str:
        """Get weather information for a city."""
        time.sleep(3)  # Fast query
        return f"✅ 天气查询成功：{city}：晴天，气温 15°C"

    return Tool(get_weather)


def create_stock_tool() -> Tool:
    """Create a tool that simulates stock query (10s delay)"""

    def get_stock_price(symbol: str) -> str:
        """Get stock price for a symbol."""
        time.sleep(10)  # Slow query
        return f"✅ 股票查询成功：{symbol}: $182.45 ↑ +1.2%"

    return Tool(get_stock_price)


def create_weather_agent(llm) -> Agent:
    """Create weather agent (fast, 3s) with its own LLM instance"""
    weather_tool = create_weather_tool()

    # Create a NEW LLM instance for this agent to avoid history contamination
    if hasattr(llm, "api_key"):  # DeepSeekLLM
        weather_llm = type(llm)(api_key=llm.api_key, model=llm.model)
    else:  # CopilotLLM or other
        weather_llm = type(llm)(
            model=llm.model, temperature=getattr(llm, "temperature", 0.7)
        )

    system_prompt = """你是一个天气查询Agent。

你的任务：
1. 使用 get_weather 工具查询北京(Beijing)的天气
2. 返回天气信息

重要：必须先调用 get_weather(city="Beijing")，然后将结果返回给用户。"""

    return Agent(
        llm=weather_llm,
        tools=[weather_tool],
        name="WeatherAgent",
        system_prompt=system_prompt,
        max_iterations=5,
    )


def create_stock_agent(llm) -> Agent:
    """Create stock agent (slow, 10s) with its own LLM instance"""
    stock_tool = create_stock_tool()

    # Create a NEW LLM instance for this agent to avoid history contamination
    if hasattr(llm, "api_key"):  # DeepSeekLLM
        stock_llm = type(llm)(api_key=llm.api_key, model=llm.model)
    else:  # CopilotLLM or other
        stock_llm = type(llm)(
            model=llm.model, temperature=getattr(llm, "temperature", 0.7)
        )

    system_prompt = """你是一个股票查询Agent。

你的任务：
1. 使用 get_stock_price 工具查询苹果公司(AAPL)的股票价格
2. 返回股票信息

重要：必须先调用 get_stock_price(symbol="AAPL")，然后将结果返回给用户。"""

    return Agent(
        llm=stock_llm,
        tools=[stock_tool],
        name="StockAgent",
        system_prompt=system_prompt,
        max_iterations=5,
    )


def create_parent_agent(llm) -> Agent:
    """Create parent agent with real-time reporting instructions"""
    weather_agent = create_weather_agent(llm)
    stock_agent = create_stock_agent(llm)

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
   - 【关键】在Thought中立即向用户实时汇报刚完成的Agent结果
   - 检查是否还有pending的Agent
   - 如果还有pending的，继续 wait_for_subagents
   - 如果所有都完成了，使用 finish 提供最终总结

**实时汇报策略（非常重要）**：
- 【必须】每次resume时，第一件事就是在Thought中汇报新完成的结果
- Thought是用户可见的，用它来实现实时汇报
- 不要等所有Agent都完成再一起汇报

**示例执行流程**：
  * 第一次被唤醒（WeatherAgent完成）：
    Thought: "【实时汇报】天气查询完成！北京：晴天，15°C。股票查询还在进行中，请稍候..."
    Action: wait_for_subagents (继续等待StockAgent)
  
  * 第二次被唤醒（StockAgent完成）：
    Thought: "【实时汇报】股票查询完成！AAPL: $182.45 ↑+1.2%。所有查询已完成。"
    Action: finish

**重要提醒**：
- 每次resume后必须先输出Thought来汇报结果
- 然后再决定下一步Action（wait_for_subagents或finish）
"""

    return Agent(
        llm=llm,
        subagents={
            "WeatherAgent": weather_agent,
            "StockAgent": stock_agent,
        },
        name="ParentAgent",
        system_prompt=system_prompt,
        max_iterations=20,
    )


# ============================================================================
# Core Test Logic
# ============================================================================


async def run_realtime_test(llm, log_dir: str) -> dict:
    """
    Run the real-time reporting test.

    Args:
        llm: LLM instance to use
        log_dir: Directory to save logs

    Returns:
        dict with test results and analysis
    """
    # Initialize logger with custom log directory
    log_path = Path(log_dir)
    logger = await init_logger(log_dir=log_dir, console_output=True)
    # logger = await init_logger(log_dir=log_dir, console_output=False)

    try:
        # Create parent agent
        parent_agent = create_parent_agent(llm)

        # Run test
        start_time = time.time()
        result = await parent_agent._run_async(
            task="请同时查询北京天气和AAPL股票价格。每获得一个结果就立即向我汇报，不要等所有结果都出来再一起告诉我。",
        )
        end_time = time.time()
        elapsed = end_time - start_time

        # Find parent agent log
        parent_log = sorted(
            log_path.glob("ParentAgent_*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[0]

        # Read and analyze log
        with open(parent_log, "r") as f:
            log_content = f.read()

        analysis = analyze_log(log_content)

        return {
            "success": result.success,
            "elapsed": elapsed,
            "iterations": result.iterations,
            "log_file": str(parent_log),
            "analysis": analysis,
        }

    finally:
        await close_logger()


def analyze_log(log_content: str) -> dict:
    """
    EXTREMELY STRICT analysis of log for perfect real-time reporting behavior.

    This function validates EVERY step of the expected workflow:

    Expected workflow (based on correct log example):
    ========================================================
    1. ✅ launch_subagents action
    2. ✅ First wait_for_subagents action
    3. ✅ Suspended: Waiting for: WeatherAgent, StockAgent
    4. ✅ WeatherAgent finishes
    5. ✅ Resumed: Triggered by: WeatherAgent
    6. ✅ Thought with ACTUAL weather data (晴天, 15°C, 北京, etc.)
    7. ✅ Second wait_for_subagents action (continue waiting for StockAgent)
    8. ✅ Suspended: Waiting for: StockAgent (only StockAgent now!)
    9. ✅ StockAgent finishes
    10. ✅ Resumed: Triggered by: StockAgent
    11. ✅ Thought with stock data (AAPL, $182.45, etc.)
    12. ✅ finish action

    All steps must appear in the correct order with correct content!
    """
    lines = log_content.split("\n")

    # Track all required steps - values are line numbers (int) or None if not found
    steps_found: dict[str, int | None] = {
        "launch_subagents": None,
        "first_wait": None,
        "first_suspended": None,
        "first_resume_weather": None,
        "weather_thought": None,
        "second_wait": None,
        "second_suspended": None,
        "second_resume_stock": None,
        "stock_thought": None,
        "finish": None,
    }

    errors = []

    # Parse the log line by line - use independent checks to detect all steps
    # Track first occurrence of each pattern
    wait_count = 0  # Count how many wait_for_subagents actions we've seen
    thought_after_weather = False  # Track if we've seen a thought after weather resume

    for idx, line in enumerate(lines):
        line_num = idx + 1

        # Step 1: launch_subagents
        if (
            steps_found["launch_subagents"] is None
            and "Action: launch_subagents" in line
        ):
            steps_found["launch_subagents"] = line_num

        # Step 2: First wait_for_subagents
        if "Action: wait_for_subagents" in line:
            wait_count += 1
            if wait_count == 1 and steps_found["first_wait"] is None:
                steps_found["first_wait"] = line_num
            elif wait_count == 2 and steps_found["second_wait"] is None:
                steps_found["second_wait"] = line_num

        # Step 3: First suspended (waiting for both)
        if (
            steps_found["first_suspended"] is None
            and "Suspended: Waiting for:" in line
            and "WeatherAgent" in line
            and "StockAgent" in line
        ):
            steps_found["first_suspended"] = line_num

        # Step 4: First resume (WeatherAgent)
        if (
            steps_found["first_resume_weather"] is None
            and "Resumed: Triggered by: WeatherAgent" in line
        ):
            steps_found["first_resume_weather"] = line_num

        # Step 5: Weather thought (CRITICAL - must have actual weather data)
        if (
            steps_found["first_resume_weather"] is not None
            and not thought_after_weather
        ):
            if "💭 Thought:" in line or "[AGENT] 💭" in line:
                thought_after_weather = True
                # Check this line AND the next few lines for weather data
                # (weather data might be on separate lines after the Thought marker)
                context_lines = "\n".join(lines[idx : min(idx + 5, len(lines))])

                # Check for ACTUAL weather data (not just agent names)
                # More lenient patterns to catch variations like "天气状况：晴天" or "气温：15°C"
                has_weather_condition = re.search(
                    r"晴天?|阴天?|雨|雪|多云|sunny|cloudy|rainy|snowy|clear|晴朗",
                    context_lines,
                    re.IGNORECASE,
                )
                has_temperature = re.search(
                    r"\d+\s*°\s*[CF]|\d+\s*度|气温[：:]\s*\d+|temperature[：:]\s*\d+",
                    context_lines,
                    re.IGNORECASE,
                )
                has_location = re.search(r"北京|beijing", context_lines, re.IGNORECASE)

                # Must have weather condition OR temperature, preferably with location
                if (has_weather_condition or has_temperature) and has_location:
                    steps_found["weather_thought"] = line_num
                else:
                    # Found a Thought but it doesn't have weather data
                    preview = context_lines[:200].replace("\n", " ")
                    errors.append(
                        f"❌ Line {line_num}: Found Thought after WeatherAgent resume, but it lacks actual weather data. "
                        f"Expected: weather condition (晴/阴/雨) or temperature (15°C), with location (北京). "
                        f"Got: {preview}"
                    )

        # Step 7: Second suspended (waiting for StockAgent only)
        if (
            steps_found["second_suspended"] is None
            and wait_count >= 2  # We've seen the second wait
            and "Suspended: Waiting for:" in line
            and "StockAgent" in line
        ):
            # Make sure it's ONLY waiting for StockAgent (WeatherAgent should NOT be mentioned)
            if "WeatherAgent" not in line:
                steps_found["second_suspended"] = line_num
            else:
                errors.append(
                    f"❌ Line {line_num}: Second suspend still waiting for WeatherAgent! "
                    f"Should only wait for StockAgent at this point."
                )

        # Step 8: Second resume (StockAgent)
        if (
            steps_found["second_resume_stock"] is None
            and "Resumed: Triggered by: StockAgent" in line
        ):
            steps_found["second_resume_stock"] = line_num

        # Step 9: Stock thought (should have AAPL and price data)
        if (
            steps_found["stock_thought"] is None
            and steps_found["second_resume_stock"] is not None
            and ("💭 Thought:" in line or "[AGENT] 💭" in line)
        ):
            has_stock_symbol = re.search(r"AAPL|苹果|apple", line, re.IGNORECASE)
            has_price = re.search(r"\$?\d+\.\d+|价格|price", line, re.IGNORECASE)

            if has_stock_symbol or has_price:
                steps_found["stock_thought"] = line_num

        # Step 10: finish action
        if steps_found["finish"] is None and "Action: finish" in line:
            steps_found["finish"] = line_num

    # Validate all steps were found in order
    step_names = [
        "launch_subagents",
        "first_wait",
        "first_suspended",
        "first_resume_weather",
        "weather_thought",
        "second_wait",
        "second_suspended",
        "second_resume_stock",
        "stock_thought",
        "finish",
    ]

    step_descriptions = {
        "launch_subagents": "Launch both WeatherAgent and StockAgent",
        "first_wait": "First wait_for_subagents action",
        "first_suspended": "Suspended waiting for both agents",
        "first_resume_weather": "Resumed by WeatherAgent completion",
        "weather_thought": "Thought with actual weather data (晴/阴/雨, 15°C, 北京)",
        "second_wait": "Second wait_for_subagents (continue waiting for StockAgent)",
        "second_suspended": "Suspended waiting for StockAgent only",
        "second_resume_stock": "Resumed by StockAgent completion",
        "stock_thought": "Thought with stock data (AAPL, $182.45)",
        "finish": "Finish action with final result",
    }

    # Check for missing steps
    missing_steps = []
    for step in step_names:
        if steps_found[step] is None:
            missing_steps.append(f"❌ Missing: {step_descriptions[step]}")
            errors.append(f"❌ Step '{step}' not found: {step_descriptions[step]}")

    # Check order (each step should come after previous)
    order_errors = []
    for i in range(len(step_names) - 1):
        curr_step = step_names[i]
        next_step = step_names[i + 1]

        curr_line = steps_found[curr_step]
        next_line = steps_found[next_step]

        if curr_line is not None and next_line is not None:
            if curr_line >= next_line:
                order_errors.append(
                    f"❌ Order violation: {curr_step} (line {curr_line}) "
                    f"should come BEFORE {next_step} (line {next_line})"
                )

    errors.extend(order_errors)

    # Determine overall success
    all_steps_found = all(steps_found[step] is not None for step in step_names)
    no_order_errors = len(order_errors) == 0
    real_time_reporting = all_steps_found and no_order_errors

    # Build explanation
    if real_time_reporting:
        explanation = (
            f"✅ PERFECT real-time reporting! All {len(step_names)} steps found in correct order.\n"
            f"  Weather reported at line {steps_found['weather_thought']}, "
            f"then continued waiting (line {steps_found['second_wait']}), "
            f"stock reported at line {steps_found['stock_thought']}."
        )
    else:
        explanation = "❌ Real-time reporting validation FAILED:\n" + "\n".join(
            errors[:5]
        )  # Show first 5 errors
        if len(errors) > 5:
            explanation += f"\n  ... and {len(errors) - 5} more errors"

    # Extract weather content preview
    weather_content_preview = ""
    if steps_found["weather_thought"]:
        weather_line = lines[steps_found["weather_thought"] - 1]
        if "💭" in weather_line:
            weather_content_preview = weather_line.split("💭")[1].strip()[:100]

    return {
        "real_time_reporting": real_time_reporting,
        "steps_found": steps_found,
        "missing_steps": missing_steps,
        "errors": errors,
        "first_resume_line": steps_found["first_resume_weather"],
        "first_thought_line": steps_found["weather_thought"],
        "second_resume_line": steps_found["second_resume_stock"],
        "weather_info_found": steps_found["weather_thought"] is not None,
        "weather_content_preview": weather_content_preview,
        "explanation": explanation,
    }


# ============================================================================
# Pytest Tests
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize("llm_provider", ["deepseek", "copilot"])
async def test_realtime_reporting_by_provider(llm_provider, llm_instance, log_dir):
    """
    Test STRICT real-time reporting behavior for each LLM provider.

    This test verifies that when a parent agent launches multiple subagents in parallel,
    it reports ACTUAL WEATHER CONTENT immediately when WeatherAgent completes,
    BEFORE StockAgent finishes.

    STRICT criteria:
    - WeatherAgent (3s) completes first
    - Parent outputs Thought containing WEATHER INFO (not just "waiting" message)
    - This happens BEFORE StockAgent (10s) completes
    - Weather info must contain keywords like: 天气, 晴, 气温, temperature, etc.

    Real-time reporting means the parent actively reports what it learned from
    the completed subagent, not just acknowledges completion and keeps waiting.
    """
    print(f"\n{'=' * 70}")
    print(f"Testing STRICT Real-Time Reporting: {llm_provider.upper()}")
    print(f"Log directory: {log_dir}")
    print(f"{'=' * 70}\n")

    # Run the test
    result = await run_realtime_test(llm_instance, log_dir)

    # Print results for debugging
    print(f"✅ Test completed in {result['elapsed']:.2f}s")
    print(f"Success: {result['success']}")
    print(f"Iterations: {result['iterations']}")
    print(f"Log file: {result['log_file']}\n")

    analysis = result["analysis"]
    print(f"Analysis:")
    print(f"  First resume (WeatherAgent): Line {analysis['first_resume_line']}")
    print(f"  Thought with weather info: Line {analysis['first_thought_line']}")
    print(f"  Second resume (StockAgent): Line {analysis['second_resume_line']}")
    print(f"  Weather info found: {analysis['weather_info_found']}")
    if analysis.get("weather_content_preview"):
        print(f"  Weather preview: {analysis['weather_content_preview']}")
    print(f"  Result: {analysis['explanation']}\n")

    # Assertions
    assert result["success"], "Agent execution should complete successfully"
    assert result["iterations"] > 0, "Agent should have at least one iteration"

    # Critical assertion: Real-time reporting should work
    assert analysis["real_time_reporting"], (
        f"STRICT real-time reporting failed for {llm_provider}.\n"
        f"{analysis['explanation']}\n"
        f"Check log file: {result['log_file']}"
    )

    # Verify execution time (should be ~10-40s for parallel execution)
    # Note: Actual time depends on LLM response speed (DeepSeek can be slow)
    assert 9 < result["elapsed"] < 60, (
        f"Execution time {result['elapsed']:.2f}s is outside expected range (9-60s). "
        f"Expected ~10-40s for parallel execution of 3s + 10s tasks plus LLM processing."
    )
