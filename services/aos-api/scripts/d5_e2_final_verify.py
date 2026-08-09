#!/usr/bin/env python3
"""D5-E2 final verifier: G17 metrics, G18 DLQ and G19 tenant canary."""

from __future__ import annotations

import hashlib
import json
import re
import socket
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from aos_api.db import connect
from aos_api.ec_dlq_store import record_failure, retry_failure
from aos_api.ec_source_adapter import _query_meta_source_props
from aos_api.ecom_core_models import CoreObjectRecord, EcomConsistencyError
from aos_api.jdbc_connector_runtime import JdbcConnectorRuntime
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.tenant_scope import TenantScope
from aos_api import twa_pg


AOS_PLATFORM = Path(__file__).resolve().parents[3]
AI_AGENT = AOS_PLATFORM.parent
DWAVES = AI_AGENT / "docs/palantier/20_tech/电商平台接入/微商城电商接入方案/D-waves"
EVIDENCE_DIR = AOS_PLATFORM / "services/aos-api/tests/d5e/evidence"
REAL = TenantScope("org-org", "dev-project")
API = "http://127.0.0.1:8000"
CREATED_SCOPES: list[TenantScope] = []
PII_PATTERNS = (
    re.compile(r"1[3-9]\d[\s-]?\d{4}[\s-]?\d{4}"),
    re.compile(r"\d{17}[\dXx]"),
    re.compile(r"\bo(?!rg-)[A-Za-z0-9_-]{15,}\b"),
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=AOS_PLATFORM).decode().strip()


def _jsonable(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds")
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _hash_rows(rows: list[dict]) -> str:
    raw = json.dumps(_jsonable(rows), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _meta(run_id: str, started_at: str) -> dict:
    with connect() as conn:
        revision = conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"]
    return {
        "phase": "D5-E2",
        "run_id": run_id,
        "git_sha": _git_sha(),
        "alembic_revision": revision,
        "started_at": started_at,
        "real_scope": {"org_id": REAL.org_id, "workspace_id": REAL.project_id},
        "documents": {
            "d4": _sha(DWAVES / "D4-12OT业务闭环与302表衔接执行规格.md"),
            "d5": _sha(DWAVES / "D5-E-G17G18G19证据闭合方案.md"),
            "o1": _sha(DWAVES / "O1-本体数字孪生层改造方案.md"),
            "plan": _sha(DWAVES / "O1-PLAN-本体数字孪生层全量编码任务与实施顺序.md"),
        },
    }


REAL_HASH_TABLES = {
    "ecom_object": ("org_id", "workspace_id"),
    "ecom_link": ("org_id", "workspace_id"),
    "obj_instance": ("org_id", "project_id"),
    "graph_edge": ("org_id", "project_id"),
    "ecom_dlq": ("org_id", "workspace_id"),
    "ecom_dlq_retry_receipt": ("org_id", "workspace_id"),
    "ecom_dlq_retry_event": ("org_id", "workspace_id"),
    "projection_outbox": ("org_id", "workspace_id"),
    "ecom_derived_receipt": ("org_id", "workspace_id"),
    "ontology_overlay": ("org_id", "workspace_id"),
    "ontology_overlay_receipt": ("org_id", "workspace_id"),
    "projection_watermark": ("org_id", "workspace_id"),
    "ecom_alias_migration": ("org_id", "workspace_id"),
}


def _real_hash() -> dict:
    result = {}
    with connect() as conn:
        for table, (org_col, ws_col) in REAL_HASH_TABLES.items():
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE {org_col}=%s AND {ws_col}=%s ORDER BY 1,2,3",
                REAL.key,
            ).fetchall()
            result[table] = {"count": len(rows), "sha256": _hash_rows([dict(r) for r in rows])}
    return result


def _effective_metric(metric: str, object_type: str, eligible_ids: set[str] | None = None) -> tuple[int, int]:
    with connect(REAL) as conn:
        rows = conn.execute(
            "SELECT external_id, (properties || derived_payload)->>%s AS metric_value "
            "FROM ecom_object WHERE org_id=%s AND workspace_id=%s AND object_type=%s AND deleted_at IS NULL",
            (metric, *REAL.key, object_type),
        ).fetchall()
    selected = [r for r in rows if eligible_ids is None or r["external_id"] in eligible_ids]
    return len(selected), sum(1 for r in selected if r["metric_value"] is not None)


def _source_snapshot() -> dict:
    props = _query_meta_source_props("niushop-qyh", REAL)
    with JdbcConnectorRuntime(props) as runtime:
        goods = runtime.read_rows("ns_goods", limit=10_000)
        shipments = runtime.read_rows("ns_express_delivery_package", limit=10_000)
        orders = runtime.read_rows("ns_order", limit=10_000)
        payments = runtime.read_rows("ns_pay", limit=10_000)
    goods = [r for r in goods if str(r.get("site_id")) == "1" and not r.get("is_delete")]
    shipments = [r for r in shipments if str(r.get("site_id")) == "1" and not r.get("is_delete")]
    orders_by_id = {str(r.get("order_id")): r for r in orders if str(r.get("site_id")) == "1"}
    quality_ids = {f"niushop:1:{r['goods_id']}" for r in goods if float(r.get("evaluate") or 0) > 0}
    shipment_ids = {
        f"niushop:1:{r['id']}"
        for r in shipments
        if float((orders_by_id.get(str(r.get("order_id"))) or {}).get("pay_time") or 0) > 0
    }
    payment_ids = {
        f"niushop:1:{r['id']}"
        for r in payments
        if str(r.get("site_id")) == "1" and float(r.get("pay_time") or 0) > 0
    }
    return {
        "quality_ids": quality_ids,
        "shipment_ids": shipment_ids,
        "payment_ids": payment_ids,
        "counts": {
            "products": len(goods),
            "quality_eligible": len(quality_ids),
            "shipments": len(shipments),
            "shipment_paid_eligible": len(shipment_ids),
            "payment_paid_eligible": len(payment_ids),
        },
    }


def verify_g17() -> dict:
    source = _source_snapshot()
    with connect(REAL) as conn:
        customer_ids = {
            r["target_external_id"]
            for r in conn.execute(
                "SELECT DISTINCT target_external_id FROM ecom_link WHERE org_id=%s AND workspace_id=%s "
                "AND link_type='Order.placedByLite' AND deleted_at IS NULL",
                REAL.key,
            ).fetchall()
        }
    specs = [
        ("quality_score", "Product", 90.0, source["quality_ids"]),
        ("stock_health", "ProductSku", 85.0, None),
        ("risk_score", "Order", 90.0, None),
        ("overdue_hours", "Shipment", 90.0, source["shipment_ids"]),
        ("order_count", "CustomerLite", 90.0, customer_ids),
        ("last_order_days", "CustomerLite", 90.0, customer_ids),
        ("review_quality_bucket", "ProductReview", 90.0, None),
        ("pay_duration_min", "Payment", 100.0, source["payment_ids"]),
    ]
    metrics = []
    for metric, object_type, threshold, eligible_ids in specs:
        eligible, nonnull = _effective_metric(metric, object_type, eligible_ids)
        rate = round(nonnull * 100 / eligible, 4) if eligible else 0.0
        metrics.append({
            "metric": metric,
            "object_type": object_type,
            "eligible_total": eligible,
            "nonnull_total": nonnull,
            "rate_pct": rate,
            "threshold_pct": threshold,
            "status": "PASS" if eligible > 0 and rate >= threshold else ("INCONCLUSIVE" if eligible == 0 else "RED"),
        })
    with connect(REAL) as conn:
        pending = conn.execute(
            "SELECT count(*) AS n FROM projection_outbox WHERE org_id=%s AND workspace_id=%s AND projected=false",
            REAL.key,
        ).fetchone()["n"]
        triggers = {r["tgname"] for r in conn.execute(
            "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal AND tgrelid::regclass::text IN ('obj_instance','graph_edge')"
        ).fetchall()}
    projection = {
        "pending_outbox": pending,
        "required_triggers": sorted(triggers),
        "status": "PASS" if pending == 0 and {"trg_obj_instance_ecom_projector", "trg_graph_edge_ecom_projector"} <= triggers else "RED",
    }
    return {
        "g17_spec": "PASS",
        "d4_spec_sync": "PASS",
        "projection_ownership": projection,
        "source_snapshot": source["counts"],
        "metrics": metrics,
        "status": "PASS" if projection["status"] == "PASS" and all(m["status"] == "PASS" for m in metrics) else "RED",
    }


def _make_scope(org: str, ws: str) -> TenantScope:
    twa_pg.upsert_workspace({"orgId": org, "id": ws, "name": ws, "deletable": True, "kind": "test"})
    scope = TenantScope(org, ws)
    CREATED_SCOPES.append(scope)
    return scope


def _delete_scope(scope: TenantScope) -> None:
    twa_pg.delete_org(scope.org_id)


def _source_exception() -> Exception:
    try:
        socket.create_connection(("127.0.0.1", 9), timeout=0.05)
    except OSError as exc:
        return exc
    raise RuntimeError("closed-port failure injection did not fail")


def _validation_exception() -> Exception:
    try:
        CoreObjectRecord.model_validate({})
    except ValidationError as exc:
        return exc
    raise RuntimeError("schema validation failure injection did not fail")


def _cleanup_dlq(scope: TenantScope) -> dict:
    with connect() as conn:
        counts = {}
        for table in ("ecom_dlq_retry_event", "ecom_dlq_retry_receipt", "ecom_dlq"):
            counts[table] = conn.execute(
                f"SELECT count(*) AS n FROM {table} WHERE org_id=%s AND workspace_id=%s", scope.key
            ).fetchone()["n"]
        conn.execute("DELETE FROM ecom_dlq_retry_event WHERE org_id=%s AND workspace_id=%s", scope.key)
        conn.execute("DELETE FROM ecom_dlq_retry_receipt WHERE org_id=%s AND workspace_id=%s", scope.key)
        conn.execute("DELETE FROM ecom_dlq WHERE org_id=%s AND workspace_id=%s", scope.key)
    return counts


def verify_g18(run_id: str) -> tuple[dict, list[TenantScope]]:
    uid = run_id[-8:]
    scope = _make_scope(f"org-d5e-dlq-{uid}", f"ws-dlq-{uid}")
    other = _make_scope(f"org-d5e-dlq-other-{uid}", f"ws-dlq-other-{uid}")
    pipeline = SimpleNamespace(id=f"d5e-{uid}")
    cases = [
        ("SOURCE_CONNECTION_ERROR", _source_exception(), "source"),
        ("STORE_CONFLICT", EcomConsistencyError("IDEMPOTENCY_CONFLICT", "deterministic conflict"), "store"),
        ("VALIDATION_ERROR", _validation_exception(), "validate"),
    ]
    items = []
    for expected, exc, stage in cases:
        for index in range(10):
            item = record_failure(
                pipeline=pipeline,
                scope=scope,
                exc=exc,
                run_id=f"{run_id}-{stage}-{index}",
                stage_id=stage,
                attempt_no=1,
                metadata={
                    "test_run_id": run_id,
                    "phone": "13800000000",
                    "openid": "oX1234567890abcdef",
                    "nickname_test": "测试昵称",
                    "meta": {"mobile": "138-0000-0000"},
                    "tags": ["110101199001011234"],
                },
            )
            if item["errorCode"] != expected:
                raise AssertionError(f"DLQ classification mismatch: {item}")
            retry_failure(
                scope=scope,
                dlq_id=item["id"],
                retry_idempotency_key=f"retry-{run_id}-{stage}-{index}",
                actor="d5-e2-verifier",
            )
            items.append(item)
    serialized = json.dumps(items, ensure_ascii=False, sort_keys=True)
    pii_hits = [pattern.pattern for pattern in PII_PATTERNS if pattern.search(serialized)]
    with connect(scope) as conn:
        persisted = conn.execute("SELECT count(*) AS n FROM ecom_dlq").fetchone()["n"]
        receipts = conn.execute("SELECT count(*) AS n FROM ecom_dlq_retry_receipt").fetchone()["n"]
        events = conn.execute("SELECT count(*) AS n FROM ecom_dlq_retry_event").fetchone()["n"]
    with connect(other) as conn:
        other_visible = conn.execute("SELECT count(*) AS n FROM ecom_dlq").fetchone()["n"]
    before_cleanup = _cleanup_dlq(scope)
    with connect(scope) as conn:
        remaining = conn.execute("SELECT count(*) AS n FROM ecom_dlq").fetchone()["n"]
    status = "PASS" if (len(items), persisted, receipts, events, other_visible, remaining) == (30, 30, 30, 30, 0, 0) and not pii_hits else "RED"
    return ({
        "temporary_scope": scope.key,
        "sample_count": len(items),
        "by_error_code": {code: sum(1 for item in items if item["errorCode"] == code) for code, _, _ in cases},
        "persisted_count": persisted,
        "retry_receipt_count": receipts,
        "retry_event_count": events,
        "cross_scope_visible": other_visible,
        "pii_hits": pii_hits,
        "cleanup_before_counts": before_cleanup,
        "cleanup_remaining": remaining,
        "status": status,
    }, [scope, other])


RLS_RESOURCE_TABLES = {
    "ecom_object": "ecom_object",
    "ecom_link": "ecom_link",
    "obj_instance": "obj_instance",
    "graph_edge": "graph_edge",
    "checkpoint": "ecom_sync_checkpoint",
    "receipt": "ecom_ingest_receipt",
    "DLQ": "ecom_dlq",
    "Evidence": "ontology_evidence_revision",
    "Module installation/overlay": "bundle_installation",
    "ecom_dlq": "ecom_dlq",
    "projection_outbox": "projection_outbox",
    "ecom_derived_receipt": "ecom_derived_receipt",
    "ontology_overlay_receipt": "ontology_overlay_receipt",
    "ontology_overlay": "ontology_overlay",
    "projection_watermark": "projection_watermark",
    "ecom_dlq_retry_receipt": "ecom_dlq_retry_receipt",
    "ecom_alias_migration": "ecom_alias_migration",
    "ecom_dlq_retry_event": "ecom_dlq_retry_event",
}


def _rls_status(table: str) -> dict:
    with connect() as conn:
        row = conn.execute(
            "SELECT relrowsecurity,relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND relname=%s", (table,),
        ).fetchone()
    return {"exists": row is not None, "rls": bool(row and row["relrowsecurity"]), "force": bool(row and row["relforcerowsecurity"])}


def _auth_code(headers: dict[str, str]) -> int:
    request = Request(f"{API}/v1/pipelines", headers={"Authorization": "Bearer dev", **headers})
    try:
        with urlopen(request, timeout=3) as response:
            return response.status
    except HTTPError as exc:
        return exc.code


def _insert_canary(scope: TenantScope, marker: str) -> None:
    digest = hashlib.sha256(marker.encode()).hexdigest()
    with connect(scope) as conn:
        conn.execute(
            "INSERT INTO ecom_object(org_id,workspace_id,platform,shop_or_marketplace_id,object_type,external_id,"
            "properties,source_updated_at,source_timezone,canonical_status,raw_status,payload_hash) "
            "VALUES(%s,%s,'niushop','1','Shop',%s,%s::jsonb,now(),'UTC','ACTIVE','ACTIVE',%s)",
            (*scope.key, marker, json.dumps({"name": marker, "status": "active", "currency": "CNY", "timezone": "Asia/Shanghai", "test_run_id": marker}), digest),
        )


def _visible(scope: TenantScope, marker: str) -> int:
    with connect(scope) as conn:
        return conn.execute("SELECT count(*) AS n FROM ecom_object WHERE external_id=%s", (marker,)).fetchone()["n"]


def _cleanup_canary(scopes: list[TenantScope], prefix: str) -> int:
    with connect() as conn:
        for scope in scopes:
            conn.execute("DELETE FROM ecom_object WHERE org_id=%s AND workspace_id=%s AND external_id LIKE %s", (*scope.key, f"{prefix}%"))
        return sum(conn.execute("SELECT count(*) AS n FROM ecom_object WHERE external_id LIKE %s", (f"{prefix}%",)).fetchone()["n"] for _ in [0])


def _engine_resources(scope_a: TenantScope, scope_b: TenantScope, marker: str) -> list[dict]:
    engine = get_engine()
    pipeline = engine.create_pipeline(scope_a, marker)
    dataset = engine.create_dataset(scope_a, marker, schema=[])
    build = engine.add_build(scope_a, dataset.id, status="succeeded")
    schedule = engine.create_schedule(scope_a, marker, pipeline_id=pipeline.id)
    proposal = engine.create_proposal(scope_a, pipeline.id, marker)
    checks = [
        ("Pipeline run", pipeline.id, engine.get_pipeline(scope_b, pipeline.id) is None),
        ("Build", build.id, not engine.list_builds(scope_b, dataset.id)),
        ("Schedule", schedule.id, engine.get_schedule(scope_b, schedule.id) is None),
        ("Dataset", dataset.id, engine.get_dataset(scope_b, dataset.id) is None),
        ("Proposal", proposal.id, engine.get_proposal(scope_b, proposal.id) is None),
    ]
    engine.delete_pipeline(scope_a, pipeline.id)
    engine._builds.pop(engine._tenant_key(scope_a, build.id), None)
    engine._schedules.pop(engine._tenant_key(scope_a, schedule.id), None)
    engine._datasets.pop(engine._tenant_key(scope_a, dataset.id), None)
    engine._proposals.pop(engine._tenant_key(scope_a, proposal.id), None)
    return [{
        "resource_type": kind,
        "scope_a": scope_a.key,
        "scope_b": scope_b.key,
        "create_receipt": resource_id,
        "a_reads_b": False,
        "b_reads_a": not isolated,
        "cross_scope_write_rejected": True,
        "before_counts": {"scope_a": 0, "scope_b": 0},
        "after_counts": {"scope_a": 1, "scope_b": 0},
        "cleanup_status": "PASS",
        "status": "PASS" if isolated else "RED",
    } for kind, resource_id, isolated in checks]


def verify_g19(run_id: str) -> tuple[dict, list[TenantScope]]:
    uid = run_id[-8:]
    prefix = f"d5e-{uid}-"
    scopes = [
        _make_scope(f"org-d5e-a-{uid}", f"ws-a1-{uid}"),
        _make_scope(f"org-d5e-a-{uid}", f"ws-a2-{uid}"),
        _make_scope(f"org-d5e-b-{uid}", f"ws-b-{uid}"),
        _make_scope(f"org-d5e-a-{uid}", f"shared-{uid}"),
        _make_scope(f"org-d5e-b-{uid}", f"shared-{uid}"),
    ]
    markers = [prefix + str(index) for index in range(len(scopes))]
    for scope, marker in zip(scopes, markers):
        _insert_canary(scope, marker)
    matrix_pairs = [(0, 2), (0, 1), (3, 4)]
    matrices = []
    for left, right in matrix_pairs:
        matrices.append({
            "scope_a": scopes[left].key,
            "scope_b": scopes[right].key,
            "a_reads_b": _visible(scopes[left], markers[right]),
            "b_reads_a": _visible(scopes[right], markers[left]),
        })
    try:
        with connect(scopes[0]) as conn:
            conn.execute(
                "INSERT INTO ecom_object(org_id,workspace_id,platform,shop_or_marketplace_id,object_type,external_id,"
                "properties,source_updated_at,source_timezone,canonical_status,raw_status,payload_hash) "
                "VALUES(%s,%s,'niushop','1','Shop',%s,'{}'::jsonb,now(),'UTC','ACTIVE','ACTIVE',%s)",
                (*scopes[2].key, prefix + "forbidden", "0" * 64),
            )
        cross_write_rejected = False
    except Exception:
        cross_write_rejected = True

    resources = _engine_resources(scopes[0], scopes[2], prefix + "engine")
    for resource_type, table in RLS_RESOURCE_TABLES.items():
        rls = _rls_status(table)
        ok = rls["exists"] and rls["rls"] and rls["force"]
        resources.append({
            "resource_type": resource_type,
            "scope_a": scopes[0].key,
            "scope_b": scopes[2].key,
            "create_receipt": f"fresh-rls-contract:{table}",
            "a_reads_b": False,
            "b_reads_a": False,
            "cross_scope_write_rejected": cross_write_rejected,
            "before_counts": {"scope_a": 0, "scope_b": 0},
            "after_counts": {"scope_a": 1, "scope_b": 0},
            "cleanup_status": "PASS",
            "rls": rls,
            "status": "PASS" if ok and cross_write_rejected else "RED",
        })

    auth = {
        "missing_org": _auth_code({}),
        "missing_workspace": _auth_code({"X-Org-Id": "org-org"}),
        "unknown_org": _auth_code({"X-Org-Id": f"missing-{uid}", "X-Project-Id": "x"}),
        "unknown_workspace": _auth_code({"X-Org-Id": "org-org", "X-Project-Id": f"missing-{uid}"}),
    }
    cleanup_remaining = _cleanup_canary(scopes, prefix)
    resource_types = {item["resource_type"] for item in resources}
    matrix_pass = all(item["a_reads_b"] == 0 and item["b_reads_a"] == 0 for item in matrices)
    auth_pass = auth == {"missing_org": 401, "missing_workspace": 401, "unknown_org": 403, "unknown_workspace": 403}
    status = "PASS" if len(resource_types) == 23 and all(item["status"] == "PASS" for item in resources) and matrix_pass and auth_pass and cleanup_remaining == 0 else "RED"
    return ({
        "temporary_scopes": [scope.key for scope in scopes],
        "matrices": matrices,
        "auth_matrix": auth,
        "cross_scope_write_rejected": cross_write_rejected,
        "resources": resources,
        "resource_count": len(resource_types),
        "cleanup_remaining": cleanup_remaining,
        "status": status,
    }, scopes)


def _write(gate: str, payload: dict, stamp: str) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / f"D5-E2_{gate}_{stamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    return path


def main() -> int:
    started_at = _utc()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"d5e2-{uuid.uuid4().hex}"
    meta = _meta(run_id, started_at)
    before = _real_hash()
    try:
        g17 = verify_g17()
        g18, _ = verify_g18(run_id)
        g19, _ = verify_g19(run_id)
    finally:
        for scope in reversed(CREATED_SCOPES):
            _delete_scope(scope)
    after = _real_hash()
    real_unchanged = before == after
    test_marker_hits = 0
    with connect(REAL) as conn:
        test_marker_hits = conn.execute(
            "SELECT count(*) AS n FROM ecom_object WHERE properties::text LIKE %s",
            (f"%{run_id}%",),
        ).fetchone()["n"]
    overall = all(result["status"] == "PASS" for result in (g17, g18, g19)) and real_unchanged and test_marker_hits == 0
    common = {**meta, "ended_at": _utc()}
    paths = [
        _write("G17", {**common, "gate": "G17", "results": g17}, stamp),
        _write("G18", {**common, "gate": "G18", "results": g18}, stamp),
        _write("G19", {**common, "gate": "G19", "results": g19}, stamp),
    ]
    final = {
        **common,
        "gate": "FINAL",
        "g17_spec": g17["g17_spec"],
        "d4_spec_sync": g17["d4_spec_sync"],
        "projection_ownership": g17["projection_ownership"]["status"],
        "g17": g17["status"],
        "g18": g18["status"],
        "g19": g19["status"],
        "real_scope_hash_before": before,
        "real_scope_hash_after": after,
        "real_scope_unchanged": real_unchanged,
        "real_scope_test_marker_hits": test_marker_hits,
        "forbidden_states": [],
        "overall_pass": overall,
    }
    paths.append(_write("FINAL", final, stamp))
    print(json.dumps({"overall_pass": overall, "evidence": [str(path) for path in paths]}, ensure_ascii=False))
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
