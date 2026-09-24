"""「GET 端点要求请求体」缺陷族门禁（app 级，判据取 FastAPI 真实推断结果）。

存在理由（09-24 全量 GET 面「线上 vs HEAD」对照的洞外收获）：
`GET /v1/exportable-markings/can-export` 的形参写成裸序列注解
`markings: list[str]`，FastAPI 把它归入 **requestBody**
（实测 fastapi 0.141.1：`dependant.body_params == [("markings", Body)]`），
于是任何正常查询串调用都返 `400 VALIDATION {"loc":["body"],"msg":"Field required"}`。

它是**契约可见**的：快照里该操作带 `requestBody.required=true`，
而全平台 4530 个操作里只有这 1 个 GET 声明了 requestBody。

为什么此前所有探针都没抓到：它被同前缀的 `{policy_id}` 模板路由**遮蔽**，
旧代码下表现为 404（「资源不存在」），看起来像正常的 not-found；
路由重排修复（`8ec20112`）让字面段真正命中**自己的** handler 之后，
这个 400 才浮出来。**修一个缺陷会暴露被它掩盖的缺陷** —— 故必须有族级门禁。

本文件两条锁：
- `test_no_get_route_requires_request_body`：遍历**真实 app** 的全部 GET 路由，
  断言 `dependant.body_params` 为空（ground truth，不做 AST 近似）。
- `test_gate_detects_get_body_shape`：正对照 —— 合成一个同样写法的 GET 路由，
  判据必须报红（防止门禁退化成恒绿）。
外加两条行为断言，锁住 `can-export` 已能从查询串调用。
"""
from __future__ import annotations

from typing import Iterator

import pytest


def _walk_routes(routes) -> Iterator[object]:
    """扁平化真实路由表。

    注：venv 的 fastapi 0.141.1 把 `include_router` 做成惰性包装
    （`fastapi.routing._IncludedRouter`），`app.routes` 里拿不到真实 APIRoute，
    必须走 `effective_candidates()` 递归展开。
    """
    for route in routes:
        effective = getattr(route, "effective_candidates", None)
        if callable(effective):
            yield from _walk_routes(effective())
            continue
        if hasattr(route, "path") and hasattr(route, "dependant"):
            yield route
            continue
        nested = getattr(route, "routes", None)
        if nested:
            yield from _walk_routes(nested)


def _get_routes_with_body() -> list[str]:
    from aos_api.main import create_app

    app = create_app()
    out = []
    for route in _walk_routes(app.router.routes):
        methods = getattr(route, "methods", set()) or set()
        if "GET" not in methods:
            continue
        body_params = getattr(route.dependant, "body_params", None) or []
        if body_params:
            names = ",".join(p.name for p in body_params)
            out.append(f"{route.path} (body={names})")
    return sorted(out)


def test_no_get_route_requires_request_body() -> None:
    offenders = _get_routes_with_body()
    assert not offenders, (
        "GET 端点不得要求请求体（HTTP 语义 + 浏览器/普通客户端无法发送）。"
        "修法：给序列形参加 `Query(...)`，参照 aip_memory_improvement.purpose。\n"
        + "\n".join(offenders)
    )


def test_gate_detects_get_body_shape() -> None:
    """正对照：同一判据必须能识别合成出来的坏形态。"""
    from fastapi import APIRouter, FastAPI

    router = APIRouter()

    @router.get("/bad-get-body")
    def bad_get_body(connection_id: str, markings: list[str]):  # noqa: ANN202
        return {"connection_id": connection_id, "markings": markings}

    app = FastAPI()
    app.include_router(router)
    flagged = [
        route.path
        for route in _walk_routes(app.router.routes)
        if "GET" in (getattr(route, "methods", set()) or set())
        and (getattr(route.dependant, "body_params", None) or [])
    ]
    assert flagged == ["/bad-get-body"]


def _can_export_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from aos_api.auth import Principal, require_principal
    from aos_api.errors import register_exception_handlers
    from aos_api.routers.data_connection_security import router

    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="get-body-family-test",
        org_id="org-org",
        project_id="dev-project",
        roles=["developer", "admin"],
        markings=["public"],
        token_kind="test",
    )
    return TestClient(app, raise_server_exceptions=False)


def test_can_export_marking_takes_query_params() -> None:
    """修复后：查询串调用必须可用（修复前为 400 body Field required）。"""
    resp = _can_export_client().get(
        "/v1/exportable-markings/can-export",
        params=[("connection_id", "conn-1"), ("markings", "public")],
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"can_export": True}


def test_can_export_marking_rejects_missing_query_markings() -> None:
    """请求体不再是该端点的取值来源；缺 `markings` 必须走校验错误而不是静默成功。"""
    resp = _can_export_client().get(
        "/v1/exportable-markings/can-export?connection_id=conn-1"
    )
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 200


@pytest.mark.parametrize("markings", [["public"], ["public", "pii"]])
def test_can_export_marking_query_list_repeats(markings: list[str]) -> None:
    resp = _can_export_client().get(
        "/v1/exportable-markings/can-export",
        params=[("connection_id", "conn-1"), *[("markings", m) for m in markings]],
    )
    assert resp.status_code == 200, resp.text
