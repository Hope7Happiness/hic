# LLM Provider Switching Guide

This guide explains how to switch between different LLM providers (Copilot and DeepSeek) in the async parallel agent examples.

## Quick Start

### Use Copilot (Default)

```bash
python examples/async_parallel_agents.py
python examples/async_parallel_agents_real.py
```

### Use DeepSeek

**Method 1: Command line argument**
```bash
python examples/async_parallel_agents.py --llm deepseek
python examples/async_parallel_agents_real.py --llm deepseek
```

**Method 2: Environment variable**
```bash
LLM_PROVIDER=deepseek python examples/async_parallel_agents.py
LLM_PROVIDER=deepseek python examples/async_parallel_agents_real.py
```

**Method 3: Set in .env file**
```bash
# Add to .env file
LLM_PROVIDER=deepseek
```

## Supported Providers

| Provider | Model | Speed | Cost | Setup Required |
|----------|-------|-------|------|----------------|
| `copilot` | claude-haiku-4.5 | ⚡⚡⚡ Fast | 💰 Cheap | OAuth auth (one-time) |
| `deepseek` | deepseek-chat | ⚡⚡ Medium | 💰💰 Medium | API key in .env |

## Configuration Priority

The examples check for the LLM provider in this order:

1. **Command line argument**: `--llm copilot/deepseek`
2. **Environment variable**: `LLM_PROVIDER=copilot/deepseek`
3. **Default**: `copilot`

## Setup Instructions

### Copilot Setup (Default)

1. Authenticate once:
   ```bash
   cd auth/copilot
   python cli.py auth login
   ```

2. Test authentication:
   ```bash
   pytest tests/test_copilot_auth.py -v
   ```

3. Run examples:
   ```bash
   python examples/async_parallel_agents.py
   ```

**See**: [AI_COPILOT_SETUP.md](AI_COPILOT_SETUP.md) for detailed setup

### DeepSeek Setup

1. Get API key from https://platform.deepseek.com/

2. Add to `.env` file:
   ```bash
   DEEPSEEK_API_KEY=sk-your_deepseek_api_key_here
   ```

3. Run examples with DeepSeek:
   ```bash
   python examples/async_parallel_agents.py --llm deepseek
   ```

## Comparing Providers

To compare behavior between providers, run the same example with both:

```bash
# Test with Copilot
python examples/async_parallel_agents_real.py --llm copilot

# Test with DeepSeek
python examples/async_parallel_agents_real.py --llm deepseek
```

### What to Compare

- **Response Quality**: Check if the LLM follows instructions correctly
- **Speed**: Total execution time (shown at end)
- **Parallel Execution**: Verify both subagents run in parallel
- **Real-time Reporting**: Check if parent agent reports results immediately (async_parallel_agents_real.py)

## Example Output

### With Copilot
```
======================================================================
Async Agent Example with Real LLM (COPILOT)
======================================================================

🤖 Using GitHub Copilot LLM (model: claude-haiku-4.5)
Starting parent agent...
...
```

### With DeepSeek
```
======================================================================
Async Agent Example with Real LLM (DEEPSEEK)
======================================================================

🤖 Using DeepSeek LLM (model: deepseek-chat)
Starting parent agent...
...
```

## Debugging Tips

### Issue: "Expected" behavior not matching

1. **Check System Prompts**: Different LLMs may interpret instructions differently
2. **Try Both Providers**: Compare outputs to identify if it's LLM-specific
3. **Increase Iterations**: Some LLMs may need more iterations (adjust `max_iterations`)
4. **Check Logs**: Each agent creates a log file in `logs/` directory

### Enable Verbose Logging

The examples already have console logging enabled. To see even more detail, check the log files:

```bash
# View most recent parent agent log
ls -t logs/ParentAgent_*.log | head -1 | xargs cat

# View most recent subagent logs
ls -t logs/WeatherAgent_*.log | head -1 | xargs cat
ls -t logs/StockAgent_*.log | head -1 | xargs cat
```

### Common Issues

**Copilot: "Not authenticated"**
```bash
# Solution: Authenticate
cd auth/copilot
python cli.py auth login
```

**DeepSeek: "DEEPSEEK_API_KEY not found"**
```bash
# Solution: Add to .env file
echo "DEEPSEEK_API_KEY=sk-your_key_here" >> .env
```

**Different behavior between providers**
- This is expected - different LLMs have different reasoning patterns
- Adjust system prompts if one provider consistently fails
- Consider the trade-offs (speed vs quality vs cost)

## Advanced: Modify LLM Configuration

To change models or parameters, edit the `create_llm()` function in the example files:

```python
def create_llm(provider: str | None = None):
    if provider == "deepseek":
        return DeepSeekLLM(
            api_key=api_key, 
            model="deepseek-chat",
            temperature=0.7,  # Adjust temperature
        )
    else:  # copilot
        return CopilotLLM(
            model="claude-sonnet-4.5",  # Try different model
            temperature=0.7,
        )
```

### Available Copilot Models

- `claude-haiku-4.5` - Fast and cheap (default)
- `claude-sonnet-4.5` - More capable, balanced
- `gpt-4o` - Latest GPT-4
- `gpt-4o-mini` - Smaller GPT-4
- `o1-preview` - Advanced reasoning

Run `cd auth/copilot && python cli.py models` to see all available models.

## Performance Comparison

Based on testing with `async_parallel_agents.py`:

| Provider | FastAgent | SlowAgent | Parent Agent | Total Time |
|----------|-----------|-----------|--------------|------------|
| Copilot (claude-haiku-4.5) | ~13s | ~18s | ~13s | ~26s |
| DeepSeek (deepseek-chat) | ~10s | ~16s | ~11s | ~25s |

**Note**: Times include LLM API calls. Actual sleep times are 3s and 8s respectively.

## Troubleshooting Real-Time Reporting

If the parent agent in `async_parallel_agents_real.py` is **not** reporting results immediately:

1. **Check System Prompt**: The prompt instructs the parent to use `Thought` field for real-time updates
2. **Verify Resume Events**: Parent should be resumed after each subagent completes
3. **Check Logs**: Look for "Resumed: Triggered by:" messages
4. **Compare Providers**: Try both to see if it's LLM-specific

Expected behavior:
- Parent resumes when WeatherAgent finishes (~3s)
- Parent reports weather in Thought, continues waiting
- Parent resumes when StockAgent finishes (~10s)
- Parent reports stock price in Thought, then finishes

## Support

For issues or questions:
- Check existing test results: `pytest tests/test_copilot_auth.py -v`
- Review logs in `logs/` directory
- Try both providers to isolate issues
- Refer to [AI_COPILOT_SETUP.md](AI_COPILOT_SETUP.md) for Copilot setup
- Check `.env.example` for configuration template

## Summary

✅ **Two examples support both Copilot and DeepSeek**:
- `examples/async_parallel_agents.py` - Basic parallel execution
- `examples/async_parallel_agents_real.py` - Real-time reporting

✅ **Easy switching**: Use `--llm` flag or `LLM_PROVIDER` env var

✅ **Default provider**: Copilot (no API key needed, just one-time OAuth)

✅ **Backward compatible**: DeepSeek still supported for comparison

Happy debugging! 🎉
