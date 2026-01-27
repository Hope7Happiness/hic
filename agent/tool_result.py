"""
Structured tool result format for consistent tool returns.

This module provides the ToolResult and Attachment classes that all tools
should use to return results. This ensures consistency and enables better
UI integration, metadata tracking, and LLM consumption.
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Optional
from datetime import datetime
import base64


@dataclass
class Attachment:
    """
    Represents an attachment (image, file, or raw data) returned by a tool.

    Attributes:
        type: Type of attachment ('image', 'file', 'data')
        content: The actual content (bytes or string)
        filename: Optional filename for the attachment
        mime_type: Optional MIME type (e.g., 'image/png', 'text/plain')
        description: Optional human-readable description
    """

    type: Literal["image", "file", "data"]
    content: bytes | str
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert attachment to dictionary format."""
        result = {
            "type": self.type,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "description": self.description,
        }

        # Encode bytes content as base64 for JSON serialization
        if isinstance(self.content, bytes):
            result["content"] = base64.b64encode(self.content).decode("utf-8")
            result["content_encoding"] = "base64"
        else:
            result["content"] = self.content
            result["content_encoding"] = "utf-8"

        return result

    @classmethod
    def from_file(
        cls, file_path: str, description: Optional[str] = None
    ) -> "Attachment":
        """Create an attachment from a file path."""
        from pathlib import Path
        import mimetypes

        path = Path(file_path)
        content = path.read_bytes()
        mime_type = mimetypes.guess_type(file_path)[0]

        return cls(
            type="file",
            content=content,
            filename=path.name,
            mime_type=mime_type,
            description=description,
        )

    @classmethod
    def from_image(
        cls, image_path: str, description: Optional[str] = None
    ) -> "Attachment":
        """Create an image attachment from a file path."""
        attachment = cls.from_file(image_path, description)
        attachment.type = "image"
        return attachment


@dataclass
class ToolResult:
    """
    Structured result returned by all tools.

    This class provides a consistent interface for tool returns, optimized
    for both UI display and LLM consumption.

    Attributes:
        title: Short, human-readable summary for UI display (e.g., "Executed: npm install")
        output: Detailed text output for LLM consumption
        metadata: Structured data for UI, tracking, and filtering
        attachments: Optional list of files, images, or data attachments
        error: Optional error message if the tool failed
        timestamp: When the result was created

    Examples:
        >>> # Simple success result
        >>> result = ToolResult(
        ...     title="Read config.json",
        ...     output="{\n  \"version\": \"1.0.0\"\n}",
        ...     metadata={"file_path": "config.json", "lines": 3}
        ... )

        >>> # Result with error
        >>> result = ToolResult(
        ...     title="Failed to read file",
        ...     output="",
        ...     error="File not found: missing.txt"
        ... )

        >>> # Result with attachment
        >>> result = ToolResult(
        ...     title="Generated plot",
        ...     output="Created visualization of data trends",
        ...     attachments=[Attachment.from_image("plot.png")]
        ... )
    """

    title: str
    output: str
    metadata: dict[str, Any] = field(default_factory=dict)
    attachments: list[Attachment] = field(default_factory=list)
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def is_success(self) -> bool:
        """Check if the tool execution was successful."""
        return self.error_message is None

    @property
    def is_error(self) -> bool:
        """Check if the tool execution failed."""
        return self.error_message is not None

    # Backward compatibility property
    @property
    def error(self) -> Optional[str]:
        """Alias for error_message for backward compatibility."""
        return self.error_message

    def to_dict(self) -> dict[str, Any]:
        """
        Convert result to dictionary format for serialization.

        Returns:
            Dictionary containing all result data
        """
        return {
            "title": self.title,
            "output": self.output,
            "metadata": self.metadata,
            "attachments": [att.to_dict() for att in self.attachments],
            "error": self.error_message,
            "timestamp": self.timestamp,
            "is_success": self.is_success,
        }

    def to_llm_string(self) -> str:
        """
        Format result as a string for LLM consumption.

        This includes the title and output, with error information if present.
        Attachments are described but content is not included.

        Returns:
            Formatted string suitable for LLM context
        """
        lines = [self.title]

        if self.error_message:
            lines.append(f"\nERROR: {self.error_message}")

        if self.output:
            lines.append(f"\n{self.output}")

        if self.attachments:
            lines.append("\nAttachments:")
            for att in self.attachments:
                desc = att.description or att.filename or f"Unnamed {att.type}"
                lines.append(f"  - {desc} ({att.type})")

        return "\n".join(lines)

    def __str__(self) -> str:
        """
        String representation for display and LLM consumption.

        This method is called when the agent converts the result to string.
        Returns the same format as to_llm_string() for consistency.
        """
        return self.to_llm_string()

    def add_attachment(self, attachment: Attachment) -> "ToolResult":
        """
        Add an attachment to the result.

        Args:
            attachment: The attachment to add

        Returns:
            Self for method chaining
        """
        self.attachments.append(attachment)
        return self

    def add_metadata(self, **kwargs) -> "ToolResult":
        """
        Add metadata fields to the result.

        Args:
            **kwargs: Key-value pairs to add to metadata

        Returns:
            Self for method chaining
        """
        self.metadata.update(kwargs)
        return self

    @classmethod
    def success(cls, title: str, output: str, **metadata) -> "ToolResult":
        """
        Create a successful result.

        Args:
            title: Short summary
            output: Detailed output
            **metadata: Additional metadata fields

        Returns:
            ToolResult instance
        """
        return cls(title=title, output=output, metadata=metadata)

    @classmethod
    def from_error(cls, title: str, error_msg: str, **metadata) -> "ToolResult":
        """
        Create an error result.

        Args:
            title: Short summary
            error_msg: Error message
            **metadata: Additional metadata fields

        Returns:
            ToolResult instance with error set
        """
        return cls(title=title, output="", error_message=error_msg, metadata=metadata)


# Type alias for tool functions
from typing import Callable, Awaitable

ToolFunction = Callable[..., Awaitable[ToolResult]]
