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
from typing import Optional, Protocol, Callable
import difflib
import importlib.util
import os
import time

_levenshtein_distance: Optional[Callable[[str, str], int]]
try:
    from Levenshtein import distance as _levenshtein_distance
except ImportError:  # Fallback to difflib if dependency missing
    _levenshtein_distance = None


def levenshtein_distance(a: str, b: str) -> int:
    if _levenshtein_distance is None:
        return int(
            (1 - difflib.SequenceMatcher(None, a, b).ratio()) * max(len(a), len(b))
        )
    return _levenshtein_distance(a, b)


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


class FileLockTimeout(Exception):
    pass


class _SimpleFileLock:
    def __init__(self, lock_path: Path, timeout: float = 5.0, poll: float = 0.1):
        self.lock_path = lock_path
        self.timeout = timeout
        self.poll = poll
        self._fd = None

    def acquire(self) -> None:
        start = time.time()
        while True:
            try:
                self._fd = os.open(
                    str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY
                )
                return
            except FileExistsError:
                if time.time() - start >= self.timeout:
                    raise FileLockTimeout(
                        f"Timed out waiting for lock {self.lock_path}"
                    )
                time.sleep(self.poll)

    def release(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None
        try:
            if self.lock_path.exists():
                self.lock_path.unlink()
        except Exception:
            pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()


filelock = None
try:
    import importlib

    filelock = importlib.import_module("filelock")
except Exception:
    filelock = None


def _get_lock(lock_path: Path, timeout: float):
    if filelock is not None:
        _FileLock = getattr(filelock, "FileLock")
        _FileLockTimeout = getattr(filelock, "Timeout")

        class _LockWrapper:
            def __init__(self, path: Path, timeout: float = 5.0):
                self._lock = _FileLock(str(path))
                self._timeout = timeout

            def __enter__(self):
                try:
                    self._lock.acquire(timeout=self._timeout)
                except _FileLockTimeout as e:
                    raise FileLockTimeout(str(e))
                return self

            def __exit__(self, exc_type, exc, tb):
                self._lock.release()

        return _LockWrapper(lock_path, timeout=timeout)
    return _SimpleFileLock(lock_path, timeout=timeout)


class Replacer(Protocol):
    def try_replace(
        self, content: str, old: str, new: str, replace_all: bool
    ) -> Optional[tuple[str, float, int]]: ...


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
    ) -> Optional[tuple[str, float, int]]:
        if old not in content:
            return None
        occurrences = content.count(old)
        if replace_all:
            return content.replace(old, new), 1.0, occurrences
        if content.count(old) == 1:
            return content.replace(old, new, 1), 1.0, occurrences
        return None


class LineTrimmedReplacer:
    def try_replace(
        self, content: str, old: str, new: str, replace_all: bool
    ) -> Optional[tuple[str, float, int]]:
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
        similarity = _similar(replaced, content)
        if similarity < SIMILARITY_THRESHOLD:
            return None
        occurrences = content_joined.count(old_joined)
        return replaced, similarity, occurrences


class BlockAnchorReplacer:
    def try_replace(
        self, content: str, old: str, new: str, replace_all: bool
    ) -> Optional[tuple[str, float, int]]:
        content_lines = content.splitlines()
        old_lines = old.splitlines()
        if len(old_lines) < 2:
            return None

        first = old_lines[0].strip()
        last = old_lines[-1].strip()

        if not first or not last:
            return None

        matches = []
        for i in range(len(content_lines)):
            if content_lines[i].strip() != first:
                continue
            for j in range(i + 1, len(content_lines)):
                if content_lines[j].strip() == last:
                    block = "\n".join(content_lines[i : j + 1])
                    similarity = _similar(block, old)
                    if similarity >= SIMILARITY_THRESHOLD:
                        matches.append((i, j, block, similarity))
                    break

        if not matches:
            return None

        matches.sort(key=lambda x: x[3], reverse=True)
        if replace_all:
            new_lines = content_lines[:]
            offset = 0
            for i, j, _, _ in matches:
                start = i + offset
                end = j + offset
                new_lines[start : end + 1] = new.splitlines()
                offset += len(new.splitlines()) - (end - start + 1)
            return "\n".join(new_lines), matches[0][3], len(matches)

        i, j, _, similarity = matches[0]
        new_lines = content_lines[:i] + new.splitlines() + content_lines[j + 1 :]
        return "\n".join(new_lines), similarity, len(matches)


class WhitespaceNormalizedReplacer:
    def try_replace(
        self, content: str, old: str, new: str, replace_all: bool
    ) -> Optional[tuple[str, float, int]]:
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
        similarity = _similar(replaced, norm_content)
        if similarity < SIMILARITY_THRESHOLD:
            return None
        # We cannot easily reconstruct exact whitespace; fallback to original replace
        if old in content:
            occurrences = content.count(old)
            return (
                content.replace(old, new, 0 if replace_all else 1),
                similarity,
                occurrences,
            )
        return None


class IndentationFlexibleReplacer:
    def try_replace(
        self, content: str, old: str, new: str, replace_all: bool
    ) -> Optional[tuple[str, float, int]]:
        content_lines = content.splitlines()
        old_lines = old.splitlines()
        if not old_lines:
            return None

        def strip_indent(lines: list[str]) -> list[str]:
            return [line.lstrip() for line in lines]

        target = strip_indent(old_lines)
        matches = []
        for i in range(len(content_lines) - len(old_lines) + 1):
            window = content_lines[i : i + len(old_lines)]
            if strip_indent(window) == target:
                window_text = "\n".join(window)
                similarity = _similar(window_text, old)
                matches.append((i, similarity))

        if not matches:
            return None

        matches.sort(key=lambda x: x[1], reverse=True)
        if replace_all:
            new_lines = content_lines[:]
            offset = 0
            for i, _ in matches:
                start = i + offset
                end = start + len(old_lines)
                new_lines[start:end] = new.splitlines()
                offset += len(new.splitlines()) - len(old_lines)
            return "\n".join(new_lines), matches[0][1], len(matches)

        i, similarity = matches[0]
        new_lines = (
            content_lines[:i] + new.splitlines() + content_lines[i + len(old_lines) :]
        )
        return "\n".join(new_lines), similarity, len(matches)


class EscapeNormalizedReplacer:
    def try_replace(
        self, content: str, old: str, new: str, replace_all: bool
    ) -> Optional[tuple[str, float, int]]:
        def unescape(s: str) -> str:
            return (
                s.replace("\\\\", "\\")
                .replace("\\n", "\n")
                .replace("\\t", "\t")
                .replace("\\r", "\r")
                .replace('\\"', '"')
                .replace("\\'", "'")
            )

        old_unescaped = unescape(old)
        new_unescaped = unescape(new)

        if old_unescaped not in content:
            return None

        occurrences = content.count(old_unescaped)
        if replace_all:
            replaced = content.replace(old_unescaped, new_unescaped)
        else:
            if occurrences != 1:
                return None
            replaced = content.replace(old_unescaped, new_unescaped, 1)

        similarity = _similar(old_unescaped, old)
        return replaced, similarity, occurrences


class TrimmedBoundaryReplacer:
    def try_replace(
        self, content: str, old: str, new: str, replace_all: bool
    ) -> Optional[tuple[str, float, int]]:
        old_trim = old.strip()
        if not old_trim:
            return None
        if old_trim not in content:
            return None
        occurrences = content.count(old_trim)
        if replace_all:
            replaced = content.replace(old_trim, new)
        else:
            if occurrences != 1:
                return None
            replaced = content.replace(old_trim, new, 1)
        similarity = _similar(old_trim, old)
        return replaced, similarity, occurrences


class ContextAwareReplacer:
    def try_replace(
        self, content: str, old: str, new: str, replace_all: bool
    ) -> Optional[tuple[str, float, int]]:
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
                    replaced = "\n".join(
                        content_lines[:i]
                        + new.splitlines()
                        + content_lines[i + len(old_lines) :]
                    )
                    return replaced, best_ratio, 1
                # single replace
                replaced = "\n".join(
                    content_lines[:i]
                    + new.splitlines()
                    + content_lines[i + len(old_lines) :]
                )
                return replaced, best_ratio, 1

        return None


class MultiOccurrenceReplacer:
    def try_replace(
        self, content: str, old: str, new: str, replace_all: bool
    ) -> Optional[tuple[str, float, int]]:
        occurrences = content.count(old)
        if occurrences == 0:
            return None
        if replace_all:
            return content.replace(old, new), 1.0, occurrences
        if occurrences == 1:
            return content.replace(old, new, 1), 1.0, occurrences
        return None


REPLACERS: list[Replacer] = [
    SimpleReplacer(),
    LineTrimmedReplacer(),
    BlockAnchorReplacer(),
    IndentationFlexibleReplacer(),
    EscapeNormalizedReplacer(),
    TrimmedBoundaryReplacer(),
    WhitespaceNormalizedReplacer(),
    ContextAwareReplacer(),
    MultiOccurrenceReplacer(),
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
    lock_timeout: float = 5.0,
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

        lock_path = Path(str(resolved) + ".lock")
        try:
            with _get_lock(lock_path, timeout=lock_timeout):
                original = resolved.read_text(encoding="utf-8", errors="replace")

                new_content: Optional[str] = None
                strategy_used: Optional[str] = None
                similarity: Optional[float] = None
                occurrences: Optional[int] = None

                for replacer in REPLACERS:
                    candidate: Optional[tuple[str, float, int]] = replacer.try_replace(
                        original, old_string, new_string, replace_all
                    )
                    if candidate is not None:
                        replaced, sim, count = candidate
                        if replaced != original:
                            new_content = replaced
                            similarity = sim
                            occurrences = count
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
        except FileLockTimeout:
            return ToolResult.from_error(
                "File locked",
                f"Timed out waiting for lock: {lock_path}",
                file_path=file_path,
            )

        diff = _make_diff(original, new_content, str(file_path))

        return ToolResult.success(
            f"Edited {file_path}",
            diff if diff else "(content unchanged)",
            file_path=str(file_path),
            resolved_path=str(resolved),
            strategy=strategy_used,
            similarity=similarity,
            occurrences=occurrences,
            replace_all=replace_all,
        )

    except PermissionDeniedError as e:
        return ToolResult.from_error("Permission denied", str(e), file_path=file_path)
    except Exception as e:
        return ToolResult.from_error(
            "Edit failed", str(e), file_path=file_path, error_type=type(e).__name__
        )
