"""
Tests for Tool functionality.

Test cases:
1. test_tool_creation_from_function
2. test_tool_parameter_extraction
3. test_tool_call_with_validation
4. test_tool_schema_generation
"""

import pytest
from agent.tool import Tool
from pydantic import ValidationError


def sample_function(x: int, y: int) -> int:
    """Add two numbers together."""
    return x + y


def function_with_optional(name: str, age: int = 25) -> str:
    """Format a person's information."""
    return f"{name} is {age} years old"


def function_with_defaults(a: int = 1, b: int = 2) -> int:
    """Add two numbers with defaults."""
    return a + b


def test_tool_creation_from_function():
    """Test creating a Tool from a Python function."""
    tool = Tool(sample_function)

    # Verify basic attributes
    assert tool.name == "sample_function"
    assert tool.description == "Add two numbers together."
    assert tool.func == sample_function

    # Verify parameters were extracted
    assert "x" in tool.parameters
    assert "y" in tool.parameters
    assert tool.parameters["x"]["type"] == int
    assert tool.parameters["y"]["type"] == int
    assert tool.parameters["x"]["required"] is True
    assert tool.parameters["y"]["required"] is True


def test_tool_parameter_extraction():
    """Test that Tool correctly extracts parameter information."""
    tool = Tool(function_with_optional)

    # Check required parameter
    assert "name" in tool.parameters
    assert tool.parameters["name"]["type"] == str
    assert tool.parameters["name"]["required"] is True

    # Check optional parameter
    assert "age" in tool.parameters
    assert tool.parameters["age"]["type"] == int
    assert tool.parameters["age"]["required"] is False
    assert tool.parameters["age"]["default"] == 25


def test_tool_call_with_validation():
    """Test calling a tool with type validation."""
    tool = Tool(sample_function)

    # Valid call
    result = tool.call(x=5, y=3)
    assert result == 8

    # Valid call with keyword arguments
    result = tool.call(y=10, x=20)
    assert result == 30

    # Invalid call - missing required argument
    with pytest.raises(ValidationError):
        tool.call(x=5)  # Missing y

    # Invalid call - wrong type
    with pytest.raises(ValidationError):
        tool.call(x="not a number", y=5)


def test_tool_call_with_optional_params():
    """Test calling a tool with optional parameters."""
    tool = Tool(function_with_optional)

    # Call with all parameters
    result = tool.call(name="Alice", age=30)
    assert result == "Alice is 30 years old"

    # Call with only required parameter (should use default)
    result = tool.call(name="Bob")
    assert result == "Bob is 25 years old"


def test_tool_schema_generation():
    """Test that Tool generates a proper schema for prompts."""
    tool = Tool(sample_function)

    schema = tool.to_schema()

    # Verify schema contains key information
    assert "sample_function" in schema
    assert "Add two numbers together" in schema
    assert "x" in schema
    assert "y" in schema
    assert "int" in schema
    assert "required" in schema


def test_tool_with_no_docstring():
    """Test creating a Tool from a function without docstring."""

    def no_doc_function(x: int) -> int:
        return x * 2

    tool = Tool(no_doc_function)

    assert tool.name == "no_doc_function"
    assert tool.description == ""
    assert "x" in tool.parameters


def test_tool_with_complex_types():
    """Test Tool with more complex type annotations."""
    from typing import List

    def complex_function(items: List[str], count: int) -> str:
        """Process a list of items."""
        return f"Processed {count} items: {', '.join(items[:count])}"

    tool = Tool(complex_function)

    assert "items" in tool.parameters
    assert "count" in tool.parameters

    # Call the tool
    result = tool.call(items=["a", "b", "c"], count=2)
    assert "a, b" in result
