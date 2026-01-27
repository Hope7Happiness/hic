"""
Read tool with pagination, safety checks, and line numbering.

This tool reads a text file from the workspace with the following features:
- Permission request before access
- Path safety validation (no escaping project root)
- Binary file detection (refuses to read binary files)
- Pagination via offset/limit
- cat -n style line numbering
- Structured ToolResult with truncation metadata
"""

from pathlib import Path
from typing import Optional
import sys
import importlib.util


# Import required modules without triggering package __init__
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
    """Resolve file path relative to the working directory."""
    base = Path(ctx.working_directory).resolve()
    target = Path(file_path)
    return (base / target).resolve() if not target.is_absolute() else target.resolve()


def _is_binary(path: Path, sample_size: int = 1024) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(sample_size)
            if b"\0" in chunk:
                return True
    except Exception:
        return False
    return False


async def read(
    file_path: str,
    ctx,
    offset: int = 0,
    limit: int = 2000,
):
    """
    Read a text file with pagination and line numbers.

    Args:
        file_path: Path to the file to read (relative to workspace allowed)
        ctx: Execution context
        offset: Line offset (0-based)
        limit: Maximum lines to read (defaults to 2000)
    """

    try:
        # Resolve and validate path
        resolved = _resolve_path(file_path, ctx)
        if not is_path_safe(resolved, ctx.working_directory):
            return ToolResult.from_error(
                "Invalid path",
                f"Path '{file_path}' escapes the workspace",
                file_path=file_path,
            )

        # Permission request
        await ctx.ask(
            PermissionRequest(
                permission=PermissionType.READ,
                patterns=[str(file_path)],
                metadata={"resolved_path": str(resolved)},
                description=f"Read file: {file_path}",
            )
        )

        # File existence
        if not resolved.exists():
            return ToolResult.from_error(
                "File not found",
                f"File does not exist: {file_path}",
                file_path=file_path,
            )

        if resolved.is_dir():
            return ToolResult.from_error(
                "Path is a directory",
                f"Cannot read directory: {file_path}",
                file_path=file_path,
            )

        # Binary detection
        if _is_binary(resolved):
            return ToolResult.from_error(
                "Binary file detected",
                f"File appears to be binary and cannot be read as text: {file_path}",
                file_path=file_path,
            )

        content = resolved.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        total_lines = len(lines)

        # Bounds
        if offset < 0:
            offset = 0
        if limit <= 0:
            limit = 2000

        end = min(total_lines, offset + limit)
        slice_lines = lines[offset:end]
        lines_read = len(slice_lines)

        # Line numbering like cat -n (1-based)
        # Pad to 5 digits (cat -n style) or total_lines length, whichever is larger
        line_num_width = max(5, len(str(total_lines if total_lines > 0 else 1)))
        numbered = []
        for idx, line in enumerate(slice_lines, start=offset + 1):
            numbered.append(f"{str(idx).zfill(line_num_width)}| {line}")

        is_truncated = end < total_lines
        if is_truncated:
            numbered.append("")
            numbered.append(
                f"... ({total_lines - end} more lines) — use offset={end} to continue"
            )

        output = "\n".join(numbered)

        return ToolResult.success(
            f"Read {file_path}",
            output,
            file_path=str(file_path),
            resolved_path=str(resolved),
            offset=offset,
            limit=limit,
            lines_read=lines_read,
            total_lines=total_lines,
            is_truncated=is_truncated,
        )

    except PermissionDeniedError as e:
        return ToolResult.from_error("Permission denied", str(e), file_path=file_path)
    except Exception as e:
        return ToolResult.from_error(
            "Read failed", str(e), file_path=file_path, error_type=type(e).__name__
        )
