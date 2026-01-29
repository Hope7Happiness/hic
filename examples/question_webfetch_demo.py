"""
Demo for question + webfetch tools.
"""

import asyncio

from agent import Agent, Tool
from agent.tools import question, webfetch
from agent.tools.question import tui_handler
from agent.llm import DeepSeekLLM
from agent.config import load_env, get_deepseek_api_key


async def main():
    load_env()
    api_key = get_deepseek_api_key()
    if not api_key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY")

    llm = DeepSeekLLM(api_key=api_key)
    tools = [Tool(question), Tool(webfetch)]

    agent = Agent(llm=llm, tools=tools, working_directory=".")
    agent.context.set_user_input_handler(tui_handler)

    task = (
        "Ask me which format to fetch (markdown/text/html), "
        "then fetch https://kaiming.me with webfetch and show a short summary."
    )

    result = await agent._run_async(task)
    print(result.content)


if __name__ == "__main__":
    asyncio.run(main())
