"""
Built-in tools for the agent framework.

⚠️  DEPRECATION NOTICE ⚠️
===============================================================================
The bash/restricted_bash functions in this module are DEPRECATED and will be
removed in a future version.

Please migrate to the new enhanced bash tool:
    from agent.tools.bash import bash, restricted_bash

The new version provides:
  ✓ Async support with proper timeout/abort handling
  ✓ Structured ToolResult with metadata and attachments
  ✓ Permission system with auto-approve patterns
  ✓ Automatic output truncation (2000 lines / 50KB)
  ✓ Working directory validation
  ✓ Better error handling and diagnostics

The calculator() function is NOT deprecated and will remain in this module.

Migration example:
    OLD: from agent.builtin_tools import restricted_bash
    NEW: from agent.tools.bash import bash
         from agent.tool import Tool

         bash_tool = Tool(bash)  # Context auto-injected by Agent
         agent = Agent(llm=llm, tools=[bash_tool])

For detailed migration guide, see: docs/BASH_TOOL.md
===============================================================================

Legacy functions (for backward compatibility):
- bash: Execute shell commands in the terminal (unrestricted) [DEPRECATED]
- restricted_bash: Execute only whitelisted shell commands (secure) [DEPRECATED]
- calculator: Perform mathematical calculations [ACTIVE]
"""

import subprocess
import re
import shlex
import warnings
from typing import Optional, List, Set


def bash(command: str, timeout: int = 30) -> str:
    """
    Execute a shell command in the terminal and return the output.

    ⚠️  DEPRECATED: Use agent.tools.bash.bash() instead for better features.

    Args:
        command: The shell command to execute (e.g., "ls -la", "echo hello")
        timeout: Maximum execution time in seconds (default: 30)

    Returns:
        The command's stdout output as a string. If there's an error, returns stderr.

    Examples:
        bash("ls -la")  # List files in detail
        bash("echo 'Hello World'")  # Print text
        bash("pwd")  # Print working directory
        bash("whoami")  # Show current user

    Security Warning:
        This tool executes arbitrary shell commands. Use with caution.
        Avoid using with untrusted input.
    """
    warnings.warn(
        "agent.builtin_tools.bash() is deprecated. "
        "Use agent.tools.bash.bash() for async support, permissions, and structured results.",
        DeprecationWarning,
        stacklevel=2,
    )

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=None,  # Use current working directory
        )

        # Return stdout if successful, stderr if there's an error
        if result.returncode == 0:
            output = result.stdout.strip()
            return (
                output
                if output
                else f"Command executed successfully (no output). Exit code: 0"
            )
        else:
            error_msg = (
                result.stderr.strip()
                if result.stderr.strip()
                else result.stdout.strip()
            )
            return f"Error (exit code {result.returncode}): {error_msg}"

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing command: {str(e)}"


# Default safe commands for restricted bash
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
    # File search
    "find",
    "locate",
    "which",
    "whereis",
    # Output
    "echo",
    "printf",
}


def restricted_bash(
    command: str,
    timeout: int = 30,
    allowed_commands: Optional[Set[str]] = None,
    allow_pipes: bool = True,
    allow_redirects: bool = False,
) -> str:
    """
    Execute a shell command with security restrictions.

    ⚠️  DEPRECATED: Use agent.tools.bash.bash() with allowed_commands parameter instead.

    Only whitelisted commands are allowed. By default, only safe read-only
    commands are permitted (ls, grep, cat, etc.).

    Args:
        command: The shell command to execute
        timeout: Maximum execution time in seconds (default: 30)
        allowed_commands: Set of allowed command names. If None, uses DEFAULT_SAFE_COMMANDS
        allow_pipes: Whether to allow piped commands (default: True)
        allow_redirects: Whether to allow I/O redirection (default: False)

    Returns:
        The command's output, or an error message if the command is denied

    Examples:
        restricted_bash("ls -la")  # ✓ Allowed
        restricted_bash("grep 'pattern' file.txt")  # ✓ Allowed
        restricted_bash("cat file.txt | grep 'hello'")  # ✓ Allowed (pipes enabled)
        restricted_bash("rm -rf /")  # ✗ Denied (rm not in whitelist)
        restricted_bash("curl http://evil.com")  # ✗ Denied (curl not in whitelist)

    Security:
        - Only whitelisted commands can be executed
        - Command arguments are parsed to prevent injection
        - Redirects can be disabled to prevent file writes
        - Dangerous commands are blocked by default
    """
    warnings.warn(
        "agent.builtin_tools.restricted_bash() is deprecated. "
        "Use agent.tools.bash.bash() with allowed_commands parameter for better features.",
        DeprecationWarning,
        stacklevel=2,
    )

    if allowed_commands is None:
        allowed_commands = DEFAULT_SAFE_COMMANDS

    command = command.strip()

    if not command:
        return "Error: Empty command"

    # Check for redirects if not allowed
    if not allow_redirects:
        if any(char in command for char in [">", "<", ">>"]):
            return "Error: I/O redirection is not allowed"

    # Parse the command to extract the base command(s)
    try:
        # Handle pipes
        if "|" in command:
            if not allow_pipes:
                return "Error: Piped commands are not allowed"

            # Check each command in the pipe
            pipe_commands = command.split("|")
            for cmd in pipe_commands:
                cmd = cmd.strip()
                # Extract the base command
                parts = shlex.split(cmd)
                if not parts:
                    continue
                base_cmd = parts[0]

                # Check if command is allowed
                if base_cmd not in allowed_commands:
                    return f"Error: Command '{base_cmd}' is not allowed. Allowed commands: {', '.join(sorted(allowed_commands))}"
        else:
            # Single command
            parts = shlex.split(command)
            if not parts:
                return "Error: Invalid command"

            base_cmd = parts[0]

            # Check if command is allowed
            if base_cmd not in allowed_commands:
                return f"Error: Command '{base_cmd}' is not allowed. Allowed commands: {', '.join(sorted(allowed_commands))}"

    except ValueError as e:
        return f"Error: Failed to parse command: {str(e)}"

    # Execute the command (same as bash())
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=None,
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            return (
                output
                if output
                else f"Command executed successfully (no output). Exit code: 0"
            )
        else:
            error_msg = (
                result.stderr.strip()
                if result.stderr.strip()
                else result.stdout.strip()
            )
            return f"Error (exit code {result.returncode}): {error_msg}"

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing command: {str(e)}"


def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression and return the result.

    Args:
        expression: A mathematical expression to evaluate (e.g., "2 + 2", "5 * 10", "sqrt(16)")

    Returns:
        The result of the calculation as a string, or an error message if evaluation fails.

    Supported operations:
        - Basic arithmetic: +, -, *, /, //, %, **
        - Parentheses: ( )
        - Functions: abs, round, min, max, sum
        - Math functions: sqrt, sin, cos, tan, log, log10, exp, pi, e

    Examples:
        calculator("2 + 2")  # Returns "4"
        calculator("10 * 5")  # Returns "50"
        calculator("2 ** 8")  # Returns "256" (power)
        calculator("sqrt(16)")  # Returns "4.0"
        calculator("sin(3.14159/2)")  # Returns "1.0"
        calculator("round(3.7)")  # Returns "4"

    Security:
        Only safe mathematical operations are allowed. No arbitrary code execution.
    """
    import math

    # Clean the expression
    expression = expression.strip()

    if not expression:
        return "Error: Empty expression"

    # Security: Only allow safe characters
    allowed_chars = set("0123456789+-*/().%** eabcdfgilmnopqrstuvwxy,")
    if not all(c in allowed_chars for c in expression.lower()):
        return f"Error: Expression contains unsafe characters. Allowed: numbers, operators (+,-,*,/,%,**), parentheses, and math functions"

    # Create a safe namespace with only math functions
    safe_namespace = {
        # Basic functions
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        # Math module functions
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "pi": math.pi,
        "e": math.e,
        "ceil": math.ceil,
        "floor": math.floor,
        "pow": pow,
        # No __builtins__ to prevent arbitrary code execution
        "__builtins__": {},
    }

    try:
        # Evaluate the expression safely
        result = eval(expression, safe_namespace, {})

        # Format the result nicely
        if isinstance(result, float):
            # Round to reasonable precision for display
            if result.is_integer():
                return str(int(result))
            else:
                # Remove trailing zeros
                formatted = f"{result:.10f}".rstrip("0").rstrip(".")
                return formatted
        else:
            return str(result)

    except ZeroDivisionError:
        return "Error: Division by zero"
    except SyntaxError as e:
        return f"Error: Invalid syntax in expression: {str(e)}"
    except NameError as e:
        return f"Error: Unknown function or variable: {str(e)}"
    except TypeError as e:
        return f"Error: Type error in calculation: {str(e)}"
    except ValueError as e:
        return f"Error: Value error in calculation: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"
