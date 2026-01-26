"""
Example: System Analysis Agent with Restricted Bash and Calculator

This example demonstrates:
1. Using restricted_bash tool for safe command execution
2. Using calculator tool for data analysis
3. An agent that analyzes system information and performs calculations

The agent can:
- List files and directories (ls, find)
- Search text files (grep, cat)
- Get system information (whoami, hostname, date)
- Perform calculations on the data
- But CANNOT execute dangerous commands (rm, curl, wget, etc.)
"""

import asyncio
from agent.agent import Agent
from agent.llm import DeepSeekLLM
from agent.tool import Tool
from agent.builtin_tools import restricted_bash, calculator
from agent.config import load_env, get_deepseek_api_key
from agent.async_logger import init_logger, close_logger


def create_system_analyst_agent(api_key: str) -> Agent:
    """
    Create a system analyst agent with restricted bash and calculator.

    The agent can analyze the system using safe commands and perform
    calculations, but cannot execute dangerous operations.
    """
    llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")

    # Create tools
    bash_tool = Tool(restricted_bash)
    calc_tool = Tool(calculator)

    system_prompt = """你是一个系统分析助手（System Analyst）。

你可以使用的工具：
1. restricted_bash - 执行安全的 shell 命令
   - 允许的命令：ls, cat, grep, wc, find, pwd, whoami, date 等
   - 禁止的命令：rm, curl, wget, chmod, sudo 等危险命令
   
2. calculator - 执行数学计算
   - 支持基本运算、数学函数、常量等

你的任务：
1. 使用 restricted_bash 收集系统信息
2. 分析文件和目录
3. 使用 calculator 进行数据计算和统计
4. 提供清晰的分析报告

重要提示：
- 如果命令被拒绝（显示 "not allowed"），说明该命令不在白名单中
- 只能使用安全的只读命令
- 可以使用管道（pipe）组合命令，例如：ls | grep .py
- 所有计算都应该使用 calculator 工具

工作流程：
1. 理解用户的分析需求
2. 使用 restricted_bash 收集必要的数据
3. 使用 calculator 进行计算
4. 整理结果并给出分析报告
5. 使用 Action: finish 返回最终报告
"""

    return Agent(
        llm=llm,
        tools=[bash_tool, calc_tool],
        name="SystemAnalyst",
        system_prompt=system_prompt,
        max_iterations=15,
    )


async def main():
    """Run the system analyst example."""
    # Load environment variables
    load_env()

    api_key = get_deepseek_api_key()
    if not api_key:
        print("错误：请在 .env 文件中设置 DEEPSEEK_API_KEY")
        return

    print("=" * 80)
    print("系统分析助手示例 - 使用受限 Bash 和计算器")
    print("=" * 80)
    print()
    print("功能特点：")
    print("  ✓ 安全的命令执行（只允许白名单命令）")
    print("  ✓ 支持管道和文本处理")
    print("  ✓ 数学计算和数据分析")
    print("  ✗ 禁止危险命令（rm, curl, wget, chmod 等）")
    print()
    print("=" * 80)
    print()

    # Initialize async logger
    logger = await init_logger(log_dir="logs", console_output=True)

    try:
        # Create agent
        agent = create_system_analyst_agent(api_key)

        # Task 1: Analyze current directory
        print("\n" + "=" * 80)
        print("任务 1: 分析当前目录")
        print("=" * 80)

        task1 = """
请分析当前目录（hic 项目）的结构：
1. 列出所有 Python 文件（.py）
2. 统计 Python 文件的数量
3. 找出最大的 3 个 Python 文件
4. 计算所有 Python 文件的总行数（使用 wc -l）
5. 计算平均每个文件的行数

请给出详细的分析报告。
"""

        result1 = await agent._run_async(task=task1)

        print("\n结果:")
        print("-" * 80)
        print(result1.content)
        print("-" * 80)
        print(f"执行状态: {'✓ 成功' if result1.success else '✗ 失败'}")
        print(f"迭代次数: {result1.iterations}")

        # Reset agent for next task
        agent.llm.reset_history()

        # Task 2: Test security restrictions
        print("\n" + "=" * 80)
        print("任务 2: 测试安全限制")
        print("=" * 80)

        task2 = """
请尝试以下操作，并报告哪些被允许，哪些被拒绝：

1. 查看当前用户：whoami
2. 查看当前日期：date
3. 列出文件：ls -la
4. 尝试删除文件（应该被拒绝）：rm test.txt
5. 尝试下载文件（应该被拒绝）：curl http://example.com
6. 使用管道查找 Python 文件：ls | grep .py
7. 计算：sqrt(144) + 10 * 2

请总结安全机制的效果。
"""

        result2 = await agent._run_async(task=task2)

        print("\n结果:")
        print("-" * 80)
        print(result2.content)
        print("-" * 80)
        print(f"执行状态: {'✓ 成功' if result2.success else '✗ 失败'}")
        print(f"迭代次数: {result2.iterations}")

        print("\n" + "=" * 80)
        print("示例完成！")
        print("=" * 80)
        print()
        print("总结：")
        print("  • 安全命令（ls, grep, cat, whoami, date）- 全部通过")
        print("  • 危险命令（rm, curl）- 被安全拦截")
        print("  • 数学计算 - 正常执行")
        print("  • 管道命令 - 支持使用")
        print()

    except Exception as e:
        print(f"错误: {str(e)}")
        import traceback

        traceback.print_exc()
    finally:
        # Close logger
        await close_logger()


def demo_restricted_bash():
    """
    Quick demo of restricted_bash functionality without agent.
    """
    print("\n" + "=" * 80)
    print("Restricted Bash 快速演示（无 Agent）")
    print("=" * 80)
    print()

    from agent.builtin_tools import restricted_bash

    test_cases = [
        ("ls -la", "列出文件", True),
        ("whoami", "当前用户", True),
        ("pwd", "当前目录", True),
        ("echo 'Hello World'", "输出文本", True),
        ("ls | grep .py", "管道：查找 Python 文件", True),
        ("cat README.md | head -n 5", "管道：读取文件前5行", True),
        ("rm test.txt", "删除文件", False),
        ("curl http://example.com", "网络请求", False),
        ("wget file.zip", "下载文件", False),
        ("chmod 777 file", "修改权限", False),
        ("sudo apt-get install", "特权命令", False),
    ]

    for command, description, should_succeed in test_cases:
        result = restricted_bash(command)
        status = "✓" if "Error" not in result or not should_succeed else "✗"
        expected = "允许" if should_succeed else "拒绝"

        print(f"{status} {description} ({expected})")
        print(f"   命令: {command}")
        if "Error" in result:
            print(f"   结果: {result[:80]}...")
        else:
            print(f"   结果: {result[:80]}{'...' if len(result) > 80 else ''}")
        print()


if __name__ == "__main__":
    # Quick demo without agent
    print("\n运行快速演示（不使用 Agent）...")
    demo_restricted_bash()

    # Full agent example
    print("\n\n运行完整的 Agent 示例...")
    asyncio.run(main())
