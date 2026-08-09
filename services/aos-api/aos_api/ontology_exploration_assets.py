"""O1-UX2 PostgreSQL authority for saved explorations and related assets."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.ontology_explorer_contracts import KnowledgeSubjectRefDTO, ObjectRefDTO
from aos_api.ontology_operational_authority import canonical_hash
from aos_api.tenant_scope import TenantScope


AssetKind = Literal["exploration", "object_set", "annotation"]
Visibility = Literal["private", "workspace"]


class StrictAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExplorationAssetPayload(StrictAsset):
    name: str = Field(min_length=1, max_length=240)
    objectType: str = Field(min_length=1, max_length=128)
    viewMode: Literal["table", "graph", "annotation"] = "table"
    visibility: Visibility = "private"
    query: dict[str, Any] = Field(default_factory=dict)
    columns: list[dict[str, Any]] = Field(default_factory=list, max_length=256)
    graph: dict[str, Any] = Field(default_factory=dict)


class ObjectSetAssetPayload(StrictAsset):
    name: str = Field(min_length=1, max_length=240)
    objectType: str = Field(min_length=1, max_length=128)
    visibility: Visibility = "private"
    items: list[ObjectRefDTO] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def single_object_type(self) -> "ObjectSetAssetPayload":
        if any(item.objectType != self.objectType for item in self.items):
            raise ValueError("OBJECT_SET_TYPE_MISMATCH: one Object Type is required")
        if len({(item.objectType, item.objectId) for item in self.items}) != len(self.items):
            raise ValueError("duplicate ObjectRef in object set")
        return self


class AnnotationAssetPayload(StrictAsset):
    title: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=100_000)
    subject: KnowledgeSubjectRefDTO
    visibility: Visibility = "private"
    state: Literal["draft"] = "draft"


MODELS: dict[str, type[StrictAsset]] = {
    "exploration": ExplorationAssetPayload,
    "object_set": ObjectSetAssetPayload,
    "annotation": AnnotationAssetPayload,
}


def _tables(kind: str) -> tuple[str, str]:
    if kind not in MODELS:
        raise ValueError("unknown exploration asset kind")
    return f"ontology_{kind}_asset_head", f"ontology_{kind}_asset_revision"


def _normalize(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    model = MODELS.get(kind)
    if model is None:
        raise ValueError("unknown exploration asset kind")
    return model.model_validate(payload).model_dump(mode="json")


def _etag(kind: str, revision: int, payload_hash: str) -> str:
    return f'"ontology-{kind}-asset-v1:{revision}:{payload_hash}"'


def append_asset(
    scope: TenantScope,
    *,
    kind: AssetKind,
    asset_id: str,
    payload: dict[str, Any],
    expected_revision: int,
    idempotency_key: str,
    actor: str,
) -> tuple[dict[str, Any], str]:
    if expected_revision < 0 or not asset_id.strip() or not idempotency_key.strip() or not actor.strip():
        raise ValueError("asset id, revision, idempotency key and actor are required")
    normalized = _normalize(kind, payload)
    request_hash = canonical_hash({
        "scope": scope.key,
        "kind": kind,
        "id": asset_id,
        "operation": "append",
        "expectedRevision": expected_revision,
        "actor": actor,
        "payload": normalized,
    })
    head_table, revision_table = _tables(kind)
    with connect(scope) as conn:
        replay = _replay(conn, scope, idempotency_key, request_hash)
        if replay is not None:
            return replay
        conn.execute(
            f"INSERT INTO {head_table}(org_id,workspace_id,asset_id,owner_subject) "
            "VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (*scope.key, asset_id, actor),
        )
        head = conn.execute(
            f"SELECT owner_subject,active_revision,archived_at FROM {head_table} "
            "WHERE org_id=%s AND workspace_id=%s AND asset_id=%s FOR UPDATE",
            (*scope.key, asset_id),
        ).fetchone()
        if head["owner_subject"] != actor:
            raise ApiError(code="EXPLORATION_SHARE_FORBIDDEN", message="only the asset owner may write", status_code=403)
        current = int(head["active_revision"])
        if head["archived_at"] is not None:
            raise ApiError(code="EXPLORATION_ARCHIVE_REQUIRED", message="restore the asset before updating", status_code=409)
        if current != expected_revision:
            raise ApiError(
                code="REVISION_CONFLICT",
                message="exploration asset revision changed",
                status_code=412,
                details={"expected": expected_revision, "actual": current},
            )
        revision = current + 1
        payload_hash = canonical_hash(normalized)
        conn.execute(
            f"INSERT INTO {revision_table}(org_id,workspace_id,asset_id,revision,payload,payload_hash,created_by) "
            "VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s)",
            (*scope.key, asset_id, revision, json.dumps(normalized, ensure_ascii=False), payload_hash, actor),
        )
        if kind == "object_set":
            for position, item in enumerate(normalized["items"]):
                conn.execute(
                    "INSERT INTO ontology_object_set_item(org_id,workspace_id,object_set_id,object_set_revision," 
                    "position,object_type,object_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (*scope.key, asset_id, revision, position, item["objectType"], item["objectId"]),
                )
        conn.execute(
            f"UPDATE {head_table} SET active_revision=%s,updated_at=now() "
            "WHERE org_id=%s AND workspace_id=%s AND asset_id=%s",
            (revision, *scope.key, asset_id),
        )
        etag = _etag(kind, revision, payload_hash)
        result = _result(kind, asset_id, actor, revision, normalized, payload_hash, archived=False)
        _insert_receipt(
            conn, scope, idempotency_key, request_hash, kind, asset_id, "append",
            expected_revision, revision, etag, result, actor,
        )
        return result, etag


def get_asset(
    scope: TenantScope,
    *,
    kind: AssetKind,
    asset_id: str,
    actor: str,
    include_archived: bool = False,
) -> tuple[dict[str, Any], str] | None:
    head_table, revision_table = _tables(kind)
    with connect(scope) as conn:
        row = conn.execute(
            f"SELECT h.owner_subject,h.archived_at,r.revision,r.payload,r.payload_hash "
            f"FROM {head_table} h JOIN {revision_table} r ON r.org_id=h.org_id AND r.workspace_id=h.workspace_id "
            "AND r.asset_id=h.asset_id AND r.revision=h.active_revision "
            "WHERE h.org_id=%s AND h.workspace_id=%s AND h.asset_id=%s",
            (*scope.key, asset_id),
        ).fetchone()
        if row is None or (row["archived_at"] is not None and not include_archived):
            return None
        payload = dict(row["payload"])
        if payload.get("visibility") == "private" and row["owner_subject"] != actor:
            return None
        result = _result(
            kind, asset_id, row["owner_subject"], int(row["revision"]), payload,
            row["payload_hash"], archived=row["archived_at"] is not None,
        )
        return result, _etag(kind, int(row["revision"]), row["payload_hash"])


def list_assets(
    scope: TenantScope,
    *,
    kind: AssetKind,
    actor: str,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    head_table, revision_table = _tables(kind)
    with connect(scope) as conn:
        rows = conn.execute(
            f"SELECT h.asset_id,h.owner_subject,h.archived_at,r.revision,r.payload,r.payload_hash "
            f"FROM {head_table} h JOIN {revision_table} r ON r.org_id=h.org_id AND r.workspace_id=h.workspace_id "
            "AND r.asset_id=h.asset_id AND r.revision=h.active_revision "
            "WHERE h.org_id=%s AND h.workspace_id=%s "
            "AND (%s OR h.archived_at IS NULL) "
            "AND (h.owner_subject=%s OR r.payload->>'visibility'='workspace') "
            "ORDER BY h.updated_at DESC,h.asset_id",
            (*scope.key, include_archived, actor),
        ).fetchall()
        return [
            _result(
                kind, row["asset_id"], row["owner_subject"], int(row["revision"]),
                dict(row["payload"]), row["payload_hash"], archived=row["archived_at"] is not None,
            )
            for row in rows
        ]


def set_archived(
    scope: TenantScope,
    *,
    kind: AssetKind,
    asset_id: str,
    archived: bool,
    expected_revision: int,
    idempotency_key: str,
    actor: str,
) -> tuple[dict[str, Any], str]:
    if expected_revision < 1:
        raise ValueError("expected revision must be positive")
    operation = "archive" if archived else "restore"
    request_hash = canonical_hash({
        "scope": scope.key, "kind": kind, "id": asset_id, "operation": operation,
        "expectedRevision": expected_revision, "actor": actor,
    })
    head_table, revision_table = _tables(kind)
    with connect(scope) as conn:
        replay = _replay(conn, scope, idempotency_key, request_hash)
        if replay is not None:
            return replay
        row = conn.execute(
            f"SELECT h.owner_subject,h.active_revision,h.archived_at,r.payload,r.payload_hash "
            f"FROM {head_table} h JOIN {revision_table} r ON r.org_id=h.org_id AND r.workspace_id=h.workspace_id "
            "AND r.asset_id=h.asset_id AND r.revision=h.active_revision "
            "WHERE h.org_id=%s AND h.workspace_id=%s AND h.asset_id=%s FOR UPDATE OF h",
            (*scope.key, asset_id),
        ).fetchone()
        if row is None:
            raise ApiError(code="EXPLORATION_NOT_FOUND", message="exploration asset not found", status_code=404)
        if row["owner_subject"] != actor:
            raise ApiError(code="EXPLORATION_SHARE_FORBIDDEN", message="only the asset owner may archive", status_code=403)
        revision = int(row["active_revision"])
        if revision != expected_revision:
            raise ApiError(code="REVISION_CONFLICT", message="exploration asset revision changed", status_code=412)
        is_archived = row["archived_at"] is not None
        if is_archived != archived:
            conn.execute(
                f"UPDATE {head_table} SET archived_at={('now()' if archived else 'NULL')},updated_at=now() "
                "WHERE org_id=%s AND workspace_id=%s AND asset_id=%s",
                (*scope.key, asset_id),
            )
        payload = dict(row["payload"])
        etag = _etag(kind, revision, row["payload_hash"])
        result = _result(kind, asset_id, actor, revision, payload, row["payload_hash"], archived=archived)
        _insert_receipt(
            conn, scope, idempotency_key, request_hash, kind, asset_id, operation,
            expected_revision, revision, etag, result, actor,
        )
        return result, etag


def _replay(conn: Any, scope: TenantScope, key: str, request_hash: str) -> tuple[dict[str, Any], str] | None:
    row = conn.execute(
        "SELECT request_hash,response_etag,result_json FROM ontology_exploration_asset_receipt "
        "WHERE org_id=%s AND workspace_id=%s AND idempotency_key=%s",
        (*scope.key, key),
    ).fetchone()
    if row is None:
        return None
    if row["request_hash"] != request_hash:
        raise ApiError(code="IDEMPOTENCY_CONFLICT", message="idempotency key payload differs", status_code=409)
    return dict(row["result_json"]), row["response_etag"]


def _insert_receipt(
    conn: Any,
    scope: TenantScope,
    key: str,
    request_hash: str,
    kind: str,
    asset_id: str,
    operation: str,
    expected_revision: int,
    resulting_revision: int,
    etag: str,
    result: dict[str, Any],
    actor: str,
) -> None:
    conn.execute(
        "INSERT INTO ontology_exploration_asset_receipt(org_id,workspace_id,idempotency_key,request_hash," 
        "asset_kind,asset_id,operation,expected_revision,resulting_revision,response_etag,result_json,actor) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
        (*scope.key, key, request_hash, kind, asset_id, operation, expected_revision,
         resulting_revision, etag, json.dumps(result, ensure_ascii=False), actor),
    )


def _result(
    kind: str,
    asset_id: str,
    owner: str,
    revision: int,
    payload: dict[str, Any],
    payload_hash: str,
    *,
    archived: bool,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": asset_id,
        "owner": owner,
        "revision": revision,
        "payload": payload,
        "payloadHash": payload_hash,
        "archived": archived,
    }
