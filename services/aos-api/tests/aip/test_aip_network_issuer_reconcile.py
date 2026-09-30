"""No resend after an unknown network approval decision."""

import os
from pathlib import Path

import pytest
from psycopg import connect

from aos_api.aip_network_issuer_contracts import NetworkIssuerDecisionCommand
from aos_api.aip_network_issuer_reconcile import (
    NetworkIssuerReconcileBlocked, ReconcileStatus,
    classify_event_row, reconcile_approval_event_read_only,
)


def _inquiry():
    return NetworkIssuerDecisionCommand.model_validate({
        "schemaVersion": 1, "bearerToken": "header.payload.signature",
        "orgId": "org-org", "projectId": "dev-project",
        "proposalId": "proposal-1", "idempotencyKey": "key-1",
        "decision": {"expectedProposalVersion": 1,
                     "expectedProposalHash": "a" * 64,
                     "decision": "approved", "reason": "reviewed"},
    }).inquiry()


def test_exact_event_observed_but_same_key_drift_is_conflict():
    inquiry = _inquiry()
    row = {"approval_event_id": "event-1", "proposal_id": "proposal-1",
           "request_hash": inquiry.request_hash, "actor_id": "checker-1",
           "decision": "approved", "event_proposal_hash": "a" * 64,
           "current_proposal_hash": "a" * 64,
           "action_type_id": "aip_activate_network_policy"}
    assert classify_event_row(inquiry, expected_actor="checker-1", row=None).status is ReconcileStatus.UNRESOLVED
    observed = classify_event_row(inquiry, expected_actor="checker-1", row=row)
    assert observed.status is ReconcileStatus.OBSERVED
    assert observed.event_id == "event-1"
    for drift in ({"proposal_id": "other"}, {"request_hash": "b" * 64},
                  {"actor_id": "maker"}, {"action_type_id": "other"},
                  {"current_proposal_hash": "b" * 64}):
        assert classify_event_row(inquiry, expected_actor="checker-1",
                                  row={**row, **drift}).status is ReconcileStatus.CONFLICT


def test_isolated_real_issuer_read_only_unresolved_and_write_connection_denied():
    private = os.environ.get("AOS_BG00CQ_PROOF_DIR")
    if not private:
        pytest.skip("explicit isolated BG00cm proof directory required")
    base = Path(private)
    proposal = (base / "proposal-id").read_text().strip()
    command = NetworkIssuerDecisionCommand.model_validate({
        "schemaVersion": 1, "bearerToken": "header.payload.signature",
        "orgId": "org-org", "projectId": "dev-project",
        "proposalId": proposal, "idempotencyKey": proposal + "-event",
        "decision": {"expectedProposalVersion": 1,
                     "expectedProposalHash": "b" * 64,
                     "decision": "approved", "reason": "isolated inquiry"},
    })
    params = dict(host="127.0.0.1", port=18437,
                  dbname="aos_current_preview_20260927",
                  user="aos_network_approval_issuer",
                  passfile=str(base / "issuer.pgpass"))
    with connect(**params) as conn:
        with pytest.raises(NetworkIssuerReconcileBlocked, match="READ_ONLY_REQUIRED"):
            reconcile_approval_event_read_only(conn, command.inquiry(),
                                               expected_actor="bg00cm-checker-testonly",
                                               expected_database="aos_current_preview_20260927")
    with connect(**params) as conn:
        conn.read_only = True
        result = reconcile_approval_event_read_only(conn, command.inquiry(),
                                                    expected_actor="bg00cm-checker-testonly",
                                                    expected_database="aos_current_preview_20260927")
        assert result.status is ReconcileStatus.UNRESOLVED
