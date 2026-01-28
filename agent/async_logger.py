"""
Async-safe logger for agent framework.

Provides structured logging with:
- Console output with colors
- Per-agent log files
- Async-safe file writing
- Hierarchical agent tracking
"""

import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from enum import Enum


class LogLevel(Enum):
    """Log levels"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class AsyncLogger:
    """
    Async-safe logger with console and file output.

    Features:
    - Color-coded console output
    - Per-agent log files with timestamps
    - Async file writing (non-blocking)
    - Hierarchical indentation for subagents
    """

    # ANSI color codes
    COLORS = {
        LogLevel.DEBUG: "\033[90m",  # Gray
        LogLevel.INFO: "\033[94m",  # Blue
        LogLevel.WARNING: "\033[93m",  # Yellow
        LogLevel.ERROR: "\033[91m",  # Red
        "RESET": "\033[0m",
        "BOLD": "\033[1m",
        "TOOL": "\033[96m",  # Cyan
        "LLM": "\033[92m",  # Green
    }

    # Agent color palette (cycling through different colors)
    AGENT_COLORS = [
        "\033[95m",  # Magenta
        "\033[96m",  # Cyan
        "\033[92m",  # Green
        "\033[93m",  # Yellow
        "\033[94m",  # Blue
        "\033[91m",  # Red
        "\033[35m",  # Purple
        "\033[36m",  # Light Cyan
        "\033[32m",  # Light Green
        "\033[33m",  # Light Yellow
    ]

    def __init__(self, log_dir: str = "logs", console_output: bool = True):
        """
        Initialize async logger.

        Args:
            log_dir: Directory for log files
            console_output: Whether to print to console
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.console_output = console_output

        # Agent hierarchy tracking
        self.agent_levels: dict[str, int] = {}
        self.parent_child: dict[str, str] = {}

        # Agent color assignment
        self.agent_colors: dict[str, str] = {}
        self._color_index = 0

        # File handles (opened lazily per agent)
        self.log_files: dict[str, Path] = {}

        # Start time for elapsed time tracking
        self.start_time = time.time()

        # Queue for async file writes
        self.write_queue: asyncio.Queue = asyncio.Queue()
        self._writer_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start the async file writer"""
        if not self._running:
            self._running = True
            self._writer_task = asyncio.create_task(self._file_writer_loop())

    async def stop(self):
        """Stop the async file writer"""
        self._running = False
        if self._writer_task:
            self._writer_task.cancel()
            try:
                await self._writer_task
            except asyncio.CancelledError:
                pass

    async def _file_writer_loop(self):
        """Background task that writes logs to files"""
        while self._running:
            try:
                # Get write task from queue (with timeout)
                try:
                    agent_id, message = await asyncio.wait_for(
                        self.write_queue.get(), timeout=0.1
                    )

                    # Write to file
                    log_file = self.log_files.get(agent_id)
                    if log_file:
                        with open(log_file, "a", encoding="utf-8") as f:
                            f.write(message + "\n")
                            f.flush()

                except asyncio.TimeoutError:
                    continue

            except Exception as e:
                print(f"[AsyncLogger] Error in file writer: {e}")

    def _get_timestamp(self) -> str:
        """Get formatted timestamp"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    def _get_elapsed(self) -> str:
        """Get elapsed time since logger start"""
        elapsed = time.time() - self.start_time
        return f"{elapsed:>7.3f}s"

    def _get_indent(self, agent_id: str) -> str:
        """Get indentation for hierarchical display"""
        level = self.agent_levels.get(agent_id, 0)
        return "  " * level

    def _colorize(self, text: str, color_key: str) -> str:
        """Add color codes to text"""
        if not self.console_output:
            return text
        color = self.COLORS.get(color_key, "")
        reset = self.COLORS["RESET"]
        return f"{color}{text}{reset}"

    def register_agent(
        self, agent_id: str, agent_name: str, parent_id: Optional[str] = None
    ):
        """
        Register an agent for logging.

        Args:
            agent_id: Unique agent ID
            agent_name: Display name
            parent_id: Parent agent ID (if subagent)
        """
        # Determine hierarchy level
        if parent_id:
            parent_level = self.agent_levels.get(parent_id, 0)
            self.agent_levels[agent_id] = parent_level + 1
            self.parent_child[agent_id] = parent_id
        else:
            self.agent_levels[agent_id] = 0

        # Assign color to agent (if not already assigned)
        if agent_id not in self.agent_colors:
            self.agent_colors[agent_id] = self.AGENT_COLORS[
                self._color_index % len(self.AGENT_COLORS)
            ]
            self._color_index += 1

        # Create log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{agent_name}_{timestamp}_{agent_id[:8]}.log"
        self.log_files[agent_id] = self.log_dir / log_filename

    async def log(
        self,
        level: LogLevel,
        agent_id: str,
        message: str,
        category: Optional[str] = None,
        console_only_for_root: bool = False,
    ):
        """
        Log a message.

        Args:
            level: Log level
            agent_id: Agent that generated the log
            message: Log message
            category: Optional category (TOOL, LLM, etc.)
            console_only_for_root: If True, only print to console for root agents (level 0)
        """
        timestamp = self._get_timestamp()
        elapsed = self._get_elapsed()
        indent = self._get_indent(agent_id)

        # Format message parts
        level_str = f"[{level.value}]"
        agent_name = agent_id.split("_")[0] if "_" in agent_id else agent_id

        if category:
            category_str = f"[{category}]"
        else:
            category_str = ""

        # Determine if we should print to console
        should_print_console = self.console_output
        if console_only_for_root:
            # Only print if this is a root agent (level 0)
            agent_level = self.agent_levels.get(agent_id, 0)
            should_print_console = should_print_console and (agent_level == 0)

        # Console output (colored)
        if should_print_console:
            colored_level = self._colorize(level_str, level.value)
            # Use agent-specific color
            agent_color = self.agent_colors.get(agent_id, self.AGENT_COLORS[0])
            reset = self.COLORS["RESET"]
            colored_agent = f"{agent_color}[{agent_name}]{reset}"

            if category:
                colored_category = self._colorize(category_str, category)
                console_msg = f"{elapsed} {colored_level} {indent}{colored_agent} {colored_category} {message}"
            else:
                console_msg = (
                    f"{elapsed} {colored_level} {indent}{colored_agent} {message}"
                )

            print(console_msg)

        # File output (no colors) - ALWAYS write to file regardless of level
        if category:
            file_msg = (
                f"{timestamp} {level_str} [{agent_name}] {category_str} {message}"
            )
        else:
            file_msg = f"{timestamp} {level_str} [{agent_name}] {message}"

        # Queue for async file write
        await self.write_queue.put((agent_id, file_msg))

    async def agent_start(
        self,
        agent_id: str,
        task: str,
        system_prompt: Optional[str] = None,
        tools: Optional[list[str]] = None,
    ):
        """Log agent start with configuration details"""
        await self.log(
            LogLevel.INFO, agent_id, f"🚀 Started with task: {task}", "AGENT"
        )

        # Log system prompt (first 200 chars)
        if system_prompt:
            prompt_preview = system_prompt.replace("\n", " ")[:200]
            if len(system_prompt) > 200:
                prompt_preview += "..."
            await self.log(
                LogLevel.INFO, agent_id, f"📋 System Prompt: {prompt_preview}", "AGENT"
            )

        # Log available tools
        if tools:
            tools_str = ", ".join(tools)
            await self.log(LogLevel.INFO, agent_id, f"🔧 Tools: [{tools_str}]", "AGENT")

    async def agent_finish(self, agent_id: str, success: bool, result: str):
        """Log agent finish"""
        emoji = "✅" if success else "❌"
        await self.log(
            LogLevel.INFO, agent_id, f"{emoji} Finished: {result[:100]}", "AGENT"
        )

    async def llm_first_request(self, agent_id: str, user_message: str):
        """Log the first LLM request (task sent to LLM)"""
        await self.log(
            LogLevel.INFO, agent_id, f"📤 First LLM Request: {user_message}", "AGENT"
        )

    async def agent_suspended(self, agent_id: str, reason: str):
        """Log agent suspension"""
        await self.log(
            LogLevel.INFO,
            agent_id,
            f"⏸️  Suspended: {reason}",
            "AGENT",
            console_only_for_root=True,  # Only print for root agents
        )

    async def agent_resumed(self, agent_id: str, trigger: str):
        """Log agent resumption"""
        await self.log(
            LogLevel.INFO,
            agent_id,
            f"▶️  Resumed: {trigger}",
            "AGENT",
            console_only_for_root=True,  # Only print for root agents
        )

    async def tool_call(self, agent_id: str, tool_name: str, arguments: dict):
        """Log tool call"""
        args_str = str(arguments)[:50]
        await self.log(
            LogLevel.INFO,
            agent_id,
            f"Calling {tool_name}({args_str}...)",
            "TOOL",
            console_only_for_root=True,  # Only print for root agents
        )

    async def tool_result(
        self, agent_id: str, tool_name: str, result: str, success: bool
    ):
        """Log tool result"""
        emoji = "✓" if success else "✗"
        result_preview = result[:80].replace("\n", " ")
        await self.log(
            LogLevel.INFO if success else LogLevel.ERROR,
            agent_id,
            f"{emoji} {tool_name} → {result_preview}",
            "TOOL",
            console_only_for_root=True,  # Only print for root agents
        )

    async def llm_request(self, agent_id: str, prompt_preview: str):
        """Log LLM request"""
        preview = prompt_preview[:60].replace("\n", " ")
        await self.log(
            LogLevel.DEBUG,
            agent_id,
            f"Request: {preview}...",
            "LLM",
            console_only_for_root=True,  # Only print for root agents
        )

    async def llm_response(self, agent_id: str, response_preview: str):
        """Log LLM response"""
        preview = response_preview[:80].replace("\n", " ")
        await self.log(
            LogLevel.DEBUG,
            agent_id,
            f"Response: {preview}...",
            "LLM",
            console_only_for_root=True,  # Only print for root agents
        )

    async def subagent_launch(self, parent_id: str, child_name: str, task: str):
        """Log subagent launch"""
        task_preview = task[:50]
        await self.log(
            LogLevel.INFO,
            parent_id,
            f"🔀 Launching subagent '{child_name}' with task: {task_preview}",
            "AGENT",
        )

    async def agent_thought(self, agent_id: str, thought: str):
        """Log agent's reasoning/thought process"""
        if thought:
            # Truncate long thoughts for readability
            thought_preview = thought[:150] if len(thought) > 150 else thought
            await self.log(
                LogLevel.INFO,
                agent_id,
                f"💭 Thought: {thought_preview}",
                "AGENT",
            )

    async def agent_action(self, agent_id: str, action_type: str, details: str = ""):
        """Log agent action/decision"""
        emoji_map = {
            "tool": "🔧",
            "launch_subagents": "🚀",
            "wait_for_subagents": "⏸️",
            "finish": "✅",
        }
        emoji = emoji_map.get(action_type, "⚡")
        if details:
            await self.log(
                LogLevel.INFO,
                agent_id,
                f"{emoji} Action: {action_type} - {details}",
                "AGENT",
            )
        else:
            await self.log(
                LogLevel.INFO,
                agent_id,
                f"{emoji} Action: {action_type}",
                "AGENT",
            )

    async def error(self, agent_id: str, error_msg: str):
        """Log error"""
        await self.log(LogLevel.ERROR, agent_id, error_msg)

    async def compaction_triggered(
        self, agent_id: str, current_tokens: int, threshold_tokens: int, model: str
    ):
        """
        Log when context compaction is triggered.

        Args:
            agent_id: Agent performing compaction
            current_tokens: Current token count
            threshold_tokens: Threshold that triggered compaction
            model: Model name
        """
        percentage = (
            (current_tokens / threshold_tokens * 100) if threshold_tokens > 0 else 0
        )
        await self.log(
            LogLevel.INFO,
            agent_id,
            f"🔄 Context compaction triggered: {current_tokens:,} tokens "
            f"({percentage:.1f}% of threshold: {threshold_tokens:,}) [model: {model}]",
            "COMPACT",
        )

    async def compaction_success(
        self,
        agent_id: str,
        before_tokens: int,
        after_tokens: int,
        before_messages: int,
        after_messages: int,
    ):
        """
        Log successful compaction.

        Args:
            agent_id: Agent that performed compaction
            before_tokens: Token count before compaction
            after_tokens: Token count after compaction
            before_messages: Message count before compaction
            after_messages: Message count after compaction
        """
        tokens_saved = before_tokens - after_tokens
        messages_removed = before_messages - after_messages
        savings_pct = (tokens_saved / before_tokens * 100) if before_tokens > 0 else 0

        await self.log(
            LogLevel.INFO,
            agent_id,
            f"✅ Compaction successful: {before_tokens:,} → {after_tokens:,} tokens "
            f"(saved {tokens_saved:,} tokens, {savings_pct:.1f}%) | "
            f"{before_messages} → {after_messages} messages (removed {messages_removed})",
            "COMPACT",
        )

    async def compaction_failed(self, agent_id: str, reason: str):
        """
        Log failed compaction.

        Args:
            agent_id: Agent that attempted compaction
            reason: Reason for failure
        """
        await self.log(
            LogLevel.WARNING,
            agent_id,
            f"⚠️ Compaction failed: {reason}",
            "COMPACT",
        )

    async def compaction_skipped(self, agent_id: str, reason: str):
        """
        Log skipped compaction.

        Args:
            agent_id: Agent that skipped compaction
            reason: Reason for skipping
        """
        await self.log(
            LogLevel.DEBUG,
            agent_id,
            f"⏭️ Compaction skipped: {reason}",
            "COMPACT",
        )


# Global logger instance
_global_logger: Optional[AsyncLogger] = None


def get_logger() -> AsyncLogger:
    """Get or create global logger instance"""
    global _global_logger
    if _global_logger is None:
        _global_logger = AsyncLogger()
    return _global_logger


async def init_logger(
    log_dir: str = "logs", console_output: bool = True
) -> AsyncLogger:
    """
    Initialize and start the global logger.

    Args:
        log_dir: Directory for log files
        console_output: Whether to print to console

    Returns:
        Initialized logger instance
    """
    global _global_logger
    _global_logger = AsyncLogger(log_dir=log_dir, console_output=console_output)
    await _global_logger.start()
    return _global_logger


async def close_logger():
    """Close the global logger"""
    global _global_logger
    if _global_logger:
        await _global_logger.stop()
        _global_logger = None
