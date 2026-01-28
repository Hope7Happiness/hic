"""
Context compaction for managing conversation history.

This module provides:
1. CompactionDetector - Detects when compaction is needed
2. CompactionAgent - Executes compaction by summarizing history
3. Integration utilities for Agent class

Design principles:
- Non-invasive: Failures don't crash the main agent
- Async-friendly: All operations are async
- Configurable: Uses CompactionConfig for settings
- Observable: Logs all compaction actions
"""

import copy
from typing import List, Dict, Optional, Tuple
from agent.llm import LLM
from agent.config import get_compaction_config
from agent.token_counter import create_counter


class CompactionDetector:
    """
    Detects when conversation history needs compaction.

    The detector checks token counts against configured thresholds
    and decides whether compaction should be triggered.
    """

    def __init__(self, llm: LLM, config=None):
        """
        Initialize the detector.

        Args:
            llm: LLM instance (used to get model name and count tokens)
            config: CompactionConfig (defaults to global config)
        """
        self.llm = llm
        self.config = config or get_compaction_config()
        self.counter = create_counter(self.config.counter_strategy)

    def should_compact(
        self, history: Optional[List[Dict[str, str]]] = None
    ) -> Tuple[bool, int, int]:
        """
        Check if compaction should be triggered.

        Args:
            history: Conversation history (defaults to LLM's current history)

        Returns:
            Tuple of (should_compact, current_tokens, threshold_tokens)
        """
        # Use LLM's history if not provided
        if history is None:
            history = self.llm.get_history()

        # Get model name
        model = getattr(self.llm, "model", "gpt-4")

        # Count tokens
        current_tokens = self.counter.count_messages(history, model)

        # Check threshold
        context_limit = self.config.get_context_limit(model)
        threshold_tokens = int(context_limit * self.config.threshold)

        # Check if we have enough messages to make compaction worthwhile
        # Calculate how many old messages we'd have after splitting
        protected_count = self.config.protect_recent_messages
        start_idx = 1 if (history and history[0].get("role") == "system") else 0
        split_point = len(history) - protected_count
        num_old_messages = max(0, split_point - start_idx)

        MIN_OLD_MESSAGES = 3  # Need at least 3 old messages for meaningful compaction
        has_enough_messages = num_old_messages >= MIN_OLD_MESSAGES

        should_compact = (
            self.config.enabled
            and current_tokens >= threshold_tokens
            and has_enough_messages
        )

        # Debug logging
        if self.config.debug_log:
            try:
                from agent.async_logger import get_logger, LogLevel
                import asyncio

                logger = get_logger()
                asyncio.create_task(
                    logger.log(
                        LogLevel.DEBUG,
                        "compaction",
                        f"should_compact check: enabled={self.config.enabled}, tokens={current_tokens}>={threshold_tokens}? {current_tokens >= threshold_tokens}, old_msgs={num_old_messages}>=3? {has_enough_messages} → {should_compact}",
                        "COMPACT",
                    )
                )
            except Exception:
                pass

        return should_compact, current_tokens, threshold_tokens

    def get_compaction_info(
        self, history: Optional[List[Dict[str, str]]] = None
    ) -> Dict:
        """
        Get detailed compaction information for logging/debugging.

        Args:
            history: Conversation history (defaults to LLM's current history)

        Returns:
            Dictionary with compaction info
        """
        if history is None:
            history = self.llm.get_history()

        model = getattr(self.llm, "model", "gpt-4")
        current_tokens = self.counter.count_messages(history, model)
        context_limit = self.config.get_context_limit(model)
        threshold_tokens = int(context_limit * self.config.threshold)
        should_compact = self.config.enabled and current_tokens >= threshold_tokens

        return {
            "enabled": self.config.enabled,
            "model": model,
            "current_tokens": current_tokens,
            "context_limit": context_limit,
            "threshold_tokens": threshold_tokens,
            "threshold_ratio": self.config.threshold,
            "should_compact": should_compact,
            "history_length": len(history),
            "protect_recent": self.config.protect_recent_messages,
        }


class CompactionAgent:
    """
    Executes context compaction by summarizing conversation history.

    The compaction agent:
    1. Splits history into recent (protected) and old (to compact) parts
    2. Calls LLM to generate a summary of old messages
    3. Replaces old messages with summary message
    4. Returns compacted history
    """

    # System prompt for compaction LLM
    COMPACTION_SYSTEM_PROMPT = """You are a context compression assistant. Your job is to create BRIEF summaries of conversation history.
    
!!! CRITICAL INSTRUCTIONS !!!:
Focus on information that would be helpful for continuing the conversation, including what we did, what we're doing, which files we're working on, and what we're going to do next considering new session will not have access to our conversation.

IMPORTANT: Your summary MUST be significantly shorter than the original text.

Instructions:
1. Create a very short summary (aim for 20-30% of original length)
2. Focus ONLY on essential facts, decisions, and outcomes
3. Omit details, examples, and explanations unless critical
4. Use bullet points or very short sentences
5. If the content is very long, use high-level overview instead of details
6. Prioritize: key decisions > outcomes > context > details

Output: A brief summary that captures only the most essential information, what was done, what needs to be done, and what needs to be remembered for future context."""

    def __init__(self, llm: LLM, config=None):
        """
        Initialize the compaction agent.

        Args:
            llm: LLM instance to use for generating summaries
            config: CompactionConfig (defaults to global config)
        """
        self.llm = llm
        self.config = config or get_compaction_config()
        self.counter = create_counter(self.config.counter_strategy)

    async def compact_history(
        self, history: List[Dict[str, str]]
    ) -> Optional[List[Dict[str, str]]]:
        """
        Compact conversation history by summarizing older messages.

        Args:
            history: Full conversation history

        Returns:
            Compacted history, or None if compaction failed

        Process:
            1. Split history into [old_messages] + [recent_messages]
            2. Generate summary of old_messages
            3. Return [system, summary] + recent_messages
        """
        # Check if compaction is needed
        if not self.config.enabled:
            return history

        # Split history
        protected_count = self.config.protect_recent_messages

        if len(history) <= protected_count:
            # History too short to compact
            return history

        # Find system message (if exists)
        system_message = None
        start_idx = 0
        if history and history[0].get("role") == "system":
            system_message = history[0]
            start_idx = 1

        # Split into old and recent
        split_point = len(history) - protected_count
        if split_point <= start_idx:
            # Not enough messages to compact
            return history

        old_messages = history[start_idx:split_point]
        recent_messages = history[split_point:]

        # Require minimum old messages for meaningful compaction
        # Compressing 1-2 messages doesn't reduce tokens significantly
        MIN_OLD_MESSAGES = 3
        if len(old_messages) < MIN_OLD_MESSAGES:
            # Not enough old messages to make compaction worthwhile
            return history

        # Generate summary of old messages
        summary = await self._generate_summary(old_messages)

        if summary is None:
            # Compaction failed - return original history
            return None

        # Build compacted history
        compacted = []

        # Add system message if it existed
        if system_message:
            compacted.append(system_message)

        # Add summary message
        compacted.append(
            {
                "role": "system",
                "content": f"[Previous conversation summary]\n\n{summary}",
            }
        )

        # Add recent messages
        compacted.extend(recent_messages)

        return compacted

    async def _generate_summary(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """
        Generate a summary of messages using the LLM.

        Args:
            messages: Messages to summarize

        Returns:
            Summary text, or None if generation failed
        """
        try:
            # Create a temporary LLM instance for compaction
            # (to avoid polluting the main LLM's history)
            compaction_llm = copy.deepcopy(self.llm)
            compaction_llm.reset_history()

            # Format messages for summarization
            messages_text = self._format_messages_for_summary(messages)

            # Calculate target summary length (aim for 25% of original)
            original_token_count = self.counter.count_messages(
                messages, getattr(self.llm, "model", "gpt-4")
            )
            target_words = max(
                50, int(original_token_count * 0.3)
            )  # At least 50 words, max 30% of original tokens

            # Generate summary with explicit length constraint
            prompt = f"""Summarize the following conversation in AT MOST {target_words} words:

{messages_text}

IMPORTANT: Your summary must be MUCH shorter than the original. Focus only on the most critical information.
Target length: {target_words} words maximum."""

            summary = compaction_llm.chat(
                prompt=prompt, system_prompt=self.COMPACTION_SYSTEM_PROMPT
            )

            return summary

        except Exception:
            # Silently fail - don't break main agent execution
            return None

    def _format_messages_for_summary(self, messages: List[Dict[str, str]]) -> str:
        """
        Format messages as text for summarization.

        Args:
            messages: Messages to format

        Returns:
            Formatted text
        """
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"{role.upper()}: {content}")

        return "\n\n".join(lines)

    def validate_compacted_history(
        self, original: List[Dict[str, str]], compacted: List[Dict[str, str]]
    ) -> bool:
        """
        Validate that compacted history is smaller than original.

        Args:
            original: Original history
            compacted: Compacted history

        Returns:
            True if compaction was successful (reduced token count)
        """
        model = getattr(self.llm, "model", "gpt-4")

        original_tokens = self.counter.count_messages(original, model)
        compacted_tokens = self.counter.count_messages(compacted, model)

        # Compaction should reduce token count
        return compacted_tokens < original_tokens


# ============================================================================
# Integration utilities for Agent class
# ============================================================================


async def check_and_compact(
    llm: LLM, agent_id: str = "unknown", config=None
) -> Optional[List[Dict[str, str]]]:
    """
    Check if compaction is needed and execute it if necessary.

    This is a high-level utility function for easy integration.

    Args:
        llm: LLM instance
        agent_id: Agent ID for logging
        config: CompactionConfig (defaults to global config)

    Returns:
        Compacted history if compaction was performed, None otherwise
    """
    config = config or get_compaction_config()

    if not config.enabled:
        return None

    # Detect if compaction is needed
    detector = CompactionDetector(llm, config)
    should_compact, current_tokens, threshold_tokens = detector.should_compact()

    # Debug logging for why compaction didn't trigger
    if config.debug_log:
        try:
            from agent.async_logger import get_logger, LogLevel

            logger = get_logger()
            if not should_compact:
                history = llm.get_history()
                protected_count = config.protect_recent_messages
                start_idx = 1 if (history and history[0].get("role") == "system") else 0
                split_point = len(history) - protected_count
                num_old_messages = max(0, split_point - start_idx)
                await logger.log(
                    LogLevel.DEBUG,
                    agent_id,
                    f"Compaction NOT triggered: tokens={current_tokens}/{threshold_tokens}, old_msgs={num_old_messages}, enabled={config.enabled}",
                    "COMPACT",
                )
        except Exception:
            pass

    if not should_compact:
        return None

    # Log compaction start
    try:
        from agent.async_logger import get_logger

        logger = get_logger()
        model = getattr(llm, "model", "gpt-4")
        await logger.compaction_triggered(
            agent_id, current_tokens, threshold_tokens, model
        )
    except Exception:
        pass  # Ignore logging errors

    # Execute compaction
    compactor = CompactionAgent(llm, config)
    history = llm.get_history()
    before_messages = len(history)
    compacted = await compactor.compact_history(history)

    if compacted is None:
        # Compaction failed
        try:
            from agent.async_logger import get_logger

            logger = get_logger()
            await logger.compaction_failed(agent_id, "Summary generation failed")
        except Exception:
            pass
        return None

    # Validate compaction
    if not compactor.validate_compacted_history(history, compacted):
        # Validation failed
        try:
            from agent.async_logger import get_logger

            logger = get_logger()
            await logger.compaction_failed(
                agent_id, "Validation failed - compacted history not smaller"
            )
        except Exception:
            pass
        return None

    # Log success
    try:
        from agent.async_logger import get_logger

        logger = get_logger()
        model = getattr(llm, "model", "gpt-4")
        after_tokens = detector.counter.count_messages(compacted, model)
        after_messages = len(compacted)
        await logger.compaction_success(
            agent_id, current_tokens, after_tokens, before_messages, after_messages
        )
    except Exception:
        pass

    return compacted
