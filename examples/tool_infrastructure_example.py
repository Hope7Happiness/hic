"""
Example: Using the new tool infrastructure (Context, Permissions, ToolResult, Truncation).

This example demonstrates how to:
1. Create a context with permission handling
2. Write tools that use ToolResult
3. Request permissions before operations
4. Automatically truncate large outputs
5. Handle errors properly

Run with: python examples/tool_infrastructure_example.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Direct module imports to avoid openai import issue
import importlib.util


def load_module(name, path):
    """Load a module directly from file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Load modules
tool_result_mod = load_module("agent.tool_result", "agent/tool_result.py")
truncation_mod = load_module("agent.truncation", "agent/truncation.py")
permissions_mod = load_module("agent.permissions", "agent/permissions.py")
context_mod = load_module("agent.context", "agent/context.py")

# Import classes
ToolResult = tool_result_mod.ToolResult
Attachment = tool_result_mod.Attachment
OutputTruncator = truncation_mod.OutputTruncator
PermissionType = permissions_mod.PermissionType
PermissionRequest = permissions_mod.PermissionRequest
PermissionDeniedError = permissions_mod.PermissionDeniedError
AutoApproveHandler = permissions_mod.AutoApproveHandler
Context = context_mod.Context
create_auto_approve_context = context_mod.create_auto_approve_context


# =============================================================================
# Example Tool Implementations
# =============================================================================


async def read_file_tool(file_path: str, ctx: Context) -> ToolResult:
    """
    Example tool: Read a file with permission checking and error handling.

    Args:
        file_path: Path to file to read
        ctx: Execution context

    Returns:
        ToolResult with file contents or error
    """
    try:
        # Request permission
        await ctx.ask(
            PermissionRequest(
                permission=PermissionType.READ,
                patterns=[file_path],
                metadata={"file_path": file_path},
                description=f"Read file: {file_path}",
            )
        )

        # Check for abort
        ctx.check_abort()

        # Read file
        path = Path(file_path)
        if not path.exists():
            return ToolResult.from_error(
                f"File not found: {file_path}",
                f"The file '{file_path}' does not exist",
                file_path=file_path,
            )

        content = path.read_text()

        # Truncate if needed
        truncated_content, trunc_meta = ctx.truncate_output(content, "file read")

        return ToolResult.success(
            f"Read {file_path}",
            truncated_content,
            file_path=file_path,
            size_bytes=len(content),
            lines=len(content.split("\n")),
            **trunc_meta,
        )

    except PermissionDeniedError as e:
        return ToolResult.from_error("Permission denied", str(e), file_path=file_path)
    except Exception as e:
        return ToolResult.from_error(
            f"Failed to read {file_path}",
            str(e),
            file_path=file_path,
            error_type=type(e).__name__,
        )


async def write_file_tool(file_path: str, content: str, ctx: Context) -> ToolResult:
    """
    Example tool: Write a file with permission checking.

    Args:
        file_path: Path to file to write
        content: Content to write
        ctx: Execution context

    Returns:
        ToolResult indicating success or failure
    """
    try:
        path = Path(file_path)
        exists = path.exists()

        # Request permission
        await ctx.ask(
            PermissionRequest(
                permission=PermissionType.WRITE,
                patterns=[file_path],
                metadata={
                    "file_path": file_path,
                    "exists": exists,
                    "size_bytes": len(content),
                },
                description=f"{'Update' if exists else 'Create'} file: {file_path}",
            )
        )

        # Write file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

        return ToolResult.success(
            f"{'Updated' if exists else 'Created'} {file_path}",
            f"Successfully wrote {len(content)} bytes to {file_path}",
            file_path=file_path,
            size_bytes=len(content),
            lines=len(content.split("\n")),
            existed=exists,
        )

    except PermissionDeniedError as e:
        return ToolResult.from_error("Permission denied", str(e), file_path=file_path)
    except Exception as e:
        return ToolResult.from_error(
            f"Failed to write {file_path}",
            str(e),
            file_path=file_path,
            error_type=type(e).__name__,
        )


async def generate_report_tool(lines: int, ctx: Context) -> ToolResult:
    """
    Example tool: Generate a large report to demonstrate truncation.

    Args:
        lines: Number of lines to generate
        ctx: Execution context

    Returns:
        ToolResult with report (potentially truncated)
    """
    try:
        # Generate large output
        report_lines = []
        for i in range(lines):
            report_lines.append(f"Line {i + 1}: Data point {i * 10}, Status: OK")

            # Check for abort periodically
            if i % 100 == 0:
                ctx.check_abort()

                # Stream progress
                await ctx.stream_metadata(
                    {
                        "progress": i / lines * 100,
                        "status": f"Generated {i}/{lines} lines",
                    }
                )

        report = "\n".join(report_lines)

        # Truncate if needed (automatic)
        truncated_report, trunc_meta = ctx.truncate_output(report, "report generation")

        return ToolResult.success(
            f"Generated {lines}-line report",
            truncated_report,
            lines_generated=lines,
            **trunc_meta,
        )

    except Exception as e:
        return ToolResult.from_error(
            "Failed to generate report", str(e), error_type=type(e).__name__
        )


# =============================================================================
# Example Usage
# =============================================================================


async def main():
    """Demonstrate the tool infrastructure."""

    print("=" * 70)
    print("TOOL INFRASTRUCTURE EXAMPLE")
    print("=" * 70)
    print()

    # Example 1: Context with auto-approve patterns
    print("1. Creating context with auto-approve patterns...")
    ctx = create_auto_approve_context(
        patterns={"read": ["*.md", "*.txt", "*.py"], "write": ["/tmp/*", "test_*"]},
        working_directory=".",
    )
    print(f"   ✓ Context created: {ctx.session_id}")
    print()

    # Example 2: Read a file (should auto-approve)
    print("2. Reading Python file (auto-approved)...")
    result = await read_file_tool(__file__, ctx)
    print(f"   {'✓' if result.is_success else '✗'} {result.title}")
    if result.is_success:
        print(f"   - Size: {result.metadata.get('size_bytes')} bytes")
        print(f"   - Lines: {result.metadata.get('lines')}")
        if result.metadata.get("is_truncated"):
            print(
                f"   - Output truncated at line {result.metadata.get('truncated_at_line')}"
            )
    print()

    # Example 3: Write a test file (should auto-approve for /tmp/)
    print("3. Writing test file to /tmp (auto-approved)...")
    test_content = "Hello, World!\nThis is a test file.\n"
    result = await write_file_tool(
        "/tmp/test_tool_infrastructure.txt", test_content, ctx
    )
    print(f"   {'✓' if result.is_success else '✗'} {result.title}")
    if result.is_success:
        print(f"   - Path: {result.metadata.get('file_path')}")
        print(f"   - Existed: {result.metadata.get('existed')}")
    print()

    # Example 4: Generate large report (demonstrates truncation)
    print("4. Generating large report (demonstrates truncation)...")
    result = await generate_report_tool(3000, ctx)
    print(f"   {'✓' if result.is_success else '✗'} {result.title}")
    if result.is_success:
        print(f"   - Lines generated: {result.metadata.get('lines_generated')}")
        print(f"   - Total lines: {result.metadata.get('total_lines')}")
        print(f"   - Is truncated: {result.metadata.get('is_truncated')}")
        if result.metadata.get("is_truncated"):
            print(
                f"   - Full output saved to: {result.metadata.get('full_output_file')}"
            )
    print()

    # Example 5: Try to read a file that requires permission (not auto-approved)
    print("5. Trying to read file that requires explicit permission...")
    ctx2 = create_auto_approve_context(
        patterns={"read": ["*.md"]}  # Only allow .md files
    )
    result = await read_file_tool("agent/permissions.py", ctx2)
    print(f"   {'✓' if result.is_success else '✗'} {result.title}")
    if result.is_error:
        print(f"   - Error: {result.error}")
    print()

    # Example 6: Context with abort signal
    print("6. Demonstrating abort signal...")
    ctx3 = create_auto_approve_context()

    # Start a long operation and abort it
    async def long_operation():
        try:
            result = await generate_report_tool(10000, ctx3)
            return result
        except RuntimeError as e:
            print(f"   ✓ Operation aborted: {e}")
            return ToolResult.from_error("Aborted", str(e))

    # Abort after a short delay
    async def abort_after_delay():
        await asyncio.sleep(0.01)
        ctx3.abort("User cancelled")

    await asyncio.gather(long_operation(), abort_after_delay())
    print()

    # Example 7: ToolResult formatting for LLM
    print("7. ToolResult formatting for LLM consumption...")
    result = ToolResult.success(
        "Executed command",
        "Command output here\nLine 2\nLine 3",
        exit_code=0,
        duration_ms=123,
    )
    result.add_attachment(
        Attachment(
            type="file",
            content=b"file data",
            filename="output.txt",
            mime_type="text/plain",
        )
    )

    llm_string = result.to_llm_string()
    print("   LLM-formatted output:")
    print("   " + "\n   ".join(llm_string.split("\n")))
    print()

    # Example 8: Session metadata
    print("8. Using session metadata...")
    ctx4 = create_auto_approve_context()
    ctx4.set_session_metadata("user_id", "user_123")
    ctx4.set_session_metadata("workspace", "/project")
    ctx4.update_session_metadata(tool_count=5, last_tool="read_file")

    print("   Session metadata:")
    for key, value in ctx4.get_all_metadata().items():
        print(f"   - {key}: {value}")
    print()

    print("=" * 70)
    print("✅ All examples completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
