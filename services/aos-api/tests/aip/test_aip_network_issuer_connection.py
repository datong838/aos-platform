"""Issuer connections never inherit the ordinary API owner DSN or role."""

import os
from pathlib import Path

import pytest

from aos_api.tenant_scope import TenantScope


def _config(path: Path):
    from aos_api.aip_network_issuer_connection import IssuerDatabaseConfig
    return IssuerDatabaseConfig(host="127.0.0.1", port=18437,
        database="aos_current_preview_20260927", passfile=path)


def test_private_passfile_and_loopback_config_required(tmp_path):
    from aos_api.aip_network_issuer_connection import IssuerDatabaseBlocked
    private = tmp_path / "issuer"
    private.mkdir(mode=0o700)
    passfile = private / "issuer.pgpass"
    passfile.write_text("test-only-placeholder")
    passfile.chmod(0o600)
    assert _config(passfile).database == "aos_current_preview_20260927"
    passfile.chmod(0o644)
    with pytest.raises(IssuerDatabaseBlocked):
        _config(passfile)
    passfile.chmod(0o600)
    from aos_api.aip_network_issuer_connection import IssuerDatabaseConfig
    with pytest.raises(IssuerDatabaseBlocked):
        IssuerDatabaseConfig(host="example.com", port=18437,
            database="aos_current_preview_20260927", passfile=passfile)
    with pytest.raises(IssuerDatabaseBlocked):
        IssuerDatabaseConfig(host="127.0.0.1", port=18437,
            database="aos-current-preview;drop", passfile=passfile)


def test_environment_password_fallback_is_rejected(monkeypatch, tmp_path):
    from aos_api.aip_network_issuer_connection import connect_issuer_read_only, IssuerDatabaseBlocked
    private = tmp_path / "issuer"
    private.mkdir(mode=0o700)
    passfile = private / "issuer.pgpass"
    passfile.write_text("test-only-placeholder")
    passfile.chmod(0o600)
    monkeypatch.setenv("PGPASSWORD", "wrong")
    with pytest.raises(IssuerDatabaseBlocked):
        with connect_issuer_read_only(_config(passfile), TenantScope("org-org", "dev-project")):
            pytest.fail("connection opened")


def test_isolated_clone_real_issuer_read_only_scope_and_role(monkeypatch):
    private = os.environ.get("AOS_BG00CM_PROOF_DIR")
    if os.environ.get("AOS_BG00CM_TEST_CONTAINER") != "aos-bg00ck-isolated-pg" or not private:
        pytest.skip("explicit BG00cm isolated clone required")
    from aos_api.aip_network_issuer_connection import connect_issuer_read_only
    monkeypatch.setenv("AOS_DATABASE_URL", "postgresql://aos_app:wrong@127.0.0.1:1/wrong")
    config = _config(Path(private) / "issuer.pgpass")
    scope = TenantScope("org-org", "dev-project")
    with connect_issuer_read_only(config, scope) as conn:
        identity = conn.execute("SELECT session_user AS login,current_user AS role,"
            "current_setting('aos.org_id',true) AS org_id,"
            "current_setting('aos.project_id',true) AS project_id").fetchone()
        assert identity == {"login": "aos_network_approval_issuer",
                            "role": "aos_runtime", "org_id": "org-org",
                            "project_id": "dev-project"}
        assert conn.read_only is True
        assert conn.execute("SELECT count(*) AS n FROM aip_action_approval_event "
            "WHERE org_id=%s AND project_id=%s", scope.key).fetchone()["n"] == 0
        from aos_api.aip_network_issuer_contracts import NetworkIssuerDecisionCommand
        from aos_api.aip_network_issuer_reconcile import (
            ReconcileStatus, reconcile_approval_event_read_only,
        )
        proposal_id = (Path(private) / "proposal-id").read_text().strip()
        inquiry = NetworkIssuerDecisionCommand.model_validate({
            "schemaVersion": 1, "bearerToken": "header.payload.signature",
            "orgId": "org-org", "projectId": "dev-project",
            "proposalId": proposal_id, "idempotencyKey": proposal_id + "-event",
            "decision": {"expectedProposalVersion": 1,
                         "expectedProposalHash": "b" * 64,
                         "decision": "approved", "reason": "isolated inquiry"},
        }).inquiry()
        result = reconcile_approval_event_read_only(conn, inquiry,
            expected_actor="bg00cm-checker-testonly",
            expected_database=config.database)
        assert result.status is ReconcileStatus.UNRESOLVED


def test_isolated_clone_decision_connection_rebinds_after_commit_and_rollback():
    private = os.environ.get("AOS_BG00CM_PROOF_DIR")
    if os.environ.get("AOS_BG00CM_TEST_CONTAINER") != "aos-bg00ck-isolated-pg" or not private:
        pytest.skip("explicit BG00cm isolated clone required")
    from aos_api.aip_network_issuer_connection import connect_issuer_decision
    config = _config(Path(private) / "issuer.pgpass")
    scope = TenantScope("org-org", "dev-project")
    with connect_issuer_decision(config, scope) as conn:
        assert conn.read_only is False
        conn.commit()
        after_commit = conn.execute("SELECT session_user AS login,current_user AS role,"
            "current_setting('aos.org_id',true) AS org_id,"
            "current_setting('aos.project_id',true) AS project_id").fetchone()
        assert after_commit == {"login": "aos_network_approval_issuer",
                                "role": "aos_runtime", "org_id": "org-org",
                                "project_id": "dev-project"}
        conn.rollback()
        after_rollback = conn.execute("SELECT current_user AS role,"
            "current_setting('aos.org_id',true) AS org_id").fetchone()
        assert after_rollback == {"role": "aos_runtime", "org_id": "org-org"}
