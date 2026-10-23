from __future__ import annotations

import json

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Collapsible, Static


_ERROR_PREFIXES = (
    "未知工具",
    "工具参数",
    "工具执行失败",
    "文件不存在",
    "目录不存在",
    "不是文件",
    "不是目录",
    "拒绝",
    "不支持",
    "创建文件失败",
    "读取失败",
    "编辑失败",
    "删除目录失败",
    "删除文件失败",
    "重命名失败",
    "列出目录失败",
    "获取文件类型失败",
    "获取当前工作目录失败",
    "获取日期和时间失败",
    "获取日期和时间超时",
)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n...（已截断，共 {len(text)} 字符）"


def _looks_like_error(result: str) -> bool:
    return (result or "").lstrip().startswith(_ERROR_PREFIXES)


class MessageBlock(Vertical):
    """A single chat message, independent from the transport/LLM layer."""

    def __init__(self, role: str, content: str, kind: str) -> None:
        super().__init__(classes=f"message message-{kind}")
        self._role = role
        self._content = content

    def compose(self) -> ComposeResult:
        yield Static(self._role, classes="role", markup=False)
        yield Static(self._content or "（空）", classes="content", markup=False)


class ToolCallBlock(Collapsible):
    """Collapsed tool call summary with lazily visible details."""

    def __init__(self, name: str, arguments: str) -> None:
        self.tool_name = name
        self.raw_arguments = arguments or "{}"
        self._arguments_static = Static(
            self._arguments_text(),
            classes="tool-detail",
            markup=False,
        )
        self._result_static = Static(
            Text("等待执行…", style="dim"),
            classes="tool-detail",
        )
        details = Vertical(
            self._arguments_static,
            self._result_static,
            classes="tool-details",
        )
        super().__init__(
            details,
            title=f"⏳ 调用 {name}…",
            collapsed=True,
            classes="tool-block",
        )

    def finish(self, result: str, display_result: str | None = None) -> None:
        shown = display_result if display_result is not None else _truncate(result, 4000)
        self._result_static.update(Text(f"返回结果\n{shown}"))
        if _looks_like_error(result):
            self.title = f"❌ 调用 {self.tool_name} 失败"
            self.add_class("failure")
        else:
            self.title = f"✅ 调用 {self.tool_name} 成功"
            self.add_class("success")

    def _arguments_text(self) -> str:
        try:
            parsed = json.loads(self.raw_arguments)
            pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
        except Exception:
            pretty = self.raw_arguments
        return f"参数\n{pretty}"


class ChatView(VerticalScroll):
    """Scrollable conversation area containing message and tool-call widgets."""

    async def add_message(self, role: str, content: str, kind: str) -> None:
        await self.mount(MessageBlock(role, content, kind))
        self.scroll_end(animate=False)

    async def add_tool_call(self, name: str, arguments: str) -> ToolCallBlock:
        block = ToolCallBlock(name, arguments)
        await self.mount(block)
        self.scroll_end(animate=False)
        return block

    async def clear_chat(self) -> None:
        await self.remove_children()
