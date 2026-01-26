"""
Pydantic schemas for type-safe data validation.

This module defines all the data models used in the async agent framework:
- AgentStatus: Enum for agent execution states
- LaunchedSubagent: Info about a launched subagent
- AgentState: Complete serializable state of an agent
- AgentMessage: Messages between agents
- Action: Represents an action the LLM wants to take
- AgentResponse: The final response from an agent
"""

from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field
from dataclasses import dataclass, field
from enum import Enum
import time


class AgentStatus(Enum):
    """Agent execution status"""

    IDLE = "idle"
    RUNNING = "running"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class LaunchedSubagent:
    """Information about a launched subagent"""

    name: str
    id: str
    task: str
    status: str  # "running", "completed", "failed"
    start_time: float
    end_time: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class AgentState:
    """Complete serializable state of an agent"""

    agent_id: str
    task: str
    iteration: int
    llm_history: List[Dict[str, str]]
    launched_subagents: List[LaunchedSubagent]  # All launched
    pending_subagents: Dict[str, LaunchedSubagent]  # Not yet completed
    completed_results: Dict[str, Any]  # Completed results
    context: Dict[str, Any]  # Additional context


@dataclass
class AgentMessage:
    """Message between agents"""

    type: str  # "subagent_completed", "subagent_failed"
    from_agent: str
    to_agent: str
    payload: Dict[str, Any]
    priority: int = 0
    timestamp: float = field(default_factory=time.time)

    def __lt__(self, other):
        """For PriorityQueue sorting (higher priority first)"""
        return self.priority > other.priority


class Action(BaseModel):
    """Represents an action parsed from LLM output."""

    type: Literal["tool", "launch_subagents", "wait_for_subagents", "finish"] = Field(
        ..., description="Type of action to take"
    )

    # For tool
    tool_name: Optional[str] = Field(None, description="Tool name (if type='tool')")
    arguments: Optional[Dict[str, Any]] = Field(None, description="Tool arguments")

    # For launch_subagents
    agents: Optional[List[str]] = Field(
        None, description="List of agent names to launch"
    )
    tasks: Optional[List[str]] = Field(None, description="List of tasks for each agent")

    # For finish
    content: Optional[str] = Field(None, description="Final response content")

    # Optional thought
    thought: Optional[str] = Field(None, description="LLM's reasoning")

    def model_post_init(self, __context: Any) -> None:
        """Validate action has required fields"""
        if self.type == "tool":
            if self.tool_name is None:
                raise ValueError("tool_name is required when type='tool'")
        elif self.type == "launch_subagents":
            if not self.agents or not self.tasks:
                raise ValueError(
                    "agents and tasks are required when type='launch_subagents'"
                )
            if len(self.agents) != len(self.tasks):
                raise ValueError("agents and tasks must have the same length")
            if len(self.agents) == 0:
                raise ValueError("Cannot launch zero subagents")
        elif self.type == "finish":
            if self.content is None:
                raise ValueError("content is required when type='finish'")


class AgentResponse(BaseModel):
    """Final response from an agent execution."""

    content: str = Field(..., description="The agent's final output")
    iterations: int = Field(..., description="Number of iterations executed")
    success: bool = Field(
        default=True, description="Whether the agent completed successfully"
    )


# Legacy classes for backward compatibility (not used in async mode)
class ToolCall(BaseModel):
    """Legacy: Represents a tool invocation."""

    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class SubAgentCall(BaseModel):
    """Legacy: Represents a subagent invocation."""

    agent_name: str
    task: str


class SkillConfig(BaseModel):
    """Configuration for a skill loaded from YAML."""

    name: str
    description: str
    tools: List[str] = Field(default_factory=list)
    subagents: Dict[str, str] = Field(default_factory=dict)
    system_prompt: Optional[str] = None
    max_iterations: int = Field(default=10)
