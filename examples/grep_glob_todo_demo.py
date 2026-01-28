"""
Real agent demo for grep, glob, and todo tools.

Scenario:
- Build a small docs workspace
- Use an agent (DeepSeekLLM) to discover files with glob
- Search for TODO markers with grep
- Write a todo list and read it back
"""

import asyncio
import tempfile
from pathlib import Path

from agent import Agent, Tool
from agent.llm import DeepSeekLLM
from agent.tools import grep, glob, todowrite, todoread
from agent.config import load_env, get_deepseek_api_key


def _seed_docs(workdir: Path) -> None:
    docs_dir = workdir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "overview.md").write_text(
        "# Overview\n\nTODO: add architecture diagram\n"
    )
    (docs_dir / "setup.md").write_text(
        "# Setup\n\nInstall steps.\n\nTODO: add Windows instructions\n"
    )
    (docs_dir / "notes.txt").write_text("misc notes\n")


async def main():
    load_env()
    api_key = get_deepseek_api_key()
    if not api_key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY")
    llm = DeepSeekLLM(api_key=api_key)

    tools = [Tool(glob), Tool(grep), Tool(todowrite), Tool(todoread)]

    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        _seed_docs(workdir)

        agent = Agent(llm=llm, tools=tools, working_directory=str(workdir))

        task = (
            "You are working in a small docs workspace. "
            "Use glob to list markdown files under docs/. "
            "Use grep to find TODO markers in docs (only .md files). "
            "Then create a todo list with two items: review TODOs (high priority, pending) "
            "and verify docs completeness (medium priority, pending). "
            "Finally, read the todo list and summarize what you did."
        )

        result = await agent._run_async(task)
        print(result.content)


if __name__ == "__main__":
    asyncio.run(main())
