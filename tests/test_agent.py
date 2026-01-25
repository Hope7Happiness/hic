"""
Tests for Agent functionality.

Test cases:
1. test_agent_with_three_tools - Main test with python_exec, file_write, file_search
2. test_agent_parsing_and_execution
3. test_agent_max_iterations
4. test_agent_with_subagent
5. test_agent_with_skill - Test agent loaded from YAML skill
"""

import os
import pytest
from unittest.mock import Mock, MagicMock
from agent.llm import LLM
from agent.tool import Tool
from agent.agent import Agent
from agent.skill import Skill
from agent.schemas import AgentResponse
from tests.test_utils import (
    python_exec,
    file_write,
    file_search,
    get_weather,
    get_temperature,
)


def test_agent_with_three_tools():
    """
    Test agent with three tools: python_exec, file_write, file_search.

    This test uses a mock LLM to simulate the agent using the correct tool.
    It verifies that the agent can:
    1. Parse LLM output correctly
    2. Execute the right tool with correct arguments
    3. Handle tool responses
    """
    # Create the three tools
    tool1 = Tool(python_exec)
    tool2 = Tool(file_write)
    tool3 = Tool(file_search)

    # Create mock LLM that will simulate tool usage
    mock_llm = Mock(spec=LLM)

    # Simulate LLM responses:
    # 1. First response: decide to use python_exec
    # 2. Second response: finish with result
    mock_llm.chat.side_effect = [
        # First call: LLM decides to execute Python code
        """Thought: I need to calculate 5 + 3 using Python.
Action: tool
Tool: python_exec
Arguments: {"code": "print(5 + 3)"}""",
        # Second call: LLM receives observation and finishes
        """Thought: The calculation is complete.
Action: finish
Response: The result is 8.""",
    ]
    mock_llm.reset_history = Mock()
    mock_llm.get_history = Mock(return_value=[])

    # Create agent with the three tools
    agent = Agent(llm=mock_llm, tools=[tool1, tool2, tool3], max_iterations=5)

    # Run agent
    response = agent.run("Calculate 5 + 3 using Python")

    # Verify response
    assert response.success is True
    assert "8" in response.content
    assert response.iterations == 2

    # Verify LLM was called correctly
    assert mock_llm.chat.call_count == 2


def test_agent_file_operations():
    """
    Test agent using file_write and file_search tools.
    """
    tool_write = Tool(file_write)
    tool_search = Tool(file_search)

    # Mock LLM
    mock_llm = Mock(spec=LLM)
    mock_llm.chat.side_effect = [
        # Write a file
        """Thought: I'll write a test file.
Action: tool
Tool: file_write
Arguments: {"path": "/tmp/test_agent_file.txt", "content": "Hello World"}""",
        # Search for the file
        """Thought: Now I'll search for .txt files.
Action: tool
Tool: file_search
Arguments: {"pattern": "*.txt", "directory": "/tmp"}""",
        # Finish
        """Thought: File operations completed.
Action: finish
Response: File created and found successfully.""",
    ]
    mock_llm.reset_history = Mock()
    mock_llm.get_history = Mock(return_value=[])

    # Create agent
    agent = Agent(llm=mock_llm, tools=[tool_write, tool_search], max_iterations=5)

    # Run agent
    response = agent.run("Create a test file and search for it")

    # Verify
    assert response.success is True
    assert response.iterations == 3

    # Cleanup
    if os.path.exists("/tmp/test_agent_file.txt"):
        os.remove("/tmp/test_agent_file.txt")


def test_agent_max_iterations():
    """
    Test that agent respects max_iterations limit.
    """

    def dummy_tool(x: int) -> int:
        """A dummy tool."""
        return x * 2

    tool = Tool(dummy_tool)

    # Mock LLM that never finishes (always returns tool action)
    mock_llm = Mock(spec=LLM)
    mock_llm.chat.return_value = """Thought: I'll use the tool again.
Action: tool
Tool: dummy_tool
Arguments: {"x": 5}"""
    mock_llm.reset_history = Mock()
    mock_llm.get_history = Mock(return_value=[])

    # Create agent with low max_iterations
    agent = Agent(llm=mock_llm, tools=[tool], max_iterations=3)

    # Run agent
    response = agent.run("Keep using the tool")

    # Should hit max iterations and return a summary
    assert response.iterations == 3
    assert mock_llm.chat.call_count >= 3


def test_agent_tool_not_found():
    """
    Test agent handling of non-existent tool.
    """

    def sample_tool(x: int) -> int:
        """A sample tool."""
        return x

    tool = Tool(sample_tool)

    # Mock LLM that tries to use a non-existent tool
    mock_llm = Mock(spec=LLM)
    mock_llm.chat.side_effect = [
        # Try to use non-existent tool
        """Thought: I'll use a tool that doesn't exist.
Action: tool
Tool: nonexistent_tool
Arguments: {"x": 5}""",
        # Finish after receiving error
        """Thought: The tool doesn't exist.
Action: finish
Response: Tool not found.""",
    ]
    mock_llm.reset_history = Mock()
    mock_llm.get_history = Mock(return_value=[])

    # Create agent
    agent = Agent(llm=mock_llm, tools=[tool], max_iterations=5)

    # Run agent
    response = agent.run("Use a nonexistent tool")

    # Verify that agent handled the error
    assert response.success is True
    assert mock_llm.chat.call_count == 2


def test_agent_with_subagent():
    """
    Test agent delegating to a subagent.
    """

    # Create a simple tool for the subagent
    def subagent_tool(x: int) -> int:
        """Subagent's tool."""
        return x * 10

    tool = Tool(subagent_tool)

    # Mock LLM for subagent
    subagent_llm = Mock(spec=LLM)
    subagent_llm.chat.side_effect = [
        """Thought: I'll use my tool.
Action: tool
Tool: subagent_tool
Arguments: {"x": 5}""",
        """Thought: Done.
Action: finish
Response: Subagent completed: result is 50.""",
    ]
    subagent_llm.reset_history = Mock()
    subagent_llm.get_history = Mock(return_value=[])

    # Create subagent
    subagent = Agent(llm=subagent_llm, tools=[tool], name="SubAgent")

    # Mock LLM for parent agent
    parent_llm = Mock(spec=LLM)
    parent_llm.chat.side_effect = [
        # Delegate to subagent
        """Thought: I'll delegate this to my subagent.
Action: subagent
Agent: SubAgent
Task: Calculate 5 * 10""",
        # Finish after subagent completes
        """Thought: Subagent completed the task.
Action: finish
Response: Final result from subagent: 50.""",
    ]
    parent_llm.reset_history = Mock()
    parent_llm.get_history = Mock(return_value=[])

    # Create parent agent with subagent
    parent_agent = Agent(
        llm=parent_llm, subagents={"SubAgent": subagent}, name="ParentAgent"
    )

    # Run parent agent
    response = parent_agent.run("Delegate calculation to subagent")

    # Verify
    assert response.success is True
    assert "50" in response.content
    assert parent_llm.chat.call_count == 2
    assert subagent_llm.chat.call_count == 2


def test_agent_parse_retry():
    """
    Test that agent retries parsing on format errors.
    """

    def dummy_tool(x: int) -> int:
        """Dummy tool."""
        return x

    tool = Tool(dummy_tool)

    # Mock LLM that returns bad format first, then good format
    mock_llm = Mock(spec=LLM)
    mock_llm.chat.side_effect = [
        # Bad format (no Action field)
        "I think I should do something",
        # Good format after error feedback
        """Thought: Let me use the tool properly.
Action: tool
Tool: dummy_tool
Arguments: {"x": 5}""",
        # Finish
        """Thought: Done.
Action: finish
Response: Completed.""",
    ]
    mock_llm.reset_history = Mock()
    mock_llm.get_history = Mock(return_value=[])

    # Create agent
    agent = Agent(llm=mock_llm, tools=[tool], max_iterations=5)

    # Run agent
    response = agent.run("Test parse retry")

    # Should successfully complete after retry
    assert response.success is True
    # At least 3 calls: initial + retry + finish
    assert mock_llm.chat.call_count >= 3


def test_agent_with_skill():
    """
    Test agent loaded from YAML skill configuration.

    This test verifies that:
    1. Skills can be loaded from YAML files
    2. Agents created from skills work correctly
    3. Tools specified in the skill are properly loaded
    """
    # Create tools dictionary with weather tools
    available_tools = {
        "get_weather": Tool(get_weather),
        "get_temperature": Tool(get_temperature),
        "python_exec": Tool(python_exec),
    }

    # Mock LLM
    mock_llm = Mock(spec=LLM)
    mock_llm.chat.side_effect = [
        # First call: use get_weather tool
        """Thought: I'll check the weather for Tokyo.
Action: tool
Tool: get_weather
Arguments: {"city": "Tokyo"}""",
        # Second call: use get_temperature tool
        """Thought: Now let me get the temperature for London.
Action: tool
Tool: get_temperature
Arguments: {"city": "London"}""",
        # Third call: finish with summary
        """Thought: I have all the weather information.
Action: finish
Response: Tokyo is rainy at 18°C, and London is at 15°C.""",
    ]
    mock_llm.reset_history = Mock()
    mock_llm.get_history = Mock(return_value=[])

    # Load skill from YAML
    yaml_path = "tests/fixtures/skills/weather_skill.yaml"
    agent = Skill.from_yaml(yaml_path, available_tools, mock_llm)

    # Verify agent was configured correctly from YAML
    assert agent.name == "weather_assistant"
    assert agent.max_iterations == 8
    assert len(agent.tools) == 2
    assert "get_weather" in agent.tools
    assert "get_temperature" in agent.tools
    assert "weather assistant" in agent.system_prompt.lower()

    # Run the agent
    response = agent.run("What's the weather in Tokyo and the temperature in London?")

    # Verify execution
    assert response.success is True
    assert response.iterations == 3
    assert "Tokyo" in response.content or "rainy" in response.content.lower()
    assert "London" in response.content or "15" in response.content

    # Verify LLM was called the expected number of times
    assert mock_llm.chat.call_count == 3
