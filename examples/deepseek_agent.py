"""
Example demonstrating the LLM Agent framework with DeepSeek LLM.

This example shows:
1. Creating custom tools
2. Setting up a DeepSeek LLM
3. Creating an agent with tools
4. Running the agent on a task with verbose mode

DeepSeek API key should be:
- Set in DEEPSEEK_API_KEY in .env file or environment variable
"""

import os
from agent import DeepSeekLLM, Tool, Agent, get_deepseek_api_key


# Define custom tools
def calculator(expression: str) -> float:
    """
    Evaluate a mathematical expression.

    Args:
        expression: A mathematical expression to evaluate (e.g., "2 + 2")

    Returns:
        The result of the calculation
    """
    try:
        # Note: eval is used here for simplicity. In production, use a safer alternative.
        result = eval(expression)
        return float(result)
    except Exception as e:
        return f"Error: {str(e)}"


def get_weather(city: str) -> str:
    """
    Get the weather for a city (mock implementation).

    Args:
        city: Name of the city

    Returns:
        Weather description
    """
    # Mock weather data
    weather_data = {
        "London": "Cloudy, 15°C",
        "New York": "Sunny, 22°C",
        "Tokyo": "Rainy, 18°C",
        "Beijing": "Clear, 20°C",
        "Shanghai": "Partly cloudy, 23°C",
    }
    return weather_data.get(city, f"Weather data not available for {city}")


def main():
    """Run the example."""

    # Get API key using dotenv configuration
    api_key = get_deepseek_api_key()
    if not api_key:
        print("❌ Error: DeepSeek API key not found!")
        print("Please set DEEPSEEK_API_KEY in .env file or environment variable")
        return

    # Step 1: Create tools from functions
    calc_tool = Tool(calculator)
    weather_tool = Tool(get_weather)

    print("Created tools:")
    print(f"  - {calc_tool.name}: {calc_tool.description}")
    print(f"  - {weather_tool.name}: {weather_tool.description}")
    print()

    # Step 2: Initialize DeepSeek LLM
    llm = DeepSeekLLM(
        api_key=api_key, model="deepseek-chat", base_url="https://api.deepseek.com"
    )
    print("Initialized DeepSeek LLM (deepseek-chat)")
    print()

    # Step 3: Create agent with tools
    agent = Agent(
        llm=llm,
        tools=[calc_tool, weather_tool],
        max_iterations=10,
        name="DeepSeekAgent",
    )
    print("Created agent with 2 tools")
    print()

    # Step 4: Run agent on a task with verbose mode
    task = "What is 25 * 4 + 10? Also, what's the weather like in Beijing?"
    print(f"Task: {task}")
    print()

    print("Running agent with verbose output...")
    print()
    response = agent.run(task, verbose=True)

    # Step 5: Display results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Success: {response.success}")
    print(f"Iterations: {response.iterations}")
    print(f"\nResponse:\n{response.content}")


if __name__ == "__main__":
    main()
