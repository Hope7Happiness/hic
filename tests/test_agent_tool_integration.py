"""
Test agent integration with new async tool system.

This tests that:
1. Agent can use async tools
2. Context is properly injected
3. ToolResult is properly converted to string for LLM
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Direct module imports to avoid __init__.py issues
import importlib.util


def load_module(name, path):
    """Load a module directly from file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Load modules in dependency order
agent_dir = Path(__file__).parent.parent / "agent"

print("Loading modules...")
tool_result_mod = load_module("agent.tool_result", agent_dir / "tool_result.py")
truncation_mod = load_module("agent.truncation", agent_dir / "truncation.py")
permissions_mod = load_module("agent.permissions", agent_dir / "permissions.py")
context_mod = load_module("agent.context", agent_dir / "context.py")
bash_mod = load_module("agent.tools.bash", agent_dir / "tools" / "bash.py")
tool_mod = load_module("agent.tool", agent_dir / "tool.py")

# Import classes
Tool = tool_mod.Tool
bash = bash_mod.bash
Context = context_mod.Context


async def test_async_tool_direct():
    """Test async tool call directly."""
    print("\n" + "=" * 70)
    print("TEST: Direct async tool call")
    print("=" * 70)

    # Create context
    ctx = context_mod.create_auto_approve_context(patterns={"bash": ["*"]})

    # Create tool with context
    bash_tool = Tool(bash, context=ctx)

    print(f"Tool created: {bash_tool}")
    print(f"Is async: {bash_tool.is_async}")
    print(f"Has context: {bash_tool.context is not None}")

    # Call tool
    print("\nCalling: echo 'Hello from async tool'")
    result = await bash_tool.call_async(command="echo 'Hello from async tool'")

    print(f"\nResult type: {type(result)}")
    print(f"Result is_success: {result.is_success}")
    print(f"Result as string:\n{str(result)}")

    assert result.is_success, "Tool call should succeed"
    assert "Hello from async tool" in result.output, (
        "Output should contain expected text"
    )

    print("\n✓ Direct async tool call works!")


async def test_sync_tool_compatibility():
    """Test that sync tools still work."""
    print("\n" + "=" * 70)
    print("TEST: Sync tool compatibility")
    print("=" * 70)

    # Create a simple sync tool
    def my_sync_tool(text: str) -> str:
        """A simple sync tool for testing."""
        return f"You said: {text}"

    sync_tool = Tool(my_sync_tool)

    print(f"Tool created: {sync_tool}")
    print(f"Is async: {sync_tool.is_async}")

    # Call sync tool with call_async (should work)
    print("\nCalling: my_sync_tool with 'hello'")
    result = await sync_tool.call_async(text="hello")

    print(f"Result: {result}")

    assert result == "You said: hello", "Sync tool should work via call_async"

    print("\n✓ Sync tool compatibility works!")


async def test_context_injection():
    """Test that context is auto-injected."""
    print("\n" + "=" * 70)
    print("TEST: Context auto-injection")
    print("=" * 70)

    # Create a tool that uses ctx parameter
    async def tool_with_ctx(command: str, ctx) -> str:
        """Tool that requires ctx parameter."""
        from agent.context import Context

        assert isinstance(ctx, Context), "ctx should be Context instance"
        return f"Context injected! Command: {command}"

    ctx = context_mod.create_auto_approve_context(patterns={"bash": ["*"]})
    tool = Tool(tool_with_ctx, context=ctx)

    print(f"Tool created: {tool}")
    print(f"Parameters (visible): {[k for k in tool.parameters.keys() if k != 'ctx']}")

    # Call without providing ctx - it should be injected
    print("\nCalling without ctx parameter...")
    result = await tool.call_async(command="ls")

    print(f"Result: {result}")

    assert "Context injected!" in result, "Context should be auto-injected"

    print("\n✓ Context auto-injection works!")


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("AGENT TOOL INTEGRATION TESTS")
    print("=" * 70)

    try:
        await test_async_tool_direct()
        await test_sync_tool_compatibility()
        await test_context_injection()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
