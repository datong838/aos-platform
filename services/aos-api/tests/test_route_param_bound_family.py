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
"""
from __future__ import annotations

import ast
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
