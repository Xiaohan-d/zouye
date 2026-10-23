from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

ToolHandler = Callable[..., str]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def as_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Owns tool metadata and dispatches model tool calls to Python handlers."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, tool: ToolSpec) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具重复注册: {tool.name}")
        self._tools[tool.name] = tool

    def register_all(self, tools: Iterable[ToolSpec]) -> None:
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    @property
    def schemas(self) -> list[dict[str, Any]]:
        return [tool.as_openai_schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: str | dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"未知工具: {name}"

        try:
            parsed = self._parse_arguments(arguments)
        except ValueError as exc:
            return f"工具参数解析失败: {exc}"

        try:
            kwargs = self._filter_arguments(tool.handler, parsed)
            result = tool.handler(**kwargs)
        except TypeError as exc:
            return f"工具参数错误: {exc}"
        except Exception as exc:
            return f"工具执行失败: {exc}"

        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, default=str)

    @staticmethod
    def _parse_arguments(arguments: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(arguments, dict):
            return arguments
        try:
            parsed = json.loads(arguments or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(str(exc)) from exc
        if not isinstance(parsed, dict):
            raise ValueError("参数必须是 JSON 对象")
        return parsed

    @staticmethod
    def _filter_arguments(
        handler: ToolHandler, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        parameters = inspect.signature(handler).parameters
        accepts_any = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        if accepts_any:
            return arguments
        return {key: value for key, value in arguments.items() if key in parameters}
