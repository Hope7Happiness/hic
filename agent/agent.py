"""
Agent core logic.

This module provides the Agent class that:
1. Manages tools and subagents
2. Executes multi-turn iterations with the LLM
3. Parses LLM output and executes actions
4. Handles errors and retries
"""

from typing import Dict, List, Optional
from agent.llm import LLM
from agent.tool import Tool
from agent.parser import OutputParser, ParseError
from agent.schemas import AgentResponse, Action
from agent.callbacks import AgentCallback


class Agent:
    """
    Core agent that can use tools and delegate to subagents.

    The agent runs in a loop:
    1. Send prompt to LLM with available tools/subagents
    2. Parse LLM output into an Action
    3. Execute the action (tool, subagent, or finish)
    4. Add result to history and continue
    """

    def __init__(
        self,
        llm: LLM,
        tools: Optional[List[Tool]] = None,
        subagents: Optional[Dict[str, "Agent"]] = None,
        max_iterations: int = 10,
        system_prompt: Optional[str] = None,
        name: Optional[str] = None,
        callbacks: Optional[List[AgentCallback]] = None,
    ):
        """
        Initialize an agent.

        Args:
            llm: LLM instance for chat completion
            tools: List of Tool objects this agent can use
            subagents: Dict mapping subagent names to Agent instances
            max_iterations: Maximum number of iterations before forcing completion
            system_prompt: Custom system prompt (uses default if None)
            name: Name of this agent (for debugging/logging)
            callbacks: List of callbacks for observability/logging
        """
        self.llm = llm
        self.tools = {tool.name: tool for tool in (tools or [])}
        self.subagents = subagents or {}
        self.max_iterations = max_iterations
        self.name = name or "Agent"
        self.callbacks = callbacks or []

        # Build system prompt
        if system_prompt is None:
            self.system_prompt = self._build_default_system_prompt()
        else:
            self.system_prompt = system_prompt

    def _build_default_system_prompt(self) -> str:
        """Build a concise default system prompt."""
        prompt_parts = ["You are a helpful assistant. Think step by step."]

        # Add available tools
        if self.tools:
            prompt_parts.append("\nAvailable tools:")
            for tool in self.tools.values():
                prompt_parts.append(f"\n{tool.to_schema()}")

        # Add available subagents
        if self.subagents:
            prompt_parts.append("\n\nAvailable subagents:")
            for agent_name in self.subagents:
                prompt_parts.append(f"  - {agent_name}")

        # Add format instruction
        prompt_parts.append(f"\n\n{OutputParser.get_format_instruction()}")

        return "".join(prompt_parts)

    def run(self, task: str, verbose: bool = False) -> AgentResponse:
        """
        Execute a task by iterating with the LLM.

        Args:
            task: The task description from the user
            verbose: If True, automatically adds a ColorfulConsoleCallback for detailed logging
                    with color-coded hierarchical output

        Returns:
            AgentResponse with the final output
        """
        # Add verbose callback if requested
        from agent.callbacks import ColorfulConsoleCallback

        original_callbacks = self.callbacks
        if verbose and not any(
            isinstance(cb, ColorfulConsoleCallback) for cb in self.callbacks
        ):
            # Add a colorful verbose console callback
            verbose_callback = ColorfulConsoleCallback(verbose=True)
            self.callbacks = self.callbacks + [verbose_callback]

        try:
            # Notify callbacks: agent start
            for callback in self.callbacks:
                callback.on_agent_start(task, self.name)

            # Reset LLM history for fresh start
            self.llm.reset_history()

            iteration = 0

            # Notify callbacks: LLM request
            for callback in self.callbacks:
                callback.on_llm_request(iteration, task, self.system_prompt)

            # Send initial task with system prompt
            llm_output = self.llm.chat(task, system_prompt=self.system_prompt)

            # Notify callbacks: LLM response
            for callback in self.callbacks:
                callback.on_llm_response(iteration, llm_output)

            while iteration < self.max_iterations:
                iteration += 1

                # Notify callbacks: iteration start
                for callback in self.callbacks:
                    callback.on_iteration_start(iteration, self.name)

                # Try to parse LLM output (with retries)
                action = self._parse_with_retry(llm_output, iteration)

                if action is None:
                    # Failed to parse after retries
                    response = AgentResponse(
                        content="Failed to parse LLM output after multiple attempts.",
                        iterations=iteration,
                        success=False,
                    )
                    # Notify callbacks: agent finish
                    for callback in self.callbacks:
                        callback.on_agent_finish(False, iteration, response.content)
                    return response

                # Notify callbacks: parse success
                action_details = {"type": action.type}
                if action.tool_call:
                    action_details["tool_name"] = action.tool_call.tool_name
                    action_details["arguments"] = action.tool_call.arguments
                elif action.subagent_call:
                    action_details["agent_name"] = action.subagent_call.agent_name
                    action_details["task"] = action.subagent_call.task

                for callback in self.callbacks:
                    callback.on_parse_success(iteration, action.type, action_details)

                # Execute action based on type
                if action.type == "finish":
                    # Agent decided to finish
                    response = AgentResponse(
                        content=action.response or "",
                        iterations=iteration,
                        success=True,
                    )
                    # Notify callbacks: agent finish
                    for callback in self.callbacks:
                        callback.on_agent_finish(True, iteration, response.content)

                    # Notify callbacks: iteration end
                    for callback in self.callbacks:
                        callback.on_iteration_end(iteration, action.type)

                    return response

                elif action.type == "tool":
                    # Execute tool
                    observation = self._execute_tool(action, iteration)

                    # Notify callbacks: LLM request
                    for callback in self.callbacks:
                        callback.on_llm_request(
                            iteration, f"Observation: {observation}", None
                        )

                    llm_output = self.llm.chat(f"Observation: {observation}")

                    # Notify callbacks: LLM response
                    for callback in self.callbacks:
                        callback.on_llm_response(iteration, llm_output)

                elif action.type == "subagent":
                    # Delegate to subagent
                    observation = self._execute_subagent(action, iteration)

                    # Notify callbacks: LLM request
                    for callback in self.callbacks:
                        callback.on_llm_request(
                            iteration, f"Subagent result: {observation}", None
                        )

                    llm_output = self.llm.chat(f"Subagent result: {observation}")

                    # Notify callbacks: LLM response
                    for callback in self.callbacks:
                        callback.on_llm_response(iteration, llm_output)

                # Notify callbacks: iteration end
                for callback in self.callbacks:
                    callback.on_iteration_end(iteration, action.type)

            # Reached max iterations - force a summary
            summary_prompt = "You have reached the maximum number of iterations. Please provide a final summary of what you've accomplished."

            # Notify callbacks: LLM request
            for callback in self.callbacks:
                callback.on_llm_request(iteration, summary_prompt, None)

            llm_output = self.llm.chat(summary_prompt)

            # Notify callbacks: LLM response
            for callback in self.callbacks:
                callback.on_llm_response(iteration, llm_output)

            response = AgentResponse(
                content=llm_output, iterations=iteration, success=True
            )

            # Notify callbacks: agent finish
            for callback in self.callbacks:
                callback.on_agent_finish(True, iteration, response.content)

            return response

        finally:
            # Restore original callbacks
            self.callbacks = original_callbacks

    def _parse_with_retry(
        self, llm_output: str, iteration: int, max_retries: int = 3
    ) -> Optional[Action]:
        """
        Try to parse LLM output with retries on failure.

        Args:
            llm_output: The LLM's text output
            iteration: Current iteration number
            max_retries: Maximum number of retry attempts

        Returns:
            Parsed Action or None if all retries failed
        """
        for attempt in range(max_retries):
            try:
                action = OutputParser.parse(llm_output)
                return action
            except (ParseError, ValueError) as e:
                # Notify callbacks: parse error
                for callback in self.callbacks:
                    callback.on_parse_error(iteration, str(e), attempt + 1)

                if attempt < max_retries - 1:
                    # Retry with error feedback
                    error_msg = f"Parse error: {str(e)}\n\nPlease follow the exact format:\n{OutputParser.get_format_instruction()}"

                    # Notify callbacks: LLM request
                    for callback in self.callbacks:
                        callback.on_llm_request(iteration, error_msg, None)

                    llm_output = self.llm.chat(error_msg)

                    # Notify callbacks: LLM response
                    for callback in self.callbacks:
                        callback.on_llm_response(iteration, llm_output)
                else:
                    # Final attempt failed
                    return None

        return None

    def _execute_tool(self, action: Action, iteration: int) -> str:
        """
        Execute a tool and return the result.

        Args:
            action: Action containing tool call details
            iteration: Current iteration number

        Returns:
            String representation of the tool result or error message
        """
        tool_call = action.tool_call
        if tool_call is None:
            result = "Error: No tool call information provided"
            # Notify callbacks: tool result (failure)
            for callback in self.callbacks:
                callback.on_tool_result(iteration, "unknown", result, False)
            return result

        tool_name = tool_call.tool_name

        # Check if tool exists
        if tool_name not in self.tools:
            result = f"Error: Tool '{tool_name}' not found. Available tools: {list(self.tools.keys())}"
            # Notify callbacks: tool result (failure)
            for callback in self.callbacks:
                callback.on_tool_result(iteration, tool_name, result, False)
            return result

        # Notify callbacks: tool call
        for callback in self.callbacks:
            callback.on_tool_call(iteration, tool_name, tool_call.arguments)

        tool = self.tools[tool_name]

        # Try to execute the tool
        try:
            result = tool.call(**tool_call.arguments)
            result_str = str(result)

            # Notify callbacks: tool result (success)
            for callback in self.callbacks:
                callback.on_tool_result(iteration, tool_name, result_str, True)

            return result_str
        except Exception as e:
            result = f"Error executing tool '{tool_name}': {str(e)}"

            # Notify callbacks: tool result (failure)
            for callback in self.callbacks:
                callback.on_tool_result(iteration, tool_name, result, False)

            return result

    def _execute_subagent(self, action: Action, iteration: int) -> str:
        """
        Delegate task to a subagent and return its summary.

        Args:
            action: Action containing subagent call details
            iteration: Current iteration number

        Returns:
            Summary from the subagent or error message
        """
        subagent_call = action.subagent_call
        if subagent_call is None:
            result = "Error: No subagent call information provided"
            for callback in self.callbacks:
                callback.on_subagent_result(iteration, "unknown", result)
            return result

        agent_name = subagent_call.agent_name

        # Check if subagent exists
        if agent_name not in self.subagents:
            result = f"Error: Subagent '{agent_name}' not found. Available subagents: {list(self.subagents.keys())}"
            for callback in self.callbacks:
                callback.on_subagent_result(iteration, agent_name, result)
            return result

        # Notify callbacks: subagent call
        for callback in self.callbacks:
            callback.on_subagent_call(iteration, agent_name, subagent_call.task)

        subagent = self.subagents[agent_name]

        # Run subagent and get its response
        try:
            response = subagent.run(subagent_call.task)

            # Return the subagent's summary
            result = f"Subagent '{agent_name}' completed the task. Summary: {response.content}"

            # Notify callbacks: subagent result
            for callback in self.callbacks:
                callback.on_subagent_result(iteration, agent_name, result)

            return result
        except Exception as e:
            result = f"Error running subagent '{agent_name}': {str(e)}"

            # Notify callbacks: subagent result
            for callback in self.callbacks:
                callback.on_subagent_result(iteration, agent_name, result)

            return result
