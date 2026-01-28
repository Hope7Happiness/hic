# OpenCode Context Compaction 实现分析

## 概览

OpenCode实现了一个自动化的context compaction系统，用于在对话历史（chat history）接近模型的context limit时自动触发压缩，避免超过token限制导致的错误。

该系统的核心思想是：**当检测到context overflow时，自动触发一个特殊的"compaction" agent来总结之前的对话，并将总结作为新的context继续对话**。

---

## 核心组件

### 1. Token计数与Overflow检测

**文件**: `src/session/compaction.ts`

**关键函数**: `isOverflow()`

```typescript
export async function isOverflow(input: { 
  tokens: MessageV2.Assistant["tokens"]; 
  model: Provider.Model 
}) {
  const config = await Config.get()
  if (config.compaction?.auto === false) return false
  
  const context = input.model.limit.context  // 模型的context limit
  if (context === 0) return false
  
  const count = input.tokens.input + input.tokens.cache.read + input.tokens.output
  const output = Math.min(input.model.limit.output, SessionPrompt.OUTPUT_TOKEN_MAX) || SessionPrompt.OUTPUT_TOKEN_MAX
  const usable = input.model.limit.input || context - output
  
  return count > usable  // 如果当前token数超过可用空间，返回true
}
```

**原理**:
- 计算当前conversation使用的total tokens: `input + cache.read + output`
- 计算usable context: `context_limit - reserved_for_output`
- 如果 `total > usable`，判定为overflow

**Token估算**:
```typescript
// src/util/token.ts
const CHARS_PER_TOKEN = 4
export function estimate(input: string) {
  return Math.max(0, Math.round(input.length / 4))
}
```

简单的启发式算法：平均每4个字符约等于1个token。

---

### 2. Compaction触发时机

**文件**: `src/session/processor.ts` (line 274-276)

在每次LLM响应完成后（`step-finish`事件），检查是否overflow：

```typescript
case "step-finish":
  // ... 更新token使用情况 ...
  if (await SessionCompaction.isOverflow({ tokens: usage.tokens, model: input.model })) {
    needsCompaction = true
  }
  break
```

如果`needsCompaction = true`，在处理循环结束时返回`"compact"`：

```typescript
// line 397
if (needsCompaction) return "compact"
```

**文件**: `src/session/prompt.ts` (line 500-513, line 620-627)

在主处理循环中，有两处检测并触发compaction：

**位置1**: 检测上一条assistant message是否overflow：
```typescript
// line 500-513: 自动触发compaction
if (
  lastFinished &&
  lastFinished.summary !== true &&  // 不是已经compacted的消息
  (await SessionCompaction.isOverflow({ tokens: lastFinished.tokens, model }))
) {
  await SessionCompaction.create({
    sessionID,
    agent: lastUser.agent,
    model: lastUser.model,
    auto: true,  // 自动触发
  })
  continue  // 跳到下一轮循环
}
```

**位置2**: 处理processor返回的`"compact"`结果：
```typescript
// line 620-627
if (result === "compact") {
  await SessionCompaction.create({
    sessionID,
    agent: lastUser.agent,
    model: lastUser.model,
    auto: true,
  })
}
```

---

### 3. Compaction Agent

**文件**: `src/agent/agent.ts` (line 154-168)

OpenCode定义了一个内置的"compaction" agent：

```typescript
compaction: {
  name: "compaction",
  mode: "primary",
  native: true,
  hidden: true,  // 对用户隐藏
  prompt: PROMPT_COMPACTION,
  permission: PermissionNext.merge(
    defaults,
    PermissionNext.fromConfig({
      "*": "deny",  // 禁止所有工具调用
    }),
    user,
  ),
  options: {},
}
```

**Compaction Prompt** (`src/agent/prompt/compaction.txt`):
```
You are a helpful AI assistant tasked with summarizing conversations.

When asked to summarize, provide a detailed but concise summary of the conversation. 
Focus on information that would be helpful for continuing the conversation, including:
- What was done
- What is currently being worked on
- Which files are being modified
- What needs to be done next
- Key user requests, constraints, or preferences that should persist
- Important technical decisions and why they were made

Your summary should be comprehensive enough to provide context but concise enough to be quickly understood.
```

**关键特点**:
- **hidden**: 不在UI中显示，纯内部使用
- **no tools**: 所有工具权限都是deny，只能生成文本
- **专注总结**: prompt明确要求总结对话，提取关键信息

---

### 4. Compaction执行流程

**文件**: `src/session/compaction.ts` (line 92-193)

**核心函数**: `process()`

```typescript
export async function process(input: {
  parentID: string
  messages: MessageV2.WithParts[]
  sessionID: string
  abort: AbortSignal
  auto: boolean
}) {
  // 1. 获取compaction agent和model
  const userMessage = input.messages.findLast((m) => m.info.id === input.parentID)!.info
  const agent = await Agent.get("compaction")
  const model = agent.model 
    ? await Provider.getModel(agent.model.providerID, agent.model.modelID)
    : await Provider.getModel(userMessage.model.providerID, userMessage.model.modelID)
  
  // 2. 创建assistant message（标记为summary=true）
  const msg = await Session.updateMessage({
    id: Identifier.ascending("message"),
    role: "assistant",
    parentID: input.parentID,
    sessionID: input.sessionID,
    mode: "compaction",
    agent: "compaction",
    summary: true,  // 关键标记：这是一个summary message
    // ...其他字段...
  })
  
  // 3. 创建processor
  const processor = SessionProcessor.create({
    assistantMessage: msg,
    sessionID: input.sessionID,
    model,
    abort: input.abort,
  })
  
  // 4. 允许插件自定义compaction prompt
  const compacting = await Plugin.trigger(
    "experimental.session.compacting",
    { sessionID: input.sessionID },
    { context: [], prompt: undefined },
  )
  
  const defaultPrompt = 
    "Provide a detailed prompt for continuing our conversation above. " +
    "Focus on information that would be helpful for continuing the conversation, " +
    "including what we did, what we're doing, which files we're working on, " +
    "and what we're going to do next considering new session will not have " +
    "access to our conversation."
  
  const promptText = compacting.prompt ?? [defaultPrompt, ...compacting.context].join("\n\n")
  
  // 5. 执行LLM调用
  const result = await processor.process({
    user: userMessage,
    agent,
    abort: input.abort,
    sessionID: input.sessionID,
    tools: {},  // 没有工具
    system: [],
    messages: [
      ...MessageV2.toModelMessages(input.messages, model),  // 所有历史消息
      {
        role: "user",
        content: [{
          type: "text",
          text: promptText,  // 总结请求
        }],
      },
    ],
    model,
  })
  
  // 6. 如果是自动触发，可能继续对话
  if (result === "continue" && input.auto) {
    const continueMsg = await Session.updateMessage({
      id: Identifier.ascending("message"),
      role: "user",
      sessionID: input.sessionID,
      // ...
    })
    await Session.updatePart({
      // ...
      type: "text",
      synthetic: true,
      text: "Continue if you have next steps",
      // ...
    })
  }
  
  if (processor.message.error) return "stop"
  Bus.publish(Event.Compacted, { sessionID: input.sessionID })
  return "continue"
}
```

**执行步骤**:
1. 获取compaction agent配置和model
2. 创建一个新的assistant message，标记为`summary: true`
3. 构建compaction prompt（可被插件覆盖）
4. 将**所有历史消息**+compaction请求发送给LLM
5. LLM返回总结
6. 如果是自动触发，可能插入"Continue if you have next steps"继续对话
7. 发布`session.compacted`事件

**关键设计**:
- `summary: true`标记：后续在检测overflow时会跳过这条消息（line 502-503）
- 所有历史消息都发送给compaction agent，让它生成全面的总结
- 总结后的消息成为新的context起点

---

### 5. Tool Output Pruning（工具输出修剪）

**文件**: `src/session/compaction.ts` (line 41-90)

**核心函数**: `prune()`

除了compaction，OpenCode还实现了一个**tool output pruning**机制：

```typescript
export const PRUNE_MINIMUM = 20_000   // 最少修剪20k tokens
export const PRUNE_PROTECT = 40_000   // 保护最近40k tokens

export async function prune(input: { sessionID: string }) {
  const config = await Config.get()
  if (config.compaction?.prune === false) return
  
  const msgs = await Session.messages({ sessionID: input.sessionID })
  let total = 0
  let pruned = 0
  const toPrune = []
  let turns = 0
  
  // 从最新的消息往前遍历
  loop: for (let msgIndex = msgs.length - 1; msgIndex >= 0; msgIndex--) {
    const msg = msgs[msgIndex]
    if (msg.info.role === "user") turns++
    if (turns < 2) continue  // 保护最近2轮对话
    if (msg.info.role === "assistant" && msg.info.summary) break loop  // 遇到summary停止
    
    for (let partIndex = msg.parts.length - 1; partIndex >= 0; partIndex--) {
      const part = msg.parts[partIndex]
      if (part.type === "tool" && part.state.status === "completed") {
        if (PRUNE_PROTECTED_TOOLS.includes(part.tool)) continue  // 跳过保护的工具（如skill）
        if (part.state.time.compacted) break loop  // 遇到已修剪的停止
        
        const estimate = Token.estimate(part.state.output)
        total += estimate
        
        // 保护最近40k tokens的输出
        if (total > PRUNE_PROTECT) {
          pruned += estimate
          toPrune.push(part)
        }
      }
    }
  }
  
  // 只有修剪量超过20k才执行
  if (pruned > PRUNE_MINIMUM) {
    for (const part of toPrune) {
      if (part.state.status === "completed") {
        part.state.time.compacted = Date.now()  // 标记为已修剪
        await Session.updatePart(part)
      }
    }
    log.info("pruned", { count: toPrune.length })
  }
}
```

**Pruning策略**:
- **保护范围**: 最近2轮对话，最近40k tokens的tool outputs
- **修剪目标**: 40k tokens之前的旧tool outputs
- **修剪条件**: 累计修剪量需超过20k tokens
- **修剪方式**: 设置`part.state.time.compacted = Date.now()`标记，不删除数据

**何时调用**:
```typescript
// src/session/prompt.ts line 630
SessionCompaction.prune({ sessionID })
```
在主处理循环结束后调用。

**修剪后的处理**:
```typescript
// src/session/message-v2.ts line 544
const outputText = part.state.time.compacted 
  ? "[Old tool result content cleared]" 
  : part.state.output
const attachments = part.state.time.compacted ? [] : (part.state.attachments ?? [])
```
显示时，已修剪的tool output显示为`"[Old tool result content cleared]"`。

---

### 6. Message结构与标记

**文件**: `src/session/message-v2.ts`

**Assistant Message Schema**:
```typescript
export const Assistant = Base.extend({
  role: z.literal("assistant"),
  // ...
  summary: z.boolean().optional(),  // 标记这是一个compaction summary
  tokens: z.object({
    input: z.number(),
    output: z.number(),
    reasoning: z.number(),
    cache: z.object({
      read: z.number(),
      write: z.number(),
    }),
  }),
  // ...
})
```

**Compaction Part Schema**:
```typescript
export const CompactionPart = PartBase.extend({
  type: z.literal("compaction"),
  auto: z.boolean(),  // 是否为自动触发
})
```

**Tool Part Compaction标记**:
```typescript
export const ToolStateCompleted = z.object({
  status: z.literal("completed"),
  // ...
  time: z.object({
    start: z.number(),
    end: z.number(),
    compacted: z.number().optional(),  // 被修剪的时间戳
  }),
  // ...
})
```

---

## 完整工作流程

### 场景：用户发送新消息，context即将满

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User sends message                                        │
│    SessionPrompt.continue() triggered                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Main processing loop in prompt.ts                         │
│    - Check if lastFinished has overflow                      │
│    - If yes: SessionCompaction.create({ auto: true })       │
│    - Create a "compaction" part in user message              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Loop detects compaction part                              │
│    - Call SessionCompaction.process()                        │
│    - Create assistant message with summary: true             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. SessionCompaction.process()                               │
│    - Get "compaction" agent                                  │
│    - Build compaction prompt                                 │
│    - Send ALL history + compaction request to LLM           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. LLM generates summary                                     │
│    - Summary saved as assistant message (summary: true)      │
│    - This message becomes new context anchor                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. Continue processing (if auto)                             │
│    - Insert synthetic "Continue if you have next steps"      │
│    - OR user's original request continues                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. SessionCompaction.prune()                                 │
│    - Mark old tool outputs as compacted                      │
│    - Reduce token usage further                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 配置选项

**文件**: `src/config/config.ts` (line 1041-1046)

```typescript
compaction: z.object({
  auto: z.boolean().optional()  // 默认true，启用自动compaction
    .describe("Enable automatic compaction when context is full (default: true)"),
  prune: z.boolean().optional()  // 默认true，启用tool output pruning
    .describe("Enable pruning of old tool outputs (default: true)"),
}).optional()
```

**用户配置示例**:
```json
{
  "compaction": {
    "auto": false,  // 禁用自动compaction
    "prune": true   // 保留pruning
  }
}
```

**环境变量覆盖**:
```typescript
// line 188-193
if (Flag.OPENCODE_COMPACTION_DISABLED) {
  result.compaction = { ...result.compaction, auto: false }
}
if (Flag.OPENCODE_COMPACTION_PRUNE_DISABLED) {
  result.compaction = { ...result.compaction, prune: false }
}
```

---

## 关键设计决策

### 1. **两层机制**：Compaction + Pruning
- **Compaction**: 生成对话总结，替换长context
- **Pruning**: 删除旧tool输出，保留结构但清除内容
- 两者互补，Compaction更彻底但消耗LLM调用，Pruning更轻量

### 2. **保护最近context**
- Pruning保护最近2轮对话、40k tokens的tool outputs
- Overflow检测会跳过已标记为`summary: true`的消息
- 避免过度压缩导致信息丢失

### 3. **透明的compaction**
- Compaction agent对用户隐藏（`hidden: true`）
- 自动触发（`auto: true`），用户无感知
- 总结消息成为新的context起点

### 4. **插件扩展点**
```typescript
// 允许插件自定义compaction prompt
const compacting = await Plugin.trigger(
  "experimental.session.compacting",
  { sessionID: input.sessionID },
  { context: [], prompt: undefined },
)
```
插件可以：
- 替换默认prompt
- 注入额外context

### 5. **Token估算简单但有效**
- `CHARS_PER_TOKEN = 4` 是粗略估算
- 对于英文约为3.5-4，中文约为1-2
- 足够用于overflow检测，不需要精确计数

---

## 优势与局限

### 优势
1. **自动化**: 完全透明，用户无需干预
2. **灵活**: 可配置是否启用compaction和pruning
3. **渐进式**: Pruning先尝试轻量级修剪，compaction是最后手段
4. **可扩展**: 插件可以自定义compaction行为
5. **保留历史**: 数据不删除，只标记`compacted`，可追溯

### 局限
1. **Token估算不精确**: 简单的字符计数可能偏差较大
2. **Compaction消耗**: 每次compaction需要一次完整的LLM调用
3. **信息损失**: 总结可能丢失细节，尤其是复杂技术讨论
4. **无法回退**: Compaction后无法恢复原始详细历史
5. **依赖LLM质量**: 总结质量完全依赖compaction agent的能力

---

## 实现要点总结

### 核心类与文件
| 文件 | 行数 | 职责 |
|------|------|------|
| `session/compaction.ts` | 226 | Compaction核心逻辑：检测、执行、pruning |
| `session/processor.ts` | 406 | 流式处理LLM响应，检测overflow |
| `session/prompt.ts` | 1822 | 主处理循环，触发compaction |
| `agent/agent.ts` | ~200 | 定义compaction agent |
| `util/token.ts` | 8 | Token估算 |

### 关键常量
```typescript
OUTPUT_TOKEN_MAX = 32_000        // 最大输出token
PRUNE_MINIMUM = 20_000           // 最小修剪量
PRUNE_PROTECT = 40_000           // 保护的token数
CHARS_PER_TOKEN = 4              // 字符到token的转换比率
```

### 关键检测点
1. `processor.ts:274` - 每次LLM响应后检测
2. `prompt.ts:500` - 处理循环开始时检测
3. `prompt.ts:620` - 处理processor返回的compact信号

### 关键数据结构
```typescript
// Assistant message标记
{ summary: true }

// Tool part compaction标记
{ state: { time: { compacted: Date.now() } } }

// Compaction part
{ type: "compaction", auto: true }
```

---

## 对我们项目的启示

### 可以借鉴的设计
1. ✅ **两层机制**: Pruning（轻量）+ Compaction（重型）
2. ✅ **自动检测**: 在LLM响应后自动检测overflow
3. ✅ **保护策略**: 保护最近N轮对话/N个tokens
4. ✅ **标记式删除**: 不真正删除数据，只标记`compacted`
5. ✅ **专用agent**: 单独的compaction agent负责总结

### 需要调整的地方
1. ⚠️ **Token计数**: 我们可能需要更精确的计数（tiktoken库）
2. ⚠️ **简化实现**: OpenCode的实现很复杂（2453行），我们需要简化版本
3. ⚠️ **同步vs异步**: 我们的agent是异步的，需要考虑compaction时的状态管理
4. ⚠️ **无插件系统**: 我们暂时不需要插件扩展点

### 实现优先级
1. **P0**: 基础overflow检测 + 简单的message数量限制
2. **P1**: Token计数（tiktoken） + Compaction agent
3. **P2**: Tool output pruning
4. **P3**: 更精细的保护策略

---

## 附录：相关代码片段

### A. 完整的isOverflow实现
```typescript
// src/session/compaction.ts:30-39
export async function isOverflow(input: { 
  tokens: MessageV2.Assistant["tokens"]; 
  model: Provider.Model 
}) {
  const config = await Config.get()
  if (config.compaction?.auto === false) return false
  const context = input.model.limit.context
  if (context === 0) return false
  const count = input.tokens.input + input.tokens.cache.read + input.tokens.output
  const output = Math.min(input.model.limit.output, SessionPrompt.OUTPUT_TOKEN_MAX) || SessionPrompt.OUTPUT_TOKEN_MAX
  const usable = input.model.limit.input || context - output
  return count > usable
}
```

### B. Compaction触发入口
```typescript
// src/session/prompt.ts:500-513
if (
  lastFinished &&
  lastFinished.summary !== true &&
  (await SessionCompaction.isOverflow({ tokens: lastFinished.tokens, model }))
) {
  await SessionCompaction.create({
    sessionID,
    agent: lastUser.agent,
    model: lastUser.model,
    auto: true,
  })
  continue
}
```

### C. Compaction执行核心
```typescript
// src/session/compaction.ts:144-164 (简化)
const result = await processor.process({
  user: userMessage,
  agent,
  abort: input.abort,
  sessionID: input.sessionID,
  tools: {},
  system: [],
  messages: [
    ...MessageV2.toModelMessages(input.messages, model),
    {
      role: "user",
      content: [{
        type: "text",
        text: promptText,  // "Provide a detailed prompt for continuing..."
      }],
    },
  ],
  model,
})
```

---

**文档生成时间**: 2026-01-27  
**OpenCode版本**: 基于external/opencode目录的源码分析  
**分析文件总行数**: ~2500行（compaction.ts + processor.ts + prompt.ts）
