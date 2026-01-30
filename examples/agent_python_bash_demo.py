"""
Demo: agent with bash tool that allows python/python3.
"""

import asyncio

from agent import Agent, Tool
from agent.tools import bash, DEFAULT_SAFE_COMMANDS
from agent.llm import DeepSeekLLM
from agent.config import load_env, get_deepseek_api_key


async def bash_with_python(
    command: str,
    ctx,
    timeout: int = 120,
    working_dir: str | None = None,
    allow_dangerous: bool = False,
):
    allowed = set(DEFAULT_SAFE_COMMANDS) | {"python", "python3"}
    return await bash(
        command=command,
        ctx=ctx,
        timeout=timeout,
        working_dir=working_dir,
        allowed_commands=allowed,
        allow_dangerous=allow_dangerous,
    )


bash_with_python.__name__ = "bash"
bash_with_python.__doc__ = (bash.__doc__ or "") + "\n\nAllows python/python3 commands."


async def main():
    load_env()
    api_key = get_deepseek_api_key()
    if not api_key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY")

    llm = DeepSeekLLM(api_key=api_key)
    tools = [Tool(bash_with_python)]

    agent = Agent(llm=llm, tools=tools, working_directory=".")

    task = 'Use the bash tool to run: python3 -c "print(1+1)". Report the output.'

    result = await agent._run_async(task)
    print(result.content)


if __name__ == "__main__":
    asyncio.run(main())
