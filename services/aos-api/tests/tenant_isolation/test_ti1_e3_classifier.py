from __future__ import annotations

from aos_api.tenant_ownership_classifier import classify_source_snapshot


def _snapshot() -> dict:
    return {
        "environmentFingerprint": "a" * 64,
        "resources": {
            "authz_tuple": {
                "unassignedKeyFingerprints": ["1" * 64],
                "orphanKeyFingerprints": [],
            },
            "meta_membership": {
                "unassignedKeyFingerprints": [],
                "orphanKeyFingerprints": ["2" * 64, "3" * 64],
            },
        },
    }


def test_classifier_quarantines_unknown_and_orphan_records() -> None:
    result = classify_source_snapshot(_snapshot())

    assert result["gate"] == "GREEN"
    assert result["totalDiscovered"] == 3
    assert result["counts"] == {
        "ASSIGN": 0,
        "QUARANTINE": 3,
        "NO_ACTION": 0,
        "BLOCKED": 0,
    }
    assert {item["reasonCode"] for item in result["decisions"]} == {
        "NO_A_GRADE_EVIDENCE",
        "ORPHAN_PARENT_UNVERIFIED",
    }
    assert all(item["targetScopeHash"] is None for item in result["decisions"])


def test_classifier_is_deterministic_and_contains_no_raw_keys() -> None:
    first = classify_source_snapshot(_snapshot())
    second = classify_source_snapshot(_snapshot())

    assert first == second
    serialized = str(first)
    assert "user:" not in serialized
    assert "object:" not in serialized
    assert first["rawKeysReturned"] is False
    assert first["rawPayloadReturned"] is False


def test_orphan_reason_wins_when_same_record_is_also_unassigned() -> None:
    snapshot = _snapshot()
    snapshot["resources"]["meta_membership"]["unassignedKeyFingerprints"] = [
        "2" * 64
    ]

    result = classify_source_snapshot(snapshot)

    assert result["totalDiscovered"] == 3
    decision = next(
        item for item in result["decisions"] if item["keyHash"] == "2" * 64
    )
    assert decision["reasonCode"] == "ORPHAN_PARENT_UNVERIFIED"

