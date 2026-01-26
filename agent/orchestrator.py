"""
Agent Orchestrator - Central coordination for async agent execution.

This module provides the AgentOrchestrator singleton that manages:
- Agent registration and lifecycle
- Subagent launching and callback handling
- Message queue for agent communication
- Agent state persistence and recovery
"""

import asyncio
import time
from typing import Dict, List, Optional, TYPE_CHECKING, Any
from collections import defaultdict
from agent.schemas import AgentStatus, AgentState, AgentMessage, LaunchedSubagent

if TYPE_CHECKING:
    from agent.agent import Agent


class AgentOrchestrator:
    """
    Singleton orchestrator for managing async agent execution.

    Handles:
    - Agent registration
    - Subagent launching (instant, non-blocking)
    - Message passing between agents
    - Agent suspension and resumption
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        # Core data structures
        self.agents: Dict[str, "Agent"] = {}
        self.agent_states: Dict[str, AgentState] = {}
        self.agent_status: Dict[str, AgentStatus] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.completion_events: Dict[
            str, asyncio.Event
        ] = {}  # For waiting on completion
        self.agent_results: Dict[str, Any] = {}  # Store final results

        # Message queue
        self.message_queue: asyncio.Queue = asyncio.Queue()

        # Relationship graph
        self.parent_child: Dict[str, List[str]] = defaultdict(list)
        self.child_parent: Dict[str, str] = {}

        # NEW: Peer communication
        self.agent_name_to_id: Dict[str, List[str]] = defaultdict(list)  # name -> [ids]
        self.peer_message_queues: Dict[str, List[AgentMessage]] = defaultdict(
            list
        )  # agent_id -> queued messages
        self.pending_state_messages: Dict[str, List[AgentMessage]] = defaultdict(
            list
        )  # Messages received before agent state is saved

        # Message processing
        self._processing = False
        self._start_time = time.time()
        self._processor_task = None

    def _status_label(self, status: Optional[AgentStatus]) -> str:
        """Return a human-readable label for an AgentStatus."""
        mapping = {
            AgentStatus.IDLE: "idle",
            AgentStatus.RUNNING: "running",
            AgentStatus.SUSPENDED: "wait",
            AgentStatus.COMPLETED: "completed",
            AgentStatus.FAILED: "failed",
        }
        return mapping.get(status, "unknown")

    def reset(self):
        """Reset the orchestrator (for testing)"""
        self.__init__.__wrapped__(self)
        self._initialized = False
        self.__init__()

    async def register_agent(self, agent: "Agent") -> str:
        """Register an agent and return its ID"""
        agent_id = f"{agent.name}_{id(agent)}"
        self.agents[agent_id] = agent
        self.agent_status[agent_id] = AgentStatus.IDLE
        self.completion_events[agent_id] = asyncio.Event()  # Create completion event

        # NEW: Register name mapping for peer communication
        self.agent_name_to_id[agent.name].append(agent_id)

        # Register with logger if available
        try:
            from agent.async_logger import get_logger

            logger = get_logger()
            parent_id = self.child_parent.get(agent_id)
            logger.register_agent(agent_id, agent.name, parent_id)
        except Exception:
            pass  # Logger not initialized, skip

        return agent_id

    async def launch_subagent(
        self, parent_id: str, child_agent: "Agent", task: str
    ) -> str:
        """
        Launch a subagent (returns immediately, doesn't wait).

        Args:
            parent_id: ID of the parent agent
            child_agent: The subagent to launch
            task: Task for the subagent

        Returns:
            child_id: ID of the launched subagent
        """
        # Register subagent
        child_id = await self.register_agent(child_agent)

        # Establish relationship
        self.parent_child[parent_id].append(child_id)
        self.child_parent[child_id] = parent_id

        # Re-register with logger to update parent relationship
        try:
            from agent.async_logger import get_logger

            logger = get_logger()
            logger.register_agent(child_id, child_agent.name, parent_id)
        except Exception:
            pass

        # Launch subagent asynchronously
        self.agent_status[child_id] = AgentStatus.RUNNING
        task_obj = asyncio.create_task(
            self._run_agent_with_callback(child_id, child_agent, task)
        )
        self.running_tasks[child_id] = task_obj

        return child_id

    async def _run_agent_with_callback(self, agent_id: str, agent: "Agent", task: str):
        """Run an agent and send a message to parent when done"""
        try:
            # Execute agent
            result = await agent._internal_run(task, agent_id)

            # Check if agent is suspended (not truly completed)
            current_status = self.agent_status.get(agent_id)
            if current_status == AgentStatus.SUSPENDED:
                # Agent is suspended (waiting), don't mark as completed
                return

        except Exception as e:
            # Notify parent on failure
            if agent_id in self.child_parent:
                parent_id = self.child_parent[agent_id]
                message = AgentMessage(
                    type="subagent_failed",
                    from_agent=agent_id,
                    to_agent=parent_id,
                    payload={"agent_name": agent.name, "error": str(e)},
                    priority=10,  # Higher priority for errors
                )
                await self.send_message(message)

            self.agent_status[agent_id] = AgentStatus.FAILED
            # Don't re-raise - we've already notified the parent via message
            # Re-raising would cause "Task exception was never retrieved" warnings

    async def send_message(self, message: AgentMessage):
        """Send a message to the queue"""
        await self.message_queue.put(message)

    async def start_message_processing(self):
        """Start the message processing loop"""
        if self._processing:
            return

        self._processing = True

        while self._processing:
            try:
                message = await self.message_queue.get()
                await self._handle_message(message)
            except Exception as e:
                print(f"Error processing message: {e}")
                import traceback

                traceback.print_exc()

    async def _handle_message(self, message: AgentMessage):
        """Handle a single message"""
        to_agent_id = message.to_agent
        agent = self.agents.get(to_agent_id)

        if not agent:
            print(f"Warning: Agent {to_agent_id} not found")
            return

        # Resume the parent agent
        await self._resume_agent(to_agent_id, agent, message)

    async def _resume_agent(self, agent_id: str, agent: "Agent", message: AgentMessage):
        """Resume an agent from suspended state"""
        # Load state
        state = self.agent_states.get(agent_id)
        if not state:
            # Agent hasn't saved its state yet (still running). Queue message.
            self.pending_state_messages[agent_id].append(message)
            return

        # Update state based on message type
        agent_name = message.payload.get("agent_name", "")

        if message.type == "peer_message":
            # Add peer message to state for agent to process
            state.peer_messages.append(message)
        elif message.type == "subagent_completed":
            result = message.payload["result"]
            state.completed_results[agent_name] = result
            if agent_name in state.pending_subagents:
                state.pending_subagents[agent_name].status = "completed"
                state.pending_subagents[agent_name].result = result
                state.pending_subagents[agent_name].end_time = time.time()
                del state.pending_subagents[agent_name]

        elif message.type == "subagent_failed":
            error = message.payload["error"]
            if agent_name in state.pending_subagents:
                state.pending_subagents[agent_name].status = "failed"
                state.pending_subagents[agent_name].error = error
                state.pending_subagents[agent_name].end_time = time.time()

        # Mark as running
        self.agent_status[agent_id] = AgentStatus.RUNNING

        # Resume execution (wrapped to handle exceptions)
        task = asyncio.create_task(
            self._resume_agent_with_error_handling(agent_id, agent, state, message)
        )
        self.running_tasks[agent_id] = task

    async def _resume_agent_with_error_handling(
        self, agent_id: str, agent: "Agent", state: AgentState, message: AgentMessage
    ):
        """Resume an agent with proper error handling"""
        try:
            result = await agent._internal_resume(state, message)
            # Agent will call mark_agent_completed itself on finish
            # We just return the result here
            return result

        except Exception as e:
            # Log the error
            try:
                from agent.async_logger import get_logger, LogLevel

                logger = get_logger()
                await logger.log(
                    LogLevel.ERROR,
                    agent_id,
                    f"❌ Agent failed during resume: {str(e)[:200]}",
                    "AGENT",
                )
            except Exception:
                pass

            # Create error response
            from agent.schemas import AgentResponse

            error_response = AgentResponse(
                content=f"Agent failed: {str(e)}",
                iterations=state.iteration,
                success=False,
            )

            # Mark as failed and signal completion with error result
            self.agent_status[agent_id] = AgentStatus.FAILED
            self.agent_results[agent_id] = error_response
            if agent_id in self.completion_events:
                self.completion_events[agent_id].set()

            # Don't re-raise to avoid "Task exception was never retrieved"

    async def save_agent_state(self, agent_id: str, state: AgentState):
        """Save agent state and mark as suspended"""
        self.agent_states[agent_id] = state
        self.agent_status[agent_id] = AgentStatus.SUSPENDED
        # Deliver any messages that arrived before the agent suspended
        pending_messages = self.pending_state_messages.get(agent_id)
        while pending_messages:
            message = pending_messages.pop(0)
            await self.send_message(message)
        if pending_messages == []:
            del self.pending_state_messages[agent_id]

    async def mark_agent_completed(self, agent_id: str, result: Any):
        """Mark agent as completed and signal completion event"""
        self.agent_status[agent_id] = AgentStatus.COMPLETED
        self.agent_results[agent_id] = result
        if agent_id in self.completion_events:
            self.completion_events[agent_id].set()

        # Notify parent if this is a subagent
        if agent_id in self.child_parent:
            parent_id = self.child_parent[agent_id]
            agent = self.agents.get(agent_id)
            agent_name = agent.name if agent else agent_id
            payload_result = getattr(result, "content", result)
            message = AgentMessage(
                type="subagent_completed",
                from_agent=agent_id,
                to_agent=parent_id,
                payload={"agent_name": agent_name, "result": payload_result},
                priority=0,
            )
            await self.send_message(message)

    async def wait_for_completion(self, agent_id: str) -> Any:
        """Wait for an agent to truly complete (not just suspend)"""
        if agent_id in self.completion_events:
            await self.completion_events[agent_id].wait()
            return self.agent_results.get(agent_id)

    def get_elapsed_time(self) -> float:
        """Get elapsed time since orchestrator started"""
        return time.time() - self._start_time

    def stop_processing(self):
        """Stop message processing"""
        self._processing = False

    def find_agent_by_name(self, agent_name: str, requester_id: str) -> Optional[str]:
        """
        Find agent ID by name (sibling agent with same parent).

        Args:
            agent_name: Name of the agent to find
            requester_id: ID of the requesting agent

        Returns:
            Agent ID if found and is a sibling, None otherwise
        """
        # Get requester's parent
        requester_parent = self.child_parent.get(requester_id)
        if not requester_parent:
            return None  # Requester has no parent

        # Find all agents with the target name
        candidate_ids = self.agent_name_to_id.get(agent_name, [])

        # Find the one with the same parent (sibling)
        for candidate_id in candidate_ids:
            if self.child_parent.get(candidate_id) == requester_parent:
                return candidate_id

        return None

    async def send_peer_message(self, message: AgentMessage):
        """
        Send a peer-to-peer message.

        If recipient is in SUSPENDED (wait) state, immediately wake them up.
        Otherwise, queue the message for later processing.
        """
        recipient_id = message.to_agent
        recipient_status = self.agent_status.get(recipient_id)

        sender_name = message.payload.get("sender_name", "unknown")
        message_content = message.payload.get("message", "")
        recipient_agent = self.agents.get(recipient_id)
        if recipient_agent:
            recipient_name = recipient_agent.name
        else:
            recipient_name = recipient_id
        status_label = self._status_label(recipient_status)

        # Debug logging
        try:
            from agent.async_logger import get_logger, LogLevel

            logger = get_logger()
            await logger.log(
                LogLevel.INFO,
                recipient_id,
                f"📨 [{sender_name} -> {recipient_name}]发送信息，对方状态是{status_label}，信息内容：{message_content}",
                "COMM",
            )
        except Exception:
            pass

        if recipient_status == AgentStatus.SUSPENDED:
            # Recipient is waiting - deliver immediately
            await self.send_message(message)

            # Log immediate delivery
            try:
                from agent.async_logger import get_logger, LogLevel

                logger = get_logger()
                await logger.log(
                    LogLevel.INFO,
                    recipient_id,
                    f"📬 [{sender_name} -> {recipient_name}]收到信息（立即送达），内容：{message_content}",
                    "COMM",
                )
            except Exception:
                pass
        else:
            # Recipient is busy - queue the message
            self.peer_message_queues[recipient_id].append(message)

            # Log queuing
            try:
                from agent.async_logger import get_logger, LogLevel

                logger = get_logger()
                await logger.log(
                    LogLevel.INFO,
                    recipient_id,
                    f"📥 [{sender_name} -> {recipient_name}]信息暂存在队列中，对方状态仍是{status_label}，内容：{message_content}",
                    "COMM",
                )
            except Exception:
                pass

    async def check_queued_messages(self, agent_id: str):
        """
        Check if there are queued peer messages and deliver the first one.

        Called when an agent enters wait state or completes a task.
        """
        queued_messages = self.peer_message_queues.get(agent_id, [])
        if queued_messages:
            # Deliver first queued message
            message = queued_messages.pop(0)
            await self.send_message(message)

            # Log delivery
            try:
                from agent.async_logger import get_logger, LogLevel

                logger = get_logger()
                sender_name = message.payload.get("sender_name", "unknown")
                message_content = message.payload.get("message", "")
                recipient_agent = self.agents.get(agent_id)
                if recipient_agent:
                    recipient_name = recipient_agent.name
                else:
                    recipient_name = agent_id
                await logger.log(
                    LogLevel.INFO,
                    agent_id,
                    f"📬 [{sender_name} -> {recipient_name}]收到信息（来自队列），内容：{message_content}",
                    "COMM",
                )
            except Exception:
                pass
