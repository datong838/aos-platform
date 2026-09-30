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
    monkeypatch.setattr(gate, "_runtime_file_dsns", lambda *_a, **_k: ({
        plane: f"host=localhost dbname=aos_meta_head user={plane}"
        for plane in ("directory", "runtime", "web")}, [1, 2, 3, 4, 5]))
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


def test_explicit_preparation_only_keeps_identity_gate_and_reports_missing_candidates(gate, monkeypatch):
    from aos_api.extension_runtime.runtime_configuration_candidates import RuntimeConfigurationCandidates
    monkeypatch.setattr(gate, "read_candidates", lambda *_: RuntimeConfigurationCandidates(
        {"budgets": 0}, ("budgets",), False))
    conn = ReadConn({"state": "assigned", "host_id": "host-1", "database_role": "directory",
                     "database_role_oid": 1, "enabled": True})
    result = gate.require_current_host_and_candidates(
        conn, identity("directory", 1, directory=True), preparation_only=True)
    assert result == {"hostId": "host-1", "candidateCounts": {"budgets": 0},
                      "admissionMode": "PREPARATION_ONLY"}
    assert conn.calls[0][1] == ("org-org", "dev-project")


def test_green_report_carries_exact_physical_authority_and_signed_paths(gate, monkeypatch):
    signed = {"database": "aos_current_preview_20260927", "installationId": "current-install",
              "signedRoot": "/signed/current", "trustRoots": "/signed/trust-roots.json"}
    monkeypatch.setattr(gate, "signed_preflight", lambda **_: ({"dbname": signed["database"]}, signed))
    monkeypatch.setattr(gate, "_runtime_file_dsns", lambda *_a, **_k: ({
        plane: f"dbname={signed['database']} user={plane}"
        for plane in ("directory", "runtime", "web")}, [1, 2, 3, 4, 5]))

    class Conn:
        read_only = False
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def execute(self, _query):
            assert self.read_only is True
            return self
        def fetchone(self):
            return {"server_addr": "172.0.0.2", "server_port": 5432,
                    "database_name": signed["database"]}

    monkeypatch.setattr(gate.psycopg, "connect", lambda *_a, **_k: Conn())
    roles = {"directory": identity("directory", 1, directory=True),
             "runtime": identity("runtime", 2, runtime=True),
             "web": identity("web", 3)}
    monkeypatch.setattr(gate, "probe_runtime_database_identity",
                        lambda conn, **kw: roles.pop(next(iter(roles))))
    monkeypatch.setattr(gate, "require_current_host_and_candidates",
                        lambda *_, **__: {"hostId": "host-1", "candidateCounts": {"budgets": 1},
                                          "admissionMode": "FULL"})
    report = gate.preflight(signed_receipt=Path("/signed/receipt.json"),
                            credential_file=Path("/protected/identities.json"))
    assert report["databaseAuthority"] == ["172.0.0.2", 5432, signed["database"]]
    assert report["signedRoot"] == signed["signedRoot"]
    assert report["trustRoots"] == signed["trustRoots"]
    assert report["credentialFileGeneration"] == [1, 2, 3, 4, 5]
    assert report["authorization"] == "PREFLIGHT_ONLY_NO_RUNTIME_START"
    generations = iter(([1, 2, 3, 4, 5], [1, 2, 3, 4, 6]))
    monkeypatch.setattr(gate, "_runtime_file_dsns", lambda *_a, **_k: ({
        plane: f"dbname={signed['database']} user={plane}"
        for plane in ("directory", "runtime", "web")}, next(generations)))
    roles = {"directory": identity("directory", 1, directory=True),
             "runtime": identity("runtime", 2, runtime=True),
             "web": identity("web", 3)}
    monkeypatch.setattr(gate, "probe_runtime_database_identity",
                        lambda conn, **kw: roles.pop(next(iter(roles))))
    with pytest.raises(gate.HostPreflightBlocked, match="CREDENTIAL_FILE_CHANGED"):
        gate.preflight(signed_receipt=Path("/signed/receipt.json"),
                       credential_file=Path("/protected/identities.json"))
