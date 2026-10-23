from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator
from typing import Any

from .config import LLMSettings
from .events import (
    AgentError,
    AgentEvent,
    AssistantDelta,
    ToolCallFinished,
    ToolCallStarted,
    TurnFinished,
)
from .llm import create_async_client
from .tools import ToolRegistry, build_default_registry


class ChatAgent:
    """UI-independent chat agent with streaming and tool-calling support."""

    def __init__(
        self,
        settings: LLMSettings,
        registry: ToolRegistry | None = None,
        client: Any | None = None,
        max_tool_rounds: int = 10,
    ) -> None:
        self.settings = settings
        self.registry = registry or build_default_registry()
        self.client = client or create_async_client(settings)
        self.max_tool_rounds = max(1, max_tool_rounds)
        self.messages: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    def reset(self) -> None:
        self.messages.clear()

    async def aclose(self) -> None:
        close = getattr(self.client, "close", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result

    async def stream_turn(self, user_text: str) -> AsyncIterator[AgentEvent]:
        text = (user_text or "").strip()
        if not text:
            yield AgentError("消息不能为空")
            return

        async with self._lock:
            self.messages.append({"role": "user", "content": text})

            for round_index in range(self.max_tool_rounds + 1):
                try:
                    response = await self.client.chat.completions.create(
                        model=self.settings.model_name,
                        messages=self.messages,
                        tools=self.registry.schemas,
                        tool_choice="auto",
                        stream=False,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    yield AgentError(f"调用模型失败: {exc}")
                    return

                if not response.choices:
                    yield AgentError("模型没有返回任何结果")
                    return

                message = response.choices[0].message
                tool_calls = getattr(message, "tool_calls", None)

                if tool_calls:
                    if round_index >= self.max_tool_rounds:
                        yield AgentError(
                            f"工具调用轮数超过上限 {self.max_tool_rounds}，已停止"
                        )
                        return

                    self.messages.append(
                        {
                            "role": "assistant",
                            "content": message.content or "",
                            "tool_calls": self._serialize_tool_calls(tool_calls),
                        }
                    )

                    for tool_call in tool_calls:
                        name = tool_call.function.name
                        arguments = tool_call.function.arguments or "{}"
                        yield ToolCallStarted(name=name, arguments=arguments)

                        try:
                            result = await asyncio.to_thread(
                                self.registry.execute, name, arguments
                            )
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            result = f"工具执行失败: {exc}"

                        self.messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": result,
                            }
                        )
                        yield ToolCallFinished(name=name, result=result)
                    continue

                try:
                    stream = await self.client.chat.completions.create(
                        model=self.settings.model_name,
                        messages=self.messages,
                        stream=True,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    yield AgentError(f"调用模型失败: {exc}")
                    return

                reply_parts: list[str] = []
                try:
                    async for chunk in stream:
                        if not chunk.choices:
                            continue
                        delta = chunk.choices[0].delta
                        content = getattr(delta, "content", None) or ""
                        if content:
                            reply_parts.append(content)
                            yield AssistantDelta(content)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    yield AgentError(f"读取模型流式响应失败: {exc}")
                    return

                reply = "".join(reply_parts)
                self.messages.append({"role": "assistant", "content": reply})
                yield TurnFinished(reply)
                return

    @staticmethod
    def _serialize_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:
        return [
            {
                "id": tool_call.id,
                "type": tool_call.type,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in tool_calls
        ]
