# 快速迁移指南

## 从旧版本迁移到新版本

### 最小改动 (推荐)

只需要修改导入语句：

```python
# 之前
from agent import LLM

# 之后
from agent import OpenAILLM

# 或者使用别名保持代码不变
from agent import OpenAILLM as LLM
```

### 代码示例对比

#### 基本用法

```python
# ═══════════════════════════════════════════════════════════════
# 旧版本
# ═══════════════════════════════════════════════════════════════
from agent import LLM, Agent, Tool

llm = LLM(model="gpt-4", temperature=0.7)
agent = Agent(llm=llm, tools=tools)

# ═══════════════════════════════════════════════════════════════
# 新版本
# ═══════════════════════════════════════════════════════════════
from agent import OpenAILLM, Agent, Tool

llm = OpenAILLM(model="gpt-4", temperature=0.7)
agent = Agent(llm=llm, tools=tools)
```

#### 使用别名 (最简单的迁移方式)

```python
# 只需要修改一行
from agent import OpenAILLM as LLM, Agent, Tool

# 其余代码完全不变
llm = LLM(model="gpt-4")
agent = Agent(llm=llm, tools=tools)
response = agent.run("任务")
```

## 新功能：自定义LLM

现在你可以实现自己的LLM provider！

### 示例：Anthropic Claude

```python
from agent import LLM
from typing import Optional
import anthropic

class ClaudeLLM(LLM):
    def __init__(self, model: str = "claude-3-sonnet", api_key: str = None):
        super().__init__()
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key)
    
    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        # 添加system prompt
        if not self.history and system_prompt:
            self.history.append({"role": "system", "content": system_prompt})
        
        # 添加用户消息
        self.history.append({"role": "user", "content": prompt})
        
        # 调用Anthropic API
        response = self.client.messages.create(
            model=self.model,
            messages=self.history
        )
        
        assistant_message = response.content[0].text
        
        # 添加助手回复
        self.history.append({"role": "assistant", "content": assistant_message})
        
        return assistant_message

# 使用
llm = ClaudeLLM(api_key="your-api-key")
agent = Agent(llm=llm, tools=tools)
```

### 示例：本地模型

```python
from agent import LLM
from typing import Optional
import requests

class LocalLLM(LLM):
    def __init__(self, endpoint: str = "http://localhost:8000"):
        super().__init__()
        self.endpoint = endpoint
    
    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.history and system_prompt:
            self.history.append({"role": "system", "content": system_prompt})
        
        self.history.append({"role": "user", "content": prompt})
        
        # 调用本地API
        response = requests.post(
            f"{self.endpoint}/chat",
            json={"messages": self.history}
        )
        
        assistant_message = response.json()["response"]
        self.history.append({"role": "assistant", "content": assistant_message})
        
        return assistant_message

# 使用
llm = LocalLLM(endpoint="http://localhost:8000")
agent = Agent(llm=llm, tools=tools)
```

### 示例：测试用Mock

```python
from agent import LLM
from typing import Optional, List

class MockLLM(LLM):
    def __init__(self, responses: List[str]):
        super().__init__()
        self.responses = responses
        self.call_count = 0
    
    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.history and system_prompt:
            self.history.append({"role": "system", "content": system_prompt})
        
        self.history.append({"role": "user", "content": prompt})
        
        # 返回预定义的响应
        response = self.responses[self.call_count] if self.call_count < len(self.responses) else "默认响应"
        self.call_count += 1
        
        self.history.append({"role": "assistant", "content": response})
        
        return response

# 在测试中使用
def test_agent_with_mock():
    mock_responses = [
        "Thought: 测试\nAction: tool\nTool: test_tool\nArguments: {}",
        "Thought: 完成\nAction: finish\nResponse: 测试完成"
    ]
    
    llm = MockLLM(responses=mock_responses)
    agent = Agent(llm=llm, tools=tools)
    response = agent.run("测试任务")
    
    assert response.success
```

## 兼容性检查清单

- [ ] 将所有 `from agent import LLM` 改为 `from agent import OpenAILLM`
- [ ] 将所有 `llm = LLM(...)` 改为 `llm = OpenAILLM(...)`
- [ ] 或者使用别名：`from agent import OpenAILLM as LLM`
- [ ] 运行测试确保一切正常
- [ ] (可选) 考虑实现自定义LLM provider

## 常见问题

### Q: 为什么要做这个改动？

**A**: 为了支持多种LLM provider，提高框架的可扩展性和测试性。

### Q: 旧代码会不会不能用了？

**A**: 只需要改导入语句，其他代码完全不用改。

### Q: 如何在测试中避免调用真实API？

**A**: 实现一个MockLLM类，返回预定义的响应。

### Q: 可以混用不同的LLM吗？

**A**: 可以！每个Agent可以使用不同的LLM实例。

```python
gpt4_llm = OpenAILLM(model="gpt-4")
claude_llm = ClaudeLLM(model="claude-3")

agent1 = Agent(llm=gpt4_llm, tools=tools1)
agent2 = Agent(llm=claude_llm, tools=tools2)
```

### Q: Skill配置文件需要改吗？

**A**: 不需要！YAML配置文件完全不需要改动。

## 需要帮助？

查看以下资源：

- `README.md` - 完整文档
- `REFACTOR_SUMMARY.md` - 详细的重构说明
- `examples/custom_llm.py` - 自定义LLM示例
- `tests/test_llm_abstract.py` - 测试示例
