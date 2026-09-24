"""Static and model-level preflight only; never calls the closure Owner."""

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from aos_api.pipeline_snapshot_stalled_group_closure import (
    StalledSnapshotGroupClosureRequest,
)


MIGRATION = (Path(__file__).resolve().parents[2] / "alembic" / "versions" /
             "a0v_091_snapshot_stalled_group_closure.py")


def request(**changes):
    identity = str(uuid4())
    reference = {
        "resourceType": "SnapshotScheduleDefinitionRevision",
        "resourceId": "snapshot-schedule-" + identity,
        "revision": 3,
        "contentHash": "sha256:" + "a" * 64,
    }
    value = {
        "schemaVersion": "aos.pipeline-snapshot.stalled-group-closure/v1",
        "groupId": str(uuid4()),
        "originalDefinitionRef": reference,
        "currentDisabledDefinitionRef": {**reference, "revision": 4, "contentHash": "sha256:" + "b" * 64},
        "reasonCode": "STALLED_EXECUTOR_ABANDONED_WITH_EFFECTS",
        "idempotencyKey": "a0v-w5c4w-fixture-v1",
    }
    value.update(changes)
    return value


def test_exact_stalled_closure_request_model_is_accepted_without_execution():
    parsed = StalledSnapshotGroupClosureRequest.model_validate(request())
    assert parsed.reason_code == "STALLED_EXECUTOR_ABANDONED_WITH_EFFECTS"
    assert parsed.idempotency_key == "a0v-w5c4w-fixture-v1"


@pytest.mark.parametrize("change", (
    {"groupId": "NOT-A-UUID"},
    {"idempotencyKey": " padded "},
    {"reasonCode": "UNACCEPTED"},
    {"originalDefinitionRef": {"resourceType": "SnapshotScheduleDefinitionRevision"}},
    {"extra": True},
))
def test_stalled_request_rejects_non_exact_inputs(change):
    with pytest.raises((ValidationError, ValueError)):
        StalledSnapshotGroupClosureRequest.model_validate(request(**change))


def test_migration_keeps_strict_time_effects_and_non_business_receipt():
    source = MIGRATION.read_text()
    assert "r.started_at < clock_timestamp()-interval '24 hours'" in source
    assert "v_member_count<>12 OR v_run_count<>12 OR v_stale_count<>12" in source
    assert "v_head.state<>'disabled'" in source
    assert "lower(role) IN ('admin','owner')" in source
    assert "'businessAccepted',false" in source
    assert "'effectEvidence',jsonb_build_object(" in source
    assert "v_old.request_hash<>v_hash OR v_old.actor<>p_actor" in source
