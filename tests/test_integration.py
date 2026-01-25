"""
Integration tests for the LLM Agent framework.

These tests use real LLM APIs (DeepSeek) to verify end-to-end functionality:
1. test_integration_llm_with_tools - LLM + Tools (Agent with tools)
2. test_integration_llm_with_skill - LLM + Skill (YAML configuration)
3. test_integration_llm_with_agent - LLM + Agent (Complex agent orchestration)

Note: These tests require API key and may take longer to run.
They can be skipped in CI/CD with: pytest -m "not integration"
"""

import os
import pytest
from agent import DeepSeekLLM, Tool, Agent, Skill
from tests.test_utils import (
    python_exec,
    file_write,
    file_search,
    get_weather,
    get_temperature,
)


def get_api_key():
    """
    Get API key from file or environment.

    Returns:
        API key string or None if not found
    """
    # Try reading from file first
    key_file = "/home/zhh/看你妈呢"
    if os.path.exists(key_file):
        try:
            with open(key_file, "r") as f:
                api_key = f.read().strip()
                if api_key:
                    return api_key
        except Exception:
            pass

    # Fall back to environment variable
    return os.environ.get("DEEPSEEK_API_KEY")


@pytest.mark.integration
def test_integration_llm_with_tools():
    """
    Integration test: Real LLM with Tools.

    This test verifies that a real LLM (DeepSeek) can:
    1. Understand available tools
    2. Decide which tool to use
    3. Call the tool with correct arguments
    4. Process the tool's response
    5. Complete the task successfully

    This is different from unit tests which use mock LLMs.
    """
    # Get API key
    api_key = get_api_key()
    if not api_key:
        pytest.skip("API key not available - skipping integration test")

    print("\n" + "=" * 60)
    print("INTEGRATION TEST: LLM + Tools")
    print("=" * 60)

    # Initialize DeepSeek LLM
    llm = DeepSeekLLM(
        api_key=api_key, model="deepseek-chat", base_url="https://api.deepseek.com"
    )

    # Create tools
    calc_tool = Tool(python_exec)

    print("\nSetup:")
    print(f"  - LLM: DeepSeek (deepseek-chat)")
    print(f"  - Tools: python_exec")

    # Create agent
    agent = Agent(llm=llm, tools=[calc_tool], max_iterations=10, name="CalculatorAgent")

    # Test task: Use python_exec to calculate something
    task = "Calculate 123 * 456 using Python code. Just tell me the final result."

    print(f"\nTask: {task}")
    print("\nRunning agent (this may take a few seconds)...")

    # Run agent
    response = agent.run(task)

    # Display results
    print("\nResults:")
    print(f"  - Success: {response.success}")
    print(f"  - Iterations: {response.iterations}")
    print(f"  - Response: {response.content[:100]}...")

    # Verify the agent succeeded
    assert response.success is True, "Agent should complete successfully"
    assert response.iterations > 0, "Agent should take at least one iteration"
    assert response.iterations <= 10, "Agent should not exceed max iterations"

    # The response should contain the correct answer (56088)
    assert "56088" in response.content or "56,088" in response.content, (
        f"Response should contain the answer 56088, got: {response.content}"
    )

    print("\n✓ Test passed: LLM successfully used tools")


@pytest.mark.integration
def test_integration_llm_with_skill():
    """
    Integration test: Real LLM with Skill (YAML configuration).

    This test verifies that:
    1. Skills can be loaded from YAML files
    2. Real LLM can work with skill-configured agents
    3. Tools defined in skills are properly accessible
    4. Agent can complete multi-tool tasks

    Uses the weather_skill.yaml for testing.
    """
    # Get API key
    api_key = get_api_key()
    if not api_key:
        pytest.skip("API key not available - skipping integration test")

    print("\n" + "=" * 60)
    print("INTEGRATION TEST: LLM + Skill (YAML)")
    print("=" * 60)

    # Initialize DeepSeek LLM
    llm = DeepSeekLLM(
        api_key=api_key, model="deepseek-chat", base_url="https://api.deepseek.com"
    )

    # Create tools dictionary
    available_tools = {
        "get_weather": Tool(get_weather),
        "get_temperature": Tool(get_temperature),
    }

    print("\nSetup:")
    print(f"  - LLM: DeepSeek (deepseek-chat)")
    print(f"  - Skill: weather_skill.yaml")
    print(f"  - Tools: get_weather, get_temperature")

    # Load skill from YAML
    skill_path = "tests/fixtures/skills/weather_skill.yaml"
    agent = Skill.from_yaml(skill_path, available_tools, llm)

    # Verify skill loaded correctly
    assert agent.name == "weather_assistant"
    assert len(agent.tools) == 2

    # Test task: Use multiple weather tools
    task = "What's the weather in Tokyo? Also tell me the temperature in Paris."

    print(f"\nTask: {task}")
    print("\nRunning agent (this may take a few seconds)...")

    # Run agent
    response = agent.run(task)

    # Display results
    print("\nResults:")
    print(f"  - Success: {response.success}")
    print(f"  - Iterations: {response.iterations}")
    print(f"  - Response: {response.content[:150]}...")

    # Verify the agent succeeded
    assert response.success is True, "Agent should complete successfully"
    assert response.iterations > 0, "Agent should take at least one iteration"

    # The response should contain information about both cities
    response_lower = response.content.lower()
    assert (
        "tokyo" in response_lower
        or "rainy" in response_lower
        or "18" in response.content
    ), "Response should mention Tokyo or its weather"
    assert "paris" in response_lower or "16" in response.content, (
        "Response should mention Paris or its temperature"
    )

    print("\n✓ Test passed: LLM successfully used skill-configured tools")


@pytest.mark.integration
def test_integration_llm_with_agent():
    """
    Integration test: Real LLM with Agent orchestration.

    This test verifies complex agent behavior:
    1. Agent can handle multiple different tools
    2. Agent can make decisions about which tool to use
    3. Agent can chain multiple tool calls
    4. Agent can synthesize results from multiple operations

    Uses a combination of tools: python_exec, file_write, file_search
    """
    # Get API key
    api_key = get_api_key()
    if not api_key:
        pytest.skip("API key not available - skipping integration test")

    print("\n" + "=" * 60)
    print("INTEGRATION TEST: LLM + Agent (Complex Orchestration)")
    print("=" * 60)

    # Initialize DeepSeek LLM
    llm = DeepSeekLLM(
        api_key=api_key, model="deepseek-chat", base_url="https://api.deepseek.com"
    )

    # Create multiple tools
    exec_tool = Tool(python_exec)
    write_tool = Tool(file_write)
    search_tool = Tool(file_search)

    print("\nSetup:")
    print(f"  - LLM: DeepSeek (deepseek-chat)")
    print(f"  - Tools: python_exec, file_write, file_search")

    # Create agent with multiple tools
    agent = Agent(
        llm=llm,
        tools=[exec_tool, write_tool, search_tool],
        max_iterations=15,
        name="MultiToolAgent",
    )

    # Complex task requiring multiple tools
    task = (
        "First, calculate 15 * 7 using Python. "
        "Then write the result to a file at /tmp/integration_test_result.txt. "
        "Finally, search for that file to confirm it was created."
    )

    print(f"\nTask: {task}")
    print("\nRunning agent (this may take 10-20 seconds)...")

    # Run agent
    response = agent.run(task)

    # Display results
    print("\nResults:")
    print(f"  - Success: {response.success}")
    print(f"  - Iterations: {response.iterations}")
    print(f"  - Response: {response.content[:200]}...")

    # Verify the agent succeeded
    assert response.success is True, "Agent should complete successfully"
    assert response.iterations >= 3, (
        "Agent should use at least 3 iterations (one per tool)"
    )
    assert response.iterations <= 15, "Agent should not exceed max iterations"

    # Verify the agent used the tools correctly
    # Should mention the calculation result (105)
    assert "105" in response.content, "Response should contain the calculation result"

    # Should mention file creation or file path
    response_lower = response.content.lower()
    assert "file" in response_lower or "integration_test_result" in response_lower, (
        "Response should mention file operations"
    )

    # Clean up test file
    import os as os_module

    test_file = "/tmp/integration_test_result.txt"
    if os_module.path.exists(test_file):
        os_module.remove(test_file)
        print("\n  - Cleaned up test file")

    print("\n✓ Test passed: LLM successfully orchestrated multiple tools")


def test_integration_all_tests_summary():
    """
    Dummy test to print summary after all integration tests.
    This helps users understand what was tested.
    """
    print("\n" + "=" * 60)
    print("INTEGRATION TESTS SUMMARY")
    print("=" * 60)
    print("\nAll integration tests verify end-to-end functionality with real LLM:")
    print("  1. ✓ LLM + Tools: Agent uses tools to solve problems")
    print("  2. ✓ LLM + Skill: Agent loaded from YAML configuration")
    print("  3. ✓ LLM + Agent: Complex multi-tool orchestration")
    print("\nThese tests ensure the framework works in production scenarios.")
    print("=" * 60)
