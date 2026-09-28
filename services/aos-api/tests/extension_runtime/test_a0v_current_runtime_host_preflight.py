import importlib.util
from pathlib import Path

import pytest

from aos_api.extension_runtime.runtime_identity import RuntimeDatabaseIdentity


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_current_runtime_host_preflight.py"


@pytest.fixture
def gate():
    spec = importlib.util.spec_from_file_location("a0v_current_runtime_host_preflight", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def identity(role, oid, *, database="aos_current_preview_20260927", directory=False,
             runtime=False, privileged=False):
    return RuntimeDatabaseIdentity(
        authority=("172.0.0.2", 5432, database), session_user=role, role_oid=oid,
        directory_member=directory, runtime_member=runtime, privileged=privileged,
        owns_protected_relation=False,
    )


def test_missing_credentials_fail_before_signed_or_database_access(gate, monkeypatch):
    monkeypatch.setattr(gate, "signed_preflight", lambda **_: pytest.fail("signed preflight ran"))
    with pytest.raises(gate.HostPreflightBlocked, match="CREDENTIAL_FILE_REQUIRED"):
        gate.preflight(signed_receipt=Path("/unused"), credential_file=None)


def test_old_database_dsn_rejected_before_connection(gate):
    dsns = {plane: f"host=localhost dbname=aos_meta_head user={plane}"
            for plane in ("directory", "runtime", "web")}
    with pytest.raises(gate.HostPreflightBlocked, match="CREDENTIAL_DATABASE_DRIFT"):
        gate.require_current_dsn_targets(dsns, "aos_current_preview_20260927")


def test_signed_receipt_failure_rejected_before_credential_read(gate, monkeypatch):
    monkeypatch.setattr(gate, "signed_preflight", lambda **_: (_ for _ in ()).throw(ValueError("bad")))
    monkeypatch.setattr(gate, "_runtime_file_dsns", lambda *_: pytest.fail("credential file read"))
    with pytest.raises(gate.HostPreflightBlocked, match="SIGNED_INSTALLATION_INVALID"):
        gate.preflight(signed_receipt=Path("/invalid"), credential_file=Path("/protected/current.json"))


def test_old_database_credential_rejected_before_identity_connection(gate, monkeypatch):
    monkeypatch.setattr(gate, "signed_preflight", lambda **_: (
        {"dbname": "aos_current_preview_20260927"},
        {"database": "aos_current_preview_20260927"}))
    monkeypatch.setattr(gate, "_runtime_file_dsns", lambda *_: {
        plane: f"host=localhost dbname=aos_meta_head user={plane}"
        for plane in ("directory", "runtime", "web")})
    monkeypatch.setattr(gate.psycopg, "connect", lambda *_a, **_k: pytest.fail("database connected"))
    with pytest.raises(gate.HostPreflightBlocked, match="CREDENTIAL_DATABASE_DRIFT"):
        gate.preflight(signed_receipt=Path("/signed"), credential_file=Path("/protected/old.json"))


@pytest.mark.parametrize("bad", [
    identity("web", 3, database="aos_meta_head"),
    identity("runtime", 2),
    identity("web", 3, privileged=True),
])
def test_mixed_same_role_or_privileged_identity_rejected(gate, bad):
    with pytest.raises(gate.HostPreflightBlocked, match="RUNTIME_IDENTITY_INVALID"):
        gate.require_current_identities(
            directory=identity("directory", 1, directory=True),
            runtime=identity("runtime", 2, runtime=True), web=bad,
            authority=("172.0.0.2", 5432, "aos_current_preview_20260927"),
        )


class ReadConn:
    read_only = True

    def __init__(self, assignment=None, candidates=None):
        self.assignment = assignment
        self.candidates = candidates
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        return self

    def fetchone(self):
        return self.assignment


def test_exact_host_assignment_and_identity_required(gate, monkeypatch):
    monkeypatch.setattr(gate, "read_candidates", lambda *_: pytest.fail("candidates read too early"))
    conn = ReadConn()
    with pytest.raises(gate.HostPreflightBlocked, match="HOST_ASSIGNMENT_MISSING"):
        gate.require_current_host_and_candidates(conn, identity("directory", 1, directory=True))
    assert conn.calls[0][1] == ("org-org", "dev-project")


def test_host_identity_must_match_directory_role_and_oid(gate, monkeypatch):
    monkeypatch.setattr(gate, "read_candidates", lambda *_: pytest.fail("candidates read too early"))
    conn = ReadConn({"state": "assigned", "host_id": "host-1", "database_role": "old-dir",
                     "database_role_oid": 99, "enabled": True})
    with pytest.raises(gate.HostPreflightBlocked, match="HOST_IDENTITY_MISMATCH"):
        gate.require_current_host_and_candidates(conn, identity("directory", 1, directory=True))


def test_missing_configuration_candidates_fail_closed(gate, monkeypatch):
    from aos_api.extension_runtime.runtime_configuration_candidates import RuntimeConfigurationCandidates
    monkeypatch.setattr(gate, "read_candidates", lambda *_: RuntimeConfigurationCandidates(
        {"budgets": 0}, ("budgets",), False))
    conn = ReadConn({"state": "assigned", "host_id": "host-1", "database_role": "directory",
                     "database_role_oid": 1, "enabled": True})
    with pytest.raises(gate.HostPreflightBlocked, match="CONFIGURATION_CANDIDATES_MISSING"):
        gate.require_current_host_and_candidates(conn, identity("directory", 1, directory=True))
