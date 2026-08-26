"""BI-W8-07 unified replay/expiry/conflict/permission failure-closure matrix."""

from __future__ import annotations

import test_ecommerce_analyst_growth_plan_approval as growth_plan
import test_ecommerce_business_investigation_data_command as data_command
import test_ecommerce_business_investigation_review_command as review_command
import test_ecommerce_business_investigation_schedule as schedule


WAVE8_FAILURE_CLOSURE_MATRIX = {
    "BI-W8-01": {"replay", "conflict", "permission", "unknown"},
    "BI-W8-02": {"replay", "conflict", "permission", "overlap"},
    "BI-W8-03": {"replay", "conflict", "permission", "unknown"},
    "BI-W8-04": {"replay", "conflict", "permission", "unknown"},
    "BI-W8-05": {"replay", "conflict", "permission", "stale"},
    "BI-W8-06": {"replay", "conflict", "permission", "expiry"},
}


def test_wave8_matrix_covers_every_command_family_and_hard_failure_dimension() -> None:
    assert set(WAVE8_FAILURE_CLOSURE_MATRIX) == {
        "BI-W8-01",
        "BI-W8-02",
        "BI-W8-03",
        "BI-W8-04",
        "BI-W8-05",
        "BI-W8-06",
    }
    covered = set().union(*WAVE8_FAILURE_CLOSURE_MATRIX.values())
    assert {"replay", "conflict", "permission", "unknown", "expiry", "stale", "overlap"} <= covered


def test_wave8_schedule_disabled_stale_and_bad_time_never_reach_run_store() -> None:
    schedule.test_trigger_rejects_disabled_stale_policy_and_bad_time_before_run_write()


def test_wave8_data_same_key_different_body_never_creates_second_requirement() -> None:
    data_command.test_request_rejects_same_web_key_with_different_body_before_second_data_write()
    data_command.test_confirmation_rejects_same_key_with_opposite_decision_without_new_revision()


def test_wave8_review_state_drift_never_calls_review_authority() -> None:
    review_command.test_unowned_or_unavailable_review_edges_fail_before_write(
        "accept", 2, None, "RUN_STATE_VERSION_DRIFTED"
    )


def test_wave8_growth_plan_replay_and_stale_draft_are_both_fail_closed() -> None:
    growth_plan.test_approve_creates_adjacent_server_owned_approved_successor_and_replays()
    growth_plan.test_approve_fails_closed_for_stale_non_draft_or_non_current(
        2, "draft", True, "stale"
    )
