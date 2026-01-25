"""
Callback system for agent observability and extensibility.

This module provides:
1. AgentCallback base class - Define custom event handlers
2. Built-in callbacks - Console logging, file logging, metrics
3. Event hooks - Track agent execution in real-time

Usage:
    from agent import Agent, ConsoleCallback, MetricsCallback

    agent = Agent(
        llm=llm,
        tools=tools,
        callbacks=[ConsoleCallback(verbose=True), MetricsCallback()]
    )

    response = agent.run("task")
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import json


class AgentCallback(ABC):
    """
    Abstract base class for agent callbacks.

    Callbacks receive notifications about agent execution events:
    - Iteration lifecycle (start, end)
    - LLM interactions (request, response)
    - Tool executions (call, result)
    - Errors and retries
    - Agent completion

    Override methods to implement custom behavior.
    """

    def on_agent_start(self, task: str, agent_name: str):
        """Called when agent starts executing a task."""
        pass

    def on_iteration_start(self, iteration: int, agent_name: str):
        """Called at the start of each iteration."""
        pass

    def on_llm_request(
        self, iteration: int, prompt: str, system_prompt: Optional[str] = None
    ):
        """Called before sending a request to the LLM."""
        pass

    def on_llm_response(self, iteration: int, response: str):
        """Called after receiving a response from the LLM."""
        pass

    def on_parse_success(
        self, iteration: int, action_type: str, details: Dict[str, Any]
    ):
        """Called after successfully parsing LLM output."""
        pass

    def on_parse_error(self, iteration: int, error: str, retry_count: int):
        """Called when parsing LLM output fails."""
        pass

    def on_tool_call(self, iteration: int, tool_name: str, arguments: Dict[str, Any]):
        """Called before executing a tool."""
        pass

    def on_tool_result(
        self, iteration: int, tool_name: str, result: str, success: bool
    ):
        """Called after tool execution completes."""
        pass

    def on_subagent_call(self, iteration: int, agent_name: str, task: str):
        """Called before delegating to a subagent."""
        pass

    def on_subagent_result(self, iteration: int, agent_name: str, result: str):
        """Called after subagent completes."""
        pass

    def on_iteration_end(self, iteration: int, action_type: str):
        """Called at the end of each iteration."""
        pass

    def on_agent_finish(self, success: bool, iterations: int, content: str):
        """Called when agent completes execution."""
        pass

    def on_error(self, error: Exception, context: Dict[str, Any]):
        """Called when an unexpected error occurs."""
        pass


class ConsoleCallback(AgentCallback):
    """
    Built-in callback that logs agent execution to console.

    Args:
        verbose: If True, logs all events. If False, only logs major events.
        show_prompts: If True, includes full prompts in output.
        show_responses: If True, includes full LLM responses in output.
        color: If True, uses ANSI color codes for formatting.
    """

    def __init__(
        self,
        verbose: bool = False,
        show_prompts: bool = False,
        show_responses: bool = True,
        color: bool = True,
    ):
        self.verbose = verbose
        self.show_prompts = show_prompts
        self.show_responses = show_responses
        self.color = color
        self._start_time = None

    def _log(self, message: str, level: str = "INFO"):
        """Helper to print formatted log messages."""
        if self.color:
            colors = {
                "INFO": "\033[36m",  # Cyan
                "SUCCESS": "\033[32m",  # Green
                "WARNING": "\033[33m",  # Yellow
                "ERROR": "\033[31m",  # Red
                "RESET": "\033[0m",
            }
            color_code = colors.get(level, "")
            reset = colors["RESET"]
            print(f"{color_code}{message}{reset}")
        else:
            print(message)

    def on_agent_start(self, task: str, agent_name: str):
        self._start_time = datetime.now()
        self._log(f"\n{'=' * 80}", "INFO")
        self._log(f"🚀 Agent '{agent_name}' Starting", "INFO")
        self._log(f"{'=' * 80}", "INFO")
        self._log(f"📋 Task: {task}", "INFO")
        self._log(f"🕐 Started: {self._start_time.strftime('%H:%M:%S')}", "INFO")

    def on_iteration_start(self, iteration: int, agent_name: str):
        if self.verbose:
            self._log(f"\n{'─' * 80}", "INFO")
            self._log(f"🔄 Iteration {iteration}", "INFO")
            self._log(f"{'─' * 80}", "INFO")

    def on_llm_request(
        self, iteration: int, prompt: str, system_prompt: Optional[str] = None
    ):
        if self.verbose and self.show_prompts:
            self._log(f"\n💬 Prompt to LLM:", "INFO")
            self._log(f"   {prompt[:200]}{'...' if len(prompt) > 200 else ''}", "INFO")

    def on_llm_response(self, iteration: int, response: str):
        if self.show_responses:
            self._log(f"\n🧠 LLM Response:", "INFO")
            lines = response.split("\n")
            for line in lines[:10]:  # Show first 10 lines
                self._log(f"   {line}", "INFO")
            if len(lines) > 10:
                self._log(f"   ... ({len(lines) - 10} more lines)", "INFO")

    def on_parse_success(
        self, iteration: int, action_type: str, details: Dict[str, Any]
    ):
        if self.verbose:
            self._log(f"✅ Parsed action: {action_type}", "SUCCESS")

    def on_parse_error(self, iteration: int, error: str, retry_count: int):
        self._log(f"⚠️  Parse error (retry {retry_count}): {error[:100]}", "WARNING")

    def on_tool_call(self, iteration: int, tool_name: str, arguments: Dict[str, Any]):
        self._log(f"\n🔧 Calling tool: {tool_name}", "INFO")
        if self.verbose:
            args_str = json.dumps(arguments, indent=2)
            self._log(f"   Arguments: {args_str}", "INFO")

    def on_tool_result(
        self, iteration: int, tool_name: str, result: str, success: bool
    ):
        result_preview = result[:150] + "..." if len(result) > 150 else result
        if success:
            self._log(f"✅ Tool result: {result_preview}", "SUCCESS")
        else:
            self._log(f"❌ Tool failed: {result_preview}", "ERROR")

    def on_subagent_call(self, iteration: int, agent_name: str, task: str):
        self._log(f"\n🤖 Delegating to subagent: {agent_name}", "INFO")
        self._log(f"   Task: {task[:100]}{'...' if len(task) > 100 else ''}", "INFO")

    def on_subagent_result(self, iteration: int, agent_name: str, result: str):
        result_preview = result[:150] + "..." if len(result) > 150 else result
        self._log(f"✅ Subagent completed: {result_preview}", "SUCCESS")

    def on_agent_finish(self, success: bool, iterations: int, content: str):
        elapsed = (
            (datetime.now() - self._start_time).total_seconds()
            if self._start_time
            else 0
        )

        self._log(f"\n{'=' * 80}", "INFO")
        self._log(f"🏁 Agent Finished", "SUCCESS" if success else "ERROR")
        self._log(f"{'=' * 80}", "INFO")
        self._log(f"✅ Success: {success}", "SUCCESS" if success else "ERROR")
        self._log(f"🔄 Iterations: {iterations}", "INFO")
        self._log(f"⏱️  Time: {elapsed:.2f}s", "INFO")
        self._log(f"\n📝 Final Result:", "INFO")
        self._log(f"{'─' * 80}", "INFO")
        for line in content.split("\n")[:20]:
            self._log(f"   {line}", "INFO")
        self._log(f"{'─' * 80}", "INFO")

    def on_error(self, error: Exception, context: Dict[str, Any]):
        self._log(f"\n❌ Error: {str(error)}", "ERROR")
        if self.verbose:
            self._log(f"   Context: {context}", "ERROR")


class MetricsCallback(AgentCallback):
    """
    Built-in callback that collects execution metrics.

    Tracks:
    - Total iterations
    - Tool usage counts
    - Success/failure rates
    - Execution time
    - Parse error counts
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset all metrics."""
        self.start_time = None
        self.end_time = None
        self.total_iterations = 0
        self.tool_calls = {}  # tool_name -> count
        self.tool_successes = {}  # tool_name -> count
        self.tool_failures = {}  # tool_name -> count
        self.parse_errors = 0
        self.llm_requests = 0
        self.subagent_calls = {}  # agent_name -> count

    def on_agent_start(self, task: str, agent_name: str):
        self.start_time = datetime.now()

    def on_iteration_start(self, iteration: int, agent_name: str):
        self.total_iterations = iteration

    def on_llm_request(
        self, iteration: int, prompt: str, system_prompt: Optional[str] = None
    ):
        self.llm_requests += 1

    def on_parse_error(self, iteration: int, error: str, retry_count: int):
        self.parse_errors += 1

    def on_tool_call(self, iteration: int, tool_name: str, arguments: Dict[str, Any]):
        self.tool_calls[tool_name] = self.tool_calls.get(tool_name, 0) + 1

    def on_tool_result(
        self, iteration: int, tool_name: str, result: str, success: bool
    ):
        if success:
            self.tool_successes[tool_name] = self.tool_successes.get(tool_name, 0) + 1
        else:
            self.tool_failures[tool_name] = self.tool_failures.get(tool_name, 0) + 1

    def on_subagent_call(self, iteration: int, agent_name: str, task: str):
        self.subagent_calls[agent_name] = self.subagent_calls.get(agent_name, 0) + 1

    def on_agent_finish(self, success: bool, iterations: int, content: str):
        self.end_time = datetime.now()

    def get_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics as a dictionary."""
        elapsed = (
            (self.end_time - self.start_time).total_seconds()
            if self.start_time and self.end_time
            else 0
        )

        return {
            "execution_time_seconds": elapsed,
            "total_iterations": self.total_iterations,
            "llm_requests": self.llm_requests,
            "parse_errors": self.parse_errors,
            "tool_calls": dict(self.tool_calls),
            "tool_successes": dict(self.tool_successes),
            "tool_failures": dict(self.tool_failures),
            "subagent_calls": dict(self.subagent_calls),
        }

    def print_summary(self):
        """Print a formatted summary of metrics."""
        metrics = self.get_metrics()

        print("\n" + "=" * 80)
        print("📊 EXECUTION METRICS")
        print("=" * 80)
        print(f"⏱️  Execution Time: {metrics['execution_time_seconds']:.2f}s")
        print(f"🔄 Total Iterations: {metrics['total_iterations']}")
        print(f"💬 LLM Requests: {metrics['llm_requests']}")
        print(f"⚠️  Parse Errors: {metrics['parse_errors']}")

        if metrics["tool_calls"]:
            print(f"\n🔧 Tool Usage:")
            for tool_name, count in metrics["tool_calls"].items():
                successes = metrics["tool_successes"].get(tool_name, 0)
                failures = metrics["tool_failures"].get(tool_name, 0)
                success_rate = (successes / count * 100) if count > 0 else 0
                print(f"   {tool_name}: {count} calls ({success_rate:.0f}% success)")

        if metrics["subagent_calls"]:
            print(f"\n🤖 Subagent Calls:")
            for agent_name, count in metrics["subagent_calls"].items():
                print(f"   {agent_name}: {count} calls")

        print("=" * 80)


class FileLoggerCallback(AgentCallback):
    """
    Built-in callback that logs agent execution to a file.

    Args:
        log_file: Path to the log file
        format: Log format ('text' or 'json')
    """

    def __init__(self, log_file: str, format: str = "text"):
        self.log_file = log_file
        self.format = format
        self.logs = []

    def _write_log(self, event: str, data: Dict[str, Any]):
        """Write a log entry."""
        timestamp = datetime.now().isoformat()
        log_entry = {"timestamp": timestamp, "event": event, "data": data}
        self.logs.append(log_entry)

        # Write to file
        with open(self.log_file, "a") as f:
            if self.format == "json":
                f.write(json.dumps(log_entry) + "\n")
            else:
                f.write(f"[{timestamp}] {event}: {data}\n")

    def on_agent_start(self, task: str, agent_name: str):
        self._write_log("agent_start", {"task": task, "agent_name": agent_name})

    def on_iteration_start(self, iteration: int, agent_name: str):
        self._write_log(
            "iteration_start", {"iteration": iteration, "agent_name": agent_name}
        )

    def on_llm_response(self, iteration: int, response: str):
        self._write_log(
            "llm_response", {"iteration": iteration, "response": response[:500]}
        )

    def on_tool_call(self, iteration: int, tool_name: str, arguments: Dict[str, Any]):
        self._write_log(
            "tool_call",
            {"iteration": iteration, "tool_name": tool_name, "arguments": arguments},
        )

    def on_tool_result(
        self, iteration: int, tool_name: str, result: str, success: bool
    ):
        self._write_log(
            "tool_result",
            {
                "iteration": iteration,
                "tool_name": tool_name,
                "success": success,
                "result": result[:200],
            },
        )

    def on_agent_finish(self, success: bool, iterations: int, content: str):
        self._write_log(
            "agent_finish",
            {"success": success, "iterations": iterations, "content": content[:500]},
        )
