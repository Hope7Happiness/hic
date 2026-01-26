"""
复杂的三层 Agent 系统示例 - 研究助理系统

这个示例展示了：
1. 三层 Agent 架构：
   - L1 (顶层): ResearchDirector - 研究总监
   - L2 (中层): DataAnalyst, LiteratureResearcher - 数据分析师、文献研究员
   - L3 (底层): DataCollector, DataProcessor, PaperFinder, SummaryGenerator - 数据采集/处理员、论文查找/摘要员

2. 多轮调用：
   - 每个 agent 可以多次调用 tools 和 subagents
   - 父 agent 可以等待子 agent 完成后继续执行

3. 递归调用：
   - DataAnalyst 调用 DataCollector 和 DataProcessor
   - LiteratureResearcher 调用 PaperFinder 和 SummaryGenerator
   - 所有调用都是异步并行执行

架构图：
                    ResearchDirector (L1)
                    /
        DataAnalyst (L2)        LiteratureResearcher (L2)
           /                          /
 DataCollector  DataProcessor   PaperFinder    SummaryGenerator
     (L3)           (L3)            (L3)              (L3)

使用场景：
研究总监接收一个研究任务，将其分解为数据分析和文献研究两部分。
数据分析师负责数据收集和处理，文献研究员负责查找论文和生成摘要。
"""

import asyncio
import time
import json
from typing import Dict, List, Any
from agent.agent import Agent
from agent.llm import DeepSeekLLM
from agent.tool import Tool
from agent.async_logger import init_logger, close_logger
from agent.config import load_env, get_deepseek_api_key


# ============================================================================
# Layer 3 Tools (底层工具) - 实际执行具体任务
# ============================================================================


def fetch_data_from_api(api_name: str, params: str) -> str:
    """
    从指定 API 获取数据

    Args:
        api_name: API 名称 (只能为 "weather_api", "stock_api", "census_api")
        params: API 参数 (JSON 格式字符串)

    Returns:
        API 返回的数据 (JSON 字符串)
    """
    time.sleep(1)  # 模拟 API 调用延迟

    # 模拟不同 API 返回不同数据
    mock_data = {
        "weather_api": {"temperature": 25, "humidity": 60, "condition": "sunny"},
        "stock_api": {"symbol": "AAPL", "price": 178.50, "change": +2.3},
        "census_api": {"population": 1400000000, "growth_rate": 0.5},
    }

    result = mock_data.get(api_name, {"error": "API not found"})
    return json.dumps(result, ensure_ascii=False)


def scrape_website(url: str, selector: str) -> str:
    """
    从网站抓取数据

    Args:
        url: 网站 URL (只能为 "research.com", "data.gov", "arxiv.org")
        selector: CSS 选择器

    Returns:
        抓取到的文本内容
    """
    time.sleep(1.5)  # 模拟网页抓取延迟

    # 模拟抓取结果
    mock_content = {
        "research.com": "Latest research shows AI is transforming healthcare...",
        "data.gov": "Government statistics indicate economic growth of 3.2%...",
        "arxiv.org": "Recent papers on machine learning and neural networks...",
    }

    for domain, content in mock_content.items():
        if domain in url:
            return content

    return "Sample scraped content from " + url


def clean_data(raw_data: str) -> str:
    """
    清洗和预处理原始数据

    Args:
        raw_data: 原始数据 (JSON 或文本)

    Returns:
        清洗后的数据描述
    """
    time.sleep(0.5)

    try:
        data = json.loads(raw_data)
        return f"Cleaned data: {len(data)} fields processed, normalized, and validated"
    except:
        return f"Cleaned text data: {len(raw_data)} characters, removed duplicates and invalid entries"


def transform_data(clean_data_desc: str, format: str) -> str:
    """
    转换数据格式

    Args:
        clean_data_desc: 清洗后的数据描述
        format: 目标格式 (例如: "csv", "json", "table")

    Returns:
        转换后的数据描述
    """
    time.sleep(0.3)
    return f"Transformed data to {format} format: {clean_data_desc}"


def search_papers(query: str, max_results: int = 5) -> str:
    """
    搜索学术论文

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数

    Returns:
        找到的论文列表 (JSON 字符串)
    """
    time.sleep(2)  # 模拟搜索延迟

    # 模拟搜索结果
    papers = [
        {
            "title": f"Deep Learning Applications in {query}",
            "authors": ["Zhang et al."],
            "year": 2024,
            "abstract": f"This paper explores novel applications of deep learning in {query}...",
        },
        {
            "title": f"A Survey on {query} Techniques",
            "authors": ["Smith et al."],
            "year": 2023,
            "abstract": f"We provide a comprehensive survey of current {query} methodologies...",
        },
        {
            "title": f"{query}: Challenges and Future Directions",
            "authors": ["Wang et al."],
            "year": 2024,
            "abstract": f"This work identifies key challenges in {query} and proposes future research directions...",
        },
    ][:max_results]

    return json.dumps(papers, ensure_ascii=False, indent=2)


def download_paper(paper_title: str) -> str:
    """
    下载论文全文

    Args:
        paper_title: 论文标题

    Returns:
        论文内容摘要
    """
    time.sleep(1)
    return f"Downloaded paper: {paper_title}\nContent: Full text of {len(paper_title) * 100} words available."


def summarize_text(text: str, max_length: int = 200) -> str:
    """
    生成文本摘要

    Args:
        text: 原始文本
        max_length: 摘要最大长度

    Returns:
        文本摘要
    """
    time.sleep(0.8)

    # 简单模拟摘要生成
    summary = text[:max_length] + "..." if len(text) > max_length else text
    return f"Summary ({len(summary)} chars): {summary}"


def extract_key_findings(text: str) -> str:
    """
    提取关键发现

    Args:
        text: 文本内容

    Returns:
        关键发现列表
    """
    time.sleep(0.5)

    # 模拟提取关键发现
    findings = [
        "Key Finding 1: Significant improvement in accuracy (95%)",
        "Key Finding 2: Novel architecture reduces training time by 40%",
        "Key Finding 3: Generalizes well to multiple domains",
    ]

    return "\n".join(findings)


# ============================================================================
# Create All Tools
# ============================================================================


def create_all_tools() -> Dict[str, Tool]:
    """创建所有工具的字典"""
    return {
        # Data collection tools
        "fetch_data_from_api": Tool(fetch_data_from_api),
        "scrape_website": Tool(scrape_website),
        # Data processing tools
        "clean_data": Tool(clean_data),
        "transform_data": Tool(transform_data),
        # Literature research tools
        "search_papers": Tool(search_papers),
        "download_paper": Tool(download_paper),
        # Summary generation tools
        "summarize_text": Tool(summarize_text),
        "extract_key_findings": Tool(extract_key_findings),
    }


# ============================================================================
# Layer 3 Agents (底层 Agents) - 执行具体任务
# ============================================================================


def create_data_collector(api_key: str) -> Agent:
    """
    创建数据采集员 (L3)

    职责：
    - 从各种数据源收集原始数据
    - 使用 API 和网页抓取工具
    """
    llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")

    tools_dict = create_all_tools()
    tools = [tools_dict["fetch_data_from_api"], tools_dict["scrape_website"]]

    system_prompt = """你是数据采集员（Data Collector）。

你的职责：
1. 从指定的数据源收集原始数据
2. 使用 fetch_data_from_api 工具从 API 获取数据
3. 使用 scrape_website 工具从网站抓取数据
4. 返回收集到的所有原始数据

工作流程：
1. 分析任务，确定需要哪些数据源
2. 调用相应的工具收集数据
3. 整理并返回所有收集到的数据

重要：
- 收集完所有数据后，使用 Action: finish 返回结果
- 结果应该包含所有数据源和收集到的内容
"""

    return Agent(
        llm=llm,
        tools=tools,
        name="DataCollector",
        system_prompt=system_prompt,
        max_iterations=5,
    )


def create_data_processor(api_key: str) -> Agent:
    """
    创建数据处理员 (L3)

    职责：
    - 清洗和转换原始数据
    - 准备数据用于分析
    """
    llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")

    tools_dict = create_all_tools()
    tools = [tools_dict["clean_data"], tools_dict["transform_data"]]

    system_prompt = """你是数据处理员（Data Processor）。

你的职责：
1. 接收原始数据并进行清洗
2. 转换数据为指定格式
3. 返回处理后的数据

工作流程：
1. 使用 clean_data 工具清洗原始数据
2. 使用 transform_data 工具转换数据格式
3. 返回最终处理结果

重要：
- 必须先清洗数据，再转换格式
- 处理完成后使用 Action: finish 返回结果
"""

    return Agent(
        llm=llm,
        tools=tools,
        name="DataProcessor",
        system_prompt=system_prompt,
        max_iterations=5,
    )


def create_paper_finder(api_key: str) -> Agent:
    """
    创建论文查找员 (L3)

    职责：
    - 搜索相关学术论文
    - 下载论文全文
    """
    llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")

    tools_dict = create_all_tools()
    tools = [tools_dict["search_papers"], tools_dict["download_paper"]]

    system_prompt = """你是论文查找员（Paper Finder）。

你的职责：
1. 根据关键词搜索学术论文
2. 下载相关论文的全文
3. 返回论文信息和内容

工作流程：
1. 使用 search_papers 搜索相关论文
2. 选择最相关的论文
3. 使用 download_paper 下载论文全文
4. 整理并返回论文信息和内容

重要：
- 先搜索论文，再下载最相关的几篇
- 完成后使用 Action: finish 返回结果
"""

    return Agent(
        llm=llm,
        tools=tools,
        name="PaperFinder",
        system_prompt=system_prompt,
        max_iterations=5,
    )


def create_summary_generator(api_key: str) -> Agent:
    """
    创建摘要生成员 (L3)

    职责：
    - 生成文本摘要
    - 提取关键发现
    """
    llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")

    tools_dict = create_all_tools()
    tools = [tools_dict["summarize_text"], tools_dict["extract_key_findings"]]

    system_prompt = """你是摘要生成员（Summary Generator）。

你的职责：
1. 为给定文本生成简洁摘要
2. 提取关键发现和要点
3. 返回结构化的摘要结果

工作流程：
1. 使用 summarize_text 生成整体摘要
2. 使用 extract_key_findings 提取关键发现
3. 整合所有信息返回完整摘要

重要：
- 摘要要简洁但包含关键信息
- 关键发现应该结构清晰
- 完成后使用 Action: finish 返回结果
"""

    return Agent(
        llm=llm,
        tools=tools,
        name="SummaryGenerator",
        system_prompt=system_prompt,
        max_iterations=5,
    )


# ============================================================================
# Layer 2 Agents (中层 Agents) - 协调底层 agents
# ============================================================================


def create_data_analyst(api_key: str) -> Agent:
    """
    创建数据分析师 (L2)

    职责：
    - 协调数据采集和处理工作
    - 管理 DataCollector 和 DataProcessor
    - 提供数据分析结果
    """
    llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")

    # 创建子 agents
    data_collector = create_data_collector(api_key)
    data_processor = create_data_processor(api_key)

    system_prompt = """你是数据分析师（Data Analyst）。

你有两个助手：
1. DataCollector - 负责收集原始数据
2. DataProcessor - 负责清洗和转换数据

你的职责：
1. 接收数据分析任务
2. 将任务分解为数据收集和处理两个步骤
3. 先启动 DataCollector 收集数据
4. 等待 DataCollector 完成
5. 将收集到的数据交给 DataProcessor 处理
6. 等待 DataProcessor 完成
7. 整合结果并返回最终的数据分析报告

重要步骤：
1. 使用 launch_subagents 启动 DataCollector
   格式：Action: launch_subagents
        Agents: ["DataCollector"]
        Tasks: ["收集关于X的数据"]

2. 使用 wait_for_subagents 等待完成

3. 收到 DataCollector 结果后：
   - 检查状态，如果有 🔄 运行中的，继续 wait
   - 如果系统提示"所有子 Agent 都已完成"，启动 DataProcessor

4. 启动 DataProcessor：
   格式：Action: launch_subagents
        Agents: ["DataProcessor"]
        Tasks: ["处理以下数据：{DataCollector的结果}"]

5. 再次 wait_for_subagents 等待处理完成

6. 收到 DataProcessor 结果后：
   - 如果系统提示"所有子 Agent 都已完成"，整合结果
   - 使用 Action: finish 返回数据分析报告

注意：
- 必须等待一个子 agent 完成才能启动下一个
- 根据系统的状态提示判断是否所有子 Agent 都完成
- 只有当系统明确提示"所有子 Agent 都已完成"时才能 finish
"""

    return Agent(
        llm=llm,
        subagents={
            "DataCollector": data_collector,
            "DataProcessor": data_processor,
        },
        name="DataAnalyst",
        system_prompt=system_prompt,
        max_iterations=15,
    )


def create_literature_researcher(api_key: str) -> Agent:
    """
    创建文献研究员 (L2)

    职责：
    - 协调论文查找和摘要生成
    - 管理 PaperFinder 和 SummaryGenerator
    - 提供文献综述
    """
    llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")

    # 创建子 agents
    paper_finder = create_paper_finder(api_key)
    summary_generator = create_summary_generator(api_key)

    system_prompt = """你是文献研究员（Literature Researcher）。

你有两个助手：
1. PaperFinder - 负责查找和下载学术论文
2. SummaryGenerator - 负责生成摘要和提取关键发现

你的职责：
1. 接收文献研究任务
2. 先启动 PaperFinder 查找相关论文
3. 等待 PaperFinder 完成
4. 将论文内容交给 SummaryGenerator 生成摘要
5. 等待 SummaryGenerator 完成
6. 整合所有结果，返回完整的文献综述

重要步骤：
1. 使用 launch_subagents 启动 PaperFinder
   格式：Action: launch_subagents
        Agents: ["PaperFinder"]
        Tasks: ["查找关于X的论文"]

2. 使用 wait_for_subagents 等待完成

3. 收到 PaperFinder 结果后：
   - 检查状态，如果有 🔄 运行中的，继续 wait
   - 如果系统提示"所有子 Agent 都已完成"，启动 SummaryGenerator

4. 启动 SummaryGenerator：
   格式：Action: launch_subagents
        Agents: ["SummaryGenerator"]
        Tasks: ["生成以下内容的摘要：{PaperFinder的结果}"]

5. 再次 wait_for_subagents 等待完成

6. 收到 SummaryGenerator 结果后：
   - 如果系统提示"所有子 Agent 都已完成"，整合结果
   - 使用 Action: finish 返回文献综述

注意：
- 必须按顺序执行：先找论文，再生成摘要
- 每次启动子 agent 后都要 wait
- 根据系统的状态提示判断是否所有子 Agent 都完成
- 只有当系统明确提示"所有子 Agent 都已完成"时才能 finish
"""

    return Agent(
        llm=llm,
        subagents={
            "PaperFinder": paper_finder,
            "SummaryGenerator": summary_generator,
        },
        name="LiteratureResearcher",
        system_prompt=system_prompt,
        max_iterations=15,
    )


# ============================================================================
# Layer 1 Agent (顶层 Agent) - 研究总监
# ============================================================================


def create_research_director(api_key: str) -> Agent:
    """
    创建研究总监 (L1)

    职责：
    - 接收研究任务
    - 协调数据分析和文献研究
    - 生成最终研究报告
    """
    llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")

    # 创建子 agents
    data_analyst = create_data_analyst(api_key)
    literature_researcher = create_literature_researcher(api_key)

    system_prompt = """你是研究总监（Research Director）。

你有两个核心团队：
1. DataAnalyst - 数据分析团队（包含 DataCollector 和 DataProcessor）
2. LiteratureResearcher - 文献研究团队（包含 PaperFinder 和 SummaryGenerator）

你的职责：
1. 接收研究任务
2. 将任务分解为数据分析和文献研究两部分
3. 同时启动两个团队并行工作
4. 等待两个团队完成
5. 整合所有结果，生成最终研究报告

工作流程：
1. 分析研究任务，确定数据分析需求和文献研究需求

2. 同时启动两个团队：
   Action: launch_subagents
   Agents: ["DataAnalyst", "LiteratureResearcher"]
   Tasks: ["数据分析任务描述", "文献研究任务描述"]

3. 等待团队完成：
   Action: wait_for_subagents

4. 当收到子 Agent 完成通知时：
   - 系统会显示当前状态（哪些已完成，哪些还在运行）
   - 如果还有子 Agent 在运行（状态显示 🔄 运行中），继续 wait_for_subagents
   - 如果所有子 Agent 都已完成（没有 🔄 运行中的），立即进入步骤 5

5. 所有团队完成后（系统会明确提示"所有子 Agent 都已完成"）：
   - 整合两个团队的结果
   - 生成最终研究报告（包括数据分析、文献综述、结论）
   - 使用 Action: finish 返回最终报告

重要注意事项：
- 两个团队应该并行工作，不是顺序执行
- 每个团队完成后都会收到通知并更新状态
- 当系统提示"所有子 Agent 都已完成"时，不要再 wait_for_subagents
- 必须根据状态提示判断是否还需要等待
- 只有当状态中没有 🔄 运行中的子 Agent 时才能 finish
"""

    return Agent(
        llm=llm,
        subagents={
            "DataAnalyst": data_analyst,
            "LiteratureResearcher": literature_researcher,
        },
        name="ResearchDirector",
        system_prompt=system_prompt,
        max_iterations=20,
    )


# ============================================================================
# Main Function
# ============================================================================


async def main():
    """运行三层 agent 系统示例"""
    # 加载环境变量
    load_env()

    api_key = get_deepseek_api_key()
    if not api_key:
        print("错误：请在 .env 文件中设置 DEEPSEEK_API_KEY")
        return

    print("=" * 80)
    print("三层 Agent 系统示例 - 研究助理系统")
    print("=" * 80)
    print()
    print("系统架构：")
    print("  L1: ResearchDirector (研究总监)")
    print("      ├── L2: DataAnalyst (数据分析师)")
    print("      │   ├── L3: DataCollector (数据采集员)")
    print("      │   └── L3: DataProcessor (数据处理员)")
    print("      └── L2: LiteratureResearcher (文献研究员)")
    print("          ├── L3: PaperFinder (论文查找员)")
    print("          └── L3: SummaryGenerator (摘要生成员)")
    print()
    print("特点：")
    print("  ✓ 三层嵌套调用")
    print("  ✓ L2 agents 并行执行")
    print("  ✓ 每层 agent 都可以多轮调用其子 agents")
    print("  ✓ 递归任务分解和结果聚合")
    print("=" * 80)
    print()

    # 初始化异步日志
    logger = await init_logger(log_dir="logs", console_output=True)

    try:
        # 创建研究总监
        print("正在初始化研究总监系统...")
        research_director = create_research_director(api_key)
        print("✓ 系统初始化完成")
        print()

        # 定义研究任务
        research_task = """
请对"人工智能在医疗健康领域的应用"进行全面研究。

研究要求：
1. 数据分析部分：
   - 收集医疗健康相关的统计数据
   - 收集 AI 应用案例的数据
   - 清洗和分析这些数据

2. 文献研究部分：
   - 查找 AI 医疗相关的最新学术论文
   - 生成文献综述和关键发现

最终需要一份整合数据分析和文献研究的完整报告。
"""

        print("研究任务：")
        print(research_task)
        print()
        print("开始执行研究任务...")
        print("=" * 80)
        print()

        # 记录开始时间
        start_time = time.time()

        # 执行任务
        result = await research_director._run_async(task=research_task)

        # 记录结束时间
        end_time = time.time()
        elapsed_time = end_time - start_time

        # 输出结果
        print()
        print("=" * 80)
        print("研究完成！")
        print("=" * 80)
        print()
        print(f"执行状态: {'✓ 成功' if result.success else '✗ 失败'}")
        print(f"迭代次数: {result.iterations}")
        print(f"总耗时: {elapsed_time:.2f} 秒")
        print()
        print("最终研究报告：")
        print("-" * 80)
        print(result.content)
        print("-" * 80)
        print()

        # 系统统计
        print("系统执行统计：")
        print(f"  • 涉及 agents: 7 个 (1个L1 + 2个L2 + 4个L3)")
        print(f"  • 使用 tools: 8 个")
        print(f"  • 并行执行: L2 层的 2 个 agents 并行")
        print(f"  • 嵌套深度: 3 层")
        print()
        print(f"日志保存位置: logs/")
        print()

    except Exception as e:
        print(f"错误: {str(e)}")
        import traceback

        traceback.print_exc()
    finally:
        # 关闭日志
        await close_logger()


if __name__ == "__main__":
    asyncio.run(main())
