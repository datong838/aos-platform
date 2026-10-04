"""Formal uninstall command login must fail before any privileged fallback."""

import json

import psycopg
import pytest

from aos_api.asset_registry.uninstall_command_connection import (
    CREDENTIAL_FILE,
    connect_uninstall_command,
)


def test_missing_formal_credential_fails_closed(monkeypatch):
    monkeypatch.delenv(CREDENTIAL_FILE, raising=False)
    with pytest.raises(RuntimeError, match="uninstall command identity"):
        with connect_uninstall_command():
            pytest.fail("uninstall command connected without formal identity")


@pytest.mark.parametrize("defect", ("wide-mode", "symlink", "duplicate-field", "web-dsn", "hostaddr", "session-options", "wrong-target", "role-drift"))
def test_untrusted_command_identity_fails_before_connect(tmp_path, monkeypatch, defect):
    web_dsn = "postgresql://web@127.0.0.1:18432/postgres"
    monkeypatch.setenv("AOS_DATABASE_URL", web_dsn)
    identity = {
        "schemaVersion": "aos.installation-uninstall-command-identity/v1",
        "role": "dedicated_install_command",
        "dsn": web_dsn if defect == "web-dsn"
        else "postgresql://dedicated_install_command@127.0.0.1:18432/postgres",
    }
    if defect == "hostaddr":
        identity["dsn"] += "?hostaddr=127.0.0.2"
    if defect == "session-options":
        identity["dsn"] += "?options=-csearch_path%3Devil"
    if defect == "wrong-target":
        identity["dsn"] = identity["dsn"].replace(":18432/", ":18433/")
    if defect == "role-drift":
        identity["role"] = "another_command_role"
    target = tmp_path / "identity.json"
    content = json.dumps(identity)
    if defect == "duplicate-field":
        content = content[:-1] + ',"role":"dedicated_install_command"}'
    target.write_text(content)
    target.chmod(0o644 if defect == "wide-mode" else 0o600)
    if defect == "symlink":
        link = tmp_path / "link.json"
        link.symlink_to(target)
        target = link
    monkeypatch.setenv(CREDENTIAL_FILE, str(target))
    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: pytest.fail("untrusted identity opened a database connection"))
    with pytest.raises(RuntimeError, match="uninstall command identity"):
        with connect_uninstall_command():
            pytest.fail("untrusted identity reached connection body")
