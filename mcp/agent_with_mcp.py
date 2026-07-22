"""让上一阶段手写的 agent 调用本阶段手写的 MCP server（caculator.py和weather.py）。

从 tool_call_agent_pro.py 改到本文件的步骤：
1. 不再手写 tools JSON、也不再手写 tool_map。启动时连接 MCP server，
   用 session.list_tools() 让 server 自己report它有哪些工具（MCP 的核心价值）。
2. 把 MCP 的 tool.inputSchema 转成 OpenAI 要的 tools 格式（几乎照搬，见下）。
3. agent loop 里，原来的 tool_map[name](**args)（进程内调用）
   改成 await session.call_tool(name, args)（跨进程调用），
   再从 result.content 里取出文本。
4. 因为 MCP client 的 API 全是 async 的，send_message 变成 async def，
   用 asyncio.run 启动，多个 server 连接用 AsyncExitStack 统一管理。
"""

from contextlib import AsyncExitStack
import json
import logging
from mcp import ClientSession, StdioServerParameters, stdio_client
from openai import OpenAI
import asyncio
import sys
from pathlib import Path
import os

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Settings

config = Settings()

MCP_DIR = os.path.dirname(__file__)

# 要连接的 MCP server：直接用 uv run 启动你自己写的 server。
# （.mcp.json 里那层 mcp_logger.py 是给 Claude Code 记日志用的包装，agent 直连不需要。）
SERVERS = {
    "weather": StdioServerParameters(
        command="/usr/bin/python3",
        args=[f"{MCP_DIR}/mcp_logger.py", "/opt/homebrew/bin/uv", "--directory", MCP_DIR, "run", "weather.py"],
        env={"MCP_LOG_FILE": f"{MCP_DIR}/mcp_weather.log"}  # 独立日志文件
    ),
    "caculator": StdioServerParameters(
        command="/usr/bin/python3",
        args=[f"{MCP_DIR}/mcp_logger.py", "/opt/homebrew/bin/uv", "--directory", MCP_DIR, "run", "caculator.py"],
        env={"MCP_LOG_FILE": f"{MCP_DIR}/mcp_caculator.log"}  # 独立日志文件
    )
}

logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), "agent_with_mcp.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

logger = logging.getLogger(__name__)

max_rounds = 10

async def main():
    client = OpenAI(api_key=config.api_key, base_url=config.base_url)
    messages = [{"role": "system", "content": "你是一个有用的助手"}]

    async with AsyncExitStack() as stack:
        # 步骤 1：连接每个 server，握手（initialize），并收集它们的工具。
        tool_to_session = {} # 工具名 -> 属于哪个 session（调用时要知道找谁）
        openai_tools = []   # 转换成 OpenAI chat.completions 要的 tools 格式

        for name, params in SERVERS.items():
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            resp = await session.list_tools() #获取一个mcp server可用的工具列表

            logger.info(f"mcp session: {name}, tool list: {str(resp)}")
            
            for tool in resp.tools:
                tool_to_session[tool.name] = session
                # 步骤 2：MCP 的 inputSchema 本身就是一份 JSON Schema，
                # 直接塞进 OpenAI 的 function.parameters 即可。
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema
                    }
                })
            
            logger.info(f"已连接{name}工具：{[t.name for t in resp.tools]}")
        
        async def send_message(user_input):
            messages.append({"role": "user", "content": user_input})
            # OpenAI 用的是同步 client，在 async 里直接调会短暂阻塞事件循环，
            # 单用户 CLI 学习场景无所谓；重点是下面 MCP 的调用是 async 的。
            for _ in range(max_rounds):
                response = client.chat.completions.create(
                    model=config.model,
                    messages=messages,
                    tools=openai_tools
                )

                resp = response.choices[0].message
                messages.append(resp)
                if resp.tool_calls is None:
                    return resp.content
                
                for tool in resp.tool_calls:
                    name = tool.function.name
                    args = json.loads(tool.function.arguments)
                    logger.info(f"调用mcp工具{name}:{args}")

                    try:
                        # 步骤 3：核心变化——跨进程调用 MCP 工具。
                        result = await tool_to_session[name].call_tool(name, args)
                        # result.content 是一个列表，取出所有文本块拼起来。
                        text = "\n".join(t.text for t in result.content if hasattr(t,"text"))
                
                    except Exception as e:
                        logger.error(f"工具{name}执行错误{e}")
                        text= f"工具{name}执行错误:{e}"
                    message = {
                        "role": "tool",
                        "tool_call_id": tool.id,
                        "content": text
                    }
                    messages.append(message)

            return "（达到最大循环次数，未得到最终回答）"
        
        # demo 模式：命令行带参数就跑一轮然后退出，方便测试。
        if len(sys.argv) > 1:
            print(f"\n助手：{await send_message(' '.join(sys.argv[1:]))}")
            return
        
        # 交互模式
        print("\nMCP 版 agent（输入 quit 退出）")
        while True:
            user_input = input("\n你：")
            if user_input.strip().lower == "quit":
                break
            print(f"\n助手：{await send_message(user_input)}")

if __name__== "__main__":
    asyncio.run(main())


