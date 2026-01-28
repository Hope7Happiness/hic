# Context Compaction Examples

This directory contains examples demonstrating the context compaction feature for the HIC agent framework.

## What is Context Compaction?

Context compaction automatically summarizes old conversation history when the total token count exceeds a threshold. This allows agents to:

- Handle long-running tasks without hitting context limits
- Continue working on complex tasks that generate lots of conversation
- Automatically manage memory by summarizing old messages

## How It Works

1. **Monitor**: After each LLM response, count tokens in conversation history
2. **Detect**: If tokens >= threshold (e.g., 75% of context limit), trigger compaction
3. **Split**: Divide history into `[system] + [old messages] + [recent protected messages]`
4. **Summarize**: Use LLM to create a concise summary of old messages
5. **Replace**: Replace old messages with a single summary message
6. **Validate**: Ensure compacted history has fewer tokens than original

## Examples

### 1. `test_compaction_direct.py` - Direct Testing (Recommended)

**Best for**: Understanding how compaction works

This example:
- Manually builds a large conversation history
- Guarantees compaction will trigger
- Shows detailed before/after statistics
- Runs quickly (no real agent task)

```bash
python examples/test_compaction_direct.py
```

**Output:**
```
Configuration:
  - Context limit: 2000 tokens
  - Threshold: 10%
  - Will trigger at: 200 tokens
  - Protect recent: 2 messages

Current conversation:
  - Messages: 7
  - Estimated tokens: 1,083
  - Exceeds threshold: True

🔄 Context compaction triggered: 1,083 tokens (541.5% of threshold: 200)
✅ Compaction successful: 1,083 → 276 tokens (saved 807 tokens, 74.5%)
   Messages: 7 → 4 (removed 3)
```

### 2. `test_compaction.py` - Real Agent Task

**Best for**: Seeing compaction in production-like scenario

This example:
- Runs a real agent with tools
- Asks agent to write 3 long stories (300+ words each)
- Saves stories to files using `save_story` tool
- Uses very low context limit to force compaction

```bash
python examples/test_compaction.py
```

**Note:** This example uses a 180-second timeout for the Copilot API to handle long content generation tasks.

**Output:**
```
🔄 Context compaction triggered: 3,079 tokens (154.0% of threshold: 2,000)
⚠️ Compaction failed: Validation failed - compacted history not smaller

📊 Execution Results:
   - Success: True
   - Iterations: 5
   - Stories created: 3
```

## Configuration

### Basic Setup

```python
from agent.config import CompactionConfig, set_compaction_config

# Production settings (default behavior)
config = CompactionConfig(
    enabled=True,
    threshold=0.75,  # Trigger at 75% of context limit
    protect_recent_messages=2,  # Keep last 2 messages
    counter_strategy="simple",  # Use fast heuristic counting
    context_limits={
        "gpt-4": 128_000,
        "claude-sonnet-4.5": 200_000,
        "deepseek-chat": 64_000,
        "default": 100_000
    }
)

set_compaction_config(config)
```

### Aggressive Settings (Force Compaction)

```python
# For testing or memory-constrained environments
config = CompactionConfig(
    enabled=True,
    threshold=0.25,  # Trigger at 25% of limit
    protect_recent_messages=2,
    context_limits={
        "claude-sonnet-4.5": 8_000,  # Much lower than real limit
        "default": 8_000
    }
)
```

### LLM Timeout Configuration

For long-running tasks that generate lots of content, you may need to increase the API timeout:

```python
from agent.llm import CopilotLLM

# Default timeout: 60 seconds
llm = CopilotLLM(model="claude-sonnet-4.5")

# Increased timeout for long tasks: 180 seconds (3 minutes)
llm = CopilotLLM(model="claude-sonnet-4.5", timeout=180)
```

**When to increase timeout:**
- Writing multiple long documents (stories, articles, reports)
- Complex analysis tasks with detailed output
- Tasks that generate > 1000 tokens of output
- When you see `ReadTimeoutError` or timeout-related errors

**Timeout behavior:**
- Default: 60 seconds
- On timeout: Automatically retries with exponential backoff (1s, 2s, 4s, 8s, 16s)
- Max retries: 5 attempts
- Clear error message if all retries fail

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | `True` | Enable/disable compaction |
| `threshold` | float | `0.75` | Trigger at % of context limit (0.0-1.0) |
| `protect_recent_messages` | int | `2` | Number of recent messages to keep |
| `reserved_output_tokens` | int | `4000` | Reserve tokens for LLM response |
| `counter_strategy` | str | `"simple"` | Token counter: "simple", "tiktoken", "auto" |
| `context_limits` | dict | See above | Model-specific context limits |

### Token Counting Strategies

**Simple Counter** (Default)
- Fast heuristic: `chars / 4`
- No external dependencies
- Good enough for most cases
- ~10-20% margin of error

**Tiktoken Counter** (Optional)
- Accurate OpenAI tokenization
- Requires `tiktoken` library
- Slightly slower
- Use for precise counting

```python
config = CompactionConfig(
    counter_strategy="tiktoken"  # or "auto" for fallback
)
```

## Logging

Compaction events are automatically logged with detailed metrics:

```python
from agent.async_logger import init_logger

# Enable console output to see compaction messages
await init_logger(log_dir="logs", console_output=True)
```

**Log Messages:**

- `🔄 Context compaction triggered`: Shows when compaction starts
- `✅ Compaction successful`: Shows tokens saved and messages removed
- `⚠️ Compaction failed`: Shows reason for failure
- `⏭️ Compaction skipped`: Shows why compaction was skipped

## Testing

Run all compaction tests:

```bash
# Unit tests for token counter
pytest tests/test_token_counter.py -v

# Integration tests for compaction
pytest tests/test_compaction_integration.py -v

# All compaction tests
pytest tests/test_*compaction*.py -v
```

**Test Coverage:**
- 17 token counter tests
- 11 compaction integration tests
- 1 backward compatibility test
- **Total: 29 tests, all passing**

## Troubleshooting

### Compaction Not Triggering

**Symptoms:** No compaction messages in logs

**Solutions:**
1. Check if enabled: `config.enabled = True`
2. Lower threshold: `config.threshold = 0.25`
3. Reduce context limit: `config.context_limits["default"] = 8000`
4. Ensure task generates enough tokens

### Compaction Fails to Reduce Tokens

**Symptoms:** `⚠️ Compaction failed: Validation failed - compacted history not smaller`

**Causes:**
- Summary is longer than original messages
- Not enough old messages to summarize (all recent)
- Complex structured content that doesn't compress well

**Solutions:**
- Increase `protect_recent_messages` to leave more old messages
- Task continues normally with full history
- Non-critical - agent remains functional

### API Timeout Errors

**Symptoms:** `ReadTimeoutError: Read timed out. (read timeout=60)`

**Solutions:**
1. Increase timeout:
   ```python
   llm = CopilotLLM(timeout=180)  # 3 minutes
   ```
2. Break large tasks into smaller subtasks
3. Check network connectivity
4. Verify API endpoint is responding

### Rate Limit Errors

**Symptoms:** `⚠️ Rate limit (429) hit`

**Behavior:**
- Automatically retries with exponential backoff
- 5 attempts: 1s, 2s, 4s, 8s, 16s delays
- No action needed - handled automatically

**If it persists:**
- Check API quota/billing
- Reduce request frequency
- Use a different LLM provider

## Design Principles

1. **Non-invasive**: Compaction failures don't crash the agent
2. **Graceful degradation**: If compaction fails, continue with full history
3. **Async-compatible**: All operations use async/await
4. **Configurable**: Can be disabled or tuned per deployment
5. **Observable**: Detailed logs with colorful console output
6. **Model-agnostic**: Works with OpenAI, DeepSeek, Copilot, etc.
7. **Test-driven**: Comprehensive test coverage ensures reliability

## Integration Points

Compaction is integrated at 3 checkpoints in `agent/agent.py`:

1. **After initial LLM response** (`_run_async()`)
2. **After each LLM call in main loop** (`_run_async()`)
3. **After resume LLM call** (`_resume_async()`)

No code changes needed to use compaction - just configure and enable!

## Performance Impact

- **Detection**: < 1ms (simple counting)
- **Compaction**: 2-5 seconds (LLM summarization)
- **Frequency**: Only when threshold exceeded
- **Overhead**: Minimal for normal tasks, pays off for long tasks

## Files

### Core Implementation

- `agent/token_counter.py` - Token counting strategies
- `agent/compaction.py` - Compaction detection and execution
- `agent/config.py` - Configuration management
- `agent/async_logger.py` - Logging utilities

### Examples

- `test_compaction_direct.py` - Direct testing with mock history
- `test_compaction.py` - Real agent task with story generation

### Tests

- `tests/test_token_counter.py` - Token counter unit tests
- `tests/test_compaction_integration.py` - End-to-end tests

## Further Reading

- [OpenAI Token Counting](https://platform.openai.com/docs/guides/text-generation/managing-tokens)
- [Claude Context Windows](https://docs.anthropic.com/claude/docs/models-overview)
- [Tiktoken Library](https://github.com/openai/tiktoken)

## Support

If you encounter issues:

1. Check logs for detailed error messages
2. Verify configuration with `get_compaction_config()`
3. Run tests to ensure system integrity
4. Open an issue with logs and reproduction steps
