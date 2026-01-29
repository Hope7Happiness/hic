"""
Tools package for HIC agent framework.

This package contains various tools that agents can use:
- bash: Execute shell commands with safety checks
- read: Read files with pagination and numbering
- write: Create or overwrite files with diff
- edit: Tolerant text replacement with multi-strategy matching
"""

from .bash import bash, restricted_bash, DEFAULT_SAFE_COMMANDS
from .read import read
from .write import write
from .edit import edit
from .grep import grep
from .glob import glob
from .todo import todowrite, todoread
from .question import question
from .webfetch import webfetch

__all__ = [
    "bash",
    "restricted_bash",
    "DEFAULT_SAFE_COMMANDS",
    "read",
    "write",
    "edit",
    "grep",
    "glob",
    "todowrite",
    "todoread",
    "question",
    "webfetch",
]
