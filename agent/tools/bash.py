"""
Enhanced bash tool with permission system, output truncation, and security features.

This module provides a modern, secure bash tool that integrates with the new
infrastructure (Context, Permissions, ToolResult, Truncation).

Key features:
- Permission-based execution
- Automatic output truncation
- Dangerous command detection
- Process management with abort support
- Detailed error handling
- Configurable allowed commands
"""

import subprocess
import asyncio
import shlex
import signal
import os
from typing import Optional, Set
from pathlib import Path

# Import modules directly to avoid triggering agent/__init__.py
import sys
from pathlib import Path

# Add agent directory to path if not already there
agent_dir = Path(__file__).parent.parent
if str(agent_dir) not in sys.path:
    sys.path.insert(0, str(agent_dir.parent))

# Import directly using importlib to avoid __init__.py
import importlib.util


def _load_agent_module(module_name, file_name):
    """Load an agent module directly without triggering package init."""
    module_path = agent_dir / file_name
    spec = importlib.util.spec_from_file_location(f"agent.{module_name}", module_path)
    if spec is None or spec.loader is None:
        # Fallback to regular import
        return importlib.import_module(f"agent.{module_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Load required modules
try:
    context_mod = _load_agent_module("context", "context.py")
    permissions_mod = _load_agent_module("permissions", "permissions.py")
    tool_result_mod = _load_agent_module("tool_result", "tool_result.py")

    Context = context_mod.Context
    PermissionType = permissions_mod.PermissionType
    PermissionRequest = permissions_mod.PermissionRequest
    PermissionDeniedError = permissions_mod.PermissionDeniedError
    is_command_dangerous = permissions_mod.is_command_dangerous
    is_path_safe = permissions_mod.is_path_safe
    ToolResult = tool_result_mod.ToolResult
except:
    # Last resort: try regular imports
    from agent.context import Context
    from agent.permissions import (
        PermissionType,
        PermissionRequest,
        PermissionDeniedError,
        is_command_dangerous,
        is_path_safe,
    )
    from agent.tool_result import ToolResult


# Default safe commands (read-only operations)
DEFAULT_SAFE_COMMANDS = {
    # File listing and inspection
    "ls",
    "ll",
    "dir",
    "cat",
    "head",
    "tail",
    "less",
    "more",
    "file",
    "stat",
    "tree",
    # Directory operations (read-only)
    "pwd",
    "cd",
    # Text processing
    "grep",
    "egrep",
    "fgrep",
    "sed",
    "awk",
    "cut",
    "sort",
    "uniq",
    "wc",
    "tr",
    "diff",
    "comm",
    "column",
    # System information (read-only)
    "whoami",
    "hostname",
    "uname",
    "date",
    "cal",
    "df",
    "du",
    "ps",
    "top",
    "uptime",
    "env",
    "printenv",
    "id",
    "groups",
    # File search
    "find",
    "locate",
    "which",
    "whereis",
    "type",
    # Output
    "echo",
    "printf",
    # Archive inspection (read-only)
    "tar",
    "gzip",
    "gunzip",
    "zip",
    "unzip",
    # Git (read-only)
    "git",
    # Package managers (read-only queries)
    "npm",
    "pip",
    "brew",
}


def extract_base_commands(command: str) -> list[str]:
    """
    Extract base commands from a shell command.

    Handles pipes, redirects, and complex command structures.

    Args:
        command: Shell command string

    Returns:
        List of base command names

    Examples:
        >>> extract_base_commands("ls -la")
        ['ls']
        >>> extract_base_commands("cat file | grep pattern")
        ['cat', 'grep']
        >>> extract_base_commands("echo 'hello' > output.txt")
        ['echo']
    """
    # Split by pipes
    pipe_parts = command.split("|")
    base_commands = []

    for part in pipe_parts:
        # Remove redirects for command extraction
        for redirect in [">", "<", ">>", "2>", "2>&1", "&>"]:
            if redirect in part:
                part = part.split(redirect)[0]

        # Check for command chains (&&, ||, ;)
        has_chain = False
        for chain in ["&&", "||", ";"]:
            if chain in part:
                has_chain = True
                # Process each chained command
                for subpart in part.split(chain):
                    cmd = extract_base_command_from_part(subpart.strip())
                    if cmd:
                        base_commands.append(cmd)
                break  # Exit chain checking loop

        # Only process as single command if no chains found
        if not has_chain:
            cmd = extract_base_command_from_part(part.strip())
            if cmd:
                base_commands.append(cmd)

    return base_commands


def extract_base_command_from_part(part: str) -> Optional[str]:
    """Extract the base command from a command part."""
    try:
        tokens = shlex.split(part)
        if not tokens:
            return None

        base_cmd = tokens[0]

        # Handle sudo, nohup, etc.
        if base_cmd in ["sudo", "nohup", "time", "nice"]:
            return tokens[1] if len(tokens) > 1 else base_cmd

        return base_cmd
    except ValueError:
        # If shlex fails, try simple split
        tokens = part.split()
        return tokens[0] if tokens else None


def validate_command_safety(
    command: str, allowed_commands: Optional[Set[str]] = None
) -> tuple[bool, Optional[str]]:
    """
    Validate if a command is safe to execute.

    Args:
        command: Command to validate
        allowed_commands: Set of allowed commands (None = allow all)

    Returns:
        Tuple of (is_safe, error_message)
    """
    # Check for dangerous commands
    is_dangerous, danger_reason = is_command_dangerous(command)
    if is_dangerous:
        return False, danger_reason

    # If no whitelist, allow (but already checked for dangerous)
    if allowed_commands is None:
        return True, None

    # Extract base commands
    base_commands = extract_base_commands(command)

    # Check each command against whitelist
    for base_cmd in base_commands:
        if base_cmd not in allowed_commands:
            return False, (
                f"Command '{base_cmd}' is not in the allowed list. "
                f"Allowed: {', '.join(sorted(allowed_commands))}"
            )

    return True, None


async def bash(
    command: str,
    ctx,  # Context type
    timeout: int = 120,
    working_dir: Optional[str] = None,
    allowed_commands: Optional[Set[str]] = DEFAULT_SAFE_COMMANDS,
    allow_dangerous: bool = False,
):  # Returns ToolResult
    """
    Execute a shell command with permission checking and output management.

    Args:
        command: Shell command to execute
        ctx: Execution context
        timeout: Maximum execution time in seconds (default: 120)
        working_dir: Working directory (default: ctx.working_directory)
        allowed_commands: Set of allowed commands (None = allow all, DEFAULT_SAFE_COMMANDS for safe mode)
        allow_dangerous: If True, skip dangerous command check (requires permission)

    Returns:
        ToolResult with command output or error

    Examples:
        >>> ctx = create_auto_approve_context(patterns={"bash": ["ls *"]})
        >>> result = await bash("ls -la", ctx)
        >>> print(result.is_success)
        True

        >>> result = await bash("rm -rf /", ctx)  # Blocked by dangerous command check
        >>> print(result.is_error)
        True
    """
    try:
        # Validate working directory
        if working_dir is None:
            working_dir = ctx.working_directory

        # Ensure working_dir is a string for safety check
        work_dir_str = str(working_dir) if working_dir else "."

        # Check if working directory is safe
        if not is_path_safe(work_dir_str, ctx.working_directory):
            return ToolResult.from_error(
                "Invalid working directory",
                f"Directory '{work_dir_str}' is outside the allowed workspace",
                command=command,
                working_dir=work_dir_str,
            )

        # Validate command safety
        if not allow_dangerous:
            is_safe, safety_error = validate_command_safety(command, allowed_commands)
            if not is_safe:
                return ToolResult.from_error(
                    "Command not allowed",
                    safety_error or "Command blocked by safety check",
                    command=command,
                    allowed_commands=list(allowed_commands)
                    if allowed_commands
                    else None,
                )

        # Check for dangerous commands if not explicitly allowed
        if not allow_dangerous:
            is_dangerous, danger_reason = is_command_dangerous(command)
            if is_dangerous:
                return ToolResult.from_error(
                    "Dangerous command blocked",
                    danger_reason or "Command matches dangerous pattern",
                    command=command,
                )

        # Request permission
        permission_metadata = {
            "command": command,
            "working_dir": working_dir,
            "timeout": timeout,
            "allowed_commands": list(allowed_commands) if allowed_commands else "all",
        }

        await ctx.ask(
            PermissionRequest(
                permission=PermissionType.BASH,
                patterns=[command],
                metadata=permission_metadata,
                description=f"Execute command: {command[:50]}{'...' if len(command) > 50 else ''}",
            )
        )

        # Check abort before execution
        ctx.check_abort()

        # Execute command
        start_time = asyncio.get_event_loop().time()

        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_dir,
            preexec_fn=os.setsid if os.name != "nt" else None,  # Unix only
        )

        # Wait for process with abort support
        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            exit_code = process.returncode

        except asyncio.TimeoutError:
            # Kill process group on timeout
            try:
                if os.name != "nt":
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                else:
                    process.terminate()

                # Give it a moment to terminate
                await asyncio.sleep(0.5)

                # Force kill if still alive
                if process.returncode is None:
                    if os.name != "nt":
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    else:
                        process.kill()

            except Exception as e:
                pass  # Process might already be dead

            return ToolResult.from_error(
                "Command timeout",
                f"Command timed out after {timeout} seconds",
                command=command,
                timeout=timeout,
            )

        # Check if aborted during execution
        if ctx.is_aborted:
            return ToolResult.from_error(
                "Command aborted", "Command was aborted by user", command=command
            )

        end_time = asyncio.get_event_loop().time()
        duration_ms = int((end_time - start_time) * 1000)

        # Decode output
        stdout = stdout_data.decode("utf-8", errors="replace")
        stderr = stderr_data.decode("utf-8", errors="replace")

        # Prepare output
        if exit_code == 0:
            # Success
            output = stdout if stdout else "(no output)"

            # Truncate large output
            truncated_output, trunc_meta = ctx.truncate_output(
                output, context="bash command output"
            )

            return ToolResult.success(
                f"Executed: {command[:50]}{'...' if len(command) > 50 else ''}",
                truncated_output,
                command=command,
                exit_code=exit_code,
                duration_ms=duration_ms,
                working_dir=working_dir,
                **trunc_meta,
            )
        else:
            # Command failed
            error_output = stderr if stderr else stdout
            if not error_output:
                error_output = f"Command failed with exit code {exit_code}"

            # Truncate error output
            truncated_error, trunc_meta = ctx.truncate_output(
                error_output, context="bash error output"
            )

            return ToolResult.from_error(
                f"Command failed (exit {exit_code})",
                truncated_error,
                command=command,
                exit_code=exit_code,
                duration_ms=duration_ms,
                working_dir=working_dir,
                **trunc_meta,
            )

    except PermissionDeniedError as e:
        return ToolResult.from_error("Permission denied", str(e), command=command)

    except Exception as e:
        return ToolResult.from_error(
            "Execution failed", str(e), command=command, error_type=type(e).__name__
        )


# Convenience function for backward compatibility
async def restricted_bash(
    command: str,
    ctx,  # Context type
    timeout: int = 120,
    **kwargs,
):  # Returns ToolResult
    """
    Alias for bash() with safe defaults (restricted to DEFAULT_SAFE_COMMANDS).

    This is a convenience wrapper that enforces the default safe command list.
    """
    return await bash(
        command=command,
        ctx=ctx,
        timeout=timeout,
        allowed_commands=DEFAULT_SAFE_COMMANDS,
        allow_dangerous=False,
        **kwargs,
    )
