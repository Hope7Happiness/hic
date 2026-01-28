"""
Agent core logic - Async version.

This module provides the Agent class that:
1. Manages tools and subagents
2. Executes multi-turn iterations with the LLM
3. Parses LLM output and executes actions
4. Supports async execution with parallel subagent launching
5. Manages execution context for tools
"""

import asyncio
import time
import os
import sys
from typing import Dict, List, Optional, Any
from agent.llm import LLM
from agent.tool import Tool
from agent.parser import OutputParser, ParseError
from agent.schemas import (
    AgentResponse,
    Action,
    AgentState,
    LaunchedSubagent,
    AgentMessage,
)
from agent.callbacks import AgentCallback


class Agent:
    """
    Core agent that can use tools and delegate to subagents.

    The agent runs in a loop:
    1. Send prompt to LLM with available tools/subagents
    2. Parse LLM output into an Action
    3. Execute the action (tool, launch_subagents, wait, send_message, or finish)
    4. Add result to history and continue

    Key async features:
    - launch_subagents: Instantly launches subagents (non-blocking)
    - wait: Suspends agent until receiving messages or subagent completion
    - Subagent completion triggers agent resumption
    """

    def __init__(
        self,
        llm: LLM,
        tools: Optional[List[Tool]] = None,
        subagents: Optional[Dict[str, "Agent"]] = None,
        allowed_peers: Optional[List[str]] = None,
        max_iterations: int = 10,
        system_prompt: Optional[str] = None,
        name: Optional[str] = None,
        callbacks: Optional[List[AgentCallback]] = None,
        working_directory: Optional[str] = None,
    ):
        """
        Initialize an agent.

        Args:
            llm: LLM instance for chat completion
            tools: List of Tool objects this agent can use
            subagents: Dict mapping subagent names to Agent instances
            allowed_peers: List of peer agent names this agent can send messages to
            max_iterations: Maximum number of iterations before forcing completion
            system_prompt: Custom system prompt (uses default if None)
            name: Name of this agent (for debugging/logging)
            callbacks: List of callbacks for observability/logging
            working_directory: Working directory for tool execution (defaults to current dir)
        """
        self.llm = llm
        self.tools = {tool.name: tool for tool in (tools or [])}
        self.subagents = subagents or {}
        self.allowed_peers = allowed_peers or []
        self.max_iterations = max_iterations
        self.name = name or "Agent"
        self.callbacks = callbacks or []

        # Create context for tool execution
        # Import here to avoid circular dependency and __init__.py issues
        import importlib.util
        import sys
        from pathlib import Path

        def load_context_module():
            """Load context module directly to avoid import issues."""
            agent_dir = Path(__file__).parent
            context_path = agent_dir / "context.py"

            if "agent.context" in sys.modules:
                return sys.modules["agent.context"]

            spec = importlib.util.spec_from_file_location("agent.context", context_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load context module from {context_path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules["agent.context"] = module
            spec.loader.exec_module(module)
            return module

        context_mod = load_context_module()
        self.context = context_mod.create_auto_approve_context(
            patterns={
                "bash": ["*"],
                "read": ["*"],
                "write": ["*"],
                "delete": ["*"],
                "network": ["*"],
                "webfetch": ["*"],
                "question": ["*"],
                "execute": ["*"],
            },
            working_directory=working_directory or ".",
        )

        # Register tools with context
        self.tools = {}
        for tool in tools or []:
            tool.context = self.context  # Inject context into tool
            self.tools[tool.name] = tool

        # If no tools provided, register default builtin tools (bash, read, write, edit)
        if not self.tools:
            try:
                from agent.tools import bash, restricted_bash, read, write, edit
                from agent.tool import Tool

                default_tools = [
                    Tool(bash, context=self.context),
                    Tool(restricted_bash, context=self.context),
                    Tool(read, context=self.context),
                    Tool(write, context=self.context),
                    Tool(edit, context=self.context),
                ]

                for tool in default_tools:
                    self.tools[tool.name] = tool
            except Exception:
                # If imports fail, keep existing tools
                pass

        self.subagents = subagents or {}

        # Build system prompt
        if system_prompt is None:
            self.system_prompt = self._build_default_system_prompt()
        else:
            self.system_prompt = system_prompt

    def _debug_llm_call(
        self,
        agent_id: Optional[str] = None,
        prompt_preview: Optional[str] = None,
        prompt_type: str = "LLM",
    ):
        """Print/log a marker before each LLM call with prompt preview."""
        if os.environ.get("DEBUG_LLM_CALLS", "0") == "0":
            return

        preview = (prompt_preview or "").replace("\n", " ").strip()
        if len(preview) > 120:
            preview = preview[:117] + "..."
        if preview:
            message = f"🧠 调用LLM({prompt_type})，如果卡住了代表LLM被rate limit | Prompt: {preview}"
        else:
            message = "🧠 调用LLM，如果卡住了代表LLM被rate limit"

        try:
            from agent.async_logger import get_logger, LogLevel

            logger = get_logger()
            if logger:
                loop = asyncio.get_running_loop()
                target_id = agent_id or self.name
                loop.create_task(logger.log(LogLevel.INFO, target_id, message, "LLM"))
                return
        except Exception:
            pass

        print(
            f"[{self.name}] [LLM] {message}",
            file=sys.stderr,
            flush=True,
        )

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

        # Add available peers (for communication)
        if self.allowed_peers:
            prompt_parts.append("\n\nAvailable peers (you can send messages to them):")
            for peer_name in self.allowed_peers:
                prompt_parts.append(f"  - {peer_name}")

        # Add format instruction
        prompt_parts.append(f"\n\n{OutputParser.get_format_instruction()}")

        return "".join(prompt_parts)

    def run(self, task: str) -> AgentResponse:
        """
        Execute a task by iterating with the LLM (sync wrapper for async execution).

        Args:
            task: The task description from the user

        Returns:
            AgentResponse with the final output
        """
        # Run async method in event loop
        return asyncio.run(self._run_async(task))

    async def _run_async(self, task: str) -> AgentResponse:
        """Async implementation of run()"""
        # Auto-initialize AsyncLogger if not already initialized
        try:
            from agent.async_logger import get_logger

            logger = get_logger()
            # Check if logger is started, if not, start it
            if not logger._running:
                await logger.start()
        except Exception:
            pass  # Logger initialization failed, continue without it

        # Register with orchestrator
        from agent.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()
        agent_id = await orchestrator.register_agent(self)

        # Start orchestrator message processing in background
        processing_task = asyncio.create_task(orchestrator.start_message_processing())

        # Run the agent (may suspend/resume multiple times)
        asyncio.create_task(self._internal_run(task, agent_id))

        # Wait for true completion (not just suspension)
        result = await orchestrator.wait_for_completion(agent_id)

        # Stop message processing
        orchestrator.stop_processing()
        processing_task.cancel()
        try:
            await processing_task
        except asyncio.CancelledError:
            pass

        return result

    async def _internal_run(self, task: str, agent_id: str) -> AgentResponse:
        """
        Main execution loop (called by orchestrator or run()).

        Args:
            task: The task to execute
            agent_id: ID of this agent instance

        Returns:
            AgentResponse with final result
        """
        # Log agent start
        try:
            from agent.async_logger import get_logger

            logger = get_logger()
            tool_names = list(self.tools.keys())
            await logger.agent_start(agent_id, task, self.system_prompt, tool_names)
        except Exception:
            pass  # Logger not initialized

        # Notify callbacks: agent start
        for callback in self.callbacks:
            callback.on_agent_start(task, self.name)

        # Reset LLM history for fresh start
        self.llm.reset_history()

        # State tracking
        iteration = 0
        launched_subagents: List[LaunchedSubagent] = []
        pending_subagents: Dict[str, LaunchedSubagent] = {}
        completed_results: Dict[str, Any] = {}

        # Notify callbacks: LLM request
        for callback in self.callbacks:
            callback.on_llm_request(iteration, task, self.system_prompt)

        # Log the first LLM request
        try:
            from agent.async_logger import get_logger

            logger = get_logger()
            await logger.llm_first_request(agent_id, task)
        except Exception:
            pass

        # Send initial task with system prompt (sync call wrapped in executor)
        # Wrap in try-except to handle LLM errors (e.g., 429 rate limit)
        try:
            loop = asyncio.get_event_loop()
            self._debug_llm_call(
                agent_id, "<system prompt hidden>" + task, "initial_task"
            )
            llm_output = await loop.run_in_executor(
                None, self.llm.chat, task, self.system_prompt
            )
        except Exception as e:
            # Log the error
            try:
                from agent.async_logger import get_logger, LogLevel

                logger = get_logger()
                await logger.log(
                    LogLevel.ERROR,
                    agent_id,
                    f"❌ LLM call failed: {str(e)[:200]}",
                    "AGENT",
                )
            except Exception:
                pass

            # Return error response - orchestrator will handle notifying parent
            error_msg = f"LLM call failed: {str(e)}"
            response = AgentResponse(
                content=error_msg,
                iterations=iteration,
                success=False,
            )
            # Notify callbacks: agent finish
            for callback in self.callbacks:
                callback.on_agent_finish(False, iteration, error_msg)

            # Re-raise so orchestrator can catch and send subagent_failed message
            raise Exception(error_msg) from e

        # Notify callbacks: LLM response
        for callback in self.callbacks:
            callback.on_llm_response(iteration, llm_output)

        # Check and perform compaction if needed (Checkpoint 1: After initial LLM response)
        try:
            from agent.compaction import check_and_compact

            compacted = await check_and_compact(self.llm, agent_id)
            if compacted is not None:
                self.llm.set_history(compacted)
        except Exception as e:
            # Compaction failed - log and continue with original history
            try:
                from agent.async_logger import get_logger, LogLevel

                logger = get_logger()
                await logger.log(
                    LogLevel.WARNING, agent_id, f"Compaction error: {e}", "COMPACTION"
                )
            except Exception:
                pass

        while iteration < self.max_iterations:
            iteration += 1

            # Notify callbacks: iteration start
            for callback in self.callbacks:
                callback.on_iteration_start(iteration, self.name)

            # Try to parse LLM output (with retries)
            action = await self._parse_with_retry(llm_output, iteration, 3, agent_id)

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
            action_details: Dict[str, Any] = {"type": action.type}
            if action.type == "tool":
                action_details["tool_name"] = action.tool_name
                action_details["arguments"] = action.arguments
            elif action.type == "launch_subagents":
                action_details["agents"] = action.agents
                action_details["tasks"] = action.tasks

            for callback in self.callbacks:
                callback.on_parse_success(iteration, action.type, action_details)

            # Log agent thought and action (for root agent only)
            try:
                from agent.async_logger import get_logger

                logger = get_logger()
                if logger.agent_levels.get(agent_id, 0) == 0:
                    # Log thought first (if present)
                    if action.thought:
                        await logger.agent_thought(agent_id, action.thought)

                    # Then log action decision
                    if action.type == "tool":
                        await logger.agent_action(
                            agent_id, "tool", f"Calling {action.tool_name}"
                        )
                    elif action.type == "launch_subagents":
                        agents_str = ", ".join(action.agents or [])
                        await logger.agent_action(
                            agent_id, "launch_subagents", f"Agents: {agents_str}"
                        )
                    elif action.type == "wait":
                        await logger.agent_action(
                            agent_id, "wait", "Waiting for messages/subagents"
                        )
                    elif action.type == "finish":
                        preview = (action.content or "")[:50]
                        await logger.agent_action(
                            agent_id, "finish", f"Result: {preview}"
                        )
            except Exception:
                pass

            # Execute action based on type
            if action.type == "finish":
                # Agent decided to finish
                response = AgentResponse(
                    content=action.content or "",
                    iterations=iteration,
                    success=True,
                )
                # Notify callbacks: agent finish
                for callback in self.callbacks:
                    callback.on_agent_finish(True, iteration, response.content)

                # Notify callbacks: iteration end
                for callback in self.callbacks:
                    callback.on_iteration_end(iteration, action.type)

                # Mark as completed in orchestrator
                from agent.orchestrator import AgentOrchestrator

                orchestrator = AgentOrchestrator()
                await orchestrator.mark_agent_completed(agent_id, response)

                # Log agent finish
                try:
                    from agent.async_logger import get_logger

                    logger = get_logger()
                    await logger.agent_finish(agent_id, True, response.content)
                except Exception:
                    pass

                return response

            elif action.type == "tool":
                # Execute tool
                observation = await self._execute_tool(action, iteration, agent_id)

                # Notify callbacks and send tool result with clear marker
                tool_result_msg = (
                    f"[TOOL RESULT from {action.tool_name}]\n{observation}"
                )
                for callback in self.callbacks:
                    callback.on_llm_request(iteration, tool_result_msg, None)

                self._debug_llm_call(agent_id, tool_result_msg, "tool_result")
                llm_output = await loop.run_in_executor(
                    None, lambda: self.llm.chat(tool_result_msg)
                )

                # Notify callbacks: LLM response
                for callback in self.callbacks:
                    callback.on_llm_response(iteration, llm_output)

                # Check and perform compaction if needed (After tool execution)
                try:
                    from agent.compaction import check_and_compact

                    compacted = await check_and_compact(self.llm, agent_id)
                    if compacted is not None:
                        self.llm.set_history(compacted)
                except Exception as e:
                    # Compaction failed - log and continue with original history
                    try:
                        from agent.async_logger import get_logger, LogLevel

                        logger = get_logger()
                        await logger.log(
                            LogLevel.WARNING,
                            agent_id,
                            f"Compaction error: {e}",
                            "COMPACTION",
                        )
                    except Exception:
                        pass

            elif action.type == "launch_subagents":
                # Launch subagents (instant, non-blocking)
                result = await self._launch_subagents(
                    action,
                    iteration,
                    agent_id,
                    launched_subagents,
                    pending_subagents,
                )

                # Notify callbacks: LLM request
                for callback in self.callbacks:
                    callback.on_llm_request(iteration, result, None)

                self._debug_llm_call(agent_id, result, "launch_subagents")
                llm_output = await loop.run_in_executor(None, self.llm.chat, result)

                # Notify callbacks: LLM response
                for callback in self.callbacks:
                    callback.on_llm_response(iteration, llm_output)

                # Check and perform compaction if needed (After launching subagents)
                try:
                    from agent.compaction import check_and_compact

                    compacted = await check_and_compact(self.llm, agent_id)
                    if compacted is not None:
                        self.llm.set_history(compacted)
                except Exception as e:
                    # Compaction failed - log and continue with original history
                    try:
                        from agent.async_logger import get_logger, LogLevel

                        logger = get_logger()
                        await logger.log(
                            LogLevel.WARNING,
                            agent_id,
                            f"Compaction error: {e}",
                            "COMPACTION",
                        )
                    except Exception:
                        pass

            elif action.type == "send_message":
                # Send a message to a peer agent
                observation = await self._execute_send_message(action, agent_id)

                # Notify callbacks: LLM request
                for callback in self.callbacks:
                    callback.on_llm_request(
                        iteration, f"Observation: {observation}", None
                    )

                self._debug_llm_call(agent_id, observation, "peer_message")
                llm_output = await loop.run_in_executor(
                    None, self.llm.chat, f"Observation: {observation}"
                )

                # Notify callbacks: LLM response
                for callback in self.callbacks:
                    callback.on_llm_response(iteration, llm_output)

                # Check and perform compaction if needed (Checkpoint 2: After LLM call in main loop)
                try:
                    from agent.compaction import check_and_compact

                    compacted = await check_and_compact(self.llm, agent_id)
                    if compacted is not None:
                        self.llm.set_history(compacted)
                except Exception as e:
                    # Compaction failed - log and continue with original history
                    try:
                        from agent.async_logger import get_logger, LogLevel

                        logger = get_logger()
                        await logger.log(
                            LogLevel.WARNING,
                            agent_id,
                            f"Compaction error: {e}",
                            "COMPACTION",
                        )
                    except Exception:
                        pass

            elif action.type == "wait":
                # Save state and suspend again
                state = AgentState(
                    agent_id=agent_id,
                    task=task,
                    iteration=iteration,
                    llm_history=self.llm.get_history(),
                    launched_subagents=launched_subagents,
                    pending_subagents=pending_subagents,
                    completed_results=completed_results,
                    context={},
                )

                from agent.orchestrator import AgentOrchestrator

                orchestrator = AgentOrchestrator()
                await orchestrator.save_agent_state(agent_id, state)
                await orchestrator.check_queued_messages(agent_id)

                # Log agent suspended (console only for root agent)
                try:
                    from agent.async_logger import get_logger

                    logger = get_logger()
                    pending_names = list(pending_subagents.keys())
                    await logger.agent_suspended(
                        agent_id, f"Waiting for: {', '.join(pending_names)}"
                    )
                except Exception:
                    pass

                # Notify callbacks: agent suspended
                for callback in self.callbacks:
                    callback.on_iteration_end(iteration, action.type)

                # Return early - will be resumed by orchestrator
                return AgentResponse(
                    content="Agent suspended, waiting for subagents",
                    iterations=iteration,
                    success=True,
                )

            # Notify callbacks: iteration end
            for callback in self.callbacks:
                callback.on_iteration_end(iteration, action.type)

        # Reached max iterations - force a summary
        summary_prompt = "You have reached the maximum number of iterations. Please provide a final summary of what you've accomplished."

        # Notify callbacks: LLM request
        for callback in self.callbacks:
            callback.on_llm_request(iteration, summary_prompt, None)

        self._debug_llm_call(agent_id, summary_prompt, "summary")
        llm_output = await loop.run_in_executor(None, self.llm.chat, summary_prompt)

        # Notify callbacks: LLM response
        for callback in self.callbacks:
            callback.on_llm_response(iteration, llm_output)

        response = AgentResponse(content=llm_output, iterations=iteration, success=True)

        # Notify callbacks: agent finish
        for callback in self.callbacks:
            callback.on_agent_finish(True, iteration, response.content)

        return response

    def _build_resume_prompt(self, state: AgentState, message: AgentMessage) -> str:
        """
        Build a prompt to resume the agent after suspension.

        Args:
            state: Current agent state
            message: Message that triggered resumption

        Returns:
            Resume prompt string
        """
        # Extract message details
        agent_name = message.payload.get("agent_name", "")

        if message.type == "subagent_completed":
            result = message.payload["result"]
            result_text = f"现在，agent '{agent_name}' 刚完成，结果为：{result}"
        elif message.type == "subagent_failed":
            error = message.payload["error"]
            result_text = f"现在，agent '{agent_name}' 执行失败，错误为：{error}"
        elif message.type == "peer_message":
            sender_name = message.payload.get("sender_name", "unknown")
            peer_message = message.payload.get("message", "")
            result_text = f"现在，你收到了来自 {sender_name} 的消息：{peer_message}"
        else:
            result_text = f"收到来自 agent '{agent_name}' 的消息"

        # Build status summary
        status_lines = ["\n当前状态："]
        for subagent in state.launched_subagents:
            if subagent.status == "completed":
                status_lines.append(
                    f"- {subagent.name}: ✅ 已完成，结果：{subagent.result}"
                )
            elif subagent.status == "failed":
                status_lines.append(
                    f"- {subagent.name}: ❌ 失败，错误：{subagent.error}"
                )
            elif subagent.status == "running":
                status_lines.append(f"- {subagent.name}: 🔄 运行中")

        status_text = "\n".join(status_lines)

        # Build options (include peer message option)
        options_text = """
你可以：
1. 使用已完成的结果调用 Tool
2. 启动新的子 Agent
3. 给 peer agent 发送消息（如果有 allowed_peers）
4. 继续等待其他子 Agent 或消息
5. 完成任务
"""

        return result_text + status_text + options_text

    async def _internal_resume(
        self, state: AgentState, message: AgentMessage
    ) -> AgentResponse:
        """
        Resume agent execution from saved state.

        Args:
            state: Saved agent state
            message: Message that triggered resumption

        Returns:
            AgentResponse with final result
        """
        # Restore state
        agent_id = state.agent_id
        iteration = state.iteration
        launched_subagents = state.launched_subagents
        pending_subagents = state.pending_subagents
        completed_results = state.completed_results

        # Restore LLM history
        self.llm.set_history(state.llm_history)

        # Build resume prompt
        resume_prompt = self._build_resume_prompt(state, message)

        # Log agent resumed
        try:
            from agent.async_logger import get_logger

            logger = get_logger()
            await logger.agent_resumed(agent_id, f"Resumed from {message.type}")
        except Exception:
            pass

        # Notify callbacks: LLM request
        for callback in self.callbacks:
            callback.on_llm_request(iteration, resume_prompt, None)

        # Get LLM response
        loop = asyncio.get_event_loop()
        self._debug_llm_call(agent_id, resume_prompt, "resume")
        llm_output = await loop.run_in_executor(None, self.llm.chat, resume_prompt)

        # Notify callbacks: LLM response
        for callback in self.callbacks:
            callback.on_llm_response(iteration, llm_output)

        # Check and perform compaction if needed (Checkpoint 3: After resume LLM call)
        try:
            from agent.compaction import check_and_compact

            compacted = await check_and_compact(self.llm, agent_id)
            if compacted is not None:
                self.llm.set_history(compacted)
        except Exception as e:
            # Compaction failed - log and continue with original history
            try:
                from agent.async_logger import get_logger, LogLevel

                logger = get_logger()
                await logger.log(
                    LogLevel.WARNING, agent_id, f"Compaction error: {e}", "COMPACTION"
                )
            except Exception:
                pass

        # Continue execution loop from where we left off
        while iteration < self.max_iterations:
            iteration += 1

            # Notify callbacks: iteration start
            for callback in self.callbacks:
                callback.on_iteration_start(iteration, self.name)

            # Parse LLM output
            action = await self._parse_with_retry(llm_output, iteration, 3, agent_id)

            if action is None:
                # Failed to parse
                response = AgentResponse(
                    content="Failed to parse LLM output after multiple attempts.",
                    iterations=iteration,
                    success=False,
                )
                for callback in self.callbacks:
                    callback.on_agent_finish(False, iteration, response.content)
                return response

            # Notify callbacks: parse success
            action_details: Dict[str, Any] = {"type": action.type}
            if action.type == "tool":
                action_details["tool_name"] = action.tool_name
                action_details["arguments"] = action.arguments
            elif action.type == "launch_subagents":
                action_details["agents"] = action.agents
                action_details["tasks"] = action.tasks

            for callback in self.callbacks:
                callback.on_parse_success(iteration, action.type, action_details)

            # Execute action
            if action.type == "finish":
                response = AgentResponse(
                    content=action.content or "",
                    iterations=iteration,
                    success=True,
                )
                for callback in self.callbacks:
                    callback.on_agent_finish(True, iteration, response.content)
                for callback in self.callbacks:
                    callback.on_iteration_end(iteration, action.type)

                # Mark as completed
                from agent.orchestrator import AgentOrchestrator

                orchestrator = AgentOrchestrator()
                await orchestrator.mark_agent_completed(agent_id, response)

                # Log finish
                try:
                    from agent.async_logger import get_logger

                    logger = get_logger()
                    await logger.agent_finish(agent_id, True, response.content)
                except Exception:
                    pass

                return response

            elif action.type == "tool":
                observation = await self._execute_tool(action, iteration, agent_id)

                # Notify callbacks and send tool result with clear marker
                tool_result_msg = (
                    f"[TOOL RESULT from {action.tool_name}]\n{observation}"
                )
                for callback in self.callbacks:
                    callback.on_llm_request(iteration, tool_result_msg, None)

                self._debug_llm_call(agent_id, tool_result_msg, "tool_result")

                llm_output = await loop.run_in_executor(
                    None, lambda: self.llm.chat(tool_result_msg)
                )
                for callback in self.callbacks:
                    callback.on_llm_response(iteration, llm_output)

            elif action.type == "launch_subagents":
                result = await self._launch_subagents(
                    action, iteration, agent_id, launched_subagents, pending_subagents
                )
                for callback in self.callbacks:
                    callback.on_llm_request(iteration, result, None)

                self._debug_llm_call(agent_id, result, "launch_subagents")
                llm_output = await loop.run_in_executor(None, self.llm.chat, result)
                for callback in self.callbacks:
                    callback.on_llm_response(iteration, llm_output)

            elif action.type == "send_message":
                observation = await self._execute_send_message(action, agent_id)
                for callback in self.callbacks:
                    callback.on_llm_request(
                        iteration, f"Observation: {observation}", None
                    )

                self._debug_llm_call(agent_id, observation, "peer_message")
                llm_output = await loop.run_in_executor(
                    None, self.llm.chat, f"Observation: {observation}"
                )
                for callback in self.callbacks:
                    callback.on_llm_response(iteration, llm_output)

            elif action.type == "wait":
                # Save state and suspend again
                state = AgentState(
                    agent_id=agent_id,
                    task=state.task,
                    iteration=iteration,
                    llm_history=self.llm.get_history(),
                    launched_subagents=launched_subagents,
                    pending_subagents=pending_subagents,
                    completed_results=completed_results,
                    context={},
                )

                from agent.orchestrator import AgentOrchestrator

                orchestrator = AgentOrchestrator()
                await orchestrator.save_agent_state(agent_id, state)

                # Check queued messages
                await orchestrator.check_queued_messages(agent_id)

                # Log suspension
                try:
                    from agent.async_logger import get_logger

                    logger = get_logger()
                    pending_names = list(pending_subagents.keys())
                    await logger.agent_suspended(
                        agent_id,
                        f"Waiting for: {', '.join(pending_names) if pending_names else 'messages'}",
                    )
                except Exception:
                    pass

                for callback in self.callbacks:
                    callback.on_iteration_end(iteration, action.type)

                return AgentResponse(
                    content="Agent suspended, waiting for messages/subagents",
                    iterations=iteration,
                    success=True,
                )

            # Notify callbacks: iteration end
            for callback in self.callbacks:
                callback.on_iteration_end(iteration, action.type)

        # Max iterations reached
        summary_prompt = "You have reached the maximum number of iterations. Please provide a final summary."
        for callback in self.callbacks:
            callback.on_llm_request(iteration, summary_prompt, None)

        self._debug_llm_call(agent_id, summary_prompt, "summary")
        llm_output = await loop.run_in_executor(None, self.llm.chat, summary_prompt)
        for callback in self.callbacks:
            callback.on_llm_response(iteration, llm_output)

        response = AgentResponse(content=llm_output, iterations=iteration, success=True)
        for callback in self.callbacks:
            callback.on_agent_finish(True, iteration, response.content)

        return response

    async def _parse_with_retry(
        self,
        llm_output: str,
        iteration: int,
        max_retries: int = 3,
        agent_id: Optional[str] = None,
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
        loop = asyncio.get_event_loop()

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

                    self._debug_llm_call(agent_id, error_msg, "parse_retry")
                    llm_output = await loop.run_in_executor(
                        None, self.llm.chat, error_msg
                    )

                    # Notify callbacks: LLM response
                    for callback in self.callbacks:
                        callback.on_llm_response(iteration, llm_output)
                else:
                    # Final attempt failed
                    return None

        return None

    async def _execute_tool(
        self, action: Action, iteration: int, agent_id: Optional[str] = None
    ) -> str:
        """
        Execute a tool and return the result.

        Args:
            action: Action containing tool call details
            iteration: Current iteration number
            agent_id: Agent ID for logging

        Returns:
            String representation of the tool result or error message
        """
        tool_name = action.tool_name

        if tool_name is None:
            result = "Error: No tool name provided"
            # Notify callbacks: tool result (failure)
            for callback in self.callbacks:
                callback.on_tool_result(iteration, "unknown", result, False)
            return result

        # Check if tool exists
        if tool_name not in self.tools:
            result = f"Error: Tool '{tool_name}' not found. Available tools: {list(self.tools.keys())}"
            # Notify callbacks: tool result (failure)
            for callback in self.callbacks:
                callback.on_tool_result(iteration, tool_name, result, False)
            return result

        # Notify callbacks: tool call
        for callback in self.callbacks:
            callback.on_tool_call(iteration, tool_name, action.arguments or {})

        # Log tool call (for all agents, but console only for root)
        if agent_id:
            try:
                from agent.async_logger import get_logger

                logger = get_logger()
                await logger.tool_call(agent_id, tool_name, action.arguments or {})
            except Exception:
                pass

        tool = self.tools[tool_name]

        # Execute tool (async with context injection)
        try:
            arguments = action.arguments or {}
            result = await tool.call_async(**arguments)
            result_str = str(result)

            # Notify callbacks: tool result (success)
            for callback in self.callbacks:
                callback.on_tool_result(iteration, tool_name, result_str, True)

            # Log tool result (for all agents, but console only for root)
            if agent_id:
                try:
                    from agent.async_logger import get_logger

                    logger = get_logger()
                    await logger.tool_result(agent_id, tool_name, result_str, True)
                except Exception:
                    pass

            return result_str
        except Exception as e:
            result = f"Error executing tool '{tool_name}': {str(e)}"

            # Notify callbacks: tool result (failure)
            for callback in self.callbacks:
                callback.on_tool_result(iteration, tool_name, result, False)

            # Log tool error (for all agents, but console only for root)
            if agent_id:
                try:
                    from agent.async_logger import get_logger

                    logger = get_logger()
                    await logger.tool_result(agent_id, tool_name, result, False)
                except Exception:
                    pass

            return result

    async def _execute_send_message(self, action: Action, agent_id: str) -> str:
        """
        Send a message to a peer agent.

        Args:
            action: Action containing recipient and message
            agent_id: ID of this agent

        Returns:
            Confirmation message or error
        """
        recipient = action.recipient
        message_content = action.message

        if message_content is None:
            return "❌ Message content is required for send_message"

        # Validate recipient
        if recipient not in self.allowed_peers:
            return f"❌ Cannot send message to '{recipient}'. Allowed peers: {self.allowed_peers}"

        # Get orchestrator
        from agent.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        # Find recipient agent ID
        recipient_id = orchestrator.find_agent_by_name(recipient, agent_id)
        if not recipient_id:
            return f"❌ Peer agent '{recipient}' not found or not registered"

        # Create peer message
        from agent.schemas import AgentMessage

        peer_message = AgentMessage(
            type="peer_message",
            from_agent=agent_id,
            to_agent=recipient_id,
            payload={
                "sender_name": self.name,
                "message": message_content,
            },
            priority=5,  # Medium priority (higher than subagent completion)
        )

        # Send through orchestrator
        await orchestrator.send_peer_message(peer_message)

        # Log message send
        try:
            from agent.async_logger import get_logger

            logger = get_logger()
            message_preview = message_content[:50]
            await logger.tool_result(
                agent_id,
                "send_message",
                f"Message sent to {recipient}: {message_preview}...",
                True,
            )
        except Exception:
            pass

        message_preview = message_content[:50]
        return f"✅ Message sent to {recipient}: {message_preview}..."

    async def _launch_subagents(
        self,
        action: Action,
        iteration: int,
        agent_id: str,
        launched_subagents: List[LaunchedSubagent],
        pending_subagents: Dict[str, LaunchedSubagent],
    ) -> str:
        """
        Launch multiple subagents (instant, non-blocking).

        Args:
            action: Action with agents and tasks lists
            iteration: Current iteration number
            agent_id: ID of this agent
            launched_subagents: List to track launched subagents
            pending_subagents: Dict to track pending subagents

        Returns:
            Confirmation message
        """
        agents = action.agents or []
        tasks = action.tasks or []

        if len(agents) == 0:
            return "Error: No subagents specified"

        if len(agents) != len(tasks):
            return f"Error: Agents and tasks lists have different lengths ({len(agents)} vs {len(tasks)})"

        from agent.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        launched_names = []

        for agent_name, task in zip(agents, tasks):
            # Check if subagent exists
            if agent_name not in self.subagents:
                return f"Error: Subagent '{agent_name}' not found. Available subagents: {list(self.subagents.keys())}"

            # Notify callbacks: subagent call
            for callback in self.callbacks:
                callback.on_subagent_call(iteration, agent_name, task)

            # Launch subagent (instant, non-blocking)
            subagent = self.subagents[agent_name]
            child_id = await orchestrator.launch_subagent(agent_id, subagent, task)

            # Log subagent launch (for root agent only)
            try:
                from agent.async_logger import get_logger

                logger = get_logger()
                if logger.agent_levels.get(agent_id, 0) == 0:
                    await logger.subagent_launch(agent_id, agent_name, task)
            except Exception:
                pass

            # Track launched subagent
            launched_info = LaunchedSubagent(
                name=agent_name,
                id=child_id,
                task=task,
                status="running",
                start_time=time.time(),
            )
            launched_subagents.append(launched_info)
            pending_subagents[agent_name] = launched_info
            launched_names.append(agent_name)

        return f"Successfully launched subagents: {', '.join(launched_names)}. They are running in parallel."
