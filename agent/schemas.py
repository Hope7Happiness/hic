"""
Pydantic schemas for type-safe data validation.

This module defines all the data models used in the agent framework:
- ToolCall: Represents a call to a tool with arguments
- SubAgentCall: Represents a call to a subagent
- Action: Represents an action the LLM wants to take
- AgentResponse: The final response from an agent
- SkillConfig: Configuration for loading skills from YAML
"""

from typing import Literal, Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """Represents a tool invocation."""

    tool_name: str = Field(..., description="Name of the tool to call")
    arguments: Dict[str, Any] = Field(
        default_factory=dict, description="Arguments to pass to the tool"
    )


class SubAgentCall(BaseModel):
    """Represents a subagent invocation."""

    agent_name: str = Field(..., description="Name of the subagent to call")
    task: str = Field(..., description="Task description for the subagent")


class Action(BaseModel):
    """Represents an action parsed from LLM output."""

    type: Literal["tool", "subagent", "finish"] = Field(
        ..., description="Type of action to take"
    )
    tool_call: Optional[ToolCall] = Field(
        None, description="Tool call details (if type='tool')"
    )
    subagent_call: Optional[SubAgentCall] = Field(
        None, description="Subagent call details (if type='subagent')"
    )
    thought: Optional[str] = Field(None, description="LLM's reasoning process")
    response: Optional[str] = Field(
        None, description="Final response (if type='finish')"
    )

    def model_post_init(self, __context: Any) -> None:
        """Validate that the action has the required fields based on type."""
        if self.type == "tool" and self.tool_call is None:
            raise ValueError("tool_call is required when type='tool'")
        if self.type == "subagent" and self.subagent_call is None:
            raise ValueError("subagent_call is required when type='subagent'")
        if self.type == "finish" and self.response is None:
            raise ValueError("response is required when type='finish'")


class AgentResponse(BaseModel):
    """Final response from an agent execution."""

    content: str = Field(..., description="The agent's final output")
    iterations: int = Field(..., description="Number of iterations executed")
    success: bool = Field(
        default=True, description="Whether the agent completed successfully"
    )


class SkillConfig(BaseModel):
    """Configuration for a skill loaded from YAML."""

    name: str = Field(..., description="Name of the skill")
    description: str = Field(..., description="Description of what the skill does")
    tools: List[str] = Field(
        default_factory=list, description="List of tool names this skill can use"
    )
    subagents: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of subagent names to their config file paths",
    )
    system_prompt: Optional[str] = Field(
        None, description="Custom system prompt for this skill"
    )
    max_iterations: int = Field(
        default=10, description="Maximum number of iterations allowed"
    )
