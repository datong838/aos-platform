"""E17 Reader maintenance preflight is a clone-only, read-only gate."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from scripts.a0v_e17_reader_maintenance import (  # noqa: E402
    ReaderMaintenanceBlocked,
    _require_catalog,
    _require_private_passfile,
    _require_target,
    main,
)


def _tables():
    from aos_api.aip_binding_readiness_reader_connection import READINESS_READER_TABLES

    return [
        {"relname": name, "relkind": "r", "relrowsecurity": name != "aip_capability_revision",
         "relforcerowsecurity": name != "aip_capability_revision"}
        for name in READINESS_READER_TABLES
    ]


def test_catalog_rejects_missing_table_rls_role_and_policy():
    rows = _tables()
    _require_catalog("a0v_135", rows, 0, 0)
    for changed in (rows[:-1], [*rows[:-1], {**rows[-1], "relforcerowsecurity": False}]):
        with pytest.raises(ReaderMaintenanceBlocked, match="READER_CLONE_CATALOG_REQUIRED"):
            _require_catalog("a0v_135", changed, 0, 0)
    for version, role_count, policy_count in (("a0v_134", 0, 0), ("a0v_135", 1, 0), ("a0v_135", 0, 1)):
        with pytest.raises(ReaderMaintenanceBlocked, match="READER_CLONE_CATALOG_REQUIRED"):
            _require_catalog(version, rows, role_count, policy_count)


def test_target_rejects_current_volume_and_changed_clone():
    from scripts.a0v_e17_reader_maintenance import CLONE_VOLUME

    target = {"Name": "/aos-a0v-test-pg", "State": {"Running": True},
              "Mounts": [{"Name": CLONE_VOLUME, "Destination": "/var/lib/postgresql/data"}],
              "NetworkSettings": {"Ports": {"5432/tcp": [{"HostPort": "5433"}]}},
              "Config": {"Env": ["POSTGRES_USER=aos_app"]}}
    _require_target(target)
    for field, value in (("Mounts", [{"Name": "aos-a0v-recovery-pg-data", "Destination": "/var/lib/postgresql/data"}]),
                         ("Name", "/aos-a0v-recovery-pg")):
        altered = {**target, field: value}
        with pytest.raises(ReaderMaintenanceBlocked, match="READER_CLONE_TARGET_REQUIRED"):
            _require_target(altered)


def test_admin_passfile_must_be_private(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    passfile = private / "admin.pgpass"
    passfile.write_text("placeholder")
    passfile.chmod(0o600)
    _require_private_passfile(passfile)
    passfile.chmod(0o644)
    with pytest.raises(ReaderMaintenanceBlocked, match="READER_ADMIN_PRIVATE_CREDENTIAL_REQUIRED"):
        _require_private_passfile(passfile)
    passfile.chmod(0o600)
    alias = private / "alias.pgpass"
    os.symlink(passfile, alias)
    with pytest.raises(ReaderMaintenanceBlocked, match="READER_ADMIN_PRIVATE_CREDENTIAL_REQUIRED"):
        _require_private_passfile(alias)


def test_cli_requires_explicit_clone_target_and_rejects_apply():
    with pytest.raises(SystemExit) as missing:
        main([])
    assert missing.value.code == 2
    with pytest.raises(SystemExit) as current:
        main(["--target", "current"])
    assert current.value.code == 2
    with pytest.raises(SystemExit) as apply:
        main(["--target", "clone", "--apply-current"])
    assert apply.value.code == 2
