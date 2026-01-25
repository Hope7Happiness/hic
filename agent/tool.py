"""
Tool system for agent framework.

This module provides the Tool class that wraps Python functions
and makes them callable by agents. It extracts:
1. Function name
2. Docstring (as description)
3. Parameter types from type annotations
4. Validates arguments using Pydantic
"""

import inspect
import json
from typing import Callable, Dict, Any, get_type_hints
from pydantic import create_model, ValidationError


class Tool:
    """
    Wraps a Python function to make it callable as an agent tool.

    The function must have:
    - Type annotations for all parameters
    - A docstring describing what it does
    """

    def __init__(self, func: Callable):
        """
        Create a tool from a Python function.

        Args:
            func: Python function with type annotations and docstring
        """
        self.func = func
        self.name = func.__name__
        self.description = (func.__doc__ or "").strip()

        # Extract parameter information
        self.signature = inspect.signature(func)
        self.type_hints = get_type_hints(func)
        self.parameters = self._extract_parameters()

    def _extract_parameters(self) -> Dict[str, Dict[str, Any]]:
        """
        Extract parameter information from function signature.

        Returns:
            Dict mapping parameter names to their type info
        """
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
        """
        Call the tool with validated arguments.

        Args:
            **kwargs: Arguments to pass to the function

        Returns:
            Result from the function

        Raises:
            ValidationError: If arguments don't match expected types
            Exception: Any exception raised by the function
        """
        # Create a Pydantic model for validation
        fields = {}
        for param_name, param_info in self.parameters.items():
            if param_info["required"]:
                fields[param_name] = (param_info["type"], ...)
            else:
                fields[param_name] = (param_info["type"], param_info["default"])

        # Create dynamic Pydantic model
        ValidationModel = create_model(f"{self.name}_args", **fields)

        # Validate arguments
        try:
            validated = ValidationModel(**kwargs)
            validated_kwargs = validated.model_dump()
        except ValidationError:
            raise  # Re-raise the original ValidationError

        # Call the function
        return self.func(**validated_kwargs)

    def to_schema(self) -> str:
        """
        Generate a text description of the tool for use in prompts.

        Returns:
            String describing the tool's name, description, and parameters
        """
        schema_parts = [f"Tool: {self.name}"]

        if self.description:
            schema_parts.append(f"Description: {self.description}")

        # Add parameter information
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
        """Get a readable name for a type hint."""
        if hasattr(type_hint, "__name__"):
            return type_hint.__name__
        else:
            return str(type_hint)

    def __repr__(self) -> str:
        return f"Tool(name='{self.name}', parameters={list(self.parameters.keys())})"
