"""Read-only issuer inquiry composition; a decision requires durable attempt authority."""

import os
from contextlib import contextmanager
from pathlib import Path

import pytest
from psycopg import connect

from aos_api.auth import Principal
from aos_api.aip_network_issuer_contracts import NetworkIssuerDecisionCommand
from aos_api.aip_network_issuer_reconcile import ReconcileResult, ReconcileStatus


def _command(proposal_id="proposal-1"):
    return NetworkIssuerDecisionCommand.model_validate({
        "schemaVersion": 1, "bearerToken": "header.payload.signature",
        "orgId": "org-org", "projectId": "dev-project",
        "proposalId": proposal_id, "idempotencyKey": proposal_id + "-event",
        "decision": {"expectedProposalVersion": 1,
                     "expectedProposalHash": "a" * 64,
                     "decision": "approved", "reason": "reviewed"},
    })


def test_decision_is_blocked_before_auth_or_database(monkeypatch):
    from aos_api import aip_network_issuer_service as module
    monkeypatch.setattr(module, "authenticate_issuer_request",
                        lambda _: pytest.fail("decision must not authenticate"))
    with pytest.raises(module.IssuerServiceBlocked, match="ATTEMPT_RECEIPT_REQUIRED"):
        module.dispatch_issuer_request(_command(), read_connect_factory=lambda: pytest.fail("DB opened"),
                                       expected_database="isolated")


def test_inquiry_auth_failure_never_opens_database():
    from aos_api.aip_network_issuer_service import dispatch_issuer_request
    with pytest.raises(Exception):
        dispatch_issuer_request(_command().inquiry(),
                                read_connect_factory=lambda: pytest.fail("DB opened"),
                                expected_database="isolated")


def test_inquiry_uses_signed_subject_and_exact_request(monkeypatch):
    from aos_api import aip_network_issuer_service as module
    principal = Principal(subject="signed-checker", org_id="org-org",
                          project_id="dev-project", token_kind="oidc")
    monkeypatch.setattr(module, "authenticate_issuer_request", lambda _: principal)
    calls = []
    class ReadFactory:
        def __call__(self):
            calls.append("open")
            return self
        def __enter__(self):
            return "read-connection"
        def __exit__(self, *_):
            calls.append("close")
    def reconciled(conn, inquiry, *, expected_actor, expected_database):
        calls.append((conn, inquiry.proposal_id, expected_actor, expected_database))
        return ReconcileResult(ReconcileStatus.UNRESOLVED)
    monkeypatch.setattr(module, "reconcile_approval_event_read_only", reconciled)
    result = module.dispatch_issuer_request(_command().inquiry(),
                                            read_connect_factory=ReadFactory(),
                                            expected_database="isolated")
    assert result.status is ReconcileStatus.UNRESOLVED
    assert calls == ["open", ("read-connection", "proposal-1", "signed-checker", "isolated"), "close"]


def test_isolated_clone_inquiry_remains_unresolved(monkeypatch):
    private = os.environ.get("AOS_BG00CQ_PROOF_DIR")
    if not private:
        pytest.skip("explicit isolated issuer proof directory required")
    from aos_api import aip_network_issuer_service as module
    base = Path(private)
    proposal_id = (base / "proposal-id").read_text().strip()
    principal = Principal(subject="bg00cm-checker-testonly", org_id="org-org",
                          project_id="dev-project", token_kind="oidc")
    monkeypatch.setattr(module, "authenticate_issuer_request", lambda _: principal)
    params = dict(host="127.0.0.1", port=18437,
                  dbname="aos_current_preview_20260927",
                  user="aos_network_approval_issuer",
                  passfile=str(base / "issuer.pgpass"))
    @contextmanager
    def read_connect():
        with connect(**params) as conn:
            conn.read_only = True
            yield conn
    result = module.dispatch_issuer_request(
        _command(proposal_id).inquiry(),
        read_connect_factory=read_connect,
        expected_database="aos_current_preview_20260927")
    assert result.status is ReconcileStatus.UNRESOLVED


def test_issue_once_persists_before_one_decision_and_reconciles(monkeypatch, tmp_path):
    from aos_api import aip_network_issuer_service as module
    principal = Principal(subject="checker", org_id="org-org", project_id="dev-project", token_kind="oidc")
    monkeypatch.setattr(module, "authenticate_issuer_request", lambda _: principal)
    calls = []
    def decided(actor, proposal_id, key, body, *, connect_factory):
        calls.append(("decide", actor.subject, proposal_id, key))
        assert list(tmp_path.iterdir())
    def reconciled(conn, inquiry, *, expected_actor, expected_database):
        calls.append(("read", expected_actor, inquiry.request_hash))
        return ReconcileResult(ReconcileStatus.OBSERVED, "event-1", "approved")
    monkeypatch.setattr(module, "decide_network_activation", decided)
    monkeypatch.setattr(module, "reconcile_approval_event_read_only", reconciled)
    class Read:
        def __enter__(self): return "read-connection"
        def __exit__(self, *_): pass
    command = _command()
    result = module.issue_decision_once(command, attempt_directory=tmp_path,
        decision_connect_factory=lambda: pytest.fail("decision factory is passed, not called by service"),
        read_connect_factory=Read, expected_database="isolated")
    assert result.status is ReconcileStatus.OBSERVED
    assert calls == [("decide", "checker", "proposal-1", "proposal-1-event"),
                     ("read", "checker", command.request_hash)]
    from aos_api.aip_network_issuer_attempt import AttemptAlreadyRecorded
    with pytest.raises(AttemptAlreadyRecorded):
        module.issue_decision_once(command, attempt_directory=tmp_path,
            decision_connect_factory=lambda: None, read_connect_factory=Read,
            expected_database="isolated")
    assert len(calls) == 2


def test_issue_exception_and_unresolved_never_resend(monkeypatch, tmp_path):
    from aos_api import aip_network_issuer_service as module
    principal = Principal(subject="checker", org_id="org-org", project_id="dev-project", token_kind="oidc")
    monkeypatch.setattr(module, "authenticate_issuer_request", lambda _: principal)
    calls = []
    def disconnected(*_, **__):
        calls.append("decide")
        raise ConnectionError("stream disconnected")
    monkeypatch.setattr(module, "decide_network_activation", disconnected)
    monkeypatch.setattr(module, "reconcile_approval_event_read_only",
                        lambda *_, **__: ReconcileResult(ReconcileStatus.UNRESOLVED))
    class Read:
        def __enter__(self): return "read-connection"
        def __exit__(self, *_): pass
    result = module.issue_decision_once(_command(), attempt_directory=tmp_path,
        decision_connect_factory=lambda: None, read_connect_factory=Read,
        expected_database="isolated")
    assert result.status is ReconcileStatus.UNRESOLVED
    from aos_api.aip_network_issuer_attempt import AttemptAlreadyRecorded
    with pytest.raises(AttemptAlreadyRecorded):
        module.issue_decision_once(_command(), attempt_directory=tmp_path,
            decision_connect_factory=lambda: None, read_connect_factory=Read,
            expected_database="isolated")
    assert calls == ["decide"]


def test_isolated_clone_disconnect_reconciles_read_only_without_resend(monkeypatch, tmp_path):
    private = os.environ.get("AOS_BG00CQ_PROOF_DIR")
    if not private:
        pytest.skip("explicit isolated issuer proof directory required")
    from aos_api import aip_network_issuer_service as module
    from aos_api.aip_network_issuer_attempt import AttemptAlreadyRecorded
    base = Path(private)
    proposal_id = (base / "proposal-id").read_text().strip()
    principal = Principal(subject="bg00cm-checker-testonly", org_id="org-org",
                          project_id="dev-project", token_kind="oidc")
    monkeypatch.setattr(module, "authenticate_issuer_request", lambda _: principal)
    calls = []
    def disconnected(*_, **__):
        calls.append("decide")
        raise ConnectionError("unknown outcome")
    monkeypatch.setattr(module, "decide_network_activation", disconnected)
    params = dict(host="127.0.0.1", port=18437,
                  dbname="aos_current_preview_20260927",
                  user="aos_network_approval_issuer",
                  passfile=str(base / "issuer.pgpass"))
    @contextmanager
    def read_connect():
        with connect(**params) as conn:
            conn.read_only = True
            yield conn
    command = _command(proposal_id)
    result = module.issue_decision_once(command, attempt_directory=tmp_path,
        decision_connect_factory=lambda: pytest.fail("single decision stub owns outcome"),
        read_connect_factory=read_connect, expected_database="aos_current_preview_20260927")
    assert result.status is ReconcileStatus.UNRESOLVED
    with pytest.raises(AttemptAlreadyRecorded):
        module.issue_decision_once(command, attempt_directory=tmp_path,
            decision_connect_factory=lambda: None, read_connect_factory=read_connect,
            expected_database="aos_current_preview_20260927")
    assert calls == ["decide"]
