"""
Tool system for agent framework.

This module provides the Tool class that wraps Python functions
and makes them callable by agents. It extracts:
1. Function name
2. Docstring (as description)
3. Parameter types from type annotations
4. Validates arguments using Pydantic

Supports both sync and async functions.
"""

import asyncio
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

    def __init__(self, func: Callable, context: Any = None):
        """
        Create a tool from a Python function.

        Args:
            func: Python function with type annotations and docstring
            context: Optional Context instance to inject into async tool calls
        """
        self.func = func
        self.name = func.__name__
        self.description = (func.__doc__ or "").strip()
        self.context = context
        self.is_async = asyncio.iscoroutinefunction(func)

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
        Call the tool with validated arguments (sync version).

        Args:
            **kwargs: Arguments to pass to the function

        Returns:
            Result from the function

        Raises:
            ValidationError: If arguments don't match expected types
            Exception: Any exception raised by the function
            RuntimeError: If called on an async function (use call_async instead)
        """
        if self.is_async:
            raise RuntimeError(
                f"Tool '{self.name}' is async. Use call_async() or await call_async() instead."
            )

        # Validate and call
        validated_kwargs = self._validate_arguments(kwargs)
        return self.func(**validated_kwargs)

    async def call_async(self, **kwargs) -> Any:
        """
        Call the tool with validated arguments (async version).

        Automatically injects Context if the tool expects it and context is set.

        Args:
            **kwargs: Arguments to pass to the function

        Returns:
            Result from the function

        Raises:
            ValidationError: If arguments don't match expected types
            Exception: Any exception raised by the function
        """
        # Validate arguments
        validated_kwargs = self._validate_arguments(kwargs)

        # Inject context if tool expects it and context is available
        if self.context and "ctx" in self.parameters and "ctx" not in validated_kwargs:
            validated_kwargs["ctx"] = self.context

        # Call async or sync function
        if self.is_async:
            return await self.func(**validated_kwargs)
        else:
            # Run sync function in executor to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, lambda: self.func(**validated_kwargs)
            )

    def _validate_arguments(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate arguments against the function signature.

        Args:
            kwargs: Arguments to validate

        Returns:
            Validated arguments dictionary

        Raises:
            ValidationError: If validation fails
        """
        # Create a Pydantic model for validation
        fields = {}
        for param_name, param_info in self.parameters.items():
            # Skip context parameter - it's injected automatically
            if param_name == "ctx":
                continue

            if param_info["required"]:
                fields[param_name] = (param_info["type"], ...)
            else:
                fields[param_name] = (param_info["type"], param_info["default"])

        # Create dynamic Pydantic model
        ValidationModel = create_model(f"{self.name}_args", **fields)

        # Validate arguments (filter out ctx if present in kwargs)
        kwargs_to_validate = {k: v for k, v in kwargs.items() if k != "ctx"}
        validated = ValidationModel(**kwargs_to_validate)
        return validated.model_dump()

    def to_schema(self) -> str:
        """
        Generate a text description of the tool for use in prompts.

        Returns:
            String describing the tool's name, description, and parameters
        """
        schema_parts = [f"Tool: {self.name}"]

        if self.description:
            schema_parts.append(f"Description: {self.description}")

        # Add parameter information (skip ctx as it's auto-injected)
        visible_params = {k: v for k, v in self.parameters.items() if k != "ctx"}
        if visible_params:
            schema_parts.append("Parameters:")
            for param_name, param_info in visible_params.items():
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
        async_marker = " (async)" if self.is_async else ""
        visible_params = [k for k in self.parameters.keys() if k != "ctx"]
        return f"Tool(name='{self.name}', parameters={visible_params}{async_marker})"
