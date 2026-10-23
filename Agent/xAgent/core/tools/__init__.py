from __future__ import annotations

from .base import ToolRegistry, ToolSpec
from .basic import register_basic_tools
from .file_ops import register_file_tools


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    register_basic_tools(registry)
    register_file_tools(registry)
    return registry


__all__ = [
    "ToolRegistry",
    "ToolSpec",
    "build_default_registry",
    "register_basic_tools",
    "register_file_tools",
]
