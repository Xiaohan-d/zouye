"""端到端自测脚本：用官方 SDK v2 的 `Client` 走 Streamable HTTP 连本地 MCP Server。

依次执行并检查：
1. `server/discover`（协议版本 / capabilities / resultType / ttlMs / cacheScope）
2. `tools/list`（只应包含 list_pets 一个工具及其 schema）
3. 若干次 `list_pets`：无参数 / 种类 / 状态 / 医生 / 费用区间 / 关键词 / 排序+分页
4. 参数校验：非法枚举 / min>max / 越界 / 负值 -> `isError: true`（非协议错误）

前置：pethospital.exe 于 127.0.0.1:8080，MCP Server 于 127.0.0.1:8000。退出码 0 表示全部通过。

用法：
    python client_test.py [mcp_url]   # 默认 http://127.0.0.1:8000/mcp
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from mcp import Client

DEFAULT_MCP_URL = "http://127.0.0.1:8000/mcp"

_PASS = 0
_FAIL = 0


def section(title: str) -> None:
    print(f"\n{'=' * 22} {title} {'=' * 22}")


def check(ok: bool, what: str, detail: str = "") -> bool:
    global _PASS, _FAIL
    if ok:
        _PASS += 1
        print(f"  [PASS] {what}")
    else:
        _FAIL += 1
        print(f"  [FAIL] {what}  {detail}")
    return ok


def dump(obj: Any, limit: int = 12) -> None:
    text = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    lines = text.splitlines()
    print("\n".join(lines[:limit]))
    if len(lines) > limit:
        print(f"  ... ({len(lines) - limit} 行已省略)")


def _summary_from(structured: dict[str, Any]) -> str:
    return structured.get("summary", "")


async def main() -> int:
    global _PASS

    mcp_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MCP_URL
    print(f"MCP Server: {mcp_url}")
    print("（若连接失败，请确认已启动：pethospital.exe 及 MCP Server）")

    async with Client(mcp_url) as client:
        # ---------- 1. server/discover ----------
        section("server/discover")
        discover = await client.session.discover()
        supported = list(discover.supported_versions)
        check("2026-07-28" in supported, f"supported 含 2026-07-28（supported={supported}）")
        check(discover.result_type == "complete", f"resultType=complete（实际 {discover.result_type}）")
        check(discover.ttl_ms is not None and discover.cache_scope is not None,
              f"缓存标注 ttlMs={discover.ttl_ms} cacheScope={discover.cache_scope}")
        check(discover.capabilities is not None, "capabilities 已通告")
        print(f"  协商协议版本：{client.protocol_version or discover.meta and '见上'}")

        # ---------- 2. tools/list ----------
        section("tools/list")
        listed = await client.list_tools()
        names = [t.name for t in listed.tools]
        check(names == ["list_pets"], f"工具清单只含 list_pets（实际 {names}）")
        check(listed.ttl_ms is not None and listed.cache_scope is not None,
              f"tools/list 缓存标注 ttlMs={listed.ttl_ms} cacheScope={listed.cache_scope}")
        tool = listed.tools[0]
        if tool.output_schema:
            print("  outputSchema 存在（JSON Schema 2020-12）")
        dump({"_sub": {"name": tool.name, "description": tool.description, "inputSchema": tool.input_schema,
                       "outputSchema": tool.output_schema}})

        # ---------- 3. 真实业务调用 ----------
        section("list_pets · 无参数（pageSize=2）")
        r = await client.call_tool("list_pets", {"page_size": 2})
        check(not r.is_error, "调用成功（isError=false）")
        sc = r.structured_content or {}
        check(sc.get("total", 0) > 0, f"命中总数 total={sc.get('total')}")
        for field in ("items", "total", "page", "pageSize", "totalPages", "totalCost", "summary"):
            check(field in sc, f"信封字段完整：{field}")
        print(f"  {_summary_from(sc)}")
        first_pet = sc["items"][0] if sc.get("items") else {}
        doctor_seed = first_pet.get("doctor", "")
        status_seed = first_pet.get("status", "")
        name_seed = first_pet.get("name", "")

        section("list_pets · 种类=犬")
        r = await client.call_tool("list_pets", {"species": "犬", "page_size": 5})
        sc = r.structured_content or {}
        ok = (not r.is_error) and sc.get("total", 0) > 0 and all(i.get("species") == "犬" for i in sc.get("items", []))
        check(ok, f"按种类筛选正确（total={sc.get('total')}，返回 {len(sc.get('items', []))} 条且均为犬）")
        print(f"  {_summary_from(sc)}")

        section("list_pets · 状态={status_seed}")
        r = await client.call_tool("list_pets", {"status": status_seed, "page_size": 5})
        sc = r.structured_content or {}
        ok = (not r.is_error) and all(i.get("status") == status_seed for i in sc.get("items", []))
        check(ok, f"按状态筛选正确（status={status_seed!r}，total={sc.get('total')}）")

        section("list_pets · 医生={doctor_seed}")
        r = await client.call_tool("list_pets", {"doctor": doctor_seed, "page_size": 5})
        sc = r.structured_content or {}
        ok = (not r.is_error) and sc.get("total", 0) > 0 and all(i.get("doctor") == doctor_seed for i in sc.get("items", []))
        check(ok, f"按医生筛选正确（doctor={doctor_seed!r}，total={sc.get('total')}）")

        section("list_pets · 费用区间 min/max")
        r = await client.call_tool("list_pets", {"min_cost": 500.0, "max_cost": 5000.0, "page_size": 5})
        sc = r.structured_content or {}
        items = sc.get("items", [])
        ok = (not r.is_error) and all(500.0 <= (i.get("totalCost") or 0) <= 5000.0 for i in items)
        check(ok, f"费用区间筛选正确（total={sc.get('total')}，返回 {len(items)} 条均落在 500–5000）")

        section("list_pets · 关键词 q={name_seed}")
        r = await client.call_tool("list_pets", {"q": name_seed})
        sc = r.structured_content or {}
        ok = (not r.is_error) and sc.get("total", 0) > 0
        check(ok, f"关键词查询正确（q={name_seed!r}，total={sc.get('total')}）")
        print(f"  {_summary_from(sc)}")

        section("list_pets · 排序 totalCost desc + 分页 page=2")
        r = await client.call_tool(
            "list_pets", {"sort_by": "totalCost", "order": "desc", "page": 2, "page_size": 5}
        )
        sc = r.structured_content or {}
        costs = [i.get("totalCost") or 0 for i in sc.get("items", [])]
        ok = (not r.is_error) and sc.get("page") == 2 and costs == sorted(costs, reverse=True)
        check(ok, f"排序+分页正确（page={sc.get('page')}，totalPages={sc.get('totalPages')}，费用降序）")

        # ---------- 4. 参数校验（isError，非协议错误） ----------
        section("参数校验 · 非法枚举 / min>max / 越界 / 负值")
        cases: list[tuple[str, dict[str, Any]]] = [
            ("非法物种枚举 species=龙", {"species": "龙"}),
            ("非法状态枚举 status=无", {"status": "无"}),
            ("min>max（2000 > 1000）", {"min_cost": 2000.0, "max_cost": 1000.0}),
            ("page_size 越界（200>100）", {"page_size": 200}),
            ("page 越界（0<1）", {"page": 0}),
            ("负花费（min=-1）", {"min_cost": -1.0}),
        ]
        for label, args in cases:
            r = await client.call_tool("list_pets", args)
            ok = r.is_error and _error_text(r)
            check(ok, f"{label} -> isError=true{'' if _error_text(r) else ''}")
            if r.is_error:
                print(f"    文本：{_error_text(r)[:80]}...")
            else:
                print(f"    意外：未置 isError，返回 {_summary_from(r.structured_content or {})}")

        # ---------- 上游不可达场景（可选，若 8080 正好被关） ----------
        section("小结")
        print(f"\n  共 {_PASS + _FAIL} 项断言：PASS={_PASS}，FAIL={_FAIL}")
        return 0 if _FAIL == 0 else 1


def _error_text(result: Any) -> str:
    if not result.content:
        return ""
    first = result.content[0]
    return getattr(first, "text", "") or str(first)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(asyncio.run(main()))