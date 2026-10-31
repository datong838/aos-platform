"""Pure contract tests for the T2 revision-2 draft renewal."""

from datetime import UTC, datetime
import importlib.util
from pathlib import Path
import sys

import pytest


BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
sys.path[:0] = [str(ROOT / "services/aos-api"), str(ROOT / "services/aos-api/tests/extension_runtime")]
from test_selected_three_backend_lifecycle_pg import build_initial_policy_drafts

MODULE = BASE / "t2_policy_draft_renewal_r883.py"
SPEC = importlib.util.spec_from_file_location("t2_policy_draft_renewal_r883", MODULE)
renewal = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renewal)


OLD_TIME = datetime(2026, 10, 28, 6, 40, 41, 433192, tzinfo=UTC)
NEW_FROM = datetime(2026, 10, 31, 14, 45, tzinfo=UTC)


def originals():
    return build_initial_policy_drafts("m2-three-t2", OLD_TIME).requests


def test_exact_four_drafts_renew_to_revision_two_and_authorized_cutoff():
    result = renewal.build_policy_draft_renewals(originals(), effective_from=NEW_FROM)
    assert len(result) == 4
    assert [item.revision for item in result] == [2, 2, 2, 2]
    assert all(item.lifecycle.value == "draft" for item in result)
    assert all(item.effective_from == NEW_FROM for item in result)
    assert all(item.effective_until == renewal.AUTHORIZED_UNTIL for item in result)


def test_only_revision_and_window_change():
    before = originals()
    after = renewal.build_policy_draft_renewals(before, effective_from=NEW_FROM)
    allowed = {"revision", "effectiveFrom", "effectiveUntil"}
    for old, new in zip(before, after, strict=True):
        old_value = old.model_dump(mode="json", by_alias=True)
        new_value = new.model_dump(mode="json", by_alias=True)
        changed = {key for key in old_value if old_value[key] != new_value[key]}
        assert changed == allowed
        for key in set(old_value) - allowed:
            assert new_value[key] == old_value[key]


@pytest.mark.parametrize("index,update", [
    (0, {"revision": 2}),
    (0, {"owner": "another-owner"}),
    (1, {"lifecycle": "active"}),
    (2, {"approval_ref": "another-approval"}),
    (3, {"policy_id": "another-policy"}),
])
def test_identity_or_authority_drift_is_rejected(index, update):
    values = list(originals())
    values[index] = values[index].model_copy(update=update)
    with pytest.raises(ValueError, match="original draft authority differs"):
        renewal.build_policy_draft_renewals(tuple(values), effective_from=NEW_FROM)


def test_new_window_must_start_after_old_window_and_before_cutoff():
    old = originals()
    with pytest.raises(ValueError, match="renewal window differs"):
        renewal.build_policy_draft_renewals(old, effective_from=old[0].effective_until)
    with pytest.raises(ValueError, match="renewal window differs"):
        renewal.build_policy_draft_renewals(old, effective_from=renewal.AUTHORIZED_UNTIL)


def test_new_window_requires_canonical_utc():
    from datetime import timedelta, timezone
    with pytest.raises(ValueError, match="original draft authority differs"):
        renewal.build_policy_draft_renewals(
            originals(), effective_from=NEW_FROM.astimezone(timezone(timedelta(hours=8)))
        )


def test_descriptors_are_new_cas_keys_and_bind_exact_requests():
    requests = renewal.build_policy_draft_renewals(originals(), effective_from=NEW_FROM)
    descriptors = renewal.build_renewal_descriptors(requests)
    assert tuple(item["step"] for item in descriptors) == renewal.STEPS
    assert all(item["expectedVersion"] == 1 for item in descriptors)
    assert [item["idempotencyKey"] for item in descriptors] == [
        "m2-three-t2-renewal-20270331-budget",
        "m2-three-t2-renewal-20270331-egress",
        "m2-three-t2-renewal-20270331-data",
        "m2-three-t2-renewal-20270331-quota",
    ]
    assert all(len(item["requestHash"]) == 64 for item in descriptors)
    assert len({item["requestHash"] for item in descriptors}) == 4


def test_descriptors_reject_post_build_identity_drift():
    requests = list(renewal.build_policy_draft_renewals(originals(), effective_from=NEW_FROM))
    requests[3] = requests[3].model_copy(update={"owner": "another-owner"})
    with pytest.raises(ValueError, match="exact renewal requests required"):
        renewal.build_renewal_descriptors(tuple(requests))
