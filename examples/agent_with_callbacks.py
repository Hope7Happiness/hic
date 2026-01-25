"""
Example: Using Callbacks for Agent Observability.

This example demonstrates how to use callbacks to monitor agent execution:
1. ConsoleCallback - Real-time console logging
2. MetricsCallback - Collect execution statistics
3. FileLoggerCallback - Write detailed logs to file
4. Custom callbacks - Implement your own event handlers

The callback system provides hooks for:
- Agent lifecycle events (start, finish)
- Iteration events (start, end)
- LLM interactions (request, response)
- Tool executions (call, result)
- Parse errors and retries
"""

import os
import sys
import tempfile

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import (
    DeepSeekLLM,
    Tool,
    Agent,
    ConsoleCallback,
    MetricsCallback,
    FileLoggerCallback,
    AgentCallback,
    get_deepseek_api_key,
)


# ===========================
# Example Tool Implementations
# ===========================


def calculator(expression: str) -> float:
    """Evaluate a mathematical expression safely."""
    try:
        # Only allow basic math operations
        allowed_chars = set("0123456789+-*/(). ")
        if not all(c in allowed_chars for c in expression):
            return "Error: Expression contains invalid characters"
        result = eval(expression)
        return float(result)
    except Exception as e:
        return f"Error: {str(e)}"


def file_writer(path: str, content: str) -> str:
    """Write content to a file."""
    try:
        with open(path, "w") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


def temperature_converter(celsius: float) -> str:
    """Convert Celsius to Fahrenheit."""
    fahrenheit = (celsius * 9 / 5) + 32
    return f"{celsius}°C = {fahrenheit}°F"


# ===========================
# Custom Callback Example
# ===========================


class PerformanceCallback(AgentCallback):
    """
    Custom callback that tracks performance metrics.

    This demonstrates how to create custom callbacks for
    specific monitoring needs.
    """

    def __init__(self):
        self.tool_execution_times = {}
        self.iteration_count = 0
        self.failed_tools = []

    def on_iteration_start(self, iteration: int, agent_name: str):
        self.iteration_count = iteration

    def on_tool_call(self, iteration: int, tool_name: str, arguments: dict):
        import time

        # Store start time for this tool
        if not hasattr(self, "_tool_start_times"):
            self._tool_start_times = {}
        self._tool_start_times[tool_name] = time.time()

    def on_tool_result(
        self, iteration: int, tool_name: str, result: str, success: bool
    ):
        import time

        # Calculate execution time
        if hasattr(self, "_tool_start_times") and tool_name in self._tool_start_times:
            elapsed = time.time() - self._tool_start_times[tool_name]
            if tool_name not in self.tool_execution_times:
                self.tool_execution_times[tool_name] = []
            self.tool_execution_times[tool_name].append(elapsed)

        # Track failures
        if not success:
            self.failed_tools.append(tool_name)

    def print_report(self):
        """Print a performance report."""
        print("\n" + "=" * 80)
        print("PERFORMANCE REPORT (Custom Callback)")
        print("=" * 80)
        print(f"Total Iterations: {self.iteration_count}")

        if self.tool_execution_times:
            print(f"\nTool Execution Times:")
            for tool_name, times in self.tool_execution_times.items():
                avg_time = sum(times) / len(times)
                print(
                    f"  {tool_name}: {avg_time * 1000:.2f}ms (avg over {len(times)} calls)"
                )

        if self.failed_tools:
            print(f"\nFailed Tools: {', '.join(set(self.failed_tools))}")
        else:
            print(f"\n✅ All tools executed successfully")
        print("=" * 80)


# ===========================
# API Key Helper
# ===========================


def get_api_key():
    """Get DeepSeek API key using dotenv configuration."""
    return get_deepseek_api_key()


# ===========================
# Main Examples
# ===========================


def example_console_callback():
    """Example 1: Using ConsoleCallback for real-time logging."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Console Callback")
    print("=" * 80)
    print("Shows real-time logging of agent execution to console.")
    print()

    # Get API key
    api_key = get_api_key()
    if not api_key:
        print("❌ Error: DeepSeek API key not found!")
        return

    # Initialize LLM
    llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")

    # Create tools
    tools = [Tool(calculator), Tool(temperature_converter)]

    # Create console callback (verbose mode)
    console = ConsoleCallback(
        verbose=True, show_prompts=False, show_responses=True, color=True
    )

    # Create agent with console callback
    agent = Agent(
        llm=llm,
        tools=tools,
        callbacks=[console],
        max_iterations=5,
        name="CalculatorAgent",
    )

    # Run task
    task = "Calculate 25 * 4, then convert 100 degrees Celsius to Fahrenheit."
    agent.run(task)


def example_metrics_callback():
    """Example 2: Using MetricsCallback to collect statistics."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Metrics Callback")
    print("=" * 80)
    print("Collects execution statistics for analysis.")
    print()

    # Get API key
    api_key = get_api_key()
    if not api_key:
        print("❌ Error: DeepSeek API key not found!")
        return

    # Initialize LLM
    llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")

    # Create tools
    tools = [Tool(calculator), Tool(temperature_converter)]

    # Create metrics callback
    metrics = MetricsCallback()

    # Create agent with metrics callback (no console output)
    agent = Agent(
        llm=llm, tools=tools, callbacks=[metrics], max_iterations=5, name="MetricsAgent"
    )

    # Run task
    task = "Calculate (100 + 50) * 2, then convert 25°C to Fahrenheit."
    result = agent.run(task)

    # Print results and metrics
    print(f"\n📝 Agent Result: {result.content}")
    print(f"✅ Success: {result.success}")
    print(f"🔄 Iterations: {result.iterations}")

    # Print detailed metrics
    metrics.print_summary()


def example_file_logger_callback():
    """Example 3: Using FileLoggerCallback to write logs to file."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: File Logger Callback")
    print("=" * 80)
    print("Writes detailed execution logs to a file.")
    print()

    # Get API key
    api_key = get_api_key()
    if not api_key:
        print("❌ Error: DeepSeek API key not found!")
        return

    # Create temporary log file
    log_file = tempfile.mktemp(suffix=".log", prefix="agent_")
    print(f"📄 Log file: {log_file}")

    # Initialize LLM
    llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")

    # Create tools
    tools = [Tool(calculator)]

    # Create file logger callback
    file_logger = FileLoggerCallback(log_file, format="json")

    # Create agent with file logger
    agent = Agent(
        llm=llm,
        tools=tools,
        callbacks=[file_logger],
        max_iterations=5,
        name="LoggedAgent",
    )

    # Run task
    task = "Calculate 123 + 456"
    result = agent.run(task)

    # Print results
    print(f"\n📝 Agent Result: {result.content}")
    print(f"✅ Success: {result.success}")

    # Show log file contents
    print(f"\n📄 Log file contents:")
    print("-" * 80)
    with open(log_file, "r") as f:
        import json

        for i, line in enumerate(f, 1):
            log_entry = json.loads(line)
            print(f"[{i}] {log_entry['event']}: {log_entry['timestamp']}")
    print("-" * 80)

    # Clean up
    os.remove(log_file)
    print(f"\n🗑️  Cleaned up log file")


def example_multiple_callbacks():
    """Example 4: Using multiple callbacks simultaneously."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Multiple Callbacks")
    print("=" * 80)
    print("Uses Console, Metrics, and Custom callbacks together.")
    print()

    # Get API key
    api_key = get_api_key()
    if not api_key:
        print("❌ Error: DeepSeek API key not found!")
        return

    # Initialize LLM
    llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")

    # Create tools
    tools = [Tool(calculator), Tool(temperature_converter)]

    # Create multiple callbacks
    console = ConsoleCallback(verbose=False, color=True)
    metrics = MetricsCallback()
    performance = PerformanceCallback()

    # Create agent with all callbacks
    agent = Agent(
        llm=llm,
        tools=tools,
        callbacks=[console, metrics, performance],
        max_iterations=5,
        name="MultiCallbackAgent",
    )

    # Run task
    task = "First calculate 99 * 88, then convert 37 degrees Celsius to Fahrenheit."
    result = agent.run(task)

    # Print all metrics
    print("\n" + "=" * 80)
    print("RESULTS FROM ALL CALLBACKS")
    print("=" * 80)

    # Standard metrics
    metrics.print_summary()

    # Custom performance metrics
    performance.print_report()


def example_custom_callback():
    """Example 5: Implementing a custom callback for specific needs."""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Custom Callback Implementation")
    print("=" * 80)
    print("Shows how to create custom callbacks for specific monitoring.")
    print()

    # Get API key
    api_key = get_api_key()
    if not api_key:
        print("❌ Error: DeepSeek API key not found!")
        return

    # Initialize LLM
    llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")

    # Create tools
    tools = [Tool(calculator)]

    # Create custom performance callback
    performance = PerformanceCallback()

    # Create agent with custom callback
    agent = Agent(
        llm=llm,
        tools=tools,
        callbacks=[performance],
        max_iterations=5,
        name="CustomAgent",
    )

    # Run task
    task = "Calculate (50 + 50) * 2 / 10"
    result = agent.run(task)

    # Print results
    print(f"\n📝 Agent Result: {result.content}")

    # Print custom metrics
    performance.print_report()


def main():
    """Run all callback examples."""

    print("\n" + "=" * 80)
    print("AGENT CALLBACKS DEMONSTRATION")
    print("=" * 80)
    print("\nThis example demonstrates the callback system for agent observability.")
    print("Callbacks provide hooks into agent execution for monitoring and logging.")
    print()
    print("Available examples:")
    print("  1. ConsoleCallback - Real-time console logging")
    print("  2. MetricsCallback - Execution statistics")
    print("  3. FileLoggerCallback - Write logs to file")
    print("  4. Multiple callbacks - Use several callbacks together")
    print("  5. Custom callback - Implement your own monitoring")
    print()

    # Run examples
    try:
        example_console_callback()
        example_metrics_callback()
        example_file_logger_callback()
        example_multiple_callbacks()
        example_custom_callback()

        print("\n" + "=" * 80)
        print("ALL EXAMPLES COMPLETED")
        print("=" * 80)

    except KeyboardInterrupt:
        print("\n\n⚠️  Examples interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error running examples: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
