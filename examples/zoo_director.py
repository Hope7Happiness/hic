"""
动物园园长示例 - 展示分层Agent的使用

这个例子展示了一个有趣的分层Agent系统：
- 🦁 园长Agent：负责决策将问题分配给哪个动物助手
- 🐱 猫猫Agent：每次回答必须以"喵呜！"开头
- 🐶 狗狗Agent：每次回答必须以"汪汪！"开头

园长不能直接回答问题，必须选择一个子Agent来处理。
每个子Agent使用不同的颜色显示，便于区分。
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import (
    DeepSeekLLM,
    Agent,
    Tool,
    get_deepseek_api_key,
    ColorfulConsoleCallback,
)
from typing import Dict


# ===========================
# 工具定义
# ===========================


def search_animal_info(animal: str) -> str:
    """
    搜索动物的相关信息。

    Args:
        animal: 动物名称

    Returns:
        动物的信息描述
    """
    animal_db = {
        "猫": "猫是一种小型哺乳动物，喜欢吃鱼和老鼠，性格独立，喜欢晒太阳和打盹。",
        "狗": "狗是人类最忠诚的朋友，喜欢玩耍和运动，性格友善，对主人非常忠诚。",
        "老虎": "老虎是大型猫科动物，是森林之王，非常凶猛但也很威武。",
        "熊猫": "熊猫是中国的国宝，喜欢吃竹子，性格憨厚可爱。",
        "大象": "大象是陆地上最大的哺乳动物，拥有长鼻子，记忆力很好。",
        "狮子": "狮子是草原之王，雄狮有威武的鬃毛，群居生活。",
    }

    return animal_db.get(animal, f"抱歉，我的数据库里没有关于{animal}的信息。")


def calculate_age(birth_year: int) -> str:
    """
    计算年龄。

    Args:
        birth_year: 出生年份

    Returns:
        年龄信息
    """
    current_year = 2026
    age = current_year - birth_year
    return f"年龄是 {age} 岁"


def tell_joke(topic: str = "通用") -> str:
    """
    讲一个笑话。

    Args:
        topic: 笑话主题

    Returns:
        笑话内容
    """
    jokes = {
        "猫": "为什么猫咪不会玩扑克？因为怕被当成猫腻！",
        "狗": "为什么狗狗看起来总是很开心？因为它们的生活很汪洋恣肆！",
        "通用": "为什么程序员总是分不清万圣节和圣诞节？因为 Oct 31 = Dec 25！",
    }

    return jokes.get(topic, jokes["通用"])


# ===========================
# 创建Agent系统
# ===========================


def create_zoo_agents(api_key: str, callback: ColorfulConsoleCallback) -> Agent:
    """创建动物园的Agent系统"""

    # 创建LLM
    llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")

    # 创建工具
    tools = [
        Tool(search_animal_info),
        Tool(calculate_age),
        Tool(tell_joke),
    ]

    # 创建猫猫Agent
    cat_agent = Agent(
        llm=llm,
        tools=tools,
        name="猫猫",
        system_prompt="""你是一只可爱的猫咪助手，名叫"猫猫"。

重要规则：
1. 你的每一次回答都必须以"喵呜！"开头
2. 你要保持猫咪的可爱性格，说话要俏皮
3. 你可以使用工具来帮助回答问题
4. 回答要准确且有帮助

示例：
用户问："狗是什么动物？"
你的回答："喵呜！让我来告诉你关于狗的信息吧～（然后使用search_animal_info工具）"

记住：永远以"喵呜！"开头！""",
        max_iterations=5,
        callbacks=[callback],  # 添加共享的callback
    )

    # 创建狗狗Agent
    dog_agent = Agent(
        llm=llm,
        tools=tools,
        name="狗狗",
        system_prompt="""你是一只友善的狗狗助手，名叫"狗狗"。

重要规则：
1. 你的每一次回答都必须以"汪汪！"开头
2. 你要保持狗狗的热情性格，说话要充满活力
3. 你可以使用工具来帮助回答问题
4. 回答要准确且有帮助

示例：
用户问："猫是什么动物？"
你的回答："汪汪！让我来帮你查查猫的信息！（然后使用search_animal_info工具）"

记住：永远以"汪汪！"开头！""",
        max_iterations=5,
        callbacks=[callback],  # 添加共享的callback
    )

    # 创建园长Agent（主Agent）
    director_agent = Agent(
        llm=llm,
        tools=tools,
        subagents={"猫猫": cat_agent, "狗狗": dog_agent},
        name="动物园园长",
        system_prompt="""你是动物园的园长，负责管理两位动物助手。

你的团队：
- 猫猫：一只可爱的猫咪助手，擅长提供温柔细致的服务
- 狗狗：一只热情的狗狗助手，擅长提供活力满满的服务

重要规则：
1. 你不能直接回答用户的问题
2. 你必须选择猫猫或狗狗其中一位来回答问题
3. 选择标准：
   - 如果问题与猫相关，或需要细致温柔的回答 → 选择猫猫
   - 如果问题与狗相关，或需要热情活泼的回答 → 选择狗狗
   - 如果都不相关，根据问题的性质选择最合适的助手
4. 你要把用户的原始问题完整地委派给子Agent

记住：你只负责分配任务，不要自己回答！""",
        max_iterations=3,
        callbacks=[callback],  # 添加共享的callback
    )

    return director_agent


# ===========================
# 主函数
# ===========================


def main():
    """运行动物园园长示例"""

    print("\n" + "=" * 80)
    print("🦁 动物园园长系统 - 分层Agent演示")
    print("=" * 80)
    print("\n这个示例展示了分层Agent系统的工作方式：")
    print("  • 园长Agent负责决策，将任务分配给合适的动物助手")
    print("  • 猫猫Agent的回答总是以'喵呜！'开头")
    print("  • 狗狗Agent的回答总是以'汪汪！'开头")
    print("  • 每个Agent使用不同的颜色显示（紫色=园长，黄色=猫猫，蓝色=狗狗）")
    print()

    # 获取API key
    api_key = get_deepseek_api_key()
    if not api_key:
        print("❌ 错误: 找不到DeepSeek API key!")
        print("请在.env文件中设置 DEEPSEEK_API_KEY")
        return

    # 创建Agent系统
    print("🔧 正在初始化动物园Agent系统...")

    # 创建彩色callback，使用自定义颜色映射
    color_map = {
        "动物园园长": "\033[35m",  # 紫色 - 园长
        "园长": "\033[35m",  # 紫色 - 园长
        "猫猫": "\033[33m",  # 黄色 - 猫猫
        "狗狗": "\033[34m",  # 蓝色 - 狗狗
    }
    callback = ColorfulConsoleCallback(verbose=True, color_map=color_map)

    # 创建Agent系统（传入callback）
    director = create_zoo_agents(api_key, callback)

    # 测试问题列表
    test_questions = [
        "请告诉我关于猫的信息",
        "狗是什么样的动物？",
        "给我讲一个关于猫的笑话",
    ]

    # 让用户选择问题
    print("\n" + "=" * 80)
    print("请选择一个问题进行测试：")
    print("=" * 80)
    for i, question in enumerate(test_questions, 1):
        print(f"{i}. {question}")
    print(f"{len(test_questions) + 1}. 自定义问题")
    print()

    try:
        choice = input("请输入选项编号 (直接回车使用问题1): ").strip()

        if not choice:
            choice = "1"

        if choice.isdigit() and 1 <= int(choice) <= len(test_questions):
            question = test_questions[int(choice) - 1]
        elif choice.isdigit() and int(choice) == len(test_questions) + 1:
            question = input("\n请输入你的问题: ").strip()
            if not question:
                question = test_questions[0]
        else:
            print(f"无效选项，使用默认问题: {test_questions[0]}")
            question = test_questions[0]
    except Exception:
        question = test_questions[0]

    print("\n" + "=" * 80)
    print(f"🎯 测试问题: {question}")
    print("=" * 80)

    # 运行Agent
    response = director.run(question)

    # 显示摘要
    print("\n" + "=" * 80)
    print("📊 执行摘要")
    print("=" * 80)
    print(f"成功: {response.success}")
    print(f"迭代次数: {response.iterations}")

    if not response.success:
        print("\n⚠️  注意: Agent未能完成任务。这可能是因为：")
        print("   - LLM未按预期格式回答")
        print("   - 达到最大迭代次数")
        print("   - 发生了其他错误")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  程序被用户中断")
    except Exception as e:
        print(f"\n\n❌ 发生错误: {str(e)}")
        import traceback

        traceback.print_exc()
