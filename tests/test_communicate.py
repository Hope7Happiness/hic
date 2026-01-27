"""
Test agent peer-to-peer communication.

Scenario:
- Parent has two children: AgentA and AgentB
- AgentA knows the first half of a hash: "abc123"
- AgentB knows the second half: "def456"
- They must communicate to assemble the full hash: "abc123def456"
- Both agents must report the complete hash to the parent

This tests:
1. Peer-to-peer messaging between sibling agents
2. Non-blocking message sending
3. Message queuing when recipient is busy
4. Automatic wake-up when recipient is in wait state
5. Deadlock avoidance through async message passing
"""

import asyncio
import pytest
import os
import json
from pathlib import Path
from typing import Optional
from agent.agent import Agent
from agent.tool import Tool
from agent.llm import DeepSeekLLM
from agent.llm import CopilotLLM
from agent.async_logger import init_logger, close_logger
from agent.config import get_deepseek_api_key
from agent.llm import LLM


HASH_PART_A = "aa491b"
HASH_PART_B = "d0273f"
FULL_HASH = HASH_PART_A + HASH_PART_B
AGENT_A_TASK = "与AgentB通信获取后半部分，拼接完整哈希码后汇报给我"
AGENT_B_TASK = "与AgentA通信获取前半部分，拼接完整哈希码后汇报给我"
HASH_ARGS_ADD_A = json.dumps({"action": "add", "part": HASH_PART_A}, ensure_ascii=False)
HASH_ARGS_ADD_B = json.dumps({"action": "add", "part": HASH_PART_B}, ensure_ascii=False)
HASH_ARGS_GET = json.dumps({"action": "get"}, ensure_ascii=False)


class ScriptedLLM(LLM):
    """Deterministic LLM used for tests to avoid external API calls."""

    def __init__(self, responses, name="ScriptedLLM"):
        super().__init__()
        self._responses = responses
        self._index = 0
        self._name = name

    def reset_history(self):  # type: ignore[override]
        super().reset_history()
        self._index = 0

    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:  # type: ignore[override]
        if not self.history and system_prompt:
            self.history.append({"role": "system", "content": system_prompt})

        self.history.append({"role": "user", "content": prompt})

        if self._index >= len(self._responses):
            raise RuntimeError(
                f"{self._name} ran out of scripted responses at call {self._index + 1}"
            )

        response = self._responses[self._index]
        self._index += 1

        self.history.append({"role": "assistant", "content": response})
        return response


def create_scripted_parent_llm() -> ScriptedLLM:
    responses = [
        f"""Thought: 我需要同时启动两个子Agent来合作
Action: launch_subagents
Agents: ["AgentA", "AgentB"]
Tasks: ["{AGENT_A_TASK}", "{AGENT_B_TASK}"]""",
        """Thought: 子Agent已经启动，我应该等待他们的结果
Action: wait""",
        """Thought: 已经收到一个子Agent的结果，还需要等待另一个
Action: wait""",
        f"""Thought: 两个子Agent都完成并提供了完整哈希码
Action: finish
Content: AgentA和AgentB都确认完整哈希码为{FULL_HASH}""",
    ]
    return ScriptedLLM(responses, name="ParentAgentLLM")


def create_scripted_agent_a_llm() -> ScriptedLLM:
    responses = [
        f"""Thought: 首先联系AgentB获取缺失的后半部分
Action: send_message
Recipient: AgentB
Message: 我有前半部分{HASH_PART_A}，请告诉我你的后半部分""",
        """Thought: 请求已发送，需要等待AgentB的回复
Action: wait""",
        f"""Thought: AgentB提供了后半部分，我需要保存下来
Action: tool
Tool: manage_hash
Arguments: {HASH_ARGS_ADD_B}""",
        """Thought: 现在获取完整哈希码以便共享
Action: tool
Tool: manage_hash
Arguments: {HASH_ARGS_GET}""",
        f"""Thought: 我必须把完整哈希码告诉AgentB
Action: send_message
Recipient: AgentB
Message: 完整哈希码是{FULL_HASH}，请确认你也保存了""",
        """Thought: 等待AgentB确认他也拥有完整哈希码
Action: wait""",
        f"""Thought: AgentB已经确认，现在可以向父Agent汇报
Action: finish
Content: 我们双方都掌握了完整哈希码{FULL_HASH}""",
    ]
    return ScriptedLLM(responses, name="AgentALLM")


def create_scripted_agent_b_llm() -> ScriptedLLM:
    responses = [
        """Thought: 必须先等待AgentA主动联系
Action: wait""",
        f"""Thought: AgentA来询问后半部分，我需要回复
Action: send_message
Recipient: AgentA
Message: 我有后半部分{HASH_PART_B}，你有前半部分吗？""",
        """Thought: 我现在等待AgentA给出完整哈希码或前半部分
Action: wait""",
        f"""Thought: AgentA提供了缺失部分，我要保存下来
Action: tool
Tool: manage_hash
Arguments: {HASH_ARGS_ADD_A}""",
        """Thought: 获取完整哈希码以确认信息
Action: tool
Tool: manage_hash
Arguments: {HASH_ARGS_GET}""",
        f"""Thought: 我需要告诉AgentA我也拥有完整哈希码
Action: send_message
Recipient: AgentA
Message: 我现在也有完整哈希码{FULL_HASH}，合作完成""",
        f"""Thought: 双方确认完毕，可以向父Agent报告
Action: finish
Content: 已和AgentA互相确认，完整哈希码是{FULL_HASH}""",
    ]
    return ScriptedLLM(responses, name="AgentBLLM")


def create_hash_storage_tool(initial_part: str) -> Tool:
    """
    Create a tool that stores and retrieves hash parts.

    Each agent starts with one part and can store additional parts.
    """
    storage = {"parts": [initial_part]}

    def manage_hash(action: str, part: str = "") -> str:
        """
        Manage hash parts.

        Args:
            action: "get" to retrieve all parts, "add" to add a new part
            part: The hash part to add (only for action="add")

        Returns:
            Current hash parts or confirmation message
        """
        if action == "get":
            all_parts = "".join(storage["parts"])
            return f"Complete hash: {all_parts}"
        elif action == "add":
            if part and part not in storage["parts"]:
                storage["parts"].append(part)
                all_parts = "".join(storage["parts"])
                return f"✅ Added part: {part}. Complete hash: {all_parts}"
            return "❌ Part is empty or already exists"
        return "❌ Invalid action. Use 'get' or 'add'"

    return Tool(manage_hash)


def create_agent_a(llm) -> Agent:
    """
    Create Agent A - knows first half of hash.

    Task: Communicate with AgentB to get second half, then report full hash to parent.
    """
    hash_tool = create_hash_storage_tool(HASH_PART_A)

    system_prompt = f"""你是AgentA，你知道一个哈希码的前半部分。

你的初始知识：
- 哈希码前半部分: {HASH_PART_A}（存储在 manage_hash 工具中）

你的任务：
1. 向AgentB发送消息，告诉他你有前半部分{HASH_PART_A}，询问他的后半部分
2. 使用 wait 等待AgentB的回复
3. 收到AgentB的后半部分后，使用 manage_hash(action="add", part="...") 保存
4. 使用 manage_hash(action="get") 获取完整哈希码，并将完整哈希码明确发送给AgentB，确保对方也知道
5. 再次使用 wait 等待AgentB确认他也得到了完整哈希码
6. 收到AgentB的确认后，再使用 finish 向父Agent汇报最终结果

通信流程：
- Action: send_message, Recipient: AgentB, Message: "我有前半部分{HASH_PART_A}，请告诉我你的后半部分"
- Action: wait（等待AgentB回复）
- 收到回复后，parse出后半部分，使用 manage_hash 保存
- Action: send_message, Recipient: AgentB, Message: "完整哈希码是{FULL_HASH}"（务必给出完整哈希码，让AgentB可以保存）
- Action: wait（等待AgentB的确认消息）
- Action: finish, Content: 包含完整哈希码

重要：
- 你可以与 AgentB 通信
- 必须使用 wait 等待AgentB的回复与确认
- 你必须把完整哈希码告诉AgentB，且在收到AgentB确认后才能 finish
- 最后的 finish Content 必须包含完整哈希码 {FULL_HASH}
"""

    return Agent(
        llm=llm,
        tools=[hash_tool],
        allowed_peers=["AgentB"],
        name="AgentA",
        system_prompt=system_prompt,
        max_iterations=15,
    )


def create_agent_b(llm) -> Agent:
    """
    Create Agent B - knows second half of hash.

    Task: Wait for AgentA's message, reply with second half, then report full hash to parent.
    """
    hash_tool = create_hash_storage_tool(HASH_PART_B)

    system_prompt = f"""你是AgentB，你知道一个哈希码的后半部分。

你的初始知识：
- 哈希码后半部分: {HASH_PART_B}（存储在 manage_hash 工具中）

你的任务：
1. 先使用 wait 等待AgentA的消息
2. 当AgentA询问你后半部分时，回复他：我有后半部分{HASH_PART_B}，你有前半部分吗？
3. 再次使用 wait，直到AgentA明确告诉你前半部分或完整哈希码
4. 收到信息后，使用 manage_hash(action="add", part="...") 保存前半部分，并使用 manage_hash(action="get") 获取完整哈希码
5. 为了确保双方都拥有完整哈希码，必须再向AgentA发送一条确认消息，包含完整哈希码（例如："我现在也有完整哈希码{FULL_HASH}"）
6. 发送确认消息后，使用 finish 向父Agent汇报最终结果

通信流程：
- Action: wait（等待AgentA的消息）
- 收到消息后，Action: send_message, Recipient: AgentA, Message: "我有后半部分{HASH_PART_B}，你有前半部分吗？"
- Action: wait（等待AgentA再次回复）
- 收到前半部分或完整哈希码后，使用 manage_hash 保存，并使用 manage_hash(action="get") 确认完整哈希码
- Action: send_message, Recipient: AgentA, Message: "我现在也有完整哈希码{FULL_HASH}"（必须发送完整哈希码给对方）
- Action: finish, Content: 包含完整哈希码

重要：
- 你可以与 AgentA 通信
- 必须先 wait 等待AgentA主动联系你
- 你必须把完整哈希码告诉AgentA，并确认双方都拥有完整哈希码后才能 finish
- 最后的 finish Content 必须包含完整哈希码 {FULL_HASH}
"""

    return Agent(
        llm=llm,
        tools=[hash_tool],
        allowed_peers=["AgentA"],
        name="AgentB",
        system_prompt=system_prompt,
        max_iterations=15,
    )


def create_parent_agent(llm, agent_a, agent_b) -> Agent:
    """
    Create parent agent that coordinates A and B.

    Parent should infer that A and B need to communicate to complete the task.
    """
    system_prompt = """你是一个协调Agent，负责管理两个子Agent：AgentA和AgentB。

背景信息：
- AgentA提前已经知道了一个哈希码的前半部分
- AgentB提前已经知道了后半部分
- 你的任务是让两个子Agent合作，拼接出完整的哈希码并汇报给你

你的策略：
1. 同时启动 AgentA 和 AgentB（使用 launch_subagents）
   - AgentA的任务："与AgentB通信获取后半部分，拼接完整哈希码后汇报给我"
   - AgentB的任务："与AgentA通信获取前半部分，拼接完整哈希码后汇报给我"
2. 使用 wait 等待两个子Agent完成
3. 当两个子Agent都汇报了完整哈希码后，使用 finish 总结结果

重要：
- 不要告诉他们具体怎么做，让他们自己通信
- 必须等两个子Agent都完成并汇报
- 最后的总结应该包含两个Agent汇报的完整哈希码
"""

    return Agent(
        llm=llm,
        subagents={
            "AgentA": agent_a,
            "AgentB": agent_b,
        },
        name="ParentAgent",
        system_prompt=system_prompt,
        max_iterations=20,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("llm_type", ["deepseek", "copilot"])  # Default to real LLM flow
async def test_agent_communication(llm_type):
    """
    Test that two agents can communicate to assemble a complete hash.

    Success criteria:
    - Both agents finish successfully
    - Both agents' final responses contain the complete hash
    - No deadlocks occur
    """
    # Create LLM
    use_scripted = os.environ.get("USE_SCRIPTED_LLM") == "1"

    if not use_scripted:
        if llm_type == "deepseek":
            api_key = get_deepseek_api_key()
            if not api_key:
                pytest.skip("DEEPSEEK_API_KEY not set")
            llm_parent = DeepSeekLLM(api_key=api_key, model="deepseek-chat")
            llm_a = DeepSeekLLM(api_key=api_key, model="deepseek-chat")
            llm_b = DeepSeekLLM(api_key=api_key, model="deepseek-chat")
        elif llm_type == "copilot":
            llm_parent = CopilotLLM(model="claude-haiku-4.5", temperature=0.7)
            llm_a = CopilotLLM(model="claude-haiku-4.5", temperature=0.7)
            llm_b = CopilotLLM(model="claude-haiku-4.5", temperature=0.7)
        else:
            raise ValueError(f"Unsupported real LLM type: {llm_type}")
    else:
        llm_parent = create_scripted_parent_llm()
        llm_a = create_scripted_agent_a_llm()
        llm_b = create_scripted_agent_b_llm()

    # Initialize logger
    logger = await init_logger(log_dir="logs", console_output=True)

    try:
        # Create agents with independent LLM instances
        agent_a = create_agent_a(llm_a)
        agent_b = create_agent_b(llm_b)
        parent = create_parent_agent(llm_parent, agent_a, agent_b)

        # Run parent agent
        task = "请协调AgentA和AgentB合作，拼接出完整的哈希码"
        result = await parent._run_async(task)

        # Assertions
        assert result.success, f"Parent agent failed: {result.content}"

        # Check that the parent received the full hash from both agents
        # Look for the full hash in the result
        assert FULL_HASH in result.content, (
            f"Complete hash {FULL_HASH} not found in parent result: {result.content}"
        )

        # Check log files for AgentA and AgentB completion
        log_dir = Path("logs")

        # Find most recent log files
        agent_a_logs = sorted(
            log_dir.glob("AgentA_*.log"), key=os.path.getmtime, reverse=True
        )
        agent_b_logs = sorted(
            log_dir.glob("AgentB_*.log"), key=os.path.getmtime, reverse=True
        )

        assert agent_a_logs, "AgentA log file not found"
        assert agent_b_logs, "AgentB log file not found"

        # Read last log content
        with open(agent_a_logs[0], "r") as f:
            agent_a_content = f.read()
            assert FULL_HASH in agent_a_content, (
                f"AgentA did not report complete hash {FULL_HASH}"
            )

        with open(agent_b_logs[0], "r") as f:
            agent_b_content = f.read()
            assert FULL_HASH in agent_b_content, (
                f"AgentB did not report complete hash {FULL_HASH}"
            )

        print(
            f"\n✅ Test passed! Both agents successfully communicated and assembled hash: {FULL_HASH}"
        )

    finally:
        # Close logger
        await close_logger()


if __name__ == "__main__":
    # Run test directly
    asyncio.run(test_agent_communication("deepseek"))
