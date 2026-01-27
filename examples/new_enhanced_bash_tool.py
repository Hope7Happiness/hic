"""
Example: System Analysis Agent with NEW Enhanced Bash Tool and Calculator

This example demonstrates the NEW bash tool from agent/tools/bash.py with:
1. Async execution with proper timeout/abort handling
2. Structured ToolResult with metadata
3. Automatic Context injection by Agent
4. Permission system (auto-approve in this example)
5. Automatic output truncation for large outputs
6. Better error handling and diagnostics

The agent can:
- List files and directories (ls, find)
- Search text files (grep, cat)
- Get system information (whoami, hostname, date)
- Perform calculations on the data
- But CANNOT execute dangerous commands (rm, curl, wget, etc.)

Key differences from the old version:
- Import from agent.tools.bash instead of agent.builtin_tools
- Agent automatically creates Context and injects it into tools
- Tool returns ToolResult with structured metadata
- Fully async with better timeout handling
"""

import asyncio
from agent.agent import Agent
from agent.llm import DeepSeekLLM
from agent.tool import Tool
from agent.tools.bash import bash, DEFAULT_SAFE_COMMANDS  # NEW: Enhanced bash tool
from agent.builtin_tools import calculator  # calculator is not deprecated
from agent.config import load_env, get_deepseek_api_key
from agent.async_logger import init_logger, close_logger


def create_system_analyst_agent(api_key: str) -> Agent:
    """
    Create a system analyst agent with the NEW enhanced bash tool and calculator.

    The agent can analyze the system using safe commands and perform
    calculations, but cannot execute dangerous operations.

    The NEW bash tool provides:
    - Async execution with timeout support
    - Structured ToolResult with metadata (exit_code, duration, etc.)
    - Automatic Context injection (no manual setup needed)
    - Permission system with auto-approve patterns
    - Automatic output truncation for large results
    """
    llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")

    # Create tools using the NEW bash tool
    # Note: Context will be automatically created and injected by Agent
    bash_tool = Tool(bash)  # NEW: agent/tools/bash.py (async, enhanced)
    calc_tool = Tool(calculator)

    system_prompt = """你是一个系统分析助手（System Analyst）。

你可以使用的工具：
1. bash - 执行安全的 shell 命令（增强版）
   - 允许的命令：ls, cat, grep, wc, find, pwd, whoami, date 等
   - 禁止的命令：rm, curl, wget, chmod, sudo 等危险命令
   - 新特性：异步执行、结构化结果、自动输出截断
   
2. calculator - 执行数学计算
   - 支持基本运算、数学函数、常量等

你的任务：
1. 使用 bash 收集系统信息
2. 分析文件和目录
3. 使用 calculator 进行数据计算和统计
4. 提供清晰的分析报告

重要提示：
- 如果命令被拒绝（显示 "not allowed"），说明该命令不在白名单中
- 只能使用安全的只读命令
- 可以使用管道（pipe）组合命令，例如：ls | grep .py
- 所有计算都应该使用 calculator 工具
- bash 工具现在返回结构化结果，包含执行时间等元数据

工作流程：
1. 理解用户的分析需求
2. 使用 bash 收集必要的数据
3. 使用 calculator 进行计算
4. 整理结果并给出分析报告
5. 使用 Action: finish 返回最终报告
"""

    # Agent will automatically create Context and inject it into tools
    return Agent(
        llm=llm,
        tools=[bash_tool, calc_tool],
        name="SystemAnalyst",
        system_prompt=system_prompt,
        max_iterations=15,
    )


async def main():
    """Run the system analyst example with NEW enhanced bash tool."""
    # Load environment variables
    load_env()

    api_key = get_deepseek_api_key()
    if not api_key:
        print("错误：请在 .env 文件中设置 DEEPSEEK_API_KEY")
        return

    print("=" * 80)
    print("系统分析助手示例 - 使用 NEW 增强版 Bash 工具")
    print("=" * 80)
    print()
    print("新功能特点：")
    print("  ✓ 异步执行，支持 timeout 和 abort signals")
    print("  ✓ 结构化 ToolResult（包含 metadata、attachments）")
    print("  ✓ 自动 Context 注入（无需手动配置）")
    print("  ✓ 权限系统（基于 Context 的细粒度控制）")
    print("  ✓ 自动输出截断（>2000行或>50KB 自动保存到文件）")
    print("  ✓ 详细元数据（exit_code、duration_ms、working_dir）")
    print("  ✗ 禁止危险命令（rm, curl, wget, chmod 等）")
    print()
    print("=" * 80)
    print()

    # Initialize async logger
    logger = await init_logger(log_dir="logs", console_output=True)

    try:
        # Create agent (Context is automatically created and injected)
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
        print("  • NEW: 所有工具调用都返回结构化 ToolResult")
        print("  • NEW: Context 自动管理，无需手动配置")
        print()

    except Exception as e:
        print(f"错误: {str(e)}")
        import traceback

        traceback.print_exc()
    finally:
        # Close logger
        await close_logger()


async def demo_enhanced_bash():
    """
    Quick demo of the NEW enhanced bash tool without agent.

    This shows the differences from the old version:
    - Returns ToolResult instead of string
    - Requires Context (but easy to create)
    - Provides detailed metadata
    - Async by default
    """
    print("\n" + "=" * 80)
    print("NEW 增强版 Bash 工具快速演示（无 Agent）")
    print("=" * 80)
    print()

    from agent.tools.bash import bash, DEFAULT_SAFE_COMMANDS
    from agent.context import create_auto_approve_context

    # Create context (auto-approve all bash commands)
    ctx = create_auto_approve_context(patterns={"bash": ["*"]})

    test_cases = [
        ("ls -la", "列出文件", DEFAULT_SAFE_COMMANDS),
        ("whoami", "当前用户", DEFAULT_SAFE_COMMANDS),
        ("pwd", "当前目录", DEFAULT_SAFE_COMMANDS),
        ("echo 'Hello World'", "输出文本", DEFAULT_SAFE_COMMANDS),
        ("ls | grep .py", "管道：查找 Python 文件", DEFAULT_SAFE_COMMANDS),
        ("rm test.txt", "删除文件", DEFAULT_SAFE_COMMANDS),
        ("curl http://example.com", "网络请求", DEFAULT_SAFE_COMMANDS),
    ]

    for command, description, allowed_cmds in test_cases:
        print(f"测试: {description}")
        print(f"命令: {command}")

        # Call the NEW bash tool (async)
        result = await bash(command, ctx, allowed_commands=allowed_cmds)

        # NEW: result is a ToolResult object with structured data
        if result.is_success:
            print(f"✓ 成功")
            print(f"  标题: {result.title}")
            print(
                f"  输出: {result.output[:60]}{'...' if len(result.output) > 60 else ''}"
            )
            print(
                f"  元数据: exit_code={result.metadata.get('exit_code')}, "
                f"duration={result.metadata.get('duration_ms')}ms"
            )
        else:
            print(f"✗ 失败")
            print(f"  标题: {result.title}")
            print(f"  错误: {result.error}")

        print()


async def demo_direct_tool_usage():
    """
    Demo: Using Tool class directly without Agent.

    This shows how Context is automatically injected when using Tool wrapper.
    """
    print("\n" + "=" * 80)
    print("NEW Tool 类直接使用演示（Context 自动注入）")
    print("=" * 80)
    print()

    from agent.tools.bash import bash
    from agent.tool import Tool
    from agent.context import create_auto_approve_context

    # Create context
    ctx = create_auto_approve_context(patterns={"bash": ["*"]})

    # Create tool with context (context will be auto-injected)
    bash_tool = Tool(bash, context=ctx)

    print(f"Tool 信息: {bash_tool}")
    print(f"Is async: {bash_tool.is_async}")
    print(f"Has context: {bash_tool.context is not None}")
    print()

    # Call tool without providing ctx parameter (it's auto-injected!)
    print("执行命令: echo 'Hello from NEW Tool'")
    result = await bash_tool.call_async(command="echo 'Hello from NEW Tool'")

    print(f"\n结果类型: {type(result).__name__}")
    print(f"成功: {result.is_success}")
    print(f"标题: {result.title}")
    print(f"输出: {result.output}")
    print(f"元数据: {result.metadata}")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("NEW 增强版 Bash 工具示例")
    print("=" * 80)
    print()
    print("这个示例展示了新版本 agent/tools/bash.py 的特性：")
    print("  1. 异步执行，支持 timeout 和 abort")
    print("  2. 结构化 ToolResult 返回")
    print("  3. Context 自动注入（Agent 自动管理）")
    print("  4. 权限系统和安全限制")
    print("  5. 输出自动截断")
    print("  6. 详细的执行元数据")
    print()

    # Demo 1: Direct bash tool usage
    print("\n=== Demo 1: 直接使用 bash 工具 ===")
    asyncio.run(demo_enhanced_bash())

    # Demo 2: Using Tool class
    print("\n=== Demo 2: 使用 Tool 类封装 ===")
    asyncio.run(demo_direct_tool_usage())

    # Demo 3: Full agent example
    print("\n=== Demo 3: 完整的 Agent 示例 ===")
    asyncio.run(main())
