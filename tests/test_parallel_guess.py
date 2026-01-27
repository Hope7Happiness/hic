"""
Test parallel guessing challenge with peer messaging and ranking validation.

Scenario:
- Parent agent launches three questioner/answerer pairs simultaneously
- Each questioner must binary-search (by asking greater/smaller/equal questions) to guess a hidden number
- Answerers reply truthfully with "大于/小于/相等" style hints
- Parent must wait for all questioners to finish and then report the finish order
- Test asserts the reported ranking matches the real completion order extracted from logs
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Any, TypedDict

import pytest

from agent.agent import Agent
from agent.llm import LLM
from agent.async_logger import init_logger, close_logger
from agent.tool import Tool
from agent.tool import Tool
from agent.llm import DeepSeekLLM
from agent.llm import CopilotLLM
from agent.config import get_deepseek_api_key


class AnswerStep(TypedDict):
    reply: str
    final: bool


class PairConfig(TypedDict):
    questioner: str
    answerer: str
    number: int
    guesses: List[int]
    answer_responses: List[AnswerStep]


QUESTION_PAIRS: List[PairConfig] = [
    {
        "questioner": "Questioner1",
        "answerer": "Answerer1",
        "number": 2,
        "guesses": [5, 2],
        "answer_responses": [
            {"reply": "真实数字比5小", "final": False},
            {"reply": "真实数字刚好等于2", "final": True},
        ],
    },
    {
        "questioner": "Questioner2",
        "answerer": "Answerer2",
        "number": 6,
        "guesses": [4, 7, 6],
        "answer_responses": [
            {"reply": "真实数字比4大", "final": False},
            {"reply": "真实数字比7小", "final": False},
            {"reply": "真实数字刚好等于6", "final": True},
        ],
    },
    {
        "questioner": "Questioner3",
        "answerer": "Answerer3",
        "number": 9,
        "guesses": [2, 6, 8, 9],
        "answer_responses": [
            {"reply": "真实数字比2大", "final": False},
            {"reply": "真实数字比6大", "final": False},
            {"reply": "真实数字比8大", "final": False},
            {"reply": "真实数字刚好等于9", "final": True},
        ],
    },
]

QUESTIONER_NAMES = [pair["questioner"] for pair in QUESTION_PAIRS]


def make_llm(llm_type: str) -> LLM:
    if llm_type == "deepseek":
        api_key = get_deepseek_api_key()
        if not api_key:
            pytest.skip("DEEPSEEK_API_KEY not set")
        return DeepSeekLLM(api_key=api_key, model="deepseek-chat")
    if llm_type == "copilot":
        return CopilotLLM(model="claude-haiku-4.5", temperature=0.2)
    raise ValueError(f"Unknown llm_type: {llm_type}")


class SequencedLLM(LLM):
    """Simple deterministic LLM that replays pre-defined responses."""

    def __init__(self, responses: List[str], name: str):
        super().__init__()
        self._responses = responses
        self._index = 0
        self._name = name

    def reset_history(self):  # type: ignore[override]
        super().reset_history()
        self._index = 0

    def chat(self, prompt: str, system_prompt: str | None = None) -> str:  # type: ignore[override]
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


class RankingLLM(LLM):
    """Parent LLM that tracks questioner completion order and reports ranking."""

    def __init__(self, launch_plan: List[Tuple[str, str]], tracked_agents: List[str]):
        super().__init__()
        self.launch_plan = launch_plan
        self.tracked_agents = tracked_agents
        self.stage = "launch"
        self.finish_order: List[str] = []

    def reset_history(self):  # type: ignore[override]
        super().reset_history()
        self.stage = "launch"
        self.finish_order = []

    def chat(self, prompt: str, system_prompt: str | None = None) -> str:  # type: ignore[override]
        if not self.history and system_prompt:
            self.history.append({"role": "system", "content": system_prompt})

        self.history.append({"role": "user", "content": prompt})

        if self.stage == "launch":
            agents = ", ".join(f'"{name}"' for name, _ in self.launch_plan)
            tasks = ", ".join(f'"{task}"' for _, task in self.launch_plan)
            response = (
                "Thought: 我需要同时启动所有问答代理，让他们并行工作\n"
                "Action: launch_subagents\n"
                f"Agents: [{agents}]\n"
                f"Tasks: [{tasks}]"
            )
            self.stage = "wait"
            self.history.append({"role": "assistant", "content": response})
            return response

        if self.stage == "wait":
            self.stage = "tracking"
            response = "Thought: 子Agent已经启动，我需要等待他们完成\nAction: wait"
            self.history.append({"role": "assistant", "content": response})
            return response

        # tracking completions
        match = re.search(r"agent '([^']+)'", prompt)
        if match:
            agent_name = match.group(1)
            if (
                agent_name in self.tracked_agents
                and agent_name not in self.finish_order
            ):
                self.finish_order.append(agent_name)

        if len(self.finish_order) < len(self.tracked_agents):
            response = "Thought: 仍有问答代理在进行，需要继续等待\nAction: wait"
            self.history.append({"role": "assistant", "content": response})
            return response

        ranking = "、".join(
            f"第{idx + 1}名: {name}" for idx, name in enumerate(self.finish_order)
        )
        response = (
            f"Thought: 所有问答代理都已完成，我可以总结结果\n"
            f"Action: finish\nContent: 问题解决完成，排名为：{ranking}"
        )
        self.history.append({"role": "assistant", "content": response})
        return response


def build_question_responses(answer_name: str, guesses: List[int]) -> List[str]:
    responses: List[str] = []
    for guess in guesses:
        responses.append(
            "Thought: 我需要询问范围来缩小答案\n"
            "Action: send_message\n"
            f"Recipient: {answer_name}\n"
            f"Message: 我选择数字{guess}，真实数字比它大、小，还是相等？"
        )
        responses.append("Thought: 等待答题Agent反馈\nAction: wait")
    final_guess = guesses[-1]
    responses.append(
        "Thought: 已经得到足够信息，可以报告答案\n"
        f"Action: finish\nContent: 我确定目标数字是{final_guess}，任务完成"
    )
    return responses


def build_answer_responses(question_name: str, replies: List[AnswerStep]) -> List[str]:
    responses: List[str] = ["Thought: 等待提问\nAction: wait"]
    for item in replies:
        reply_text = item["reply"]  # type: ignore[index]
        is_final = bool(item["final"])
        responses.append(
            "Thought: 收到询问，需要如实回答范围\n"
            "Action: send_message\n"
            f"Recipient: {question_name}\n"
            f"Message: {reply_text}"
        )
        if is_final:
            responses.append(
                "Thought: 已经确认最终答案，可以收尾\n"
                "Action: finish\nContent: 所有问题都已如实回答，任务完成"
            )
        else:
            responses.append("Thought: 继续等待下一次提问\nAction: wait")
    return responses


# def create_sleep_tool() -> Tool:
#     def sleep_ms(ms: int) -> str:
#         time.sleep(ms / 1000.0)
#         return f"slept {ms}ms"

#     return Tool(sleep_ms)


def create_question_agent(pair: PairConfig, llm: LLM | None, delay_ms: int) -> Agent:
    questioner = pair["questioner"]
    answerer = pair["answerer"]
    guesses = pair["guesses"]

    if llm is None:
        responses = build_question_responses(answerer, guesses)
        llm = SequencedLLM(responses, name=f"LLM_{questioner}")
        tools: List[Tool] = []
        system_prompt = (
            f"你是{questioner}，你的任务是通过向{answerer}提问，判定一个1-10之间的整数。\n"
            "允许的行为：\n"
            "1. 使用 send_message 询问“真实数字比X大/小/等于？”\n"
            f"2. 使用 wait 等待{answerer}的回答\n"
            "3. 当你确定答案后，使用 finish 并在内容中写出最终数字\n"
            "请务必在接收到答复后再继续下一步操作。"
        )
    else:
        # tools = [create_sleep_tool()]
        tools = []
        system_prompt = (
            f"你是{questioner}，你要猜一个 1-10 的整数。你只能与 {answerer} 通信。\n"
            "规则（必须严格遵守，否则测试失败）：\n"
            "- 每轮只能输出一个 Action（不要在同一次输出里写多个 Action）\n"
            "- send_message 的 Message 必须是单行文本，且不能包含 'Action:'/'Tool:'/'Arguments:' 这些关键词\n"
            "- 你可以问两种格式之一：\n"
            "  A) 真实数字比X大/小/等于？\n"
            "  B) 你的数字是X吗？\n"
            f"- 发送后必须 wait 等待 {answerer} 的回复，再决定下一次的X\n"
            # "- 你必须采用二分/缩小区间策略，直到收到“刚好等于X”\n"
            # f"- 为了避免同时结束造成并列：开始前先调用 tool sleep_ms(ms={delay_ms * 2})；并且每次收到回复后都必须调用 tool sleep_ms(ms={delay_ms})\n"
            "- 一旦确认等于某个X，立刻 finish，并在 Content 中包含：我确定目标数字是<数字>\n"
            "输出格式必须严格遵循 Action/Tool/Arguments 规范。"
        )

    return Agent(
        llm=llm,
        tools=tools,
        allowed_peers=[answerer],
        name=questioner,
        system_prompt=system_prompt,
        max_iterations=30,
    )


def create_answer_agent(pair: PairConfig, llm: LLM | None) -> Agent:
    questioner = pair["questioner"]
    answerer = pair["answerer"]
    number = pair["number"]
    replies = pair["answer_responses"]

    if llm is None:
        responses = build_answer_responses(questioner, replies)
        llm = SequencedLLM(responses, name=f"LLM_{answerer}")
        system_prompt = (
            f"你是{answerer}，知道父Agent分配给你的数字：{number}。\n"
            f"等待{questioner}的提问，只能回答“比X大”“比X小”或“等于X”，并保持诚实。"
        )
    else:
        system_prompt = (
            f"你是{answerer}。你的秘密数字 N 是 1-10 的整数。\n"
            "你可能通过两种方式获得 N：\n"
            "1) 父Agent(GuessMaster)发消息：'你的数字是N'\n"
            "2) 任务描述中直接给出 N\n"
            "规则（必须严格遵守，否则测试失败）：\n"
            "- 每轮只能输出一个 Action\n"
            f"- 你只能与 {questioner} 通信（send_message），并且必须诚实\n"
            "- 你需要从提问中提取整数X（无论是 '真实数字比X...' 还是 '你的数字是X吗？'）\n"
            "- 你必须按比较结果回复以下之一：\n"
            "  - 真实数字比X大\n"
            "  - 真实数字比X小\n"
            "  - 真实数字刚好等于X\n"
            "- 当你回复“刚好等于X”后，你可以 finish。\n"
            "建议动作序列：先 wait 等到你明确知道 N，再 wait 等提问 -> send_message 回复 -> 视情况 finish。"
        )

    return Agent(
        llm=llm,
        tools=[],
        allowed_peers=[questioner],
        name=answerer,
        system_prompt=system_prompt,
        max_iterations=50,
    )


def create_parent_agent(
    question_agents: Dict[str, Agent],
    answer_agents: Dict[str, Agent],
    llm: LLM | None,
) -> Agent:
    launch_plan: List[Tuple[str, str]] = []
    for pair in QUESTION_PAIRS:
        qname = pair["questioner"]
        aname = pair["answerer"]
        launch_plan.append((qname, f"与{aname}配对猜测父Agent分配的数字"))
        launch_plan.append((aname, "等待父Agent发送数字并如实回答提问"))

    if llm is None:
        parent_llm: LLM = RankingLLM(launch_plan, QUESTIONER_NAMES)
        system_prompt = (
            "你是父Agent，已经秘密选择了三个1-10的整数，并把它们告诉了各自的答题Agent。\n"
            "你的任务：\n1. 同时启动所有问答Agent\n2. 等待三位提问Agent都完成\n3. 根据完成先后顺序给出排名（第一名、第二名、第三名）并使用 finish 总结"
        )
        allowed_peers: List[str] = []
        max_iterations = 20
    else:
        parent_llm = llm
        allowed_peers = ["Answerer1", "Answerer2", "Answerer3"]
        max_iterations = 80
        system_prompt = (
            "你是父Agent(GuessMaster)。你必须完成并行猜数挑战。\n\n"
            "固定规则（必须严格遵守，否则测试失败）：\n"
            "- 每轮只能输出一个 Action\n"
            "- 你必须选择三个整数：Answerer1=2, Answerer2=6, Answerer3=9（1-10之间）\n"
            "- 你必须启动6个子Agent：Questioner1/2/3 与 Answerer1/2/3\n"
            "- 启动后，你必须连续执行3次 send_message，把数字发给 Answerer1/2/3\n"
            "  Message 形如：你的数字是6\n"
            "- 之后用 wait 等待子Agent完成。\n"
            "- 你只需要对 Questioner1/2/3 的完成顺序排名（Answerer完成顺序不计入）。\n"
            "- 你必须按收到 Questioner 完成消息的顺序给排名，不要用自己的推测。\n"
            "- 最终 finish 的 Content 必须包含：第1名/第2名/第3名，并按完成先后顺序列出 Questioner 名字。"
        )
    subagents = {**question_agents, **answer_agents}
    return Agent(
        llm=parent_llm,
        subagents=subagents,
        tools=[],
        allowed_peers=allowed_peers,
        name="GuessMaster",
        system_prompt=system_prompt,
        max_iterations=max_iterations,
    )


def parse_ranking(content: str) -> List[str]:
    return re.findall(r"Questioner\d", content)


def latest_log_path(agent_name: str) -> Path:
    log_dir = Path("logs")
    candidates = sorted(
        log_dir.glob(f"{agent_name}_*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise AssertionError(f"Log file for {agent_name} not found")
    return candidates[0]


def extract_finish_time(path: Path) -> datetime:
    finish_line = None
    with open(path, "r") as f:
        for line in f:
            if "Finished" in line:
                finish_line = line.strip()
    if not finish_line:
        raise AssertionError(f"No finish line found in {path}")
    timestamp = finish_line.split(" [", 1)[0]
    return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")


def get_actual_finish_order(questioners: List[str]) -> List[str]:
    times = []
    for name in questioners:
        path = latest_log_path(name)
        times.append((extract_finish_time(path), name))
    times.sort()
    return [name for _, name in times]


@pytest.mark.asyncio
@pytest.mark.parametrize("llm_type", ["deepseek"])
async def test_parallel_guessing_challenge(llm_type: str):
    use_scripted = os.environ.get("USE_SCRIPTED_LLM") == "1"
    logger = await init_logger(log_dir="logs", console_output=True)
    try:
        delays = [50, 150, 250]
        question_agents: Dict[str, Agent] = {}
        answer_agents: Dict[str, Agent] = {}

        for idx, pair in enumerate(QUESTION_PAIRS):
            q_llm = None if use_scripted else make_llm(llm_type)
            a_llm = None if use_scripted else make_llm(llm_type)
            question_agents[pair["questioner"]] = create_question_agent(
                pair, q_llm, delays[idx]
            )
            answer_agents[pair["answerer"]] = create_answer_agent(pair, a_llm)

        parent_llm = None if use_scripted else make_llm(llm_type)
        parent = create_parent_agent(question_agents, answer_agents, parent_llm)

        task = "并行agent猜数挑战：请完成三组问答猜数并给出排名"
        result = await parent._run_async(task)

        assert result.success, f"Parent agent failed: {result.content}"
        ranking_from_parent = parse_ranking(result.content)
        actual_order = get_actual_finish_order(QUESTIONER_NAMES)
        assert ranking_from_parent == actual_order, (
            f"Ranking {ranking_from_parent} does not match actual completion order {actual_order}"
        )
    finally:
        await close_logger()
