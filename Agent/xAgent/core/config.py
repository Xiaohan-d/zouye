from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    """Raised when the LLM configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class LLMSettings:
    base_url: str
    model_name: str
    api_key: str


def default_config_path() -> Path:
    override = os.getenv("XAGENT_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[1] / "config.ini"


def load_settings(config_path: str | Path | None = None) -> LLMSettings:
    path = Path(config_path).expanduser() if config_path else default_config_path()
    parser = configparser.ConfigParser()
    if path.exists():
        parser.read(path, encoding="utf-8")

    section = parser["llm"] if parser.has_section("llm") else {}
    base_url = os.getenv("XAGENT_BASE_URL") or section.get("base_url", "")
    model_name = os.getenv("XAGENT_MODEL") or section.get("model_name", "")
    api_key = os.getenv("XAGENT_API_KEY") or section.get("api_key", "")

    base_url = base_url.strip()
    model_name = model_name.strip()
    api_key = api_key.strip()

    if not base_url:
        raise ConfigError(
            f"未配置 base_url，请检查 {path} 或设置环境变量 XAGENT_BASE_URL"
        )
    if not model_name:
        raise ConfigError(
            f"未配置 model_name，请检查 {path} 或设置环境变量 XAGENT_MODEL"
        )

    return LLMSettings(
        base_url=base_url,
        model_name=model_name,
        api_key=api_key or "not-needed",
    )
