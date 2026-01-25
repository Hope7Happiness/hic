"""
Tests for Skill (YAML configuration loading).

Test cases:
1. test_skill_from_yaml_simple
2. test_skill_from_yaml_with_subagent
3. test_skill_validation
"""

import os
import pytest
from unittest.mock import Mock
from agent.llm import LLM
from agent.tool import Tool
from agent.skill import Skill
from tests.test_utils import python_exec, file_write, file_search


def test_skill_from_yaml_simple():
    """
    Test loading a simple skill from YAML.
    """
    # Create tools
    tools = {
        "python_exec": Tool(python_exec),
        "file_write": Tool(file_write),
        "file_search": Tool(file_search),
    }

    # Mock LLM
    mock_llm = Mock(spec=LLM)

    # Load skill from YAML
    yaml_path = "tests/fixtures/skills/simple_skill.yaml"
    agent = Skill.from_yaml(yaml_path, tools, mock_llm)

    # Verify agent was created correctly
    assert agent.name == "simple_skill"
    assert agent.max_iterations == 5
    assert len(agent.tools) == 1
    assert "python_exec" in agent.tools
    assert (
        agent.system_prompt == "You are a helpful assistant that executes Python code."
    )


def test_skill_from_yaml_with_subagent():
    """
    Test loading a skill with a subagent from YAML.
    """
    # Create tools
    tools = {
        "python_exec": Tool(python_exec),
        "file_write": Tool(file_write),
        "file_search": Tool(file_search),
    }

    # Mock LLM
    mock_llm = Mock(spec=LLM)

    # Load parent agent (which loads subagent)
    yaml_path = "tests/fixtures/skills/parent_agent.yaml"
    agent = Skill.from_yaml(yaml_path, tools, mock_llm)

    # Verify parent agent
    assert agent.name == "parent_agent"
    assert "python_exec" in agent.tools
    assert len(agent.subagents) == 1
    assert "file_helper" in agent.subagents

    # Verify subagent
    subagent = agent.subagents["file_helper"]
    assert subagent.name == "file_skill"
    assert "file_write" in subagent.tools
    assert "file_search" in subagent.tools


def test_skill_from_dict():
    """
    Test creating a skill from a dictionary.
    """
    # Create tools
    tools = {"python_exec": Tool(python_exec)}

    # Mock LLM
    mock_llm = Mock(spec=LLM)

    # Create skill from dict
    config = {
        "name": "test_skill",
        "description": "A test skill",
        "tools": ["python_exec"],
        "max_iterations": 8,
        "system_prompt": "Test prompt",
    }

    agent = Skill.from_dict(config, tools, mock_llm)

    # Verify
    assert agent.name == "test_skill"
    assert agent.max_iterations == 8
    assert "python_exec" in agent.tools
    assert agent.system_prompt == "Test prompt"


def test_skill_missing_tool():
    """
    Test that loading a skill with a missing tool raises an error.
    """
    # Create tools (missing python_exec)
    tools = {"file_write": Tool(file_write)}

    # Mock LLM
    mock_llm = Mock(spec=LLM)

    # Try to load skill that requires python_exec
    yaml_path = "tests/fixtures/skills/simple_skill.yaml"

    with pytest.raises(ValueError, match="Tool 'python_exec' not found"):
        Skill.from_yaml(yaml_path, tools, mock_llm)


def test_skill_missing_yaml_file():
    """
    Test that loading from a non-existent YAML file raises an error.
    """
    tools = {"python_exec": Tool(python_exec)}
    mock_llm = Mock(spec=LLM)

    with pytest.raises(FileNotFoundError):
        Skill.from_yaml("nonexistent.yaml", tools, mock_llm)


def test_skill_default_values():
    """
    Test that skill uses default values when not specified in YAML.
    """
    tools = {"python_exec": Tool(python_exec)}
    mock_llm = Mock(spec=LLM)

    # Minimal config (no system_prompt, default max_iterations)
    config = {
        "name": "minimal_skill",
        "description": "Minimal config",
        "tools": ["python_exec"],
    }

    agent = Skill.from_dict(config, tools, mock_llm)

    # Check defaults
    assert agent.name == "minimal_skill"
    assert agent.max_iterations == 10  # default from SkillConfig
    assert agent.system_prompt is None or len(agent.system_prompt) > 0  # uses default
