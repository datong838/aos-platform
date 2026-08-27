from __future__ import annotations

from aos_api.tenant_e3_rebaseline import (
    E1_FROZEN_BASELINE,
    RESOURCE_SPECS,
    build_e1_reconciliation,
    build_resource_snapshot,
    environment_fingerprint,
)


def _source_snapshot(*, authz_rows: int = 9, scan_ok: bool = True) -> dict:
    return {
        "scanOk": scan_ok,
        "resources": {
            "authz_tuple": {
                "rowCount": authz_rows,
                "unassignedTenantRowCount": authz_rows,
            },
            "meta_membership": {"orphanRowCount": 57},
            "twa_ws_member": {"orphanRowCount": 4},
            "twa_audit": {"orphanRowCount": 3},
        },
        "global": {
            "unattributedTenantOwnedRowCount": 993,
            "targetBusinessRowCount": 0,
            "targetControlPlaneRowCount": 5,
        },
    }


def test_resource_snapshot_returns_hashes_without_raw_keys() -> None:
    spec = RESOURCE_SPECS[0]
    result = build_resource_snapshot(
        [
            {
                "user_key": "user:alice",
                "relation": "viewer",
                "object_key": "object:1",
                "org_id": None,
                "project_id": None,
            }
        ],
        spec=spec,
    )

    assert result["rowCount"] == 1
    assert result["unassignedTenantRowCount"] == 1
    assert result["rawKeysReturned"] is False
    assert result["rawPayloadReturned"] is False
    serialized = str(result)
    assert "user:alice" not in serialized
    assert "object:1" not in serialized


def test_resource_snapshot_detects_orphan_by_composite_parent() -> None:
    spec = RESOURCE_SPECS[1]
    result = build_resource_snapshot(
        [
            {
                "org_id": "org-a",
                "project_id": "project-a",
                "subject": "alice",
            },
            {
                "org_id": "org-b",
                "project_id": "project-b",
                "subject": "bob",
            },
        ],
        spec=spec,
        parent_rows=[{"org_id": "org-a", "project_id": "project-a"}],
    )

    assert result["rowCount"] == 2
    assert result["orphanRowCount"] == 1
    assert len(result["orphanKeyFingerprints"]) == 1


def test_reconciliation_blocks_matching_counts_without_identity_evidence() -> None:
    result = build_e1_reconciliation(_source_snapshot())

    assert result["gate"] == "BLOCKED"
    assert result["blockers"] == ["E1_ROW_IDENTITY_EVIDENCE_UNAVAILABLE"]
    assert result["historyMutated"] is False
    assert all(item["status"] == "MATCH" for item in result["metrics"])


def test_reconciliation_reports_unexplained_drift() -> None:
    result = build_e1_reconciliation(_source_snapshot(authz_rows=0))

    assert result["gate"] == "BLOCKED"
    assert "UNEXPLAINED_BASELINE_DRIFT" in result["blockers"]
    metric = next(
        item for item in result["metrics"] if item["metric"] == "authzTupleRows"
    )
    assert metric == {
        "metric": "authzTupleRows",
        "baseline": E1_FROZEN_BASELINE["authzTupleRows"],
        "current": 0,
        "delta": -9,
        "status": "UNEXPLAINED_DRIFT",
    }


def test_reconciliation_green_requires_counts_identity_and_scan() -> None:
    result = build_e1_reconciliation(
        _source_snapshot(), identity_evidence_available=True
    )
    assert result["gate"] == "GREEN"
    assert result["blockers"] == []
    assert result["nextAuthorizedStage"] == "E3-1"


def test_incomplete_source_snapshot_blocks_gate() -> None:
    result = build_e1_reconciliation(
        _source_snapshot(scan_ok=False), identity_evidence_available=True
    )
    assert result["gate"] == "BLOCKED"
    assert result["blockers"] == ["SOURCE_SNAPSHOT_INCOMPLETE"]


def test_environment_fingerprint_excludes_credentials() -> None:
    first = environment_fingerprint(
        "postgresql://"
        + "synthetic-a"
        + ":"
        + "invalid-a"
        + "@127.0.0.1:5433/aos_meta"
    )
    second = environment_fingerprint(
        "postgresql://"
        + "synthetic-b"
        + ":"
        + "invalid-b"
        + "@127.0.0.1:5433/aos_meta"
    )
    assert first == second
