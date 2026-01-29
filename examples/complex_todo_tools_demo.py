"""
Complex demo that combines multiple tools in one workflow.

Scenario:
- Seed a temporary workspace with a Python app containing TODOs + priorities
- Agent discovers TODOs, writes a todo list, implements them, and runs the app
"""

import asyncio
import tempfile
from pathlib import Path

from agent import Agent, Tool
from agent.llm import DeepSeekLLM
from agent.tools import bash, grep, read, write, edit, todowrite, todoread
from agent.config import load_env, get_deepseek_api_key


def _seed_app(workdir: Path) -> None:
    app_file = workdir / "app.py"
    app_file.write_text(
        """
import json

DATA = [
  {"name": "Pencil", "price": 0.5, "tags": ["stationery", "writing"]},
  {"name": "Notebook", "price": 2.75, "tags": ["stationery", "paper"]},
  {"name": "Eraser", "tags": ["stationery", "rubber", "stationery"]},
  {"name": "Marker", "price": -1.0, "tags": ["writing"]},
  {"name": "Desk Lamp", "price": 12.0, "tags": []},
  {"name": "Stapler"}
]


def load_items(raw: str):
    # TODO(high): parse JSON; return list of dicts; raise ValueError on invalid input
    pass


def normalize_item(item: dict):
    # TODO(medium): ensure name string, price >= 0 float default 0, tags list of strings
    # - tags should be unique, sorted alphabetically
    pass


def render_report(items):
    # TODO(low): render multiline report:
    # - Title line: "Inventory Report"
    # - "Total items: N"
    # - "Average price: $X.XX"
    # - Bullet list sorted by name: "- Name ($price) [tag1, tag2]"
    pass


def main():
    items = load_items(DATA)
    normalized = [normalize_item(item) for item in items]
    print(render_report(normalized))


if __name__ == "__main__":
    main()
""".lstrip()
    )


async def main():
    load_env()
    api_key = get_deepseek_api_key()
    if not api_key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY")

    llm = DeepSeekLLM(api_key=api_key, timeout=30, max_retries=2)

    tools = [
        Tool(read),
        Tool(write),
        Tool(edit),
        Tool(grep),
        Tool(todowrite),
        Tool(todoread),
        Tool(bash),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        _seed_app(workdir)

        agent = Agent(llm=llm, tools=tools, working_directory=str(workdir))

        task = (
            "You are working in a temporary Python project. "
            "First, use grep to find TODO markers and build a todo list using todowrite. "
            "Then implement all TODOs in app.py using read/edit. "
            "After implementing, run 'python app.py' using bash and include the output. "
            "Finally, use todoread to show the final todo list."
        )

        result = await agent._run_async(task)
        print(result.content)


if __name__ == "__main__":
    asyncio.run(main())
