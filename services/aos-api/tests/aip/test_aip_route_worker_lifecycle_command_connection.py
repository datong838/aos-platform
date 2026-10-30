"""Dedicated Route worker lifecycle command identity must fail closed."""

import json

import psycopg
import pytest

from aos_api.aip_route_worker_lifecycle_command_connection import (
    CREDENTIAL_FILE,
    connect_route_worker_lifecycle_command,
)


class _Cursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _Connection:
    def __init__(self, row):
        self.row = row
        self.read_only = False
        self.commits = 0
        self.rollbacks = 0
        self.parameters = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, _query, parameters):
        assert self.read_only is True
        self.parameters = parameters
        return _Cursor(self.row)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _identity_file(tmp_path, *, dsn=None, role="route_worker_lifecycle_login"):
    path = tmp_path / "route-worker-command.json"
    path.write_text(
        json.dumps(
            {
                "schemaVersion": "aos.route-worker-lifecycle-command-identity/v1",
                "role": role,
                "dsn": dsn
                or "postgresql://route_worker_lifecycle_login@127.0.0.1:18432/postgres",
            }
        )
    )
    path.chmod(0o600)
    return path


def _permitted_row():
    return {
        "session_name": "route_worker_lifecycle_login",
        "current_name": "route_worker_lifecycle_login",
        "database_name": "postgres",
        "rolcanlogin": True,
        "rolinherit": False,
        "rolsuper": False,
        "rolbypassrls": False,
        "rolcreaterole": False,
        "rolcreatedb": False,
        "rolreplication": False,
        "runtime_member": False,
        "runtime_usage": False,
        "runtime_set": False,
        "app_member": False,
        "app_usage": False,
        "app_set": False,
        "extra_roles": 0,
        "schema_usage": True,
        "schema_create": False,
        "command_select": True,
        "command_insert": True,
        "command_update": False,
        "command_delete": False,
        "command_truncate": False,
        "command_references": False,
        "command_trigger": False,
        "rls_enabled": True,
        "rls_forced": True,
        "exact_policy": True,
        "other_table_writes": 0,
        "sequence_access": 0,
    }


def test_missing_formal_credential_fails_closed(monkeypatch):
    monkeypatch.delenv(CREDENTIAL_FILE, raising=False)
    with pytest.raises(RuntimeError, match="lifecycle command identity"):
        with connect_route_worker_lifecycle_command():
            pytest.fail("command connected without a formal identity")


@pytest.mark.parametrize(
    "defect",
    (
        "wide-mode",
        "symlink",
        "duplicate-field",
        "web-dsn",
        "hostaddr",
        "session-options",
        "wrong-target",
        "role-drift",
    ),
)
def test_untrusted_identity_fails_before_connect(tmp_path, monkeypatch, defect):
    web_dsn = "postgresql://web@127.0.0.1:18432/postgres"
    monkeypatch.setenv("AOS_DATABASE_URL", web_dsn)
    command_dsn = (
        web_dsn
        if defect == "web-dsn"
        else "postgresql://route_worker_lifecycle_login@127.0.0.1:18432/postgres"
    )
    if defect == "hostaddr":
        command_dsn += "?hostaddr=127.0.0.2"
    if defect == "session-options":
        command_dsn += "?options=-csearch_path%3Devil"
    if defect == "wrong-target":
        command_dsn = command_dsn.replace(":18432/", ":18433/")
    role = (
        "another_route_worker_login"
        if defect == "role-drift"
        else "route_worker_lifecycle_login"
    )
    target = _identity_file(tmp_path, dsn=command_dsn, role=role)
    if defect == "duplicate-field":
        content = target.read_text()
        target.write_text(content[:-1] + ',"role":"route_worker_lifecycle_login"}')
    target.chmod(0o644 if defect == "wide-mode" else 0o600)
    if defect == "symlink":
        link = tmp_path / "link.json"
        link.symlink_to(target)
        target = link
    monkeypatch.setenv(CREDENTIAL_FILE, str(target))
    monkeypatch.setattr(
        psycopg,
        "connect",
        lambda *_args, **_kwargs: pytest.fail(
            "untrusted identity opened a database connection"
        ),
    )

    with pytest.raises(RuntimeError, match="lifecycle command identity"):
        with connect_route_worker_lifecycle_command():
            pytest.fail("untrusted identity reached the command body")


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("rolinherit", True),
        ("rolsuper", True),
        ("runtime_member", True),
        ("app_usage", True),
        ("extra_roles", 1),
        ("schema_create", True),
        ("command_insert", False),
        ("command_update", True),
        ("rls_enabled", False),
        ("rls_forced", False),
        ("exact_policy", False),
        ("other_table_writes", 1),
        ("sequence_access", 1),
    ),
)
def test_over_privileged_or_unscoped_connection_is_rejected(
    tmp_path, monkeypatch, field, value
):
    monkeypatch.setenv(
        "AOS_DATABASE_URL", "postgresql://web@127.0.0.1:18432/postgres"
    )
    target = _identity_file(tmp_path)
    monkeypatch.setenv(CREDENTIAL_FILE, str(target))
    row = _permitted_row()
    row[field] = value
    connection = _Connection(row)
    monkeypatch.setattr(psycopg, "connect", lambda *_args, **_kwargs: connection)

    with pytest.raises(RuntimeError, match="identity is not permitted"):
        with connect_route_worker_lifecycle_command():
            pytest.fail("unsafe identity reached the command body")

    assert connection.rollbacks == 1
    assert connection.read_only is True


def test_permitted_identity_is_read_only_until_verification_completes(
    tmp_path, monkeypatch
):
    monkeypatch.setenv(
        "AOS_DATABASE_URL", "postgresql://web@127.0.0.1:18432/postgres"
    )
    target = _identity_file(tmp_path)
    monkeypatch.setenv(CREDENTIAL_FILE, str(target))
    connection = _Connection(_permitted_row())
    monkeypatch.setattr(psycopg, "connect", lambda *_args, **_kwargs: connection)

    with connect_route_worker_lifecycle_command() as yielded:
        assert yielded is connection
        assert connection.read_only is False

    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.parameters[0:2] == ("public", "public")
    assert connection.parameters[2:9] == (
        "public.bundle_installation_command",
    ) * 7
    assert connection.parameters[9:12] == (
        "route_worker_lifecycle_command_scope",
        "((org_id = 'org-org'::text) AND (project_id = 'dev-project'::text))",
        "((org_id = 'org-org'::text) AND (project_id = 'dev-project'::text))",
    )
    assert connection.parameters[12:] == (
        "public",
        "public",
        "public",
        "bundle_installation_command",
    )
