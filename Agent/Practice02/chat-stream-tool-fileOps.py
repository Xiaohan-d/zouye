"""大模型对话 Demo（无限循环 + 上下文记忆 + Function Call）：在 getDate / isLeapYear 的基础上新增本地文件操作工具，支持多轮工具调用。"""
import codecs
import configparser
import inspect
import json
import mimetypes
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from openai import OpenAI

config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")
llm = config["llm"]

client = OpenAI(
    base_url=llm["base_url"],
    api_key=llm["api_key"],
)

messages = []

MAX_READ_CHARS = 100000

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
    {
        "type": "function",
        "function": {
            "name": "getCurrentWorkingDirectory",
            "description": "获取当前工作目录的完整路径",
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
            "name": "listDirectory",
            "description": "列出指定目录下的所有文件和子目录，包含名称、类型、大小和修改时间",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要列出的目录路径，默认为当前工作目录",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "getFileType",
            "description": "获取指定文件的类型，包括扩展名、MIME 类型、大小以及是否为纯文本",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要检查的文件路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "readTextFile",
            "description": "读取指定纯文本文件的内容，不支持二进制文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要读取的纯文本文件路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "createFile",
            "description": "在指定目录下创建新文件，如果目录不存在会自动创建（包括多级目录），文件已存在时不会覆盖",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "文件所在目录，可以是相对路径或绝对路径",
                    },
                    "filename": {
                        "type": "string",
                        "description": "文件名，可以包含子目录，例如 notes/todo.txt",
                    },
                    "content": {
                        "type": "string",
                        "description": "文件的初始文本内容，默认为空",
                    },
                },
                "required": ["directory", "filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "editTextFile",
            "description": "编辑指定纯文本文件的内容，支持覆盖、追加到末尾、插入到开头三种模式",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要编辑的纯文本文件路径",
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的文本内容",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["overwrite", "append", "prepend"],
                        "description": "编辑模式：overwrite 覆盖整个文件，append 追加到末尾，prepend 插入到开头，默认为 overwrite",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "createDirectory",
            "description": "创建新目录，支持一次创建多级目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要创建的目录路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deleteDirectory",
            "description": "删除指定目录及其全部内容（支持非空目录），请谨慎使用",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要删除的目录路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deleteFile",
            "description": "删除指定的文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要删除的文件路径",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "renameFileOrDirectory",
            "description": "重命名文件或目录，也可以用于移动文件或目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "old_path": {
                        "type": "string",
                        "description": "原文件或目录的路径",
                    },
                    "new_path": {
                        "type": "string",
                        "description": "新路径；如果只给文件名，则重命名到原目录下；否则按相对路径或绝对路径处理",
                    },
                },
                "required": ["old_path", "new_path"],
            },
        },
    },
]


def _resolve_path(path):
    text = "" if path is None else str(path).strip()
    if not text:
        text = "."
    target = Path(text).expanduser()
    if not target.is_absolute():
        target = Path.cwd() / target
    return target.resolve()


def _format_size(size):
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024


def _detect_text_encoding(path):
    with open(path, "rb") as file:
        sample = file.read(65536)
    if not sample:
        return "utf-8"
    if b"\x00" in sample:
        return None
    control = sum(
        1 for byte in sample if byte < 32 and byte not in (8, 9, 10, 12, 13)
    )
    if control / len(sample) > 0.1:
        return None
    if sample.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    for encoding in ("utf-8", "gbk"):
        try:
            decoder = codecs.getincrementaldecoder(encoding)()
            decoder.decode(sample, final=False)
            return encoding
        except UnicodeDecodeError:
            continue
    return None


def _is_root(path):
    return path.parent == path


def getDate():
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
    year = int(year)
    if year % 4 == 0 and year % 100 != 0:
        return f"{year} 年是闰年"
    elif year % 400 == 0:
        return f"{year} 年是闰年"
    else:
        return f"{year} 年不是闰年"


def getCurrentWorkingDirectory():
    try:
        return f"当前工作目录: {Path.cwd()}"
    except Exception as e:
        return f"获取当前工作目录失败: {str(e)}"


def listDirectory(path="."):
    try:
        target = _resolve_path(path)
        if not target.exists():
            return f"目录不存在: {target}"
        if not target.is_dir():
            return f"不是目录: {target}"

        entries = sorted(
            target.iterdir(),
            key=lambda item: (not item.is_dir(), item.name.lower()),
        )
        if not entries:
            return f"目录: {target}\n（目录为空）"

        lines = [f"目录: {target}"]
        for entry in entries:
            try:
                stat = entry.stat()
                modified = datetime.fromtimestamp(stat.st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if entry.is_dir():
                    lines.append(f"[目录] {entry.name}  修改时间: {modified}")
                else:
                    lines.append(
                        f"[文件] {entry.name}  大小: {_format_size(stat.st_size)}  修改时间: {modified}"
                    )
            except OSError as e:
                lines.append(f"[未知] {entry.name}  读取信息失败: {e}")
        lines.append(f"共 {len(entries)} 项")
        return "\n".join(lines)
    except Exception as e:
        return f"列出目录失败: {str(e)}"


def getFileType(path):
    try:
        target = _resolve_path(path)
        if not target.exists():
            return f"文件不存在: {target}"
        if target.is_dir():
            return f"路径: {target}\n类型: 目录"

        mime_type, _ = mimetypes.guess_type(target.name)
        suffix = target.suffix or "（无扩展名）"
        encoding = _detect_text_encoding(target)
        if encoding:
            content_type = f"纯文本（编码: {encoding}）"
        else:
            content_type = "二进制文件"

        return (
            f"路径: {target}\n"
            f"类型: 文件\n"
            f"扩展名: {suffix}\n"
            f"MIME 类型: {mime_type or '未知'}\n"
            f"大小: {_format_size(target.stat().st_size)}\n"
            f"内容类型: {content_type}"
        )
    except Exception as e:
        return f"获取文件类型失败: {str(e)}"


def readTextFile(path):
    try:
        target = _resolve_path(path)
        if not target.exists():
            return f"文件不存在: {target}"
        if target.is_dir():
            return f"不是文件: {target}"

        encoding = _detect_text_encoding(target)
        if encoding is None:
            return f"不支持读取: {target} 不是纯文本文件"

        content = target.read_text(encoding=encoding)
        if not content:
            return "（文件为空）"
        if len(content) > MAX_READ_CHARS:
            content = (
                content[:MAX_READ_CHARS]
                + f"\n\n...（文件内容过长，仅显示前 {MAX_READ_CHARS} 个字符）"
            )
        return content
    except UnicodeDecodeError:
        return f"读取失败: {target} 不是可识别的纯文本文件"
    except Exception as e:
        return f"读取文件失败: {str(e)}"


def createFile(directory, filename, content=""):
    try:
        if not filename or not str(filename).strip():
            return "创建文件失败: 文件名不能为空"

        name_path = Path(str(filename)).expanduser()
        if name_path.is_absolute():
            target = name_path.resolve()
        else:
            target = (_resolve_path(directory) / name_path).resolve()

        if target.exists():
            return f"文件已存在，未创建: {target}（如需修改请使用 editTextFile）"

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("" if content is None else str(content), encoding="utf-8")
        return f"已创建文件: {target}"
    except Exception as e:
        return f"创建文件失败: {str(e)}"


def editTextFile(path, content, mode="overwrite"):
    try:
        target = _resolve_path(path)
        if not target.exists():
            return f"文件不存在: {target}（请先使用 createFile）"
        if target.is_dir():
            return f"不是文件: {target}"

        encoding = _detect_text_encoding(target)
        if encoding is None:
            return f"不支持编辑: {target} 不是纯文本文件"

        mode = (mode or "overwrite").lower()
        if mode not in ("overwrite", "append", "prepend"):
            return f"不支持的编辑模式: {mode}（可选 overwrite / append / prepend）"

        content = "" if content is None else str(content)
        if mode == "overwrite":
            new_content = content
        else:
            old_content = target.read_text(encoding=encoding)
            if mode == "append":
                new_content = old_content + content
            else:
                new_content = content + old_content

        target.write_text(new_content, encoding=encoding)
        mode_text = {
            "overwrite": "覆盖写入",
            "append": "追加内容",
            "prepend": "插入内容",
        }[mode]
        return f"已{mode_text}: {target}（编码: {encoding}）"
    except UnicodeEncodeError:
        return f"编辑失败: {target} 无法使用原文件编码保存新内容"
    except Exception as e:
        return f"编辑文件失败: {str(e)}"


def createDirectory(path):
    try:
        target = _resolve_path(path)
        if target.exists():
            if target.is_dir():
                return f"目录已存在: {target}"
            return f"创建目录失败: {target} 已存在且不是目录"
        target.mkdir(parents=True, exist_ok=True)
        return f"已创建目录: {target}"
    except Exception as e:
        return f"创建目录失败: {str(e)}"


def deleteDirectory(path):
    try:
        target = _resolve_path(path)
        if not target.exists() and not target.is_symlink():
            return f"目录不存在: {target}"
        if target.is_symlink():
            target.unlink()
            return f"已删除目录链接: {target}"
        if not target.is_dir():
            return f"不是目录: {target}（删除文件请使用 deleteFile）"
        if _is_root(target):
            return f"拒绝删除根目录: {target}"

        shutil.rmtree(target)
        return f"已删除目录及其全部内容: {target}"
    except Exception as e:
        return f"删除目录失败: {str(e)}"


def deleteFile(path):
    try:
        target = _resolve_path(path)
        if not target.exists() and not target.is_symlink():
            return f"文件不存在: {target}"
        if target.is_dir() and not target.is_symlink():
            return f"不是文件: {target}（删除目录请使用 deleteDirectory）"
        if _is_root(target):
            return f"拒绝删除根路径: {target}"

        target.unlink()
        return f"已删除文件: {target}"
    except Exception as e:
        return f"删除文件失败: {str(e)}"


def renameFileOrDirectory(old_path, new_path):
    try:
        source = _resolve_path(old_path)
        if not source.exists() and not source.is_symlink():
            return f"原路径不存在: {source}"
        if _is_root(source):
            return f"拒绝重命名根目录: {source}"

        new_name = Path(str(new_path)).expanduser()
        if not new_name.is_absolute() and new_name.parent == Path("."):
            destination = (source.parent / new_name).resolve()
        else:
            destination = _resolve_path(new_path)

        if destination.exists():
            return f"重命名失败: 目标路径已存在: {destination}"
        if not destination.parent.exists():
            return f"重命名失败: 目标目录不存在: {destination.parent}"

        is_directory = source.is_dir() and not source.is_symlink()
        source.rename(destination)
        kind = "目录" if is_directory else "文件"
        return f"已重命名{kind}: {source} -> {destination}"
    except Exception as e:
        return f"重命名失败: {str(e)}"


tool_functions = {
    "getDate": getDate,
    "isLeapYear": isLeapYear,
    "getCurrentWorkingDirectory": getCurrentWorkingDirectory,
    "listDirectory": listDirectory,
    "getFileType": getFileType,
    "readTextFile": readTextFile,
    "createFile": createFile,
    "editTextFile": editTextFile,
    "createDirectory": createDirectory,
    "deleteDirectory": deleteDirectory,
    "deleteFile": deleteFile,
    "renameFileOrDirectory": renameFileOrDirectory,
}


def executeTool(tool_call):
    function_name = tool_call.function.name
    function = tool_functions.get(function_name)
    if function is None:
        return f"未知工具: {function_name}"

    try:
        arguments = json.loads(tool_call.function.arguments or "{}")
        if not isinstance(arguments, dict):
            return "工具参数必须是 JSON 对象"
    except json.JSONDecodeError as e:
        return f"工具参数解析失败: {str(e)}"

    parameters = inspect.signature(function).parameters
    accepts_any = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
    if not accepts_any:
        arguments = {
            key: value for key, value in arguments.items() if key in parameters
        }

    try:
        result = function(**arguments)
    except TypeError as e:
        return f"工具参数错误: {str(e)}"
    except Exception as e:
        return f"工具执行失败: {str(e)}"

    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False)


while True:
    try:
        prompt = input("请输入提示词：")
    except (KeyboardInterrupt, EOFError):
        print()
        break

    messages.append({"role": "user", "content": prompt})

    while True:
        try:
            response = client.chat.completions.create(
                model=llm["model_name"],
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=False,
            )
        except Exception as e:
            print(f"发生错误: {e}")
            break

        message = response.choices[0].message
        tool_calls = message.tool_calls

        if tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": tool_call.type,
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                        for tool_call in tool_calls
                    ],
                }
            )

            for tool_call in tool_calls:
                tool_result = executeTool(tool_call)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result,
                    }
                )
            continue

        try:
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
        except Exception as e:
            print(f"发生错误: {e}")
        break
