"""Durable at-most-once marker before any network approval decision."""

import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from aos_api.auth import Principal
from aos_api.aip_network_issuer_contracts import NetworkIssuerDecisionCommand


def _command(**changes):
    raw = {
        "schemaVersion": 1, "bearerToken": "header.payload.signature",
        "orgId": "org-org", "projectId": "dev-project",
        "proposalId": "proposal-1", "idempotencyKey": "decision-1",
        "decision": {"expectedProposalVersion": 1,
                     "expectedProposalHash": "a" * 64,
                     "decision": "approved", "reason": "reviewed"},
    }
    raw.update(changes)
    return NetworkIssuerDecisionCommand.model_validate(raw)


def _principal():
    return Principal(subject="checker-1", org_id="org-org", project_id="dev-project", token_kind="oidc")


def test_first_receipt_is_fsynced_private_and_replay_never_authorizes(tmp_path):
    from aos_api.aip_network_issuer_attempt import reserve_decision_attempt, AttemptAlreadyRecorded
    receipt = reserve_decision_attempt(tmp_path, _command(), _principal())
    files = list(tmp_path.iterdir())
    assert len(files) == 1 and files[0].name.endswith(".json")
    assert files[0].stat().st_mode & 0o777 == 0o600
    content = files[0].read_text()
    assert "header.payload.signature" not in content
    assert json.loads(content)["requestHash"] == _command().request_hash
    assert receipt.request_hash == _command().request_hash
    with pytest.raises(AttemptAlreadyRecorded):
        reserve_decision_attempt(tmp_path, _command(), _principal())


def test_same_key_different_request_is_conflict(tmp_path):
    from aos_api.aip_network_issuer_attempt import reserve_decision_attempt, AttemptConflict
    reserve_decision_attempt(tmp_path, _command(), _principal())
    with pytest.raises(AttemptConflict):
        reserve_decision_attempt(tmp_path, _command(proposalId="proposal-2"), _principal())


def test_partial_receipt_stays_unknown_and_never_retries(tmp_path):
    from aos_api.aip_network_issuer_attempt import reserve_decision_attempt, AttemptUnknown
    reserve_decision_attempt(tmp_path, _command(), _principal())
    path = next(tmp_path.iterdir())
    path.write_text("")
    with pytest.raises(AttemptUnknown):
        reserve_decision_attempt(tmp_path, _command(), _principal())


def test_concurrent_attempts_have_one_winner_and_tampered_mode_denies(tmp_path):
    from aos_api.aip_network_issuer_attempt import (
        reserve_decision_attempt, AttemptBlocked, AttemptUnknown,
    )
    def reserve():
        try:
            reserve_decision_attempt(tmp_path, _command(), _principal())
            return "first"
        except AttemptBlocked:
            return "denied"
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: reserve(), range(8)))
    assert results.count("first") == 1
    assert results.count("denied") == 7
    os.chmod(next(tmp_path.iterdir()), 0o644)
    with pytest.raises(AttemptUnknown):
        reserve_decision_attempt(tmp_path, _command(), _principal())


def test_bad_directory_or_identity_rejected(tmp_path):
    from aos_api.aip_network_issuer_attempt import reserve_decision_attempt, AttemptBlocked
    link = tmp_path.parent / (tmp_path.name + "-link")
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(AttemptBlocked):
        reserve_decision_attempt(link, _command(), _principal())
    os.chmod(tmp_path, 0o755)
    with pytest.raises(AttemptBlocked):
        reserve_decision_attempt(tmp_path, _command(), _principal())
    os.chmod(tmp_path, 0o700)
    with pytest.raises(AttemptBlocked):
        reserve_decision_attempt(tmp_path, _command(), Principal(
            subject="checker-1", org_id="dev-org", project_id="dev-project", token_kind="oidc"))
