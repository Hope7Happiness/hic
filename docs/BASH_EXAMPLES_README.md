# Bash Tool Examples

本目录包含两个展示 bash 工具的示例文件。

## 📄 文件对比

### ✅ `new_enhanced_bash_tool.py` - **推荐使用**

**使用新版增强 bash 工具**：`agent/tools/bash.py`

**特性：**
- ✅ 异步执行，支持 timeout 和 abort signals
- ✅ 返回结构化 `ToolResult` 对象（包含 metadata、attachments）
- ✅ Context 自动注入（Agent 自动管理）
- ✅ 权限系统（基于 Context 的细粒度控制）
- ✅ 自动输出截断（>2000行或>50KB 时保存到文件）
- ✅ 详细元数据（exit_code、duration_ms、working_dir）

**运行：**
```bash
python examples/new_enhanced_bash_tool.py
```

**代码示例：**
```python
from agent.tools.bash import bash  # NEW
from agent.tool import Tool

bash_tool = Tool(bash)  # Context 自动注入
agent = Agent(llm=llm, tools=[bash_tool])
```

---

### ⚠️ `builtin_tool_call.py` - **已过时但保留**

**使用旧版 bash 工具**：`agent/builtin_tools.py`

**状态：** DEPRECATED（已标记为过时）

**限制：**
- ❌ 同步执行，不支持 abort signals
- ❌ 只返回字符串，没有结构化结果
- ❌ 没有权限系统
- ❌ 没有自动输出截断
- ❌ 功能较少

**为什么保留：**
- 展示向后兼容性
- 帮助用户理解迁移过程
- 作为对比参考

**运行：**
```bash
python examples/builtin_tool_call.py  # 会显示 DeprecationWarning
```

---

## 🚀 快速开始

### 新用户 - 直接使用新版本

```python
# 1. 导入新版 bash 工具
from agent.tools.bash import bash, DEFAULT_SAFE_COMMANDS
from agent.tool import Tool

# 2. 创建工具（Context 会被 Agent 自动注入）
bash_tool = Tool(bash)

# 3. 创建 Agent
agent = Agent(llm=llm, tools=[bash_tool])

# 4. Agent 会自动管理 Context，无需手动配置
result = await agent._run_async("列出所有 Python 文件")
```

### 老用户 - 迁移到新版本

**只需修改一行 import：**

```python
# 旧版本
from agent.builtin_tools import restricted_bash

# 新版本
from agent.tools.bash import bash

# 其他代码保持不变！
bash_tool = Tool(bash)  # Context 自动注入
```

---

## 📊 功能对比

| 功能 | `builtin_tools.py` (旧) | `tools/bash.py` (新) |
|------|-------------------------|---------------------|
| 执行方式 | 同步 | 异步 ⭐ |
| 返回类型 | `str` | `ToolResult` ⭐ |
| 超时处理 | 基本 | 完善（支持 abort） ⭐ |
| 命令白名单 | ✅ | ✅ |
| 危险命令检测 | ❌ | ✅ ⭐ |
| 输出截断 | ❌ | ✅ 自动 ⭐ |
| 元数据 | ❌ | ✅ 详细 ⭐ |
| 权限系统 | ❌ | ✅ Context ⭐ |
| Agent 集成 | ✅ | ✅ 更好 ⭐ |

---

## 📖 详细文档

- **迁移指南**: `docs/BASH_TOOL_MIGRATION.md`
- **新工具源码**: `agent/tools/bash.py`
- **测试用例**: `tests/test_bash_tool.py`

---

## 💡 三个使用场景

### 场景 1: 与 Agent 集成（最常用）

```python
from agent.tools.bash import bash
from agent.tool import Tool

bash_tool = Tool(bash)  # Context 自动注入
agent = Agent(llm=llm, tools=[bash_tool])
```

### 场景 2: 直接调用（需要 Context）

```python
from agent.tools.bash import bash
from agent.context import create_auto_approve_context

ctx = create_auto_approve_context(patterns={"bash": ["*"]})
result = await bash("ls -la", ctx)

print(result.title)
print(result.output)
print(result.metadata)
```

### 场景 3: 使用 Tool 封装（推荐独立使用）

```python
from agent.tools.bash import bash
from agent.tool import Tool
from agent.context import create_auto_approve_context

ctx = create_auto_approve_context(patterns={"bash": ["*"]})
bash_tool = Tool(bash, context=ctx)

# Context 自动注入，无需传递
result = await bash_tool.call_async(command="ls -la")
```

---

## ⚙️ 运行要求

- Python 3.10+
- 设置 `DEEPSEEK_API_KEY` 在 `.env` 文件中
- 安装依赖: `pip install -r requirements.txt`

---

## 🎯 建议

- ✅ 新项目：直接使用 `new_enhanced_bash_tool.py` 作为模板
- ✅ 老项目：参考迁移指南更新到新版本
- ✅ 学习对比：同时看两个文件，理解改进之处

**问题？** 查看 `docs/BASH_TOOL_MIGRATION.md`
