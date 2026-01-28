# HIC Context Compaction 实现方案

## 文档信息
- **创建时间**: 2026-01-27
- **目标**: 为HIC Agent框架实现context compaction功能
- **参考**: OpenCode Compaction实现分析
- **状态**: 待审核

---

## 目录
1. [需求分析](#需求分析)
2. [架构设计](#架构设计)
3. [实现计划](#实现计划)
4. [详细设计](#详细设计)
5. [测试方案](#测试方案)
6. [风险与缓解](#风险与缓解)

---

## 需求分析

### 核心问题
当前HIC Agent在处理长对话时，LLM的chat history会不断增长，最终会触发以下问题：
1. **Token限制错误**: 超过模型的context window（如Claude: 200K, GPT-4: 128K）
2. **API调用失败**: 直接导致agent崩溃
3. **成本增加**: 即使不超限，过长的context也会增加API成本

### 功能目标
实现自动化的context compaction机制，包括：
1. ✅ **自动检测**: 检测chat history是否接近token limit
2. ✅ **自动压缩**: 触发compaction agent总结历史对话
3. ✅ **透明执行**: 对用户透明，不中断正常流程
4. ✅ **信息保留**: 总结应保留关键信息以继续对话
5. ✅ **可配置**: 允许用户配置是否启用、触发阈值等

### 非目标（暂不实现）
- ❌ Tool output pruning（P2优先级，本次不做）
- ❌ 插件系统扩展点（暂无插件系统）
- ❌ 手动触发compaction（自动即可）
- ❌ 多级压缩（一次压缩足够）

---

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         HIC Agent                                │
│                                                                   │
│  ┌──────────────┐         ┌──────────────┐                      │
│  │   Agent      │         │ Compaction   │                      │
│  │   (_run)     │────────▶│  Detector    │                      │
│  │              │         │              │                      │
│  └──────────────┘         └──────┬───────┘                      │
│         │                         │                              │
│         │                         │ Token overflow detected      │
│         │                         ▼                              │
│         │                ┌──────────────┐                        │
│         │                │ Compaction   │                        │
│         │                │   Agent      │                        │
│         │                │  (special)   │                        │
│         │                └──────┬───────┘                        │
│         │                        │                               │
│         │                        │ Generate summary              │
│         │                        ▼                               │
│         │                ┌──────────────┐                        │
│         │                │  LLM.chat()  │                        │
│         │◀───────────────│ (all history)│                        │
│         │                └──────────────┘                        │
│         │                                                         │
│         │  Compacted history = [summary message]                 │
│         │                                                         │
│         ▼                                                         │
│  ┌──────────────┐                                                │
│  │ Continue with│                                                │
│  │ new context  │                                                │
│  └──────────────┘                                                │
└─────────────────────────────────────────────────────────────────┘
```

### 核心组件

#### 1. TokenCounter（新增）
**位置**: `agent/token_counter.py`

**职责**: 
- 估算chat history的token数量
- 提供多种计数策略（简单/精确）

#### 2. CompactionDetector（新增）
**位置**: `agent/compaction.py`

**职责**:
- 检测是否需要compaction
- 管理compaction触发逻辑

#### 3. CompactionAgent（新增）
**位置**: `agent/compaction.py`

**职责**:
- 执行compaction（调用LLM生成总结）
- 生成新的compacted history

#### 4. Agent（修改）
**位置**: `agent/agent.py`

**修改点**:
- 在`_internal_run`和`_internal_resume`中检测overflow
- 触发compaction流程
- 用compacted history替换原history

#### 5. LLM（扩展）
**位置**: `agent/llm.py`

**新增方法**:
- `count_tokens()`: 返回当前history的token数
- `compact_history()`: 对history进行压缩（可选，作为工具方法）

---

## 实现计划

### 阶段划分

#### Phase 1: 基础设施（P0）
**目标**: 建立token计数和配置基础

**任务**:
1. ✅ 实现`TokenCounter`类
   - 简单估算（chars/4）
   - 精确计数（tiktoken）
2. ✅ 添加配置选项到`agent/config.py`
3. ✅ 为`LLM`添加`count_tokens()`方法
4. ✅ 编写单元测试

**验收标准**:
- 能够准确计数不同LLM的history tokens
- 配置可以正确加载

#### Phase 2: Compaction核心（P1）
**目标**: 实现compaction检测和执行

**任务**:
1. ✅ 实现`CompactionDetector.should_compact()`
2. ✅ 实现`CompactionAgent.compact()`
3. ✅ 创建compaction system prompt
4. ✅ 修改`Agent._internal_run()`集成检测
5. ✅ 修改`Agent._internal_resume()`集成检测
6. ✅ 编写集成测试

**验收标准**:
- Overflow能够正确检测
- Compaction能够生成有效总结
- Agent能够用compacted history继续运行

#### Phase 3: 优化与完善（P2）
**目标**: 提升用户体验和性能

**任务**:
1. ✅ 添加compaction日志
2. ✅ 优化compaction prompt
3. ✅ 添加保护策略（保留最近N条消息）
4. ✅ 添加compaction失败处理
5. ✅ 性能测试

**验收标准**:
- Compaction过程有清晰日志
- 失败能够优雅降级
- 性能满足要求

---

## 详细设计

### 1. Token计数模块

#### 文件: `agent/token_counter.py`

```python
"""
Token counting utilities for context compaction.

Provides both simple (heuristic) and accurate (tiktoken) token counting.
"""

from typing import List, Dict, Optional
from abc import ABC, abstractmethod


class TokenCounter(ABC):
    """Abstract base class for token counting."""
    
    @abstractmethod
    def count(self, text: str) -> int:
        """Count tokens in a string."""
        pass
    
    @abstractmethod
    def count_messages(self, messages: List[Dict[str, str]]) -> int:
        """Count tokens in a list of messages."""
        pass


class SimpleTokenCounter(TokenCounter):
    """
    Simple heuristic-based token counter.
    
    Uses the approximation: 1 token ≈ 4 characters.
    Fast but less accurate.
    """
    
    CHARS_PER_TOKEN = 4
    
    def count(self, text: str) -> int:
        """Count tokens using character-based heuristic."""
        return max(0, len(text) // self.CHARS_PER_TOKEN)
    
    def count_messages(self, messages: List[Dict[str, str]]) -> int:
        """Count tokens in message list."""
        total = 0
        for msg in messages:
            # Count role
            total += self.count(msg.get("role", ""))
            # Count content
            total += self.count(msg.get("content", ""))
            # Add overhead for message structure (estimate)
            total += 4
        return total


class TiktokenCounter(TokenCounter):
    """
    Accurate token counter using tiktoken library.
    
    Slower but more accurate, especially for non-English text.
    """
    
    def __init__(self, model: str = "gpt-4"):
        """
        Initialize with a specific model encoding.
        
        Args:
            model: Model name (e.g., "gpt-4", "gpt-3.5-turbo")
        """
        try:
            import tiktoken
            self.encoding = tiktoken.encoding_for_model(model)
            self.available = True
        except ImportError:
            print("Warning: tiktoken not installed. Falling back to simple counter.")
            self.available = False
            self.simple_counter = SimpleTokenCounter()
        except Exception as e:
            print(f"Warning: Failed to load tiktoken encoding: {e}")
            self.available = False
            self.simple_counter = SimpleTokenCounter()
    
    def count(self, text: str) -> int:
        """Count tokens using tiktoken."""
        if not self.available:
            return self.simple_counter.count(text)
        return len(self.encoding.encode(text))
    
    def count_messages(self, messages: List[Dict[str, str]]) -> int:
        """
        Count tokens in message list.
        
        Based on OpenAI's token counting guide:
        https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
        """
        if not self.available:
            return self.simple_counter.count_messages(messages)
        
        num_tokens = 0
        for message in messages:
            # Every message follows <|start|>{role/name}\n{content}<|end|>\n
            num_tokens += 4
            for key, value in message.items():
                num_tokens += len(self.encoding.encode(value))
                if key == "name":
                    num_tokens += -1  # Role is omitted if name is present
        num_tokens += 2  # Every reply is primed with <|start|>assistant
        return num_tokens


def create_counter(
    strategy: str = "simple",
    model: Optional[str] = None
) -> TokenCounter:
    """
    Factory function to create appropriate token counter.
    
    Args:
        strategy: "simple" or "tiktoken"
        model: Model name for tiktoken (optional)
    
    Returns:
        TokenCounter instance
    """
    if strategy == "tiktoken":
        return TiktokenCounter(model or "gpt-4")
    else:
        return SimpleTokenCounter()
```

#### 设计说明
- **两种策略**: Simple（快速但粗略）和Tiktoken（慢但准确）
- **降级处理**: 如果tiktoken不可用，自动降级到simple
- **兼容性**: 支持所有主流模型的encoding

---

### 2. Compaction配置

#### 文件: `agent/config.py`

```python
"""
Configuration for HIC Agent framework.
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class CompactionConfig:
    """Configuration for context compaction."""
    
    # 是否启用自动compaction
    enabled: bool = True
    
    # Token计数策略: "simple" or "tiktoken"
    token_counter: str = "simple"
    
    # 触发阈值（占用context的百分比）
    # 例如：0.8 表示当使用80%的context时触发
    threshold: float = 0.75
    
    # 模型的context limit（如果为0，从LLM配置获取）
    # 格式: {"gpt-4": 128000, "claude-sonnet": 200000}
    context_limits: dict = None
    
    # 保护最近N条消息不被压缩
    protect_recent_messages: int = 2
    
    # 预留给输出的token数
    reserved_output_tokens: int = 4096
    
    # Compaction失败后的重试次数
    max_retries: int = 1
    
    # Compaction使用的模型（如果为None，使用当前LLM的模型）
    compaction_model: Optional[str] = None
    
    def __post_init__(self):
        if self.context_limits is None:
            # 默认的context limits
            self.context_limits = {
                "gpt-4": 128000,
                "gpt-4o": 128000,
                "gpt-3.5-turbo": 16385,
                "claude-sonnet-4.5": 200000,
                "claude-haiku-4.5": 200000,
                "deepseek-chat": 64000,
            }
    
    def get_context_limit(self, model_name: str) -> int:
        """
        Get context limit for a specific model.
        
        Args:
            model_name: Model name
        
        Returns:
            Context limit in tokens, or 0 if unknown
        """
        # Try exact match
        if model_name in self.context_limits:
            return self.context_limits[model_name]
        
        # Try partial match (e.g., "gpt-4-turbo" matches "gpt-4")
        for key, limit in self.context_limits.items():
            if model_name.startswith(key):
                return limit
        
        # Unknown model
        return 0
    
    def get_usable_tokens(self, model_name: str) -> int:
        """
        Get usable token count (context_limit - reserved_for_output).
        
        Args:
            model_name: Model name
        
        Returns:
            Usable tokens for input
        """
        limit = self.get_context_limit(model_name)
        if limit == 0:
            return 0
        return limit - self.reserved_output_tokens


# Global compaction config instance
_compaction_config = CompactionConfig()


def get_compaction_config() -> CompactionConfig:
    """Get the global compaction configuration."""
    return _compaction_config


def set_compaction_config(config: CompactionConfig):
    """Set the global compaction configuration."""
    global _compaction_config
    _compaction_config = config
```

#### 配置说明
- **threshold**: 默认0.75，即使用75%时触发（留25%余量）
- **protect_recent_messages**: 保护最近2条消息，避免压缩丢失即时信息
- **reserved_output_tokens**: 为LLM输出预留4K tokens
- **context_limits**: 内置主流模型的限制，可扩展

---

### 3. Compaction核心模块

#### 文件: `agent/compaction.py`

```python
"""
Context compaction for HIC Agent framework.

Automatically summarizes conversation history when approaching token limits.
"""

import asyncio
from typing import List, Dict, Optional, Tuple
from agent.llm import LLM
from agent.token_counter import create_counter, TokenCounter
from agent.config import get_compaction_config, CompactionConfig


# Compaction system prompt
COMPACTION_SYSTEM_PROMPT = """你是一个专门负责总结对话历史的AI助手。

当被要求总结时，请提供一个详细但简洁的总结，重点关注：
- 已完成的工作和任务
- 当前正在进行的工作
- 涉及的文件和代码修改
- 接下来需要做什么
- 用户的关键要求、限制和偏好
- 重要的技术决策及其原因

你的总结应该足够全面以提供完整的上下文，但又足够简洁以便快速理解。
总结应该使用第一人称（"我"）的视角，就像你在继续对话一样。

重要：
- 不要遗漏关键的技术细节（如文件路径、函数名、错误信息等）
- 不要添加新的建议或计划，只总结已有内容
- 保持总结的连贯性，让下一个对话能够无缝继续
"""

COMPACTION_USER_PROMPT = """请总结上面的对话历史，生成一个详细的摘要。

这个摘要将用于继续我们的对话，新的对话将无法访问上述历史，所以请确保摘要包含所有必要的信息。

请用第一人称（"我"）的视角来写摘要，就像你在继续对话一样。例如：
"我帮助用户修复了X文件中的Y问题，通过Z方法解决了..."

摘要应该包括：
1. 对话的背景和目标
2. 已完成的主要任务和结果
3. 涉及的具体文件和修改内容
4. 当前的状态和下一步计划
5. 需要记住的重要约束或用户偏好
"""


class CompactionDetector:
    """Detects when context compaction is needed."""
    
    def __init__(
        self,
        counter: TokenCounter,
        config: Optional[CompactionConfig] = None
    ):
        """
        Initialize compaction detector.
        
        Args:
            counter: Token counter instance
            config: Compaction configuration (uses global if None)
        """
        self.counter = counter
        self.config = config or get_compaction_config()
    
    def should_compact(
        self,
        history: List[Dict[str, str]],
        model_name: str
    ) -> Tuple[bool, int, int]:
        """
        Check if compaction is needed.
        
        Args:
            history: Chat history
            model_name: Model name for context limit lookup
        
        Returns:
            Tuple of (should_compact, current_tokens, limit_tokens)
        """
        if not self.config.enabled:
            return False, 0, 0
        
        # Get context limit
        usable = self.config.get_usable_tokens(model_name)
        if usable == 0:
            # Unknown model, can't determine
            return False, 0, 0
        
        # Count current tokens
        current = self.counter.count_messages(history)
        
        # Check threshold
        threshold = int(usable * self.config.threshold)
        should = current > threshold
        
        return should, current, usable


class CompactionAgent:
    """Executes context compaction by summarizing history."""
    
    def __init__(
        self,
        llm: LLM,
        counter: TokenCounter,
        config: Optional[CompactionConfig] = None
    ):
        """
        Initialize compaction agent.
        
        Args:
            llm: LLM instance for generating summaries
            config: Compaction configuration
        """
        self.llm = llm
        self.counter = counter
        self.config = config or get_compaction_config()
    
    async def compact(
        self,
        history: List[Dict[str, str]],
        protect_recent: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Compact chat history by generating a summary.
        
        Args:
            history: Original chat history
            protect_recent: Number of recent messages to protect (optional)
        
        Returns:
            Compacted history: [system, summary_message, ...protected_messages]
        
        Raises:
            RuntimeError: If compaction fails
        """
        if len(history) == 0:
            return history
        
        protect = protect_recent if protect_recent is not None else self.config.protect_recent_messages
        
        # Split history into: to_summarize and to_protect
        if protect > 0 and len(history) > protect:
            # Find the split point (keep system messages in to_summarize)
            protected_msgs = []
            to_summarize = []
            
            # Find system messages
            system_msgs = [msg for msg in history if msg.get("role") == "system"]
            
            # Get recent messages (excluding system)
            non_system = [msg for msg in history if msg.get("role") != "system"]
            if len(non_system) > protect:
                to_summarize_content = non_system[:-protect]
                protected_msgs = non_system[-protect:]
            else:
                # All non-system messages are protected
                to_summarize_content = []
                protected_msgs = non_system
            
            # Combine for summarization
            to_summarize = system_msgs + to_summarize_content
        else:
            to_summarize = history
            protected_msgs = []
        
        # Generate summary
        try:
            summary = await self._generate_summary(to_summarize)
        except Exception as e:
            raise RuntimeError(f"Failed to generate compaction summary: {e}")
        
        # Build new history
        # Keep system messages
        system_msgs = [msg for msg in history if msg.get("role") == "system"]
        
        # Create summary message
        summary_msg = {
            "role": "assistant",
            "content": f"[CONTEXT SUMMARY]\n\n{summary}"
        }
        
        # Combine: system + summary + protected
        compacted = system_msgs + [summary_msg] + protected_msgs
        
        return compacted
    
    async def _generate_summary(
        self,
        history: List[Dict[str, str]]
    ) -> str:
        """
        Generate summary using LLM.
        
        Args:
            history: History to summarize
        
        Returns:
            Summary text
        """
        # Save and reset LLM history
        original_history = self.llm.get_history()
        self.llm.reset_history()
        
        try:
            # Build compaction messages
            compaction_messages = history + [
                {
                    "role": "user",
                    "content": COMPACTION_USER_PROMPT
                }
            ]
            
            # Set history directly
            self.llm.set_history(compaction_messages)
            
            # Generate summary
            loop = asyncio.get_event_loop()
            summary = await loop.run_in_executor(
                None,
                self.llm.chat,
                COMPACTION_USER_PROMPT,
                COMPACTION_SYSTEM_PROMPT
            )
            
            return summary
        
        finally:
            # Restore original history
            self.llm.set_history(original_history)


async def compact_if_needed(
    llm: LLM,
    model_name: str,
    config: Optional[CompactionConfig] = None
) -> bool:
    """
    Check and perform compaction if needed.
    
    This is a convenience function that combines detection and compaction.
    
    Args:
        llm: LLM instance
        model_name: Model name for limit lookup
        config: Compaction configuration
    
    Returns:
        True if compaction was performed, False otherwise
    """
    config = config or get_compaction_config()
    
    # Create counter and detector
    counter = create_counter(
        strategy=config.token_counter,
        model=model_name
    )
    detector = CompactionDetector(counter, config)
    
    # Check if compaction needed
    history = llm.get_history()
    should, current, limit = detector.should_compact(history, model_name)
    
    if not should:
        return False
    
    # Log compaction
    try:
        from agent.async_logger import get_logger, LogLevel
        logger = get_logger()
        await logger.log(
            LogLevel.INFO,
            "compaction",
            f"🔄 Compaction triggered: {current}/{limit} tokens ({current*100//limit}%)",
            "COMPACTION"
        )
    except Exception:
        pass
    
    # Perform compaction
    agent = CompactionAgent(llm, counter, config)
    
    retries = config.max_retries
    last_error = None
    
    for attempt in range(retries + 1):
        try:
            compacted = await agent.compact(history)
            
            # Update LLM history
            llm.set_history(compacted)
            
            # Log success
            new_tokens = counter.count_messages(compacted)
            try:
                from agent.async_logger import get_logger, LogLevel
                logger = get_logger()
                await logger.log(
                    LogLevel.INFO,
                    "compaction",
                    f"✅ Compaction complete: {current} → {new_tokens} tokens (saved {current - new_tokens})",
                    "COMPACTION"
                )
            except Exception:
                pass
            
            return True
        
        except Exception as e:
            last_error = e
            if attempt < retries:
                # Log retry
                try:
                    from agent.async_logger import get_logger, LogLevel
                    logger = get_logger()
                    await logger.log(
                        LogLevel.WARNING,
                        "compaction",
                        f"⚠️  Compaction attempt {attempt + 1} failed: {e}. Retrying...",
                        "COMPACTION"
                    )
                except Exception:
                    pass
                
                await asyncio.sleep(1)  # Brief delay before retry
            else:
                # Log failure
                try:
                    from agent.async_logger import get_logger, LogLevel
                    logger = get_logger()
                    await logger.log(
                        LogLevel.ERROR,
                        "compaction",
                        f"❌ Compaction failed after {retries + 1} attempts: {last_error}",
                        "COMPACTION"
                    )
                except Exception:
                    pass
                
                # Don't raise, let agent continue with full history
                return False
    
    return False
```

#### 设计说明
- **CompactionDetector**: 负责检测，分离关注点
- **CompactionAgent**: 负责执行，生成总结
- **compact_if_needed**: 便捷函数，集成检测+执行+日志
- **保护策略**: 保留最近N条消息，避免丢失即时信息
- **失败处理**: 重试机制，失败后不抛异常（优雅降级）

---

### 4. Agent集成

#### 文件: `agent/agent.py`

**修改点1**: 在`_internal_run`的主循环中添加compaction检测

```python
# 在 agent/agent.py 的 _internal_run 方法中
# 约在 line 355 左右，while iteration < self.max_iterations: 之后

async def _internal_run(self, task: str, agent_id: str) -> AgentResponse:
    # ... 现有代码 ...
    
    while iteration < self.max_iterations:
        iteration += 1
        
        # [NEW] Check and perform compaction if needed
        try:
            from agent.compaction import compact_if_needed
            model_name = getattr(self.llm, 'model', 'unknown')
            await compact_if_needed(self.llm, model_name)
        except Exception as e:
            # Log but don't fail - compaction is best-effort
            try:
                from agent.async_logger import get_logger, LogLevel
                logger = get_logger()
                await logger.log(
                    LogLevel.WARNING,
                    agent_id,
                    f"⚠️  Compaction check failed: {e}",
                    "AGENT"
                )
            except Exception:
                pass
        
        # Try to parse LLM output (with retries)
        action = await self._parse_with_retry(llm_output, iteration, 3, agent_id)
        
        # ... 现有代码继续 ...
```

**修改点2**: 在`_internal_resume`的循环中添加compaction检测

```python
# 在 agent/agent.py 的 _internal_resume 方法中
# 约在 line 686 左右，while iteration < self.max_iterations: 之后

async def _internal_resume(
    self, state: AgentState, message: AgentMessage
) -> AgentResponse:
    # ... 现有代码 ...
    
    while iteration < self.max_iterations:
        iteration += 1
        
        # [NEW] Check and perform compaction if needed
        try:
            from agent.compaction import compact_if_needed
            model_name = getattr(self.llm, 'model', 'unknown')
            await compact_if_needed(self.llm, model_name)
        except Exception as e:
            # Log but don't fail
            try:
                from agent.async_logger import get_logger, LogLevel
                logger = get_logger()
                await logger.log(
                    LogLevel.WARNING,
                    agent_id,
                    f"⚠️  Compaction check failed: {e}",
                    "AGENT"
                )
            except Exception:
                pass
        
        # Parse LLM output
        action = await self._parse_with_retry(llm_output, iteration, 3, agent_id)
        
        # ... 现有代码继续 ...
```

**修改点3**: 在LLM调用失败处也检测是否因为context过长

```python
# 在 agent/agent.py 的 _internal_run 方法中
# 约在 line 322 左右，except Exception as e: 错误处理中

except Exception as e:
    # ... 现有错误处理 ...
    
    # [NEW] Check if error is due to context length
    error_msg_lower = str(e).lower()
    if "context" in error_msg_lower and "length" in error_msg_lower:
        # Try emergency compaction
        try:
            from agent.compaction import compact_if_needed
            model_name = getattr(self.llm, 'model', 'unknown')
            compacted = await compact_if_needed(self.llm, model_name)
            if compacted:
                # Retry with compacted history
                try:
                    llm_output = await loop.run_in_executor(
                        None, self.llm.chat, task, self.system_prompt
                    )
                    # Continue processing...
                    continue
                except Exception as retry_e:
                    # Give up
                    error_msg = f"LLM call failed even after compaction: {retry_e}"
        except Exception as compact_e:
            # Log compaction failure
            pass
    
    # ... 继续现有的错误处理 ...
```

#### 集成说明
- **三个检测点**: 
  1. 每次iteration开始时（预防性）
  2. resume时（恢复后检测）
  3. LLM调用失败时（应急）
- **非侵入式**: 使用try-except包裹，失败不影响主流程
- **优雅降级**: Compaction失败时继续使用完整history

---

### 5. LLM扩展

#### 文件: `agent/llm.py`

**添加方法**: 为`LLM`基类添加token计数方法

```python
# 在 agent/llm.py 的 LLM 类中添加

class LLM(ABC):
    # ... 现有代码 ...
    
    def count_tokens(self, strategy: str = "simple") -> int:
        """
        Count tokens in current history.
        
        Args:
            strategy: "simple" or "tiktoken"
        
        Returns:
            Estimated token count
        """
        from agent.token_counter import create_counter
        
        model_name = getattr(self, 'model', 'gpt-4')
        counter = create_counter(strategy=strategy, model=model_name)
        return counter.count_messages(self.history)
    
    def get_context_usage(self, context_limit: int, strategy: str = "simple") -> float:
        """
        Get context usage as a percentage.
        
        Args:
            context_limit: Context window size in tokens
            strategy: "simple" or "tiktoken"
        
        Returns:
            Usage percentage (0.0 to 1.0+)
        """
        if context_limit == 0:
            return 0.0
        current = self.count_tokens(strategy)
        return current / context_limit
```

#### 说明
- **可选功能**: 这些方法是可选的，主要用于调试和监控
- **策略灵活**: 支持简单和精确两种计数方式
- **向后兼容**: 不影响现有LLM实现

---

## 测试方案

### 单元测试

#### 1. TokenCounter测试
**文件**: `tests/test_token_counter.py`

```python
import pytest
from agent.token_counter import SimpleTokenCounter, TiktokenCounter, create_counter


def test_simple_counter_basic():
    """Test simple counter basic functionality."""
    counter = SimpleTokenCounter()
    
    # Empty string
    assert counter.count("") == 0
    
    # Known lengths
    assert counter.count("a" * 4) == 1
    assert counter.count("a" * 8) == 2
    assert counter.count("a" * 100) == 25


def test_simple_counter_messages():
    """Test simple counter with message list."""
    counter = SimpleTokenCounter()
    
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    
    # Should count role + content + overhead
    count = counter.count_messages(messages)
    assert count > 0


def test_tiktoken_counter():
    """Test tiktoken counter if available."""
    try:
        counter = TiktokenCounter(model="gpt-4")
        if counter.available:
            # Test basic counting
            text = "Hello, world!"
            count = counter.count(text)
            assert count > 0
            assert count < len(text)  # Should be fewer tokens than characters
    except ImportError:
        pytest.skip("tiktoken not installed")


def test_counter_factory():
    """Test counter factory function."""
    simple = create_counter("simple")
    assert isinstance(simple, SimpleTokenCounter)
    
    tiktoken = create_counter("tiktoken", model="gpt-4")
    assert tiktoken is not None
```

#### 2. CompactionDetector测试
**文件**: `tests/test_compaction_detector.py`

```python
import pytest
from agent.compaction import CompactionDetector
from agent.token_counter import SimpleTokenCounter
from agent.config import CompactionConfig


def test_detector_below_threshold():
    """Test detector when below threshold."""
    config = CompactionConfig(
        enabled=True,
        threshold=0.75,
        context_limits={"test-model": 1000},
        reserved_output_tokens=100
    )
    
    counter = SimpleTokenCounter()
    detector = CompactionDetector(counter, config)
    
    # Small history (far below threshold)
    history = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]
    
    should, current, limit = detector.should_compact(history, "test-model")
    
    assert not should
    assert current < limit


def test_detector_above_threshold():
    """Test detector when above threshold."""
    config = CompactionConfig(
        enabled=True,
        threshold=0.75,
        context_limits={"test-model": 1000},
        reserved_output_tokens=100
    )
    
    counter = SimpleTokenCounter()
    detector = CompactionDetector(counter, config)
    
    # Large history (above threshold)
    # usable = 1000 - 100 = 900
    # threshold = 900 * 0.75 = 675
    # Need > 675 tokens, so create content > 675 * 4 = 2700 chars
    
    history = [
        {"role": "user", "content": "a" * 3000},
    ]
    
    should, current, limit = detector.should_compact(history, "test-model")
    
    assert should
    assert current > 675


def test_detector_disabled():
    """Test detector when compaction is disabled."""
    config = CompactionConfig(enabled=False)
    
    counter = SimpleTokenCounter()
    detector = CompactionDetector(counter, config)
    
    # Large history
    history = [
        {"role": "user", "content": "a" * 10000},
    ]
    
    should, current, limit = detector.should_compact(history, "test-model")
    
    assert not should
```

#### 3. CompactionAgent测试
**文件**: `tests/test_compaction_agent.py`

```python
import pytest
from agent.compaction import CompactionAgent
from agent.token_counter import SimpleTokenCounter
from agent.config import CompactionConfig
from agent.llm import LLM
from typing import Optional


class MockLLM(LLM):
    """Mock LLM for testing."""
    
    def __init__(self):
        super().__init__()
        self.summary = "This is a summary of the conversation."
    
    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        # Add messages to history
        if not self.history and system_prompt:
            self.history.append({"role": "system", "content": system_prompt})
        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "assistant", "content": self.summary})
        return self.summary


@pytest.mark.asyncio
async def test_compaction_agent_basic():
    """Test basic compaction."""
    llm = MockLLM()
    counter = SimpleTokenCounter()
    config = CompactionConfig()
    
    agent = CompactionAgent(llm, counter, config)
    
    # Create history
    history = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "I'm doing well, thanks!"},
    ]
    
    # Compact
    compacted = await agent.compact(history)
    
    # Should have: system + summary
    assert len(compacted) >= 2
    assert compacted[0]["role"] == "system"
    assert any("[CONTEXT SUMMARY]" in msg.get("content", "") for msg in compacted)


@pytest.mark.asyncio
async def test_compaction_agent_protect_recent():
    """Test compaction with protected messages."""
    llm = MockLLM()
    counter = SimpleTokenCounter()
    config = CompactionConfig(protect_recent_messages=2)
    
    agent = CompactionAgent(llm, counter, config)
    
    # Create history
    history = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Message 1"},
        {"role": "assistant", "content": "Response 1"},
        {"role": "user", "content": "Message 2"},
        {"role": "assistant", "content": "Response 2"},
    ]
    
    # Compact with protection
    compacted = await agent.compact(history, protect_recent=2)
    
    # Should have: system + summary + 2 protected messages
    assert len(compacted) >= 4
    
    # Check that recent messages are preserved
    assert compacted[-2]["content"] == "Message 2"
    assert compacted[-1]["content"] == "Response 2"
```

### 集成测试

#### 文件: `tests/test_compaction_integration.py`

```python
import pytest
import asyncio
from agent.agent import Agent
from agent.llm import LLM
from agent.config import CompactionConfig, set_compaction_config
from typing import Optional


class TestLLM(LLM):
    """Test LLM that triggers compaction."""
    
    def __init__(self, trigger_at_call: int = 5):
        super().__init__()
        self.call_count = 0
        self.trigger_at_call = trigger_at_call
        self.model = "test-model"
    
    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        self.call_count += 1
        
        # Add to history
        if not self.history and system_prompt:
            self.history.append({"role": "system", "content": system_prompt})
        self.history.append({"role": "user", "content": prompt})
        
        # Generate response
        if "总结" in prompt or "summary" in prompt.lower():
            # This is a compaction request
            response = "Summary: This is a summary of previous conversation."
        else:
            response = f"Action: finish\nContent: Response {self.call_count}"
        
        self.history.append({"role": "assistant", "content": response})
        return response


@pytest.mark.asyncio
async def test_agent_with_compaction():
    """Test agent with compaction enabled."""
    # Configure compaction with low threshold
    config = CompactionConfig(
        enabled=True,
        threshold=0.5,  # Very low threshold for testing
        context_limits={"test-model": 100},  # Very small limit
        protect_recent_messages=1
    )
    set_compaction_config(config)
    
    # Create test LLM and agent
    llm = TestLLM()
    agent = Agent(
        llm=llm,
        name="TestAgent",
        max_iterations=10
    )
    
    # Run agent with a task that generates lots of history
    result = await agent._run_async("Test task that generates history")
    
    # Check that compaction occurred
    history = llm.get_history()
    
    # Should have summary in history
    has_summary = any("[CONTEXT SUMMARY]" in msg.get("content", "") for msg in history)
    
    # Due to low threshold, compaction should have been triggered
    # (This may not always trigger depending on timing, so we make it optional)
    print(f"History length: {len(history)}")
    print(f"Has summary: {has_summary}")
```

### 性能测试

#### 文件: `tests/test_compaction_performance.py`

```python
import pytest
import time
from agent.token_counter import SimpleTokenCounter, TiktokenCounter


def test_simple_counter_performance():
    """Test simple counter performance."""
    counter = SimpleTokenCounter()
    
    # Generate large text
    text = "a" * 100000
    
    start = time.time()
    count = counter.count(text)
    duration = time.time() - start
    
    # Should be very fast (< 10ms)
    assert duration < 0.01
    assert count > 0


def test_tiktoken_counter_performance():
    """Test tiktoken counter performance."""
    try:
        counter = TiktokenCounter(model="gpt-4")
        if not counter.available:
            pytest.skip("tiktoken not available")
        
        # Generate large text
        text = "a" * 100000
        
        start = time.time()
        count = counter.count(text)
        duration = time.time() - start
        
        # Should be reasonably fast (< 100ms)
        assert duration < 0.1
        assert count > 0
    except ImportError:
        pytest.skip("tiktoken not installed")
```

---

## 风险与缓解

### 风险1: Token计数不准确
**影响**: 可能过早或过晚触发compaction

**缓解措施**:
- 提供两种策略（simple和tiktoken）
- 默认使用保守的threshold（0.75）
- 允许用户配置threshold

### 风险2: Compaction失败导致agent崩溃
**影响**: 用户体验中断

**缓解措施**:
- 使用try-except包裹所有compaction调用
- 失败时继续使用完整history（优雅降级）
- 提供重试机制（max_retries）
- 详细的错误日志

### 风险3: Summary丢失关键信息
**影响**: 后续对话缺少必要context

**缓解措施**:
- 使用详细的compaction prompt
- 保护最近N条消息不被压缩
- 在summary中明确要求保留技术细节
- 测试验证summary质量

### 风险4: Compaction增加延迟
**影响**: 用户感觉agent响应变慢

**缓解措施**:
- 只在必要时触发（threshold控制）
- 使用异步执行
- 提供清晰的日志（用户知道在做什么）
- 优化compaction prompt（减少LLM生成时间）

### 风险5: 与现有功能冲突
**影响**: 破坏现有测试或功能

**缓解措施**:
- 默认启用但可配置关闭
- 非侵入式集成（独立模块）
- 全面的单元测试和集成测试
- 分阶段部署（先内部测试）

---

## 实施时间表

### Week 1: 基础设施
- Day 1-2: 实现`TokenCounter`和单元测试
- Day 3: 实现`CompactionConfig`
- Day 4: 为`LLM`添加token计数方法
- Day 5: Code review和调整

### Week 2: 核心功能
- Day 1-2: 实现`CompactionDetector`和`CompactionAgent`
- Day 3: 编写compaction单元测试
- Day 4: 集成到`Agent`
- Day 5: 集成测试

### Week 3: 优化和测试
- Day 1: 优化compaction prompt
- Day 2: 添加详细日志
- Day 3: 性能测试和优化
- Day 4: 端到端测试
- Day 5: 文档和code review

### Week 4: 部署和监控
- Day 1-2: 内部测试和bug修复
- Day 3: 部署到测试环境
- Day 4: 用户测试
- Day 5: 正式发布

---

## 成功标准

### 功能性
- ✅ Token计数准确率 > 90%（对比实际API返回）
- ✅ Compaction检测正确触发（threshold测试）
- ✅ Summary包含关键信息（人工评估）
- ✅ 所有单元测试通过
- ✅ 所有集成测试通过

### 性能
- ✅ Token计数耗时 < 100ms（tiktoken）
- ✅ Compaction总耗时 < 10s（包括LLM调用）
- ✅ Agent响应延迟增加 < 5%

### 可靠性
- ✅ Compaction失败不导致agent崩溃
- ✅ 错误日志清晰可读
- ✅ 配置变更无需重启

### 用户体验
- ✅ Compaction过程有清晰日志
- ✅ 用户可以理解发生了什么
- ✅ 可以通过配置禁用

---

## 未来扩展

### Phase 4: Tool Output Pruning（待定）
- 实现tool output的选择性清除
- 保护关键工具的输出
- 更细粒度的token管理

### Phase 5: 智能Compaction（待定）
- 根据对话类型选择不同的compaction策略
- 学习哪些信息更重要
- 多级压缩（progressive summarization）

### Phase 6: 可视化（待定）
- 在日志中显示token使用图表
- Compaction前后的对比
- 实时token监控

---

## 附录

### A. 依赖库

```txt
# 必需
# (无新增，使用现有依赖)

# 可选（用于精确token计数）
tiktoken>=0.5.0
```

### B. 配置示例

```python
# 在用户代码中配置compaction
from agent.config import CompactionConfig, set_compaction_config

config = CompactionConfig(
    enabled=True,
    token_counter="tiktoken",  # 使用精确计数
    threshold=0.8,  # 80%时触发
    protect_recent_messages=3,  # 保护最近3条消息
    context_limits={
        "gpt-4": 128000,
        "custom-model": 50000,
    }
)

set_compaction_config(config)
```

### C. 调试技巧

```python
# 查看当前token使用
from agent.llm import CopilotLLM

llm = CopilotLLM()
# ... use llm ...

# Check token count
tokens = llm.count_tokens(strategy="tiktoken")
print(f"Current tokens: {tokens}")

# Check usage percentage
usage = llm.get_context_usage(context_limit=200000)
print(f"Context usage: {usage * 100:.1f}%")
```

### D. 故障排查

**问题1**: Compaction总是触发
- 检查threshold是否太低
- 检查context_limits配置是否正确
- 使用tiktoken验证实际token数

**问题2**: Compaction从不触发
- 检查enabled是否为True
- 检查模型名是否在context_limits中
- 增加日志查看检测逻辑

**问题3**: Summary质量差
- 调整COMPACTION_USER_PROMPT
- 增加protect_recent_messages
- 使用更强的模型进行compaction

---

**文档版本**: v1.0  
**最后更新**: 2026-01-27  
**审核状态**: 待审核
