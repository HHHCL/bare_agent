from email import message

from openai import OpenAI
from config import Settings

config = Settings()
api_key = config.api_key

client = OpenAI(api_key=config.api_key, base_url=config.base_url)

messages = [{"role": "system", "content":"你是一个有用的助手"}]

def send_message(mes):
    messages.append({"role": "user", "content":mes})
    #发送prompt，获得返回内容
    response = client.chat.completions.create(
        model=config.model,
        messages=messages,
    )
    reply = response.choices[0].message.content
    # print(f"assitent reply = {reply}")
    messages.append({"role": "assistant", "content":reply})
    return reply

if __name__ == "__main__":
    print("最小聊天程序（输入 quit 退出）")
    while True:
        user_input = input("\n你：")
        if user_input.strip().lower() == "quit":
            break
        reply = send_message(user_input)
        print(f"\n助手：{reply}")