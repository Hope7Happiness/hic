# Async Parallel Agents Example

这个示例演示了异步 Agent 框架的并行执行能力。

## 功能特性

- ✅ **真实 LLM**：使用 DeepSeek Chat 模型（非 Mock）
- ✅ **并行执行**：两个子 Agent 同时运行
- ✅ **异步日志**：彩色控制台输出 + 文件日志
- ✅ **状态追踪**：Agent 启动、挂起、恢复、完成的完整生命周期

## 场景说明

**Parent Agent（父 Agent）**
- 协调两个子 Agent 的工作
- 使用 `launch_subagents` 同时启动两个子 Agent
- 使用 `wait_for_subagents` 等待完成

**Fast Agent（快速子 Agent）**
- 任务：睡眠 3 秒
- 执行时间：~10 秒（3s 睡眠 + ~7s LLM 交互）

**Slow Agent（慢速子 Agent）**
- 任务：睡眠 8 秒
- 执行时间：~15 秒（8s 睡眠 + ~7s LLM 交互）

## 预期结果

### 并行执行
- 两个子 Agent 几乎同时启动（时间差 < 0.01s）
- 并行执行时间 = max(10s, 15s) = **~15 秒**

### 如果是顺序执行
- Fast Agent 先执行：10 秒
- Slow Agent 后执行：15 秒
- 总时间 = 10s + 15s = **25 秒**

## 运行示例

```bash
# 1. 确保已安装依赖
pip install -r requirements.txt

# 2. 设置 DeepSeek API Key
export DEEPSEEK_API_KEY="your-api-key-here"

# 3. 运行示例
python examples/async_parallel_agents.py
```

## 输出示例

```
======================================================================
Async Agent Example with Real LLM
======================================================================

Starting parent agent...
Expected: FastAgent (3s) and SlowAgent (8s) run in parallel
Total time should be ~8 seconds, not ~11 seconds

  0.052s [INFO] [ParentAgent] [AGENT] 🚀 Started with task: ...
  2.407s [INFO] [FastAgent] [AGENT] 🚀 Started with task: 睡眠3秒
  2.410s [INFO] [SlowAgent] [AGENT] 🚀 Started with task: 睡眠8秒
 11.618s [INFO] [FastAgent] [AGENT] ✅ Finished: 已完成3秒睡眠任务
 18.357s [INFO] [SlowAgent] [AGENT] ✅ Finished: 已完成8秒睡眠任务
 28.412s [INFO] [ParentAgent] [AGENT] ✅ Finished: 所有子Agent任务执行完毕

======================================================================
Results
======================================================================
Success: True
Iterations: 4
Total Time: 28.36s

Agent Execution Times (from logs):
  FastAgent: 2026-01-25 22:43:48.208 -> 2026-01-25 22:43:57.419
  SlowAgent: 2026-01-25 22:43:48.212 -> 2026-01-25 22:44:04.159

✅ Both agents started at nearly the same time - parallel execution confirmed!
   FastAgent: 3s sleep + ~7s LLM calls = ~10s total
   SlowAgent: 8s sleep + ~7s LLM calls = ~15s total
   Parallel execution means total = max(10s, 15s) = ~15s
   If sequential: 10s + 15s = 25s

Logs saved to: logs/
```

## 日志文件

执行后会在 `logs/` 目录生成以下文件：

- `ParentAgent_YYYYMMDD_HHMMSS_*.log` - 父 Agent 的日志
- `FastAgent_YYYYMMDD_HHMMSS_*.log` - 快速子 Agent 的日志
- `SlowAgent_YYYYMMDD_HHMMSS_*.log` - 慢速子 Agent 的日志

日志包含：
- 时间戳（毫秒级）
- 日志级别
- Agent 名称
- 分类标签（AGENT、TOOL、LLM）
- 消息内容

## 技术细节

### 异步执行流程

1. **ParentAgent 启动** → 发送初始任务给 LLM
2. **LLM 返回** → `Action: launch_subagents`
3. **启动子 Agent** → 创建两个异步任务（非阻塞）
4. **ParentAgent 挂起** → `Action: wait_for_subagents`
5. **子 Agent 并行执行** → FastAgent 和 SlowAgent 同时运行
6. **FastAgent 完成** → 发送消息唤醒 ParentAgent
7. **ParentAgent 恢复** → 检查状态，继续等待 SlowAgent
8. **SlowAgent 完成** → 再次唤醒 ParentAgent
9. **ParentAgent 完成** → `Action: finish` 返回最终结果

### 关键代码

```python
# 创建带有 sleep 工具的子 Agent
def create_fast_subagent() -> Agent:
    sleep_tool = Tool(sleep)  # sleep 是一个普通的 Python 函数
    llm = DeepSeekLLM(api_key=api_key, model="deepseek-chat")
    return Agent(llm=llm, tools=[sleep_tool], name="FastAgent")

# 在异步环境中运行
async def main():
    logger = await init_logger(log_dir="logs")
    parent_agent = create_parent_agent()
    result = await parent_agent._run_async(task="...")
    await close_logger()
```

## 注意事项

1. **API Key**：需要有效的 DeepSeek API Key
2. **网络连接**：需要能够访问 DeepSeek API
3. **执行时间**：总时间包括 LLM 调用时间（~10-15 秒）+ 子 Agent 执行时间（~15 秒）
4. **并发性**：子 Agent 的并行执行已通过时间戳验证

## 扩展

你可以基于这个示例：
- 添加更多子 Agent
- 使用不同的工具
- 创建更深的 Agent 层级
- 实现自定义的日志格式
- 添加错误处理和重试逻辑
