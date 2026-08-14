"""Golden and tamper tests for permanent installation evidence."""

from datetime import UTC, datetime

import pytest

from aos_api.asset_registry.installation_evidence import (
    build_event_evidence,
    format_evidence_timestamp,
    verify_event_evidence,
)

INSTALLATION_ID = "22222222-2222-4222-8222-222222222222"
HASHES = {
    "lock_hash": "sha256:" + "a" * 64,
    "permission_diff_hash": "sha256:" + "b" * 64,
    "migration_plan_hash": "sha256:" + "c" * 64,
    "contribution_diff_hash": "sha256:" + "d" * 64,
}


def _arguments():
    return {
        "evidence_type": "dry_apply",
        "installation_id": INSTALLATION_ID,
        "from_revision": 3,
        "to_revision": 4,
        **HASHES,
        "decision_id": "33333333-3333-4333-8333-333333333333",
        "observed_at": datetime(2026, 8, 3, 1, 2, 3, 120000, tzinfo=UTC),
    }


def test_evidence_is_reproducible_with_canonical_utc_timestamp() -> None:
    first = build_event_evidence(**_arguments())
    second = build_event_evidence(**_arguments())

    assert first == second
    assert first.evidence_ref.endswith("/revisions/4/dry_apply")
    assert first.evidence_hash.startswith("sha256:")
    assert (
        format_evidence_timestamp(first.observed_at) == "2026-08-03T01:02:03.12+00:00"
    )
    verify_event_evidence(
        first, **{k: v for k, v in _arguments().items() if k != "evidence_type"}
    )


def test_uninstall_evidence_is_a_canonical_active_transition() -> None:
    arguments = {
        **_arguments(),
        "evidence_type": "uninstall",
        "from_revision": 5,
        "to_revision": 6,
    }

    evidence = build_event_evidence(**arguments)

    assert evidence.type == "uninstall"
    assert evidence.evidence_ref.endswith("/revisions/6/uninstall")
    verify_event_evidence(
        evidence,
        **{key: value for key, value in arguments.items() if key != "evidence_type"},
    )


def test_evidence_tampering_is_rejected() -> None:
    evidence = build_event_evidence(**_arguments()).model_copy(
        update={"evidence_hash": "sha256:" + "f" * 64}
    )
    with pytest.raises(ValueError, match="integrity"):
        verify_event_evidence(
            evidence,
            **{k: v for k, v in _arguments().items() if k != "evidence_type"},
        )
