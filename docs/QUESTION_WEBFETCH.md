# Question and Webfetch Tools

This document describes the Phase 4 tools: `question` and `webfetch`.

## question

Ask the user clarifying questions during execution.

Signature:

```python
async def question(
    questions: list[dict[str, Any]],
    ctx,
    custom: bool = True,
)
```

Question schema:

```json
{
  "header": "Short label",
  "question": "Full question text",
  "options": [
    {"label": "Option A", "description": "Details"}
  ],
  "multiple": false,
  "custom": true
}
```

Requirements:

- `Context` must provide a user input handler via `set_user_input_handler()`
- If no handler is configured, the tool returns an error
- For TUI arrow-key selection, use `prompt_toolkit` and the built-in handler

Output:

- `metadata.answers`: list of `{question_index, selected}`

## webfetch

Fetch content from a URL and convert format.

Signature:

```python
async def webfetch(
    url: str,
    ctx,
    format: str = "markdown",
    timeout: int = 30,
)
```

Behavior:

- Supports `markdown`, `text`, or `html`
- Enforces 5MB size limit
- Validates http/https URLs
- Uses a modern User-Agent

Dependencies:

- `requests`
- `beautifulsoup4`
- `html2text`
- `prompt_toolkit` (for TUI question handler)

Output metadata:

- `url`, `final_url`, `status_code`, `content_type`, `mime_type`, `charset`, `size_bytes`, `format`, `format_applied`

## Example

```python
from agent.tools import question, webfetch
from agent.tool import Tool
from agent.context import create_auto_approve_context

ctx = create_auto_approve_context(
    patterns={"question": ["*"], "webfetch": ["*"]},
    working_directory=".",
)

from agent.tools.question import tui_handler
ctx.set_user_input_handler(tui_handler)

question_tool = Tool(question, context=ctx)
webfetch_tool = Tool(webfetch, context=ctx)

q = [{
    "header": "Format",
    "question": "Which format?",
    "options": [
        {"label": "markdown", "description": "HTML to Markdown"},
        {"label": "text", "description": "Plain text"}
    ],
    "multiple": false
}]

answers = question_tool.call(questions=q)
fmt = answers.metadata["answers"][0]["selected"][0]

result = webfetch_tool.call(url="https://example.com", format=fmt)
print(result.output)
```
