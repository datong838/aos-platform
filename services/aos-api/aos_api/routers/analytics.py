"""TA.0–TA.8 Analytics / Notebooks Facade — schemes 109–117 · OpenAPI · 73.

TA.4: read. TA.5: Draft propose. TA.6: export/lineage.
TA.8: Contour/Quiver/Vertex subset (not full BI/ML platforms).
Web never holds sidecar admin.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Any
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from aos_api.aip_kv_store import get_payload, put_payload
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.idempotency import idempotency_store
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["analytics"])
log = get_logger("aos-api.analytics")

KEY_SESSIONS = "analytics_notebook_sessions"
KEY_VERTEX_EXPERIMENTS = "analytics_vertex_experiments"
_TA8_DISCLAIMER = (
    "subset only · not Contour/Quiver/Vertex full product · "
    "not Superset/Metabase/Grafana/MLflow server"
)


def _fill_quiver_day_gaps(
    points: list[dict[str, Any]],
    limit_days: int,
) -> list[dict[str, Any]]:
    """159 · Fill missing calendar days with v=0 for continuous sparkline."""
    from datetime import date, timedelta

    end = date.today()
    start = end - timedelta(days=max(1, int(limit_days)) - 1)
    by_day = {str(p.get("t")): int(p.get("v") or 0) for p in points if p.get("t")}
    out: list[dict[str, Any]] = []
    cur = start
    while cur <= end:
        key = cur.isoformat()
        out.append({"t": key, "v": int(by_day.get(key, 0))})
        cur += timedelta(days=1)
    return out
_SQL_DENY = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|copy|pragma|call|execute)\b",
    re.I,
)
_SQL_SELECT_1 = re.compile(r"^\s*select\s+1\s*;?\s*$", re.I)
_SQL_SELECT_STAR = re.compile(r"^\s*select\s+\*\s*(from\s+\w+)?\s*;?\s*$", re.I)


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def analytics_url() -> str:
    return _env("AOS_ANALYTICS_URL").rstrip("/")


def analytics_public_url() -> str:
    return (_env("AOS_ANALYTICS_PUBLIC_URL") or analytics_url()).rstrip("/")


def sidecar_configured() -> bool:
    return bool(analytics_url())


def _probe_timeout() -> float:
    raw = _env("AOS_ANALYTICS_TIMEOUT_SEC", "2")
    try:
        return max(0.2, min(10.0, float(raw)))
    except ValueError:
        return 2.0


def probe_sidecar(base: str | None = None) -> tuple[bool, str, dict[str, Any]]:
    """Probe GET {base}/health. Returns (ok, detail, body_snippet)."""
    url = (base or analytics_url()).rstrip("/")
    if not url:
        return False, "unset", {}
    timeout = _probe_timeout()
    try:
        req = urlrequest.Request(f"{url}/health", method="GET")
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(4096)
        try:
            body = json.loads(raw.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeError):
            body = {}
        if not isinstance(body, dict):
            body = {}
        status = str(body.get("status") or "").lower()
        if status and status not in ("ok", "healthy", "up"):
            return False, f"unhealthy status={status}", body
        return True, "ok", body
    except (urlerror.URLError, TimeoutError, ValueError, OSError) as exc:
        return False, str(exc)[:200], {}


def _sidecar_json(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """HTTP JSON to analytics-runtime. Returns (status_code, body_dict)."""
    base = analytics_url()
    if not base:
        raise ApiError(
            code="ANALYTICS_SIDECAR_UNAVAILABLE",
            message="AOS_ANALYTICS_URL unset",
            status_code=503,
        )
    url = f"{base}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urlrequest.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urlrequest.urlopen(req, timeout=_probe_timeout()) as resp:
            raw = resp.read(65536)
            code = int(getattr(resp, "status", 200) or 200)
    except urlerror.HTTPError as exc:
        raw = exc.read(65536) if hasattr(exc, "read") else b"{}"
        code = int(exc.code)
    except (urlerror.URLError, TimeoutError, OSError) as exc:
        raise ApiError(
            code="ANALYTICS_SIDECAR_UNAVAILABLE",
            message="analytics-runtime request failed",
            status_code=503,
            details={"detail": str(exc)[:200], "path": path},
        ) from exc
    try:
        parsed = json.loads(raw.decode("utf-8", errors="replace")) if raw else {}
    except (json.JSONDecodeError, UnicodeError):
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {"raw": str(parsed)[:200]}
    return code, parsed


def _rewrite_ui_url(ui_url: str) -> str:
    """Rewrite sidecar host to AOS_ANALYTICS_PUBLIC_URL when set."""
    public = analytics_public_url()
    internal = analytics_url()
    if not ui_url or not public or public == internal:
        return ui_url
    try:
        parts = urlparse.urlsplit(ui_url)
        pub = urlparse.urlsplit(public)
        return urlparse.urlunsplit((pub.scheme, pub.netloc, parts.path, parts.query, parts.fragment))
    except ValueError:
        return ui_url


def _public_session_view(row: dict[str, Any]) -> dict[str, Any]:
    """Strip internal-only fields before returning to Web."""
    out = {
        "id": row.get("id"),
        "status": row.get("status"),
        "uiUrl": row.get("uiUrl"),
        "ticketExpiresAt": row.get("ticketExpiresAt"),
        "objectType": row.get("objectType"),
        "datasetRid": row.get("datasetRid"),
        "purpose": row.get("purpose"),
        "notebookUi": row.get("notebookUi") or "notebook7",
        "engine": row.get("engine") or "shaped-dev",
        "sidecar": row.get("sidecar") or "ok",
        "mode": row.get("mode") or "ta2-ticket",
    }
    return {k: v for k, v in out.items() if v is not None}


def _load_sessions() -> list[dict[str, Any]]:
    stored = get_payload(KEY_SESSIONS) or {}
    raw = stored.get("items")
    return list(raw) if isinstance(raw, list) else []


def _save_sessions(items: list[dict[str, Any]]) -> None:
    put_payload(KEY_SESSIONS, {"items": items[-100:]})


class SessionCreateIn(BaseModel):
    objectType: str | None = None
    datasetRid: str | None = None
    purpose: str | None = Field(default="explore")


class SqlPreviewIn(BaseModel):
    sql: str
    datasetRid: str | None = None
    objectType: str | None = None
    limit: int = Field(default=100, ge=1, le=1000)


class ObjectsListIn(BaseModel):
    objectType: str
    limit: int = Field(default=50, ge=1, le=1000)
    filters: list[dict[str, Any]] = Field(default_factory=list)


class ObjectsGetIn(BaseModel):
    objectType: str
    objectId: str


class DatasetPreviewIn(BaseModel):
    datasetRid: str
    limit: int = Field(default=100, ge=1, le=1000)


class WritebackProposeIn(BaseModel):
    objectType: str
    objectId: str
    proposed: dict[str, Any] = Field(default_factory=dict)
    actionTypeId: str = "CloseWorkOrder"
    title: str | None = None
    analysisNote: str | None = None
    autoApprove: bool = False


class AnalyticsExportIn(BaseModel):
    objectType: str | None = None
    datasetRid: str | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    format: str = Field(default="json")


class VertexExperimentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    objectType: str = "WorkOrder"
    params: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    mediaRid: str | None = None
    note: str | None = None


@router.get("/v1/analytics/health")
def analytics_health() -> dict[str, Any]:
    """Sidecar /health; unset/unreachable => degraded (honest)."""
    url = analytics_url()
    if not url:
        return {
            "status": "degraded",
            "sidecar": "unset",
            "notebookUi": "notebook7",
            "mode": "ta0-contract",
            "detail": "AOS_ANALYTICS_URL empty · start aos-dev-analytics (TA.1) or host script",
        }
    ok, detail, body = probe_sidecar(url)
    if ok:
        return {
            "status": "ok",
            "sidecar": "ok",
            "notebookUi": str(body.get("notebookUi") or "notebook7"),
            "engine": str(body.get("engine") or "shaped-dev"),
            "mode": "ta2-session",
            "urlSet": True,
            "service": str(body.get("service") or "analytics-runtime"),
            "sessionsCapable": True,
        }
    return {
        "status": "degraded",
        "sidecar": "unreachable",
        "notebookUi": "notebook7",
        "mode": "ta1-sidecar",
        "detail": detail,
        "urlSet": True,
    }


@router.get("/v1/notebooks/sessions")
def list_notebook_sessions(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    _ = principal
    items = [_public_session_view(s) for s in _load_sessions()]
    return {"items": items}


@router.post("/v1/notebooks/sessions")
def create_notebook_session(
    body: SessionCreateIn | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    payload = body or SessionCreateIn()
    if not sidecar_configured():
        raise ApiError(
            code="ANALYTICS_SIDECAR_UNAVAILABLE",
            message="analytics-runtime sidecar unset (AOS_ANALYTICS_URL); start TA.1 sidecar",
            status_code=503,
            details={
                "notebookUi": "notebook7",
                "objectType": payload.objectType,
                "datasetRid": payload.datasetRid,
                "purpose": payload.purpose,
            },
        )
    ok, detail, _hb = probe_sidecar()
    if not ok:
        raise ApiError(
            code="ANALYTICS_SIDECAR_UNAVAILABLE",
            message="analytics-runtime unreachable",
            status_code=503,
            details={"sidecar": "unreachable", "detail": detail, "mode": "ta2-ticket"},
        )
    code, remote = _sidecar_json(
        "POST",
        "/v1/sessions",
        {
            "objectType": payload.objectType,
            "datasetRid": payload.datasetRid,
            "purpose": payload.purpose or "explore",
            "principal": principal.subject,
        },
    )
    if code >= 400 or not remote.get("id"):
        raise ApiError(
            code="ANALYTICS_SESSION_TICKET_UNAVAILABLE",
            message="sidecar refused session ticket",
            status_code=503,
            details={"sidecarStatus": code, "body": {k: remote.get(k) for k in ("detail", "message", "status")}},
        )
    ui = _rewrite_ui_url(str(remote.get("uiUrl") or ""))
    row = {
        "id": str(remote["id"]),
        "status": str(remote.get("status") or "idle"),
        "uiUrl": ui,
        "ticketExpiresAt": remote.get("ticketExpiresAt"),
        "objectType": payload.objectType,
        "datasetRid": payload.datasetRid,
        "purpose": payload.purpose or "explore",
        "notebookUi": str(remote.get("notebookUi") or "notebook7"),
        "engine": str(remote.get("engine") or "shaped-dev"),
        "sidecar": "ok",
        "mode": "ta2-ticket",
        "createdAt": time.time(),
        "principal": principal.subject,
    }
    items = _load_sessions()
    items.append(row)
    _save_sessions(items)
    log.info("notebook_session_created id=%s principal=%s", row["id"], principal.subject)
    return _public_session_view(row)


@router.get("/v1/notebooks/sessions/{session_id}")
def get_notebook_session(
    session_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    hit = next((s for s in _load_sessions() if s.get("id") == session_id), None)
    if not hit:
        raise ApiError(code="NOT_FOUND", message="notebook session not found", status_code=404)
    return _public_session_view(hit)


@router.delete("/v1/notebooks/sessions/{session_id}")
def stop_notebook_session(
    session_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    items = _load_sessions()
    hit = next((s for s in items if s.get("id") == session_id), None)
    if not hit:
        raise ApiError(code="NOT_FOUND", message="notebook session not found", status_code=404)
    if sidecar_configured():
        try:
            _sidecar_json("DELETE", f"/v1/sessions/{session_id}")
        except ApiError:
            log.warning("notebook_session_sidecar_stop_failed id=%s", session_id)
    hit = {**hit, "status": "stopped", "stoppedAt": time.time(), "uiUrl": None}
    rest = [s for s in items if s.get("id") != session_id]
    rest.append(hit)
    _save_sessions(rest)
    log.info("notebook_session_stopped id=%s", session_id)
    return _public_session_view(hit)


def _snippet_object_type(type_id: str) -> str:
    return (
        f"# Object Type: {type_id}\n"
        f"# Host: POST /v1/analytics/objects/list ; explore only; write-back via Drafts\n"
        f'df = aos.objects.list("{type_id}")\n'
        f"print(df.head())\n"
    )


def _snippet_object(type_id: str, object_id: str) -> str:
    return (
        f"# Object: {type_id}/{object_id}\n"
        f"# Host: POST /v1/analytics/objects/get\n"
        f'obj = aos.objects.get("{type_id}", "{object_id}")\n'
        f"print(obj)\n"
    )


def _snippet_dataset(rid: str, name: str | None = None) -> str:
    label = name or rid
    return (
        f"# Dataset: {label}\n"
        f"# Host: POST /v1/analytics/datasets/preview ; read-only\n"
        f'df = aos.datasets.preview("{rid}", limit=100)\n'
        f"print(df.head())\n"
    )


def _rows_to_table(rows: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    cols: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                cols.append(k)
    return cols, rows


def _redacted_field_union(rows: list[dict[str, Any]]) -> list[str]:
    found: set[str] = set()
    for row in rows:
        raw = row.get("_redactedFields")
        if isinstance(raw, list):
            for f in raw:
                if f:
                    found.add(str(f))
    return sorted(found)


def _with_governance(table: dict[str, Any]) -> dict[str, Any]:
    rows = list(table.get("rows") or [])
    redacted = _redacted_field_union(rows)
    out = dict(table)
    out["governance"] = {
        "redactionApplied": True,
        "exportPolicy": "deny-if-redacted",
        "redactedFieldUnion": redacted,
        "mode": "ta6-governance",
    }
    return out


def _list_objects_table(
    principal: Principal,
    object_type: str,
    *,
    limit: int,
    filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from aos_api.db import connect
    from aos_api.marking import apply_field_redaction, can_access_object
    from aos_api.routers.object_sets import _prop_defs, _query_pg

    result = _query_pg(
        object_type=object_type,
        filters=list(filters or []),
        page=1,
        page_size=limit,
    )
    prop_defs = _prop_defs(object_type)
    kept: list[dict[str, Any]] = []
    with connect() as conn:
        for it in result.get("items") or []:
            oid = str(it.get("id") or "")
            if not oid or not can_access_object(principal, conn, object_type, oid):
                continue
            if prop_defs:
                kept.append(apply_field_redaction(principal, dict(it), prop_defs, conn=conn))
            else:
                kept.append(dict(it))
    columns, rows = _rows_to_table(kept)
    return _with_governance(
        {
            "mode": "ta4-read",
            "kind": "objectType",
            "objectType": object_type,
            "columns": columns,
            "rows": rows,
            "total": len(rows),
            "source": result.get("source") or "pg",
        }
    )


def _get_object_table(
    principal: Principal,
    object_type: str,
    object_id: str,
) -> dict[str, Any]:
    from aos_api.branch_store import effective_object, ensure_overlay_table
    from aos_api.db import connect
    from aos_api.marking import apply_field_redaction, ensure_object_access
    from aos_api.routers.object_sets import _prop_defs

    prop_defs = _prop_defs(object_type)
    with connect() as conn:
        ensure_overlay_table(conn)
        ensure_object_access(principal, conn, object_type, object_id)
        hit = effective_object(conn, object_type, object_id, None)
        if not hit:
            raise ApiError(code="NOT_FOUND", message="object not found", status_code=404)
        raw = {"id": object_id, "type": object_type, **(hit.get("props") or {})}
        if prop_defs:
            raw = apply_field_redaction(principal, raw, prop_defs, conn=conn)
    columns, rows = _rows_to_table([raw])
    return _with_governance(
        {
            "mode": "ta4-read",
            "kind": "object",
            "objectType": object_type,
            "objectId": object_id,
            "columns": columns,
            "rows": rows,
            "total": 1,
            "source": "pg",
        }
    )


def _lookup_dataset(rid: str) -> dict[str, Any] | None:
    from aos_api.routers import wave_ext

    ds = getattr(wave_ext, "_datasets", {}).get(rid)
    return dict(ds) if isinstance(ds, dict) else None


def _dataset_preview_table(
    principal: Principal,
    dataset_rid: str,
    *,
    limit: int,
) -> dict[str, Any]:
    ds = _lookup_dataset(dataset_rid)
    if not ds:
        raise ApiError(code="NOT_FOUND", message="dataset not found", status_code=404)
    hint = str(ds.get("objectTypeHint") or "").strip()
    if not hint:
        return _with_governance(
            {
                "mode": "ta4-read",
                "kind": "dataset",
                "datasetRid": dataset_rid,
                "name": ds.get("name"),
                "columns": [],
                "rows": [],
                "total": 0,
                "source": "dataset-meta",
                "detail": "no objectTypeHint; physical lake preview deferred",
            }
        )
    table = _list_objects_table(principal, hint, limit=limit)
    return _with_governance(
        {
            **table,
            "kind": "dataset",
            "datasetRid": dataset_rid,
            "name": ds.get("name"),
            "objectType": hint,
            "source": "dataset-hint",
        }
    )


@router.get("/v1/analytics/ontology-rail")
def analytics_ontology_rail(
    principal: Principal = Depends(require_principal),
    typeLimit: int = Query(default=20, ge=1, le=50),
    instanceLimit: int = Query(default=5, ge=0, le=20),
    datasetLimit: int = Query(default=20, ge=0, le=50),
) -> dict[str, Any]:
    """TA.3 · left-rail catalog with insertable code snippets (read-only explore)."""
    from aos_api.branch_store import effective_objects, ensure_overlay_table
    from aos_api.db import connect
    from aos_api.marking import can_access_object

    object_types: list[dict[str, Any]] = []
    try:
        with connect() as conn:
            ensure_overlay_table(conn)
            rows = conn.execute(
                "SELECT id, name, description, published FROM meta_object_type ORDER BY id"
            ).fetchall()
            for r in rows[:typeLimit]:
                tid = str(r["id"])
                instances: list[dict[str, Any]] = []
                if instanceLimit > 0:
                    try:
                        obj_rows = effective_objects(conn, tid, None)
                    except Exception as exc:  # pragma: no cover — table missing edge
                        log.warning("ontology_rail_instances_skip type=%s err=%s", tid, exc)
                        obj_rows = []
                    for o in obj_rows[:instanceLimit]:
                        oid = str(o.get("object_id") or "")
                        if not oid:
                            continue
                        if not can_access_object(principal, conn, tid, oid):
                            continue
                        instances.append(
                            {
                                "id": oid,
                                "kind": "object",
                                "snippet": _snippet_object(tid, oid),
                            }
                        )
                object_types.append(
                    {
                        "id": tid,
                        "name": r.get("name") or tid,
                        "description": r.get("description"),
                        "published": bool(r.get("published")),
                        "kind": "objectType",
                        "snippet": _snippet_object_type(tid),
                        "instances": instances,
                    }
                )
    except Exception as exc:
        raise ApiError(
            code="ANALYTICS_RAIL_UNAVAILABLE",
            message="failed to load ontology rail",
            status_code=503,
            details={"detail": str(exc)[:200]},
        ) from exc

    datasets: list[dict[str, Any]] = []
    try:
        from aos_api.routers import wave_ext

        raw_ds = list(getattr(wave_ext, "_datasets", {}).values())
        for d in raw_ds[:datasetLimit]:
            if not isinstance(d, dict):
                continue
            rid = str(d.get("rid") or d.get("id") or "")
            if not rid:
                continue
            name = d.get("name")
            datasets.append(
                {
                    "rid": rid,
                    "name": name,
                    "kind": "dataset",
                    "objectTypeHint": d.get("objectTypeHint"),
                    "snippet": _snippet_dataset(rid, str(name) if name else None),
                }
            )
    except Exception as exc:  # pragma: no cover
        log.warning("ontology_rail_datasets_skip err=%s", exc)

    log.info(
        "ontology_rail types=%s datasets=%s",
        len(object_types),
        len(datasets),
    )
    return {
        "mode": "ta3-rail",
        "objectTypes": object_types,
        "datasets": datasets,
    }


@router.post("/v1/analytics/objects/list")
def analytics_objects_list(
    body: ObjectsListIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """TA.4 · aos.objects.list — read-only ObjectSet sample."""
    if not (body.objectType or "").strip():
        raise ApiError(code="VALIDATION", message="objectType required", status_code=400)
    if len(body.filters) > 10:
        raise ApiError(
            code="VALIDATION",
            message="filters exceed 10 dimensions",
            status_code=400,
            details={"maxFilters": 10},
        )
    out = _list_objects_table(
        principal,
        body.objectType.strip(),
        limit=body.limit,
        filters=body.filters,
    )
    log.info("analytics_objects_list type=%s total=%s", body.objectType, out["total"])
    return out


@router.post("/v1/analytics/objects/get")
def analytics_objects_get(
    body: ObjectsGetIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """TA.4 · aos.objects.get — read-only single object."""
    if not (body.objectType or "").strip() or not (body.objectId or "").strip():
        raise ApiError(
            code="VALIDATION",
            message="objectType and objectId required",
            status_code=400,
        )
    return _get_object_table(principal, body.objectType.strip(), body.objectId.strip())


@router.post("/v1/analytics/datasets/preview")
def analytics_datasets_preview(
    body: DatasetPreviewIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """TA.4 · aos.datasets.preview — read-only; Dev via objectTypeHint."""
    if not (body.datasetRid or "").strip():
        raise ApiError(code="VALIDATION", message="datasetRid required", status_code=400)
    out = _dataset_preview_table(principal, body.datasetRid.strip(), limit=body.limit)
    log.info(
        "analytics_datasets_preview rid=%s total=%s source=%s",
        body.datasetRid,
        out.get("total"),
        out.get("source"),
    )
    return out


@router.post("/v1/analytics/sql/preview")
def analytics_sql_preview(
    body: SqlPreviewIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """TA.4 · whitelist SQL preview (select 1 | select * over sample)."""
    sql = (body.sql or "").strip()
    if not sql:
        raise ApiError(code="VALIDATION", message="sql required", status_code=400)
    if _SQL_DENY.search(sql):
        raise ApiError(
            code="ANALYTICS_SQL_FORBIDDEN",
            message="mutating / DDL SQL not allowed in analytics preview",
            status_code=400,
        )
    if _SQL_SELECT_1.match(sql):
        return {
            "mode": "ta4-read",
            "kind": "sql",
            "columns": ["v"],
            "rows": [{"v": 1}],
            "total": 1,
            "source": "sql-literal",
            "sql": sql,
        }
    if _SQL_SELECT_STAR.match(sql):
        if body.datasetRid:
            table = _dataset_preview_table(
                principal, body.datasetRid.strip(), limit=body.limit
            )
            return {**table, "kind": "sql", "sql": sql, "mode": "ta4-read"}
        object_type = (body.objectType or "").strip()
        if object_type:
            table = _list_objects_table(principal, object_type, limit=body.limit)
            return {**table, "kind": "sql", "sql": sql, "mode": "ta4-read"}
        raise ApiError(
            code="ANALYTICS_SQL_UNSUPPORTED",
            message="select * requires objectType or datasetRid context",
            status_code=400,
        )
    raise ApiError(
        code="ANALYTICS_SQL_UNSUPPORTED",
        message="only 'select 1' or 'select *' (with objectType/datasetRid) supported in TA.4",
        status_code=400,
        details={
            "hint": "use POST /v1/analytics/objects/list or /v1/analytics/datasets/preview",
            "datasetRid": body.datasetRid,
            "objectType": body.objectType,
        },
    )


@router.post("/v1/analytics/writeback/propose")
def analytics_writeback_propose(
    body: WritebackProposeIn,
    principal: Principal = Depends(require_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JSONResponse:
    """TA.5 · propose Draft from analysis context. Never writes production."""
    from aos_api.routers.runtime_write import _create_draft_from_execute

    if body.autoApprove:
        raise ApiError(
            code="ANALYTICS_SELF_APPROVE_FORBIDDEN",
            message="analyst self-approve forbidden; use Draft inbox after propose",
            status_code=400,
        )
    if not (body.objectType or "").strip() or not (body.objectId or "").strip():
        raise ApiError(
            code="VALIDATION",
            message="objectType and objectId required",
            status_code=400,
        )
    if not idempotency_key or not str(idempotency_key).strip():
        raise ApiError(
            code="MISSING_IDEMPOTENCY_KEY",
            message="Idempotency-Key required for analytics writeback propose",
            status_code=400,
        )
    key = str(idempotency_key).strip()
    cached = idempotency_store.get(principal.org_id, principal.project_id, key)
    if cached:
        return JSONResponse(
            status_code=cached["status_code"],
            content={**cached["body"], "idempotentReplay": True},
        )

    proposed = dict(body.proposed or {})
    # Keep analysisNote out of object props merge; use for reason/title only.
    note = (body.analysisNote or "").strip()
    proposed.pop("analysisNote", None)
    if not str(proposed.get("reason") or "").strip():
        proposed["reason"] = note or f"analytics-writeback:{body.objectType}/{body.objectId}"

    ot = body.objectType.strip()
    oid = body.objectId.strip()
    created = _create_draft_from_execute(
        principal=principal,
        action_type_id=(body.actionTypeId or "CloseWorkOrder").strip(),
        object_type=ot,
        object_id=oid,
        proposed=proposed,
    )
    title = (body.title or "").strip() or (
        f"分析写回 · {ot}/{oid}" + (f" · {note}" if note else "")
    )
    out = {
        **created,
        "title": title,
        "analysisNote": note or None,
        "mode": "ta5-writeback",
        "productionWritten": False,
        "approvePath": "/aip/drafts",
        "message": "draft proposed; approve in Draft inbox (no analyst self-approve)",
    }
    log.info(
        "analytics_writeback_propose draft=%s type=%s id=%s",
        out.get("id"),
        body.objectType,
        body.objectId,
    )
    idempotency_store.put(
        principal.org_id,
        principal.project_id,
        key,
        status_code=201,
        body=out,
    )
    return JSONResponse(status_code=201, content=out)


@router.post("/v1/analytics/export")
def analytics_export(
    body: AnalyticsExportIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """TA.6 · export analysis sample; deny if any field was redacted by Marking."""
    fmt = (body.format or "json").strip().lower()
    if fmt != "json":
        raise ApiError(
            code="ANALYTICS_EXPORT_UNSUPPORTED",
            message="only format=json supported in TA.6",
            status_code=400,
        )
    if body.datasetRid:
        table = _dataset_preview_table(
            principal, body.datasetRid.strip(), limit=body.limit
        )
    elif body.objectType and body.objectType.strip():
        table = _list_objects_table(
            principal, body.objectType.strip(), limit=body.limit
        )
    else:
        raise ApiError(
            code="VALIDATION",
            message="objectType or datasetRid required",
            status_code=400,
        )
    gov = table.get("governance") or {}
    redacted = list(gov.get("redactedFieldUnion") or [])
    if redacted:
        raise ApiError(
            code="ANALYTICS_EXPORT_FORBIDDEN",
            message="export denied: result contains Marking-redacted fields",
            status_code=403,
            details={
                "redactedFieldUnion": redacted,
                "exportPolicy": "deny-if-redacted",
                "hint": "raise markings or export only cleared subsets via approve path",
            },
        )
    # Strip per-row meta for export payload
    clean_rows: list[dict[str, Any]] = []
    for row in table.get("rows") or []:
        clean_rows.append({k: v for k, v in row.items() if k != "_redactedFields"})
    columns = [c for c in (table.get("columns") or []) if c != "_redactedFields"]
    log.info(
        "analytics_export ok type=%s rid=%s total=%s",
        body.objectType,
        body.datasetRid,
        len(clean_rows),
    )
    return {
        "mode": "ta6-export",
        "format": "json",
        "kind": table.get("kind"),
        "objectType": table.get("objectType"),
        "datasetRid": table.get("datasetRid"),
        "columns": columns,
        "rows": clean_rows,
        "total": len(clean_rows),
        "governance": gov,
        "productionWritten": False,
    }


@router.get("/v1/analytics/lineage")
def analytics_lineage(
    principal: Principal = Depends(require_principal),
    objectType: str = Query(...),
    objectId: str = Query(...),
    limit: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    """TA.6 · list recent decision_lineage for an analytics object context."""
    from aos_api.db import connect
    from aos_api.routers.runtime_write import ensure_lineage_schema

    _ = principal
    ensure_lineage_schema()
    ot = objectType.strip()
    oid = objectId.strip()
    if not ot or not oid:
        raise ApiError(
            code="VALIDATION",
            message="objectType and objectId required",
            status_code=400,
        )
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, draft_id, action_type_id, object_type, object_id, steps
            FROM decision_lineage
            WHERE object_type=%s AND object_id=%s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (ot, oid, limit),
        ).fetchall()
    items: list[dict[str, Any]] = []
    for r in rows:
        steps = r["steps"]
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except json.JSONDecodeError:
                steps = []
        items.append(
            {
                "id": r["id"],
                "draftId": r["draft_id"],
                "actionTypeId": r["action_type_id"],
                "objectType": r["object_type"],
                "objectId": r["object_id"],
                "steps": steps,
                "uiPath": f"/aip/lineage?id={r['id']}",
            }
        )
    log.info("analytics_lineage type=%s id=%s n=%s", ot, oid, len(items))
    return {
        "mode": "ta6-lineage",
        "objectType": ot,
        "objectId": oid,
        "items": items,
        "approvePath": "/aip/drafts",
        "lineagePath": "/aip/lineage",
    }


@router.get("/v1/analytics/contour/explore")
def analytics_contour_explore(
    principal: Principal = Depends(require_principal),
    objectType: str = Query(default="WorkOrder"),
    groupBy: str = Query(default="status"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, Any]:
    """TA.8 · Contour subset: group-by bucket counts over ObjectSet sample."""
    ot = (objectType or "WorkOrder").strip()
    field = (groupBy or "status").strip() or "status"
    if not ot:
        raise ApiError(code="VALIDATION", message="objectType required", status_code=400)
    table = _list_objects_table(principal, ot, limit=limit)
    rows = list(table.get("rows") or [])
    cols_raw = table.get("columns")
    if isinstance(cols_raw, list) and cols_raw:
        columns = [str(c) for c in cols_raw]
    elif rows:
        columns = [str(k) for k in rows[0].keys()]
    else:
        columns = ["status"]
    skip = {"id", "rid", "objectId", "object_id"}
    group_by_options = [c for c in columns if c not in skip][:16] or ["status"]
    if field not in group_by_options and field not in columns:
        # still allow explicit field; surface in options for honesty
        group_by_options = [field, *group_by_options]
    buckets: dict[str, int] = {}
    for row in rows:
        raw = row.get(field)
        key = "(null)" if raw is None or raw == "" else str(raw)
        buckets[key] = buckets.get(key, 0) + 1
    total_bucket = sum(buckets.values()) or 1
    items = [
        {
            "key": k,
            "count": v,
            "share": round(v / total_bucket, 4),
        }
        for k, v in sorted(buckets.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    log.info("analytics_contour type=%s groupBy=%s buckets=%s", ot, field, len(items))
    return {
        "mode": "ta8-contour-subset",
        "scheme": "159",
        "kind": "explore",
        "objectType": ot,
        "groupBy": field,
        "groupByOptions": group_by_options,
        "chartHint": "bar",
        "buckets": items,
        "totalRows": table.get("total") or 0,
        "source": table.get("source"),
        "governance": table.get("governance"),
        "disclaimer": _TA8_DISCLAIMER,
        "productionWritten": False,
    }


@router.get("/v1/analytics/quiver/series")
def analytics_quiver_series(
    principal: Principal = Depends(require_principal),
    objectType: str = Query(default="WorkOrder"),
    limitDays: int = Query(default=14, ge=1, le=90),
    fillGaps: bool = Query(default=True),
) -> dict[str, Any]:
    """TA.8 / 159 · Quiver subset: daily lineage density (+ optional day gaps)."""
    from aos_api.db import connect
    from aos_api.routers.runtime_write import ensure_lineage_schema

    _ = principal
    ot = (objectType or "WorkOrder").strip()
    if not ot:
        raise ApiError(code="VALIDATION", message="objectType required", status_code=400)
    ensure_lineage_schema()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT to_char(date_trunc('day', created_at), 'YYYY-MM-DD') AS day,
                   COUNT(*)::int AS n
            FROM decision_lineage
            WHERE object_type=%s
              AND created_at >= NOW() - (INTERVAL '1 day' * %s)
            GROUP BY 1
            ORDER BY 1
            """,
            (ot, int(limitDays)),
        ).fetchall()
    raw_points = [{"t": r["day"], "v": int(r["n"] or 0)} for r in rows]
    points = _fill_quiver_day_gaps(raw_points, int(limitDays)) if fillGaps else raw_points
    max_v = max((int(p.get("v") or 0) for p in points), default=0)
    log.info("analytics_quiver type=%s points=%s fillGaps=%s", ot, len(points), fillGaps)
    return {
        "mode": "ta8-quiver-subset",
        "scheme": "159",
        "kind": "timeseries",
        "objectType": ot,
        "metric": "lineageEventsPerDay",
        "chartHint": "line",
        "points": points,
        "rawPointCount": len(raw_points),
        "maxV": max_v,
        "fillGaps": bool(fillGaps),
        "total": len(points),
        "source": "decision_lineage",
        "disclaimer": _TA8_DISCLAIMER,
        "note": "true sensor timeseries deferred; series = writeback lineage density",
        "productionWritten": False,
    }


def _load_vertex_experiments() -> list[dict[str, Any]]:
    stored = get_payload(KEY_VERTEX_EXPERIMENTS) or {}
    items = stored.get("items")
    return list(items) if isinstance(items, list) else []


def _save_vertex_experiments(items: list[dict[str, Any]]) -> None:
    put_payload(KEY_VERTEX_EXPERIMENTS, {"items": items})


@router.get("/v1/analytics/vertex/experiments")
def analytics_vertex_list(
    principal: Principal = Depends(require_principal),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """TA.8 · Vertex subset: list registered experiments (metadata only)."""
    _ = principal
    items = _load_vertex_experiments()
    items_sorted = sorted(
        items,
        key=lambda x: str(x.get("createdAt") or ""),
        reverse=True,
    )[:limit]
    return {
        "mode": "ta8-vertex-subset",
        "scheme": "159",
        "kind": "experiments",
        "items": items_sorted,
        "total": len(items),
        "disclaimer": _TA8_DISCLAIMER,
        "note": "metadata registry only · not MLflow server / AutoML",
        "productionWritten": False,
    }


@router.post("/v1/analytics/vertex/experiments")
def analytics_vertex_create(
    body: VertexExperimentIn,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    """TA.8 · Vertex subset: register experiment metadata (no Ontology write)."""
    items = _load_vertex_experiments()
    exp_id = f"exp-{uuid.uuid4().hex[:10]}"
    row = {
        "id": exp_id,
        "name": body.name.strip(),
        "objectType": (body.objectType or "WorkOrder").strip(),
        "params": dict(body.params or {}),
        "metrics": dict(body.metrics or {}),
        "mediaRid": (body.mediaRid or "").strip() or None,
        "note": (body.note or "").strip() or None,
        "status": "registered",
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "createdBy": principal.subject,
        "orgId": principal.org_id,
        "projectId": principal.project_id,
    }
    items.append(row)
    _save_vertex_experiments(items)
    log.info("analytics_vertex_create id=%s name=%s", exp_id, row["name"])
    out = {
        **row,
        "mode": "ta8-vertex-subset",
        "scheme": "159",
        "disclaimer": _TA8_DISCLAIMER,
        "productionWritten": False,
        "message": "experiment registered; Ontology write still requires Draft approve",
    }
    return JSONResponse(status_code=201, content=out)


def seed_demo_session_meta_for_tests() -> dict[str, Any]:
    sid = f"nb-{uuid.uuid4().hex[:8]}"
    row = {
        "id": sid,
        "status": "stopped",
        "notebookUi": "notebook7",
        "sidecar": "unset",
        "mode": "ta0-contract",
    }
    items = _load_sessions()
    items.append(row)
    _save_sessions(items)
    return row
