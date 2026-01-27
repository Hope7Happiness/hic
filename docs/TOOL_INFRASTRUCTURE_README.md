# HIC Tool Infrastructure

Modern, secure, and extensible tool infrastructure for AI agents, inspired by OpenCode's architecture.

## Quick Start

```python
import asyncio
from agent.context import create_auto_approve_context
from agent.permissions import PermissionType, PermissionRequest
from agent.tool_result import ToolResult

async def my_tool(file_path: str, ctx) -> ToolResult:
    """Example tool with permissions and auto-truncation."""
    
    # 1. Request permission
    await ctx.ask(PermissionRequest(
        permission=PermissionType.READ,
        patterns=[file_path]
    ))
    
    # 2. Do the work
    from pathlib import Path
    content = Path(file_path).read_text()
    
    # 3. Auto-truncate large output
    truncated, meta = ctx.truncate_output(content)
    
    # 4. Return structured result
    return ToolResult.success(
        f"Read {file_path}",
        truncated,
        size_bytes=len(content),
        **meta
    )

# Usage
async def main():
    ctx = create_auto_approve_context(
        patterns={"read": ["*.md", "*.py"]}
    )
    
    result = await my_tool("README.md", ctx)
    print(result.to_llm_string())

asyncio.run(main())
```

## Core Components

### 1. ToolResult - Structured Returns

```python
from agent.tool_result import ToolResult, Attachment

# Success
result = ToolResult.success(
    "Operation completed",
    "detailed output here",
    key1="value1"
)

# Error
result = ToolResult.from_error(
    "Operation failed",
    "error message",
    error_type="ValueError"
)

# With attachment
result.add_attachment(Attachment.from_image("plot.png"))
```

### 2. OutputTruncator - Automatic Truncation

```python
from agent.truncation import OutputTruncator

truncator = OutputTruncator(max_lines=100, max_bytes=10000)

large_output = "line\n" * 1000
truncated, metadata = truncator.truncate(large_output, "call_id")

if metadata.is_truncated:
    print(f"Full output: {metadata.full_output_file}")
```

### 3. Permission System

```python
from agent.permissions import (
    PermissionType,
    PermissionRequest,
    AutoApproveHandler
)

# Setup handler
handler = AutoApproveHandler()
handler.add_pattern(PermissionType.READ, "*.md")
handler.add_pattern(PermissionType.BASH, "git *")

# Use in context
ctx = Context("session", "message", permission_handler=handler)

# Request permission
await ctx.ask(PermissionRequest(
    permission=PermissionType.WRITE,
    patterns=["output.txt"],
    metadata={"size": 1024}
))
```

### 4. Context - Unified Execution Context

```python
from agent.context import create_auto_approve_context

# Create context
ctx = create_auto_approve_context(
    patterns={
        "read": ["*.md", "*.txt"],
        "write": ["/tmp/*"],
        "bash": ["git status", "npm test"]
    }
)

# Use features
ctx.set_session_metadata("user_id", "user_123")
await ctx.stream_metadata({"progress": 50})
ctx.check_abort()  # Raises if aborted

truncated, meta = ctx.truncate_output(large_output)
```

## Architecture Benefits

✅ **Safety First** - Explicit permissions for all operations  
✅ **No Context Bloat** - Automatic output truncation  
✅ **Structured Data** - Consistent tool returns  
✅ **Real-time Updates** - Metadata streaming  
✅ **Error Resilience** - Comprehensive error handling  
✅ **Abort Support** - Graceful cancellation  

## Documentation

- **Implementation Details**: [TOOL_INFRASTRUCTURE_IMPLEMENTATION.md](TOOL_INFRASTRUCTURE_IMPLEMENTATION.md)
- **OpenCode Analysis**: [OPENCODE_BUILTIN_TOOLS_ANALYSIS.md](OPENCODE_BUILTIN_TOOLS_ANALYSIS.md)
- **Example Usage**: [examples/tool_infrastructure_example.py](../examples/tool_infrastructure_example.py)
- **Tests**: [tests/test_tool_infrastructure.py](../tests/test_tool_infrastructure.py)

## Running Examples

```bash
# Run the comprehensive example
python examples/tool_infrastructure_example.py

# Run tests (requires pytest)
pytest tests/test_tool_infrastructure.py -v
```

## Next Steps

With this foundation in place, we can now implement:

1. **Edit Tool** - Multi-strategy string replacement (most important!)
2. **Enhanced Bash Tool** - Tree-sitter parsing, better errors
3. **Write Tool** - File writing with diffs
4. **Grep/Glob Tools** - Code search and discovery
5. **Question Tool** - User interaction
6. **Todo Tools** - Task management

## Contributing

When implementing new tools:

1. Accept a `Context` parameter
2. Request permissions with `ctx.ask()`
3. Check abort with `ctx.check_abort()`
4. Truncate output with `ctx.truncate_output()`
5. Return `ToolResult`

See [examples/tool_infrastructure_example.py](../examples/tool_infrastructure_example.py) for patterns.
