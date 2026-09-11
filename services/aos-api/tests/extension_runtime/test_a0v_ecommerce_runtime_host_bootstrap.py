"""Fail-closed tests for the local production runtime-host bootstrap."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ecommerce_runtime_host_bootstrap.py"
SPEC = importlib.util.spec_from_file_location("runtime_host_bootstrap", SCRIPT)
assert SPEC and SPEC.loader
BOOTSTRAP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BOOTSTRAP)


def test_credentials_are_private_and_replay_exactly(tmp_path: Path) -> None:
    path = tmp_path / "state/runtime-host-identities.json"
    parameters = {"host": "127.0.0.1", "port": "18435"}

    first = BOOTSTRAP._credentials(path, parameters=parameters, create=True)
    second = BOOTSTRAP._credentials(path, parameters=parameters, create=True)

    assert second == first
    assert path.stat().st_mode & 0o777 == 0o600
    assert set(first) == set(BOOTSTRAP.ROLES)
    assert len({item["password"] for item in first.values()}) == 3
    assert all(item["password"] not in str(path) for item in first.values())


def test_missing_credentials_preflight_does_not_create_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    assert BOOTSTRAP._credentials(
        path, parameters={"host": "127.0.0.1", "port": "1"}, create=False
    ) == {}
    assert not path.exists()


def test_exact_snapshot_rejects_membership_and_canary_drift() -> None:
    clean = {
        "roles": {"web": None, "runtime": None, "directory": None},
        "identity": None,
        "assignment": None,
        "canaryAssignments": 0,
    }
    BOOTSTRAP._assert_exact(clean, applied=False)
    bad_role = json.loads(json.dumps(clean))
    bad_role["roles"]["runtime"] = {
        "rolcanlogin": True, "rolsuper": False, "rolbypassrls": False,
        "runtime_member": False, "directory_member": False,
    }
    with pytest.raises(BOOTSTRAP.BootstrapBlocked) as captured:
        BOOTSTRAP._assert_exact(bad_role, applied=False)
    assert captured.value.code == "LOGIN_ROLE_DRIFT"

    canary = {**clean, "canaryAssignments": 1}
    with pytest.raises(BOOTSTRAP.BootstrapBlocked) as captured:
        BOOTSTRAP._assert_exact(canary, applied=False)
    assert captured.value.code == "CANARY_ASSIGNMENT_PRESENT"


def test_apply_requires_exact_database_before_loading_connector(monkeypatch) -> None:
    monkeypatch.setattr(
        BOOTSTRAP, "_load_first",
        lambda: (_ for _ in ()).throw(AssertionError("connector loaded")),
    )
    with pytest.raises(BOOTSTRAP.BootstrapBlocked) as captured:
        BOOTSTRAP.run(BOOTSTRAP.parse_args(["--apply", "--database-name", "wrong"]))
    assert captured.value.code == "EXPLICIT_ISOLATED_DATABASE_REQUIRED"


def test_main_records_unexpected_failure(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "result.json"
    monkeypatch.setattr(
        BOOTSTRAP, "run",
        lambda _args: (_ for _ in ()).throw(ValueError("unexpected")),
    )
    assert BOOTSTRAP.main(["--output", str(output)]) == 2
    assert json.loads(output.read_text())["reasonCode"] == "UNEXPECTED_DOMAIN_ERROR"


def test_backup_replays_existing_nonempty_dump_without_docker(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "backups/aos_meta_head-pre-runtime-host-bootstrap.dump"
    target.parent.mkdir()
    target.write_bytes(b"existing-backup")
    monkeypatch.setattr(
        BOOTSTRAP.subprocess, "check_output",
        lambda *_args, **_kwargs: '{"Config":{"Env":[]}}',
    )
    monkeypatch.setattr(
        BOOTSTRAP.subprocess, "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pg_dump called")),
    )
    result = BOOTSTRAP._backup(tmp_path)
    assert result["size"] == len(b"existing-backup")
    assert result["sha256"] == BOOTSTRAP._sha(b"existing-backup")


def test_provision_binds_identity_and_assignment() -> None:
    class Result:
        @staticmethod
        def fetchone():
            return (1,)

    class Connection:
        def __init__(self) -> None:
            self.calls: list[tuple[object, object]] = []

        def execute(self, statement, parameters=None):
            self.calls.append((statement, parameters))
            return Result()

    connection = Connection()
    credentials = {
        plane: {"password": f"{plane}-password"}
        for plane in BOOTSTRAP.ROLES
    }

    BOOTSTRAP._provision(connection, credentials)

    statements = [str(statement) for statement, _parameters in connection.calls]
    assert sum("extension_runtime_read_host_assignments" in item for item in statements) == 1
    assert sum("extension_runtime_bind_host_identity" in item for item in statements) == 1
    assert sum("extension_runtime_set_host_assignment" in item for item in statements) == 1
    assignment_parameters = next(
        parameters
        for statement, parameters in connection.calls
        if "extension_runtime_set_host_assignment" in str(statement)
    )
    assert assignment_parameters[:3] == (
        BOOTSTRAP.ORG_ID,
        BOOTSTRAP.PROJECT_ID,
        BOOTSTRAP.HOST_ID,
    )
