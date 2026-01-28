"""
Todo tools for session-scoped task management.

Provides:
- todowrite: replace current todo list
- todoread: read current todo list
"""

from __future__ import annotations

from typing import Any
from pathlib import Path
import importlib.util
from datetime import datetime


agent_dir = Path(__file__).parent.parent


def _load_agent_module(module_name: str, file_name: str):
    module_path = agent_dir / file_name
    spec = importlib.util.spec_from_file_location(f"agent.{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_name} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


permissions_mod = _load_agent_module("permissions", "permissions.py")
tool_result_mod = _load_agent_module("tool_result", "tool_result.py")

PermissionType = permissions_mod.PermissionType
PermissionRequest = permissions_mod.PermissionRequest
PermissionDeniedError = permissions_mod.PermissionDeniedError
ToolResult = tool_result_mod.ToolResult


VALID_STATUS = {"pending", "in_progress", "completed", "cancelled"}
VALID_PRIORITY = {"high", "medium", "low"}


def _validate_todo(todo: dict[str, Any]) -> Optional[str]:
    required = {"id", "content", "status", "priority"}
    missing = required - set(todo.keys())
    if missing:
        return f"Missing fields: {', '.join(sorted(missing))}"

    if todo.get("status") not in VALID_STATUS:
        return f"Invalid status: {todo.get('status')}"

    if todo.get("priority") not in VALID_PRIORITY:
        return f"Invalid priority: {todo.get('priority')}"

    return None


def _format_todos(todos: list[dict[str, Any]]) -> str:
    if not todos:
        return "(no todos)"

    lines = []
    for idx, todo in enumerate(todos, start=1):
        status = todo.get("status")
        priority = todo.get("priority")
        content = todo.get("content")
        todo_id = todo.get("id")
        lines.append(f"{idx}. [{status}] ({priority}) {content} (id={todo_id})")
    return "\n".join(lines)


async def todowrite(todos: list[dict[str, Any]], ctx):
    """
    Replace the current todo list for this session.

    Args:
        todos: List of todo items with id/content/status/priority
        ctx: Execution context
    """
    try:
        await ctx.ask(
            PermissionRequest(
                permission=PermissionType.TODO,
                patterns=["todos"],
                metadata={"count": len(todos)},
                description="Update todo list",
            )
        )

        for todo in todos:
            if not isinstance(todo, dict):
                return ToolResult.from_error(
                    "Invalid todo",
                    "Each todo must be an object",
                )
            error = _validate_todo(todo)
            if error:
                return ToolResult.from_error("Invalid todo", error, todo=todo)

        payload = {
            "session_id": ctx.session_id,
            "todos": todos,
            "updated_at": datetime.now().isoformat(),
        }
        ctx.set_session_metadata("todos", payload)

        output = _format_todos(todos)
        truncated, trunc_meta = ctx.truncate_output(output, context="todo list")

        return ToolResult.success(
            "Updated todo list",
            truncated,
            count=len(todos),
            **trunc_meta,
        )

    except PermissionDeniedError as e:
        return ToolResult.from_error("Permission denied", str(e))
    except Exception as e:
        return ToolResult.from_error(
            "Todo update failed", str(e), error_type=type(e).__name__
        )


async def todoread(ctx):
    """
    Read the current todo list for this session.
    """
    try:
        await ctx.ask(
            PermissionRequest(
                permission=PermissionType.TODO,
                patterns=["todos"],
                metadata={},
                description="Read todo list",
            )
        )

        payload = ctx.get_session_metadata("todos", None)
        todos = []
        updated_at = None
        if isinstance(payload, dict):
            todos = payload.get("todos") or []
            updated_at = payload.get("updated_at")

        output = _format_todos(todos)
        truncated, trunc_meta = ctx.truncate_output(output, context="todo list")

        return ToolResult.success(
            "Todo list",
            truncated,
            count=len(todos),
            updated_at=updated_at,
            **trunc_meta,
        )

    except PermissionDeniedError as e:
        return ToolResult.from_error("Permission denied", str(e))
    except Exception as e:
        return ToolResult.from_error(
            "Todo read failed", str(e), error_type=type(e).__name__
        )
