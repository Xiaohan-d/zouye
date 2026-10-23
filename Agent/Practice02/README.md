# Python Chat Agent：本地文件操作版

基于 `pythonchat2.py` 扩展的本地对话 Agent。主程序为 `chat-stream-tool-fileOps.py`，通过 OpenAI 兼容接口调用本地大模型，支持无限轮对话、上下文记忆、流式输出和 Function Call。

在原有 `getDate`、`isLeapYear` 两个工具的基础上，本项目新增 10 个本地文件操作工具，模型可以通过多轮工具调用完成目录查询、文件读取、文件创建、内容编辑、目录创建、删除和重命名等任务。

## 功能特性

- 无限循环对话，使用 `messages` 保存上下文历史。
- 通过 `tools` + `tool_choice="auto"` 让模型自主决定是否调用工具。
- 支持多轮工具调用：执行工具后把结果返回模型，继续推理，直到生成最终回答。
- 最终回答使用流式请求，逐字打印到控制台。
- 内置 10 个本地文件操作工具，覆盖查询、读取、创建、编辑、删除、重命名。
- 自动识别 UTF-8、UTF-8 BOM 和 GBK 纯文本，拒绝二进制文件读取和编辑。
- 带有基础安全保护：创建文件不覆盖、重命名不覆盖、拒绝删除或重命名根目录。

## 文件结构

```text
Practice02/
├─ chat-stream-tool-fileOps.py   # 主程序：对话循环、工具定义与文件操作实现
├─ arch.mmd                      # Mermaid 纯文本架构图
├─ README.md                     # 项目说明和工具清单
├─ config.ini                    # 大模型接口配置
├─ pythonchat.py                 # 早期基础对话 Demo
└─ pythonchat2.py                # 带 getDate / isLeapYear 的对话 Demo
```

## 快速开始

### 1. 安装依赖

```powershell
pip install openai
```

### 2. 配置模型

编辑 `config.ini`：

```ini
[llm]
base_url = http://localhost:11434/v1
model_name = qwen2.5:3b
api_key = your-api-key
```

`base_url` 和 `model_name` 请替换为实际使用的 OpenAI 兼容服务地址和模型名称。

### 3. 运行

在 `Practice02` 目录下执行：

```powershell
python chat-stream-tool-fileOps.py
```

程序会循环提示输入，输入 `Ctrl+C` 退出。

> 注意：代码通过相对路径读取 `config.ini`，因此建议在 `Practice02` 目录中启动程序。

## 架构概览

完整架构图见 [arch.mmd](arch.mmd)，该文件是纯 Mermaid 文本，可使用 Mermaid CLI、支持 Mermaid 的编辑器或在线渲染器查看。核心运行流程如下：

```text
用户输入
  -> 追加到 messages
  -> 携带 tools 请求模型
  -> 模型返回 tool_calls?
       ├─ 是：executeTool 执行工具 -> 追加 tool 结果 -> 再次请求模型
       └─ 否：流式生成最终回答 -> 逐字输出 -> 追加到 messages
```

代码分为四层：

1. **入口与配置层**：读取 `config.ini`，维护对话循环和 `messages` 历史。
2. **模型交互层**：调用 OpenAI SDK，判断是否需要工具调用。
3. **工具分发层**：`executeTool` 解析 JSON 参数，通过 `tool_functions` 注册表调用具体工具。
4. **工具实现层**：基础工具和 10 个本地文件操作工具，内部复用路径解析、文本编码检测、大小格式化和根目录保护等辅助函数。

## 工具清单

### 基础工具

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `getDate` | 无 | 调用 Windows `cmd /c date /t && time /t` 获取当前日期和时间 |
| `isLeapYear` | `year: integer` | 判断指定年份是否为闰年 |

### 文件操作工具

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `getCurrentWorkingDirectory` | 无 | 获取当前工作目录的绝对路径 |
| `listDirectory` | `path?: string` | 列出目录下所有文件和子目录，显示类型、大小和修改时间；默认当前目录 |
| `getFileType` | `path: string` | 获取扩展名、MIME 类型、文件大小，并判断是纯文本还是二进制 |
| `readTextFile` | `path: string` | 读取指定纯文本文件内容，二进制文件会被拒绝 |
| `createFile` | `directory: string`, `filename: string`, `content?: string` | 在指定目录创建文件，目录不存在时自动创建；文件已存在时不覆盖 |
| `editTextFile` | `path: string`, `content: string`, `mode?: string` | 编辑纯文本文件；`mode` 支持 `overwrite`、`append`、`prepend`，默认 `overwrite` |
| `createDirectory` | `path: string` | 创建目录，支持一次创建多级目录 |
| `deleteDirectory` | `path: string` | 递归删除目录及其中全部内容，支持非空目录 |
| `deleteFile` | `path: string` | 删除指定文件 |
| `renameFileOrDirectory` | `old_path: string`, `new_path: string` | 重命名文件或目录，也可用于移动；只给新文件名时保留在原目录 |

所有工具都返回字符串结果，失败的操作用中文错误信息返回给模型。

## 文本文件与编码策略

- 支持 UTF-8、UTF-8 BOM 和 GBK 文本。
- 通过 NUL 字节和控制字符比例初步判断二进制文件。
- `readTextFile` 最多返回前 100,000 个字符，超出部分会给出截断提示。
- `createFile` 创建的文本文件默认使用 UTF-8 编码。
- `editTextFile` 会沿用原文件检测到的编码；如果新内容无法用原编码保存，会返回错误。
- `readTextFile` 和 `editTextFile` 仅支持纯文本文件，不支持图片、压缩包、可执行文件等二进制内容。

## 安全与限制

- 本项目是本地演示程序，**没有沙箱隔离**，工具可以访问当前用户有权限访问的路径。
- `deleteDirectory` 会递归删除目录内容，调用前请确认路径正确。
- 已对文件系统根目录做删除和重命名保护，但没有路径白名单。
- `createFile` 和 `renameFileOrDirectory` 不会覆盖已存在的目标。
- `getDate` 使用 Windows 命令，跨平台运行时需要调整实现。
- 如需用于生产环境，建议增加工作目录白名单、操作确认、审计日志、回收站删除等机制。

## 使用示例

可以直接用自然语言描述任务，例如：

- “查看当前工作目录，并列出里面的文件。”
- “读取 `README.md` 的内容。”
- “在 `notes` 目录下创建 `todo.txt`，内容为：今天完成文件工具测试。”
- “在 `todo.txt` 末尾追加一行：明天检查编码处理。”
- “把 `notes/todo.txt` 重命名为 `notes/done.txt`。”
- “删除 `temp` 目录及其中的所有内容。”
- “现在几点了？顺便判断 2024 年是不是闰年。”

模型会根据任务自行选择工具；如果一次回答需要多个操作，程序会连续执行多轮工具调用，最后汇总结果并流式输出。
