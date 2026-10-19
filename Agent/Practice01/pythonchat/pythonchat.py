"""大模型对话 Demo（无限循环 + 上下文记忆）：读配置 -> 循环输入提示词 -> 携带历史消息流式调用大模型 -> 逐字打印回答，Ctrl+C 退出。"""
import configparser

from openai import OpenAI

config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")
llm = config["llm"]

client = OpenAI(
    base_url=llm["base_url"],
    api_key=llm["api_key"],
)

messages = []

while True:
    try:
        prompt = input("请输入提示词：")
    except (KeyboardInterrupt, EOFError):
        print()
        break

    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=llm["model_name"],
        messages=messages,
        stream=True,
    )

    print("---")
    reply = ""
    for chunk in response:
        delta = chunk.choices[0].delta.content or ""
        reply += delta
        print(delta, end="", flush=True)
    print()

    messages.append({"role": "assistant", "content": reply})
