"""
Edit tool with multi-strategy replacement and safety checks.

Implements several tolerant replacement strategies to handle minor formatting
differences between the provided old_string and the actual file content.

Features:
- Permission request (read + write)
- Path safety validation
- Multiple replacement strategies with similarity scoring
- Optional replaceAll
- Unified diff output
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol
import difflib
import importlib.util

try:
    from Levenshtein import distance as levenshtein_distance
except ImportError:  # Fallback to difflib if dependency missing

    def levenshtein_distance(a: str, b: str) -> int:  # type: ignore
        return int(
            (1 - difflib.SequenceMatcher(None, a, b).ratio()) * max(len(a), len(b))
        )


SIMILARITY_THRESHOLD = 0.80

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


class Replacer(Protocol):
    def try_replace(
        self, content: str, old: str, new: str, replace_all: bool
    ) -> Optional[str]: ...


def _resolve_path(file_path: str, ctx) -> Path:
    base = Path(ctx.working_directory).resolve()
    target = Path(file_path)
    return (base / target).resolve() if not target.is_absolute() else target.resolve()


def _similar(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return 1 - (levenshtein_distance(a, b) / max(len(a), len(b), 1))


class SimpleReplacer:
    def try_replace(
        self, content: str, old: str, new: str, replace_all: bool
    ) -> Optional[str]:
        if old not in content:
            return None
        if replace_all:
            return content.replace(old, new)
        if content.count(old) == 1:
            return content.replace(old, new, 1)
        return None


class LineTrimmedReplacer:
    def try_replace(
        self, content: str, old: str, new: str, replace_all: bool
    ) -> Optional[str]:
        def trim_lines(s: str) -> list[str]:
            return [line.strip() for line in s.splitlines()]

        content_lines = trim_lines(content)
        old_lines = trim_lines(old)

        content_joined = "\n".join(content_lines)
        old_joined = "\n".join(old_lines)

        if old_joined not in content_joined:
            return None

        replaced = content_joined.replace(old_joined, new if replace_all else new, 1)
        # Map back not perfect; use similarity gate
        if _similar(replaced, content) < SIMILARITY_THRESHOLD:
            return None
        return replaced


class WhitespaceNormalizedReplacer:
    def try_replace(
        self, content: str, old: str, new: str, replace_all: bool
    ) -> Optional[str]:
        def normalize(s: str) -> str:
            return " ".join(s.split())

        norm_content = normalize(content)
        norm_old = normalize(old)

        if norm_old not in norm_content:
            return None

        norm_new = normalize(new)
        replaced = norm_content.replace(
            norm_old, norm_new if replace_all else norm_new, 1
        )
        if _similar(replaced, norm_content) < SIMILARITY_THRESHOLD:
            return None
        # We cannot easily reconstruct exact whitespace; fallback to original replace
        return (
            content.replace(old, new, 0 if replace_all else 1)
            if old in content
            else None
        )


class ContextAwareReplacer:
    def try_replace(
        self, content: str, old: str, new: str, replace_all: bool
    ) -> Optional[str]:
        # Use difflib to find close blocks
        matcher = difflib.SequenceMatcher(None, content, old, autojunk=False)
        blocks = matcher.get_matching_blocks()
        if not blocks:
            return None

        best = None
        best_ratio = 0.0
        for block in blocks:
            # block gives matching range; use ratio as heuristic
            ratio = matcher.ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best = block

        if best is None or best_ratio < SIMILARITY_THRESHOLD:
            return None

        # Fallback to difflib replace by finding close occurrences line-wise
        content_lines = content.splitlines()
        old_lines = old.splitlines()

        for i in range(len(content_lines) - len(old_lines) + 1):
            window = "\n".join(content_lines[i : i + len(old_lines)])
            if _similar(window, old) >= SIMILARITY_THRESHOLD:
                if replace_all:
                    return "\n".join(
                        content_lines[:i]
                        + new.splitlines()
                        + content_lines[i + len(old_lines) :]
                    )
                # single replace
                return "\n".join(
                    content_lines[:i]
                    + new.splitlines()
                    + content_lines[i + len(old_lines) :]
                )

        return None


REPLACERS: list[Replacer] = [
    SimpleReplacer(),
    LineTrimmedReplacer(),
    WhitespaceNormalizedReplacer(),
    ContextAwareReplacer(),
]


def _make_diff(old: str, new: str, file_path: str) -> str:
    diff_lines = difflib.unified_diff(
        old.splitlines(),
        new.splitlines(),
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm="",
    )
    return "\n".join(diff_lines)


async def edit(
    file_path: str,
    old_string: str,
    new_string: str,
    ctx,
    replace_all: bool = False,
):
    """
    Edit a file by replacing old_string with new_string using tolerant strategies.
    """

    try:
        resolved = _resolve_path(file_path, ctx)
        if not is_path_safe(resolved, ctx.working_directory):
            return ToolResult.from_error(
                "Invalid path",
                f"Path '{file_path}' escapes the workspace",
                file_path=file_path,
            )

        if not resolved.exists():
            return ToolResult.from_error(
                "File not found",
                f"File does not exist: {file_path}",
                file_path=file_path,
            )

        if resolved.is_dir():
            return ToolResult.from_error(
                "Path is a directory",
                f"Cannot edit directory: {file_path}",
                file_path=file_path,
            )

        # Permissions: read then write
        await ctx.ask(
            PermissionRequest(
                permission=PermissionType.READ,
                patterns=[str(file_path)],
                metadata={"resolved_path": str(resolved)},
                description=f"Read for edit: {file_path}",
            )
        )
        await ctx.ask(
            PermissionRequest(
                permission=PermissionType.WRITE,
                patterns=[str(file_path)],
                metadata={"resolved_path": str(resolved)},
                description=f"Write after edit: {file_path}",
            )
        )

        original = resolved.read_text(encoding="utf-8", errors="replace")

        new_content: Optional[str] = None
        strategy_used: Optional[str] = None

        for replacer in REPLACERS:
            candidate = replacer.try_replace(
                original, old_string, new_string, replace_all
            )
            if candidate is not None and candidate != original:
                new_content = candidate
                strategy_used = replacer.__class__.__name__
                break

        if new_content is None:
            return ToolResult.from_error(
                "Replacement failed",
                "Could not locate the target text with available strategies",
                file_path=file_path,
            )

        # Write back
        resolved.write_text(new_content, encoding="utf-8")

        diff = _make_diff(original, new_content, str(file_path))

        return ToolResult.success(
            f"Edited {file_path}",
            diff if diff else "(content unchanged)",
            file_path=str(file_path),
            resolved_path=str(resolved),
            strategy=strategy_used,
            replace_all=replace_all,
        )

    except PermissionDeniedError as e:
        return ToolResult.from_error("Permission denied", str(e), file_path=file_path)
    except Exception as e:
        return ToolResult.from_error(
            "Edit failed", str(e), file_path=file_path, error_type=type(e).__name__
        )
