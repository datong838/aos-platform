"""W2-AD · 开发者工具组路由：#104 调试器 + #105 单元测试 + #106 制品仓库."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.dev_tooling import (
    Artifact,
    DevToolingError,
    TestCase,
    get_artifact_engine,
    get_debugger_engine,
    get_unittest_engine,
)
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["dev-tooling"])
log = get_logger("aos-api.dev-tooling")


def _map_err(err: DevToolingError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ════════════════════ #104 Python Debugger ════════════════════

class CreateSessionIn(BaseModel):
    code: str = Field(min_length=1)
    breakpoints: list[int] = Field(default_factory=list)


@router.post("/v1/dev-tooling/debug-sessions")
def create_debug_session(
    body: CreateSessionIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#104 · 创建调试会话。"""
    _ = principal
    s = get_debugger_engine().create_session(body.code, body.breakpoints)
    return {"item": s.model_dump()}


@router.get("/v1/dev-tooling/debug-sessions")
def list_debug_sessions(
    state: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#104 · 调试会话列表。"""
    _ = principal
    items = get_debugger_engine().list_sessions(state=state)
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.get("/v1/dev-tooling/debug-sessions/{session_id}")
def get_debug_session(
    session_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#104 · 单条调试会话。"""
    _ = principal
    try:
        return {"item": get_debugger_engine().get_session(session_id).model_dump()}
    except DevToolingError as exc:
        raise _map_err(exc) from exc


@router.post("/v1/dev-tooling/debug-sessions/{session_id}/step")
def step_debug_session(
    session_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#104 · 单步执行。"""
    _ = principal
    try:
        step = get_debugger_engine().step(session_id)
    except DevToolingError as exc:
        raise _map_err(exc) from exc
    return {"item": step.model_dump()}


@router.post("/v1/dev-tooling/debug-sessions/{session_id}/run")
def run_debug_session(
    session_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#104 · 运行到完成。"""
    _ = principal
    try:
        s = get_debugger_engine().run_to_completion(session_id)
    except DevToolingError as exc:
        raise _map_err(exc) from exc
    return {"item": s.model_dump()}


@router.get("/v1/dev-tooling/debug-sessions/{session_id}/variables")
def get_session_variables(
    session_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#104 · 变量快照。"""
    _ = principal
    try:
        variables = get_debugger_engine().get_variables(session_id)
    except DevToolingError as exc:
        raise _map_err(exc) from exc
    return {"variables": variables}


@router.delete("/v1/dev-tooling/debug-sessions/{session_id}")
def delete_debug_session(
    session_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#104 · 删除调试会话。"""
    _ = principal
    ok = get_debugger_engine().delete_session(session_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"会话 {session_id} 不存在", status_code=404)
    return {"id": session_id, "deleted": True}


# ════════════════════ #105 Unit Test Runner ════════════════════

class TestCaseIn(BaseModel):
    name: str = Field(min_length=1)
    language: str = Field(min_length=1)
    code: str = Field(min_length=1)
    target_function: str = ""
    timeout_seconds: float = 30.0


class TestCaseUpdateIn(BaseModel):
    name: str | None = None
    code: str | None = None
    language: str | None = None
    target_function: str | None = None
    timeout_seconds: float | None = None


@router.post("/v1/dev-tooling/test-cases")
def register_test_case(
    body: TestCaseIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#105 · 注册测试用例。"""
    _ = principal
    try:
        c = get_unittest_engine().register(TestCase(**body.model_dump()))
    except DevToolingError as exc:
        raise _map_err(exc) from exc
    return {"item": c.model_dump()}


@router.get("/v1/dev-tooling/test-cases")
def list_test_cases(
    language: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#105 · 测试用例列表。"""
    _ = principal
    items = get_unittest_engine().list(language=language)
    return {"items": [c.model_dump() for c in items], "count": len(items)}


@router.get("/v1/dev-tooling/test-cases/{case_id}")
def get_test_case(
    case_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#105 · 单条测试用例。"""
    _ = principal
    try:
        return {"item": get_unittest_engine().get(case_id).model_dump()}
    except DevToolingError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/dev-tooling/test-cases/{case_id}")
def update_test_case(
    case_id: str, body: TestCaseUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#105 · 更新测试用例。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        c = get_unittest_engine().update(case_id, updates)
    except DevToolingError as exc:
        raise _map_err(exc) from exc
    return {"item": c.model_dump()}


@router.delete("/v1/dev-tooling/test-cases/{case_id}")
def delete_test_case(
    case_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#105 · 删除测试用例。"""
    _ = principal
    ok = get_unittest_engine().delete(case_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"用例 {case_id} 不存在", status_code=404)
    return {"id": case_id, "deleted": True}


@router.post("/v1/dev-tooling/test-cases/{case_id}/run")
def run_test_case(
    case_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#105 · 执行测试。"""
    _ = principal
    try:
        r = get_unittest_engine().run(case_id)
    except DevToolingError as exc:
        raise _map_err(exc) from exc
    return {"item": r.model_dump()}


@router.get("/v1/dev-tooling/test-results")
def list_test_results(
    case_id: str | None = None, limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#105 · 测试结果列表。"""
    _ = principal
    items = get_unittest_engine().list_results(case_id=case_id, limit=limit)
    return {"items": [r.model_dump() for r in items], "count": len(items)}


# ════════════════════ #106 Artifact Registry ════════════════════

class ArtifactIn(BaseModel):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    format: str = Field(min_length=1)
    registry_url: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    size_bytes: int = 0
    checksum: str = ""


class ArtifactUpdateIn(BaseModel):
    registry_url: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    dependencies: list[str] | None = None
    size_bytes: int | None = None
    checksum: str | None = None


@router.post("/v1/dev-tooling/artifacts")
def register_artifact(
    body: ArtifactIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#106 · 注册制品。"""
    _ = principal
    try:
        a = get_artifact_engine().register(Artifact(**body.model_dump()))
    except DevToolingError as exc:
        raise _map_err(exc) from exc
    return {"item": a.model_dump()}


@router.get("/v1/dev-tooling/artifacts")
def list_artifacts(
    format: str | None = None, name: str | None = None, tag: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#106 · 制品列表。"""
    _ = principal
    items = get_artifact_engine().list(format=format, name=name, tag=tag)
    return {"items": [a.model_dump() for a in items], "count": len(items)}


@router.get("/v1/dev-tooling/artifacts/{artifact_id}")
def get_artifact(
    artifact_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#106 · 单条制品。"""
    _ = principal
    try:
        return {"item": get_artifact_engine().get(artifact_id).model_dump()}
    except DevToolingError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/dev-tooling/artifacts/{artifact_id}")
def update_artifact(
    artifact_id: str, body: ArtifactUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#106 · 更新制品。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        a = get_artifact_engine().update(artifact_id, updates)
    except DevToolingError as exc:
        raise _map_err(exc) from exc
    return {"item": a.model_dump()}


@router.delete("/v1/dev-tooling/artifacts/{artifact_id}")
def delete_artifact(
    artifact_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#106 · 删除制品。"""
    _ = principal
    ok = get_artifact_engine().delete(artifact_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"制品 {artifact_id} 不存在", status_code=404)
    return {"id": artifact_id, "deleted": True}


@router.get("/v1/dev-tooling/artifacts/by-name/{name}/versions")
def list_artifact_versions(
    name: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#106 · 制品版本列表。"""
    _ = principal
    items = get_artifact_engine().list_versions(name)
    return {"items": [a.model_dump() for a in items], "count": len(items)}


@router.get("/v1/dev-tooling/artifacts/{artifact_id}/dependencies")
def list_artifact_dependencies(
    artifact_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#106 · 制品依赖列表。"""
    _ = principal
    try:
        deps = get_artifact_engine().list_dependencies(artifact_id)
    except DevToolingError as exc:
        raise _map_err(exc) from exc
    return {"items": [a.model_dump() for a in deps], "count": len(deps)}
