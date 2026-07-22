# MCP (Model Context Protocol)

## MCP是什么
>官方文档：https://modelcontextprotocol.io/docs/getting-started/intro

**没有MCP时**：Agent想要调用工具，可以在Agent模型里写上tool函数，但是Agent调用时需要代码手动处理去调用函数。需要使用tool_map对已有的工具进行管理。

**有了MCP以后**：工具是独立于Agent运行的服务，将工具与agent解耦了，agent启动时通过协议动态拿到工具列表。

---

### MCP协议改变的是工具放在哪里，怎么被发现

MCP使得Agent可以自动触发去调用功能。MCP就像一根数据线（MCP Client），一头连接着电器设备（Agent），一头连接着各种电源（MCP Server）。电器设备通过数据线可以从各种电源处获取电。

---

### MCP就是Agent与工具服务器之间的一套标准交互协议

MCP定义了 Agent（Client）和工具服务（Server）之间怎么通信 :
- 怎么连接
- 怎么问"你有哪些工具"
- 怎么调用某个工具
- 结果怎么返回
有了这个标准，任何遵循 MCP 的 Agent 可以对接任何遵循 MCP 的工具服务，不用每次单独适配。

---

## MCP Client、Host、MCP Server 三者之间是什么关系
Host：Agent
**启动阶段：**
Agent 创建 MCP Client → 连接 MCP Server → 获取可用工具列表
**运行阶段（循环）:**
用户输入->模型判断是否需要使用工具->Agent 通过 MCP Client 调 Server 的工具->拿到结果塞回 messages->调用模型处理工具调用结果->模型给出最终回答->...(循环)

---

## MCP Server如何本地安装
1. 访问专门的MCP提供网站（https://mcpmarket.com/zh）
2. 搜索关键词查找需要的MCP Server
3. 在Server的README里找到安装描述进行安装
