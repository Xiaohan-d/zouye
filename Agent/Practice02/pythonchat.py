"""大模型对话 Demo（无限循环 + 上下文记忆 + Function Call）：读配置 -> 循环输入提示词 -> 携带历史消息流式调用大模型 -> 支持工具调用 getDate / isLeapYear -> 逐字打印回答，Ctrl+C 退出。"""
import configparser
import subprocess

from openai import OpenAI

config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")
llm = config["llm"]

client = OpenAI(
    base_url=llm["base_url"],
    api_key=llm["api_key"],
)

messages = []

tools = [
    {
        "type": "function",
        "function": {
            "name": "getDate",
            "description": "获取当前电脑的日期和时间",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "isLeapYear",
            "description": "计算输入的年份是否是闰年",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "要判断的年份，例如 2024",
                    }
                },
                "required": ["year"],
            },
        },
    },
]


def getDate():
    """调用本地 date / time 命令获取当前日期和时间"""
    try:
        result = subprocess.run(
            ["cmd", "/c", "date /t && time /t"],
            capture_output=True,
            text=True,
            timeout=5,
            encoding="gbk",
            errors="ignore",
        )
        if result.stdout:
            return result.stdout.strip()
        elif result.stderr:
            return result.stderr.strip()
        else:
            return "无法获取日期和时间"
    except subprocess.TimeoutExpired:
        return "获取日期和时间超时"
    except Exception as e:
        return f"获取日期和时间失败: {str(e)}"


def isLeapYear(year):
    """用 Python 代码计算某年是否是闰年"""
    year = int(year)
    if year % 4 == 0 and year % 100 != 0:
        return f"{year} 年是闰年"
    elif year % 400 == 0:
        return f"{year} 年是闰年"
    else:
        return f"{year} 年不是闰年"


tool_functions = {
    "getDate": getDate,
    "isLeapYear": isLeapYear,
}


while True:
    try:
        prompt = input("请输入提示词：")
    except (KeyboardInterrupt, EOFError):
        print()
        break

    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model=llm["model_name"],
            messages=messages,
            tools=tools,
            tool_choice="auto",
            stream=False,
        )

        message = response.choices[0].message
        tool_calls = message.tool_calls

        if tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )

            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = tool_call.function.arguments

                if function_name in tool_functions:
                    if function_name == "isLeapYear":
                        import json

                        args = json.loads(function_args or "{}")
                        function_result = tool_functions[function_name](args["year"])
                    else:
                        function_result = tool_functions[function_name]()

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": function_result,
                        }
                    )
                else:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": f"未知工具: {function_name}",
                        }
                    )

            final_response = client.chat.completions.create(
                model=llm["model_name"],
                messages=messages,
                stream=True,
            )

            print("---")
            reply = ""
            for chunk in final_response:
                delta = chunk.choices[0].delta.content or ""
                reply += delta
                print(delta, end="", flush=True)
            print()

            messages.append({"role": "assistant", "content": reply})

        else:
            response_stream = client.chat.completions.create(
                model=llm["model_name"],
                messages=messages,
                stream=True,
            )

            print("---")
            reply = ""
            for chunk in response_stream:
                delta = chunk.choices[0].delta.content or ""
                reply += delta
                print(delta, end="", flush=True)
            print()

            messages.append({"role": "assistant", "content": reply})

    except Exception as e:
        print(f"发生错误: {e}")
        continue
