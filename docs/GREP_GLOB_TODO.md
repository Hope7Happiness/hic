# Grep, Glob, and Todo Tools

This document describes the new search and task tools added in Phase 3.

## Overview

- `grep` searches file contents with regex
- `glob` finds files by pattern
- `todowrite` and `todoread` manage session-scoped todos

All tools follow the modern tool architecture:

1. Request permission via `ctx.ask()`
2. Validate paths or inputs
3. Truncate large outputs with `ctx.truncate_output()`
4. Return a structured `ToolResult`

## grep

Search file contents using a regular expression. Uses ripgrep when available.

Signature:

```python
async def grep(
    pattern: str,
    ctx,
    path: Optional[str] = None,
    include: Optional[str] = None,
    max_results: int = 100,
    context_lines: int = 0,
)
```

Parameters:

- `pattern`: regex pattern
- `path`: base directory (defaults to working directory)
- `include`: optional glob filter (e.g., `"*.py"`)
- `max_results`: max matches to return
- `context_lines`: lines of context around each match

Output format:

```
path/to/file.py:42:5: matched line text
```

Metadata:

- `match_count`
- `file_count`
- `source` (`rg` or `python` fallback)
- `is_truncated` (from OutputTruncator)

Permissions:

- Uses `PermissionType.READ`

## glob

Find files matching a glob pattern. Uses ripgrep when available.

Signature:

```python
async def glob(
    pattern: str,
    ctx,
    path: Optional[str] = None,
    max_results: int = 100,
    include_hidden: bool = False,
)
```

Parameters:

- `pattern`: glob pattern (e.g., `"**/*.md"`)
- `path`: base directory (defaults to working directory)
- `max_results`: max results to return
- `include_hidden`: include dotfiles

Metadata:

- `match_count`
- `source` (`rg` or `python` fallback)
- `is_truncated` (from OutputTruncator)

Permissions:

- Uses `PermissionType.READ`

## todowrite / todoread

Manage a session-scoped todo list stored in `Context` metadata.

Signature:

```python
async def todowrite(todos: list[dict[str, Any]], ctx)
async def todoread(ctx)
```

Todo item schema:

```
{
  "id": "unique-id",
  "content": "Task description",
  "status": "pending|in_progress|completed|cancelled",
  "priority": "high|medium|low"
}
```

Metadata:

- `count`
- `updated_at` (todoread)

Permissions:

- Uses `PermissionType.TODO`

## Example

```python
from agent.tools import grep, glob, todowrite, todoread
from agent.tool import Tool
from agent.context import create_auto_approve_context

ctx = create_auto_approve_context(
    patterns={"read": ["*"], "todo": ["*"]},
    working_directory=".",
)

grep_tool = Tool(grep, context=ctx)
glob_tool = Tool(glob, context=ctx)
todowrite_tool = Tool(todowrite, context=ctx)
todoread_tool = Tool(todoread, context=ctx)

# Find python files
files = glob_tool.call(pattern="**/*.py")

# Search for TODO markers
matches = grep_tool.call(pattern="TODO", include="*.py")

# Record tasks
todos = [
    {"id": "1", "content": "Review TODO matches", "status": "pending", "priority": "high"}
]
todowrite_tool.call(todos=todos)

# Read back
print(todoread_tool.call())
```
