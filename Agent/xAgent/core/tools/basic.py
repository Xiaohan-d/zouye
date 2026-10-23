from __future__ import annotations

import os
import subprocess
from datetime import datetime

from .base import ToolRegistry, ToolSpec


def get_date() -> str:
    if os.name != "nt":
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        result = subprocess.run(
            ["cmd", "/c", "date /t && time /t"],
            capture_output=True,
            text=True,
            timeout=5,
            encoding="gbk",
            errors="ignore",
        )
        output = result.stdout.strip() or result.stderr.strip()
        return output or "无法获取日期和时间"
    except subprocess.TimeoutExpired:
        return "获取日期和时间超时"
    except Exception as exc:
        return f"获取日期和时间失败: {exc}"


def is_leap_year(year: int) -> str:
    year = int(year)
    if year % 400 == 0 or (year % 4 == 0 and year % 100 != 0):
        return f"{year} 年是闰年"
    return f"{year} 年不是闰年"


def register_basic_tools(registry: ToolRegistry) -> None:
    registry.register_all(
        [
            ToolSpec(
                name="getDate",
                description="获取当前电脑的日期和时间",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=get_date,
            ),
            ToolSpec(
                name="isLeapYear",
                description="计算输入的年份是否是闰年",
                parameters={
                    "type": "object",
                    "properties": {
                        "year": {
                            "type": "integer",
                            "description": "要判断的年份，例如 2024",
                        }
                    },
                    "required": ["year"],
                },
                handler=is_leap_year,
            ),
        ]
    )
