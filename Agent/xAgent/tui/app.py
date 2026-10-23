from __future__ import annotations

import asyncio
import json
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Static

from core import (
    AgentError,
    AssistantDelta,
    ChatAgent,
    ToolCallFinished,
    ToolCallStarted,
    TurnFinished,
    load_settings,
)
from tui.screens import FilePreviewScreen
from tui.widgets import ChatView, ToolCallBlock


PREVIEW_THRESHOLD = 1000


class XAgentApp(App):
    """Textual front-end. All agent logic lives in the core package."""

    CSS_PATH = "styles.tcss"
    TITLE = "xAgent"
    SUB_TITLE = "本地文件操作 Agent"

    BINDINGS = [
        Binding("ctrl+c", "quit", "退出", priority=True),
        Binding("ctrl+l", "clear_view", "清屏"),
        Binding("ctrl+r", "reset_session", "重置会话"),
        Binding("escape", "stop_turn", "中止", show=True),
    ]

    def __init__(self, agent: ChatAgent | None = None) -> None:
        super().__init__()
        self.agent = agent
        self._busy = False
        self._stream_buffer = ""
        self._active_tool_block: ToolCallBlock | None = None
        self._preview_queue: list[tuple[str, str, str]] = []
        self._preview_open = False
        self._prompt_input: Input
        self._chat_view: ChatView
        self._stream_container: VerticalScroll
        self._stream_static: Static
        self._status_line: Static
        self._banner_widget: Static
        self._quick_buttons: list[Button] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="banner")
        yield ChatView(id="chat")
        with VerticalScroll(id="streaming"):
            yield Static("", id="streaming-text")
        with Horizontal(id="quick-actions"):
            yield Button("列出目录", id="btn-list", variant="primary", compact=True)
            yield Button("查看当前目录", id="btn-cwd", compact=True)
            yield Button("中止生成", id="btn-stop", variant="error", compact=True)
            yield Button(
                "重置会话",
                id="btn-reset",
                variant="warning",
                compact=True,
            )
        with Horizontal(id="composer"):
            yield Input(
                placeholder="输入消息，Enter 发送；Esc 中止；Ctrl+C 退出",
                id="prompt",
            )
            yield Static("就绪", id="status")
        yield Footer()

    async def on_mount(self) -> None:
        self._prompt_input = self.query_one("#prompt", Input)
        self._chat_view = self.query_one("#chat", ChatView)
        self._stream_container = self.query_one("#streaming", VerticalScroll)
        self._stream_static = self.query_one("#streaming-text", Static)
        self._status_line = self.query_one("#status", Static)
        self._banner_widget = self.query_one("#banner", Static)
        self._quick_buttons = [
            self.query_one("#btn-list", Button),
            self.query_one("#btn-cwd", Button),
            self.query_one("#btn-stop", Button),
            self.query_one("#btn-reset", Button),
        ]

        if self.agent is None:
            try:
                self.agent = ChatAgent(load_settings())
            except Exception as exc:
                self._banner_widget.update(
                    Text(f"配置错误: {exc}", style="bold red")
                )
                self._status_line.update("配置错误")
                self._set_busy(False)
                return

        self._banner_widget.update(self._banner_text())
        await self._chat_view.add_message("xAgent", self._welcome_text(), "system")
        self._set_busy(False)
        self._prompt_input.focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text or self._busy or self.agent is None:
            return
        event.input.value = ""
        await self._submit_prompt(text)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "btn-list":
            event.stop()
            await self._submit_prompt("请列出当前工作目录下的所有文件和子目录。")
        elif button_id == "btn-cwd":
            event.stop()
            await self._submit_prompt("请获取当前工作目录的完整路径。")
        elif button_id == "btn-stop":
            event.stop()
            await self.action_stop_turn()
        elif button_id == "btn-reset":
            event.stop()
            await self.action_reset_session()

    async def _submit_prompt(self, text: str) -> None:
        if not text or self._busy or self.agent is None:
            return
        await self._chat_view.add_message("你", text, "user")
        self._set_busy(True)
        self._status_line.update("思考中…")
        self._run_turn(text)

    @work(exclusive=True)
    async def _run_turn(self, text: str) -> None:
        if self.agent is None:
            return

        self._set_busy(True)
        self._status_line.update("思考中…")
        self._stream_buffer = ""
        self._hide_stream()
        self._active_tool_block = None

        try:
            async for event in self.agent.stream_turn(text):
                if isinstance(event, AssistantDelta):
                    self._stream_buffer += event.text
                    self._update_stream()
                elif isinstance(event, ToolCallStarted):
                    self._active_tool_block = await self._chat_view.add_tool_call(
                        event.name,
                        event.arguments,
                    )
                    self._status_line.update(f"执行 {event.name}…")
                elif isinstance(event, ToolCallFinished):
                    block = self._active_tool_block
                    self._active_tool_block = None
                    if (
                        event.name == "readTextFile"
                        and len(event.result) > PREVIEW_THRESHOLD
                    ):
                        if block is not None:
                            block.finish(
                                event.result,
                                display_result=(
                                    f"内容较长（{len(event.result)} 字符），"
                                    "已在文件预览弹窗中展示。"
                                ),
                            )
                            arguments = block.raw_arguments
                        else:
                            arguments = ""
                        self._open_preview(event.name, arguments, event.result)
                    elif block is not None:
                        block.finish(event.result)
                    else:
                        await self._chat_view.add_message(
                            "工具",
                            f"{event.name} 返回：\n{event.result}",
                            "system",
                        )
                    self._status_line.update("思考中…")
                elif isinstance(event, TurnFinished):
                    await self._finish_reply(event.content)
                    self._status_line.update("就绪")
                elif isinstance(event, AgentError):
                    self._hide_stream()
                    await self._chat_view.add_message(
                        "错误",
                        event.message,
                        "error",
                    )
                    self._status_line.update("出错")
        except asyncio.CancelledError:
            self._hide_stream()
            self._active_tool_block = None
            if self._busy:
                self._status_line.update("已中止")
            else:
                self._status_line.update("已取消")
            self._set_busy(False)
            if not self._preview_open:
                self._prompt_input.focus()
            return
        except Exception as exc:
            self._hide_stream()
            self._active_tool_block = None
            await self._chat_view.add_message(
                "错误",
                f"未处理错误: {exc}",
                "error",
            )
            self._status_line.update("出错")
        finally:
            self._active_tool_block = None
            if not self._busy:
                pass
            else:
                self._set_busy(False)
            if not self._preview_open:
                self._prompt_input.focus()

    async def action_clear_view(self) -> None:
        await self._chat_view.clear_chat()
        self._hide_stream()
        self._status_line.update("就绪")

    async def action_stop_turn(self) -> None:
        if not self._busy:
            self._status_line.update("无正在进行的任务")
            return
        self.workers.cancel_all()
        self._active_tool_block = None
        self._hide_stream()
        self._status_line.update("已中止")
        self._set_busy(False)
        if not self._preview_open:
            self._prompt_input.focus()

    async def action_reset_session(self) -> None:
        if self.agent is None:
            return
        self.workers.cancel_all()
        self.agent.reset()
        self._active_tool_block = None
        self._preview_queue.clear()
        self._set_busy(False)
        await self._chat_view.clear_chat()
        self._hide_stream()
        self._status_line.update("会话已重置")
        if not self._preview_open:
            self._prompt_input.focus()

    def action_quit(self) -> None:
        self.exit()

    def _banner_text(self) -> Text:
        assert self.agent is not None
        text = Text()
        text.append("xAgent", style="bold blue")
        text.append("  模型: ", style="dim")
        text.append(self.agent.settings.model_name, style="cyan")
        text.append("  工具: ", style="dim")
        text.append(str(len(self.agent.registry.names)), style="cyan")
        text.append("  目录: ", style="dim")
        text.append(str(Path.cwd()), style="cyan")
        return text

    @staticmethod
    def _welcome_text() -> str:
        return (
            "输入问题开始对话，也可以点击下方快捷按钮。\n"
            "Ctrl+L 清屏  ·  Ctrl+R 重置会话  ·  Ctrl+C 退出"
        )

    async def _finish_reply(self, content: str) -> None:
        self._hide_stream()
        await self._chat_view.add_message(
            "助手",
            content or "（空响应）",
            "assistant",
        )

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        ready = self.agent is not None
        if hasattr(self, "_prompt_input"):
            self._prompt_input.disabled = busy or not ready
        for button in self._quick_buttons:
            if button.id == "btn-reset":
                button.disabled = not ready
                continue
            if button.id == "btn-stop":
                button.disabled = not ready or not busy
                continue
            button.disabled = busy or not ready

    def _open_preview(
        self,
        tool_name: str,
        arguments: str,
        content: str,
    ) -> None:
        self._preview_queue.append((tool_name, arguments, content))
        self._show_next_preview()

    def _show_next_preview(self) -> None:
        if self._preview_open or not self._preview_queue:
            return
        tool_name, arguments, content = self._preview_queue.pop(0)
        self._preview_open = True
        self.push_screen(
            FilePreviewScreen(
                content=content,
                path=self._argument_value(arguments, "path"),
                tool_name=tool_name,
            ),
            callback=self._on_preview_closed,
        )

    def _on_preview_closed(self, _result: None) -> None:
        self._preview_open = False
        self._show_next_preview()

    @staticmethod
    def _argument_value(arguments: str, key: str) -> str:
        try:
            parsed = json.loads(arguments or "{}")
        except Exception:
            return ""
        value = parsed.get(key, "")
        return str(value) if value is not None else ""

    def _update_stream(self) -> None:
        self._stream_static.update(Text(self._stream_buffer))
        if not self._stream_container.has_class("visible"):
            self._stream_container.add_class("visible")
        self._stream_container.scroll_end(animate=False)

    def _hide_stream(self) -> None:
        self._stream_buffer = ""
        self._stream_static.update("")
        self._stream_container.remove_class("visible")
