"""not-found 错误码 → HTTP 状态码的映射契约测试（含全族门禁）。

背景（09-24 探针 G：1679 个 GET 全量扫掠，必填 query 参数已填齐）：
线上实测「含 NOT_FOUND 的错误码」状态码分布为 **404 × 537 / 400 × 7**。
⇒ 平台的既有约定是「资源不存在 ⇒ 404」，那 7 处 400 是**映射缺陷**，不是约定差异。

7 处里有 6 处来自两个映射器把状态码**硬编码成 400**：
- `routers/web_ide.py::_map_error` —— `IdeError` 发 `SESSION_NOT_FOUND` / `FILE_NOT_FOUND`
  ⇒ 5 个端点把「资源不存在」当请求错误返回；
- `routers/gantt.py::_map_error` —— `GanttError` 发**裸** `NOT_FOUND`（还有 `INVALID_HORIZON`）
  ⇒ 1 个端点同上。
（第 7 处 `media-set-browser-interaction/items` 已在同日的前一批修复中处理。）

本文件三条锁：
- 共享判据 `is_not_found_code` 的边界（含**裸码**与**后缀码**两种形态，且不接受拼写错误）；
- 行为断言：不存在的资源必须得到 **404**，而不是 400；
- AST 门禁：路由层不得再出现「返回 `ApiError(..., status_code=400)` 字面量且不含
  not-found 分支」的映射器（防同族回退）。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from aos_api.auth import Principal, require_principal
from aos_api.errors import is_not_found_code

ROUTERS = Path(__file__).resolve().parents[1] / "aos_api" / "routers"


# ─────────────── 共享判据的边界 ───────────────

@pytest.mark.parametrize(
    "code",
    [
        "NOT_FOUND",                       # 裸码（gantt.GanttError）
        "MEDIA_SET_NOT_FOUND",
        "ITEM_NOT_FOUND",
        "VIEW_NOT_FOUND",
        "JOB_NOT_FOUND",
        "SESSION_NOT_FOUND",               # web_ide.IdeError
        "FILE_NOT_FOUND",
        "AIP_AGENT_REGISTRY_NOT_FOUND",
        "CONFIG_NOT_FOUND",
    ],
)
def test_predicate_accepts_not_found_codes(code: str) -> None:
    assert is_not_found_code(code) is True


@pytest.mark.parametrize(
    "code",
    [
        "INVALID_HORIZON",                 # gantt.GanttError 的另一码：仍是 400
        "FILE_EXISTS",
        "VALIDATION",
        "XNOT_FOUND",                      # 拼写错误不得误收
        "NOT_FOUNDX",
        "NOTFOUND",
        "",
    ],
)
def test_predicate_rejects_other_codes(code: str) -> None:
    assert is_not_found_code(code) is False


# ─────────────── 行为断言：不存在的资源 ⇒ 404 ───────────────

def _client(router):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from aos_api.errors import register_exception_handlers

    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="not-found-status-test",
        org_id="org-org",
        project_id="dev-project",
        roles=["developer", "admin"],
        markings=["public"],
        token_kind="test",
    )
    return TestClient(app, raise_server_exceptions=False)


def test_web_ide_missing_session_is_404() -> None:
    """修复前：400 SESSION_NOT_FOUND（状态码与错误码语义相斥）。"""
    from aos_api.routers.web_ide import router

    resp = _client(router).get("/v1/web-ide/sessions/zzz-missing-session")
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "SESSION_NOT_FOUND"


def test_web_ide_missing_file_is_404() -> None:
    from aos_api.routers.web_ide import router

    resp = _client(router).get("/v1/web-ide/sessions/zzz-missing-session/files")
    assert resp.status_code == 404, resp.text


def test_gantt_missing_schedule_is_404() -> None:
    """修复前：400 NOT_FOUND（裸码）。"""
    from aos_api.routers.gantt import router

    resp = _client(router).get("/v1/scheduling/schedules/zzz-missing-sched/gantt")
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "NOT_FOUND"


def test_gantt_invalid_horizon_stays_400() -> None:
    """正对照：非 not-found 的领域错误仍必须是 400（修复不得一刀切）。

    注意：不能走 HTTP 打这个端点做正对照 —— `build_for_schedule` 先校验**调度是否存在**，
    用一个不存在的 sched_id 只会得到 404 NOT_FOUND（这本身是对的）。
    故正对照直接在**映射器**层做，边界精确且不依赖真实数据。
    """
    from aos_api.gantt import GanttError
    from aos_api.routers.gantt import _map_error

    assert _map_error(GanttError("INVALID_HORIZON", "越界")).status_code == 400
    assert _map_error(GanttError("NOT_FOUND", "不存在")).status_code == 404


def test_web_ide_non_not_found_code_stays_400() -> None:
    """正对照：`FILE_EXISTS`（冲突语义，非 not-found）保持 400。"""
    from aos_api.routers.web_ide import _map_error
    from aos_api.web_ide import IdeError

    assert _map_error(IdeError("FILE_EXISTS", "已存在")).status_code == 400
    assert _map_error(IdeError("FILE_NOT_FOUND", "不存在")).status_code == 404


def test_all_router_modules_import() -> None:
    """11 个被统一改写的路由模块必须可导入（防机械改写引入语法/导入错误）。"""
    import importlib

    for name in [
        "action_rules", "action_visual_editor", "aip_nodes", "functions",
        "functions_runtime", "gantt", "logic", "media_set_browser_interaction",
        "multi_language", "object_explorer", "object_views", "tool_registry",
        "transforms", "web_ide",
    ]:
        importlib.import_module(f"aos_api.routers.{name}")


# ─────────────── AST 门禁：映射器不得硬编码 400 ───────────────

def _hardcoded_400_mappers() -> list[str]:
    """找出「转发领域码（`X.code`）却把状态码写死成 400、且不含 not-found 分支」的映射器。

    只覆盖**转发领域错误码**的映射器：像 `ecommerce_growth_dispatch._map_error`
    那样按 `isinstance` 分派、状态码与码一一硬绑的映射器不属于本族，不纳入。
    """
    hits: list[str] = []
    for path in ROUTERS.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except SyntaxError:
            continue
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef) or not fn.name.startswith("_map"):
                continue
            src = ast.unparse(fn)
            if "ApiError(" not in src or ".code" not in src:
                continue
            has_not_found_branch = (
                "is_not_found_code" in src
                or "_is_not_found" in src
                or "NOT_FOUND" in src
            )
            if has_not_found_branch:
                continue
            if "status_code=400" in src:
                hits.append(
                    f"{path.relative_to(ROUTERS.parent)}:{fn.lineno} {fn.name}()"
                )
    return sorted(hits)


def test_no_router_mapper_hardcodes_400() -> None:
    """整族门禁：映射器把状态码写死成 400 而不区分 not-found ⇒ 红。"""
    hits = _hardcoded_400_mappers()
    assert not hits, (
        "以下映射器把状态码硬编码为 400，not-found 会被降级成请求错误：\n  "
        + "\n  ".join(hits)
    )


def test_gate_detects_the_known_defect_shape() -> None:
    """自检：门禁必须能抓到已知缺陷形态（否则门禁本身失效）。"""
    tree = ast.parse(
        "from aos_api.errors import ApiError\n"
        "def _map_error(err):\n"
        "    return ApiError(code=err.code, message=err.message, status_code=400)\n"
    )
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    src = ast.unparse(fn)
    assert "ApiError(" in src and "status_code=400" in src
    assert not ("is_not_found_code" in src or "_is_not_found" in src or "NOT_FOUND" in src)
