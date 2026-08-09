"""O1-D canonical alias migration with a versioned, reversible sidecar."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from aos_api.db import connect
from aos_api.ecom_projector import PROJECTOR_ACTOR, project_pending
from aos_api.tenant_scope import TenantScope


class AliasClassification(StrEnum):
    COPY = "COPY"
    ALREADY_EQUAL = "ALREADY_EQUAL"
    HASH_CONFLICT = "HASH_CONFLICT"
    UNRESOLVED = "UNRESOLVED"


def deterministic_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def canonical_external_id(platform: str, shop_or_marketplace_id: str, source_pk: str) -> str:
    platform = platform.strip()
    shop_or_marketplace_id = shop_or_marketplace_id.strip()
    source_pk = source_pk.strip()
    if not platform or not shop_or_marketplace_id or not source_pk:
        raise ValueError("canonical identity scope and source key are required")
    prefix = f"{platform}:{shop_or_marketplace_id}:"
    if source_pk.startswith(prefix):
        return source_pk
    if re.fullmatch(r"[^:]+:[^:]+:.+", source_pk):
        raise ValueError("canonical identity belongs to another platform or shop scope")
    return prefix + source_pk


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        value = value.astimezone(timezone.utc).isoformat()
    return str(value)


def build_projection_payload(authority: dict[str, Any]) -> dict[str, Any]:
    properties = dict(authority.get("properties") or {})
    properties.update(dict(authority.get("derived_payload") or {}))
    identity = {
        "orgId": authority["org_id"],
        "workspaceId": authority["workspace_id"],
        "platform": authority["platform"],
        "shopOrMarketplaceId": authority["shop_or_marketplace_id"],
        "externalId": authority["external_id"],
    }
    record = {
        "identity": identity,
        "objectType": authority["object_type"],
        "sourceUpdatedAt": _iso(authority["source_updated_at"]),
        "sourceTimezone": authority["source_timezone"],
        "status": {
            "canonical": authority["canonical_status"],
            "rawStatus": authority["raw_status"],
            "unknown": False,
        },
        "isDeleted": False,
        "schemaVersion": int(authority["schema_version"]),
        "properties": properties,
    }
    return {
        "schemaVersion": 1,
        "entityKind": "object",
        "changeKind": "objects_written",
        "objectType": authority["object_type"],
        "identity": identity,
        "record": record,
    }


def projected_properties(payload: dict[str, Any]) -> dict[str, Any]:
    record = payload["record"]
    props = dict(record["properties"])
    props["_sourceIdentity"] = record["identity"]
    props["_sourceUpdatedAt"] = record["sourceUpdatedAt"]
    props["_schemaVersion"] = record["schemaVersion"]
    return props


def classify_alias(
    canonical_props: dict[str, Any] | None,
    expected_props: dict[str, Any] | None,
) -> AliasClassification:
    if expected_props is None:
        return AliasClassification.UNRESOLVED
    if canonical_props is None:
        return AliasClassification.COPY
    if deterministic_hash(canonical_props) == deterministic_hash(expected_props):
        return AliasClassification.ALREADY_EQUAL
    return AliasClassification.HASH_CONFLICT


@dataclass(frozen=True)
class AliasEntry:
    alias_entry_id: str
    old_pk: str
    object_type: str
    legacy_object_id: str
    target_external_id: str
    legacy_props: dict[str, Any]
    expected_props: dict[str, Any] | None
    authority: dict[str, Any] | None
    classification: AliasClassification

    def manifest_row(self) -> dict[str, Any]:
        return {
            "aliasEntryId": self.alias_entry_id,
            "oldPk": self.old_pk,
            "objectType": self.object_type,
            "legacyObjectId": self.legacy_object_id,
            "targetCanonicalId": self.target_external_id,
            "legacyPropsHash": deterministic_hash(self.legacy_props),
            "canonicalPropsHash": (
                deterministic_hash(self.expected_props) if self.expected_props is not None else None
            ),
            "classification": self.classification.value,
            "state": "inventoried",
            "sourcePlatform": (self.authority or {}).get("platform"),
            "sourceShopId": (self.authority or {}).get("shop_or_marketplace_id"),
        }


def inventory(scope: TenantScope) -> list[AliasEntry]:
    with connect(scope) as conn:
        rows = conn.execute(
            """
            SELECT o.object_type,o.object_id AS legacy_object_id,o.props AS legacy_props,
                   e.org_id,e.workspace_id,e.platform,e.shop_or_marketplace_id,
                   e.object_type AS authority_object_type,e.external_id,e.properties,
                   e.derived_payload,e.source_updated_at,e.source_timezone,
                   e.canonical_status,e.raw_status,e.schema_version,
                   c.props AS canonical_props
              FROM obj_instance o
              LEFT JOIN ecom_object e
                ON e.org_id=o.org_id AND e.workspace_id=o.project_id
               AND e.object_type=o.object_type
               AND e.external_id=e.platform || ':' || e.shop_or_marketplace_id || ':' || o.object_id
               AND e.deleted_at IS NULL
              LEFT JOIN obj_instance c
                ON c.org_id=o.org_id AND c.project_id=o.project_id
               AND c.object_type=o.object_type AND c.object_id=e.external_id
             WHERE o.org_id=%s AND o.project_id=%s
               AND o.object_type IN (
                 'Shop','Product','ProductSku','Category','Order','OrderLine','Shipment',
                 'CustomerLite','Weapp','SystemConfig','ProductReview','Payment'
               )
               AND o.object_id !~ '^[^:]+:[^:]+:.+$'
             ORDER BY o.object_type,o.object_id
            """,
            scope.key,
        ).fetchall()
    entries: list[AliasEntry] = []
    for row in rows:
        authority = None
        expected = None
        target = ""
        if row["external_id"] is not None:
            authority = {
                "org_id": row["org_id"],
                "workspace_id": row["workspace_id"],
                "platform": row["platform"],
                "shop_or_marketplace_id": row["shop_or_marketplace_id"],
                "object_type": row["authority_object_type"],
                "external_id": row["external_id"],
                "properties": row["properties"],
                "derived_payload": row["derived_payload"],
                "source_updated_at": row["source_updated_at"],
                "source_timezone": row["source_timezone"],
                "canonical_status": row["canonical_status"],
                "raw_status": row["raw_status"],
                "schema_version": row["schema_version"],
            }
            payload = build_projection_payload(authority)
            expected = projected_properties(payload)
            target = str(row["external_id"])
        old_pk = "|".join((*scope.key, row["object_type"], row["legacy_object_id"]))
        alias_id = deterministic_hash({"oldPk": old_pk, "target": target or None})
        entries.append(
            AliasEntry(
                alias_entry_id=alias_id,
                old_pk=old_pk,
                object_type=row["object_type"],
                legacy_object_id=row["legacy_object_id"],
                target_external_id=target,
                legacy_props=dict(row["legacy_props"]),
                expected_props=expected,
                authority=authority,
                classification=classify_alias(
                    dict(row["canonical_props"]) if row["canonical_props"] is not None else None,
                    expected,
                ),
            )
        )
    return entries


def manifest(scope: TenantScope, entries: list[AliasEntry], *, run_id: uuid.UUID) -> dict[str, Any]:
    rows = [entry.manifest_row() for entry in entries]
    counts = {classification.value: 0 for classification in AliasClassification}
    for entry in entries:
        counts[entry.classification.value] += 1
    body = {
        "schemaVersion": 1,
        "runId": str(run_id),
        "scope": {"orgId": scope.org_id, "workspaceId": scope.project_id},
        "counts": counts,
        "rows": rows,
    }
    body["manifestHash"] = deterministic_hash(body)
    return body


def _outbox_payload(entry: AliasEntry) -> tuple[dict[str, Any], str]:
    if entry.authority is None:
        raise RuntimeError("ALIAS_AUTHORITY_UNRESOLVED")
    payload = build_projection_payload(entry.authority)
    payload_hash = deterministic_hash(payload)
    return payload, payload_hash


def apply_manifest(
    scope: TenantScope,
    entries: list[AliasEntry],
    *,
    run_id: uuid.UUID,
    evidence_ref: str,
) -> dict[str, int]:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", evidence_ref):
        raise ValueError("evidence_ref must be a sha256 reference")
    blocked = [e for e in entries if e.classification in {AliasClassification.HASH_CONFLICT, AliasClassification.UNRESOLVED}]
    if blocked:
        raise RuntimeError(f"ALIAS_MANIFEST_BLOCKED:{len(blocked)}")
    with connect(scope) as conn:
        next_revision = int(
            conn.execute(
                "SELECT COALESCE(MAX(input_revision),0) AS max_revision FROM projection_outbox "
                "WHERE org_id=%s AND project_id=%s AND event_source='authoritative_store'",
                scope.key,
            ).fetchone()["max_revision"]
        )
        for offset, entry in enumerate(entries, start=1):
            source = entry.authority or {}
            state = "verified" if entry.classification is AliasClassification.ALREADY_EQUAL else "inventoried"
            conn.execute(
                """
                INSERT INTO ecom_alias_migration(
                  org_id,project_id,workspace_id,alias_entry_id,old_pk,target_external_id,
                  target_object_type,props_hash,source_platform,source_shop_id,
                  conflict_category,conflict_details,disposition,run_id,evidence_ref,
                  canonical_props_hash,classification,state,legacy_snapshot,verification_cycle
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s::jsonb,0)
                ON CONFLICT (org_id,project_id,run_id,alias_entry_id) DO UPDATE SET
                  evidence_ref=EXCLUDED.evidence_ref,
                  canonical_props_hash=EXCLUDED.canonical_props_hash,
                  classification=EXCLUDED.classification,state=EXCLUDED.state,
                  legacy_snapshot=EXCLUDED.legacy_snapshot,updated_at=now()
                """,
                (
                    scope.org_id, scope.project_id, scope.project_id, entry.alias_entry_id,
                    entry.old_pk, entry.target_external_id, entry.object_type,
                    deterministic_hash(entry.legacy_props), source.get("platform", ""),
                    source.get("shop_or_marketplace_id", ""),
                    None, json.dumps({}), "verified" if state == "verified" else "pending",
                    str(run_id), evidence_ref,
                    deterministic_hash(entry.expected_props) if entry.expected_props is not None else None,
                    entry.classification.value, state,
                    json.dumps(entry.legacy_props, ensure_ascii=False),
                ),
            )
            if entry.classification is not AliasClassification.COPY:
                continue
            payload, payload_hash = _outbox_payload(entry)
            event_key = deterministic_hash({"runId": str(run_id), "aliasEntryId": entry.alias_entry_id})
            conn.execute(
                """
                INSERT INTO projection_outbox(
                  org_id,project_id,workspace_id,input_revision,change_kind,object_type,
                  external_id,link_type,source_external_id,target_external_id,platform,
                  shop_or_marketplace_id,payload,event_key,payload_hash,event_source,
                  authority_tx_id,projected,created_at
                ) VALUES (%s,%s,%s,%s,'objects_written',%s,%s,NULL,NULL,NULL,%s,%s,
                          %s::jsonb,%s,%s,'authoritative_store',%s,FALSE,now())
                ON CONFLICT DO NOTHING
                """,
                (
                    scope.org_id, scope.project_id, scope.project_id, next_revision + offset,
                    entry.object_type, entry.target_external_id, source["platform"],
                    source["shop_or_marketplace_id"], json.dumps(payload, ensure_ascii=False),
                    event_key, payload_hash, deterministic_hash({"runId": str(run_id)}),
                ),
            )
    projected = project_pending(scope, limit=5000)["projected"]
    verified = verify_manifest(scope, run_id=run_id, increment_cycle=False)
    return {"projected": projected, **verified}


def verify_manifest(
    scope: TenantScope,
    *,
    run_id: uuid.UUID,
    increment_cycle: bool = True,
) -> dict[str, int]:
    verified = conflicts = 0
    with connect(scope) as conn:
        rows = conn.execute(
            "SELECT * FROM ecom_alias_migration WHERE org_id=%s AND project_id=%s AND run_id=%s ORDER BY alias_entry_id",
            (*scope.key, str(run_id)),
        ).fetchall()
        for row in rows:
            canonical = conn.execute(
                "SELECT props FROM obj_instance WHERE org_id=%s AND project_id=%s AND object_type=%s AND object_id=%s",
                (*scope.key, row["target_object_type"], row["target_external_id"]),
            ).fetchone()
            actual_hash = deterministic_hash(dict(canonical["props"])) if canonical is not None else None
            if actual_hash != row["canonical_props_hash"]:
                conflicts += 1
                conn.execute(
                    "UPDATE ecom_alias_migration SET state='quarantined',disposition='conflict_isolated',"
                    "conflict_category='HASH_CONFLICT',conflict_details=%s::jsonb,updated_at=now() "
                    "WHERE org_id=%s AND project_id=%s AND alias_entry_id=%s",
                    (json.dumps({"actualHash": actual_hash}), *scope.key, row["alias_entry_id"]),
                )
                continue
            verified += 1
            cycle_sql = ",verification_cycle=verification_cycle+1" if increment_cycle else ""
            conn.execute(
                f"UPDATE ecom_alias_migration SET state='verified',disposition='verified',verified_at=now(){cycle_sql},updated_at=now() "
                "WHERE org_id=%s AND project_id=%s AND alias_entry_id=%s",
                (*scope.key, row["alias_entry_id"]),
            )
    if conflicts:
        raise RuntimeError(f"ALIAS_HASH_CONFLICT:{conflicts}")
    return {"verified": verified, "conflicts": conflicts}


def approve_cleanup(scope: TenantScope, *, run_id: uuid.UUID, actor: str) -> int:
    with connect(scope) as conn:
        blocked = conn.execute(
            "SELECT COUNT(*) AS count FROM ecom_alias_migration WHERE org_id=%s AND project_id=%s AND run_id=%s "
            "AND (state<>'verified' OR verification_cycle<2)",
            (*scope.key, str(run_id)),
        ).fetchone()["count"]
        if blocked:
            raise RuntimeError(f"ALIAS_CLEANUP_NOT_READY:{blocked}")
        result = conn.execute(
            "UPDATE ecom_alias_migration SET state='cleanup_approved',cleanup_approved_by=%s,"
            "cleanup_approved_at=now(),updated_at=now() WHERE org_id=%s AND project_id=%s AND run_id=%s",
            (actor, *scope.key, str(run_id)),
        )
        return result.rowcount


def cleanup(scope: TenantScope, *, run_id: uuid.UUID) -> int:
    cleaned = 0
    with connect(scope) as conn:
        conn.execute("SELECT set_config('aos.projection_actor', %s, true)", (PROJECTOR_ACTOR,))
        rows = conn.execute(
            "SELECT * FROM ecom_alias_migration WHERE org_id=%s AND project_id=%s AND run_id=%s "
            "AND state='cleanup_approved' ORDER BY alias_entry_id FOR UPDATE",
            (*scope.key, str(run_id)),
        ).fetchall()
        for row in rows:
            legacy = conn.execute(
                "SELECT props FROM obj_instance WHERE org_id=%s AND project_id=%s AND object_type=%s AND object_id=%s FOR UPDATE",
                (*scope.key, row["target_object_type"], row["old_pk"].rsplit("|", 1)[-1]),
            ).fetchone()
            if legacy is None:
                raise RuntimeError("ALIAS_LEGACY_ROW_MISSING")
            if deterministic_hash(dict(legacy["props"])) != row["props_hash"]:
                raise RuntimeError("ALIAS_LEGACY_SNAPSHOT_DRIFT")
            conn.execute(
                "DELETE FROM obj_instance WHERE org_id=%s AND project_id=%s AND object_type=%s AND object_id=%s",
                (*scope.key, row["target_object_type"], row["old_pk"].rsplit("|", 1)[-1]),
            )
            conn.execute(
                "UPDATE ecom_alias_migration SET state='cleaned',disposition='cleaned',cleaned_at=now(),updated_at=now() "
                "WHERE org_id=%s AND project_id=%s AND alias_entry_id=%s",
                (*scope.key, row["alias_entry_id"]),
            )
            cleaned += 1
    return cleaned


def restore_rehearsal(scope: TenantScope, *, run_id: uuid.UUID) -> int:
    """Exercise row restoration in one transaction and always roll it back."""
    restored = 0
    with connect(scope) as conn:
        conn.execute("SELECT set_config('aos.projection_actor', %s, true)", (PROJECTOR_ACTOR,))
        rows = conn.execute(
            "SELECT * FROM ecom_alias_migration WHERE org_id=%s AND project_id=%s AND run_id=%s "
            "AND state='cleaned' ORDER BY alias_entry_id",
            (*scope.key, str(run_id)),
        ).fetchall()
        for row in rows:
            legacy_id = row["old_pk"].rsplit("|", 1)[-1]
            conn.execute(
                "INSERT INTO obj_instance(org_id,project_id,object_type,object_id,props) VALUES (%s,%s,%s,%s,%s::jsonb)",
                (*scope.key, row["target_object_type"], legacy_id, json.dumps(row["legacy_snapshot"], ensure_ascii=False)),
            )
            restored += 1
        for row in rows:
            legacy_id = row["old_pk"].rsplit("|", 1)[-1]
            restored_row = conn.execute(
                "SELECT props FROM obj_instance WHERE org_id=%s AND project_id=%s AND object_type=%s AND object_id=%s",
                (*scope.key, row["target_object_type"], legacy_id),
            ).fetchone()
            if restored_row is None or deterministic_hash(dict(restored_row["props"])) != row["props_hash"]:
                raise RuntimeError("ALIAS_RESTORE_HASH_MISMATCH")
        conn.rollback()
    return restored


def seal_report(scope: TenantScope, *, run_id: uuid.UUID) -> dict[str, Any]:
    """Build the final read-only gate report after cleanup."""
    core_types = (
        "Shop", "Product", "ProductSku", "Category", "Order", "OrderLine",
        "Shipment", "CustomerLite", "Weapp", "SystemConfig", "ProductReview", "Payment",
    )
    with connect(scope) as conn:
        sidecar = conn.execute(
            "SELECT state,classification,MIN(verification_cycle) AS min_cycle,COUNT(*) AS count "
            "FROM ecom_alias_migration WHERE org_id=%s AND project_id=%s AND run_id=%s "
            "GROUP BY state,classification ORDER BY state,classification",
            (*scope.key, str(run_id)),
        ).fetchall()
        projected_rows = conn.execute(
            """
            SELECT e.org_id,e.workspace_id,e.platform,e.shop_or_marketplace_id,e.object_type,
                   e.external_id,e.properties,e.derived_payload,e.source_updated_at,e.source_timezone,
                   e.canonical_status,e.raw_status,e.schema_version,o.props
              FROM ecom_object e
              LEFT JOIN obj_instance o
                ON o.org_id=e.org_id AND o.project_id=e.workspace_id
               AND o.object_type=e.object_type AND o.object_id=e.external_id
             WHERE e.org_id=%s AND e.workspace_id=%s AND e.deleted_at IS NULL
             ORDER BY e.object_type,e.external_id
            """,
            scope.key,
        ).fetchall()
        mismatches = 0
        canonical_material: list[dict[str, Any]] = []
        for row in projected_rows:
            authority = {key: row[key] for key in (
                "org_id", "workspace_id", "platform", "shop_or_marketplace_id", "object_type",
                "external_id", "properties", "derived_payload", "source_updated_at", "source_timezone",
                "canonical_status", "raw_status", "schema_version",
            )}
            expected = projected_properties(build_projection_payload(authority))
            actual = dict(row["props"]) if row["props"] is not None else None
            if actual is None or deterministic_hash(actual) != deterministic_hash(expected):
                mismatches += 1
            canonical_material.append({"objectType": row["object_type"], "objectId": row["external_id"], "props": actual})
        bare_count = conn.execute(
            "SELECT COUNT(*) AS count FROM obj_instance WHERE org_id=%s AND project_id=%s "
            "AND object_type=ANY(%s) AND object_id !~ '^[^:]+:[^:]+:.+$'",
            (*scope.key, list(core_types)),
        ).fetchone()["count"]
        bare_edges = conn.execute(
            "SELECT COUNT(*) AS count FROM graph_edge WHERE org_id=%s AND project_id=%s "
            "AND (src_id !~ '^[^:]+:[^:]+:.+$' OR dst_id !~ '^[^:]+:[^:]+:.+$')",
            scope.key,
        ).fetchone()["count"]
        pending = conn.execute(
            "SELECT COUNT(*) AS count FROM projection_outbox WHERE org_id=%s AND project_id=%s AND projected=FALSE",
            scope.key,
        ).fetchone()["count"]
        conn.execute("SET LOCAL ROLE aos_runtime")
        conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
        conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
        foreign_sidecar = conn.execute("SELECT COUNT(*) AS count FROM ecom_alias_migration").fetchone()["count"]
        foreign_objects = conn.execute(
            "SELECT COUNT(*) AS count FROM obj_instance WHERE object_type=ANY(%s) AND object_id ~ '^[^:]+:[^:]+:.+$'",
            (list(core_types),),
        ).fetchone()["count"]
    sidecar_total = sum(int(row["count"]) for row in sidecar)
    sidecar_cleaned = sum(int(row["count"]) for row in sidecar if row["state"] == "cleaned")
    report = {
        "schemaVersion": 1,
        "gate": "O1-D",
        "runId": str(run_id),
        "scope": {"orgId": scope.org_id, "workspaceId": scope.project_id},
        "sidecar": [dict(row) for row in sidecar],
        "authorityObjectCount": len(projected_rows),
        "canonicalProjectionCount": len(canonical_material) - mismatches,
        "canonicalMismatchCount": mismatches,
        "canonicalSetHash": deterministic_hash(canonical_material),
        "bareObjectIdCount": int(bare_count),
        "bareGraphEndpointCount": int(bare_edges),
        "pendingOutboxCount": int(pending),
        "crossTenantCanary": {
            "scope": "dev-org/dev-project",
            "visibleAliasRows": int(foreign_sidecar),
            "visibleCanonicalCoreObjects": int(foreign_objects),
        },
    }
    report["status"] = "GREEN" if (
        len(projected_rows) > 0 and mismatches == 0 and bare_count == 0 and bare_edges == 0
        and pending == 0 and foreign_sidecar == 0 and foreign_objects == 0
        and sidecar_total > 0 and sidecar_cleaned == sidecar_total
    ) else "RED"
    report["reportHash"] = deterministic_hash(report)
    return report
