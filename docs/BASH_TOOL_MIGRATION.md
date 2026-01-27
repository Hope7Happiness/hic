# Bash Tool 迁移指南

## 概述

`agent/builtin_tools.py` 中的 `bash()` 和 `restricted_bash()` 已被标记为 **DEPRECATED**。

新版本位于 `agent/tools/bash.py`，提供更强大的功能和更好的集成。

## 为什么要迁移？

### 旧版本的限制
- ❌ 同步执行，不支持 abort signals
- ❌ 只返回字符串，没有结构化结果
- ❌ 没有权限系统
- ❌ 没有自动输出截断
- ❌ 简单的错误处理

### 新版本的优势
- ✅ 异步执行，支持 timeout 和 abort signals
- ✅ 返回 `ToolResult` 对象（title、output、metadata、attachments）
- ✅ 基于 Context 的权限系统
- ✅ 自动输出截断（2000行/50KB），超过部分写入文件
- ✅ 工作目录验证
- ✅ 详细的元数据（exit_code、duration_ms、working_dir）
- ✅ 与 Agent 完美集成（自动注入 Context）

## 迁移步骤

### 1. 基本使用（与 Agent 集成）

**旧代码：**
```python
from agent.builtin_tools import restricted_bash, calculator
from agent.tool import Tool
from agent.agent import Agent

bash_tool = Tool(restricted_bash)
calc_tool = Tool(calculator)

agent = Agent(llm=llm, tools=[bash_tool, calc_tool])
```

**新代码：**
```python
from agent.tools.bash import bash  # 新版 bash 工具
from agent.builtin_tools import calculator  # calculator 未 deprecated
from agent.tool import Tool
from agent.agent import Agent

bash_tool = Tool(bash)  # Context 会被 Agent 自动注入
calc_tool = Tool(calculator)

agent = Agent(llm=llm, tools=[bash_tool, calc_tool])
```

**变化说明：**
- ✅ Agent 会自动创建 Context 并注入到工具中
- ✅ Tool 类已支持 async 函数
- ✅ 不需要手动管理 Context
- ✅ API 几乎相同，只需修改 import

### 2. 直接调用（不使用 Agent）

**旧代码：**
```python
from agent.builtin_tools import restricted_bash

result = restricted_bash("ls -la")
print(result)  # 字符串
```

**新代码：**
```python
import asyncio
from agent.tools.bash import bash
from agent.context import create_auto_approve_context

async def main():
    # 创建 context（自动批准所有命令）
    ctx = create_auto_approve_context(patterns={"bash": ["*"]})
    
    # 调用工具
    result = await bash("ls -la", ctx)
    
    # result 是 ToolResult 对象
    print(f"Title: {result.title}")
    print(f"Output: {result.output}")
    print(f"Exit code: {result.metadata['exit_code']}")
    print(f"Duration: {result.metadata['duration_ms']}ms")

asyncio.run(main())
```

### 3. 限制允许的命令（restricted_bash 替代）

**旧代码：**
```python
from agent.builtin_tools import restricted_bash, DEFAULT_SAFE_COMMANDS

# 只允许安全命令
result = restricted_bash("ls -la")
```

**新代码：**
```python
from agent.tools.bash import bash, DEFAULT_SAFE_COMMANDS
from agent.context import create_auto_approve_context

async def main():
    ctx = create_auto_approve_context(patterns={"bash": ["*"]})
    
    # 使用 allowed_commands 参数限制命令
    result = await bash("ls -la", ctx, allowed_commands=DEFAULT_SAFE_COMMANDS)
    
    # 或者自定义白名单
    custom_safe_commands = {"ls", "cat", "grep", "echo"}
    result = await bash("ls", ctx, allowed_commands=custom_safe_commands)

asyncio.run(main())
```

### 4. 使用 Tool 类（推荐）

如果你想在非 Agent 环境中使用，但又想保持简洁的 API：

```python
import asyncio
from agent.tools.bash import bash
from agent.tool import Tool
from agent.context import create_auto_approve_context

async def main():
    # 创建 context
    ctx = create_auto_approve_context(patterns={"bash": ["*"]})
    
    # 创建 tool（注入 context）
    bash_tool = Tool(bash, context=ctx)
    
    # 调用工具（context 自动传递）
    result = await bash_tool.call_async(command="ls -la")
    
    print(str(result))  # 自动格式化为 LLM 友好的字符串

asyncio.run(main())
```

## 向后兼容性

旧的 `agent/builtin_tools.py` 中的函数**仍然可用**，但会显示 deprecation 警告：

```python
from agent.builtin_tools import restricted_bash

result = restricted_bash("ls")  
# DeprecationWarning: agent.builtin_tools.restricted_bash() is deprecated.
# Use agent.tools.bash.bash() with allowed_commands parameter for better features.
```

## 功能对比表

| 功能 | 旧版 `builtin_tools.bash` | 新版 `tools.bash.bash` |
|------|---------------------------|------------------------|
| 返回类型 | `str` | `ToolResult` |
| 执行方式 | 同步 | 异步 |
| 超时处理 | ✅ 基本 | ✅ 完善（abort signals） |
| 命令白名单 | ✅ `allowed_commands` | ✅ `allowed_commands` |
| 危险命令检测 | ❌ | ✅ |
| 输出截断 | ❌ | ✅ 自动（2000行/50KB） |
| 元数据 | ❌ | ✅ exit_code, duration_ms, etc. |
| 权限系统 | ❌ | ✅ 基于 Context |
| 工作目录验证 | ❌ | ✅ |
| 与 Agent 集成 | ✅ | ✅ (更好) |
| Abort 支持 | ❌ | ✅ |

## 常见问题

### Q: 我必须立即迁移吗？
A: 不必。旧版本仍然可用，但建议尽快迁移以获得新功能和更好的性能。

### Q: calculator 也被 deprecated 了吗？
A: **没有**。`calculator()` 仍然是推荐使用的，没有被标记为 deprecated。

### Q: 新版本的 API 复杂吗？
A: 与 Agent 集成时，API 几乎相同。只需要修改 import 语句。

### Q: 我可以同时使用新旧两个版本吗？
A: 可以，但不建议。选择一个版本并保持一致性。

### Q: 新版本的测试覆盖如何？
A: 新版本有完整的测试套件（8个测试用例，全部通过），包括：
- 命令提取和验证
- 安全性检查
- 超时处理
- 工作目录验证
- 输出截断
- 元数据生成

## 测试你的迁移

运行测试以确保新版本正常工作：

```bash
# 测试新 bash 工具
python tests/test_bash_tool.py

# 测试旧版本（确保向后兼容）
python tests/test_builtin_tools.py
```

## 获取帮助

如果你在迁移过程中遇到问题：

1. 查看新 bash 工具的测试：`tests/test_bash_tool.py`
2. 查看示例代码：`examples/builtin_tool_call.py`（待更新）
3. 查看源码注释：`agent/tools/bash.py`

## 时间表

- ✅ **2026-01** - 新版本发布，旧版本标记为 deprecated
- 📅 **2026-03** - 旧版本将在 deprecation 警告中添加更严格的提示
- 📅 **2026-06** - 旧版本可能被移除（具体时间待定）

---

**建议：** 尽快迁移到新版本以获得最佳体验！
