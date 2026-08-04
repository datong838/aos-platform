"""TI-1 E3-0 read-only source snapshot and baseline reconciliation."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from aos_api.tenant_dual_write import stable_key_hash

E1_FROZEN_BASELINE = {
    "authzTupleRows": 9,
    "authzTupleUnassignedRows": 9,
    "metaMembershipOrphans": 57,
    "twaWsMemberOrphans": 4,
    "twaAuditOrphans": 3,
    "globalUnattributedRows": 993,
    "qiyueBusinessRows": 0,
    "qiyueControlPlaneRows": 5,
}


@dataclass(frozen=True)
class ResourceSpec:
    name: str
    key_columns: tuple[str, ...]
    tenant_columns: tuple[str, ...]
    parent_table: str | None = None
    parent_source_columns: tuple[str, ...] = ()
    parent_target_columns: tuple[str, ...] = ()


RESOURCE_SPECS = (
    ResourceSpec(
        name="authz_tuple",
        key_columns=("user_key", "relation", "object_key"),
        tenant_columns=("org_id", "project_id"),
    ),
    ResourceSpec(
        name="meta_membership",
        key_columns=("org_id", "project_id", "subject"),
        tenant_columns=("org_id", "project_id"),
        parent_table="meta_workspace",
        parent_source_columns=("org_id", "project_id"),
        parent_target_columns=("org_id", "project_id"),
    ),
    ResourceSpec(
        name="twa_ws_member",
        key_columns=("org_id", "project_id", "subject"),
        tenant_columns=("org_id", "project_id"),
        parent_table="twa_workspace",
        parent_source_columns=("org_id", "project_id"),
        parent_target_columns=("org_id", "project_id"),
    ),
    ResourceSpec(
        name="twa_audit",
        key_columns=("id",),
        tenant_columns=("org_id", "project_id"),
        parent_table="twa_workspace",
        parent_source_columns=("org_id", "project_id"),
        parent_target_columns=("org_id", "project_id"),
    ),
)


def environment_fingerprint(dsn: str) -> str:
    """Identify the database without including credentials in hash input."""
    values = conninfo_to_dict(dsn)
    return stable_key_hash(
        str(values.get("host") or ""),
        str(values.get("port") or ""),
        str(values.get("dbname") or ""),
    )


def read_e3_source_snapshot(
    conn: Any,
    *,
    postgres_precheck: Mapping[str, Any],
    environment_fingerprint: str,
    target_org_id: str,
    target_project_id: str,
) -> dict[str, Any]:
    resources: dict[str, Any] = {}
    for spec in RESOURCE_SPECS:
        rows = _read_columns(conn, spec.name, _selected_columns(spec))
        parent_rows: Sequence[Mapping[str, Any]] = ()
        if spec.parent_table:
            parent_rows = _read_columns(
                conn, spec.parent_table, spec.parent_target_columns
            )
        resources[spec.name] = build_resource_snapshot(
            rows, spec=spec, parent_rows=parent_rows
        )

    table_reports = list(postgres_precheck.get("tables") or [])
    target_business = sum(
        int(item.get("targetTenantRowCount") or 0)
        for item in table_reports
        if item.get("classification") == "TENANT_OWNED"
        and item.get("baselineScope") == "BUSINESS_DATA"
    )
    target_control = sum(
        int(item.get("targetTenantRowCount") or 0)
        for item in table_reports
        if item.get("classification") == "TENANT_OWNED"
        and item.get("baselineScope") == "CONTROL_PLANE"
    )
    unattributed = sum(
        int(item.get("unattributedRows") or 0)
        for item in table_reports
        if item.get("classification") == "TENANT_OWNED"
    )
    total_rows = sum(int(item.get("rowCount") or 0) for item in table_reports)
    revision_row = conn.execute("SELECT version_num FROM alembic_version").fetchone()

    return {
        "stage": "TI-1-E3-0",
        "mode": "READ_ONLY_REBASELINE",
        "scanOk": bool(postgres_precheck.get("scanOk")),
        "environmentFingerprint": environment_fingerprint,
        "alembicRevision": str((revision_row or {}).get("version_num") or ""),
        "targetTenantHash": stable_key_hash(target_org_id, target_project_id),
        "global": {
            "postgresTableCount": int(postgres_precheck.get("tableCount") or 0),
            "postgresRowCount": total_rows,
            "unattributedTenantOwnedRowCount": unattributed,
            "targetBusinessRowCount": target_business,
            "targetControlPlaneRowCount": target_control,
        },
        "resources": resources,
        "contentReturned": False,
    }


def build_resource_snapshot(
    rows: Sequence[Mapping[str, Any]],
    *,
    spec: ResourceSpec,
    parent_rows: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    parent_keys = {
        tuple(_normalized(row.get(column)) for column in spec.parent_target_columns)
        for row in parent_rows
    }
    key_fingerprints: list[str] = []
    unassigned_fingerprints: list[str] = []
    orphan_fingerprints: list[str] = []
    content_fingerprints: list[str] = []
    scope_counts: dict[str, int] = {}

    for row in rows:
        key_values = tuple(_normalized(row.get(column)) for column in spec.key_columns)
        key_fingerprint = stable_key_hash(spec.name, *key_values)
        key_fingerprints.append(key_fingerprint)
        tenant_values = tuple(
            _normalized(row.get(column)) for column in spec.tenant_columns
        )
        if not tenant_values or any(not value for value in tenant_values):
            unassigned_fingerprints.append(key_fingerprint)
        else:
            scope_hash = stable_key_hash(*tenant_values)
            scope_counts[scope_hash] = scope_counts.get(scope_hash, 0) + 1
        content_fingerprints.append(
            stable_key_hash(spec.name, *key_values, *tenant_values)
        )
        if spec.parent_table:
            source_key = tuple(
                _normalized(row.get(column))
                for column in spec.parent_source_columns
            )
            if all(source_key) and source_key not in parent_keys:
                orphan_fingerprints.append(key_fingerprint)

    sorted_keys = sorted(key_fingerprints)
    sorted_unassigned = sorted(unassigned_fingerprints)
    sorted_orphans = sorted(orphan_fingerprints)
    sorted_content = sorted(content_fingerprints)
    return {
        "resource": spec.name,
        "rowCount": len(rows),
        "unassignedTenantRowCount": len(sorted_unassigned),
        "orphanRowCount": len(sorted_orphans),
        "keySetHash": stable_key_hash(*sorted_keys),
        "contentSetHash": stable_key_hash(*sorted_content),
        "unassignedKeySetHash": stable_key_hash(*sorted_unassigned),
        "orphanKeySetHash": stable_key_hash(*sorted_orphans),
        "unassignedKeyFingerprints": sorted_unassigned,
        "orphanKeyFingerprints": sorted_orphans,
        "scopeGroupCounts": [
            {"scopeHash": scope_hash, "rowCount": scope_counts[scope_hash]}
            for scope_hash in sorted(scope_counts)
        ],
        "rawKeysReturned": False,
        "rawPayloadReturned": False,
    }


def build_e1_reconciliation(
    source_snapshot: Mapping[str, Any],
    *,
    identity_evidence_available: bool = False,
) -> dict[str, Any]:
    resources = source_snapshot.get("resources") or {}
    global_summary = source_snapshot.get("global") or {}
    current = {
        "authzTupleRows": _resource_metric(resources, "authz_tuple", "rowCount"),
        "authzTupleUnassignedRows": _resource_metric(
            resources, "authz_tuple", "unassignedTenantRowCount"
        ),
        "metaMembershipOrphans": _resource_metric(
            resources, "meta_membership", "orphanRowCount"
        ),
        "twaWsMemberOrphans": _resource_metric(
            resources, "twa_ws_member", "orphanRowCount"
        ),
        "twaAuditOrphans": _resource_metric(
            resources, "twa_audit", "orphanRowCount"
        ),
        "globalUnattributedRows": int(
            global_summary.get("unattributedTenantOwnedRowCount") or 0
        ),
        "qiyueBusinessRows": int(global_summary.get("targetBusinessRowCount") or 0),
        "qiyueControlPlaneRows": int(
            global_summary.get("targetControlPlaneRowCount") or 0
        ),
    }
    metrics = []
    for name, baseline_value in E1_FROZEN_BASELINE.items():
        current_value = current[name]
        delta = current_value - baseline_value
        metrics.append(
            {
                "metric": name,
                "baseline": baseline_value,
                "current": current_value,
                "delta": delta,
                "status": "MATCH" if delta == 0 else "UNEXPLAINED_DRIFT",
            }
        )
    unresolved = [item for item in metrics if item["status"] != "MATCH"]
    identity_blocked = not identity_evidence_available
    gate = (
        "GREEN"
        if not unresolved and not identity_blocked and source_snapshot.get("scanOk")
        else "BLOCKED"
    )
    blockers = []
    if unresolved:
        blockers.append("UNEXPLAINED_BASELINE_DRIFT")
    if identity_blocked:
        blockers.append("E1_ROW_IDENTITY_EVIDENCE_UNAVAILABLE")
    if not source_snapshot.get("scanOk"):
        blockers.append("SOURCE_SNAPSHOT_INCOMPLETE")
    return {
        "stage": "TI-1-E3-0",
        "mode": "READ_ONLY_BASELINE_RECONCILIATION",
        "gate": gate,
        "blockers": blockers,
        "identityEvidenceAvailable": identity_evidence_available,
        "metrics": metrics,
        "nextAuthorizedStage": "E3-1" if gate == "GREEN" else None,
        "historyMutated": False,
    }


def _read_columns(
    conn: Any, table: str, columns: Sequence[str]
) -> Sequence[Mapping[str, Any]]:
    selected = sql.SQL(", ").join(sql.Identifier(column) for column in columns)
    query = sql.SQL("SELECT {} FROM {} ORDER BY {}").format(
        selected,
        sql.Identifier(table),
        selected,
    )
    return conn.execute(query).fetchall()


def _selected_columns(spec: ResourceSpec) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*spec.key_columns, *spec.tenant_columns)))


def _normalized(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _resource_metric(
    resources: Mapping[str, Any], resource: str, metric: str
) -> int:
    return int((resources.get(resource) or {}).get(metric) or 0)
