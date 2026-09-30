"""一次性大模型对话 Demo：读配置 -> 输入提示词 -> 流式调用大模型 -> 逐字打印回答。"""
import configparser

from openai import OpenAI

config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")
llm = config["llm"]

client = OpenAI(
    base_url=llm["base_url"],
    api_key=llm["api_key"],
)

prompt = input("请输入提示词：")

response = client.chat.completions.create(
    model=llm["model_name"],
    messages=[{"role": "user", "content": prompt}],
    stream=True,
)

print("---")
for chunk in response:
    print(chunk.choices[0].delta.content or "", end="", flush=True)
print()
