"""路由标量参数 ↔ 受约束 DTO 字段的边界契约测试（500 家族门禁）。

存在理由（09-24 参数化 GET 全量扫掠结论，855 端点 / 4×500）：
FastAPI 只校验**它自己声明在签名上的**约束。若路由把裸标量形参（无 `Path()`/`Query()`
边界，或只有 `min_length` 而无 `max_length`）直接透传给某个 pydantic 模型构造器，
而该模型的对应字段**带约束**，则越界输入会：

1. 通过 FastAPI 的请求校验（路由侧没写边界）；
2. 在 handler 内触发 pydantic `ValidationError`；
3. 因为它是**运行期异常**而非请求校验错误，被兜底成 **500 INTERNAL**。

正确行为是 400 VALIDATION —— 平台自身的 POST 兄弟端点就是这么做的
（`POST /v1/ontology/graph/query` body 里 `hops=6` → `400 {"code":"VALIDATION", ...}`）。

线上实测（本文件修复前，8080 旧代码）：
| 注入点 | 输入 | 结果 |
|---|---|---|
| `GET /v1/objects/{ot}/{oid}/neighbors/{hops}` | `hops=0` / `hops=6` | **500 INTERNAL** |
| `GET /v1/aip/memory-authority/agent-instances/{id}/memory-context` | `instance_id` 300 字符 | **500 INTERNAL** |
| 同上 | `skillId` 300 字符 | **500 INTERNAL** |
| 同上 | `logicId` 300 字符 | **500 INTERNAL** |

本文件两条锁：
- `test_no_route_scalar_bypasses_dto_bound`：AST 全量扫描，锁住整族（新增即红）。
- 行为断言：越界输入必须得到 400 `VALIDATION`，而不是 500。

---

**第二批（同族，约束权威在下游 SQL 而不是 pydantic）**

探针 K（数值型 query 参数取边界值 `0`/`-1`，覆盖 111 个端点 / 266 个变体）又抓出
第 6 处 500，但它的约束不在任何 DTO 里，而在 **PostgreSQL**：

| 注入点 | 输入 | 结果 |
|---|---|---|
| `GET /v1/aip/capacity/usage` | `limit=-1` | **500 INTERNAL** |

栈帧：`model_capacity.py:131 list_usage` → `psycopg.errors.InvalidRowCountInLimitClause:
LIMIT must not be negative`。路由原文是 `limit: int = Query(30, le=365)` —— **只有上界、没有下界**。
⇒ `probe F` 的「路由 ↔ DTO 边界」判据**结构上看不到这一类**（没有 DTO 可比）。

故本文件再加一条同族判据：**路由把无下界的数值参数传给「函数体内含 `LIMIT %s` / `OFFSET %s`
的引擎函数」⇒ 红**（`test_no_unbounded_param_reaches_sql_limit`）。

⚠️ 注意一条会误导人的假安全信号：很多端点在 `limit=-1` 下返回 **200**，但那只是因为**表是空的**
（`items[:-1]` 对空列表无害）。而 **SQL `LIMIT -1` 是确定性报错**，与数据量无关
⇒ 对「进 SQL」的这条子链，`-1` 是决定性探针；对「Python 切片」的链则不是（见 §待办）。

⚠️ **判据边界：路由有下界 ≠ 唯一合法修法**。真正的判据是「值有没有**不被夹取地**到达 SQL」。
首版门禁只认路由签名，于是把 `GET /v1/schedules/{id}/runs` 判红；复核被调端
`qyh_cron_scheduler.list_runs` 第一行就是 `safe_limit = max(1, min(int(limit), 100))`
⇒ **值根本没有裸奔到 SQL**，静态命中 ≠ 缺陷（本族第 2 次踩同一个坑）。
故判据升级为：路由无下界 **且** 被调函数在 SQL 之前**未**对该参数做 `min()/max()` 夹取 ⇒ 红。
`_callee_clamps_param()` 是启发式（只看 `min/max` 调用是否引用该形参、且行号早于 SQL 常量），
用 `test_gate_flags_sql_limit_shape_when_clamp_ignored` 做正对照，保证豁免不是把门禁整体关掉。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from aos_api.auth import Principal, require_principal

API_ROOT = Path(__file__).resolve().parents[1] / "aos_api"

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
_CONSTRAINT_KW = {
    "ge", "le", "gt", "lt", "min_length", "max_length",
    "pattern", "regex", "multiple_of", "min_items", "max_items",
}
_MODEL_BASES = {"BaseModel", "FrozenDTO", "DTO"}
_SKIP_ANN = ("Depends", "Request", "Response", "Principal", "UploadFile", "BackgroundTasks")


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8-sig"))
    except SyntaxError:
        return None  # 带 BOM/非标准编码的存量文件跳过（与生产加载路径无关）


def _is_route(fn: ast.FunctionDef) -> bool:
    for dec in fn.decorator_list:
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            if dec.func.attr in _HTTP_METHODS:
                return True
    return False


def _collect_models() -> dict[str, dict[str, set[str]]]:
    """模型类名 -> {字段: 约束关键字集合}。"""
    models: dict[str, dict[str, set[str]]] = {}
    for path in API_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = {ast.unparse(b).split(".")[-1] for b in node.bases}
            looks_like_model = (
                bool(bases & _MODEL_BASES)
                or any(b.endswith(("DTO", "Model", "Request", "In", "Out")) for b in bases)
                or node.name.endswith(("DTO", "Request", "In"))
            )
            if not looks_like_model:
                continue
            fields: dict[str, set[str]] = {}
            for stmt in node.body:
                if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
                    continue
                if not isinstance(stmt.value, ast.Call):
                    continue
                callee = ast.unparse(stmt.value.func).split(".")[-1]
                if callee not in {"Field", "Query", "Body", "Path"}:
                    continue
                kws = {k.arg for k in stmt.value.keywords if k.arg} & _CONSTRAINT_KW
                if kws:
                    fields[stmt.target.id] = kws
            if fields:
                models[node.name] = fields
    return models


def _route_scalar_params(fn: ast.FunctionDef) -> tuple[set[str], dict[str, set[str]]]:
    """返回 (未带边界的标量形参名, 各形参已声明的约束集合)。"""
    defaults: dict[str, ast.expr] = {}
    pos = list(fn.args.args)
    if fn.args.defaults:
        for arg, d in zip(pos[-len(fn.args.defaults):], fn.args.defaults):
            defaults[arg.arg] = d
    for arg, d in zip(fn.args.kwonlyargs, fn.args.kw_defaults):
        if d is not None:
            defaults[arg.arg] = d

    raw: set[str] = set()
    declared: dict[str, set[str]] = {}
    for a in list(fn.args.args) + list(fn.args.kwonlyargs):
        if a.arg in ("self", "cls"):
            continue
        ann = ast.unparse(a.annotation) if a.annotation else ""
        if any(k in ann for k in _SKIP_ANN):
            continue
        kws: set[str] = set()
        d = defaults.get(a.arg)
        if isinstance(d, ast.Call):
            kws = {k.arg for k in d.keywords if k.arg} & _CONSTRAINT_KW
        declared[a.arg] = kws
        if not kws:
            raw.add(a.arg)
    return raw, declared


def _find_violations() -> list[str]:
    models = _collect_models()
    out: list[str] = []
    for path in API_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or not _is_route(node):
                continue
            raw, declared = _route_scalar_params(node)
            if not raw and not declared:
                continue
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                cname = ast.unparse(sub.func).split(".")[-1]
                if cname not in models:
                    continue
                for kw in sub.keywords:
                    if kw.arg is None or not isinstance(kw.value, ast.Name):
                        continue
                    var = kw.value.id
                    if var not in declared or kw.arg not in models[cname]:
                        continue
                    missing = models[cname][kw.arg] - declared[var]
                    if missing:
                        out.append(
                            f"{path.relative_to(API_ROOT.parent)}:{sub.lineno} "
                            f"{node.name}({var}) -> {cname}.{kw.arg} 缺约束 {sorted(missing)}"
                        )
    return sorted(set(out))


def test_no_route_scalar_bypasses_dto_bound() -> None:
    """整族门禁：路由裸标量透传给受约束 DTO 字段而不补齐边界 ⇒ 红。"""
    violations = _find_violations()
    assert not violations, (
        "以下路由参数绕过了 DTO 边界（越界输入会变成 500 而非 400）：\n  "
        + "\n  ".join(violations)
    )


def test_gate_detects_the_known_defect_shape() -> None:
    """自检：门禁必须能抓到已知缺陷形态（否则门禁本身失效）。"""
    tree = ast.parse(
        "from fastapi import APIRouter, Depends\n"
        "router = APIRouter()\n"
        "@router.get('/x/{hops}')\n"
        "def h(hops: int, principal=Depends(None)):\n"
        "    return SomeDTO(hops=hops)\n"
    )
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    raw, declared = _route_scalar_params(fn)
    assert "hops" in raw and declared["hops"] == set()
    assert {"ge", "le"} - declared["hops"] == {"ge", "le"}  # 缺约束被识别


# ─────────────── 行为断言：越界 ⇒ 400，不是 500 ───────────────

_H64 = "a" * 64


def _client(router):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from aos_api.errors import register_exception_handlers

    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="route-param-bound-test",
        org_id="org-org",
        project_id="dev-project",
        roles=["developer", "admin"],
        markings=["public"],
        token_kind="test",
    )
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("hops", ["0", "6", "999999999"])
def test_neighbors_hops_out_of_range_is_400(hops: str) -> None:
    """`hops` 越界必须是 400 VALIDATION（修复前为 500 INTERNAL）。"""
    from aos_api.routers.ontology_governance import router

    resp = _client(router).get(f"/v1/objects/WorkOrder/oid/neighbors/{hops}")
    assert resp.status_code == 400, f"hops={hops} 得到 {resp.status_code}"
    body = resp.json()
    assert body["code"] == "VALIDATION"
    assert any("hops" in str(e.get("loc")) for e in body["details"]["errors"])


@pytest.mark.parametrize("hops", ["1", "5"])
def test_neighbors_hops_in_range_passes_validation(hops: str) -> None:
    """边界内取值必须通过请求校验（不再被误拦）。"""
    from aos_api.routers.ontology_governance import router

    resp = _client(router).get(f"/v1/objects/WorkOrder/oid/neighbors/{hops}")
    assert resp.status_code != 400, f"hops={hops} 被误拦为 400"


def _memory_query(**over: str) -> dict[str, str]:
    q = {
        "instanceRevision": "1",
        "instanceHash": _H64,
        "skillId": "skill-1",
        "skillRevision": "1",
        "skillHash": _H64,
        "logicId": "logic-1",
        "logicRevision": "1",
        "logicHash": _H64,
        "purpose": "analysis",
        "timeCutoff": "2026-01-01T00:00:00Z",
    }
    q.update(over)
    return q


@pytest.mark.parametrize("field", ["instance_id", "skillId", "logicId"])
def test_memory_context_overlong_asset_id_is_400(field: str) -> None:
    """三个直接充当 `VersionedAssetRef.asset_id` 的注入点，越界必须 400。"""
    from aos_api.routers.aip_memory_improvement import router

    long_id = "a" * 300
    if field == "instance_id":
        url = f"/v1/aip/memory-authority/agent-instances/{long_id}/memory-context"
        params = _memory_query()
    else:
        url = "/v1/aip/memory-authority/agent-instances/probe-1/memory-context"
        params = _memory_query(**{field: long_id})

    resp = _client(router).get(url, params=params)
    assert resp.status_code == 400, f"{field} 越界得到 {resp.status_code}"
    assert resp.json()["code"] == "VALIDATION"


# ─────────────── 第二批：约束权威在下游 SQL（LIMIT/OFFSET） ───────────────

_SQL_LIMIT_RX = re.compile(r"\b(LIMIT|OFFSET)\s+%s", re.I)
_BOUNDED_KW = {"ge", "gt"}
_SIZE_KW = {"limit", "offset", "page_size", "pageSize"}
_CLAMP_FUNCS = {"min", "max"}
_FUNC_CACHE: dict[str, dict[str, ast.AST]] = {}


def _parse_rel(rel: str) -> ast.Module | None:
    path = API_ROOT.parent / rel
    return _parse(path) if path.exists() else None


def _func_index(rel: str) -> dict[str, ast.AST]:
    """`{函数名: 函数节点}`（带缓存）；同名重载取首个。"""
    if rel not in _FUNC_CACHE:
        idx: dict[str, ast.AST] = {}
        tree = _parse_rel(rel)
        if tree is not None:
            for fn in ast.walk(tree):
                if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    idx.setdefault(fn.name, fn)
        _FUNC_CACHE[rel] = idx
    return _FUNC_CACHE[rel]


def _callee_clamps_param(rel: str, func: str, param: str) -> bool:
    """被调函数是否在 SQL `LIMIT/OFFSET` **之前**对该形参做了 `min()/max()` 夹取。

    启发式（故意保守，宁可漏报夹具也不误报缺陷）：
    - 只看直接引用该形参名的 `min()/max()` 调用（`min(int(limit), 100)` 亦覆盖）；
    - 只认行号早于含 `LIMIT %s` 字符串常量的语句；
    - 找不到函数体 / 找不到 SQL ⇒ 返回 False（即按「会裸奔」处理）。
    """
    fn = _func_index(rel).get(func)
    if fn is None:
        return False
    sql_line: int | None = None
    for node in ast.walk(fn):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _SQL_LIMIT_RX.search(node.value):
                sql_line = node.lineno if sql_line is None else min(sql_line, node.lineno)
    if sql_line is None:
        return False
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        if ast.unparse(node.func).split(".")[-1] not in _CLAMP_FUNCS:
            continue
        if node.lineno > sql_line:
            continue
        for arg in node.args:
            if any(isinstance(n, ast.Name) and n.id == param for n in ast.walk(arg)):
                return True
    return False


def _sql_limit_funcs() -> dict[str, set[str]]:
    """{模块相对路径: {含 `LIMIT %s`/`OFFSET %s` 的函数名}}。"""
    out: dict[str, set[str]] = {}
    for path in API_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        names = set()
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if _SQL_LIMIT_RX.search(node.value):
                        names.add(fn.name)
                        break
        if names:
            out[str(path.relative_to(API_ROOT.parent))] = names
    return out


def _route_unbounded_params(fn) -> set[str]:
    """路由函数里**没有下界**（无 ge/gt，且注解为数值）的形参名。"""
    defaults: dict[str, ast.expr] = {}
    pos = list(fn.args.args)
    if fn.args.defaults:
        for a, d in zip(pos[-len(fn.args.defaults):], fn.args.defaults):
            defaults[a.arg] = d
    for a, d in zip(fn.args.kwonlyargs, fn.args.kw_defaults):
        if d is not None:
            defaults[a.arg] = d
    out = set()
    for a in pos + list(fn.args.kwonlyargs):
        ann = ast.unparse(a.annotation) if a.annotation else ""
        if any(k in ann for k in _SKIP_ANN):
            continue
        if ann.strip() not in ("int", "int | None", "float", "float | None"):
            continue
        d = defaults.get(a.arg)
        kws = {k.arg for k in d.keywords if k.arg} if isinstance(d, ast.Call) else set()
        if not (kws & _BOUNDED_KW):
            out.add(a.arg)
    return out


def _find_sql_limit_violations(ignore_callee_clamp: bool = False) -> list[str]:
    limit_funcs = _sql_limit_funcs()
    hits: list[str] = []
    for path in API_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        # 本文件导入的「含 SQL LIMIT 的函数」→ 定义模块
        imported: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("aos_api"):
                mod = str(Path(*node.module.split(".")).with_suffix(".py"))
                for al in node.names:
                    if mod in limit_funcs and al.name in limit_funcs[mod]:
                        imported[al.name] = mod
        if not imported:
            continue
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or not _is_route(fn):
                continue
            unbounded = _route_unbounded_params(fn)
            if not unbounded:
                continue
            for sub in ast.walk(fn):
                if not isinstance(sub, ast.Call):
                    continue
                callee = ast.unparse(sub.func).split(".")[-1]
                if callee not in imported:
                    continue
                for kw in sub.keywords:
                    if kw.arg not in _SIZE_KW:
                        continue
                    if not (isinstance(kw.value, ast.Name) and kw.value.id in unbounded):
                        continue
                    if not ignore_callee_clamp and _callee_clamps_param(
                        imported[callee], callee, kw.value.id
                    ):
                        continue  # 被调端已夹取 ⇒ 值不裸奔，非缺陷
                    hits.append(
                        f"{path.relative_to(API_ROOT.parent)}:{fn.lineno} {fn.name}() "
                        f"把无下界的 {kw.value.id} 传给 {callee}({kw.arg}=) "
                        f"（{imported[callee]} 内含 SQL LIMIT/OFFSET）"
                    )
    return sorted(set(hits))


def test_no_unbounded_param_reaches_sql_limit() -> None:
    """整族门禁：无下界的路由参数**不被夹取地**直达 SQL `LIMIT/OFFSET` ⇒ 红。"""
    hits = _find_sql_limit_violations()
    assert not hits, (
        "以下路由参数没有下界、被调端也没有 min()/max() 夹取，直接进 SQL LIMIT/OFFSET"
        "（`-1` 会 500）：\n  " + "\n  ".join(hits)
    )


def test_gate_detects_sql_limit_shape() -> None:
    """自检：SQL-LIMIT 判据必须能认出含 `LIMIT %s` 的函数（否则门禁失效）。"""
    funcs = _sql_limit_funcs()
    assert funcs, "未扫到任何含 SQL LIMIT/OFFSET 的函数 —— 判据本身失效"
    assert any("model_capacity.py" in k for k in funcs), (
        f"已知站点 model_capacity.py 未被识别：{sorted(funcs)[:5]}"
    )


def test_gate_flags_sql_limit_shape_when_clamp_ignored() -> None:
    """正对照：关掉夹取豁免后同一形状必须判红 ⇒ 证明「绿」是豁免给的，不是判据瞎了。"""
    hits = _find_sql_limit_violations(ignore_callee_clamp=True)
    assert any("wave_ext.py" in h and "list_schedule_runs" in h for h in hits), (
        f"关掉豁免后仍然扫不到已知形状（判据被改坏了）：{hits[:5]}"
    )
    assert not _find_sql_limit_violations(), "默认判据应当为绿"


@pytest.mark.parametrize(
    "rel,func,param,expected",
    [
        # 已夹取：list_runs 首行 safe_limit = max(1, min(int(limit), 100))
        ("aos_api/qyh_cron_scheduler.py", "list_runs", "limit", True),
        # 未夹取：list_usage 原样进 SQL（正是本轮修的那个站点）
        ("aos_api/model_capacity.py", "list_usage", "limit", False),
        # 函数不存在 ⇒ 保守判为「未夹取」
        ("aos_api/qyh_cron_scheduler.py", "no_such_func", "limit", False),
    ],
)
def test_callee_clamp_detector(rel: str, func: str, param: str, expected: bool) -> None:
    """夹取探测器自检（含 1 正例 / 2 反例）。"""
    assert _callee_clamps_param(rel, func, param) is expected


def test_capacity_usage_negative_limit_is_400() -> None:
    """修复前：`limit=-1` → PG `InvalidRowCountInLimitClause` → 500 INTERNAL。"""
    from aos_api.routers.model_capacity import router

    resp = _client(router).get("/v1/aip/capacity/usage", params={"limit": -1})
    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == "VALIDATION"


def test_capacity_usage_over_max_limit_is_400() -> None:
    """正对照：上界仍然生效（`le=365`）。"""
    from aos_api.routers.model_capacity import router

    resp = _client(router).get("/v1/aip/capacity/usage", params={"limit": 400})
    assert resp.status_code == 400, resp.text


# ───────── 第三批：负 limit 走**内存切片**（静默丢行，无任何错误码） ─────────

# 判据：路由参数无下界 且 被调函数体里有 `items[-<同名形参>:]` ⇒ 红。
# 为什么状态码探针（B/E/G/K）全部漏掉：`items[-1:]`… 其实是 `items[1:]`，
# 它**成功返回 200**，只是把最新/首条记录从结果里悄悄抹掉。唯一可观测的差异在
# **内容**（条数 / 首元素身份），状态码一律 200 ⇒ 必须用内容判据。
#
# 上游一条真实先例：`triggers_and_link_output.list_fires` 写的是
# `if limit > 0: items = items[:limit]` —— 即本仓已存在「非正数不切片」的约定。


def _neg_slice_params(fn: ast.AST) -> set[str]:
    """函数体里以 `[-<Name>:]` 形式切片的形参名集合。"""
    out: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Subscript) or not isinstance(node.slice, ast.Slice):
            continue
        lo = node.slice.lower
        if isinstance(lo, ast.UnaryOp) and isinstance(lo.op, ast.USub) and isinstance(lo.operand, ast.Name):
            out.add(lo.operand.id)
    return out


def _module_neg_slice_funcs() -> dict[str, dict[str, set[str]]]:
    """{模块相对路径: {函数名: 负切片形参名}}。"""
    out: dict[str, dict[str, set[str]]] = {}
    for path in API_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        rel = str(path.relative_to(API_ROOT.parent))
        per: dict[str, set[str]] = {}
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = {a.arg for a in list(fn.args.args) + list(fn.args.kwonlyargs)}
                hit = _neg_slice_params(fn) & params
                if hit:
                    per.setdefault(fn.name, set()).update(hit)
        if per:
            out[rel] = per
    return out


def _route_numeric_params(fn: ast.AST) -> dict[str, bool]:
    """路由中的数值型形参 -> 是否声明了下界（`ge`/`gt`）。"""
    defaults: dict[str, ast.expr] = {}
    if fn.args.defaults:
        for a, d in zip(list(fn.args.args)[-len(fn.args.defaults):], fn.args.defaults):
            defaults[a.arg] = d
    for a, d in zip(fn.args.kwonlyargs, fn.args.kw_defaults):
        if d is not None:
            defaults[a.arg] = d
    out: dict[str, bool] = {}
    for a in list(fn.args.args) + list(fn.args.kwonlyargs):
        ann = ast.unparse(a.annotation) if a.annotation else ""
        if ann.strip() not in ("int", "int | None", "float", "float | None"):
            continue
        d = defaults.get(a.arg)
        kws = {k.arg for k in d.keywords if k.arg} if isinstance(d, ast.Call) else set()
        out[a.arg] = bool(kws & _BOUNDED_KW)
    return out


def _find_neg_slice_violations(ignore_route_bound: bool = False) -> list[str]:
    """路由无下界的数值参数传给「负切片引擎函数」⇒ 命中。

    被调解析按**导入来源模块**（不是函数名全局匹配）：否则 `list_runs` 这类
    同名方法会把 `qyh_cron_scheduler.list_runs`（SQL 夹取）与
    `aip_extras.list_runs`（负切片）混为一谈 —— 首版就撞了这个坑。
    工厂间接 `get_x_engine().list_runs(limit=...)` 亦覆盖。
    """
    neg_funcs = _module_neg_slice_funcs()
    hits: list[str] = []
    for path in API_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        rel = str(path.relative_to(API_ROOT.parent))
        tgt: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("aos_api"):
                mod = str(Path(*node.module.split(".")).with_suffix(".py"))
                for al in node.names:
                    tgt[al.asname or al.name] = mod
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or not _is_route(fn):
                continue
            nump = _route_numeric_params(fn)
            if not nump:
                continue
            for call in ast.walk(fn):
                if not isinstance(call, ast.Call):
                    continue
                f = call.func
                if isinstance(f, ast.Name):
                    cname, root = f.id, f.id
                elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Call) and isinstance(f.value.func, ast.Name):
                    cname, root = f.attr, f.value.func.id  # get_x_engine().method(...)
                elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                    cname, root = f.attr, f.value.id
                else:
                    continue
                mod = tgt.get(root, rel)
                neg = neg_funcs.get(mod, {}).get(cname)
                if not neg:
                    continue
                for kw in call.keywords:
                    if kw.arg not in neg:
                        continue
                    if not isinstance(kw.value, ast.Name) or kw.value.id not in nump:
                        continue
                    if not ignore_route_bound and nump[kw.value.id]:
                        continue  # 路由已给下界（ge/gt）⇒ 负值不可达，非缺陷
                    hits.append(
                        f"{rel}:{fn.lineno} {fn.name}() 把{'无下界的' if not nump[kw.value.id] else ''}"
                        f"{kw.value.id} 传给 {mod}:{cname}({kw.arg}=) —— "
                        f"函数体内 `items[-{kw.arg}:]`，负值会静默丢行"
                    )
    return sorted(set(hits))


def test_no_unbounded_param_reaches_negative_slice() -> None:
    """整族门禁：无下界的路由参数直达内存负切片 ⇒ 红（全部站点已设 `ge=1`）。"""
    hits = _find_neg_slice_violations()
    assert not hits, "以下路由参数无下界且被负切片消费（`-1` 会 200 + 静默丢行）：\n  " + "\n  ".join(hits)


def test_gate_detects_negative_slice_family() -> None:
    """自检：判据必须能认出本族（否则门禁静默失效）。"""
    funcs = _module_neg_slice_funcs()
    assert funcs, "未扫到任何负切片函数 —— 判据失效"
    for rel, name in [
        ("aos_api/aip_extras.py", "list_runs"),
        ("aos_api/pipeline_type_semantics.py", "list_dlq"),
        ("aos_api/l4_automation.py", "list_alerts"),
    ]:
        assert name in funcs.get(rel, {}), f"{rel}:{name} 未被识别为负切片函数"


def test_gate_flags_neg_slice_when_route_bound_ignored() -> None:
    """正对照：把路由下界视作无效后，本族必须重新判红 ⇒ 证明「绿」来自下界而非判据瞎了。"""
    hits = _find_neg_slice_violations(ignore_route_bound=True)
    assert len(hits) >= 10, f"关掉下界豁免后命中不足（判据被改坏）：{len(hits)}\n" + "\n".join(hits)
    assert not _find_neg_slice_violations(), "默认判据应当为绿"


# ── 行为断言：三族代表端点 `limit=-1` 必须是 400，而不是 200 ──

_H_NEG_LIMIT_SITES = [
    ("aos_api.routers.aip_extras", "list_automate_runs", {}),
    ("aos_api.routers.aip_extras", "list_maturity_assessments", {}),
    ("aos_api.routers.l4_automation", "list_l4_alerts", {}),
    ("aos_api.routers.l4_automation", "list_warmup_probe_results", {}),
    ("aos_api.routers.llm_extras", "list_audit_records", {}),
    ("aos_api.routers.llm_routing", "list_call_records", {}),
    ("aos_api.routers.pipeline_type_semantics", "list_changes", {"pipeline_id": "p-1"}),
    ("aos_api.routers.pipeline_type_semantics", "list_windows", {"pipeline_id": "p-1"}),
    ("aos_api.routers.pipeline_type_semantics", "list_events", {"pipeline_id": "p-1"}),
    ("aos_api.routers.pipeline_type_semantics", "list_dlq", {"pipeline_id": "p-1"}),
]


def _url_for(router, func_name: str, fill: dict[str, str]) -> str:
    import re as _re

    for r in router.routes:
        if getattr(r, "name", None) == func_name:
            path = r.path
            for k, v in fill.items():
                path = _re.sub(r"\{" + k + r"(?::[^}]*)?\}", v, path)
            assert "{" not in path, f"{func_name} 仍有未填路径参数：{path}"
            return path
    raise AssertionError(f"路由器里找不到 {func_name}")


@pytest.mark.parametrize("module,name,fill", _H_NEG_LIMIT_SITES, ids=[s[1] for s in _H_NEG_LIMIT_SITES])
def test_negative_limit_is_400_not_silent_200(module: str, name: str, fill: dict) -> None:
    """`limit=-1` 必须被请求校验拦成 400；修复前是 200 + 静默丢首行。"""
    import importlib

    router = importlib.import_module(module).router
    url = _url_for(router, name, fill)
    resp = _client(router).get(url, params={"limit": -1})
    assert resp.status_code == 400, f"{url} limit=-1 得到 {resp.status_code} {resp.text[:160]}"
    assert resp.json()["code"] == "VALIDATION"


@pytest.mark.parametrize("module,name,fill", _H_NEG_LIMIT_SITES, ids=[s[1] for s in _H_NEG_LIMIT_SITES])
def test_limit_one_passes_validation(module: str, name: str, fill: dict) -> None:
    """正对照：`limit=1` 必须不被误拦（下界设为 1，不是把参数整个作废）。"""
    import importlib

    router = importlib.import_module(module).router
    url = _url_for(router, name, fill)
    resp = _client(router).get(url, params={"limit": 1})
    assert resp.status_code != 400, f"{url} limit=1 被误拦 {resp.status_code}"

