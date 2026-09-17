from uuid import uuid4

import pytest

from aos_api.pipeline_snapshot_unaccepted_group_closure import (
    UnacceptedSnapshotGroupClosureRequest,
)


def ref(revision=5):
    return {
        "resourceType": "SnapshotScheduleDefinitionRevision",
        "resourceId": f"snapshot-schedule-{uuid4()}",
        "revision": revision,
        "contentHash": "sha256:" + "a" * 64,
    }


def request():
    return {
        "schemaVersion": "aos.pipeline-snapshot.unaccepted-group-closure/v1",
        "groupId": str(uuid4()),
        "originalDefinitionRef": ref(5),
        "currentDisabledDefinitionRef": ref(6),
        "reasonCode": "SOURCE_BUDGET_REJECTED_BEFORE_GROUP_CLAIM",
        "idempotencyKey": "close-snapshot-group-1",
    }


@pytest.mark.parametrize("field,value", [
    ("groupId", "bad"), ("idempotencyKey", " close"),
    ("reasonCode", "SOURCE_FAILED"), ("schemaVersion", "unknown"), ("accepted", True),
])
def test_request_rejects_nonexact_input(field, value):
    with pytest.raises(ValueError):
        UnacceptedSnapshotGroupClosureRequest.model_validate({**request(), field: value})


def test_exact_wire_roundtrip():
    wire = request()
    assert UnacceptedSnapshotGroupClosureRequest.model_validate(wire).model_dump(
        mode="json", by_alias=True
    ) == wire


def test_migration_keeps_no_effect_and_exact_definition_guards():
    from pathlib import Path

    source = (Path(__file__).parents[1] / "alembic/versions/a0v_083_snapshot_unaccepted_group_closure.py").read_text()
    for required in (
        "v_member_count<>12 OR v_run_count<>12",
        "v_group_claims<>0 OR v_group_inputs<>0 OR v_group_members<>0 OR v_source_claims<>0",
        "v_ingress_commands<>0 OR v_derived_commands<>0 OR v_dataset_receipts<>0",
        "v_current.previous_revision<>v_original.revision",
        "businessAccepted',false",
        "SOURCE_BUDGET_REJECTED_BEFORE_GROUP_CLAIM",
        "immutable snapshot group closure receipt required",
    ):
        assert required in source
