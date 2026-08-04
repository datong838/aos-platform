"""TI-0E plan compiler; it never connects to a database or emits executable SQL."""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from typing import Any

from aos_api.tenant_resource_registry import (
    load_tenant_resource_registry,
    validate_registry,
)

TEST_TYPES = (
    "SCHEMA",
    "STORE",
    "CROSS_TENANT_NEGATIVE",
    "RECONCILIATION",
    "QIYUE_BASELINE",
    "ROLLBACK",
)

ROLLBACK_POINTS = (
    {
        "stage": "E1_EXPAND",
        "allowedAction": "add_nullable_structure_only",
        "rollback": "drop_or_ignore_new_nullable_structure",
        "authorization": "TI_WAVE_E1_APPROVAL_REQUIRED",
    },
    {
        "stage": "E2_DUAL_WRITE",
        "allowedAction": "dual_write_behind_feature_flag",
        "rollback": "disable_feature_flag",
        "authorization": "SEPARATE_APPROVAL_REQUIRED",
    },
    {
        "stage": "E3_BACKFILL",
        "allowedAction": "ledger_backed_evidence_only_assignment",
        "rollback": "restore_original_values_from_immutable_ledger",
        "authorization": "SEPARATE_APPROVAL_REQUIRED",
    },
    {
        "stage": "E4_VALIDATE",
        "allowedAction": "read_only_reconciliation",
        "rollback": "do_not_switch_reads",
        "authorization": "SEPARATE_APPROVAL_REQUIRED",
    },
    {
        "stage": "E5_READ_SWITCH",
        "allowedAction": "switch_scoped_read_path",
        "rollback": "switch_back_to_legacy_read_path",
        "authorization": "SEPARATE_APPROVAL_REQUIRED",
    },
    {
        "stage": "E6_RLS",
        "allowedAction": "enable_policy_after_observe_mode",
        "rollback": "disable_policy_keep_tenant_keys",
        "authorization": "SEPARATE_APPROVAL_REQUIRED",
    },
    {
        "stage": "E7_CONTRACT",
        "allowedAction": "not_null_fk_validate_and_legacy_contract",
        "rollback": "full_backup_restore_procedure_required",
        "authorization": "TI_6_APPROVAL_REQUIRED",
    },
)


def build_ti0e_artifacts(
    *,
    registry: dict[str, Any] | None = None,
    migration_ledger: dict[str, Any],
    non_postgres_inventory: dict[str, Any],
    source_hashes: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    data = registry or load_tenant_resource_registry()
    issues = validate_registry(data)
    if issues:
        raise ValueError(f"invalid tenant resource registry: {issues}")

    entries = {
        str(entry["name"]): entry for entry in data.get("resources", [])
    }
    ledger_entries = {
        str(entry["resource"]): entry
        for entry in migration_ledger.get("resources", [])
    }
    non_postgres_entries = {
        str(entry["name"]): entry
        for entry in non_postgres_inventory.get("resources", [])
    }
    ordered_groups: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    blocker_counts: Counter[str] = Counter()
    execution_plan = data["executionPlan"]
    for ordinal, group in enumerate(execution_plan["groups"], start=1):
        resources: list[dict[str, Any]] = []
        for name in group["resources"]:
            registry_entry = entries[name]
            ledger_entry = ledger_entries.get(name, {})
            non_postgres_entry = non_postgres_entries.get(name, {})
            blockers = list(ledger_entry.get("blockers") or [])
            if registry_entry["kind"] != "postgres_table":
                probe_status = str(non_postgres_entry.get("status") or "UNPROBED")
                if probe_status != "PROBED":
                    blockers.append(f"NON_POSTGRES_{probe_status}")
            blockers = sorted(set(blockers))
            status = (
                "BLOCKED_BEFORE_E3" if blockers else "READY_FOR_E1_REVIEW"
            )
            status_counts[status] += 1
            blocker_counts.update(blockers)
            resources.append(
                {
                    "name": name,
                    "kind": registry_entry["kind"],
                    "classification": registry_entry["classification"],
                    "currentState": registry_entry.get("currentState", "N/A"),
                    "targetTenantColumns": registry_entry.get(
                        "targetTenantColumns", []
                    ),
                    "ti0dDiscoveryWave": registry_entry["migrationWave"],
                    "rowCount": ledger_entry.get("rowCount"),
                    "blockers": blockers,
                    "executionStatus": status,
                }
            )
        ordered_groups.append(
            {
                "ordinal": ordinal,
                "id": group["id"],
                "wave": group["wave"],
                "worker": group["worker"],
                "dependsOn": list(group.get("dependsOn") or []),
                "resources": resources,
            }
        )

    migration_order = {
        "stage": "TI-0E",
        "mode": "PLAN_ONLY",
        "authorization": execution_plan["authorization"],
        "sourceHashes": dict(sorted((source_hashes or {}).items())),
        "resourceCount": len(entries),
        "groupCount": len(ordered_groups),
        "statusCounts": dict(sorted(status_counts.items())),
        "blockerCounts": dict(sorted(blocker_counts.items())),
        "groups": ordered_groups,
    }
    test_matrix = {
        "stage": "TI-0E",
        "mode": "PLAN_ONLY",
        "waves": [
            {
                "wave": wave,
                "tests": [
                    {
                        "id": f"{wave}-{index:02d}",
                        "type": test_type,
                        "required": True,
                    }
                    for index, test_type in enumerate(TEST_TYPES, start=1)
                ],
            }
            for wave in ("TI-1", "TI-2", "TI-3", "TI-4", "TI-5")
        ],
    }
    rollback_points = {
        "stage": "TI-0E",
        "mode": "PLAN_ONLY",
        "points": [dict(point) for point in ROLLBACK_POINTS],
        "automaticExecutionAllowed": False,
    }
    return {
        "ti0e-migration-order.json": migration_order,
        "ti0e-test-matrix.json": test_matrix,
        "ti0e-rollback-points.json": rollback_points,
    }


def content_sha256(content: bytes) -> str:
    return sha256(content).hexdigest()
