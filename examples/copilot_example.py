"""
Example: Using GitHub Copilot LLM with Agent Framework

This example demonstrates:
1. How to use CopilotLLM with the agent framework
2. Simple agent with tools powered by Copilot
3. Authentication setup

Prerequisites:
1. Authenticate with GitHub Copilot:
   ```bash
   cd auth/copilot
   python cli.py auth login
   ```
   Follow the instructions to authenticate.

2. Install dependencies:
   ```bash
   pip install -e .
   ```
"""

import asyncio
import time
from agent.agent import Agent
from agent.copilot_llm import CopilotLLM
from agent.tool import Tool
from agent.async_logger import init_logger, close_logger


def create_calculator_tool() -> Tool:
    """Create a simple calculator tool"""

    def calculate(expression: str) -> str:
        """
        Evaluate a mathematical expression.

        Args:
            expression: Math expression to evaluate (e.g., "2 + 2", "10 * 5")

        Returns:
            Result of the calculation
        """
        try:
            result = eval(expression, {"__builtins__": {}})
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {e}"

    return Tool(calculate)


async def main():
    """Run the Copilot example"""
    print("=" * 70)
    print("GitHub Copilot LLM Example")
    print("=" * 70)
    print()

    # Initialize logger
    logger = await init_logger(log_dir="logs", console_output=True)

    try:
        # Create Copilot LLM
        print("Initializing GitHub Copilot LLM...")
        try:
            llm = CopilotLLM(
                model="claude-haiku-4.5",  # Fast and cost-effective
                temperature=0.7,
            )
            print(f"✅ Connected to GitHub Copilot (model: claude-haiku-4.5)")
        except RuntimeError as e:
            print(f"❌ Authentication error:\n{e}")
            print("\nPlease run: cd auth/copilot && python cli.py auth login")
            return

        # Create tools
        calculator = create_calculator_tool()

        # Create agent
        system_prompt = """你是一个数学助手Agent。

你可以使用 calculate 工具来计算数学表达式。

任务流程：
1. 理解用户的数学问题
2. 使用 calculate 工具计算
3. 向用户解释结果

重要：必须使用工具来计算，不要自己估算。"""

        agent = Agent(
            llm=llm,
            tools=[calculator],
            name="MathAgent",
            system_prompt=system_prompt,
            max_iterations=5,
        )

        # Test the agent
        print()
        print("Testing agent with Copilot...")
        print("Task: Calculate 123 * 456")
        print()

        start_time = time.time()

        result = await agent._run_async(
            task="请帮我计算 123 乘以 456 等于多少？",
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
        print(f"Time: {elapsed:.2f}s")
        print()
        print(f"Response:\n{result.content}")
        print()

        if result.success:
            print("✅ GitHub Copilot integration working perfectly!")
        else:
            print("⚠️  Task completed with issues")

    finally:
        # Close logger
        await close_logger()


if __name__ == "__main__":
    asyncio.run(main())
