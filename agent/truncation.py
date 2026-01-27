"""
Automatic output truncation to prevent context window bloat.

This module provides the OutputTruncator class that automatically truncates
large tool outputs and writes the full content to a temporary file. This
ensures that tools can produce large outputs without overwhelming the LLM's
context window.
"""

from pathlib import Path
import tempfile
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class TruncationMetadata:
    """
    Metadata about output truncation.

    Attributes:
        total_lines: Total number of lines in the output
        total_bytes: Total size in bytes
        is_truncated: Whether the output was truncated
        truncated_at_line: Line number where truncation occurred (if truncated)
        full_output_file: Path to file containing full output (if truncated)
    """

    total_lines: int
    total_bytes: int
    is_truncated: bool
    truncated_at_line: Optional[int] = None
    full_output_file: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "total_lines": self.total_lines,
            "total_bytes": self.total_bytes,
            "is_truncated": self.is_truncated,
            "truncated_at_line": self.truncated_at_line,
            "full_output_file": self.full_output_file,
        }


class OutputTruncator:
    """
    Automatically truncates large outputs and provides spillover to files.

    When tool output exceeds the configured limits (lines or bytes), this class:
    1. Writes the full output to a temporary file
    2. Returns a truncated version with instructions
    3. Provides metadata about the truncation

    This prevents context window bloat while preserving all data for later access.

    Attributes:
        max_lines: Maximum number of lines before truncation (default: 2000)
        max_bytes: Maximum size in bytes before truncation (default: 51200 = 50KB)
        temp_dir: Directory for storing full outputs (default: system temp)

    Examples:
        >>> truncator = OutputTruncator(max_lines=100, max_bytes=10000)
        >>> output = "line\\n" * 200  # 200 lines
        >>> truncated, metadata = truncator.truncate(output, "call_123")
        >>> print(metadata.is_truncated)
        True
        >>> print(metadata.truncated_at_line)
        100
    """

    def __init__(
        self,
        max_lines: int = 2000,
        max_bytes: int = 51200,  # 50KB
        temp_dir: Optional[str] = None,
    ):
        """
        Initialize the output truncator.

        Args:
            max_lines: Maximum number of lines before truncation
            max_bytes: Maximum size in bytes before truncation
            temp_dir: Directory for storing full outputs (uses system temp if None)
        """
        self.max_lines = max_lines
        self.max_bytes = max_bytes
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir())
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def truncate(
        self, output: str, call_id: str, context: str = ""
    ) -> Tuple[str, TruncationMetadata]:
        """
        Truncate output if it exceeds limits.

        Args:
            output: The output string to potentially truncate
            call_id: Unique identifier for this tool call (used in filename)
            context: Optional context string to add to truncation message

        Returns:
            Tuple of (truncated_output, metadata)
            If no truncation needed, returns (output, metadata) with is_truncated=False

        Examples:
            >>> truncator = OutputTruncator(max_lines=5)
            >>> output = "\\n".join([f"line {i}" for i in range(10)])
            >>> truncated, meta = truncator.truncate(output, "test_call")
            >>> print(meta.is_truncated)
            True
            >>> print(meta.total_lines)
            10
        """
        lines = output.split("\n")
        byte_size = len(output.encode("utf-8"))

        # Create metadata
        metadata = TruncationMetadata(
            total_lines=len(lines), total_bytes=byte_size, is_truncated=False
        )

        # Check if truncation is needed
        needs_truncation = len(lines) > self.max_lines or byte_size > self.max_bytes

        if not needs_truncation:
            return output, metadata

        # Write full output to file
        temp_file = self.temp_dir / f"output_{call_id}.txt"
        try:
            temp_file.write_text(output, encoding="utf-8")
        except Exception as e:
            # If file writing fails, just return truncated output without file
            print(f"Warning: Failed to write full output to file: {e}")
            temp_file = None

        # Truncate to max_lines
        truncated_lines = lines[: self.max_lines]
        truncated_output = "\n".join(truncated_lines)

        # Add truncation notice
        context_str = f" ({context})" if context else ""
        footer_lines = [
            "",
            "=" * 70,
            f"⚠️  OUTPUT TRUNCATED{context_str}",
            "=" * 70,
            f"Total lines: {len(lines)} (showing first {self.max_lines})",
            f"Total size: {byte_size:,} bytes (limit: {self.max_bytes:,} bytes)",
        ]

        if temp_file and temp_file.exists():
            footer_lines.extend(
                [
                    f"",
                    f"Full output saved to: {temp_file}",
                    f"",
                    f"To read more:",
                    f"  - Use 'read' tool with offset={self.max_lines} to continue",
                    f"  - Use 'grep' tool to search the full output file",
                ]
            )

        footer_lines.append("=" * 70)
        footer = "\n".join(footer_lines)

        # Update metadata
        metadata.is_truncated = True
        metadata.truncated_at_line = self.max_lines
        metadata.full_output_file = str(temp_file) if temp_file else None

        return truncated_output + "\n" + footer, metadata

    def truncate_by_bytes(
        self, output: str, call_id: str, max_bytes: Optional[int] = None
    ) -> Tuple[str, TruncationMetadata]:
        """
        Truncate output by byte size only (ignore line count).

        Args:
            output: The output string to truncate
            call_id: Unique identifier for this tool call
            max_bytes: Override default max_bytes limit

        Returns:
            Tuple of (truncated_output, metadata)
        """
        limit = max_bytes or self.max_bytes
        byte_size = len(output.encode("utf-8"))

        lines = output.split("\n")
        metadata = TruncationMetadata(
            total_lines=len(lines), total_bytes=byte_size, is_truncated=False
        )

        if byte_size <= limit:
            return output, metadata

        # Write full output to file
        temp_file = self.temp_dir / f"output_{call_id}.txt"
        try:
            temp_file.write_text(output, encoding="utf-8")
        except Exception as e:
            print(f"Warning: Failed to write full output to file: {e}")
            temp_file = None

        # Truncate to byte limit (careful with UTF-8)
        truncated_output = output.encode("utf-8")[:limit].decode(
            "utf-8", errors="ignore"
        )
        truncated_lines = truncated_output.count("\n") + 1

        # Add footer
        footer = (
            f"\n\n{'=' * 70}\n"
            f"⚠️  OUTPUT TRUNCATED (by size)\n"
            f"{'=' * 70}\n"
            f"Total size: {byte_size:,} bytes (limit: {limit:,} bytes)\n"
        )

        if temp_file and temp_file.exists():
            footer += f"\nFull output saved to: {temp_file}\n"

        footer += "=" * 70

        # Update metadata
        metadata.is_truncated = True
        metadata.truncated_at_line = truncated_lines
        metadata.full_output_file = str(temp_file) if temp_file else None

        return truncated_output + footer, metadata

    def clean_old_files(self, max_age_hours: int = 24) -> int:
        """
        Clean up old truncated output files.

        Args:
            max_age_hours: Remove files older than this many hours

        Returns:
            Number of files deleted
        """
        import time

        cutoff_time = time.time() - (max_age_hours * 3600)
        deleted_count = 0

        for file_path in self.temp_dir.glob("output_*.txt"):
            try:
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
            except Exception as e:
                print(f"Warning: Failed to delete {file_path}: {e}")

        return deleted_count


# Global default truncator instance
_default_truncator = None


def get_default_truncator() -> OutputTruncator:
    """
    Get the global default truncator instance.

    Returns:
        The default OutputTruncator instance
    """
    global _default_truncator
    if _default_truncator is None:
        _default_truncator = OutputTruncator()
    return _default_truncator


def set_default_truncator(truncator: OutputTruncator) -> None:
    """
    Set the global default truncator instance.

    Args:
        truncator: The OutputTruncator instance to use as default
    """
    global _default_truncator
    _default_truncator = truncator
