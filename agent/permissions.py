"""
Permission system for safe tool execution.

This module provides a comprehensive permission system that requires explicit
user approval for all potentially dangerous operations. It supports:
- Different permission types (bash, read, write, etc.)
- Pattern matching for auto-approval
- Permission requests with detailed metadata
- Configurable permission handlers
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Callable, Awaitable, Protocol
from enum import Enum
import fnmatch
from pathlib import Path


class PermissionType(str, Enum):
    """Types of permissions that can be requested."""

    BASH = "bash"  # Execute shell commands
    READ = "read"  # Read files
    WRITE = "write"  # Write/create files
    DELETE = "delete"  # Delete files
    NETWORK = "network"  # Network operations
    WEBFETCH = "webfetch"  # Fetch web content
    QUESTION = "question"  # Ask user questions
    EXECUTE = "execute"  # Execute code/scripts


@dataclass
class PermissionRequest:
    """
    A request for permission to perform an operation.

    Attributes:
        permission: Type of permission being requested
        patterns: List of patterns (file paths, commands, URLs) being accessed
        always: List of patterns that should be auto-approved (from user config)
        metadata: Additional context about the operation
        description: Human-readable description of what will be done

    Examples:
        >>> # Request permission to execute a command
        >>> request = PermissionRequest(
        ...     permission=PermissionType.BASH,
        ...     patterns=["npm install"],
        ...     metadata={"cwd": "/project", "timeout": 120}
        ... )

        >>> # Request permission to write a file
        >>> request = PermissionRequest(
        ...     permission=PermissionType.WRITE,
        ...     patterns=["config.json"],
        ...     metadata={"exists": False, "size_bytes": 1024}
        ... )
    """

    permission: PermissionType | str
    patterns: list[str] = field(default_factory=list)
    always: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "permission": str(self.permission),
            "patterns": self.patterns,
            "always": self.always,
            "metadata": self.metadata,
            "description": self.description,
        }

    def matches_always_patterns(self, pattern: str) -> bool:
        """
        Check if a pattern matches any of the always-allow patterns.

        Args:
            pattern: The pattern to check

        Returns:
            True if the pattern matches any always-allow pattern
        """
        for always_pattern in self.always:
            if fnmatch.fnmatch(pattern, always_pattern):
                return True
        return False

    def should_auto_approve(self) -> bool:
        """
        Check if this request should be auto-approved based on always patterns.

        Returns:
            True if all patterns match always-allow patterns
        """
        if not self.patterns:
            return False

        return all(self.matches_always_patterns(pattern) for pattern in self.patterns)


class PermissionDeniedError(Exception):
    """Raised when a permission request is denied."""

    def __init__(self, request: PermissionRequest, reason: str = None):
        self.request = request
        self.reason = reason or "Permission denied"
        super().__init__(f"{self.reason}: {request.permission} for {request.patterns}")


class PermissionHandler(Protocol):
    """
    Protocol for handling permission requests.

    Implementations should provide an async method that takes a PermissionRequest
    and returns True (approved) or False (denied).
    """

    async def request_permission(self, request: PermissionRequest) -> bool:
        """
        Request permission from the user or system.

        Args:
            request: The permission request

        Returns:
            True if approved, False if denied
        """
        ...


class AutoApproveHandler:
    """
    Permission handler that auto-approves based on patterns.

    This handler automatically approves requests that match configured patterns
    and denies everything else (or asks a fallback handler).

    Examples:
        >>> handler = AutoApproveHandler()
        >>> handler.add_pattern(PermissionType.READ, "*.md")
        >>> handler.add_pattern(PermissionType.BASH, "git status")
        >>>
        >>> request = PermissionRequest(
        ...     permission=PermissionType.READ,
        ...     patterns=["README.md"]
        ... )
        >>> await handler.request_permission(request)  # Returns True
    """

    def __init__(self, fallback_handler: Optional[PermissionHandler] = None):
        """
        Initialize the auto-approve handler.

        Args:
            fallback_handler: Handler to use if no auto-approve pattern matches
        """
        self._patterns: dict[PermissionType, list[str]] = {}
        self._fallback_handler = fallback_handler

    def add_pattern(self, permission_type: PermissionType | str, pattern: str):
        """
        Add a pattern that should be auto-approved.

        Args:
            permission_type: Type of permission
            pattern: Pattern to match (supports glob wildcards)
        """
        perm = (
            PermissionType(permission_type)
            if isinstance(permission_type, str)
            else permission_type
        )
        if perm not in self._patterns:
            self._patterns[perm] = []
        self._patterns[perm].append(pattern)

    def add_patterns(self, permission_type: PermissionType | str, patterns: list[str]):
        """
        Add multiple patterns for a permission type.

        Args:
            permission_type: Type of permission
            patterns: List of patterns to match
        """
        for pattern in patterns:
            self.add_pattern(permission_type, pattern)

    def matches(self, request: PermissionRequest) -> bool:
        """
        Check if a request matches any auto-approve patterns.

        Args:
            request: The permission request

        Returns:
            True if all patterns in the request match auto-approve patterns
        """
        perm = (
            PermissionType(request.permission)
            if isinstance(request.permission, str)
            else request.permission
        )

        if perm not in self._patterns:
            return False

        allowed_patterns = self._patterns[perm]

        if not request.patterns:
            return False

        # All request patterns must match at least one allowed pattern
        for req_pattern in request.patterns:
            matched = any(
                fnmatch.fnmatch(req_pattern, allowed_pattern)
                for allowed_pattern in allowed_patterns
            )
            if not matched:
                return False

        return True

    async def request_permission(self, request: PermissionRequest) -> bool:
        """
        Request permission, auto-approving if patterns match.

        Args:
            request: The permission request

        Returns:
            True if approved (either auto or via fallback)
        """
        # Check if request should be auto-approved
        if self.matches(request):
            return True

        # Use fallback handler if available
        if self._fallback_handler:
            return await self._fallback_handler.request_permission(request)

        # Deny by default
        return False


class InteractiveHandler:
    """
    Permission handler that asks the user interactively (for CLI usage).

    This handler prints the permission request and asks the user to approve
    or deny it via stdin input.
    """

    def __init__(self, auto_approve: bool = False):
        """
        Initialize the interactive handler.

        Args:
            auto_approve: If True, automatically approve all requests
        """
        self._auto_approve = auto_approve

    async def request_permission(self, request: PermissionRequest) -> bool:
        """
        Request permission interactively.

        Args:
            request: The permission request

        Returns:
            True if approved, False if denied
        """
        if self._auto_approve:
            return True

        # Print request details
        print("\n" + "=" * 70)
        print(f"🔐 PERMISSION REQUEST: {request.permission.upper()}")
        print("=" * 70)

        if request.description:
            print(f"\nDescription: {request.description}")

        if request.patterns:
            print(f"\nPatterns:")
            for pattern in request.patterns:
                print(f"  - {pattern}")

        if request.metadata:
            print(f"\nDetails:")
            for key, value in request.metadata.items():
                print(f"  {key}: {value}")

        print("\n" + "-" * 70)

        # Ask for approval
        while True:
            response = (
                input("Approve? [y/n/a] (y=yes, n=no, a=always): ").lower().strip()
            )

            if response in ["y", "yes"]:
                return True
            elif response in ["n", "no"]:
                return False
            elif response in ["a", "always"]:
                # TODO: Could save this to config for future auto-approval
                return True
            else:
                print("Invalid response. Please enter 'y', 'n', or 'a'.")


class AlwaysAllowHandler:
    """
    Permission handler that always approves everything.

    WARNING: This is unsafe and should only be used for testing or in
    completely trusted environments.
    """

    async def request_permission(self, request: PermissionRequest) -> bool:
        """Always approve."""
        return True


class AlwaysDenyHandler:
    """
    Permission handler that always denies everything.

    Useful for testing or read-only modes.
    """

    async def request_permission(self, request: PermissionRequest) -> bool:
        """Always deny."""
        return False


# Helper functions for common permission checks


def is_path_safe(file_path: str | Path, cwd: str | Path) -> bool:
    """
    Check if a file path is safe (doesn't escape the project directory).

    Args:
        file_path: The file path to check
        cwd: The current working directory (project root)

    Returns:
        True if the path is safe, False if it escapes the project

    Examples:
        >>> is_path_safe("config.json", "/project")
        True
        >>> is_path_safe("../../../etc/passwd", "/project")
        False
        >>> is_path_safe("/etc/passwd", "/project")
        False
    """
    cwd = Path(cwd).resolve()

    # Handle absolute paths
    if Path(file_path).is_absolute():
        resolved = Path(file_path).resolve()
    else:
        resolved = (cwd / file_path).resolve()

    # Check if resolved path is within cwd
    try:
        resolved.relative_to(cwd)
        return True
    except ValueError:
        return False


def get_dangerous_commands() -> list[str]:
    """
    Get a list of potentially dangerous shell command patterns.

    Returns:
        List of dangerous command patterns
    """
    return [
        "rm -rf *",
        "rm -rf /",
        "rm -r *",
        "> /dev/sda",
        "mkfs",
        "dd if=",
        "chmod -R 777",
        "chmod 777",
        "curl *| bash",
        "wget *| sh",
        "curl *| sh",
        ":(){ :|:& };:",  # Fork bomb
        "mv /* /dev/null",
        "shred",
    ]


def is_command_dangerous(command: str) -> tuple[bool, Optional[str]]:
    """
    Check if a shell command is potentially dangerous.

    Args:
        command: The shell command to check

    Returns:
        Tuple of (is_dangerous, reason)

    Examples:
        >>> is_command_dangerous("ls -la")
        (False, None)
        >>> is_command_dangerous("rm -rf /")
        (True, "Command matches dangerous pattern: rm -rf /")
    """
    dangerous = get_dangerous_commands()

    for pattern in dangerous:
        # Simple substring match (could be enhanced with regex)
        if pattern.replace("*", "") in command:
            return True, f"Command matches dangerous pattern: {pattern}"

    return False, None
