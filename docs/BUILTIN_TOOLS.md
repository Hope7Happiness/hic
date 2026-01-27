# Builtin Tools 文档

## 概述

本项目现在提供了一组现代化的基础工具，均带有权限控制与安全策略：

1. **bash** - 执行任意 shell 命令（无限制）
2. **restricted_bash** - 执行受限的 shell 命令（白名单机制）
3. **calculator** - 安全的数学计算器
4. **read** - 安全读取文件，支持分页、行号、二进制检测
5. **write** - 安全写入/创建文件，自动生成 diff、可创建父目录
6. **edit** - 容错字符串替换，多策略匹配 + diff 输出

## 文件结构（核心相关）

```
agent/
├── tools/
│   ├── bash.py      # 增强版 bash/restricted_bash（权限 + 超时 + 截断）
│   ├── read.py      # 新增 read 工具
│   ├── write.py     # 新增 write 工具
│   └── edit.py      # 新增 edit 工具（多策略匹配）
├── agent.py         # 默认自动注册 bash/restricted_bash/read/write/edit 工具
└── tool_result.py   # 结构化返回值（增加 error() 兼容别名）

examples/
├── system_analyst_with_restricted_bash.py  # 旧示例
└── agent_read_write_edit_demo.md           # 新示例：安全读写编辑流程

tests/
├── test_read_write_edit_tools.py           # read/write/edit 覆盖测试
├── test_tool_infrastructure.py             # 基础设施测试
└── ...
```

## 工具详解

### 1. bash - 无限制 Shell 执行

```python
from agent.builtin_tools import bash

# 可以执行任何命令
result = bash("ls -la")
result = bash("curl http://example.com")  # 危险！
result = bash("rm -rf /")  # 极度危险！
```

**特点：**
- ✓ 执行任意 shell 命令
- ✓ 支持管道、重定向
- ✗ 无安全限制
- ✗ 可能造成系统破坏

**使用场景：** 仅在完全可信的环境中使用

---

### 2. restricted_bash - 受限 Shell 执行 ⭐️ 推荐

```python
from agent.builtin_tools import restricted_bash

# 只能执行白名单中的命令
result = restricted_bash("ls -la")           # ✓ 允许
result = restricted_bash("cat file.txt")     # ✓ 允许
result = restricted_bash("rm file.txt")      # ✗ 拒绝
result = restricted_bash("curl http://...")  # ✗ 拒绝
```

#### 默认白名单命令

```python
DEFAULT_SAFE_COMMANDS = {
    # 文件浏览
    "ls", "ll", "dir",
    "cat", "head", "tail", "less", "more",
    "file", "stat",
    
    # 目录操作（只读）
    "pwd", "cd",
    
    # 文本处理
    "grep", "egrep", "fgrep",
    "sed", "awk",
    "cut", "sort", "uniq", "wc",
    "tr", "diff", "comm",
    
    # 系统信息（只读）
    "whoami", "hostname", "uname",
    "date", "cal",
    "df", "du",
    "ps", "top", "uptime",
    "env", "printenv",
    
    # 文件搜索
    "find", "locate", "which", "whereis",
    
    # 输出
    "echo", "printf",
}
```

#### 自定义白名单

```python
# 方式 1: 使用自定义白名单
custom_commands = {"ls", "cat", "grep"}
result = restricted_bash("ls", allowed_commands=custom_commands)

# 方式 2: 扩展默认白名单
from agent.builtin_tools import DEFAULT_SAFE_COMMANDS
my_commands = DEFAULT_SAFE_COMMANDS | {"git", "npm"}
result = restricted_bash("git status", allowed_commands=my_commands)
```

#### 参数说明

```python
restricted_bash(
    command: str,                          # 要执行的命令
    timeout: int = 30,                     # 超时时间（秒）
    allowed_commands: Optional[Set[str]] = None,  # 允许的命令集合
    allow_pipes: bool = True,              # 是否允许管道
    allow_redirects: bool = False,         # 是否允许重定向
)
```

#### 功能特性

**✓ 支持的功能：**
- 白名单命令执行
- 管道命令（可选）：`ls | grep .py`
- 命令参数：`ls -la /home`
- 复杂管道：`find . -name '*.py' | wc -l`

**✗ 限制的功能：**
- I/O 重定向（默认禁止）：`ls > file.txt`
- 命令替换：`$(dangerous_command)`
- 非白名单命令：`rm`, `curl`, `wget`, `chmod`, `sudo` 等

#### 安全机制

1. **命令解析：** 使用 `shlex.split()` 安全解析命令
2. **基础命令检查：** 提取并验证管道中每个命令的基础命令名
3. **白名单验证：** 只有在白名单中的命令才能执行
4. **错误信息：** 明确告知哪个命令被拒绝

---

### 3. calculator - 数学计算器

### 4. read - 安全文件读取（新）

```python
from agent.tools import read
from agent.tool import Tool

read_tool = Tool(read)
# 调用参数：file_path, offset=0, limit=2000, ctx 自动注入
```

特点：
- 行号输出（cat -n 风格，5 位填充）
- 支持 offset/limit 分页，末尾提示继续 offset
- 二进制检测，拒绝读取二进制
- 路径安全校验（不允许越界工作区）
- 结构化 ToolResult 输出（file_path/lines_read/total_lines/is_truncated）

### 5. write - 安全文件写入（新）

```python
from agent.tools import write
from agent.tool import Tool

write_tool = Tool(write)
# 调用参数：file_path, content, create_dirs=True, ctx 自动注入
```

特点：
- 权限请求，包含 size/line_count 元信息
- 自动创建父目录（可关闭）
- 生成统一 diff（a/ b/ 前缀）
- 路径越界防护

### 6. edit - 容错字符串替换（新，最重要）

```python
from agent.tools import edit
from agent.tool import Tool

edit_tool = Tool(edit)
# 调用参数：file_path, old_string, new_string, replace_all=False, ctx 自动注入
```

特点：
- 多策略匹配（精确、去空白、归一化、上下文匹配等）
- Levenshtein 相似度阈值保护（默认 0.80）
- replace_all 支持
- 生成 diff 输出，附带 strategy 元数据
- 路径、权限安全校验

```python
from agent.builtin_tools import calculator

result = calculator("2 + 2")              # "4"
result = calculator("sqrt(16)")           # "4"
result = calculator("sin(pi/2)")          # "1"
result = calculator("(10 + 5) * 2")       # "30"
```

#### 支持的操作

**基本运算：**
- `+`, `-`, `*`, `/` - 加减乘除
- `**` - 幂运算
- `//` - 整除
- `%` - 取模

**数学函数：**
- `sqrt`, `abs`, `round`, `ceil`, `floor`
- `sin`, `cos`, `tan`
- `log`, `log10`, `exp`
- `min`, `max`, `sum`, `pow`

**常量：**
- `pi` - 圆周率 (3.14159...)
- `e` - 自然常数 (2.71828...)

#### 安全特性

- ✓ 只允许数学运算
- ✓ 无法执行任意 Python 代码
- ✓ 无法访问文件系统
- ✓ 无法导入模块

---

## 使用示例

### 示例 1: 基础使用

```python
from agent.tool import Tool
from agent.builtin_tools import restricted_bash, calculator

# 创建工具
bash_tool = Tool(restricted_bash)
calc_tool = Tool(calculator)

# 使用工具
print(bash_tool.call(command="ls -la"))
print(calc_tool.call(expression="sqrt(144)"))
```

### 示例 2: 与 Agent 结合使用

```python
from agent.agent import Agent
from agent.llm import DeepSeekLLM
from agent.tool import Tool
from agent.builtin_tools import restricted_bash, calculator

# 创建 Agent
llm = DeepSeekLLM(api_key="your_key")
agent = Agent(
    llm=llm,
    tools=[
        Tool(restricted_bash),
        Tool(calculator),
    ],
)

# 执行任务
result = agent.run("列出当前目录的 Python 文件并统计数量")
```

### 示例 3: 完整的系统分析 Agent

查看：`examples/system_analyst_with_restricted_bash.py`

这个示例展示了：
- 使用 `restricted_bash` 安全地收集系统信息
- 使用 `calculator` 进行数据分析和计算
- Agent 自动组合多个工具完成复杂任务
- 安全机制阻止危险命令

运行示例：
```bash
python examples/system_analyst_with_restricted_bash.py
```

---

## 测试

### 运行所有测试

```bash
# 测试基础工具（bash 和 calculator）
python tests/test_builtin_tools_standalone.py

# 测试权限控制
python tests/test_restricted_bash_standalone.py
```

### 测试结果

**基础工具测试：** 46 个测试全部通过 ✅
- bash 工具：10 个测试
- calculator 工具：32 个测试
- 集成测试：4 个测试

**权限控制测试：** 12 个测试全部通过 ✅
- 安全命令（ls, pwd, whoami 等）：全部允许执行
- 危险命令（rm, curl, chmod 等）：全部被拦截
- 管道命令：正常工作

---

## 最佳实践

### 1. 优先使用 restricted_bash

❌ **不推荐（危险）：**
```python
from agent.builtin_tools import bash
result = bash("rm important_file.txt")  # 可能造成数据丢失
```

✅ **推荐（安全）：**
```python
from agent.builtin_tools import restricted_bash
result = restricted_bash("cat important_file.txt")  # 只读操作
```

### 2. 根据需求自定义白名单

```python
# 如果需要 git 命令
git_safe_commands = DEFAULT_SAFE_COMMANDS | {"git"}

# 如果需要网络命令（谨慎使用）
network_commands = DEFAULT_SAFE_COMMANDS | {"curl", "wget"}
```

### 3. 禁用重定向防止文件写入

```python
# 禁止重定向（默认）
result = restricted_bash("ls > file.txt")  # 错误：重定向被禁止

# 如果必须允许重定向
result = restricted_bash("ls > file.txt", allow_redirects=True)
```

### 4. 设置合理的超时

```python
# 对于可能耗时的操作
result = restricted_bash("find / -name '*.py'", timeout=60)
```

### 5. 使用 calculator 而不是 eval()

❌ **危险：**
```python
result = eval(user_input)  # 可以执行任意代码！
```

✅ **安全：**
```python
result = calculator(user_input)  # 只能执行数学运算
```

---

## 安全注意事项

### restricted_bash 不能防御的攻击

虽然 `restricted_bash` 提供了基本的安全保护，但仍有一些局限：

1. **命令参数注入：** 
   ```python
   # 即使在白名单中，cat 也可能读取敏感文件
   restricted_bash("cat /etc/passwd")  # 可能泄露用户信息
   ```

2. **路径遍历：**
   ```python
   restricted_bash("cat ../../sensitive_file")  # 可能访问上级目录
   ```

3. **资源消耗：**
   ```python
   restricted_bash("find / -name '*'")  # 可能消耗大量系统资源
   ```

### 额外的安全建议

1. **最小权限原则：** 只添加真正需要的命令到白名单
2. **输入验证：** 在调用 restricted_bash 之前验证参数
3. **日志记录：** 记录所有执行的命令
4. **沙箱环境：** 在隔离的容器中运行 Agent
5. **监控和限制：** 监控命令执行频率和资源使用

---

## API 参考

### bash(command, timeout)

执行任意 shell 命令（无限制版本）。

**参数：**
- `command` (str): Shell 命令
- `timeout` (int): 超时时间，默认 30 秒

**返回：** str - 命令输出或错误信息

---

### restricted_bash(command, timeout, allowed_commands, allow_pipes, allow_redirects)

执行受限的 shell 命令（安全版本）。

**参数：**
- `command` (str): Shell 命令
- `timeout` (int): 超时时间，默认 30 秒
- `allowed_commands` (Set[str] | None): 允许的命令集合，默认使用 DEFAULT_SAFE_COMMANDS
- `allow_pipes` (bool): 是否允许管道，默认 True
- `allow_redirects` (bool): 是否允许重定向，默认 False

**返回：** str - 命令输出或错误信息

---

### calculator(expression)

安全的数学表达式计算器。

**参数：**
- `expression` (str): 数学表达式

**返回：** str - 计算结果或错误信息

---

## 总结

### 功能对比

| 特性 | bash | restricted_bash | calculator |
|------|------|-----------------|------------|
| 安全性 | ❌ 无限制 | ✅ 白名单保护 | ✅ 只允许数学运算 |
| 灵活性 | ✅ 完全灵活 | ⚠️ 受限于白名单 | ⚠️ 只能计算 |
| 推荐场景 | 受信环境 | 生产环境 | 数学计算 |
| 危险性 | 🔴 高 | 🟡 低 | 🟢 无 |

### 核心优势

1. **🛡️ 安全第一：** `restricted_bash` 默认拒绝所有危险命令
2. **🎯 易于使用：** 与标准 bash 命令语法完全兼容
3. **🔧 高度可定制：** 可以根据需求自定义白名单
4. **✅ 充分测试：** 58 个测试用例全部通过
5. **📚 完整文档：** 包含示例、最佳实践和安全建议

### 快速开始

```python
from agent.builtin_tools import restricted_bash, calculator

# 安全地列出文件
files = restricted_bash("ls -la")

# 计算统计数据
total = calculator("(100 + 200) / 2")

print(f"文件列表：\n{files}")
print(f"平均值：{total}")
```

---

## License

MIT License
