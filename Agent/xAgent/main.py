from __future__ import annotations

import sys

from core import ChatAgent, ConfigError, load_settings
from tui import XAgentApp


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"配置错误: {exc}", file=sys.stderr)
        return 1

    agent = ChatAgent(settings)
    XAgentApp(agent=agent).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
