"""
Parser for LLM text output.

This module parses the LLM's text output into structured Action objects.

Supported action types:
1. tool - Call a tool with arguments
2. launch_subagents - Launch one or more subagents (non-blocking)
3. wait_for_subagents - Suspend and wait for subagents to complete
4. finish - Complete with final response
"""

import json
import re
from typing import List, Optional
from agent.schemas import Action


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

For launching subagents (can launch multiple at once):
Thought: <your reasoning>
Action: launch_subagents
Agents: ["agent_name_1", "agent_name_2", ...]
Tasks: ["task_1", "task_2", ...]

For sending a message to a peer agent:
Thought: <your reasoning>
Action: send_message
Recipient: <peer_agent_name>
Message: <your message content>

For waiting (suspends until receiving messages or subagent completions):
Thought: <your reasoning>
Action: wait

For finishing:
Thought: <your reasoning>
Action: finish
Content: <your final answer>

IMPORTANT: When you receive a message starting with "[TOOL RESULT from <tool_name>]", 
this is the output from a tool you called, NOT a user message. Trust this result and 
use it to continue your task. Do not ask the user about it or try to verify it again.
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
        # Extract thought and action type
        thought_match = re.search(
            r"Thought:\s*(.+?)(?=\nAction:)", text, re.DOTALL | re.IGNORECASE
        )
        action_match = re.search(r"Action:\s*([\w_]+)", text, re.IGNORECASE)

        if not action_match:
            raise ParseError("Could not find 'Action:' in output")

        thought = thought_match.group(1).strip() if thought_match else None
        action_type = action_match.group(1).lower()

        # Parse based on action type
        if action_type == "tool":
            return OutputParser._parse_tool_action(text, thought)
        elif action_type == "launch_subagents":
            return OutputParser._parse_launch_subagents_action(text, thought)
        elif (
            action_type == "wait" or action_type == "wait_for_subagents"
        ):  # Support both
            return OutputParser._parse_wait_action(text, thought)
        elif action_type == "send_message":
            return OutputParser._parse_send_message_action(text, thought)
        elif action_type == "finish":
            return OutputParser._parse_finish_action(text, thought)
        else:
            raise ParseError(
                f"Invalid action type: {action_type}. "
                f"Must be 'tool', 'launch_subagents', 'wait', 'send_message', or 'finish'"
            )

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
            type="tool", thought=thought, tool_name=tool_name, arguments=arguments
        )

    @staticmethod
    def _parse_launch_subagents_action(text: str, thought: Optional[str]) -> Action:
        """Parse a launch_subagents action."""
        # Extract Agents list
        agents_match = re.search(
            r"Agents:\s*\[(.*?)\]", text, re.DOTALL | re.IGNORECASE
        )
        # Extract Tasks list
        tasks_match = re.search(r"Tasks:\s*\[(.*?)\]", text, re.DOTALL | re.IGNORECASE)

        if not agents_match:
            raise ParseError("launch_subagents action requires 'Agents:' field")
        if not tasks_match:
            raise ParseError("launch_subagents action requires 'Tasks:' field")

        # Parse agents list
        agents_str = agents_match.group(1)
        agents = OutputParser._parse_string_list(agents_str)

        # Parse tasks list
        tasks_str = tasks_match.group(1)
        tasks = OutputParser._parse_string_list(tasks_str)

        if len(agents) == 0:
            raise ParseError("Cannot launch zero subagents")

        if len(agents) != len(tasks):
            raise ParseError(
                f"Agents and Tasks lists must have the same length "
                f"(got {len(agents)} agents and {len(tasks)} tasks)"
            )

        return Action(
            type="launch_subagents", thought=thought, agents=agents, tasks=tasks
        )

    @staticmethod
    def _parse_string_list(list_str: str) -> List[str]:
        """
        Parse a string list like '"item1", "item2"' into ["item1", "item2"].

        Also handles single quotes and mixed quotes.
        """
        # Try to parse as JSON first
        try:
            items = json.loads(f"[{list_str}]")
            if isinstance(items, list):
                return [str(item) for item in items]
        except:
            pass

        # Fallback: manual parsing
        # Find all quoted strings
        items = re.findall(r'["\']([^"\']+)["\']', list_str)

        if not items:
            raise ParseError(f"Could not parse list: {list_str}")

        return items

    @staticmethod
    def _parse_wait_action(text: str, thought: Optional[str]) -> Action:
        """Parse a wait action (replaces wait_for_subagents)."""
        return Action(type="wait", thought=thought)

    @staticmethod
    def _parse_send_message_action(text: str, thought: Optional[str]) -> Action:
        """Parse a send_message action."""
        recipient_match = re.search(r"Recipient:\s*(.+?)(?=\n|$)", text, re.IGNORECASE)
        message_match = re.search(r"Message:\s*(.+)", text, re.DOTALL | re.IGNORECASE)

        if not recipient_match:
            raise ParseError("send_message action requires 'Recipient:' field")
        if not message_match:
            raise ParseError("send_message action requires 'Message:' field")

        recipient = recipient_match.group(1).strip()
        message = message_match.group(1).strip()

        return Action(
            type="send_message",
            thought=thought,
            recipient=recipient,
            message=message,
        )

    @staticmethod
    def _parse_finish_action(text: str, thought: Optional[str]) -> Action:
        """Parse a finish action."""
        # Try "Content:" first, fallback to "Response:"
        content_match = re.search(
            r"(?:Content|Response):\s*(.+)", text, re.DOTALL | re.IGNORECASE
        )

        if not content_match:
            raise ParseError("Finish action requires 'Content:' or 'Response:' field")

        content = content_match.group(1).strip()

        return Action(type="finish", thought=thought, content=content)
