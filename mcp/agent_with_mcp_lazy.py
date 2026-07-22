"""stage_3_2.py - 懒加载优化版本

相比 stage_3_1.py 的改进：
1. 不在启动时连接所有 MCP server，只注册工具定义
2. 首次调用某个工具时，才连接对应的 server（懒加载）
3. 已连接的 session 会被缓存，后续调用直接复用
4. 显著减少资源占用，特别是当定义了很多工具但只用到少数时

核心变化：
- 新增 get_or_create_session() 函数：按需连接 server
- 工具定义从本地配置读取（不依赖 server.list_tools()）
- tool_to_session 改为动态填充，而非启动时全部填充
"""

from contextlib import AsyncExitStack
import json
import logging
import os
from mcp import ClientSession, StdioServerParameters, stdio_client
from openai import OpenAI
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Settings

config = Settings()

MCP_DIR = os.path.dirname(__file__)

# MCP server 配置：定义如何启动每个 server
SERVER_CONFIGS = {
    "weather": StdioServerParameters(
        command="/opt/homebrew/bin/uv",
        args=["--directory", MCP_DIR, "run", "weather.py"]
    ),
    "caculator": StdioServerParameters(
        command="/opt/homebrew/bin/uv",
        args=["--directory", MCP_DIR, "run", "caculator.py"]
    )
}

# 工具定义：本地维护，告诉 AI 有哪些工具可用
# 注意：这里需要手动维护工具的 schema，作为懒加载的代价
TOOL_DEFINITIONS = {
    "caculator": {
        "server": "caculator",  # 属于哪个 server
        "definition": {
            "type": "function",
            "function": {
                "name": "caculator",
                "description": "计算数学表达式的结果",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "express": {
                            "type": "string",
                            "description": "要计算的数学表达式，例如: '2+3*4'"
                        }
                    },
                    "required": ["express"]
                }
            }
        }
    },
    "get_forecast": {
        "server": "weather",
        "definition": {
            "type": "function",
            "function": {
                "name": "get_forecast",
                "description": "获取指定经纬度的天气预报",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "latitude": {
                            "type": "number",
                            "description": "纬度"
                        },
                        "longitude": {
                            "type": "number",
                            "description": "经度"
                        }
                    },
                    "required": ["latitude", "longitude"]
                }
            }
        }
    },
    "get_alerts": {
        "server": "weather",
        "definition": {
            "type": "function",
            "function": {
                "name": "get_alerts",
                "description": "获取美国某个州的天气警报",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "description": "美国州代码，例如: CA, NY"
                        }
                    },
                    "required": ["state"]
                }
            }
        }
    }
}

logging.basicConfig(
    filename="/Users/chunlian/Documents/claude_code/bare_agent/mcp/stage_3_2.log",
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
        # 核心变化：这些字典在启动时是空的，按需填充
        server_sessions = {}  # server_name -> session（一个 server 可能有多个工具）
        tool_to_server = {}   # tool_name -> server_name（记住工具属于哪个 server）

        # 从本地配置构建 OpenAI 工具列表
        openai_tools = []
        for tool_name, tool_info in TOOL_DEFINITIONS.items():
            openai_tools.append(tool_info["definition"])
            tool_to_server[tool_name] = tool_info["server"]

        logger.info(f"已注册工具（未连接）: {list(tool_to_server.keys())}")
        print(f"[懒加载模式] 已注册 {len(openai_tools)} 个工具，暂未连接任何 server")

        async def get_or_create_session(server_name):
            """按需连接 MCP server（懒加载的核心逻辑）"""
            if server_name not in server_sessions:
                logger.info(f"首次使用 {server_name}，正在连接...")
                print(f"  ⚡ 首次使用 {server_name}，正在连接 MCP server...")

                params = SERVER_CONFIGS[server_name]
                read, write = await stack.enter_async_context(stdio_client(params))
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()

                server_sessions[server_name] = session
                logger.info(f"{server_name} 连接成功")
                print(f"  ✓ {server_name} 已连接")

            return server_sessions[server_name]

        async def send_message(user_input):
            messages.append({"role": "user", "content": user_input})

            for round_num in range(max_rounds):
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
                    logger.info(f"[轮次 {round_num+1}] 调用工具 {name}: {args}")

                    try:
                        # 核心变化：先获取（或创建）对应的 session
                        server_name = tool_to_server[name]
                        session = await get_or_create_session(server_name)

                        # 然后调用工具
                        result = await session.call_tool(name, args)
                        text = "\n".join(t.text for t in result.content if hasattr(t, "text"))
                        logger.info(f"工具 {name} 返回: {text[:100]}...")

                    except Exception as e:
                        logger.error(f"工具 {name} 执行错误: {e}")
                        text = f"工具 {name} 执行错误: {e}"

                    message = {
                        "role": "tool",
                        "tool_call_id": tool.id,
                        "content": text
                    }
                    messages.append(message)

            return "（达到最大循环次数，未得到最终回答）"

        # 交互模式
        print("\n=== MCP 懒加载版 Agent ===")
        print("特性：只在首次使用某个工具时才连接对应的 MCP server")
        print("输入 'quit' 退出\n")

        while True:
            user_input = input("你：")
            if user_input.strip().lower() == "quit":
                break

            print(f"\n助手：{await send_message(user_input)}\n")

        # 退出时显示统计
        print(f"\n[统计] 本次会话实际连接的 server: {list(server_sessions.keys()) or '无'}")
        logger.info(f"会话结束，实际连接的 server: {list(server_sessions.keys())}")


if __name__ == "__main__":
    asyncio.run(main())
