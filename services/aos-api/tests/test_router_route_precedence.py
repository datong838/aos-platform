"""路由声明顺序契约测试 —— **字面段 GET 不得被同方法 `{param}` 兄弟路由遮蔽**。

存在理由（09-24 全量端点扫掠结论）：
FastAPI/Starlette 按 `APIRouter.routes` 的**声明顺序**做首个匹配即返回。
若 `GET /x/{id}` 声明在 `GET /x/literal` 之前，后者**永远不可达**——且失败形态分两种：

1. **响亮失败**：`literal` 被当作 `id` 查询 → 404，错误报文还把 literal 回显成 id
   （如 {"message": "逻辑流 executions 不存在"}），极易被误诊为「资源不存在」。
2. **静默错数据**（更危险）：命中同形的兄弟 handler → 返回 200 + 空列表，
   调用方拿到「成功但空」的结果（实测 `/lineage/columns/search?keyword=abc` → `200 []`）。

本文件三条锁：
- `test_no_literal_route_is_shadowed_by_template_sibling`：AST 全量扫描，锁住整族（新增也会红）。
- `test_shadowed_routes_are_declared_before_templates`：11 个已修路由的顺序断言（防回退）。
- 三条 TestClient 行为断言：证明字面段真实命中**自己的** handler，而不是兄弟 handler。
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

from aos_api.auth import Principal, require_principal

API_ROOT = Path(__file__).resolve().parents[1] / "aos_api"

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def _template_to_regex(template: str) -> re.Pattern[str]:
    """把 FastAPI 路径模板转成匹配正则；`{x}` 只匹配单个路径段。"""
    parts = re.split(r"\{[^}]*\}", template)
    return re.compile("^" + "[^/]+".join(re.escape(p) for p in parts) + "$")


def _collect_routes(source: str) -> list[tuple[int, str, str, str]]:
    """按声明顺序收集 (lineno, path, method, func_name)（仅字面量路径装饰器）。"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # 带 BOM / 非标准编码的存量文件不参与扫描（与生产加载路径无关）
    routes: list[tuple[int, str, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                continue
            if dec.func.attr not in _HTTP_METHODS or not dec.args:
                continue
            arg = dec.args[0]
            if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
                continue
            routes.append((node.lineno, arg.value, dec.func.attr.upper(), node.name))
    routes.sort()
    return routes


def _find_shadowed(routes: list[tuple[int, str, str, str]]):
    """返回被更早声明的同方法模板路由遮蔽的字面段路由。"""
    hits = []
    for idx, (lineno, path, method, name) in enumerate(routes):
        if "{" in path:
            continue
        for prev_lineno, prev_path, prev_method, prev_name in routes[:idx]:
            if "{" not in prev_path or prev_method != method:
                continue
            if _template_to_regex(prev_path).match(path):
                hits.append(
                    (path, method, prev_path, name, prev_name, lineno, prev_lineno)
                )
                break
    return hits


def test_no_literal_route_is_shadowed_by_template_sibling():
    """全量 AST 扫描：任何模块内均不得存在「字面段路由被同方法模板路由遮蔽」。"""
    offenders = []
    scanned = 0
    for dirpath, _dirnames, filenames in os.walk(API_ROOT):
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            file_path = os.path.join(dirpath, filename)
            try:
                source = open(file_path, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            scanned += 1
            for hit in _find_shadowed(_collect_routes(source)):
                rel = os.path.relpath(file_path, API_ROOT.parent)
                offenders.append(f"{rel}:{hit[5]} {hit[1]} {hit[0]}  <- {hit[2]}")
    assert scanned > 100, "扫描面过小，说明扫描根目录写错了"
    assert offenders == [], "字面段路由被模板路由遮蔽（永远不可达）：\n" + "\n".join(offenders)


# (模块, 方法, 字面段路径, 遮蔽它的模板路径)
_FIXED_SHADOW_SITES = [
    ("routers/data_connection_security.py", "GET", "/v1/egress-policies/check-allowed", "/v1/egress-policies/{policy_id}"),
    ("routers/data_connection_security.py", "GET", "/v1/egress-policies/evaluations", "/v1/egress-policies/{policy_id}"),
    ("routers/data_connection_security.py", "GET", "/v1/exportable-markings/can-export", "/v1/exportable-markings/{policy_id}"),
    ("routers/data_connection_security.py", "GET", "/v1/exportable-markings/evaluations", "/v1/exportable-markings/{policy_id}"),
    ("routers/ontology_management.py", "GET", "/v1/ontology/edit-history/timeline", "/v1/ontology/edit-history/{event_id}"),
    ("routers/materialized_access_control.py", "GET", "/agent-tools/types", "/agent-tools/{tool_id}"),
    ("routers/action_further.py", "GET", "/v1/actions/notification-effects/dispatches", "/v1/actions/notification-effects/{effect_id}"),
    ("routers/logic_flows.py", "GET", "/v1/logic-flows/executions", "/v1/logic-flows/{flow_id}"),
    ("routers/logic_flows.py", "GET", "/v1/agent-workers/jobs", "/v1/agent-workers/{worker_id}"),
    ("routers/lineage_visualization.py", "GET", "/columns/search", "/columns/{dataset_rid}"),
    ("routers/lineage_visualization.py", "GET", "/columns/trace", "/columns/{dataset_rid}"),
]


@pytest.mark.parametrize("rel_path,method,literal,template", _FIXED_SHADOW_SITES)
def test_shadowed_routes_are_declared_before_templates(rel_path, method, literal, template):
    """11 个已修路由：字面段必须声明在模板之前（按声明顺序真实取值）。"""
    source = (API_ROOT / rel_path).read_text(encoding="utf-8")
    routes = _collect_routes(source)
    order = {(path, m): lineno for lineno, path, m, _name in routes}
    assert (literal, method) in order, f"{literal} 未在该模块声明"
    assert (template, method) in order, f"{template} 未在该模块声明"
    assert order[(literal, method)] < order[(template, method)], (
        f"{literal} 声明晚于 {template}，会被遮蔽"
    )


# ─────────────── 行为断言：字面段必须命中自己的 handler ───────────────

def _light_client(router, allowed: bool = True):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from aos_api.errors import register_exception_handlers

    app = FastAPI()
    if allowed:
        app.include_router(router)
    register_exception_handlers(app)
    return app, TestClient(app)


def _principal() -> Principal:
    return Principal(
        subject="route-precedence-test",
        org_id="org-org",
        project_id="dev-project",
        roles=["developer", "admin"],
        markings=["public"],
        token_kind="test",
    )


def test_lineage_columns_search_hits_search_handler_not_list_columns(monkeypatch):
    """`/lineage/columns/search` 必须调用 search_columns；曾被 list_columns 吞掉返回 200 []。"""
    from aos_api.routers import lineage_visualization as lv

    calls: list[tuple[str, tuple]] = []

    class _FakeEngine:
        def search_columns(self, keyword, data_type, tag):
            calls.append(("search_columns", (keyword, data_type, tag)))
            return []

        def list_columns(self, dataset_rid):
            calls.append(("list_columns", (dataset_rid,)))
            return []

        def trace_column(self, dataset_rid, column_name, direction, max_depth):
            calls.append(("trace_column", (dataset_rid, column_name, direction, max_depth)))
            return {
                "column": column_name,
                "dataset_rid": dataset_rid,
                "direction": direction,
                "depth": 0,
                "path": [],
            }

    monkeypatch.setattr(lv, "get_column_lineage_search_engine", lambda: _FakeEngine())

    app, client = _light_client(lv.router)
    app.dependency_overrides[require_principal] = _principal
    with client:
        resp = client.get("/lineage/columns/search", params={"keyword": "abc"})
        assert resp.status_code == 200, resp.text
        resp_trace = client.get(
            "/lineage/columns/trace",
            params={"dataset_rid": "ds-1", "column_name": "c1"},
        )
        assert resp_trace.status_code == 200, resp_trace.text

    assert [c[0] for c in calls] == ["search_columns", "trace_column"], calls
    assert calls[0][1][0] == "abc"


def test_egress_check_allowed_hits_its_own_handler(monkeypatch):
    """`/v1/egress-policies/check-allowed` 曾被 `{policy_id}` 吞掉返回 404。"""
    from aos_api.routers import data_connection_security as dcs

    calls: list[tuple[str, tuple]] = []

    class _FakeEngine:
        def check_allowed(self, destination, port, protocol):
            calls.append(("check_allowed", (destination, port, protocol)))
            return True

        def get(self, policy_id):
            calls.append(("get", (policy_id,)))
            raise AssertionError("不应命中 {policy_id} handler")

    monkeypatch.setattr(dcs, "get_egress_policy_engine", lambda: _FakeEngine())

    app, client = _light_client(dcs.router)
    app.dependency_overrides[require_principal] = _principal
    with client:
        resp = client.get(
            "/v1/egress-policies/check-allowed",
            params={"destination": "api.example.com", "port": 443, "protocol": "https"},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"allowed": True}
    assert calls and calls[0][0] == "check_allowed"


def test_agent_workers_jobs_hits_list_jobs_not_get_worker(monkeypatch):
    """`/v1/agent-workers/jobs` 曾被 `{worker_id}` 吞掉返回 404「Worker jobs 不存在」。"""
    from aos_api.routers import logic_flows as lf

    calls: list[tuple[str, tuple]] = []

    class _FakeWorkerEngine:
        def list_jobs(self, worker_id=None, status=None):
            calls.append(("list_jobs", (worker_id, status)))
            return []

        def get(self, worker_id):
            calls.append(("get", (worker_id,)))
            raise AssertionError("不应命中 {worker_id} handler")

    monkeypatch.setattr(lf, "get_worker_engine", lambda: _FakeWorkerEngine())

    app, client = _light_client(lf.router)
    app.dependency_overrides[require_principal] = _principal
    with client:
        resp = client.get("/v1/agent-workers/jobs")
    assert resp.status_code == 200, resp.text
    assert calls and calls[0][0] == "list_jobs"


# ════════ app 级（扁平静态路由表）门禁 —— 补 AST 版的两处盲区 ════════
#
# AST 版 `_find_shadowed` 有两个盲区，只有按「app 扁平路由表的真实声明顺序」才能覆盖：
#   1. `if "{" in path: continue` —— 跳过**自身含参数**的受害路由。
#      于是 `/columns/index/{dataset_rid}`（字面段在第 3 段）被
#      `/columns/{dataset_rid}/{column_name}` 吞掉，AST 版永远看不见。
#   2. 只扫模块内声明顺序；`main.py` 按 domain 追加 include，
#      **跨模块**（如 `runtime_write` 早于 `phase3_aip_lineage`）的遮蔽不可见。
#
# venv fastapi 0.141.1 把 `include_router` 变成惰性的 `fastapi.routing._IncludedRouter`，
# 需递归 `effective_candidates()` 才能拿到真实扁平表；`_match()` 仍是「声明顺序首个命中」。

_HTTP_METHODS_UPPER = {m.upper() for m in _HTTP_METHODS}

# 同形（同段数、同 `{}` 结构）仅参数名不同的重复注册。这些是**既有**的 legacy 模块
# （`phase4_*` / `phase5_*` / `runtime_write`）与后加扩展层（`wave_ext` / `ontology`）的
# 路径重合：契约快照已记录（`v1.inventory.json` 的 `duplicatePairs`），后声明者结构性死亡，
# 线上行为由先声明者提供。冻结在此 —— **新增**任一重复注册都会让本测试变红。
_APP_SHADOW_EXEMPT_SAME_SHAPE = {
    ("GET", "/v1/ontology/object-types/{ot_id}", "/v1/ontology/object-types/{type_id}"),
    ("PUT", "/v1/ontology/object-types/{ot_id}", "/v1/ontology/object-types/{type_id}"),
    ("GET", "/v1/aip/lineage/{record_id}", "/v1/aip/lineage/{lineage_id}"),
    ("GET", "/v1/schedules/{sc_id}", "/v1/schedules/{schedule_id}"),
    ("GET", "/v1/schedules/{sc_id}/runs", "/v1/schedules/{schedule_id}/runs"),
    ("POST", "/v1/schedules/{sc_id}/run", "/v1/schedules/{schedule_id}/run"),
    ("GET", "/v1/datasets/{ds_id}", "/v1/datasets/{rid}"),
}


def _app_flat_routes() -> list[tuple[str, str, str]]:
    """按 app 真实声明顺序展开 (path, method, qualname)。"""
    from fastapi.routing import _IncludedRouter

    from aos_api.main import create_app

    flat: list[tuple[str, str, str]] = []

    def walk(candidates) -> None:
        for candidate in candidates:
            if isinstance(candidate, _IncludedRouter):
                walk(candidate.effective_candidates())
                continue
            endpoint = getattr(candidate, "endpoint", None)
            qual = "?"
            if endpoint is not None:
                qual = (
                    f"{getattr(endpoint, '__module__', '?')}."
                    f"{getattr(endpoint, '__qualname__', getattr(endpoint, '__name__', '?'))}"
                )
            for method in getattr(candidate, "methods", set()) or set():
                if method in _HTTP_METHODS_UPPER:
                    flat.append((candidate.path, method, qual))

    walk(create_app().router.routes)
    return flat


def _concrete(template: str) -> str:
    counter = [0]

    def _sub(_match: re.Match[str]) -> str:
        counter[0] += 1
        return f"zzz{counter[0]}"

    return re.sub(r"\{[^}]*\}", _sub, template)


def _same_shape(template: str) -> str:
    return re.sub(r"\{[^}]*\}", "{}", template)


def _find_captures(flat: list[tuple[str, str, str]]) -> list[tuple[str, str, str, str]]:
    """返回 (method, prev_path, prev_qual, victim_path)：受害路由被更早同方法路由吞掉。"""
    by_method: dict[str, list[tuple[int, str, str]]] = {}
    for order, (path, method, qual) in enumerate(flat):
        by_method.setdefault(method, []).append((order, path, qual))

    captures: list[tuple[str, str, str, str]] = []
    for method, entries in sorted(by_method.items()):
        for idx, (_o_victim, victim, _v_qual) in enumerate(entries):
            probe = _concrete(victim)
            for _o_prev, prev, prev_qual in entries[:idx]:
                if prev == victim:
                    break  # 精确重复：首个匹配即自身，另见契约快照 duplicatePairs
                if _template_to_regex(prev).match(probe):
                    captures.append((method, prev, prev_qual, victim))
                    break
    return captures


def test_no_route_is_captured_at_app_level():
    """app 扁平表中任何路由都不得被更早声明的同方法路由吞掉（含**自身带参数**的受害路由）。

    AST 版门禁只覆盖「全字面段受害者 + 模块内顺序」；本测试是它的严格超集。
    """
    flat = _app_flat_routes()
    assert len(flat) > 3000, f"路由表过小（{len(flat)}），app 未真正展开"

    offenders = [
        f"{method:6} {victim:50} <- {prev}  (winner={prev_qual})"
        for method, prev, prev_qual, victim in _find_captures(flat)
        if _same_shape(prev) != _same_shape(victim)
    ]

    assert offenders == [], (
        "路由被更早声明的同方法路由吞掉（结构性不可达）：\n" + "\n".join(offenders)
    )


def test_same_shape_duplicate_registrations_are_frozen():
    """同形不同参数名的重复注册清单必须与冻结值精确一致（新增即红）。"""
    found = {
        (method, victim, prev)
        for method, prev, _pq, victim in _find_captures(_app_flat_routes())
        if _same_shape(prev) == _same_shape(victim)
    }
    assert found == _APP_SHADOW_EXEMPT_SAME_SHAPE, (
        "同形重复注册清单漂移；新增重复会让后声明者永久不可达：\n"
        f"  新增={sorted(found - _APP_SHADOW_EXEMPT_SAME_SHAPE)}\n"
        f"  消失={sorted(_APP_SHADOW_EXEMPT_SAME_SHAPE - found)}"
    )


def test_columns_index_rebuild_declared_before_register_column():
    """`POST /columns/index/{dataset_rid}` 必须早于 `POST /columns/{dataset_rid}/{column_name}`。

    否则 `index` 被当成 dataset_rid，落到**写入型** `register_column`，
    在列索引里静默登记 `dataset_rid="index"` 的假列并返回 200。
    """
    source = (API_ROOT / "routers/lineage_visualization.py").read_text(encoding="utf-8")
    routes = _collect_routes(source)
    order = {(path, m): lineno for lineno, path, m, _name in routes}
    literal = ("/columns/index/{dataset_rid}", "POST")
    template = ("/columns/{dataset_rid}/{column_name}", "POST")
    assert literal in order, "字面段路由未声明"
    assert template in order, "模板路由未声明"
    assert order[literal] < order[template], (
        f"{literal[0]} 声明晚于 {template[0]}，会被吞掉"
    )


def test_columns_index_rebuild_hits_build_index_not_register_column(monkeypatch):
    """行为锁：`POST /columns/index/<rid>` 必须调用 build_index，而非 register_column。"""
    from aos_api.routers import lineage_visualization as lv

    calls: list[tuple[str, tuple]] = []

    class _FakeEngine:
        def build_index(self, dataset_rid):
            calls.append(("build_index", (dataset_rid,)))
            return 3

        def register_column(self, *args):
            calls.append(("register_column", args))
            raise AssertionError("不应命中 register_column（写入型 handler）")

    monkeypatch.setattr(lv, "get_column_lineage_search_engine", lambda: _FakeEngine())

    app, client = _light_client(lv.router)
    app.dependency_overrides[require_principal] = _principal
    with client:
        resp = client.post("/lineage/columns/index/ri.aos.main.dataset.P01-shop-qyh")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "dataset_rid": "ri.aos.main.dataset.P01-shop-qyh",
        "indexed_columns": 3,
    }
    assert [c[0] for c in calls] == ["build_index"], calls
