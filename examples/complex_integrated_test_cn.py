"""
复杂Agent集成测试示例 - 中文版

这个示例展示了一个复杂的真实场景：
1. 数据分析任务
2. 使用多个工具 (Python执行、文件操作、数据查询)
3. 多步骤推理和决策
4. 详细的中文输出展示所有中间结果

场景：数据分析助手
- 读取数据文件
- 执行数据分析
- 生成统计报告
- 保存结果并验证

输出内容：
- 每次迭代的详细信息
- LLM的思考过程
- 工具调用和结果
- 完整的执行流程
"""

import os
import sys
import json
import tempfile
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import (
    DeepSeekLLM,
    Tool,
    Agent,
    ConsoleCallback,
    MetricsCallback,
    AgentCallback,
    get_deepseek_api_key,
)


# ===========================
# 工具实现
# ===========================


def python_exec(code: str) -> str:
    """执行Python代码并返回输出结果"""
    from io import StringIO

    old_stdout = sys.stdout
    sys.stdout = StringIO()

    # 创建安全的执行环境
    exec_globals = {
        "__builtins__": __builtins__,
        "json": json,
        "os": os,
    }

    try:
        exec(code, exec_globals)
        output = sys.stdout.getvalue()
        return output if output else "代码执行成功（无输出）"
    except Exception as e:
        return f"执行错误: {str(e)}"
    finally:
        sys.stdout = old_stdout


def file_read(path: str) -> str:
    """读取文件内容"""
    try:
        if not os.path.exists(path):
            return f"错误: 文件不存在 - {path}"

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # 限制输出长度
        if len(content) > 1000:
            return content[:1000] + f"\n... (文件总长度: {len(content)} 字符)"
        return content
    except Exception as e:
        return f"读取文件错误: {str(e)}"


def file_write(path: str, content: str) -> str:
    """写入内容到文件"""
    try:
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return f"成功写入 {len(content)} 个字符到 {path}"
    except Exception as e:
        return f"写入文件错误: {str(e)}"


def data_query(query_type: str, data_source: str = "sales") -> str:
    """查询模拟数据库"""
    # 模拟数据库
    databases = {
        "sales": {
            "total": "2024年总销售额: ¥1,250,000",
            "monthly": "月平均销售额: ¥104,167",
            "top_product": "最畅销产品: 智能手机 (35%市场份额)",
            "growth": "同比增长率: +15.3%",
            "summary": json.dumps(
                {
                    "total_sales": 1250000,
                    "average_monthly": 104167,
                    "top_products": ["智能手机", "笔记本电脑", "平板电脑"],
                    "growth_rate": 15.3,
                },
                ensure_ascii=False,
                indent=2,
            ),
        },
        "customers": {
            "total": "总客户数: 5,432",
            "new": "新增客户: 847 (本月)",
            "retention": "客户留存率: 87.5%",
            "satisfaction": "客户满意度: 4.6/5.0",
        },
        "inventory": {
            "status": "库存状态: 正常",
            "low_stock": "低库存商品: 3件",
            "reorder": "需要补货: 蓝牙耳机, 充电器",
        },
    }

    if data_source not in databases:
        return f"错误: 未知的数据源 '{data_source}'"

    db = databases[data_source]

    if query_type not in db:
        available = ", ".join(db.keys())
        return f"错误: 未知的查询类型 '{query_type}'. 可用类型: {available}"

    return db[query_type]


def calculator(expression: str) -> str:
    """安全地计算数学表达式"""
    try:
        # 只允许基本的数学运算符
        allowed_chars = set("0123456789+-*/(). ")
        if not all(c in allowed_chars for c in expression):
            return "错误: 表达式包含非法字符"

        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"


# ===========================
# 自定义中文回调
# ===========================


class ChineseVerboseCallback(AgentCallback):
    """
    详细的中文回调，展示完整的执行过程
    """

    def __init__(self):
        self.iteration = 0
        self.start_time = None
        self.tool_calls = []

    def on_agent_start(self, task: str, agent_name: str):
        self.start_time = datetime.now()
        print("\n" + "=" * 80)
        print(f"🚀 Agent开始执行")
        print("=" * 80)
        print(f"📋 任务: {task}")
        print(f"🤖 Agent名称: {agent_name}")
        print(f"🕐 开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

    def on_iteration_start(self, iteration: int, agent_name: str):
        self.iteration = iteration
        print(f"\n{'─' * 80}")
        print(f"🔄 第 {iteration} 次迭代开始")
        print(f"{'─' * 80}")

    def on_llm_request(self, iteration: int, prompt: str, system_prompt=None):
        if iteration == 0 and system_prompt:
            print(f"\n📝 系统提示词:")
            # 只显示前200个字符
            preview = (
                system_prompt[:200] + "..."
                if len(system_prompt) > 200
                else system_prompt
            )
            for line in preview.split("\n"):
                print(f"   {line}")

        print(f"\n💬 用户输入到LLM:")
        # 显示前300个字符
        preview = prompt[:300] + "..." if len(prompt) > 300 else prompt
        for line in preview.split("\n"):
            print(f"   {line}")

    def on_llm_response(self, iteration: int, response: str):
        print(f"\n🧠 LLM响应:")
        print("─" * 80)

        # 解析并美化输出
        lines = response.split("\n")
        for line in lines:
            if line.strip().startswith("Thought:"):
                print(f"💭 思考: {line.replace('Thought:', '').strip()}")
            elif line.strip().startswith("Action:"):
                print(f"⚡ 动作: {line.replace('Action:', '').strip()}")
            elif line.strip().startswith("Tool:"):
                print(f"🔧 工具: {line.replace('Tool:', '').strip()}")
            elif line.strip().startswith("Arguments:"):
                print(f"📦 参数: {line.replace('Arguments:', '').strip()}")
            elif line.strip().startswith("Response:"):
                print(f"📝 回复: {line.replace('Response:', '').strip()}")
            else:
                if line.strip():
                    print(f"   {line}")

        print("─" * 80)

    def on_parse_success(self, iteration: int, action_type: str, details: dict):
        if action_type == "tool":
            print(f"✅ 成功解析 - 将执行工具: {details.get('tool_name', 'unknown')}")
        elif action_type == "finish":
            print(f"✅ 成功解析 - Agent准备完成")
        elif action_type == "subagent":
            print(
                f"✅ 成功解析 - 将调用子Agent: {details.get('agent_name', 'unknown')}"
            )

    def on_parse_error(self, iteration: int, error: str, retry_count: int):
        print(f"⚠️  解析错误 (重试 {retry_count}/3): {error[:100]}")

    def on_tool_call(self, iteration: int, tool_name: str, arguments: dict):
        print(f"\n🔧 调用工具")
        print(f"   工具名称: {tool_name}")
        print(f"   参数:")
        for key, value in arguments.items():
            # 限制参数值的显示长度
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:100] + "..."
            print(f"      {key}: {value_str}")

        self.tool_calls.append(
            {"iteration": iteration, "tool": tool_name, "arguments": arguments}
        )

    def on_tool_result(
        self, iteration: int, tool_name: str, result: str, success: bool
    ):
        print(f"\n📤 工具执行结果")
        print(f"   工具: {tool_name}")
        print(f"   状态: {'✅ 成功' if success else '❌ 失败'}")
        print(f"   结果:")

        # 美化输出结果
        result_lines = result.split("\n")
        for i, line in enumerate(result_lines):
            if i >= 10:  # 最多显示10行
                print(f"      ... (还有 {len(result_lines) - 10} 行)")
                break
            print(f"      {line}")

    def on_iteration_end(self, iteration: int, action_type: str):
        print(f"\n✓ 第 {iteration} 次迭代完成 (动作类型: {action_type})")

    def on_agent_finish(self, success: bool, iterations: int, content: str):
        elapsed = (
            (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        )

        print(f"\n{'=' * 80}")
        print(f"🏁 Agent执行完成")
        print(f"{'=' * 80}")
        print(f"✅ 成功: {success}")
        print(f"🔄 总迭代次数: {iterations}")
        print(f"⏱️  执行时间: {elapsed:.2f} 秒")
        print(f"🔧 工具调用次数: {len(self.tool_calls)}")

        print(f"\n📝 最终结果:")
        print("─" * 80)
        for line in content.split("\n"):
            print(f"   {line}")
        print("─" * 80)

        # 打印工具使用统计
        if self.tool_calls:
            print(f"\n📊 工具使用统计:")
            tool_counts = {}
            for call in self.tool_calls:
                tool = call["tool"]
                tool_counts[tool] = tool_counts.get(tool, 0) + 1

            for tool, count in sorted(
                tool_counts.items(), key=lambda x: x[1], reverse=True
            ):
                print(f"   {tool}: {count} 次")


# ===========================
# API Key 助手
# ===========================


def get_api_key():
    """从文件或环境变量获取DeepSeek API key (使用dotenv配置)"""
    return get_deepseek_api_key()


# ===========================
# 主测试场景
# ===========================


def create_test_data_file():
    """创建测试数据文件"""
    test_data = {
        "products": [
            {"name": "智能手机", "sales": 437500, "units": 2500},
            {"name": "笔记本电脑", "sales": 375000, "units": 750},
            {"name": "平板电脑", "sales": 250000, "units": 1250},
            {"name": "智能手表", "sales": 125000, "units": 1000},
            {"name": "蓝牙耳机", "sales": 62500, "units": 1250},
        ],
        "total_sales": 1250000,
        "period": "2024年1-12月",
    }

    temp_file = tempfile.mktemp(suffix=".json", prefix="sales_data_")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)

    return temp_file


def run_complex_integrated_test():
    """运行复杂的集成测试"""

    print("\n" + "=" * 80)
    print("复杂Agent集成测试 - 数据分析场景")
    print("=" * 80)
    print("\n这个测试展示一个真实的数据分析工作流:")
    print("  1. 从数据库查询销售数据")
    print("  2. 读取数据文件进行分析")
    print("  3. 使用Python进行数据处理")
    print("  4. 生成分析报告")
    print("  5. 保存结果并验证")
    print("\n所有中间步骤将以中文详细展示。")

    # 获取API key
    api_key = get_api_key()
    if not api_key:
        print("\n❌ 错误: 找不到DeepSeek API key!")
        print("请在.env文件中设置 DEEPSEEK_API_KEY 或设置环境变量")
        return

    # 创建测试数据文件
    data_file = create_test_data_file()
    print(f"\n✅ 已创建测试数据文件: {data_file}")

    # 创建输出文件路径
    report_file = tempfile.mktemp(suffix=".txt", prefix="sales_report_")
    print(f"📄 报告将保存到: {report_file}")

    try:
        # 初始化LLM
        print("\n🔧 初始化DeepSeek LLM...")
        llm = DeepSeekLLM(
            api_key=api_key, model="deepseek-chat", base_url="https://api.deepseek.com"
        )

        # 创建工具
        tools = [
            Tool(python_exec),
            Tool(file_read),
            Tool(file_write),
            Tool(data_query),
            Tool(calculator),
        ]

        print(f"✅ 已创建 {len(tools)} 个工具")

        # 创建回调
        verbose_callback = ChineseVerboseCallback()
        metrics_callback = MetricsCallback()

        # 创建Agent
        print("\n🤖 创建数据分析Agent...")
        agent = Agent(
            llm=llm,
            tools=tools,
            callbacks=[verbose_callback, metrics_callback],
            max_iterations=20,
            # max_iterations=12,
            name="数据分析助手",
            system_prompt="""你是一个专业的数据分析助手，擅长处理销售数据和生成报告。

你需要按照以下步骤完成任务：
1. 首先使用 data_query 工具查询数据库获取销售概况
2. 使用 file_read 工具读取数据文件
3. 使用 python_exec 工具分析数据（可以使用json库解析数据）
4. 使用 calculator 工具进行必要的计算
5. 最后使用 file_write 工具保存分析报告

请用中文思考和回复。""",
        )

        # 定义复杂任务
        task = f"""请完成以下数据分析任务：

1. 查询2024年销售数据的总览（使用data_query工具，query_type="summary"）
2. 读取详细数据文件: {data_file}
3. 分析数据，计算：
   - 销售额最高的3个产品
   - 平均单价（总销售额/总销量）
   - 每个产品的销售占比
4. 生成一份中文分析报告，包含所有统计结果
5. 将报告保存到: {report_file}

请一步步完成，每次使用一个工具，并在完成后总结结果。"""

        # 运行Agent
        print("\n" + "=" * 80)
        print("开始执行任务...")
        print("=" * 80)

        result = agent.run(task)

        # 打印指标
        print("\n" + "=" * 80)
        print("执行指标")
        print("=" * 80)
        metrics_callback.print_summary()

        # 验证结果
        print("\n" + "=" * 80)
        print("结果验证")
        print("=" * 80)

        if os.path.exists(report_file):
            print(f"✅ 报告文件已创建: {report_file}")
            print(f"\n📄 报告内容:")
            print("─" * 80)
            with open(report_file, "r", encoding="utf-8") as f:
                content = f.read()
                print(content)
            print("─" * 80)
        else:
            print(f"⚠️  警告: 报告文件未创建")

        # 最终总结
        print("\n" + "=" * 80)
        print("测试总结")
        print("=" * 80)
        print(f"任务完成状态: {'✅ 成功' if result.success else '❌ 失败'}")
        print(f"迭代次数: {result.iterations}")
        print(f"工具使用: {len(verbose_callback.tool_calls)} 次")

        if verbose_callback.tool_calls:
            print(f"\n工具调用序列:")
            for i, call in enumerate(verbose_callback.tool_calls, 1):
                print(f"  {i}. [{call['iteration']}] {call['tool']}")

    except Exception as e:
        print(f"\n❌ 测试执行出错: {str(e)}")
        import traceback

        traceback.print_exc()

    finally:
        # 清理临时文件
        print("\n🗑️  清理临时文件...")
        if os.path.exists(data_file):
            os.remove(data_file)
            print(f"   删除: {data_file}")
        if os.path.exists(report_file):
            # 保留报告文件供查看
            print(f"   保留报告文件: {report_file}")

        print("\n✅ 测试完成!")


# ===========================
# 入口点
# ===========================

if __name__ == "__main__":
    try:
        run_complex_integrated_test()
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 发生未预期的错误: {str(e)}")
        import traceback

        traceback.print_exc()
