from __future__ import annotations

import codecs
import mimetypes
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import ToolRegistry, ToolSpec

MAX_READ_CHARS = 100_000


def _resolve_path(path: str | None) -> Path:
    text = "" if path is None else str(path).strip()
    if not text:
        text = "."
    target = Path(text).expanduser()
    if not target.is_absolute():
        target = Path.cwd() / target
    return target.resolve()


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def _detect_text_encoding(path: Path) -> str | None:
    with open(path, "rb") as file:
        sample = file.read(65536)
    if not sample:
        return "utf-8"
    if b"\x00" in sample:
        return None
    control = sum(
        1 for byte in sample if byte < 32 and byte not in (8, 9, 10, 12, 13)
    )
    if control / len(sample) > 0.1:
        return None
    if sample.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    for encoding in ("utf-8", "gbk"):
        try:
            decoder = codecs.getincrementaldecoder(encoding)()
            decoder.decode(sample, final=False)
            return encoding
        except UnicodeDecodeError:
            continue
    return None


def _is_root(path: Path) -> bool:
    return path.parent == path


def _schema(
    properties: dict[str, Any] | None = None,
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties or {},
        "required": required or [],
    }


def get_current_working_directory() -> str:
    try:
        return f"当前工作目录: {Path.cwd()}"
    except Exception as exc:
        return f"获取当前工作目录失败: {exc}"


def list_directory(path: str = ".") -> str:
    try:
        target = _resolve_path(path)
        if not target.exists():
            return f"目录不存在: {target}"
        if not target.is_dir():
            return f"不是目录: {target}"

        entries = sorted(
            target.iterdir(),
            key=lambda item: (not item.is_dir(), item.name.lower()),
        )
        if not entries:
            return f"目录: {target}\n（目录为空）"

        lines = [f"目录: {target}"]
        for entry in entries:
            try:
                stat = entry.stat()
                modified = datetime.fromtimestamp(stat.st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if entry.is_dir():
                    lines.append(f"[目录] {entry.name}  修改时间: {modified}")
                else:
                    lines.append(
                        f"[文件] {entry.name}  大小: {_format_size(stat.st_size)}"
                        f"  修改时间: {modified}"
                    )
            except OSError as exc:
                lines.append(f"[未知] {entry.name}  读取信息失败: {exc}")
        lines.append(f"共 {len(entries)} 项")
        return "\n".join(lines)
    except Exception as exc:
        return f"列出目录失败: {exc}"


def get_file_type(path: str) -> str:
    try:
        target = _resolve_path(path)
        if not target.exists():
            return f"文件不存在: {target}"
        if target.is_dir():
            return f"路径: {target}\n类型: 目录"

        mime_type, _ = mimetypes.guess_type(target.name)
        suffix = target.suffix or "（无扩展名）"
        encoding = _detect_text_encoding(target)
        content_type = (
            f"纯文本（编码: {encoding}）" if encoding else "二进制文件"
        )

        return (
            f"路径: {target}\n"
            f"类型: 文件\n"
            f"扩展名: {suffix}\n"
            f"MIME 类型: {mime_type or '未知'}\n"
            f"大小: {_format_size(target.stat().st_size)}\n"
            f"内容类型: {content_type}"
        )
    except Exception as exc:
        return f"获取文件类型失败: {exc}"


def read_text_file(path: str) -> str:
    target: Path | None = None
    try:
        target = _resolve_path(path)
        if not target.exists():
            return f"文件不存在: {target}"
        if target.is_dir():
            return f"不是文件: {target}"

        encoding = _detect_text_encoding(target)
        if encoding is None:
            return f"不支持读取: {target} 不是纯文本文件"

        content = target.read_text(encoding=encoding)
        if not content:
            return "（文件为空）"
        if len(content) > MAX_READ_CHARS:
            content = (
                content[:MAX_READ_CHARS]
                + f"\n\n...（文件内容过长，仅显示前 {MAX_READ_CHARS} 个字符）"
            )
        return content
    except UnicodeDecodeError:
        return f"读取失败: {target} 不是可识别的纯文本文件"
    except Exception as exc:
        return f"读取文件失败: {exc}"


def create_file(directory: str, filename: str, content: str = "") -> str:
    try:
        if not filename or not str(filename).strip():
            return "创建文件失败: 文件名不能为空"

        name_path = Path(str(filename)).expanduser()
        if name_path.is_absolute():
            target = name_path.resolve()
        else:
            target = (_resolve_path(directory) / name_path).resolve()

        if target.exists():
            return f"文件已存在，未创建: {target}（如需修改请使用 editTextFile）"

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("" if content is None else str(content), encoding="utf-8")
        return f"已创建文件: {target}"
    except Exception as exc:
        return f"创建文件失败: {exc}"


def edit_text_file(path: str, content: str, mode: str = "overwrite") -> str:
    target: Path | None = None
    try:
        target = _resolve_path(path)
        if not target.exists():
            return f"文件不存在: {target}（请先使用 createFile）"
        if target.is_dir():
            return f"不是文件: {target}"

        encoding = _detect_text_encoding(target)
        if encoding is None:
            return f"不支持编辑: {target} 不是纯文本文件"

        mode = (mode or "overwrite").lower()
        if mode not in ("overwrite", "append", "prepend"):
            return f"不支持的编辑模式: {mode}（可选 overwrite / append / prepend）"

        content = "" if content is None else str(content)
        if mode == "overwrite":
            new_content = content
        else:
            old_content = target.read_text(encoding=encoding)
            if mode == "append":
                new_content = old_content + content
            else:
                new_content = content + old_content

        target.write_text(new_content, encoding=encoding)
        mode_text = {
            "overwrite": "覆盖写入",
            "append": "追加内容",
            "prepend": "插入内容",
        }[mode]
        return f"已{mode_text}: {target}（编码: {encoding}）"
    except UnicodeEncodeError:
        return f"编辑失败: {target} 无法使用原文件编码保存新内容"
    except Exception as exc:
        return f"编辑文件失败: {exc}"


def create_directory(path: str) -> str:
    try:
        target = _resolve_path(path)
        if target.exists():
            if target.is_dir():
                return f"目录已存在: {target}"
            return f"创建目录失败: {target} 已存在且不是目录"
        target.mkdir(parents=True, exist_ok=True)
        return f"已创建目录: {target}"
    except Exception as exc:
        return f"创建目录失败: {exc}"


def delete_directory(path: str) -> str:
    try:
        target = _resolve_path(path)
        if not target.exists() and not target.is_symlink():
            return f"目录不存在: {target}"
        if target.is_symlink():
            target.unlink()
            return f"已删除目录链接: {target}"
        if not target.is_dir():
            return f"不是目录: {target}（删除文件请使用 deleteFile）"
        if _is_root(target):
            return f"拒绝删除根目录: {target}"

        shutil.rmtree(target)
        return f"已删除目录及其全部内容: {target}"
    except Exception as exc:
        return f"删除目录失败: {exc}"


def delete_file(path: str) -> str:
    try:
        target = _resolve_path(path)
        if not target.exists() and not target.is_symlink():
            return f"文件不存在: {target}"
        if target.is_dir() and not target.is_symlink():
            return f"不是文件: {target}（删除目录请使用 deleteDirectory）"
        if _is_root(target):
            return f"拒绝删除根路径: {target}"

        target.unlink()
        return f"已删除文件: {target}"
    except Exception as exc:
        return f"删除文件失败: {exc}"


def rename_file_or_directory(old_path: str, new_path: str) -> str:
    try:
        source = _resolve_path(old_path)
        if not source.exists() and not source.is_symlink():
            return f"原路径不存在: {source}"
        if _is_root(source):
            return f"拒绝重命名根目录: {source}"

        new_name = Path(str(new_path)).expanduser()
        if not new_name.is_absolute() and new_name.parent == Path("."):
            destination = (source.parent / new_name).resolve()
        else:
            destination = _resolve_path(new_path)

        if destination.exists():
            return f"重命名失败: 目标路径已存在: {destination}"
        if not destination.parent.exists():
            return f"重命名失败: 目标目录不存在: {destination.parent}"

        is_directory = source.is_dir() and not source.is_symlink()
        source.rename(destination)
        kind = "目录" if is_directory else "文件"
        return f"已重命名{kind}: {source} -> {destination}"
    except Exception as exc:
        return f"重命名失败: {exc}"


def register_file_tools(registry: ToolRegistry) -> None:
    registry.register_all(
        [
            ToolSpec(
                name="getCurrentWorkingDirectory",
                description="获取当前工作目录的完整路径",
                parameters=_schema(),
                handler=get_current_working_directory,
            ),
            ToolSpec(
                name="listDirectory",
                description=(
                    "列出指定目录下的所有文件和子目录，"
                    "包含名称、类型、大小和修改时间"
                ),
                parameters=_schema(
                    {
                        "path": {
                            "type": "string",
                            "description": "要列出的目录路径，默认为当前工作目录",
                        }
                    }
                ),
                handler=list_directory,
            ),
            ToolSpec(
                name="getFileType",
                description=(
                    "获取指定文件的类型，包括扩展名、MIME 类型、"
                    "大小以及是否为纯文本"
                ),
                parameters=_schema(
                    {
                        "path": {
                            "type": "string",
                            "description": "要检查的文件路径",
                        }
                    },
                    ["path"],
                ),
                handler=get_file_type,
            ),
            ToolSpec(
                name="readTextFile",
                description="读取指定纯文本文件的内容，不支持二进制文件",
                parameters=_schema(
                    {
                        "path": {
                            "type": "string",
                            "description": "要读取的纯文本文件路径",
                        }
                    },
                    ["path"],
                ),
                handler=read_text_file,
            ),
            ToolSpec(
                name="createFile",
                description=(
                    "在指定目录下创建新文件，如果目录不存在会自动创建"
                    "（包括多级目录），文件已存在时不会覆盖"
                ),
                parameters=_schema(
                    {
                        "directory": {
                            "type": "string",
                            "description": "文件所在目录，可以是相对路径或绝对路径",
                        },
                        "filename": {
                            "type": "string",
                            "description": (
                                "文件名，可以包含子目录，例如 notes/todo.txt"
                            ),
                        },
                        "content": {
                            "type": "string",
                            "description": "文件的初始文本内容，默认为空",
                        },
                    },
                    ["directory", "filename"],
                ),
                handler=create_file,
            ),
            ToolSpec(
                name="editTextFile",
                description=(
                    "编辑指定纯文本文件的内容，"
                    "支持覆盖、追加到末尾、插入到开头三种模式"
                ),
                parameters=_schema(
                    {
                        "path": {
                            "type": "string",
                            "description": "要编辑的纯文本文件路径",
                        },
                        "content": {
                            "type": "string",
                            "description": "要写入的文本内容",
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["overwrite", "append", "prepend"],
                            "description": (
                                "编辑模式：overwrite 覆盖整个文件，"
                                "append 追加到末尾，prepend 插入到开头，"
                                "默认为 overwrite"
                            ),
                        },
                    },
                    ["path", "content"],
                ),
                handler=edit_text_file,
            ),
            ToolSpec(
                name="createDirectory",
                description="创建新目录，支持一次创建多级目录",
                parameters=_schema(
                    {
                        "path": {
                            "type": "string",
                            "description": "要创建的目录路径",
                        }
                    },
                    ["path"],
                ),
                handler=create_directory,
            ),
            ToolSpec(
                name="deleteDirectory",
                description="删除指定目录及其全部内容（支持非空目录），请谨慎使用",
                parameters=_schema(
                    {
                        "path": {
                            "type": "string",
                            "description": "要删除的目录路径",
                        }
                    },
                    ["path"],
                ),
                handler=delete_directory,
            ),
            ToolSpec(
                name="deleteFile",
                description="删除指定的文件",
                parameters=_schema(
                    {
                        "path": {
                            "type": "string",
                            "description": "要删除的文件路径",
                        }
                    },
                    ["path"],
                ),
                handler=delete_file,
            ),
            ToolSpec(
                name="renameFileOrDirectory",
                description="重命名文件或目录，也可以用于移动文件或目录",
                parameters=_schema(
                    {
                        "old_path": {
                            "type": "string",
                            "description": "原文件或目录的路径",
                        },
                        "new_path": {
                            "type": "string",
                            "description": (
                                "新路径；如果只给文件名，则重命名到原目录下；"
                                "否则按相对路径或绝对路径处理"
                            ),
                        },
                    },
                    ["old_path", "new_path"],
                ),
                handler=rename_file_or_directory,
            ),
        ]
    )
