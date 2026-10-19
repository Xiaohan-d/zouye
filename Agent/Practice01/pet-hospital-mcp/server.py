"""宠物医院 MCP Server 入口（Streamable HTTP）。

MCP `2026-07-28` 规范（stateless：无 initialize 握手 / 无 Mcp-Session-Id 依赖），
协议细节由官方 SDK v2（`mcp>=2.0.0`）处理：`server/discover`、`resultType`、
缓存标注（ttlMs/cacheScope）、Streamable HTTP 头校验与 Origin（DNS rebinding）校验。
本文件只负责：组装 `MCPServer`、注册工具、日志（stderr）、启动参数/环境变量配置。

运行：
    uv run python server.py
    # 或
    .venv\\Scripts\\python.exe server.py

环境变量：
    PETHOSPITAL_API_URL   上游 REST 地址，默认 http://127.0.0.1:8080
    MCP_HOST              监听地址，默认 127.0.0.1（仅本机）
    MCP_PORT              监听端口，默认 8000
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

from mcp.server.caching import CacheHint
from mcp.server.mcpserver import MCPServer

from tools import list_pets as list_pets_tool
from upstream import DEFAULT_API_URL, UpstreamConfig

HOST = os.environ.get("MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_PORT", "8000"))
MCP_PATH = "/mcp"
API_URL = os.environ.get("PETHOSPITAL_API_URL", DEFAULT_API_URL)

log = logging.getLogger("pet-hospital-mcp")

# tools/list 与 server/discover 为列表类结果：标注缓存以符合 2026-07-28 缓存语义。
CACHE_HINTS = {
    "server/discover": CacheHint(ttl_ms=60_000, scope="public"),
    "tools/list": CacheHint(ttl_ms=60_000, scope="public"),
}


def _configure_logging() -> None:
    logging.basicConfig(
        stream=sys.stderr,
        level=os.environ.get("MCP_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


@asynccontextmanager
async def lifespan(server: MCPServer):
    """服务启动配置：读环境变量，向上游客户端/工具注入 base URL。"""
    config = UpstreamConfig(api_url=API_URL)
    log.info("加载上游配置：PETHOSPITAL_API_URL=%s", config.api_url)
    yield config


mcp = MCPServer(
    "pet-hospital-mcp",
    version="0.1.0",
    title="宠物医院 MCP Server",
    description="宠物医院管理系统的 MCP 服务（MVP：仅 list_pets，只读），基于 MCP 2026-07-28 Streamable HTTP。",
    lifespan=lifespan,
    cache_hints=CACHE_HINTS,
)

mcp.add_tool(
    list_pets_tool.list_pets,
    name=list_pets_tool.TOOL_NAME,
    description=list_pets_tool.TOOL_DESCRIPTION,
    structured_output=True,
)


def main() -> None:
    import asyncio

    _configure_logging()
    tools = asyncio.get_event_loop().run_until_complete(mcp.list_tools())
    log.info("=" * 60)
    log.info("宠物医院 MCP Server 已启动（协议 2026-07-28 · Streamable HTTP）")
    log.info("MCP 端点：http://%s:%d%s", HOST, PORT, MCP_PATH)
    log.info("上游 REST：%s", API_URL)
    log.info("已注册工具（%d）：%s", len(tools), ", ".join(tool.name for tool in tools))
    log.info("监听地址：%s（仅本机，Origin/DNS rebinding 防护由 SDK 启用）", HOST)
    log.info("=" * 60)
    mcp.run(
        transport="streamable-http",
        host=HOST,
        port=PORT,
        streamable_http_path=MCP_PATH,
        stateless_http=True,
    )


if __name__ == "__main__":
    main()