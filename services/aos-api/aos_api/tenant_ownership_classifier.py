"""Fail-closed TI-1 E3 ownership classifier over redacted source snapshots."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.tenant_dual_write import stable_key_hash


def _canonical_hex(value: object) -> str:
    return canonical_sha256(value).removeprefix("sha256:")


def classify_source_snapshot(source_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    source_snapshot_hash = _canonical_hex(source_snapshot)
    decisions: list[dict[str, Any]] = []
    resources = source_snapshot.get("resources") or {}
    for resource in sorted(resources):
        snapshot = resources[resource] or {}
        pending: dict[str, tuple[str, str]] = {}
        for key_hash in snapshot.get("unassignedKeyFingerprints") or []:
            pending[str(key_hash)] = ("NO_A_GRADE_EVIDENCE", "C")
        for key_hash in snapshot.get("orphanKeyFingerprints") or []:
            pending[str(key_hash)] = ("ORPHAN_PARENT_UNVERIFIED", "B")
        for key_hash, (reason_code, evidence_grade) in sorted(pending.items()):
            evidence_hash = stable_key_hash(
                "TI-1-E3-2", resource, key_hash, reason_code, source_snapshot_hash
            )
            decisions.append(
                {
                    "resource": resource,
                    "keyHash": key_hash,
                    "decision": "QUARANTINE",
                    "evidenceGrade": evidence_grade,
                    "evidenceHash": evidence_hash,
                    "candidateCount": 0,
                    "targetScopeHash": None,
                    "beforeHash": stable_key_hash(
                        resource, key_hash, source_snapshot_hash
                    ),
                    "afterHash": None,
                    "reasonCode": reason_code,
                }
            )

    unique_keys = {(item["resource"], item["keyHash"]) for item in decisions}
    issues: list[str] = []
    if len(unique_keys) != len(decisions):
        issues.append("DUPLICATE_RECORD_DECISION")
    if any(item["targetScopeHash"] is not None for item in decisions):
        issues.append("QUARANTINE_HAS_TARGET_SCOPE")
    counts = {
        "ASSIGN": sum(item["decision"] == "ASSIGN" for item in decisions),
        "QUARANTINE": sum(
            item["decision"] == "QUARANTINE" for item in decisions
        ),
        "NO_ACTION": sum(item["decision"] == "NO_ACTION" for item in decisions),
        "BLOCKED": sum(item["decision"] == "BLOCKED" for item in decisions),
    }
    if len(decisions) != sum(counts.values()):
        issues.append("DECISION_CONSERVATION_FAILED")
    result = {
        "stage": "TI-1-E3-2",
        "mode": "FAIL_CLOSED_DRY_RUN",
        "sourceSnapshotHash": source_snapshot_hash,
        "historicalContinuity": "RISK_ACCEPTED_DISCONTINUITY",
        "gate": "GREEN" if not issues else "BLOCKED",
        "issues": issues,
        "totalDiscovered": len(decisions),
        "counts": counts,
        "decisions": decisions,
        "rawKeysReturned": False,
        "rawPayloadReturned": False,
    }
    result["decisionSummaryHash"] = _canonical_hex(result)
    return result
