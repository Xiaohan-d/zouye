from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static, TextArea


class FilePreviewScreen(ModalScreen[None]):
    """Read-only modal used to inspect long text returned by readTextFile."""

    BINDINGS = [Binding("escape", "close", "关闭")]

    def __init__(
        self,
        content: str,
        path: str = "",
        tool_name: str = "readTextFile",
    ) -> None:
        super().__init__()
        self._content = content
        self._path = path
        self._tool_name = tool_name

    def compose(self) -> ComposeResult:
        subtitle = (
            f"{self._tool_name}  ·  {self._path or '未知路径'}"
            f"  ·  {len(self._content)} 字符  ·  只读  ·  Esc 关闭"
        )
        with Vertical(id="preview-dialog"):
            yield Static("文件内容预览", id="preview-title", markup=False)
            yield Static(subtitle, id="preview-subtitle", markup=False)
            yield TextArea(
                self._content,
                read_only=True,
                show_line_numbers=True,
                show_cursor=False,
                highlight_cursor_line=False,
                id="preview-text",
            )
            with Horizontal(id="preview-actions"):
                yield Button("关闭", variant="primary", id="preview-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "preview-close":
            self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
