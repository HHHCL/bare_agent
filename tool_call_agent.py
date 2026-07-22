import json

from openai import OpenAI
from config import Settings
from tools import *

"""
从mini_agent修改到tool_call_agent的步骤:
1. 定义工具函数（python定义两个函数）
2. 用json 格式描述工具（描述是有固定格式的嘛？？）
3. 调API时传入tools（上一步定义的json）
4. 重写agent收到prompt回复的过程，改成一个循环（这个步骤之前可以了解一下agent收到prompt后执行的逻辑，需要使用mcp服务的情况，一个流程图）
    （1）判断回复的message里tool_calls是否等于None，如果是，则回复的是文本，请求结果直接返回
    （2）如果不等于None，从tool_calls里取出tool.name和args，直接调用tool函数，获得返回结果
    （3）将tool的调用结果追加进messages里{"role":"tool", "tool_call_id": tool_call.id, "content": result}。但是在这个步骤之前要追加一个包含tool_calls字段的message
5. 添加循环次数上限和错误处理
"""

config = Settings()

client = OpenAI(api_key=config.api_key, base_url=config.base_url)

messages = [{"role": "system", "content":"你是一个有用的助手"}]

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
    
    print(f"tool_calls={str(message.tool_calls)}")
    for tool_call in message.tool_calls:
        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)
        try:
            result = tool_map[name](**args)
        except Exception as e:
            result = f"工具执行错误：{e}"
        messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})
        print(f"messages= {messages}")


if __name__ == "__main__":
    print("最小聊天程序（输入 quit 退出）")
    while True:
        user_input = input("\n你：")
        if user_input.strip().lower() == "quit":
            break
        reply = send_message(user_input)
        print(f"\n助手：{reply}")