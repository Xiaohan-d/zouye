"""上游「宠物医院」REST API 客户端。

只读（仅 GET），每次调用创建独立的 `httpx2.AsyncClient`，无任何共享可变状态，
天然支持并发。统一解析上游响应信封 `{ code, message, data, time }`：

- `code != 200`  -> `UpstreamBusinessError`
- 非 2xx / 超时 / 连接失败 -> `UpstreamUnreachableError`
- 响应非法（非 JSON / 无信封）-> `UpstreamError`
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx2

logger = logging.getLogger(__name__)

DEFAULT_API_URL = "http://127.0.0.1:8080"
DEFAULT_TIMEOUT = 10.0

LIST_PETS_PATH = "/api/v1/pets"  # 本 MVP 唯一使用的上游端点


class UpstreamError(Exception):
    """上游调用失败（业务失败 / HTTP 非 2xx / 网络不可达 / 响应非法）。"""


class UpstreamBusinessError(UpstreamError):
    """上游返回 `code != 200` 的业务失败。"""

    def __init__(self, code: int, message: str, *, data: dict[str, Any] | None = None) -> None:
        super().__init__(f"上游业务失败（code={code} message={message!r}）")
        self.code = code
        self.message = message
        self.data = data


class UpstreamUnreachableError(UpstreamError):
    """上游 HTTP 非 2xx、超时或网络不可达。"""


@dataclass(frozen=True)
class UpstreamConfig:
    """MCP Server 启动配置（由 lifespan 注入工具）。"""

    api_url: str = DEFAULT_API_URL
    timeout: float = DEFAULT_TIMEOUT


class UpstreamClient:
    """无状态上游 REST 客户端。"""

    def __init__(self, api_url: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout

    async def list_pets(self, params: dict[str, Any]) -> dict[str, Any]:
        """`GET {api}/api/v1/pets`，返回信封内 `data`。

        `data` 形如 `{ items, total, page, pageSize, totalPages, totalCost }`。
        """
        return await self._get(LIST_PETS_PATH, params)

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self.api_url}{path}"
        try:
            async with httpx2.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
            response.raise_for_status()
        except httpx2.TimeoutException as exc:
            raise UpstreamUnreachableError(
                f"上游 API 请求超时（{type(exc).__name__}）：{url}。"
                f"请确认已启动 pethospital.exe 且监听于 {self.api_url}。"
            ) from exc
        except httpx2.HTTPStatusError as exc:
            raise UpstreamUnreachableError(
                f"上游 API 返回非 2xx 状态码 {exc.response.status_code}：{url}"
            ) from exc
        except httpx2.TransportError as exc:
            raise UpstreamUnreachableError(
                f"上游 API 不可达（{type(exc).__name__}）：{url}。"
                f"请确认已启动 pethospital.exe 且监听于 {self.api_url}（环境变量 PETHOSPITAL_API_URL 可配置）。"
            ) from exc

        try:
            envelope = response.json()
        except ValueError as exc:
            raise UpstreamError(f"上游响应不是合法 JSON：{url}") from exc

        if not isinstance(envelope, dict) or "code" not in envelope:
            raise UpstreamError(f"上游响应缺少统一信封（code 字段）：{url}")

        if envelope.get("code") != 200:
            raise UpstreamBusinessError(
                envelope["code"],
                str(envelope.get("message", "")),
                data=envelope.get("data"),
            )

        return envelope.get("data")