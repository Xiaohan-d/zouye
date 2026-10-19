# 课程实训项目汇总

本仓库为课程实训的代码整合提交，包含三个基于 **MCP（Model Context Protocol）协议** 的项目（围绕 AnythingLLM 与宠物医院管理系统展开），以及一个一次性大模型流式对话 Demo。

- 实训一：[Anythingllm-cmp](#实训一anythingllm-cmp) — AnythingLLM MCP Server（读取第一个工作区并回答提问）
- 实训二：[anythingllmserver](#实训二anythingllmserver) — AnythingLLM 文档上传前端页面
- 实训三：[pet-hospital-mcp](#实训三pet-hospital-mcp) — 宠物医院 MCP Server（宠物档案查询）
- 附加：[pythonchat](#附加pythonchat) — 一次性大模型流式对话 Demo（OpenAI 兼容接口，如本地 Ollama）

---

## 目录结构

```
zouye/
├── Anythingllm-cmp/        # 实训一：AnythingLLM MCP Server
│   ├── server.py            # MCP Server 入口（工具 ask_first_workspace）
│   ├── .env                 # 本地配置（AnythingLLM 地址 / API Key）
│   └── README.md            # 项目说明
├── anythingllmserver/       # 实训二：文档上传前端
│   └── index.html           # 单页上传工具
├── pet-hospital-mcp/        # 实训三：宠物医院 MCP Server
│   ├── server.py            # MCP Server 入口
│   ├── upstream.py          # 上游 REST API 客户端
│   ├── client_test.py       # 端到端自测脚本
│   ├── pyproject.toml       # 项目依赖与入口
│   └── tools/
│       └── list_pets.py     # list_pets 工具实现
└── pythonchat/              # 附加：一次性大模型流式对话
    ├── pythonchat.py        # 主程序（流式逐字打印回答）
    ├── config.ini           # LLM 配置（base_url / model_name / api_key）
    └── README.md            # 项目说明
```

---

## 技术栈

| 项目 | 技术 |
| --- | --- |
| Anythingllm-cmp | Python 3.10+、`mcp` SDK v2.x、Streamable HTTP |
| anythingllmserver | 原生 HTML/CSS/JavaScript（Fetch API） |
| pet-hospital-mcp | Python 3.11+、`mcp` SDK v2.x、`httpx2`、Pydantic |
| pythonchat | Python 3、`openai` SDK、OpenAI 兼容接口（如本地 Ollama） |

所有 MCP 项目均遵循 **MCP 协议版本 `2026-07-28`（modern / stateless）**，传输层采用 **Streamable HTTP**。

---

## 实训一：Anythingllm-cmp

### 项目介绍

对接本机 AnythingLLM 的 MCP Server。仅实现一个工具：读取 AnythingLLM **第一个工作区**，回答提问「我的工作区有多少个文件」。

### 功能

- 工具 `ask_first_workspace(question)`：
  1. 自动定位 AnythingLLM 第一个工作区
  2. 提取工作区内文档信息（标题、字数、预估 token）
  3. 默认问题为「我的工作区有多少个文件」，返回准确的文件数量
  4. 同时将问题以 `query` 模式发给 AnythingLLM，返回 AI 回答与引用来源

### 运行步骤

```powershell
# 1. 进入目录
cd Anythingllm-cmp

# 2. 创建虚拟环境并安装依赖
python -m venv .venv
.\.venv\Scripts\pip install mcp

# 3. 配置 .env（已提供示例，按需修改）
#    ANYTHINGLLM_BASE_URL / ANYTHINGLLM_API_KEY / SERVER_HOST / SERVER_PORT / MCP_PATH

# 4. 启动 MCP Server
.\.venv\Scripts\python server.py
```

启动后 MCP 端点为：`http://127.0.0.1:8000/mcp`

> 详见 [Anythingllm-cmp/README.md](Anythingllm-cmp/README.md)

---

## 实训二：anythingllmserver

### 项目介绍

AnythingLLM 文档上传工具的单页前端，支持将文档上传并向量化嵌入到 AnythingLLM 的第一个工作区。

### 功能

- 输入 AnythingLLM 服务器地址与 API Key
- 选择本地文件（文本 / PDF 等）
- 自动获取第一个工作区并上传文档
- 展示上传结果（工作区名称、嵌入文档列表、原始响应）

### 运行步骤

```powershell
# 1. 进入目录
cd anythingllmserver

# 2. 直接用浏览器打开 index.html 即可
#    或用任意静态服务器托管：
python -m http.server 8080
#    然后访问 http://localhost:8080
```

打开页面后填写服务器地址（默认 `http://localhost:3001`）、API Key，选择文件并点击「上传并嵌入」。

---

## 实训三：pet-hospital-mcp

### 项目介绍

宠物医院管理系统的 MCP 服务（MVP），封装上游 REST API 为 MCP 工具，供大模型按自然语言查询宠物档案。

### 功能

- 工具 `list_pets`：列出宠物档案，支持：
  - 多条件筛选：关键词（跨字段）、宠物名、主人姓名/电话、种类、医生、疾病、就诊状态、总花费区间
  - 排序：按 id / name / species / doctor / totalCost 等字段升序或降序
  - 分页：page / page_size（1–100）
  - 返回：宠物列表 items、命中总数 total、分页字段、费用汇总 totalCost、人类可读摘要 summary
- 完善的错误分层：参数不合法 / 上游不可达 / 业务失败均返回 `isError: true`
- 缓存标注：`server/discover` 与 `tools/list` 带 `ttlMs` / `cacheScope`

### 运行步骤

```powershell
# 1. 进入目录
cd pet-hospital-mcp

# 2. 创建虚拟环境并安装依赖
python -m venv .venv
.\.venv\Scripts\pip install -e .

# 3. 确保上游 pethospital.exe 已启动并监听 127.0.0.1:8080
#    （可通过环境变量 PETHOSPITAL_API_URL 自定义）

# 4. 启动 MCP Server
.\.venv\Scripts\python server.py
```

启动后 MCP 端点为：`http://127.0.0.1:8000/mcp`

### 自测

```powershell
# 运行端到端自测脚本（需同时启动 pethospital.exe 与 MCP Server）
.\.venv\Scripts\python client_test.py
```

---

## 附加：pythonchat

### 项目介绍

一次性大模型对话 Demo：读取 `config.ini` 中的 LLM 配置，接收用户提示词，先输出 `---` 分隔线，再以**流式**逐字打印模型回答，输出完毕程序结束。默认配置对接本机 Ollama 的 OpenAI 兼容接口。

### 运行步骤

```powershell
# 1. 进入目录
cd pythonchat

# 2. 安装依赖
pip install openai

# 3. 打开 config.ini，把 api_key 换成你自己的密钥（base_url、model_name 按需修改）

# 4. 运行，按提示输入问题并回车
python pythonchat.py
```

> 详见 [pythonchat/README.md](pythonchat/README.md)

---

## 环境变量说明

### Anythingllm-cmp（`.env`）

| 变量 | 说明 | 示例 |
| --- | --- | --- |
| `ANYTHINGLLM_BASE_URL` | AnythingLLM 地址 | `http://localhost:3001` |
| `ANYTHINGLLM_API_KEY` | API Key | `XXXX-XXXX-XXXX-XXXX` |
| `SERVER_HOST` | MCP 服务监听地址 | `127.0.0.1` |
| `SERVER_PORT` | MCP 服务端口 | `8000` |
| `MCP_PATH` | HTTP 端点路径 | `/mcp` |

### pet-hospital-mcp

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `PETHOSPITAL_API_URL` | 上游 REST 地址 | `http://127.0.0.1:8080` |
| `MCP_HOST` | 监听地址 | `127.0.0.1` |
| `MCP_PORT` | 监听端口 | `8000` |
| `MCP_LOG_LEVEL` | 日志级别 | `INFO` |

### pythonchat（`pythonchat/config.ini`）

| 变量 | 说明 | 示例 |
| --- | --- | --- |
| `base_url` | OpenAI 兼容接口地址 | `http://localhost:11434/v1` |
| `model_name` | 模型名称 | `qwen2.5:3b` |
| `api_key` | API 密钥 | 本地 Ollama 可任意填写；使用云端服务时替换为真实密钥 |

> ⚠️ `.env` 含本地密钥，已通过 `.gitignore` 排除，请勿提交到公共仓库。`pythonchat/config.ini` 已入库，其中仅为本地占位密钥，接入云端服务前请替换。
