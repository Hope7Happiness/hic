"""
Glob tool for file discovery with permissions and truncation.

Features:
- Permission request (read)
- Path safety validation
- Ripgrep integration with fallback to Python glob
- Modification time sorting (most recent first)
- Result limit and truncation
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import importlib.util
import subprocess
import glob as pyglob


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


def _resolve_base(path: Optional[str], ctx) -> Path:
    base = Path(ctx.working_directory).resolve()
    target = Path(path) if path else Path(".")
    return (base / target).resolve() if not target.is_absolute() else target.resolve()


def _glob_with_rg(
    pattern: str,
    base: Path,
    max_results: int,
    include_hidden: bool,
) -> tuple[list[str], str]:
    args = ["rg", "--files", "--glob", pattern, "--max-count", str(max_results)]
    if include_hidden:
        args.append("--hidden")

    try:
        result = subprocess.run(
            args,
            cwd=str(base),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return [], "python"

    if result.returncode not in (0, 1):
        raise RuntimeError(
            f"rg failed with exit code {result.returncode}: {result.stderr.strip()}"
        )

    files = [line for line in result.stdout.splitlines() if line.strip()]
    return files, "rg"


def _glob_with_python(pattern: str, base: Path, max_results: int) -> list[str]:
    matches = pyglob.glob(str(base / pattern), recursive=True)
    # Convert to relative paths to match rg behavior
    rel_matches = []
    for match in matches:
        try:
            rel_matches.append(str(Path(match).resolve().relative_to(base)))
        except Exception:
            rel_matches.append(match)
    return rel_matches[:max_results]


def _sort_by_mtime(files: list[str], base: Path) -> list[str]:
    def mtime(path_str: str) -> float:
        try:
            return (base / path_str).stat().st_mtime
        except Exception:
            return 0.0

    return sorted(files, key=mtime, reverse=True)


async def glob(
    pattern: str,
    ctx,
    path: Optional[str] = None,
    max_results: int = 100,
    include_hidden: bool = False,
):
    """
    Find files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., "**/*.py")
        ctx: Execution context
        path: Base directory to search (defaults to working directory)
        max_results: Maximum number of results to return
        include_hidden: Whether to include hidden files
    """
    try:
        base = _resolve_base(path, ctx)
        if not is_path_safe(base, ctx.working_directory):
            return ToolResult.from_error(
                "Invalid path",
                f"Path '{path}' escapes the workspace",
                path=str(path) if path else None,
            )

        if not base.exists():
            return ToolResult.from_error(
                "Path not found",
                f"Base path does not exist: {base}",
                path=str(base),
            )

        await ctx.ask(
            PermissionRequest(
                permission=PermissionType.READ,
                patterns=[pattern],
                metadata={
                    "pattern": pattern,
                    "base_path": str(base),
                    "include_hidden": include_hidden,
                    "max_results": max_results,
                },
                description=f"Glob files: {pattern}",
            )
        )

        ctx.check_abort()

        files, source = _glob_with_rg(pattern, base, max_results, include_hidden)
        if source == "python":
            files = _glob_with_python(pattern, base, max_results)

        files = _sort_by_mtime(files, base)
        if max_results > 0:
            files = files[:max_results]

        output = "\n".join(files) if files else "(no matches)"
        truncated, trunc_meta = ctx.truncate_output(output, context="glob results")

        return ToolResult.success(
            f"Glob {pattern}",
            truncated,
            pattern=pattern,
            path=str(base),
            match_count=len(files),
            include_hidden=include_hidden,
            max_results=max_results,
            source=source,
            **trunc_meta,
        )

    except PermissionDeniedError as e:
        return ToolResult.from_error(
            "Permission denied",
            str(e),
            pattern=pattern,
            path=str(path) if path else None,
        )
    except Exception as e:
        return ToolResult.from_error(
            "Glob failed",
            str(e),
            pattern=pattern,
            path=str(path) if path else None,
            error_type=type(e).__name__,
        )
