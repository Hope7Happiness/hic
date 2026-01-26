"""
A type-safe LLM agent framework.

This framework provides four core abstractions:
1. LLM: Abstract base class for LLM implementations (OpenAILLM is the default)
2. Tool: Python functions with type annotations that agents can use
3. Skill: YAML-configured combinations of tools for complex tasks
4. Agent: The core element that uses tools and delegates to subagents
5. Callbacks: Observability hooks for monitoring and logging agent execution
6. Config: Utilities for loading API keys and configuration
"""

from agent.llm import LLM, OpenAILLM
from agent.deepseek_llm import DeepSeekLLM
from agent.tool import Tool
from agent.agent import Agent
from agent.orchestrator import AgentOrchestrator
from agent.skill import Skill
from agent.schemas import (
    AgentResponse,
    Action,
    AgentStatus,
    AgentState,
    AgentMessage,
    LaunchedSubagent,
)
from agent.callbacks import (
    AgentCallback,
    ConsoleCallback,
    ColorfulConsoleCallback,
    MetricsCallback,
    FileLoggerCallback,
)
from agent.config import (
    load_env,
    get_api_key,
    get_openai_api_key,
    get_deepseek_api_key,
    check_api_keys,
)
from agent.async_logger import AsyncLogger, init_logger, close_logger, get_logger

__all__ = [
    "LLM",
    "OpenAILLM",
    "DeepSeekLLM",
    "Tool",
    "Agent",
    "AgentOrchestrator",
    "Skill",
    "AgentResponse",
    "Action",
    "AgentStatus",
    "AgentState",
    "AgentMessage",
    "LaunchedSubagent",
    "AgentCallback",
    "ConsoleCallback",
    "ColorfulConsoleCallback",
    "MetricsCallback",
    "FileLoggerCallback",
    "AsyncLogger",
    "init_logger",
    "close_logger",
    "get_logger",
    "load_env",
    "get_api_key",
    "get_openai_api_key",
    "get_deepseek_api_key",
    "check_api_keys",
]
