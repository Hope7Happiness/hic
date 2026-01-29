"""
Question tool for interactive user input.

Allows the agent to ask clarifying questions and wait for answers.

Each question must include options with label/description. Do not omit options.
Example:
{
  "header": "Format",
  "question": "Which format should I use?",
  "options": [
    {"label": "markdown", "description": "HTML to Markdown"},
    {"label": "text", "description": "Plain text"},
    {"label": "html", "description": "Raw HTML"}
  ],
  "multiple": false,
  "custom": true
}
"""

from __future__ import annotations

from typing import Any, Optional
import asyncio
from pathlib import Path
import importlib.util
import textwrap


agent_dir = Path(__file__).parent.parent


def _load_agent_module(module_name: str, file_name: str):
    module_path = agent_dir / file_name
    spec = importlib.util.spec_from_file_location(f"agent.{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_name} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


permissions_mod = _load_agent_module("permissions", "permissions.py")
tool_result_mod = _load_agent_module("tool_result", "tool_result.py")

PermissionType = permissions_mod.PermissionType
PermissionRequest = permissions_mod.PermissionRequest
PermissionDeniedError = permissions_mod.PermissionDeniedError
ToolResult = tool_result_mod.ToolResult


def _get_question_text(question: dict[str, Any]) -> str:
    return question.get("question") or question.get("text") or ""


def _get_options(question: dict[str, Any]) -> list[dict[str, Any]]:
    return question.get("options") or question.get("choices") or []


def _format_question_prompt(question: dict[str, Any], custom: bool) -> str:
    header = question.get("header", "Question")
    text = _get_question_text(question)
    options = _get_options(question)
    multiple = question.get("multiple", False)

    lines = [f"[{header}] {text}"]
    for idx, option in enumerate(options, start=1):
        label = option.get("label", "")
        description = option.get("description", "")
        if description:
            lines.append(f"{idx}) {label} — {description}")
        else:
            lines.append(f"{idx}) {label}")

    if custom:
        lines.append("0) Type your own answer")

    if multiple:
        lines.append("Enter choices (comma-separated): ")
    else:
        lines.append("Enter choice: ")

    return "\n".join(lines)


def _parse_selection(
    raw: str, options: list[dict[str, Any]], multiple: bool, custom: bool
) -> list[str]:
    raw = raw.strip()
    if not raw:
        return []

    option_labels = [opt.get("label", "") for opt in options]
    indices = [s.strip() for s in raw.split(",") if s.strip()]

    selected: list[str] = []
    for item in indices:
        if item.isdigit():
            idx = int(item)
            if idx == 0 and custom:
                continue
            if 1 <= idx <= len(option_labels):
                selected.append(option_labels[idx - 1])
                continue

        if custom:
            selected.append(item)
        else:
            raise ValueError(f"Invalid selection: {item}")

        if not multiple:
            break

    if not multiple and len(selected) > 1:
        selected = selected[:1]

    return selected


def _tui_sync(question: dict[str, Any]) -> list[str]:
    try:
        import importlib

        shortcuts = importlib.import_module("prompt_toolkit.shortcuts")

        application = importlib.import_module("prompt_toolkit.application")
        layout = importlib.import_module("prompt_toolkit.layout")
        controls = importlib.import_module("prompt_toolkit.layout.controls")
        key_binding = importlib.import_module("prompt_toolkit.key_binding")

        Application = getattr(application, "Application")
        Layout = getattr(layout, "Layout")
        HSplit = getattr(layout, "HSplit")
        Window = getattr(layout, "Window")
        FormattedTextControl = getattr(controls, "FormattedTextControl")
        KeyBindings = getattr(key_binding, "KeyBindings")
    except Exception as e:
        raise RuntimeError(f"prompt_toolkit is required for TUI: {e}")

    header = question.get("header", "Question")
    text = _get_question_text(question)
    options = _get_options(question)
    multiple = question.get("multiple", False)
    allow_custom = question.get("custom", True)

    labels = [opt.get("label", "") for opt in options if opt.get("label")]
    if not labels:
        raise RuntimeError("Question options missing")
    choices = [(label, label) for label in labels]
    if allow_custom:
        choices.append(("__custom__", "Custom"))

    if not choices:
        raise RuntimeError("Question options missing")

    index = 0
    selected_indices: set[int] = set()

    def _render() -> str:
        header_line = f"Question: {text}" if text else header
        width = 80

        lines = []
        lines.extend(textwrap.wrap(header_line, width=width))

        for i, (_, label) in enumerate(choices):
            cursor = ">" if i == index else " "
            if multiple:
                prefix = f"{cursor} [x] " if i in selected_indices else f"{cursor} [ ] "
            else:
                prefix = f"{cursor} "
            wrapped = textwrap.wrap(label, width=width - len(prefix)) or [""]
            for j, part in enumerate(wrapped):
                if j == 0:
                    lines.append(prefix + part)
                else:
                    lines.append(" " * len(prefix) + part)

        footer = "↑/↓ move  Enter confirm" + ("  Space toggle" if multiple else "")
        lines.extend(textwrap.wrap(footer, width=width))

        max_len = max(len(line) for line in lines) if lines else 0
        top = "-" * max_len
        bottom = top
        return "\n".join([top] + lines + [bottom])

    kb = KeyBindings()

    @kb.add("up")
    def _up(event):
        nonlocal index
        index = (index - 1) % len(choices)
        event.app.invalidate()

    @kb.add("down")
    def _down(event):
        nonlocal index
        index = (index + 1) % len(choices)
        event.app.invalidate()

    if multiple:

        @kb.add(" ")
        def _toggle(event):
            if index in selected_indices:
                selected_indices.remove(index)
            else:
                selected_indices.add(index)
            event.app.invalidate()

    @kb.add("enter")
    def _enter(event):
        if multiple:
            event.app.exit(result=[choices[i][0] for i in sorted(selected_indices)])
        else:
            event.app.exit(result=[choices[index][0]])

    @kb.add("c-c")
    def _cancel(event):
        event.app.exit(result=None)

    control = FormattedTextControl(text=lambda: _render())
    app = Application(
        layout=Layout(HSplit([Window(content=control)])),
        key_bindings=kb,
        full_screen=False,
    )

    result = app.run()
    if result is None:
        raise RuntimeError("User cancelled")
    selected = list(result)

    if "__custom__" in selected:
        selected = [s for s in selected if s != "__custom__"]
        custom_text = input("Custom answer: ").strip()
        if custom_text:
            selected.append(custom_text)

    return [str(item) for item in selected if str(item).strip()]


async def tui_handler(prompt: str, question: dict[str, Any]) -> list[str]:
    return await asyncio.to_thread(_tui_sync, question)


async def question(
    questions: list[dict[str, Any]],
    ctx,
    custom: bool = True,
):
    """
    Ask user questions and return answers.

    Args:
        questions: List of question objects
        ctx: Execution context
        custom: Allow custom answers (default True)
    """
    try:
        await ctx.ask(
            PermissionRequest(
                permission=PermissionType.QUESTION,
                patterns=["question"],
                metadata={"questions": questions},
                description="Ask user questions",
            )
        )

        answers = []
        for idx, q in enumerate(questions):
            allow_custom = q.get("custom", custom)
            options = _get_options(q)
            if not options:
                return ToolResult.from_error(
                    "Question options missing",
                    "Each question must include options with label/description",
                    question_index=idx,
                )
            prompt = _format_question_prompt(q, allow_custom)
            raw = await ctx.get_user_input(prompt, q)
            if isinstance(raw, list):
                selection = [str(item) for item in raw]
            elif isinstance(raw, dict) and "selected" in raw:
                selection = [str(item) for item in raw.get("selected", [])]
            else:
                selection = _parse_selection(
                    str(raw),
                    options,
                    q.get("multiple", False),
                    allow_custom,
                )

            if not allow_custom:
                allowed = {opt.get("label", "") for opt in options}
                for item in selection:
                    if item not in allowed:
                        raise ValueError(f"Custom answers not allowed: {item}")
            answers.append({"question_index": idx, "selected": selection})

        output_lines = []
        for ans in answers:
            selected = ", ".join(ans["selected"]) if ans["selected"] else "(none)"
            output_lines.append(f"Q{ans['question_index'] + 1}: {selected}")
        output = "\n".join(output_lines) if output_lines else "(no answers)"
        truncated, trunc_meta = ctx.truncate_output(output, context="question answers")

        return ToolResult.success(
            "Questions answered",
            truncated,
            answers=answers,
            **trunc_meta,
        )

    except PermissionDeniedError as e:
        return ToolResult.from_error("Permission denied", str(e))
    except Exception as e:
        return ToolResult.from_error(
            "Question failed", str(e), error_type=type(e).__name__
        )
