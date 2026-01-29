"""
Context for tool execution with permissions, metadata, and abort signals.

This module provides the Context class that is passed to all tools during
execution. It provides:
- Permission management
- Session metadata storage
- Abort signals for cancellation
- Message history access
- Real-time metadata streaming
"""

from typing import Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
import asyncio
from datetime import datetime
import uuid

# Import modules directly to avoid triggering agent/__init__.py
import sys
from pathlib import Path

# Add agent directory to path if not already there
agent_dir = Path(__file__).parent
if str(agent_dir.parent) not in sys.path:
    sys.path.insert(0, str(agent_dir.parent))

# Import directly using importlib to avoid __init__.py
import importlib.util


def _load_agent_module(module_name, file_name):
    """Load an agent module directly without triggering package init."""
    module_path = agent_dir / file_name
    spec = importlib.util.spec_from_file_location(f"agent.{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Load required modules
permissions_mod = _load_agent_module("permissions", "permissions.py")
truncation_mod = _load_agent_module("truncation", "truncation.py")

PermissionRequest = permissions_mod.PermissionRequest
PermissionHandler = permissions_mod.PermissionHandler
PermissionDeniedError = permissions_mod.PermissionDeniedError
AlwaysAllowHandler = permissions_mod.AlwaysAllowHandler
OutputTruncator = truncation_mod.OutputTruncator
get_default_truncator = truncation_mod.get_default_truncator


@dataclass
class Message:
    """
    Represents a message in the conversation.

    Attributes:
        role: Message role ('user', 'assistant', 'system')
        content: Message content
        timestamp: When the message was created
        metadata: Additional metadata
    """

    role: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


class Context:
    """
    Execution context provided to tools.

    This class provides tools with:
    - Permission management via the permission handler
    - Session-scoped metadata storage
    - Abort signals for cancellation
    - Access to conversation history
    - Real-time metadata streaming to UI

    Attributes:
        session_id: Unique identifier for this session
        message_id: Unique identifier for the current message
        call_id: Unique identifier for this tool call
        agent_name: Name of the agent executing tools
        messages: Full conversation history

    Examples:
        >>> # Create a context with permission handler
        >>> handler = AutoApproveHandler()
        >>> handler.add_pattern(PermissionType.READ, "*.md")
        >>>
        >>> ctx = Context(
        ...     session_id="session_123",
        ...     message_id="msg_456",
        ...     permission_handler=handler
        ... )
        >>>
        >>> # Request permission in a tool
        >>> await ctx.ask(PermissionRequest(
        ...     permission=PermissionType.READ,
        ...     patterns=["README.md"]
        ... ))  # Approved automatically
    """

    def __init__(
        self,
        session_id: str,
        message_id: str,
        permission_handler: Optional[PermissionHandler] = None,
        agent_name: str = "agent",
        messages: Optional[list[Message]] = None,
        working_directory: str = ".",
        truncator: Optional[OutputTruncator] = None,
    ):
        """
        Initialize the execution context.

        Args:
            session_id: Unique session identifier
            message_id: Unique message identifier
            permission_handler: Handler for permission requests (defaults to AlwaysAllowHandler)
            agent_name: Name of the agent
            messages: Conversation history
            working_directory: Current working directory
            truncator: Output truncator (defaults to global truncator)
        """
        self.session_id = session_id
        self.message_id = message_id
        self.call_id = str(uuid.uuid4())
        self.agent_name = agent_name
        self.working_directory = working_directory

        # Permission handling
        self._permission_handler = permission_handler or AlwaysAllowHandler()

        # Abort signal
        self._abort_event = asyncio.Event()
        self._abort_reason: Optional[str] = None

        # Messages
        self.messages = messages or []

        # Session metadata storage
        self._session_metadata: dict[str, Any] = {}

        # Metadata streaming callback
        self._metadata_callback: Optional[Callable[[dict], Awaitable[None]]] = None

        # User input handler (for question tool)
        self._user_input_handler: Optional[Callable[..., Any]] = None

        # Output truncator
        self._truncator = truncator or get_default_truncator()

    # Permission management

    async def ask(self, request: PermissionRequest) -> None:
        """
        Request permission to perform an operation.

        This method will call the permission handler and raise PermissionDeniedError
        if the request is denied.

        Args:
            request: The permission request

        Raises:
            PermissionDeniedError: If permission is denied

        Examples:
            >>> await ctx.ask(PermissionRequest(
            ...     permission=PermissionType.BASH,
            ...     patterns=["npm install"],
            ...     metadata={"cwd": "/project"}
            ... ))
        """
        approved = await self._permission_handler.request_permission(request)

        if not approved:
            raise PermissionDeniedError(request, "User denied permission")

    def set_permission_handler(self, handler: PermissionHandler) -> None:
        """
        Set the permission handler for this context.

        Args:
            handler: The permission handler to use
        """
        self._permission_handler = handler

    # Abort signal management

    def abort(self, reason: Optional[str] = None) -> None:
        """
        Signal that the current operation should be aborted.

        Args:
            reason: Optional reason for the abort
        """
        self._abort_reason = reason or "Operation aborted"
        self._abort_event.set()

    def check_abort(self) -> None:
        """
        Check if the operation has been aborted.

        Raises:
            RuntimeError: If the operation has been aborted
        """
        if self.is_aborted:
            raise RuntimeError(f"Operation aborted: {self._abort_reason}")

    @property
    def is_aborted(self) -> bool:
        """Check if the operation has been aborted."""
        return self._abort_event.is_set()

    async def wait_for_abort(self) -> None:
        """Wait until the operation is aborted."""
        await self._abort_event.wait()

    # Metadata management

    def get_session_metadata(self, key: str, default: Any = None) -> Any:
        """
        Get a value from session metadata.

        Args:
            key: The metadata key
            default: Default value if key doesn't exist

        Returns:
            The metadata value or default
        """
        return self._session_metadata.get(key, default)

    def set_session_metadata(self, key: str, value: Any) -> None:
        """
        Set a value in session metadata.

        Args:
            key: The metadata key
            value: The value to store
        """
        self._session_metadata[key] = value

    def update_session_metadata(self, **kwargs) -> None:
        """
        Update multiple metadata values at once.

        Args:
            **kwargs: Key-value pairs to update
        """
        self._session_metadata.update(kwargs)

    def get_all_metadata(self) -> dict[str, Any]:
        """
        Get all session metadata.

        Returns:
            Dictionary of all metadata
        """
        return self._session_metadata.copy()

    # Metadata streaming (for real-time UI updates)

    def set_metadata_callback(
        self, callback: Callable[[dict], Awaitable[None]]
    ) -> None:
        """
        Set a callback for streaming metadata updates to UI.

        Args:
            callback: Async function that receives metadata dict
        """
        self._metadata_callback = callback

    # User input handling

    def set_user_input_handler(self, handler: Optional[Callable[..., Any]]) -> None:
        """Set handler for user input prompts (question tool)."""
        self._user_input_handler = handler

    async def get_user_input(self, prompt: str, metadata: Optional[dict] = None) -> Any:
        """Ask user for input using the configured handler."""
        if self._user_input_handler is None:
            raise RuntimeError("No user input handler configured")

        handler = self._user_input_handler
        if metadata is not None:
            try:
                result = handler(prompt, metadata)
            except TypeError:
                result = handler(prompt)
        else:
            result = handler(prompt)
        if asyncio.iscoroutine(result):
            return await result
        return result

    async def stream_metadata(self, data: dict[str, Any]) -> None:
        """
        Stream metadata update to UI.

        This is useful for long-running operations to provide real-time
        progress updates.

        Args:
            data: Metadata to stream

        Examples:
            >>> # In a long-running tool
            >>> for i in range(100):
            ...     await asyncio.sleep(0.1)
            ...     await ctx.stream_metadata({"progress": i, "status": "processing"})
        """
        if self._metadata_callback:
            await self._metadata_callback(data)

    # Message history

    def add_message(self, role: str, content: str, **metadata) -> None:
        """
        Add a message to the conversation history.

        Args:
            role: Message role
            content: Message content
            **metadata: Additional metadata
        """
        self.messages.append(Message(role=role, content=content, metadata=metadata))

    def get_messages(
        self, role: Optional[str] = None, limit: Optional[int] = None
    ) -> list[Message]:
        """
        Get messages from conversation history.

        Args:
            role: Filter by role (optional)
            limit: Maximum number of messages to return

        Returns:
            List of messages
        """
        messages = self.messages

        if role:
            messages = [m for m in messages if m.role == role]

        if limit:
            messages = messages[-limit:]

        return messages

    # Output truncation

    def truncate_output(self, output: str, context: str = "") -> tuple[str, dict]:
        """
        Truncate output if it exceeds limits.

        Args:
            output: The output to truncate
            context: Optional context for the truncation message

        Returns:
            Tuple of (truncated_output, metadata_dict)
        """
        truncated, metadata = self._truncator.truncate(output, self.call_id, context)
        return truncated, metadata.to_dict()

    def set_truncator(self, truncator: OutputTruncator) -> None:
        """
        Set the output truncator for this context.

        Args:
            truncator: The truncator to use
        """
        self._truncator = truncator

    # Utility methods

    def to_dict(self) -> dict[str, Any]:
        """
        Convert context to dictionary format.

        Returns:
            Dictionary representation of the context
        """
        return {
            "session_id": self.session_id,
            "message_id": self.message_id,
            "call_id": self.call_id,
            "agent_name": self.agent_name,
            "working_directory": self.working_directory,
            "is_aborted": self.is_aborted,
            "abort_reason": self._abort_reason,
            "message_count": len(self.messages),
            "metadata": self._session_metadata,
        }

    def __repr__(self) -> str:
        """String representation of the context."""
        return (
            f"Context(session_id={self.session_id!r}, "
            f"message_id={self.message_id!r}, "
            f"call_id={self.call_id!r})"
        )


# Factory functions for common context configurations


def create_context(
    session_id: Optional[str] = None,
    message_id: Optional[str] = None,
    permission_handler: Optional[PermissionHandler] = None,
    **kwargs,
) -> Context:
    """
    Create a context with auto-generated IDs if not provided.

    Args:
        session_id: Session ID (auto-generated if None)
        message_id: Message ID (auto-generated if None)
        permission_handler: Permission handler (AlwaysAllowHandler if None)
        **kwargs: Additional arguments for Context

    Returns:
        A new Context instance
    """
    return Context(
        session_id=session_id or str(uuid.uuid4()),
        message_id=message_id or str(uuid.uuid4()),
        permission_handler=permission_handler,
        **kwargs,
    )


def create_interactive_context(
    working_directory: str = ".", auto_approve: bool = False, **kwargs
) -> Context:
    """
    Create a context with interactive permission handler.

    Args:
        working_directory: Current working directory
        auto_approve: If True, auto-approve all permissions
        **kwargs: Additional arguments for Context

    Returns:
        A new Context instance with InteractiveHandler
    """
    InteractiveHandler = permissions_mod.InteractiveHandler

    return create_context(
        permission_handler=InteractiveHandler(auto_approve=auto_approve),
        working_directory=working_directory,
        **kwargs,
    )


def create_auto_approve_context(
    patterns: Optional[dict[str, list[str]]] = None, **kwargs
) -> Context:
    """
    Create a context with auto-approve patterns.

    Args:
        patterns: Dict mapping permission types to allowed patterns
        **kwargs: Additional arguments for Context

    Returns:
        A new Context instance with AutoApproveHandler

    Examples:
        >>> ctx = create_auto_approve_context(
        ...     patterns={
        ...         "read": ["*.md", "*.txt"],
        ...         "bash": ["git status", "npm test"]
        ...     }
        ... )
    """
    AutoApproveHandler = permissions_mod.AutoApproveHandler

    handler = AutoApproveHandler()

    if patterns:
        for perm_type, pattern_list in patterns.items():
            handler.add_patterns(perm_type, pattern_list)

    return create_context(permission_handler=handler, **kwargs)
