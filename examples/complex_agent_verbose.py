"""
Complex Agent Example with Detailed Logging.

This example demonstrates a sophisticated agent that:
1. Uses multiple tools (python_exec, file_write, file_search, get_weather)
2. Makes multiple decisions across several iterations
3. Logs all intermediate steps, LLM responses, and tool executions
4. Shows the complete reasoning process

Task: Research assistant that analyzes data, generates a report, and saves it.

Output:
- Iteration-by-iteration breakdown
- LLM thoughts and decisions
- Tool inputs and outputs
- Complete conversation history
"""

import os
import sys
import json
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import DeepSeekLLM, Tool, Agent, get_deepseek_api_key


# Tool implementations (copied from test_utils for standalone example)
def python_exec(code: str) -> str:
    """Execute Python code and return the output."""
    from io import StringIO

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        exec(code, {})
        output = sys.stdout.getvalue()
        return output if output else "Code executed successfully (no output)"
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        sys.stdout = old_stdout


def file_write(path: str, content: str) -> str:
    """Write content to a file."""
    try:
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        with open(path, "w") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


def file_search(pattern: str, directory: str = ".") -> str:
    """Search for files matching a glob pattern."""
    import glob as glob_module

    try:
        search_pattern = os.path.join(directory, pattern)
        matches = glob_module.glob(search_pattern, recursive=True)
        if matches:
            return f"Found {len(matches)} files:\n" + "\n".join(matches)
        else:
            return "No files found matching the pattern"
    except Exception as e:
        return f"Error searching files: {str(e)}"


def get_weather(city: str) -> str:
    """Get weather information for a city (mock implementation)."""
    weather_db = {
        "London": "Cloudy with light rain, 15°C",
        "New York": "Sunny and clear, 22°C",
        "Tokyo": "Rainy, 18°C",
        "Beijing": "Clear skies, 20°C",
        "Shanghai": "Partly cloudy, 23°C",
        "Paris": "Overcast, 16°C",
        "Berlin": "Cold and windy, 10°C",
        "Sydney": "Hot and sunny, 28°C",
    }
    return weather_db.get(city, f"Weather data not available for {city}")


def get_api_key():
    """Get DeepSeek API key using dotenv configuration."""
    return get_deepseek_api_key()


class VerboseAgent:
    """
    Wrapper around Agent that logs all intermediate steps.

    This provides visibility into the agent's reasoning process:
    - Each iteration's input and output
    - Tool calls with arguments and results
    - LLM's internal thoughts
    - Complete conversation history
    """

    def __init__(self, agent: Agent):
        self.agent = agent
        self.iteration_logs = []

    def run(self, task: str):
        """Run the agent with detailed logging."""
        print("\n" + "=" * 80)
        print("COMPLEX AGENT EXECUTION WITH DETAILED LOGGING")
        print("=" * 80)
        print(f"\n📋 Task: {task}")
        print(f"🤖 Agent: {self.agent.name}")
        print(f"🔧 Tools Available: {', '.join(self.agent.tools.keys())}")
        print(f"📊 Max Iterations: {self.agent.max_iterations}")
        print("\n" + "=" * 80)

        # Hook into the agent's execution
        original_chat = self.agent.llm.chat
        original_execute_tool = self.agent._execute_tool

        iteration_count = [0]  # Use list for closure

        def logged_chat(prompt, system_prompt=None):
            """Wrapper for LLM chat that logs input/output."""
            iteration_count[0] += 1

            print(f"\n{'─' * 80}")
            print(f"🔄 ITERATION {iteration_count[0]}")
            print(f"{'─' * 80}")

            if system_prompt and iteration_count[0] == 1:
                print(f"\n📝 System Prompt:")
                print(f"   {system_prompt[:200]}...")

            print(f"\n💬 User Input to LLM:")
            print(f"   {prompt[:300]}{'...' if len(prompt) > 300 else ''}")

            # Call original LLM
            response = original_chat(prompt, system_prompt)

            print(f"\n🧠 LLM Response:")
            print(f"{'─' * 80}")
            # Pretty print the response with indentation
            for line in response.split("\n"):
                print(f"   {line}")
            print(f"{'─' * 80}")

            # Try to extract thought and action
            if "Thought:" in response:
                thought = response.split("Thought:")[1].split("\n")[0].strip()
                print(f"\n💭 Extracted Thought: {thought}")

            if "Action:" in response:
                action = response.split("Action:")[1].split("\n")[0].strip()
                print(f"⚡ Action Type: {action}")

            return response

        def logged_execute_tool(action):
            """Wrapper for tool execution that logs input/output."""
            print(f"\n🔧 TOOL EXECUTION")
            print(f"   Tool: {action.tool_call.tool_name}")
            print(f"   Arguments: {json.dumps(action.tool_call.arguments, indent=6)}")

            # Call original tool execution
            result = original_execute_tool(action)

            print(f"\n📤 Tool Output:")
            result_str = str(result)
            if len(result_str) > 200:
                print(f"   {result_str[:200]}...")
                print(f"   ... (truncated, total length: {len(result_str)} chars)")
            else:
                print(f"   {result_str}")

            return result

        # Replace methods with logged versions
        self.agent.llm.chat = logged_chat
        self.agent._execute_tool = logged_execute_tool

        # Run the agent
        print(f"\n🚀 Starting Agent Execution...")
        result = self.agent.run(task)

        # Restore original methods
        self.agent.llm.chat = original_chat
        self.agent._execute_tool = original_execute_tool

        # Print final summary
        print(f"\n{'=' * 80}")
        print("EXECUTION SUMMARY")
        print(f"{'=' * 80}")
        print(f"✅ Success: {result.success}")
        print(f"🔄 Total Iterations: {result.iterations}")
        print(f"📝 Final Response:")
        print(f"{'─' * 80}")
        for line in result.content.split("\n"):
            print(f"   {line}")
        print(f"{'─' * 80}")

        # Print conversation history
        print(f"\n{'=' * 80}")
        print("COMPLETE CONVERSATION HISTORY")
        print(f"{'=' * 80}")
        history = self.agent.llm.get_history()
        for i, msg in enumerate(history, 1):
            role = msg["role"].upper()
            content = msg["content"]
            print(f"\n[{i}] {role}:")
            if len(content) > 500:
                print(f"{content[:500]}...")
            else:
                print(content)

        print(f"\n{'=' * 80}")
        print("EXECUTION COMPLETE")
        print(f"{'=' * 80}\n")

        return result


def main():
    """Run the complex agent example."""

    # Get API key
    api_key = get_api_key()
    if not api_key:
        print("❌ Error: DeepSeek API key not found!")
        print("Please set DEEPSEEK_API_KEY in .env file or environment variable")
        return

    print("\n" + "=" * 80)
    print("COMPLEX AGENT DEMONSTRATION")
    print("=" * 80)
    print("\nThis example shows a research assistant agent that:")
    print("  1. Calculates statistics using Python")
    print("  2. Fetches weather data for analysis")
    print("  3. Generates a report with the data")
    print("  4. Saves the report to a file")
    print("  5. Verifies the file was created")
    print("\nAll intermediate steps will be logged in detail.")

    # Initialize LLM
    llm = DeepSeekLLM(
        api_key=api_key, model="deepseek-chat", base_url="https://api.deepseek.com"
    )

    # Create tools
    tools = [
        Tool(python_exec),
        Tool(file_write),
        Tool(file_search),
        Tool(get_weather),
    ]

    # Create agent
    agent = Agent(llm=llm, tools=tools, max_iterations=15, name="ResearchAssistant")

    # Wrap with verbose logger
    verbose_agent = VerboseAgent(agent)

    # Define complex task (simplified to avoid multi-line JSON issues)
    task = """I need you to create a weather analysis report. Here's what to do:

1. Calculate the sum of 15 + 22 + 18 using Python (use simple code like: print(15+22+18)).
2. Get the weather information for Tokyo using the get_weather tool.
3. Create a report file at /tmp/weather_analysis_report.txt with both pieces of information.
4. Search for the file to confirm it was created.

Complete all steps in order."""

    # Run the agent with detailed logging
    result = verbose_agent.run(task)

    # Additional statistics
    print("\n" + "=" * 80)
    print("PERFORMANCE STATISTICS")
    print("=" * 80)
    print(f"Total Iterations: {result.iterations}")
    print(f"Success Rate: {'100%' if result.success else '0%'}")
    print(f"Tools Used: {len(agent.tools)}")

    # Clean up
    test_file = "/tmp/weather_analysis_report.txt"
    if os.path.exists(test_file):
        print(f"\n🗑️  Cleaning up test file: {test_file}")
        os.remove(test_file)
        print("✅ Cleanup complete")


if __name__ == "__main__":
    main()
