# Edit Tool Enhancements

This document describes the enhanced edit tool behavior.

## Features

- File locking to prevent concurrent edits
- Multiple replacement strategies with similarity scoring
- Optional replace_all support
- Structured diff output

## Signature

```python
async def edit(
    file_path: str,
    old_string: str,
    new_string: str,
    ctx,
    replace_all: bool = False,
    lock_timeout: float = 5.0,
)
```

## Replacement Strategies

Strategies are tried in order until one succeeds:

1. SimpleReplacer (exact match)
2. LineTrimmedReplacer (trim each line)
3. BlockAnchorReplacer (match first/last line anchors)
4. IndentationFlexibleReplacer (ignore indentation)
5. EscapeNormalizedReplacer (normalize \n, \t, quotes)
6. TrimmedBoundaryReplacer (trim boundaries only)
7. WhitespaceNormalizedReplacer (normalize whitespace)
8. ContextAwareReplacer (similarity-based block match)
9. MultiOccurrenceReplacer (handles multiple occurrences)

## File Locking

- Lock file path: `<target>.lock`
- Default timeout: 5 seconds
- If lock cannot be acquired, returns an error:
  - title: `File locked`
  - message: `Timed out waiting for lock: <path>`

## Output Metadata

- `strategy`: strategy class name
- `similarity`: similarity score for the match
- `occurrences`: number of matches found
- `replace_all`: whether replace_all was used

## Example

```python
from agent.tools import edit
from agent.tool import Tool

edit_tool = Tool(edit)

result = edit_tool.call(
    file_path="src/app.py",
    old_string="def foo():\n    return 1",
    new_string="def foo():\n    return 2",
    replace_all=False,
    lock_timeout=5.0,
)
```
