"""
Simple example: say hello to Codex (via CodexLLM) and print the reply.

Usage:
    # Make sure Codex CLI works first:
    #   codex login
    #
    # Then run:
    #   python examples/codex_hello.py
"""

from agent.llm import CodexLLM


def main():
    # Create Codex LLM (uses `codex exec --json` under the hood)
    llm = CodexLLM(model="gpt-5.2")

    prompt = "请用一句简短、自然的中文向我打个招呼。"

    reply = llm.chat(prompt)

    print("=" * 60)
    print("Codex Hello Example")
    print("=" * 60)
    print(f"Prompt: {prompt}")
    print(f"Codex reply: {reply}")
    print("=" * 60)


if __name__ == "__main__":
    main()


