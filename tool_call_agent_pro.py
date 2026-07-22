import json
import logging
from openai import OpenAI
from config import Settings
from tools import *
import os

"""
从tool_call_agent修改到tool_call_agent_pro的步骤:
1. 添加循环次数上限和错误处理
2. 添加日志
"""

config = Settings()

client = OpenAI(api_key=config.api_key, base_url=config.base_url)

messages = [{"role": "system", "content":"你是一个有用的助手"}]

max_rounds = 10

logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), "tool_call_agent.log"),
    level=logging.INFO,  #这个设置会把httpx的底层网络细节全记录下来（TLS握手，请求头等）
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

logger = logging.getLogger(__name__)

tools = [
    {
        "type": "function",
        "function": {
            "name": "caculator",
            "description": "计算数学表达式",
            "parameters": {
                "type": "object",
                "properties": {
                    "express": {"type": "string", "description": "数学表达式"}
                },
                "required": ["express"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取当前时间",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
    ]

tool_map = {
    "caculator": caculator,
    "get_current_time": get_current_time
} 

def send_message(mes):
    messages.append({"role": "user", "content":mes})

    #发送prompt，获得返回内容
    for _ in range(max_rounds):
        response = client.chat.completions.create(
            model=config.model,
            messages=messages,
            tools=tools
        )

        message = response.choices[0].message
        # messages.append({"role": "assistant", "content":message}) #因为这样子写，相当于把模型回复里的message的内容都当成了content，但是API要求role: "tool" 的消息前面必须有一条带 tool_calls 的 assistant 消息。所以这样写执行时会报错
        messages.append(message)

        if message.tool_calls is None:
            reply = message.content
            return reply
        
        logger.info(f"tool_calls={str(message.tool_calls)}")

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            try:
                result = tool_map[name](**args)
            except Exception as e:
                result = f"工具执行错误：{e}"
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})
            logger.info(f"messages= {messages}")

if __name__ == "__main__":
    print("最小聊天程序（输入 quit 退出）")
    while True:
        user_input = input("\n你：")
        if user_input.strip().lower() == "quit":
            break
        reply = send_message(user_input)
        print(f"\n助手：{reply}")
