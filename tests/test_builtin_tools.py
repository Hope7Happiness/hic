"""
Tests for builtin tools (bash and calculator).

This module tests the basic functionality of the bash and calculator tools.
Run with: python tests/test_builtin_tools.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Direct imports to avoid dependency issues
import inspect
import json
from typing import Callable, Dict, Any, get_type_hints
from pydantic import create_model, ValidationError


# Copy Tool class locally to avoid import issues
class Tool:
    """Wraps a Python function to make it callable as an agent tool."""

    def __init__(self, func: Callable):
        self.func = func
        self.name = func.__name__
        self.description = (func.__doc__ or "").strip()
        self.signature = inspect.signature(func)
        self.type_hints = get_type_hints(func)
        self.parameters = self._extract_parameters()

    def _extract_parameters(self) -> Dict[str, Dict[str, Any]]:
        params = {}
        for param_name, param in self.signature.parameters.items():
            param_type = self.type_hints.get(param_name, Any)
            param_info = {
                "type": param_type,
                "required": param.default == inspect.Parameter.empty,
                "default": param.default
                if param.default != inspect.Parameter.empty
                else None,
            }
            params[param_name] = param_info
        return params

    def call(self, **kwargs) -> Any:
        fields = {}
        for param_name, param_info in self.parameters.items():
            if param_info["required"]:
                fields[param_name] = (param_info["type"], ...)
            else:
                fields[param_name] = (param_info["type"], param_info["default"])

        ValidationModel = create_model(f"{self.name}_args", **fields)

        try:
            validated = ValidationModel(**kwargs)
            validated_kwargs = validated.model_dump()
        except ValidationError:
            raise

        return self.func(**validated_kwargs)

    def to_schema(self) -> str:
        schema_parts = [f"Tool: {self.name}"]
        if self.description:
            schema_parts.append(f"Description: {self.description}")
        if self.parameters:
            schema_parts.append("Parameters:")
            for param_name, param_info in self.parameters.items():
                type_name = self._get_type_name(param_info["type"])
                required = "required" if param_info["required"] else "optional"
                schema_parts.append(f"  - {param_name}: {type_name} ({required})")
        else:
            schema_parts.append("Parameters: none")
        return "\n".join(schema_parts)

    def _get_type_name(self, type_hint) -> str:
        if hasattr(type_hint, "__name__"):
            return type_hint.__name__
        else:
            return str(type_hint)


# Import bash and calculator functions
from agent.builtin_tools import bash, calculator


# Test utilities
class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def assert_true(self, condition, message):
        if condition:
            self.passed += 1
            print(f"  ✓ {message}")
        else:
            self.failed += 1
            self.errors.append(message)
            print(f"  ✗ {message}")

    def assert_equals(self, actual, expected, message):
        if actual == expected:
            self.passed += 1
            print(f"  ✓ {message}")
        else:
            self.failed += 1
            error = f"{message} (expected: {expected}, got: {actual})"
            self.errors.append(error)
            print(f"  ✗ {error}")

    def assert_contains(self, text, substring, message):
        if substring in text:
            self.passed += 1
            print(f"  ✓ {message}")
        else:
            self.failed += 1
            error = f"{message} ('{substring}' not in '{text[:50]}...')"
            self.errors.append(error)
            print(f"  ✗ {error}")

    def print_summary(self):
        print("\n" + "=" * 70)
        print(f"Test Results: {self.passed} passed, {self.failed} failed")
        if self.failed > 0:
            print("\nFailed tests:")
            for error in self.errors:
                print(f"  - {error}")
        print("=" * 70)
        return self.failed == 0


def test_bash_tool():
    """Test bash tool functionality."""
    print("\n" + "=" * 70)
    print("Testing bash tool")
    print("=" * 70)

    result = TestResult()
    tool = Tool(bash)

    # Test tool creation
    result.assert_equals(tool.name, "bash", "Tool name is 'bash'")
    result.assert_contains(
        tool.description.lower(), "shell", "Description mentions 'shell'"
    )
    result.assert_true("command" in tool.parameters, "Has 'command' parameter")
    result.assert_true("timeout" in tool.parameters, "Has 'timeout' parameter")

    # Test simple echo
    output = tool.call(command="echo 'Hello World'")
    result.assert_contains(output, "Hello World", "Echo command works")

    # Test pwd
    output = tool.call(command="pwd")
    result.assert_contains(output, "/", "PWD returns a path")

    # Test ls
    output = tool.call(command="ls")
    result.assert_true(len(output) > 0, "LS returns output")

    # Test error handling
    output = tool.call(command="nonexistent_command_xyz")
    result.assert_true(
        "Error" in output or "not found" in output.lower(), "Error handling works"
    )

    # Test piped commands
    output = tool.call(command="echo 'test' | grep 'test'")
    result.assert_contains(output, "test", "Piped commands work")

    return result


def test_calculator_tool():
    """Test calculator tool functionality."""
    print("\n" + "=" * 70)
    print("Testing calculator tool")
    print("=" * 70)

    result = TestResult()
    tool = Tool(calculator)

    # Test tool creation
    result.assert_equals(tool.name, "calculator", "Tool name is 'calculator'")
    result.assert_contains(
        tool.description.lower(), "mathematical", "Description mentions 'mathematical'"
    )
    result.assert_true("expression" in tool.parameters, "Has 'expression' parameter")

    # Test basic operations
    result.assert_equals(tool.call(expression="2 + 2"), "4", "Addition: 2 + 2 = 4")
    result.assert_equals(tool.call(expression="10 - 3"), "7", "Subtraction: 10 - 3 = 7")
    result.assert_equals(
        tool.call(expression="5 * 6"), "30", "Multiplication: 5 * 6 = 30"
    )
    result.assert_equals(tool.call(expression="15 / 3"), "5", "Division: 15 / 3 = 5")
    result.assert_equals(tool.call(expression="2 ** 8"), "256", "Power: 2 ** 8 = 256")
    result.assert_equals(tool.call(expression="17 % 5"), "2", "Modulo: 17 % 5 = 2")

    # Test parentheses
    result.assert_equals(
        tool.call(expression="(2 + 3) * 4"), "20", "Parentheses: (2 + 3) * 4 = 20"
    )

    # Test complex expression
    result.assert_equals(
        tool.call(expression="(10 + 5) * 2 - 8 / 4"),
        "28",
        "Complex: (10 + 5) * 2 - 8 / 4 = 28",
    )

    # Test math functions
    result.assert_equals(
        tool.call(expression="sqrt(16)"), "4", "Square root: sqrt(16) = 4"
    )
    result.assert_equals(tool.call(expression="abs(-5)"), "5", "Absolute: abs(-5) = 5")
    result.assert_equals(
        tool.call(expression="round(3.7)"), "4", "Round: round(3.7) = 4"
    )
    result.assert_equals(
        tool.call(expression="min(5, 3, 8)"), "3", "Min: min(5, 3, 8) = 3"
    )
    result.assert_equals(
        tool.call(expression="max(5, 3, 8)"), "8", "Max: max(5, 3, 8) = 8"
    )
    result.assert_equals(
        tool.call(expression="log10(100)"), "2", "Log10: log10(100) = 2"
    )
    result.assert_equals(tool.call(expression="exp(0)"), "1", "Exp: exp(0) = 1")
    result.assert_equals(tool.call(expression="sin(0)"), "0", "Sin: sin(0) = 0")
    result.assert_equals(tool.call(expression="cos(0)"), "1", "Cos: cos(0) = 1")

    # Test constants
    pi_result = tool.call(expression="pi")
    result.assert_true(pi_result.startswith("3.14"), "Pi constant works")

    # Test error handling
    div_zero = tool.call(expression="1 / 0")
    result.assert_contains(div_zero, "Error", "Division by zero handled")

    invalid_syntax = tool.call(expression="2 + * 3")
    result.assert_contains(invalid_syntax, "Error", "Invalid syntax handled")

    empty_expr = tool.call(expression="")
    result.assert_contains(empty_expr, "Error", "Empty expression handled")

    # Test whitespace handling
    result.assert_equals(
        tool.call(expression="  2  +  2  "),
        "4",
        "Whitespace handled: '  2  +  2  ' = 4",
    )

    return result


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("Running Builtin Tools Tests")
    print("=" * 70)

    bash_result = test_bash_tool()
    calc_result = test_calculator_tool()

    # Print overall summary
    print("\n" + "=" * 70)
    print("OVERALL TEST SUMMARY")
    print("=" * 70)
    total_passed = bash_result.passed + calc_result.passed
    total_failed = bash_result.failed + calc_result.failed
    print(f"Total: {total_passed} passed, {total_failed} failed")

    if total_failed == 0:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total_failed} tests failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
