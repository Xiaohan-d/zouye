# AnythingLLM MCP Server (MVP)

对接本机 AnythingLLM 的 MCP Server。仅实现一个工具：读取 AnythingLLM **第一个工作区**，回答提问「我的工作区有多少个文件」。

- MCP 协议版本：`2026-07-28`（modern / stateless）
- 传输协议：HTTP（streamable HTTP），**禁用 stdio**
- 依赖：Python 3.10+，`mcp` SDK（v2.x）

## 目录

```
server.py   MCP Server（仅一个工具 ask_first_workspace）
.env        本地配置（AnythingLLM 地址 / API Key / 服务地址）
README.md   本文件
```

## 工具

`ask_first_workspace(question)`：

1. 自动定位 AnythingLLM 第一个工作区
2. 提取工作区内文档信息（标题、字数、预估 token）
3. 默认问题为「我的工作区有多少个文件」，返回准确的文件数量
4. 同时将问题以 `query` 模式发给 AnythingLLM，返回 AI 回答与引用来源

## 安装

```powershell
# 首次：创建虚拟环境并安装依赖
python -m venv .venv
.\.venv\Scripts\pip install mcp
```

## 配置 `.env`

| 变量 | 说明 | 示例 |
| --- | --- | --- |
| `ANYTHINGLLM_BASE_URL` | AnythingLLM 地址 | `http://localhost:3001` |
| `ANYTHINGLLM_API_KEY` | API Key（AnythingLLM 设置 → API Keys 中生成） | `XXXX-XXXX-XXXX-XXXX` |
| `SERVER_HOST` | MCP 服务监听地址 | `127.0.0.1` |
| `SERVER_PORT` | MCP 服务端口 | `8000` |
| `MCP_PATH` | HTTP 端点路径 | `/mcp` |

> `.env` 含本地密钥，请勿提交到公共仓库。

## 启动

```powershell
.\.venv\Scripts\python server.py
```

启动成功后将在 HTTP（streamable HTTP）上监听：

```
http://127.0.0.1:8000/mcp
```

## 停止

```powershell
# 前台运行时直接 Ctrl+C

# 若后台运行，按端口结束进程
$pid = (Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess
Stop-Process -Id $pid -Force
```

## 客户端接入

在你的 MCP 客户端（需支持协议 2026-07-28 / streamable HTTP）中注册：

```
URL:  http://127.0.0.1:8000/mcp
传输: HTTP (streamable)，无认证
```

调用工具 `ask_first_workspace`（无需传参，默认提问「我的工作区有多少个文件」），即可得到第一个工作区的文件数量、文档信息与 AI 回答。