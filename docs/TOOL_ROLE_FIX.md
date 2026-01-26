# Tool Role Fix - Documentation

## Problem Identified

You noticed that when tools returned results, the AI agent didn't trust them and would repeat the same action. Looking at the logs:

```
69.587s [INFO] [SystemAnalyst] [AGENT] 💭 Thought: 我需要重新按照正确的格式执行分析...
69.588s [INFO] [SystemAnalyst] [AGENT] 🔧 Action: tool - Calling restricted_bash
69.603s [INFO] [SystemAnalyst] [TOOL] ✓ restricted_bash → /Users/peppaking8/Desktop/coding/hic
105.826s [INFO] [SystemAnalyst] [AGENT] 💭 Thought: 用户提供了当前目录的路径信息...
```

The AI kept saying "用户提供了..." (the user provided...) instead of recognizing it came from a tool!

## Root Cause

In `agent/llm.py`, the `chat()` method always added messages with `role: "user"`:

```python
# Before (line 110)
self.history.append({"role": "user", "content": prompt})
```

This meant when tool results were sent back to the LLM:

```
[user]      What directory am I in?
[assistant] Let me check with pwd command...
[user]      Observation: /Users/peppaking8/Desktop/coding/hic  ← ⚠️ PROBLEM!
```

The LLM thought the **USER** was telling it the result, not a tool! This caused the AI to:
- Not trust the result
- Think it needed to verify or re-execute
- Get confused about who was speaking

## Solution Implemented

### 1. Modified `agent/llm.py` (Lines 32-46, 97-116)

Added a `role` parameter to the `chat()` method with default value `"user"`:

```python
def chat(
    self, prompt: str, 
    system_prompt: Optional[str] = None, 
    role: str = "user"  # ← NEW PARAMETER
) -> str:
    """
    Send a message and get a response.

    Args:
        prompt: User message to send
        system_prompt: Optional system prompt (only used if history is empty)
        role: Role of the message sender ("user" or "tool"). Default is "user".

    Returns:
        The assistant's response text
    """
    ...
    # Add message to history with specified role
    self.history.append({"role": role, "content": prompt})  # ← USES ROLE
```

### 2. Modified `agent/agent.py` (Lines 306-309, 561-564)

Updated tool execution to use `role='tool'` when sending observations:

```python
# Before
llm_output = await loop.run_in_executor(
    None, self.llm.chat, f"Observation: {observation}"
)

# After
llm_output = await loop.run_in_executor(
    None, lambda: self.llm.chat(f"Observation: {observation}", role="tool")
)
```

This change was made in **2 places**:
- `Agent.run()` method (line ~307)
- `Agent.resume()` method (line ~560)

## Impact

Now the conversation history looks correct:

```
[user]      What directory am I in?
[assistant] Let me check with pwd command...
[tool]      Observation: /Users/peppaking8/Desktop/coding/hic  ← ✅ CORRECT!
[assistant] You are in /Users/peppaking8/Desktop/coding/hic
```

The LLM now:
- ✅ Recognizes tool results as legitimate outputs from tools
- ✅ Trusts the results and uses them directly
- ✅ Doesn't confuse tool outputs with user messages
- ✅ Won't repeat the same tool call unnecessarily

## Files Modified

1. **`agent/llm.py`**
   - Added `role` parameter to `LLM.chat()` abstract method (line 32-34)
   - Added `role` parameter to `OpenAILLM.chat()` implementation (line 97-99)
   - Changed history append to use `role` variable (line 116)
   - Updated documentation (line 41, 106)

2. **`agent/agent.py`**
   - Modified tool result handling in `run()` method (line 306-309)
   - Modified tool result handling in `resume()` method (line 561-564)
   - Both now pass `role="tool"` when sending observations

## Verification

Run the verification script:

```bash
python verify_role_fix.py
```

Expected output:
```
✅ ALL CHECKS PASSED - FIX IS COMPLETE

Summary of changes:
1. ✅ LLM.chat() now accepts role parameter (default='user')
2. ✅ OpenAILLM.chat() uses role when adding to history
3. ✅ Agent uses role='tool' for tool observations
4. ✅ LLM will now trust tool results as legitimate outputs
```

## Testing

To test the fix with a real agent:

```bash
# Make sure you have DEEPSEEK_API_KEY or OPENAI_API_KEY set
python examples/system_analyst_with_restricted_bash.py
```

You should now see the agent:
- Execute tools only once
- Trust tool results immediately
- Not repeat the same commands
- Understand that "Observation: ..." comes from tools, not users

## Technical Notes

### Why use `lambda:`?

The `run_in_executor()` function doesn't support keyword arguments directly, so we wrap the call:

```python
# Doesn't work:
await loop.run_in_executor(None, self.llm.chat, prompt, role="tool")

# Works:
await loop.run_in_executor(None, lambda: self.llm.chat(prompt, role="tool"))
```

### OpenAI API Compatibility

The OpenAI Chat Completion API supports these roles:
- `system` - System instructions
- `user` - User messages
- `assistant` - AI responses
- `tool` - Tool/function call results
- `function` - (deprecated, use `tool`)

Our fix aligns with OpenAI's official API design.

## Future Considerations

### Other LLM Implementations

If you add other LLM classes (e.g., `ClaudeLLM`, `DeepSeekLLM`), make sure they:
1. Inherit from `LLM` base class
2. Implement `chat()` with the `role` parameter
3. Pass the role to their respective APIs correctly

### Subagent Results

Currently, subagent results are sent as regular messages. Consider whether they should also use a special role (maybe `role="agent"` or similar) to distinguish them from user messages.

### Tool Call Format

For even better clarity, you might want to structure tool results like:

```python
observation = json.dumps({
    "tool": action.tool_name,
    "result": result,
    "success": True
})
```

This would make it even clearer what tool was called and what it returned.

## Related Issues

This fix addresses the issue where:
- ❌ AI doesn't trust tool results (FIXED)
- ❌ AI repeats the same tool call multiple times (FIXED)
- ❌ AI says "user provided..." when tools return data (FIXED)

## Credits

Issue identified and fixed on: January 26, 2026
Root cause: Message role confusion in conversation history
Solution: Explicit role tagging for tool outputs
