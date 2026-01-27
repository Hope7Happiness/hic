"""Demonstration of read/write/edit tools in a safe, isolated working dir.

This example does NOT touch repository files. It operates in a temporary
directory, creates dummy files, reads them with pagination, and edits them.
"""

import asyncio
import tempfile
from pathlib import Path

from agent import Agent, Tool
from agent.llm import DeepSeekLLM
from agent.tools import read, write, edit
from agent.config import load_env, get_deepseek_api_key

async def main():
    llm = DeepSeekLLM(api_key=get_deepseek_api_key())

    # Create agent with default tools plus explicit read/write/edit to be clear
    tools = [Tool(read), Tool(write), Tool(edit)]

    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)

        agent = Agent(llm=llm, tools=tools, working_directory=str(workdir))

        # Task: create notes, read first line, edit it, and show result
        task = (
            "Create notes.md with two lines: 'First line' and 'Second line'. "
            "Read only the first line. Then change 'First line' to 'Updated heading'. "
            "Also create script.py with a stub hello() function that returns 'hi'. "
            "Finally, read both files to confirm changes."
        )

        result = await agent._run_async(task)  # using internal for demonstration
        print(result.content)


if __name__ == "__main__":
    asyncio.run(main())
