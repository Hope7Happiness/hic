"""
Write tool for creating or overwriting text files with permission checks.

Features:
- Permission request with metadata (exists, size)
- Path safety validation
- Parent directory creation
- Unified diff generation against previous content
- Structured ToolResult with metadata
"""

from pathlib import Path
from typing import Optional
import difflib
import importlib.util


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
is_path_safe = permissions_mod.is_path_safe
ToolResult = tool_result_mod.ToolResult


def _resolve_path(file_path: str, ctx) -> Path:
    base = Path(ctx.working_directory).resolve()
    target = Path(file_path)
    return (base / target).resolve() if not target.is_absolute() else target.resolve()


def _make_diff(old: str, new: str, file_path: str) -> str:
    diff_lines = difflib.unified_diff(
        old.splitlines(),
        new.splitlines(),
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm="",
    )
    return "\n".join(diff_lines)


async def write(file_path: str, content: str, ctx, create_dirs: bool = True):
    """
    Create or overwrite a text file with the given content.

    Args:
        file_path: Target file path (relative to workspace allowed)
        content: New file content
        ctx: Execution context
        create_dirs: Whether to create parent directories automatically
    """

    try:
        resolved = _resolve_path(file_path, ctx)
        if not is_path_safe(resolved, ctx.working_directory):
            return ToolResult.from_error(
                "Invalid path",
                f"Path '{file_path}' escapes the workspace",
                file_path=file_path,
            )

        exists = resolved.exists()
        old_content = ""
        if exists and resolved.is_file():
            old_content = resolved.read_text(encoding="utf-8", errors="replace")
        elif resolved.exists() and not resolved.is_file():
            return ToolResult.from_error(
                "Path is not a file",
                f"Target exists and is not a file: {file_path}",
                file_path=file_path,
            )

        # Permission request
        await ctx.ask(
            PermissionRequest(
                permission=PermissionType.WRITE,
                patterns=[str(file_path)],
                metadata={
                    "resolved_path": str(resolved),
                    "exists": exists,
                    "size_bytes": len(content.encode("utf-8")),
                    "line_count": len(content.splitlines()),
                },
                description=f"Write file: {file_path}",
            )
        )

        # Ensure parent directories
        if create_dirs:
            resolved.parent.mkdir(parents=True, exist_ok=True)
        else:
            if not resolved.parent.exists():
                return ToolResult.from_error(
                    "Parent directory missing",
                    f"Directory does not exist: {resolved.parent}",
                    file_path=file_path,
                )

        # Write file
        resolved.write_text(content, encoding="utf-8")

        diff = _make_diff(old_content, content, str(file_path))

        return ToolResult.success(
            ("Updated" if exists else "Created") + f" {file_path}",
            diff if diff else "(no changes)",
            file_path=str(file_path),
            resolved_path=str(resolved),
            exists=exists,
            size_bytes=len(content.encode("utf-8")),
            line_count=len(content.splitlines()),
        )

    except PermissionDeniedError as e:
        return ToolResult.from_error("Permission denied", str(e), file_path=file_path)
    except Exception as e:
        return ToolResult.from_error(
            "Write failed", str(e), file_path=file_path, error_type=type(e).__name__
        )
