"""
Parser for LLM text output.

This module parses the LLM's text output into structured Action objects.
The LLM is expected to follow this format:

For tool calls:
    Thought: <reasoning>
    Action: tool
    Tool: <tool_name>
    Arguments: {"key": "value", ...}

For subagent calls:
    Thought: <reasoning>
    Action: subagent
    Agent: <agent_name>
    Task: <task_description>

For finishing:
    Thought: <reasoning>
    Action: finish
    Response: <final_answer>
"""

import json
import re
from typing import Dict, Any, Optional
from agent.schemas import Action, ToolCall, SubAgentCall


class ParseError(Exception):
    """Raised when LLM output cannot be parsed."""

    pass


class OutputParser:
    """Parses LLM text output into Action objects."""

    @staticmethod
    def get_format_instruction() -> str:
        """Returns the format instruction to include in prompts."""
        return """
You must format your response EXACTLY as follows:

For using a tool:
Thought: <your reasoning>
Action: tool
Tool: <tool_name>
Arguments: <JSON dict of arguments>

For calling a subagent:
Thought: <your reasoning>
Action: subagent
Agent: <subagent_name>
Task: <task for the subagent>

For finishing:
Thought: <your reasoning>
Action: finish
Response: <your final answer>
""".strip()

    @staticmethod
    def parse(text: str) -> Action:
        """
        Parse LLM text output into an Action object.

        Args:
            text: Raw text output from the LLM

        Returns:
            Action object with parsed fields

        Raises:
            ParseError: If the text cannot be parsed
        """
        # Extract sections using regex
        thought_match = re.search(
            r"Thought:\s*(.+?)(?=\nAction:)", text, re.DOTALL | re.IGNORECASE
        )
        action_match = re.search(r"Action:\s*(\w+)", text, re.IGNORECASE)

        if not action_match:
            raise ParseError("Could not find 'Action:' in output")

        thought = thought_match.group(1).strip() if thought_match else None
        action_type = action_match.group(1).lower()

        if action_type not in ["tool", "subagent", "finish"]:
            raise ParseError(
                f"Invalid action type: {action_type}. Must be 'tool', 'subagent', or 'finish'"
            )

        # Parse based on action type
        if action_type == "tool":
            return OutputParser._parse_tool_action(text, thought)
        elif action_type == "subagent":
            return OutputParser._parse_subagent_action(text, thought)
        else:  # finish
            return OutputParser._parse_finish_action(text, thought)

    @staticmethod
    def _parse_tool_action(text: str, thought: Optional[str]) -> Action:
        """Parse a tool action."""
        tool_match = re.search(r"Tool:\s*(.+?)(?=\n|$)", text, re.IGNORECASE)
        args_match = re.search(
            r"Arguments:\s*(\{.+?\})", text, re.DOTALL | re.IGNORECASE
        )

        if not tool_match:
            raise ParseError("Tool action requires 'Tool:' field")

        tool_name = tool_match.group(1).strip()

        # Parse arguments as JSON
        if args_match:
            try:
                arguments = json.loads(args_match.group(1))
                if not isinstance(arguments, dict):
                    raise ParseError("Arguments must be a JSON object")
            except json.JSONDecodeError as e:
                raise ParseError(f"Invalid JSON in Arguments: {e}")
        else:
            arguments = {}

        return Action(
            type="tool",
            thought=thought,
            tool_call=ToolCall(tool_name=tool_name, arguments=arguments),
        )

    @staticmethod
    def _parse_subagent_action(text: str, thought: Optional[str]) -> Action:
        """Parse a subagent action."""
        agent_match = re.search(r"Agent:\s*(.+?)(?=\n|$)", text, re.IGNORECASE)
        task_match = re.search(
            r"Task:\s*(.+?)(?=\n\n|$)", text, re.DOTALL | re.IGNORECASE
        )

        if not agent_match:
            raise ParseError("Subagent action requires 'Agent:' field")
        if not task_match:
            raise ParseError("Subagent action requires 'Task:' field")

        agent_name = agent_match.group(1).strip()
        task = task_match.group(1).strip()

        return Action(
            type="subagent",
            thought=thought,
            subagent_call=SubAgentCall(agent_name=agent_name, task=task),
        )

    @staticmethod
    def _parse_finish_action(text: str, thought: Optional[str]) -> Action:
        """Parse a finish action."""
        response_match = re.search(r"Response:\s*(.+)", text, re.DOTALL | re.IGNORECASE)

        if not response_match:
            raise ParseError("Finish action requires 'Response:' field")

        response = response_match.group(1).strip()

        return Action(type="finish", thought=thought, response=response)
