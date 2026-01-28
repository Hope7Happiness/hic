"""
Codex parallel tasks example.

This example demonstrates using Codex CLI to run parallel tasks,
similar to async_parallel_agents_real.py but adapted for Codex's
single-shot execution model.

Usage:
    # Make sure Codex CLI works first:
    #   codex login
    #
    # Then run:
    #   python examples/async_codex.py
"""

import asyncio
import subprocess
import json
import time
from typing import Optional


def extract_codex_response(jsonl: str) -> str:
    """Extract the last assistant/agent message from Codex JSONL output."""
    last_text = ""
    if not jsonl:
        return last_text

    for line in jsonl.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except Exception:
            continue

        if not isinstance(evt, dict):
            continue

        # Codex CLI format: {"type": "item.completed", "item": {"type": "agent_message", "text": "..."}}
        if evt.get("type") == "item.completed":
            item = evt.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    last_text = text.strip()

    return last_text


def codex_chat(prompt: str, model: str = "gpt-5.2") -> str:
    """Send a single prompt to Codex CLI and get the response."""
    cmd = ["codex", "exec", "--json", "--model", model, prompt]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        raise RuntimeError("Codex CLI not found. Please ensure `codex` is installed and in PATH.")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Codex CLI call timed out after 120 seconds.")

    if result.returncode != 0:
        raise RuntimeError(f"Codex CLI failed with exit code {result.returncode}\nstderr: {result.stderr}")

    response = extract_codex_response(result.stdout)
    return response if response else "[Codex returned empty response]"


async def query_weather_with_codex(city: str) -> dict:
    """Query weather using Codex (simulated task)."""
    start = time.time()
    
    prompt = f"""你是一个天气查询助手。
请模拟查询 {city} 的天气，然后用简短的中文告诉我结果。
格式：城市名：天气情况，温度，风向风力
不要解释，直接给出结果。"""

    # Run in thread pool to not block event loop
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, codex_chat, prompt)
    
    elapsed = time.time() - start
    return {
        "task": "weather",
        "city": city,
        "response": response,
        "elapsed": elapsed,
    }


async def query_stock_with_codex(symbol: str) -> dict:
    """Query stock price using Codex (simulated task)."""
    start = time.time()
    
    prompt = f"""你是一个股票查询助手。
请模拟查询 {symbol} 的当前股票价格，然后用简短的中文告诉我结果。
格式：公司名(代码): $价格 涨跌幅
不要解释，直接给出结果。"""

    # Run in thread pool to not block event loop
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, codex_chat, prompt)
    
    elapsed = time.time() - start
    return {
        "task": "stock",
        "symbol": symbol,
        "response": response,
        "elapsed": elapsed,
    }


async def main():
    print("=" * 70)
    print("Codex Parallel Tasks Example")
    print("=" * 70)
    print()
    print("This example runs two Codex queries in parallel:")
    print("  1. Query Beijing weather")
    print("  2. Query AAPL stock price")
    print()
    print("Starting parallel queries...")
    print("=" * 70)
    print()

    start_time = time.time()

    # Run both queries in parallel
    weather_task = asyncio.create_task(query_weather_with_codex("北京"))
    stock_task = asyncio.create_task(query_stock_with_codex("AAPL"))

    # Wait for results as they complete
    pending = {weather_task, stock_task}
    
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        
        for task in done:
            result = task.result()
            task_type = result["task"]
            elapsed = result["elapsed"]
            
            if task_type == "weather":
                print(f"[{elapsed:.1f}s] ✅ 天气查询完成:")
                print(f"    {result['response']}")
            else:
                print(f"[{elapsed:.1f}s] ✅ 股票查询完成:")
                print(f"    {result['response']}")
            print()

    total_time = time.time() - start_time

    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Total time: {total_time:.1f}s")
    print()
    
    # Both queries should run in parallel, so total time ≈ max(query1, query2)
    # not sum(query1, query2)
    print("✅ Both Codex queries ran in parallel!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
