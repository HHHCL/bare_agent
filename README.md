# Bare Agent - 手写 AI Agent 与 MCP 实现

> 不使用任何 Agent 框架，从零手写实现 Tool Calling Agent 和 MCP 协议集成。  
> 这是理解 AI Agent 底层原理的最佳学习项目。

## 项目简介

本项目演示了如何**不依赖任何 Agent 框架**（LangChain、LangGraph、CrewAI 等），纯手工实现：

1. **基础聊天机器人** - 理解 messages 数组和大模型交互的最小实现
2. **Tool Calling Agent** - 能自主调用多个工具、决策何时停止的智能代理
3. **MCP (Model Context Protocol)** - 标准化的工具接入协议
4. **资源优化** - 懒加载、跨进程通信等工程实践

## 项目结构

```
CLAUDE_CODE
  ├── .mcp.json                         # mcp工具的配置文件
  └──bare_agent/                        # 裸agent实现
      ├── README.md                     # 本文件
      ├── .env                          # 模型调用参数配置文件
      ├── config.py                     # 配置管理（API key、base_url）
      ├── pyproject.toml                # 依赖管理（uv）
      ├── mini_Agent.py                 # 最简单的裸 Agent
      ├── tools.py                      # 工具函数定义
      ├── tool_call_agent.py            # 最简单的裸 Tool Calling Agent
      ├── tool_call_agent_pro.py        # Tool Calling Agent改进版（错误处理、日志）
      └── mcp/                          # MCP 相关实现
          ├── mcp_logger.py             # MCP 通信日志记录工具 
          ├── caculate.py               # MCP Server: 计算器工具
          ├── weather.py                # MCP Server: 天气查询工具
          ├── agent_with_mcp.py         # MCP Agent 标准版（启动时连接所有 server）
          └── agent_with_mcp_lazy.py    # MCP Agent 懒加载优化版 ⭐
```

## 核心实现

### 0. 最小聊天程序（mini_agent.py）

**理解 messages 数组是如何工作的**

```python
# 核心要点
messages = [{"role": "system", "content": "你是一个有用的助手"}]

def send_message(user_input):
    # 1. 用户输入加入 messages
    messages.append({"role": "user", "content": user_input})
    
    # 2. 调用大模型
    response = client.chat.completions.create(
        model=config.model,
        messages=messages  # 传入完整对话历史
    )
    
    # 3. 助手回复加入 messages
    reply = response.choices[0].message.content
    messages.append({"role": "assistant", "content": reply})
    
    return reply
```
**关键理解**：
- messages 是对话的"记忆"，包含完整的上下文
- 每次调用都传入全部历史，模型才能理解前后文
- system/user/assistant 三种角色各司其职：
  - `system`: 设定助手的行为（"你是..."）
  - `user`: 用户的输入
  - `assistant`: 模型的回复


### 1. Tool Calling Agent 的心脏：循环

```python
# tool_Call_agent.py 核心逻辑
for _ in range(max_rounds):
    # 1. 调用大模型
    response = client.chat.completions.create(
        model=config.model,
        messages=messages,
        tools=openai_tools
    )
    
    message = response.choices[0].message
    messages.append(message)
    
    # 2. 判断：是否需要调用工具？
    if message.tool_calls is None:
        return message.content  # 完成，返回最终答案
    
    # 3. 执行工具调用
    for tool_call in message.tool_calls:
        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)
        result = execute_tool(name, args)
        
        # 4. 将结果塞回 messages
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result
        })
    
    # 5. 继续循环，让模型看到工具结果后继续推理
```

**关键理解**：
- Agent 不是"一次调用"，而是**循环**
- 每次循环：模型思考 → 决定是否用工具 → 执行 → 模型再思考
- 循环直到模型说"我完成了"或达到最大次数

### 2. MCP 协议：标准化工具接口

**问题**：每次写新工具都要改 Agent 代码？

**MCP 解决方案**：
```
┌─────────────┐                  ┌──────────────┐
│   Agent     │   MCP 协议        │ MCP Server   │
│  (Client)   │ ←─────────────→  │  (Tools)     │
└─────────────┘                  └──────────────┘
     ↓                                   ↓
1. list_tools() ───────────────→  返回工具列表 + schema
2. call_tool(name, args) ──────→  执行工具
3. ←───────────────────────────  返回结果
```

**优势**：
- ✅ Agent 不需要知道工具实现细节
- ✅ 新增工具不需要修改 Agent 代码
- ✅ 支持跨语言、跨进程工具调用


### 3. 懒加载优化（agent_with_mcp_lazy.py）⭐

**场景**：定义了 10 个工具，但用户只问"1+1等于几"，只用了 1 个。

**问题**：启动时连接所有 10 个 MCP server → 浪费资源

**解决方案**：
```python
async def get_or_create_session(server_name):
    """首次使用某个工具时才连接对应的 server"""
    if server_name not in server_sessions:
        print(f"⚡ 首次使用 {server_name}，正在连接...")
        # 建立连接...
        server_sessions[server_name] = session
    return server_sessions[server_name]
```

**效果对比**：
| 版本 | 启动时间 | 内存占用 | 适用场景 |
|------|---------|---------|---------|
| agent_with_mcp.py | 慢（连接所有） | 高 | 工具少且常用 |
| agent_with_mcp_lazy.py | 快（按需连接） | 低 | 工具多但大多不常用 |

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
cd bare_agent

# 安装依赖（使用 uv）
uv sync

# 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 API key 和 base_url
```

### 2. 运行不同版本

#### 本地版本（不使用 MCP）
```bash
# 最简单agent版本
uv run mini_agent.py

# 最简单的裸 Tool Calling Agent版本
uv run tool_call_agent.py

# Tool Calling Agent优化版本
uv run tool_call_agent_pro.py
```

#### MCP 标准版
```bash
# 启动时连接所有 server
uv run agent_with_mcp.py
```

#### MCP 懒加载版（推荐）⭐
```bash
# 按需连接 server
uv run mcp/agent_with_mcp_lazy.py
```

### 3. 测试工具调用

```
你：帮我算一下 (123 + 456) * 789
助手：⚡ 首次使用 caculate，正在连接 MCP server...
     ✓ caculate 已连接
     计算结果是 456831

你：北京的天气怎么样？（纬度39.9，经度116.4）
助手：⚡ 首次使用 weather，正在连接 MCP server...
     ✓ weather 已连接
     北京今天晴，温度 25°C...
```

## 技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.10+ | 使用 async/await |
| 大模型 | OpenAI API | 兼容 Claude、Deepseek 等 |
| 协议 | MCP | Model Context Protocol |
| 配置 | pydantic-settings | 类型安全的配置管理 |
| 包管理 | uv | 快速的 Python 包管理器 |

## 关键学习点

### 对于初学者
1. **messages 数组是 Agent 的记忆** - system/user/assistant/tool 四种角色
2. **工具调用是循环不是一次性** - 理解 for 循环的必要性
3. **错误处理很重要** - 工具执行失败时要给模型可理解的错误信息

### 对于进阶者
1. **MCP 的价值** - 标准化协议 vs 每次重写对接代码
2. **资源优化** - 懒加载、连接池、超时控制
3. **跨进程通信** - stdin/stdout、AsyncExitStack、上下文管理

## 演进路径

```
mini_agent.py          最简单的 Agent 循环
    ↓
tool_Call_agent.py          + 错误处理 + 日志
    ↓
tool_Call_agent_pro.py              + 多个工具 + 完整项目结构
    ↓
caculate.py（weather.py）    + MCP server实现
    ↓
agent_with_mcp.py         + 完整 MCP client 实现
    ↓
agent_with_mcp_lazy.py         + 懒加载优化 ⭐
```

**建议学习顺序**：从上到下，每个文件都跑通并理解再往下走。

## 面试准备

能用这个项目回答的高频问题：

1. **Agent 和普通 chatbot 的区别？**
   - Chatbot：单次问答
   - Agent：循环调用，能使用工具，有决策能力

2. **Tool Calling 的循环怎么实现？**
   - 画出 tool_Call_agent.py 的流程图

3. **MCP 解决什么问题？**
   - 标准化工具接入协议，解耦 Agent 和工具实现

4. **为什么要用 Pydantic？**
   - 类型安全、参数校验、自动生成 JSON Schema

5. **如何优化资源占用？**
   - 懒加载（agent_with_mcp_lazy.py）、连接池、超时控制

## 下一步

完成本项目后，你已经掌握了：
- ✅ Agent 底层原理
- ✅ MCP 协议
- ✅ 工程实践（错误处理、资源优化）

**建议继续学习**：
1. RAG（检索增强生成）- 给 Agent 加上长期记忆
2. LangGraph - 用状态机管理复杂 Agent 流程
3. Evaluation - 如何评估 Agent 的质量

## 常见问题

### Q1: 为什么 agent_with_mcp_lazy.py 首次调用慢？
A: 懒加载需要连接 MCP server，有 200-500ms 开销。后续调用会复用连接，很快。

### Q2: 如何添加新的 MCP 工具？
A: 
1. 在 `mcp/` 下创建新的 `xxx.py` server
2. 在 `agent_with_mcp_lazy.py` 的 `SERVER_CONFIGS` 中注册
3. 在 `TOOL_DEFINITIONS` 中定义工具 schema

### Q3: 可以用 Claude API 吗？
A: 可以！只需在 `.env` 中修改 `BASE_URL` 和 `API_KEY`。

### Q4: 如何防止 Agent 无限循环？
A: 设置 `max_rounds`（默认 10），超过后强制返回。

## 作者

这是一个学习项目，用于深入理解 AI Agent 的底层原理。


---

**如果这个项目对你有帮助，欢迎 Star ⭐**
