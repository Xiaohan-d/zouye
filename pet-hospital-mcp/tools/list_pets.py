"""list_pets 工具：列出宠物档案（支持多条件筛选 / 排序 / 分页）。

- 底层调用：`GET {api}/api/v1/pets`（见 `upstream.UpstreamClient.list_pets`）
- 输入 schema 由类型注解自动生成（`Literal[...]` = 枚举，`Field` = 约束/描述）
- 输出：返回上游 `data` 信封本体（items/total/page/pageSize/totalPages/totalCost），
  `structuredContent` 即该结果，另附人类可读 `summary` 供模型判断是否翻页。
- 错误分层：参数不合法 / 上游失败 -> `ToolError`（对外是 `isError: true`，非协议错误）。
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.mcpserver.context import Context
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from upstream import UpstreamBusinessError, UpstreamClient, UpstreamError, UpstreamUnreachableError

TOOL_NAME = "list_pets"
TOOL_DESCRIPTION = (
    "列出宠物档案。可按关键词（跨字段）、宠物名、主人姓名、主人电话、种类、医生、疾病、"
    "就诊状态、总花费区间（min/max）进行筛选，并支持排序与分页。"
    "返回命中宠物列表 items、命中总数 total、分页字段（page/pageSize/totalPages）"
    "以及当前筛选条件下的费用汇总 totalCost，并附人类可读摘要 summary。"
)

SPECIES = ("犬", "猫", "兔", "鸟", "仓鼠", "爬宠", "其他")
STATUS = ("待就诊", "就诊中", "住院中", "已康复", "慢性病随访")
SORT_FIELDS = (
    "id",
    "name",
    "ownerName",
    "species",
    "doctor",
    "disease",
    "status",
    "totalCost",
    "visitCount",
    "createdAt",
    "updatedAt",
)

# ---- 输出 schema：与上游 Pet 对象字段对齐，structuredContent 即该结构 ----


class PetRecord(BaseModel):
    """历史病历记录。"""

    id: str | None = None
    visitDate: str | None = None
    doctor: str | None = None
    diagnosis: str | None = None
    symptoms: str | None = None
    treatment: str | None = None
    prescription: list[str] | None = None
    weightKg: float | None = None
    temperature: float | None = None
    followUp: str | None = None
    charge: float | None = None
    createdAt: str | None = None


class PetCharge(BaseModel):
    """消费明细。"""

    id: str | None = None
    item: str | None = None
    category: str | None = None
    amount: float | None = None
    doctor: str | None = None
    date: str | None = None


class Pet(BaseModel):
    """宠物档案对象（含派生字段 totalCost / visitCount）。"""

    id: str
    name: str | None = None
    species: str | None = None
    breed: str | None = None
    gender: str | None = None
    ageMonths: int | None = None
    color: str | None = None
    chipNo: str | None = None
    ownerName: str | None = None
    ownerPhone: str | None = None
    ownerAddr: str | None = None
    doctor: str | None = None
    disease: str | None = None
    status: str | None = None
    allergy: str | None = None
    note: str | None = None
    records: list[PetRecord] | None = None
    charges: list[PetCharge] | None = None
    totalCost: float | None = None
    visitCount: int | None = None
    createdAt: str | None = None
    updatedAt: str | None = None


class ListPetsResult(BaseModel):
    """list_pets 的返回结果（即上游 `data` 信封 + 人类可读摘要）。"""

    items: list[Pet] = Field(default_factory=list, description="命中宠物档案列表")
    total: int = Field(description="命中总数")
    page: int = Field(description="当前页码")
    pageSize: int = Field(description="每页条数")
    totalPages: int = Field(description="总页数")
    totalCost: float = Field(description="当前筛选条件下的费用汇总")
    summary: str = Field(description="人类可读摘要：命中总数、返回条数、分页、费用汇总与本次筛选条件")


async def list_pets(
    ctx: Context,
    q: Annotated[str | None, Field(description="全局关键词（跨字段，含病历全文）")] = None,
    name: Annotated[str | None, Field(description="宠物姓名")] = None,
    owner_name: Annotated[str | None, Field(description="主人姓名")] = None,
    owner_phone: Annotated[str | None, Field(description="主人电话")] = None,
    species: Annotated[Literal[SPECIES] | None, Field(description="种类")] = None,
    doctor: Annotated[str | None, Field(description="主治医生")] = None,
    disease: Annotated[str | None, Field(description="疾病/诊断")] = None,
    status: Annotated[Literal[STATUS] | None, Field(description="就诊状态")] = None,
    min_cost: Annotated[float | None, Field(ge=0, description="总花费下限（元）")] = None,
    max_cost: Annotated[float | None, Field(ge=0, description="总花费上限（元）")] = None,
    sort_by: Annotated[Literal[SORT_FIELDS] | None, Field(description="排序字段")] = None,
    order: Literal["asc", "desc"] = Field(default="desc", description="排序方向"),
    page: Annotated[int, Field(ge=1, description="页码，从 1 开始")] = 1,
    page_size: Annotated[int, Field(ge=1, le=100, description="每页条数（1–100）")] = 20,
) -> ListPetsResult:
    """列出宠物档案，支持多条件筛选、排序、分页。"""

    if min_cost is not None and max_cost is not None and min_cost > max_cost:
        raise ToolError(f"参数不合法：min_cost（{min_cost}）不能大于 max_cost（{max_cost}）。请修正后重试。")

    raw_params: list[tuple[str, Any, str]] = [
        ("q", q, "关键词"),
        ("name", name, "宠物名"),
        ("ownerName", owner_name, "主人姓名"),
        ("ownerPhone", owner_phone, "主人电话"),
        ("species", species, "种类"),
        ("doctor", doctor, "医生"),
        ("disease", disease, "疾病"),
        ("status", status, "状态"),
        ("min", min_cost, "花费下限"),
        ("max", max_cost, "花费上限"),
        ("sortBy", sort_by, "排序字段"),
        ("order", order, "排序方向"),
        ("page", page, "页码"),
        ("pageSize", page_size, "每页条数"),
    ]
    params: dict[str, Any] = {k: v for k, v, _ in raw_params if v is not None}
    filters: list[str] = [f"{label}={value}" for _, value, label in raw_params if value is not None]

    config = ctx.request_context.lifespan_context  # UpstreamConfig
    client = UpstreamClient(config.api_url, config.timeout)

    try:
        data = await client.list_pets(params)
    except UpstreamBusinessError as exc:
        raise ToolError(
            f"上游[宠物医院]业务处理失败：code={exc.code} message={exc.message!r}。"
            f"请核对查询参数是否合法，或稍后重试。"
        ) from exc
    except UpstreamUnreachableError as exc:
        raise ToolError(
            f"{exc}\n请检查：1) 是否已启动 pethospital.exe；2) PETHOSPITAL_API_URL 配置是否正确（当前：{config.api_url}）。"
        ) from exc
    except UpstreamError as exc:
        raise ToolError(f"上游响应解析失败：{exc}") from exc

    items = data.get("items", [])
    summary = (
        f"共命中 {data['total']} 条宠物档案，本次返回 {len(items)} 条"
        f"（第 {data['page']}/{data['totalPages']} 页，每页 {data['pageSize']} 条），"
        f"当前筛选条件下费用汇总 totalCost = {data['totalCost']:,.2f} 元。"
        f"本次筛选条件：{('、'.join(filters)) if filters else '无'}。"
        f"如 total > 返回条数，可通过 page 翻页继续查询。"
    )

    return ListPetsResult(
        items=items,
        total=data["total"],
        page=data["page"],
        pageSize=data["pageSize"],
        totalPages=data["totalPages"],
        totalCost=data["totalCost"],
        summary=summary,
    )