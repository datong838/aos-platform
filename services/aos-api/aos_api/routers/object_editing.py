"""W2-N · Object 编辑增强路由：冲突解决 + 模式迁移 + 编辑历史追踪."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.object_editing import (
    ChangeLogError,
    EditConflict,
    MigrationError,
    ObjectChangeLog,
    get_changelog_engine,
    get_conflict_engine,
    get_migration_engine,
)

router = APIRouter(tags=["object-editing"])
log = get_logger("aos-api.object-editing")


def _map_conflict_error(err: Exception, status: int = 400) -> ApiError:
    code = getattr(err, "code", "INTERNAL")
    msg = getattr(err, "message", str(err))
    if code == "NOT_FOUND":
        status = 404
    elif code == "ALREADY_RESOLVED":
        status = 409
    return ApiError(code=code, message=msg, status_code=status)


def _map_migration_error(err: MigrationError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    elif err.code == "ALREADY_RUNNING":
        status = 409
    return ApiError(code=err.code, message=err.message, status_code=status)


# ─────────────── #42 冲突解决 ───────────────

class DetectConflictRequest(BaseModel):
    object_type: str = Field(min_length=1)
    object_id: str = Field(min_length=1)
    field: str = Field(min_length=1)
    edit_a: dict[str, Any] = Field(default_factory=dict)
    edit_b: dict[str, Any] = Field(default_factory=dict)


class ResolveConflictRequest(BaseModel):
    strategy: str = "timestamp_priority"


class UserPriorityRequest(BaseModel):
    user: str
    priority: int


@router.post("/v1/ontology/object-conflicts/detect")
def detect_conflict(
    body: DetectConflictRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#42 · 检测编辑冲突。"""
    _ = principal
    conflict = get_conflict_engine().detect(
        body.object_type, body.object_id, body.field,
        body.edit_a, body.edit_b,
    )
    log.info("conflict_detected id=%s ot=%s field=%s", conflict.id, body.object_type, body.field)
    return conflict.model_dump()


@router.post("/v1/ontology/object-conflicts/{conflict_id}/resolve")
def resolve_conflict(
    conflict_id: str,
    body: ResolveConflictRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#42 · 解决冲突。"""
    _ = principal
    try:
        conflict = get_conflict_engine().resolve(conflict_id, body.strategy)
        log.info("conflict_resolved id=%s strategy=%s winner=%s",
                 conflict_id, body.strategy, conflict.resolution.get("winner"))
        return conflict.model_dump()
    except Exception as err:
        raise _map_conflict_error(err) from err


@router.get("/v1/ontology/object-conflicts")
def list_conflicts(
    object_type: str | None = None,
    object_id: str | None = None,
    resolved: bool | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#42 · 列出冲突。"""
    _ = principal
    items = get_conflict_engine().list(
        object_type=object_type, object_id=object_id, resolved=resolved,
    )
    return {"items": [c.model_dump() for c in items], "count": len(items)}


@router.get("/v1/ontology/object-conflicts/{conflict_id}")
def get_conflict(
    conflict_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#42 · 获取冲突详情。"""
    _ = principal
    try:
        return get_conflict_engine().get(conflict_id).model_dump()
    except Exception as err:
        raise _map_conflict_error(err) from err


@router.post("/v1/ontology/object-conflicts/user-priorities")
def set_user_priority(
    body: UserPriorityRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#42 · 设置用户优先级。"""
    _ = principal
    get_conflict_engine().set_user_priority(body.user, body.priority)
    return {"set": True, "user": body.user, "priority": body.priority}


# ─────────────── #44 模式迁移 ───────────────

class RegisterSchemaRequest(BaseModel):
    object_type: str = Field(min_length=1)
    properties: list[dict[str, Any]] = Field(default_factory=list)


class CreateBatchRequest(BaseModel):
    object_type: str = Field(min_length=1)
    commands: list[dict[str, Any]] = Field(default_factory=list)
    dry_run: bool = False


@router.post("/v1/ontology/object-migrations/schemas")
def register_migration_schema(
    body: RegisterSchemaRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#44 · 注册对象 schema（供迁移用）。"""
    _ = principal
    get_migration_engine().register_schema(body.object_type, body.properties)
    return {"registered": True, "object_type": body.object_type, "properties": len(body.properties)}


@router.get("/v1/ontology/object-migrations/schemas/{object_type}")
def get_migration_schema(
    object_type: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#44 · 获取当前 schema。"""
    _ = principal
    props = get_migration_engine().get_schema(object_type)
    return {"object_type": object_type, "properties": props}


@router.post("/v1/ontology/object-migrations/batches")
def create_migration_batch(
    body: CreateBatchRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#44 · 创建迁移批次。"""
    _ = principal
    try:
        batch = get_migration_engine().create_batch(
            body.object_type, body.commands, dry_run=body.dry_run,
        )
        log.info("migration_batch_created id=%s ot=%s commands=%s dry_run=%s",
                 batch.id, body.object_type, batch.total, body.dry_run)
        return batch.model_dump()
    except MigrationError as err:
        raise _map_migration_error(err) from err


@router.post("/v1/ontology/object-migrations/batches/{batch_id}/execute")
def execute_migration_batch(
    batch_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#44 · 执行迁移批次。"""
    _ = principal
    try:
        batch = get_migration_engine().execute_batch(batch_id)
        log.info("migration_batch_executed id=%s status=%s processed=%s failed=%s",
                 batch_id, batch.status, batch.processed, batch.failed)
        return batch.model_dump()
    except MigrationError as err:
        raise _map_migration_error(err) from err


@router.get("/v1/ontology/object-migrations/batches")
def list_migration_batches(
    object_type: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#44 · 列出迁移批次。"""
    _ = principal
    batches = get_migration_engine().list_batches(object_type=object_type)
    return {"items": [b.model_dump() for b in batches], "count": len(batches)}


@router.get("/v1/ontology/object-migrations/batches/{batch_id}")
def get_migration_batch(
    batch_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#44 · 获取迁移批次详情。"""
    _ = principal
    try:
        return get_migration_engine().get_batch(batch_id).model_dump()
    except MigrationError as err:
        raise _map_migration_error(err) from err


# ─────────────── #45 编辑历史追踪 ───────────────

class ChangeLogIn(BaseModel):
    object_type: str = Field(min_length=1)
    object_id: str = Field(min_length=1)
    field: str = Field(min_length=1)
    old_value: Any = None
    new_value: Any = None
    author: str = ""
    operation: str = "update"


@router.post("/v1/ontology/object-changelogs/enable/{object_type}")
def enable_changelog(
    object_type: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#45 · 启用 OT 变更追踪。"""
    _ = principal
    get_changelog_engine().enable(object_type)
    return {"enabled": True, "object_type": object_type}


@router.post("/v1/ontology/object-changelogs/disable/{object_type}")
def disable_changelog(
    object_type: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#45 · 禁用 OT 变更追踪。"""
    _ = principal
    get_changelog_engine().disable(object_type)
    return {"enabled": False, "object_type": object_type}


@router.post("/v1/ontology/object-changelogs")
def record_changelog(
    body: ChangeLogIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#45 · 记录变更。"""
    _ = principal
    log_entry = ObjectChangeLog(**body.model_dump())
    result = get_changelog_engine().record(log_entry)
    if result is None:
        return {"recorded": False, "reason": "changelog_disabled"}
    return result.model_dump()


@router.get("/v1/ontology/object-changelogs")
def query_changelogs(
    object_type: str | None = None,
    object_id: str | None = None,
    field: str | None = None,
    author: str | None = None,
    operation: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 100,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#45 · 查询变更历史。"""
    _ = principal
    logs = get_changelog_engine().query(
        object_type=object_type, object_id=object_id, field=field,
        author=author, operation=operation, since=since, until=until, limit=limit,
    )
    return {"items": [l.model_dump() for l in logs], "count": len(logs)}


@router.get("/v1/ontology/object-changelogs/timeline/{object_type}/{object_id}")
def get_timeline(
    object_type: str,
    object_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#45 · 获取对象变更时间线。"""
    _ = principal
    logs = get_changelog_engine().get_timeline(object_type, object_id)
    return {"object_type": object_type, "object_id": object_id, "timeline": [l.model_dump() for l in logs]}
