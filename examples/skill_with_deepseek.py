"""
Example demonstrating using a Skill (YAML-configured agent) with DeepSeek LLM.

This example shows:
1. Defining available tools
2. Loading a skill from YAML
3. Running an agent created from the skill
4. Using DeepSeek LLM with skills

The weather_skill.yaml defines a weather assistant agent with:
- get_weather tool
- get_temperature tool
- Custom system prompt
- Max iterations limit
"""

import os
from agent import DeepSeekLLM, Tool, Skill, get_deepseek_api_key


def get_weather(city: str) -> str:
    """
    Get weather information for a city (mock implementation).

    Args:
        city: Name of the city

    Returns:
        Weather description including condition and temperature
    """
    # Mock weather database
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

    weather = weather_db.get(city, f"Weather data not available for {city}")
    return weather


def get_temperature(city: str) -> str:
    """
    Get the current temperature for a city (mock implementation).

    Args:
        city: Name of the city

    Returns:
        Temperature in Celsius
    """
    # Mock temperature database
    temp_db = {
        "London": "15°C",
        "New York": "22°C",
        "Tokyo": "18°C",
        "Beijing": "20°C",
        "Shanghai": "23°C",
        "Paris": "16°C",
        "Berlin": "10°C",
        "Sydney": "28°C",
    }

    temp = temp_db.get(city, f"Temperature data not available for {city}")
    return temp


def main():
    """Run the example."""

    # Get API key using dotenv configuration
    api_key = get_deepseek_api_key()
    if not api_key:
        print("❌ Error: DeepSeek API key not found!")
        print("Please set DEEPSEEK_API_KEY in .env file or environment variable")
        return

    print("=" * 60)
    print("SKILL-BASED AGENT EXAMPLE WITH DEEPSEEK")
    print("=" * 60)
    print()

    # Step 1: Create tools dictionary
    available_tools = {
        "get_weather": Tool(get_weather),
        "get_temperature": Tool(get_temperature),
    }

    print("Step 1: Created tools")
    for name, tool in available_tools.items():
        print(f"  - {name}: {tool.description[:50]}...")
    print()

    # Step 2: Initialize DeepSeek LLM
    llm = DeepSeekLLM(
        api_key=api_key, model="deepseek-chat", base_url="https://api.deepseek.com"
    )
    print("Step 2: Initialized DeepSeek LLM")
    print()

    # Step 3: Load skill from YAML
    skill_path = "tests/fixtures/skills/weather_skill.yaml"
    agent = Skill.from_yaml(skill_path, available_tools, llm)

    print("Step 3: Loaded skill from YAML")
    print(f"  - Name: {agent.name}")
    print(f"  - Max iterations: {agent.max_iterations}")
    print(f"  - Tools: {', '.join(agent.tools.keys())}")
    print(f"  - System prompt: {agent.system_prompt[:60]}...")
    print()

    # Step 4: Run the agent on a task with verbose mode
    task = "What's the weather like in Tokyo and Shanghai? Also tell me the temperature in Berlin."
    print(f"Step 4: Running agent on task:")
    print(f"  '{task}'")
    print()

    print("Agent is working...")
    print()
    response = agent.run(task, verbose=True)

    # Step 5: Display results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Success: {response.success}")
    print(f"Iterations: {response.iterations}")
    print(f"\nAgent Response:")
    print("-" * 60)
    print(response.content)
    print("-" * 60)


if __name__ == "__main__":
    main()
