# 动物园园长示例 - 分层Agent实现总结

**创建时间:** 2026-01-25  
**状态:** ✅ 完成  
**文件:** `examples/zoo_director.py`

## 概述

成功实现了一个有趣的分层Agent系统示例，展示了父Agent如何将任务委派给具有不同"性格"的子Agent。

## 功能特点

### 1. **三层Agent架构**

```
动物园园长 (Director) 🦁
    ├── 猫猫 (Cat Agent) 🐱
    │   └── 回答必须以"喵呜！"开头
    └── 狗狗 (Dog Agent) 🐶
        └── 回答必须以"汪汪！"开头
```

### 2. **彩色Console Callback（ColorfulConsoleCallback）**

实现了增强版的Console回调系统，支持：
- **不同Agent使用不同颜色**：
  - 紫色 (`\033[35m`) - 园长Agent
  - 黄色 (`\033[33m`) - 猫猫Agent
  - 蓝色 (`\033[34m`) - 狗狗Agent
- **Agent调用栈跟踪**：使用缩进显示嵌套层级
- **完整的生命周期日志**：
  - Agent启动/完成
  - 迭代开始/结束
  - LLM请求/响应
  - 工具调用/结果
  - 子Agent委派/返回

### 3. **角色扮演系统**

每个Agent有独特的性格：

**猫猫Agent:**
```python
system_prompt="""你是一只可爱的猫咪助手，名叫"猫猫"。

重要规则：
1. 你的每一次回答都必须以"喵呜！"开头
2. 你要保持猫咪的可爱性格，说话要俏皮
3. 你可以使用工具来帮助回答问题
4. 回答要准确且有帮助
"""
```

**狗狗Agent:**
```python
system_prompt="""你是一只友善的狗狗助手，名叫"狗狗"。

重要规则：
1. 你的每一次回答都必须以"汪汪！"开头
2. 你要保持狗狗的热情性格，说话要充满活力
3. 你可以使用工具来帮助回答问题
4. 回答要准确且有帮助
"""
```

**园长Agent:**
```python
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

记住：你只负责分配任务，不要自己回答！
"""
```

### 4. **工具集成**

提供三个工具给所有Agent使用：
1. **`search_animal_info(animal)`** - 查询动物信息
2. **`calculate_age(birth_year)`** - 计算年龄
3. **`tell_joke(topic)`** - 讲笑话

### 5. **交互式用户界面**

```python
请选择一个问题进行测试：
1. 请告诉我关于猫的信息
2. 狗是什么样的动物？
3. 给我讲一个关于猫的笑话
4. 自定义问题
```

## 实现细节

### 核心创建函数

```python
def create_zoo_agents(api_key: str, callback: ColorfulConsoleCallback) -> Agent:
    """创建动物园的Agent系统"""
    
    llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")
    tools = [Tool(search_animal_info), Tool(calculate_age), Tool(tell_joke)]
    
    # 创建子Agent，共享callback
    cat_agent = Agent(llm=llm, tools=tools, name="猫猫", 
                     system_prompt="...", callbacks=[callback])
    dog_agent = Agent(llm=llm, tools=tools, name="狗狗", 
                     system_prompt="...", callbacks=[callback])
    
    # 创建园长Agent，包含子Agent
    director = Agent(llm=llm, tools=tools, 
                    subagents={"猫猫": cat_agent, "狗狗": dog_agent},
                    name="动物园园长", system_prompt="...", 
                    callbacks=[callback])
    
    return director
```

### ColorfulConsoleCallback关键特性

```python
class ColorfulConsoleCallback(AgentCallback):
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._agent_stack = []  # 跟踪Agent调用栈
        
    def _get_agent_color(self, agent_name: str) -> str:
        """根据agent名称返回颜色代码"""
        if "园长" in agent_name: return "\033[35m"  # 紫色
        elif "猫猫" in agent_name: return "\033[33m"  # 黄色
        elif "狗狗" in agent_name: return "\033[34m"  # 蓝色
        else: return "\033[36m"  # 青色
    
    def _log(self, message: str, agent_name: str = None, level: str = "INFO"):
        """打印带颜色的日志"""
        color = self._get_agent_color(agent_name) if agent_name else "..."
        print(f"{color}{message}{reset}")
    
    def on_agent_start(self, task: str, agent_name: str):
        self._agent_stack.append(agent_name)
        indent = "  " * (len(self._agent_stack) - 1)
        # 使用缩进显示嵌套层级
        
    def on_agent_finish(self, success: bool, iterations: int, content: str):
        agent_name = self._agent_stack.pop()
        # 恢复父Agent上下文
```

## 执行示例

### 问题1: "请告诉我关于猫的信息"

```
[紫色] 🚀 动物园园长 开始工作
[紫色] 📋 任务: 请告诉我关于猫的信息

[紫色] 🔄 迭代 1
[紫色] 👉 园长委派任务给: 猫猫

  [黄色] 🤖 子Agent '猫猫' 开始处理
  [黄色] 📋 任务: 请详细介绍一下关于猫的信息
  
  [黄色] 🔄 迭代 1
  [黄色] 🧠 LLM响应:
  [黄色]    喵呜！让我来详细介绍一下我们猫咪家族吧～
  
  [黄色] 🔧 调用工具: search_animal_info
  [黄色] ✅ 工具结果: 猫是一种小型哺乳动物...
  
  [黄色] ✅ 猫猫 完成

[紫色] ✅ 猫猫 完成任务
[紫色] 📄 返回结果: 喵呜！让我来告诉你关于我们猫咪的可爱信息吧～...

[紫色] 🏁 动物园园长 工作完成
[紫色] ✅ 成功: True
[紫色] 🔄 迭代次数: 2
[紫色] ⏱️  总耗时: 22.42秒
```

### 问题2: "狗是什么样的动物？"

```
[紫色] 🚀 动物园园长 开始工作
[紫色] 📋 任务: 狗是什么样的动物？

[紫色] 🔄 迭代 1
[紫色] 👉 园长委派任务给: 狗狗

  [蓝色] 🤖 子Agent '狗狗' 开始处理
  [蓝色] 📋 任务: 用户想了解关于狗这种动物的特点...
  
  [蓝色] 🔄 迭代 1
  [蓝色] 🧠 LLM响应:
  [蓝色]    汪汪！让我来热情地介绍一下我们狗狗的特点吧！
  
  [蓝色] 🔧 调用工具: search_animal_info
  [蓝色] ✅ 工具结果: 狗是人类最忠诚的朋友...
  
  [蓝色] ✅ 狗狗 完成

[紫色] ✅ 狗狗 完成任务
[紫色] 📄 返回结果: 汪汪！让我用最热情的方式介绍一下我们狗狗的特点吧！...

[紫色] 🏁 动物园园长 工作完成
[紫色] ✅ 成功: True
[紫色] 🔄 迭代次数: 2
[紫色] ⏱️  总耗时: 27.78秒
```

## 测试结果

### ✅ 验证项目

1. **父Agent委派** - 园长成功将问题委派给合适的子Agent
2. **子Agent响应格式** - 猫猫始终以"喵呜！"开头，狗狗始终以"汪汪！"开头
3. **颜色区分** - 三个Agent使用不同颜色显示，易于区分
4. **工具使用** - 子Agent成功调用工具（search_animal_info）
5. **嵌套显示** - 子Agent的输出使用缩进，显示层级关系
6. **完整流程** - 从园长开始到子Agent完成，整个流程清晰可见

### 性能指标

- **平均执行时间**: 22-28秒（包含2个LLM调用 + 1个工具调用）
- **成功率**: 100% (测试了2个不同问题)
- **响应质量**: 子Agent都正确遵守了"喵呜！"和"汪汪！"的规则

## 技术亮点

### 1. **Callback共享**
```python
# 关键：子Agent和父Agent共享同一个callback实例
callback = ColorfulConsoleCallback(verbose=True)
cat_agent = Agent(..., callbacks=[callback])
dog_agent = Agent(..., callbacks=[callback])
director = Agent(..., callbacks=[callback])
```

这样确保了所有Agent的事件都通过同一个callback处理，可以维护全局状态（如agent_stack）。

### 2. **Agent调用栈管理**
```python
def on_agent_start(self, task: str, agent_name: str):
    self._agent_stack.append(agent_name)
    indent = "  " * (len(self._agent_stack) - 1)
    
def on_agent_finish(self, success: bool, iterations: int, content: str):
    agent_name = self._agent_stack.pop()
    self._current_agent = self._agent_stack[-1] if self._agent_stack else None
```

使用栈结构跟踪当前的Agent调用层级，实现正确的缩进显示。

### 3. **动态颜色选择**
```python
def _get_agent_color(self, agent_name: str) -> str:
    if "园长" in agent_name or "Director" in agent_name:
        return self.COLORS["DIRECTOR"]
    elif "猫猫" in agent_name or "Cat" in agent_name:
        return self.COLORS["CAT"]
    elif "狗狗" in agent_name or "Dog" in agent_name:
        return self.COLORS["DOG"]
    else:
        return self.COLORS["DEFAULT"]
```

根据Agent名称自动选择颜色，支持中英文。

## 教育价值

这个示例非常适合用来展示：

1. **分层Agent架构** - 如何构建父子Agent关系
2. **任务委派** - 如何根据任务特点选择合适的子Agent
3. **个性化Agent** - 如何通过system_prompt赋予Agent独特性格
4. **可视化调试** - 如何使用颜色和缩进让执行流程清晰可见
5. **Callback扩展** - 如何自定义Callback实现特殊功能

## 文档更新

### README.md
- 在"Hierarchical Agents"部分添加了完整的动物园示例
- 展示了如何创建具有个性的子Agent
- 说明了彩色输出和嵌套执行的特点

### README_human.md
- 在"Run Examples"部分将`zoo_director.py`标记为推荐示例🌟
- 添加了"Featured Demos"部分，详细介绍了两个重点示例
- 在项目结构中添加了zoo_director.py的说明

## 使用方法

```bash
# 运行示例
cd /home/zhh/Documents/Github/hic
source .venv/bin/activate
python examples/zoo_director.py

# 选择测试问题
# 1. 请告诉我关于猫的信息 → 会委派给猫猫
# 2. 狗是什么样的动物？ → 会委派给狗狗
# 3. 给我讲一个关于猫的笑话 → 会委派给猫猫
# 4. 自定义问题 → 园长会智能选择
```

## 可能的扩展

1. **添加更多动物Agent** - 如兔兔、鸟鸟等
2. **实现Agent协作** - 多个子Agent共同完成任务
3. **添加状态管理** - Agent之间共享信息
4. **实现更复杂的选择逻辑** - 基于任务复杂度、历史表现等因素选择
5. **添加性能监控** - 跟踪每个Agent的响应时间和成功率

## 总结

✅ 成功创建了一个有趣且功能完整的分层Agent示例  
✅ 实现了支持多颜色的增强版ConsoleCallback  
✅ 展示了Agent个性化和角色扮演的能力  
✅ 提供了清晰的可视化输出，便于理解执行流程  
✅ 完善了文档，让用户轻松上手  

这个示例不仅展示了技术能力，也增加了框架的趣味性和易用性！🎉
