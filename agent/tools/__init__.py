"""
Tools package for HIC agent framework.

This package contains various tools that agents can use:
- bash: Execute shell commands with safety checks
- (more tools to be added)
"""

from .bash import bash, restricted_bash, DEFAULT_SAFE_COMMANDS

__all__ = [
    "bash",
    "restricted_bash",
    "DEFAULT_SAFE_COMMANDS",
]
