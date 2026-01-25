"""
Skill loading from YAML configuration.

This module provides functionality to load Agent configurations from YAML files.
Skills are YAML-defined combinations of tools and subagents for complex tasks.
"""

import os
import yaml
from typing import Dict, List
from agent.schemas import SkillConfig
from agent.tool import Tool
from agent.llm import LLM


class Skill:
    """
    Loads and creates agents from YAML configuration files.

    A skill YAML file specifies:
    - name: Skill name
    - description: What the skill does
    - tools: List of tool names to use
    - subagents: Dict mapping subagent names to their config file paths
    - system_prompt: Optional custom system prompt
    - max_iterations: Maximum iterations allowed
    """

    @classmethod
    def from_yaml(
        cls, yaml_path: str, available_tools: Dict[str, Tool], llm: LLM
    ) -> "Agent":
        """
        Load an agent configuration from a YAML file.

        Args:
            yaml_path: Path to the YAML configuration file
            available_tools: Dict of all available tools (by name)
            llm: LLM instance to use for this agent

        Returns:
            Configured Agent instance

        Raises:
            FileNotFoundError: If YAML file doesn't exist
            ValueError: If configuration is invalid
        """
        # Import here to avoid circular dependency
        from agent.agent import Agent

        # Load YAML file
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"Configuration file not found: {yaml_path}")

        with open(yaml_path, "r") as f:
            config_dict = yaml.safe_load(f)

        # Validate with Pydantic
        config = SkillConfig(**config_dict)

        # Collect tools for this agent
        agent_tools = []
        for tool_name in config.tools:
            if tool_name not in available_tools:
                raise ValueError(f"Tool '{tool_name}' not found in available_tools")
            agent_tools.append(available_tools[tool_name])

        # Recursively load subagents
        subagents = {}
        base_dir = os.path.dirname(yaml_path)

        for subagent_name, subagent_config_path in config.subagents.items():
            # Resolve relative path
            if not os.path.isabs(subagent_config_path):
                subagent_config_path = os.path.join(base_dir, subagent_config_path)

            # Recursively load subagent
            subagent = cls.from_yaml(
                yaml_path=subagent_config_path,
                available_tools=available_tools,
                llm=llm,  # Subagents share the same LLM instance
            )
            subagents[subagent_name] = subagent

        # Create and return agent
        return Agent(
            llm=llm,
            tools=agent_tools,
            subagents=subagents,
            max_iterations=config.max_iterations,
            system_prompt=config.system_prompt,
            name=config.name,
        )

    @classmethod
    def from_dict(
        cls,
        config_dict: Dict,
        available_tools: Dict[str, Tool],
        llm: LLM,
        base_dir: str = ".",
    ) -> "Agent":
        """
        Create an agent from a configuration dictionary.

        This is useful for testing or programmatic agent creation.

        Args:
            config_dict: Configuration dictionary
            available_tools: Dict of all available tools (by name)
            llm: LLM instance to use
            base_dir: Base directory for resolving relative paths

        Returns:
            Configured Agent instance
        """
        # Import here to avoid circular dependency
        from agent.agent import Agent

        # Validate with Pydantic
        config = SkillConfig(**config_dict)

        # Collect tools
        agent_tools = []
        for tool_name in config.tools:
            if tool_name not in available_tools:
                raise ValueError(f"Tool '{tool_name}' not found in available_tools")
            agent_tools.append(available_tools[tool_name])

        # Load subagents
        subagents = {}
        for subagent_name, subagent_config_path in config.subagents.items():
            # Resolve relative path
            if not os.path.isabs(subagent_config_path):
                subagent_config_path = os.path.join(base_dir, subagent_config_path)

            # Load subagent from YAML
            subagent = cls.from_yaml(
                yaml_path=subagent_config_path, available_tools=available_tools, llm=llm
            )
            subagents[subagent_name] = subagent

        # Create and return agent
        return Agent(
            llm=llm,
            tools=agent_tools,
            subagents=subagents,
            max_iterations=config.max_iterations,
            system_prompt=config.system_prompt,
            name=config.name,
        )
