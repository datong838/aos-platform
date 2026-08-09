"""W2-M · Object Explorer 增强路由：高级搜索 + 保存探索 + 批量导出."""
from __future__ import annotations

from typing import Any
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, ConfigDict, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.oe_enhancements import (
    ExportError,
    SearchError,
    get_export_engine,
    get_search_engine,
)
from aos_api.ontology_exploration_assets import (
    AnnotationAssetPayload,
    ExplorationAssetPayload,
    ObjectSetAssetPayload,
    append_asset,
    get_asset,
    list_assets,
    set_archived,
)
from aos_api.tenant_scope import TenantScope

router = APIRouter(tags=["oe-enhancements"])
log = get_logger("aos-api.oe-enhancements")


def _map_search_error(err: SearchError, status: int = 400) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_export_error(err: ExportError, status: int = 400) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=status)


# ─────────────── #48 高级搜索 ───────────────

class IndexRequest(BaseModel):
    object_type: str = Field(min_length=1)
    objects: list[dict[str, Any]] = Field(default_factory=list)


class AddLinkRequest(BaseModel):
    src_id: str
    dst_id: str
    dst_obj: dict[str, Any] = Field(default_factory=dict)


class SearchRequest(BaseModel):
    object_type: str = Field(min_length=1)
    expression: str = Field(min_length=1)
    limit: int = 100
    offset: int = 0


@router.post("/v1/ontology/object-explorer/index")
def index_objects(
    body: IndexRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#48 · 索引对象供搜索（测试/管理用）。"""
    _ = principal
    get_search_engine().index(body.object_type, body.objects)
    log.info("oe_indexed ot=%s count=%s", body.object_type, len(body.objects))
    return {"indexed": True, "object_type": body.object_type, "count": len(body.objects)}


@router.post("/v1/ontology/object-explorer/links")
def add_link(
    body: AddLinkRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#48 · 添加链接关系（供 LINKS 筛选用）。"""
    _ = principal
    get_search_engine().add_link(body.src_id, body.dst_id, body.dst_obj)
    return {"added": True, "src_id": body.src_id, "dst_id": body.dst_id}


@router.post("/v1/ontology/object-explorer/search")
def search_objects(
    body: SearchRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#48 · 高级搜索。"""
    _ = principal
    try:
        result = get_search_engine().search(
            body.object_type, body.expression,
            limit=body.limit, offset=body.offset,
        )
        log.info("oe_search ot=%s total=%s", body.object_type, result["total"])
        return result
    except SearchError as err:
        raise _map_search_error(err) from err


# ─────────────── #49 保存探索 ───────────────

class ExplorationIn(ExplorationAssetPayload):
    pass


class ExplorationUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    objectType: str | None = None
    viewMode: str | None = None
    visibility: str | None = None
    query: dict[str, Any] | None = None
    columns: list[dict[str, Any]] | None = None
    graph: dict[str, Any] | None = None


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _required_key(value: str | None) -> str:
    if not value or not value.strip():
        raise ApiError(code="IDEMPOTENCY_KEY_REQUIRED", message="Idempotency-Key is required", status_code=400)
    return value.strip()


def _expected_revision(if_match: str | None) -> int:
    if not if_match:
        raise ApiError(code="IF_MATCH_REQUIRED", message="If-Match is required", status_code=428)
    try:
        parts = if_match.strip('"').split(":")
        revision = int(parts[-2])
    except (ValueError, IndexError) as exc:
        raise ApiError(code="IF_MATCH_INVALID", message="If-Match is invalid", status_code=400) from exc
    if revision < 1:
        raise ApiError(code="IF_MATCH_INVALID", message="If-Match is invalid", status_code=400)
    return revision


def _asset_id(prefix: str, key: str, principal: Principal) -> str:
    stable = uuid5(
        NAMESPACE_URL,
        f"aos:{principal.org_id}:{principal.project_id}:{prefix}:{key}",
    )
    return f"{prefix}-{stable.hex}"


@router.get("/v1/ontology/explorations")
def list_explorations(
    object_type: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """List persisted explorations visible to the current Principal."""
    items = list_assets(_scope(principal), kind="exploration", actor=principal.subject)
    if object_type:
        items = [item for item in items if item["payload"]["objectType"] == object_type]
    return {"items": items, "count": len(items)}


@router.post("/v1/ontology/explorations")
def create_exploration(
    body: ExplorationIn,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    key = _required_key(idempotency_key)
    asset_id = _asset_id("exp", key, principal)
    result, etag = append_asset(
        _scope(principal), kind="exploration", asset_id=asset_id,
        payload=body.model_dump(mode="json"), expected_revision=0,
        idempotency_key=key, actor=principal.subject,
    )
    response.headers["ETag"] = etag
    log.info("exploration_created id=%s name=%s", asset_id, body.name)
    return result


@router.get("/v1/ontology/explorations/{exp_id}")
def get_exploration(
    exp_id: str,
    response: Response,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    found = get_asset(_scope(principal), kind="exploration", asset_id=exp_id, actor=principal.subject)
    if found is None:
        raise ApiError(code="EXPLORATION_NOT_FOUND", message="exploration not found", status_code=404)
    result, etag = found
    response.headers["ETag"] = etag
    return result


@router.put("/v1/ontology/explorations/{exp_id}")
def update_exploration(
    exp_id: str,
    body: ExplorationUpdateIn,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    current = get_asset(_scope(principal), kind="exploration", asset_id=exp_id, actor=principal.subject)
    if current is None:
        raise ApiError(code="EXPLORATION_NOT_FOUND", message="exploration not found", status_code=404)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    payload = {**current[0]["payload"], **updates}
    result, etag = append_asset(
        _scope(principal), kind="exploration", asset_id=exp_id, payload=payload,
        expected_revision=_expected_revision(if_match), idempotency_key=_required_key(idempotency_key),
        actor=principal.subject,
    )
    response.headers["ETag"] = etag
    return result


@router.delete("/v1/ontology/explorations/{exp_id}")
def delete_exploration(
    exp_id: str,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    result, etag = set_archived(
        _scope(principal), kind="exploration", asset_id=exp_id, archived=True,
        expected_revision=_expected_revision(if_match), idempotency_key=_required_key(idempotency_key),
        actor=principal.subject,
    )
    response.headers["ETag"] = etag
    return result


@router.post("/v1/ontology/explorations/{exp_id}/restore")
def restore_exploration(
    exp_id: str,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    result, etag = set_archived(
        _scope(principal), kind="exploration", asset_id=exp_id, archived=False,
        expected_revision=_expected_revision(if_match), idempotency_key=_required_key(idempotency_key),
        actor=principal.subject,
    )
    response.headers["ETag"] = etag
    return result


@router.post("/v1/ontology/explorations/{exp_id}/execute")
def execute_exploration(
    exp_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """Execution moves to the authoritative query service in O1-UX3."""
    if get_asset(_scope(principal), kind="exploration", asset_id=exp_id, actor=principal.subject) is None:
        raise ApiError(code="EXPLORATION_NOT_FOUND", message="exploration not found", status_code=404)
    raise ApiError(
        code="GRAPH_AUTHORITY_UNAVAILABLE",
        message="saved exploration execution requires the O1-UX3 authoritative graph/query service",
        status_code=409,
    )


class ObjectSetIn(ObjectSetAssetPayload):
    pass


class AnnotationIn(AnnotationAssetPayload):
    pass


def _create_related_asset(
    *,
    kind: str,
    prefix: str,
    body: BaseModel,
    response: Response,
    idempotency_key: str | None,
    principal: Principal,
) -> dict[str, Any]:
    key = _required_key(idempotency_key)
    asset_id = _asset_id(prefix, key, principal)
    result, etag = append_asset(
        _scope(principal), kind=kind, asset_id=asset_id, payload=body.model_dump(mode="json"),
        expected_revision=0, idempotency_key=key, actor=principal.subject,
    )
    response.headers["ETag"] = etag
    return result


def _get_related_asset(
    *, kind: str, asset_id: str, response: Response, principal: Principal,
) -> dict[str, Any]:
    found = get_asset(_scope(principal), kind=kind, asset_id=asset_id, actor=principal.subject)
    if found is None:
        raise ApiError(code="EXPLORATION_NOT_FOUND", message=f"{kind} not found", status_code=404)
    result, etag = found
    response.headers["ETag"] = etag
    return result


def _update_related_asset(
    *, kind: str, asset_id: str, body: BaseModel, response: Response,
    if_match: str | None, idempotency_key: str | None, principal: Principal,
) -> dict[str, Any]:
    result, etag = append_asset(
        _scope(principal), kind=kind, asset_id=asset_id, payload=body.model_dump(mode="json"),
        expected_revision=_expected_revision(if_match), idempotency_key=_required_key(idempotency_key),
        actor=principal.subject,
    )
    response.headers["ETag"] = etag
    return result


def _archive_related_asset(
    *, kind: str, asset_id: str, archived: bool, response: Response,
    if_match: str | None, idempotency_key: str | None, principal: Principal,
) -> dict[str, Any]:
    result, etag = set_archived(
        _scope(principal), kind=kind, asset_id=asset_id, archived=archived,
        expected_revision=_expected_revision(if_match), idempotency_key=_required_key(idempotency_key),
        actor=principal.subject,
    )
    response.headers["ETag"] = etag
    return result


@router.get("/v1/ontology/object-sets")
def list_object_sets(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    items = list_assets(_scope(principal), kind="object_set", actor=principal.subject)
    return {"items": items, "count": len(items)}


@router.post("/v1/ontology/object-sets")
def create_object_set(
    body: ObjectSetIn,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    return _create_related_asset(
        kind="object_set", prefix="set", body=body, response=response,
        idempotency_key=idempotency_key, principal=principal,
    )


@router.get("/v1/ontology/object-sets/{asset_id}")
def get_object_set(asset_id: str, response: Response, principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    return _get_related_asset(kind="object_set", asset_id=asset_id, response=response, principal=principal)


@router.put("/v1/ontology/object-sets/{asset_id}")
def update_object_set(
    asset_id: str, body: ObjectSetIn, response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    return _update_related_asset(
        kind="object_set", asset_id=asset_id, body=body, response=response,
        if_match=if_match, idempotency_key=idempotency_key, principal=principal,
    )


@router.delete("/v1/ontology/object-sets/{asset_id}")
def archive_object_set(
    asset_id: str, response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    return _archive_related_asset(
        kind="object_set", asset_id=asset_id, archived=True, response=response,
        if_match=if_match, idempotency_key=idempotency_key, principal=principal,
    )


@router.post("/v1/ontology/object-sets/{asset_id}/restore")
def restore_object_set(
    asset_id: str, response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    return _archive_related_asset(
        kind="object_set", asset_id=asset_id, archived=False, response=response,
        if_match=if_match, idempotency_key=idempotency_key, principal=principal,
    )


@router.get("/v1/ontology/annotations")
def list_annotations(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    items = list_assets(_scope(principal), kind="annotation", actor=principal.subject)
    return {"items": items, "count": len(items)}


@router.post("/v1/ontology/annotations")
def create_annotation(
    body: AnnotationIn,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    return _create_related_asset(
        kind="annotation", prefix="ann", body=body, response=response,
        idempotency_key=idempotency_key, principal=principal,
    )


@router.get("/v1/ontology/annotations/{asset_id}")
def get_annotation(asset_id: str, response: Response, principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    return _get_related_asset(kind="annotation", asset_id=asset_id, response=response, principal=principal)


@router.put("/v1/ontology/annotations/{asset_id}")
def update_annotation(
    asset_id: str, body: AnnotationIn, response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    return _update_related_asset(
        kind="annotation", asset_id=asset_id, body=body, response=response,
        if_match=if_match, idempotency_key=idempotency_key, principal=principal,
    )


@router.delete("/v1/ontology/annotations/{asset_id}")
def archive_annotation(
    asset_id: str, response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    return _archive_related_asset(
        kind="annotation", asset_id=asset_id, archived=True, response=response,
        if_match=if_match, idempotency_key=idempotency_key, principal=principal,
    )


@router.post("/v1/ontology/annotations/{asset_id}/restore")
def restore_annotation(
    asset_id: str, response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    return _archive_related_asset(
        kind="annotation", asset_id=asset_id, archived=False, response=response,
        if_match=if_match, idempotency_key=idempotency_key, principal=principal,
    )


# ─────────────── #50 批量导出 ───────────────

class ExportRequest(BaseModel):
    object_type: str = Field(min_length=1)
    objects: list[dict[str, Any]] = Field(default_factory=list)
    fmt: str = "csv"
    columns: list[str] = Field(default_factory=list)
    object_ids: list[str] = Field(default_factory=list)


class BulkUpdateRequest(BaseModel):
    objects: list[dict[str, Any]] = Field(default_factory=list)
    updates: dict[str, Any] = Field(default_factory=dict)
    object_ids: list[str] = Field(default_factory=list)


class BulkDeleteRequest(BaseModel):
    objects: list[dict[str, Any]] = Field(default_factory=list)
    object_ids: list[str] = Field(default_factory=list)


@router.post("/v1/ontology/object-explorer/export")
def export_objects(
    body: ExportRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#50 · 导出对象数据。"""
    _ = principal
    try:
        result = get_export_engine().export(
            body.object_type, body.objects,
            fmt=body.fmt,
            columns=body.columns or None,
            object_ids=body.object_ids or None,
        )
        log.info("oe_export ot=%s fmt=%s rows=%s", body.object_type, body.fmt, result["total_rows"])
        return result
    except ExportError as err:
        raise _map_export_error(err) from err


@router.post("/v1/ontology/object-explorer/bulk-update")
def bulk_update(
    body: BulkUpdateRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#50 · 批量更新对象。"""
    _ = principal
    result = get_export_engine().bulk_update(
        body.objects, body.updates,
        object_ids=body.object_ids or None,
    )
    log.info("oe_bulk_update updated=%s", result["updated"])
    return result


@router.post("/v1/ontology/object-explorer/bulk-delete")
def bulk_delete(
    body: BulkDeleteRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#50 · 批量删除对象。"""
    _ = principal
    result = get_export_engine().bulk_delete(
        body.objects,
        object_ids=body.object_ids or None,
    )
    log.info("oe_bulk_delete deleted=%s remaining=%s", result["deleted"], result["remaining"])
    return result
