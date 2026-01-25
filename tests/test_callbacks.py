"""
Tests for the callback system.

These tests verify that:
1. Callbacks receive the correct events
2. Multiple callbacks work simultaneously
3. Built-in callbacks (Console, Metrics, FileLogger) work correctly
4. Custom callbacks can be implemented
"""

import os
import tempfile
import json
from unittest.mock import Mock, MagicMock

from agent import (
    Agent,
    Tool,
    ConsoleCallback,
    MetricsCallback,
    FileLoggerCallback,
    AgentCallback,
)
from agent.llm import LLM


class MockLLM(LLM):
    """Mock LLM for testing callbacks."""

    def __init__(self, responses):
        super().__init__()
        self.responses = responses
        self.call_count = 0

    def chat(self, prompt, system_prompt=None):
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
        else:
            response = "Thought: Task complete\nAction: finish\nResponse: Done"

        # Add to history
        if not self.history and system_prompt:
            self.history.append({"role": "system", "content": system_prompt})
        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "assistant", "content": response})

        return response


def test_callback_receives_all_events():
    """Test that a custom callback receives all expected events."""

    # Create a mock callback
    callback = Mock(spec=AgentCallback)

    # Create a simple tool
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    tool = Tool(add)

    # Mock LLM that uses the tool
    llm = MockLLM(
        [
            'Thought: I\'ll add the numbers\nAction: tool\nTool: add\nArguments: {"a": 5, "b": 3}'
        ]
    )

    # Create agent with callback
    agent = Agent(llm=llm, tools=[tool], callbacks=[callback], name="TestAgent")

    # Run the agent
    response = agent.run("Add 5 and 3")

    # Verify callback was called with expected events
    callback.on_agent_start.assert_called_once()
    callback.on_iteration_start.assert_called()
    callback.on_llm_request.assert_called()
    callback.on_llm_response.assert_called()
    callback.on_parse_success.assert_called()
    callback.on_tool_call.assert_called_once()
    callback.on_tool_result.assert_called_once()
    callback.on_agent_finish.assert_called_once()

    # Verify agent_start was called with correct arguments
    args = callback.on_agent_start.call_args
    assert args[0][0] == "Add 5 and 3"
    assert args[0][1] == "TestAgent"

    # Verify tool_call was called with correct arguments
    args = callback.on_tool_call.call_args
    assert args[0][1] == "add"  # tool name
    assert args[0][2] == {"a": 5, "b": 3}  # arguments

    # Verify tool_result indicates success
    args = callback.on_tool_result.call_args
    assert args[0][1] == "add"  # tool name
    assert args[0][3] is True  # success


def test_metrics_callback_tracks_execution():
    """Test that MetricsCallback correctly tracks execution metrics."""

    # Create tools
    def multiply(a: int, b: int) -> int:
        """Multiply two numbers."""
        return a * b

    def divide(a: int, b: int) -> float:
        """Divide two numbers."""
        return a / b

    tool1 = Tool(multiply)
    tool2 = Tool(divide)

    # Mock LLM that uses both tools
    llm = MockLLM(
        [
            'Thought: First multiply\nAction: tool\nTool: multiply\nArguments: {"a": 6, "b": 3}',
            'Thought: Now divide\nAction: tool\nTool: divide\nArguments: {"a": 18, "b": 2}',
        ]
    )

    # Create agent with metrics callback
    metrics = MetricsCallback()
    agent = Agent(
        llm=llm,
        tools=[tool1, tool2],
        callbacks=[metrics],
    )

    # Run the agent
    response = agent.run("Multiply 6 by 3, then divide result by 2")

    # Get metrics
    metrics_data = metrics.get_metrics()

    # Verify metrics
    assert metrics_data["total_iterations"] >= 2
    assert metrics_data["llm_requests"] >= 2
    assert metrics_data["tool_calls"]["multiply"] == 1
    assert metrics_data["tool_calls"]["divide"] == 1
    assert metrics_data["tool_successes"]["multiply"] == 1
    assert metrics_data["tool_successes"]["divide"] == 1
    assert metrics_data["execution_time_seconds"] > 0


def test_multiple_callbacks_work_together():
    """Test that multiple callbacks can be used simultaneously."""

    # Create callbacks
    callback1 = Mock(spec=AgentCallback)
    callback2 = Mock(spec=AgentCallback)
    metrics = MetricsCallback()

    # Create a simple tool
    def square(x: int) -> int:
        """Square a number."""
        return x * x

    tool = Tool(square)

    # Mock LLM
    llm = MockLLM(
        ['Thought: Square the number\nAction: tool\nTool: square\nArguments: {"x": 5}']
    )

    # Create agent with multiple callbacks
    agent = Agent(
        llm=llm,
        tools=[tool],
        callbacks=[callback1, callback2, metrics],
    )

    # Run the agent
    response = agent.run("Square 5")

    # Verify all callbacks received events
    callback1.on_agent_start.assert_called_once()
    callback2.on_agent_start.assert_called_once()

    callback1.on_tool_call.assert_called_once()
    callback2.on_tool_call.assert_called_once()

    callback1.on_agent_finish.assert_called_once()
    callback2.on_agent_finish.assert_called_once()

    # Verify metrics were collected
    assert metrics.get_metrics()["tool_calls"]["square"] == 1


def test_file_logger_callback_writes_logs():
    """Test that FileLoggerCallback writes logs to file."""

    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
        log_file = f.name

    try:
        # Create file logger callback
        logger = FileLoggerCallback(log_file, format="json")

        # Create a simple tool
        def negate(x: int) -> int:
            """Negate a number."""
            return -x

        tool = Tool(negate)

        # Mock LLM
        llm = MockLLM(
            [
                'Thought: Negate the number\nAction: tool\nTool: negate\nArguments: {"x": 10}'
            ]
        )

        # Create agent with file logger
        agent = Agent(
            llm=llm,
            tools=[tool],
            callbacks=[logger],
        )

        # Run the agent
        response = agent.run("Negate 10")

        # Read the log file
        with open(log_file, "r") as f:
            logs = [json.loads(line) for line in f]

        # Verify logs were written
        assert len(logs) > 0

        # Verify log structure
        assert "timestamp" in logs[0]
        assert "event" in logs[0]
        assert "data" in logs[0]

        # Find specific events
        events = [log["event"] for log in logs]
        assert "agent_start" in events
        assert "tool_call" in events
        assert "tool_result" in events
        assert "agent_finish" in events

    finally:
        # Clean up
        if os.path.exists(log_file):
            os.remove(log_file)


def test_callback_receives_parse_errors():
    """Test that callbacks receive parse error events."""

    # Create a mock callback
    callback = Mock(spec=AgentCallback)

    # Mock LLM that returns invalid format (will cause parse error)
    llm = MockLLM(
        [
            "Invalid response format",  # This will trigger parse error
            "Thought: Fixed format\nAction: finish\nResponse: Done",  # Retry succeeds
        ]
    )

    # Create agent with callback
    agent = Agent(
        llm=llm,
        tools=[],
        callbacks=[callback],
    )

    # Run the agent
    response = agent.run("Do something")

    # Verify callback received parse error event
    callback.on_parse_error.assert_called()

    # Verify parse succeeded eventually
    callback.on_parse_success.assert_called()


def test_console_callback_prints_output(capsys):
    """Test that ConsoleCallback prints formatted output."""

    # Create console callback (without color for easier testing)
    console = ConsoleCallback(verbose=True, color=False)

    # Create a simple tool
    def echo(text: str) -> str:
        """Echo the input text."""
        return text

    tool = Tool(echo)

    # Mock LLM
    llm = MockLLM(
        [
            'Thought: Echo the message\nAction: tool\nTool: echo\nArguments: {"text": "hello"}'
        ]
    )

    # Create agent with console callback
    agent = Agent(llm=llm, tools=[tool], callbacks=[console], name="EchoAgent")

    # Run the agent
    response = agent.run("Echo 'hello'")

    # Capture output
    captured = capsys.readouterr()

    # Verify output contains expected elements
    assert "EchoAgent" in captured.out
    assert "Echo 'hello'" in captured.out or "Echo" in captured.out
    assert "Calling tool: echo" in captured.out
    assert "Agent Finished" in captured.out


def test_custom_callback_implementation():
    """Test that custom callbacks can be implemented and used."""

    class CustomCallback(AgentCallback):
        """Custom callback that tracks specific events."""

        def __init__(self):
            self.tool_calls = []
            self.iterations = 0

        def on_iteration_start(self, iteration, agent_name):
            self.iterations = iteration

        def on_tool_call(self, iteration, tool_name, arguments):
            self.tool_calls.append(
                {"iteration": iteration, "tool": tool_name, "args": arguments}
            )

    # Create custom callback
    custom = CustomCallback()

    # Create a simple tool
    def concat(a: str, b: str) -> str:
        """Concatenate two strings."""
        return a + b

    tool = Tool(concat)

    # Mock LLM
    llm = MockLLM(
        [
            'Thought: Concatenate\nAction: tool\nTool: concat\nArguments: {"a": "hello", "b": "world"}'
        ]
    )

    # Create agent with custom callback
    agent = Agent(
        llm=llm,
        tools=[tool],
        callbacks=[custom],
    )

    # Run the agent
    response = agent.run("Concatenate hello and world")

    # Verify custom callback tracked events
    assert custom.iterations >= 1
    assert len(custom.tool_calls) == 1
    assert custom.tool_calls[0]["tool"] == "concat"
    assert custom.tool_calls[0]["args"] == {"a": "hello", "b": "world"}
