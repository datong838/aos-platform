"""Fail-closed tests for the standalone A0-V ecommerce Runtime Host."""
from __future__ import annotations

import importlib.util
import argparse
import asyncio
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ecommerce_runtime_host.py"
SPEC = importlib.util.spec_from_file_location("a0v_ecommerce_runtime_host", SCRIPT)
assert SPEC and SPEC.loader
HOST = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOST)


def _credential_file(path: Path) -> tuple[Path, dict[str, dict[str, str]]]:
    value = {
        plane: {"role": role, "password": f"secret-{plane}", "dsn": f"dsn-{plane}"}
        for plane, role in HOST.EXPECTED_ROLES.items()
    }
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    return path, value


def test_credentials_require_private_exact_roles(tmp_path: Path) -> None:
    path, expected = _credential_file(tmp_path / "identities.json")
    assert HOST._load_credentials(path) == expected
    path.chmod(0o644)
    with pytest.raises(HOST.HostBlocked) as captured:
        HOST._load_credentials(path)
    assert captured.value.code == "CREDENTIAL_FILE_INVALID"


def test_environment_uses_three_distinct_planes(tmp_path: Path, monkeypatch) -> None:
    path, credentials = _credential_file(tmp_path / "identities.json")
    bundle = tmp_path / "bundles"
    bundle.mkdir()
    trust = tmp_path / "trust.json"
    trust.write_text("{}")
    for key in (
        "AOS_DATABASE_URL", "AOS_EXTENSION_RUNTIME_DATABASE_URL",
        "AOS_EXTENSION_DIRECTORY_DATABASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)

    HOST._configure_environment(
        HOST._load_credentials(path), bundle_root=bundle, trust_roots_file=trust
    )

    assert os.environ["AOS_DATABASE_URL"] == credentials["web"]["dsn"]
    assert os.environ["AOS_EXTENSION_RUNTIME_DATABASE_URL"] == credentials["runtime"]["dsn"]
    assert os.environ["AOS_EXTENSION_DIRECTORY_DATABASE_URL"] == credentials["directory"]["dsn"]
    assert os.environ["AOS_EXTENSION_RUNTIME_HOST_ENABLED"] == "1"
    assert os.environ["AOS_DOTENV_DISABLED"] == "1"


def test_invalid_interval_fails_before_loading_credentials(tmp_path: Path, monkeypatch) -> None:
    status = tmp_path / "status.json"
    monkeypatch.setattr(
        HOST, "_load_credentials",
        lambda _path: (_ for _ in ()).throw(AssertionError("credentials loaded")),
    )
    assert HOST.main([
        "--bundle-root", str(tmp_path), "--trust-roots-file", str(tmp_path / "missing"),
        "--status-file", str(status), "--interval-seconds", "0",
    ]) == 2
    assert json.loads(status.read_text()) == {
        "outcome": "SAFE_BLOCKED", "reasonCode": "INTERVAL_INVALID"
    }


def test_serve_records_active_then_clean_stop(tmp_path: Path, monkeypatch) -> None:
    credential_path, _credentials = _credential_file(tmp_path / "identities.json")
    bundle = tmp_path / "bundles"
    bundle.mkdir()
    trust = tmp_path / "trust.json"
    trust.write_text("{}")
    status = tmp_path / "status.json"

    class Host:
        async def serve(self, stop_event, *, interval_seconds):
            assert isinstance(stop_event, asyncio.Event)
            assert interval_seconds == 3

    monkeypatch.setattr(HOST, "_build_host", lambda: Host())
    asyncio.run(HOST._serve(argparse.Namespace(
        credential_file=credential_path,
        bundle_root=bundle,
        trust_roots_file=trust,
        status_file=status,
        interval_seconds=3,
    )))

    result = json.loads(status.read_text())
    assert result["outcome"] == "RUNTIME_HOST_STOPPED"
    assert result["tenantCount"] == 1
    assert result["canaryTenantCount"] == 0
