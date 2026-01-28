"""
Grep tool for content search with permissions and truncation.

Features:
- Permission request (read)
- Ripgrep integration with fallback to Python regex
- Regex support and include patterns
- Result limit and truncation
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import importlib.util
import subprocess
import json
import re


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


def _parse_rg_json_lines(lines: list[str]) -> tuple[list[str], list[str]]:
    output_lines: list[str] = []
    matched_files: set[str] = set()

    for line in lines:
        if not line.strip():
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue

        evt_type = evt.get("type")
        data = evt.get("data") or {}

        if evt_type == "match":
            path = data.get("path", {}).get("text")
            line_number = data.get("line_number")
            line_text = (data.get("lines", {}) or {}).get("text", "").rstrip("\n")
            submatches = data.get("submatches", [])
            column = 1
            if submatches:
                try:
                    column = int(submatches[0].get("start", 0)) + 1
                except Exception:
                    column = 1

            if path is None or line_number is None:
                continue

            matched_files.add(path)
            output_lines.append(f"{path}:{line_number}:{column}: {line_text}")
        elif evt_type == "context":
            path = data.get("path", {}).get("text")
            line_number = data.get("line_number")
            line_text = (data.get("lines", {}) or {}).get("text", "").rstrip("\n")
            if path is None or line_number is None:
                continue
            output_lines.append(f"{path}:{line_number}: {line_text}")

    return output_lines, sorted(matched_files)


def _grep_with_rg(
    pattern: str,
    base: Path,
    include: Optional[str],
    max_results: int,
    context_lines: int,
) -> tuple[list[str], list[str], str]:
    args = [
        "rg",
        "--json",
        "--line-number",
        "--column",
        "--max-count",
        str(max_results),
        "--regexp",
        pattern,
    ]

    if context_lines > 0:
        args.extend(["--context", str(context_lines)])

    if include:
        args.extend(["--glob", include])

    try:
        result = subprocess.run(
            args,
            cwd=str(base),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return [], [], "python"

    if result.returncode not in (0, 1):
        raise RuntimeError(
            f"rg failed with exit code {result.returncode}: {result.stderr.strip()}"
        )

    output_lines, matched_files = _parse_rg_json_lines(result.stdout.splitlines())
    return output_lines, matched_files, "rg"


def _grep_with_python(
    pattern: str,
    base: Path,
    include: Optional[str],
    max_results: int,
) -> tuple[list[str], list[str]]:
    output_lines: list[str] = []
    matched_files: set[str] = set()

    regex = re.compile(pattern)
    glob_pattern = include or "**/*"
    for file_path in base.glob(glob_pattern):
        if not file_path.is_file():
            continue
        try:
            rel_path = str(file_path.relative_to(base))
        except Exception:
            rel_path = str(file_path)

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for idx, line in enumerate(content.splitlines(), start=1):
            match = regex.search(line)
            if match:
                column = match.start() + 1
                output_lines.append(f"{rel_path}:{idx}:{column}: {line}")
                matched_files.add(rel_path)
                if 0 < max_results <= len(output_lines):
                    return output_lines, sorted(matched_files)

    return output_lines, sorted(matched_files)


async def grep(
    pattern: str,
    ctx,
    path: Optional[str] = None,
    include: Optional[str] = None,
    max_results: int = 100,
    context_lines: int = 0,
):
    """
    Search file contents using a regex pattern.

    Args:
        pattern: Regex pattern to search
        ctx: Execution context
        path: Base directory to search (defaults to working directory)
        include: Optional glob to filter files (e.g., "*.py")
        max_results: Maximum number of matches to return
        context_lines: Lines of context before/after each match
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
                    "include": include,
                    "max_results": max_results,
                    "context_lines": context_lines,
                },
                description=f"Grep content: {pattern}",
            )
        )

        ctx.check_abort()

        output_lines, matched_files, source = _grep_with_rg(
            pattern, base, include, max_results, context_lines
        )
        if source == "python":
            output_lines, matched_files = _grep_with_python(
                pattern, base, include, max_results
            )

        output = "\n".join(output_lines) if output_lines else "(no matches)"
        truncated, trunc_meta = ctx.truncate_output(output, context="grep results")

        return ToolResult.success(
            f"Grep {pattern}",
            truncated,
            pattern=pattern,
            path=str(base),
            include=include,
            match_count=len(output_lines),
            file_count=len(matched_files),
            max_results=max_results,
            context_lines=context_lines,
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
    except re.error as e:
        return ToolResult.from_error(
            "Invalid regex",
            str(e),
            pattern=pattern,
        )
    except Exception as e:
        return ToolResult.from_error(
            "Grep failed",
            str(e),
            pattern=pattern,
            path=str(path) if path else None,
            error_type=type(e).__name__,
        )
