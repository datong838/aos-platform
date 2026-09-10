"""Fail-closed contract tests for the A0-V text Provider executor."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_real_text_provider_authority.py"
SPEC = importlib.util.spec_from_file_location("a0v_real_text_provider", SCRIPT)
assert SPEC and SPEC.loader
AUTHORITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUTHORITY)


def test_preflight_fixes_scope_provider_and_zero_external_effects():
    result = AUTHORITY.run(AUTHORITY.parse_args([]))

    assert result["outcome"] == "PREFLIGHT_GREEN"
    assert result["scope"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert result["provider"] == {
        "assetId": "a0v-agnes-text-readonly-dev",
        "revision": 1,
        "pluginId": "agnes-text",
        "pluginRevision": 3,
        "baseUrl": "https://api.agnes-ai.cn/v1",
        "providerModelId": "agnes-2.5-flash",
        "secretVersion": "a0v-v1",
    }
    assert result["effects"]["providerInvocationCount"] == 0
    assert result["effects"]["businessMutationCount"] == 0


def test_apply_requires_exact_isolated_database_before_env_or_connector(monkeypatch):
    monkeypatch.setattr(
        AUTHORITY,
        "_load_env",
        lambda _path: (_ for _ in ()).throw(AssertionError("env loaded")),
    )
    with pytest.raises(AUTHORITY.ProviderAuthorityBlocked) as captured:
        AUTHORITY.run(AUTHORITY.parse_args(["--apply", "--database-name", "aos_meta"]))
    assert captured.value.code == "EXPLICIT_ISOLATED_DATABASE_REQUIRED"


def test_env_validation_returns_settings_only_in_process_and_blocks_drift(tmp_path):
    secret = "never-print-this-secret"
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AGNES_API_KEY=" + secret + "\n"
        "AGNES_BASE_URL=https://api.agnes-ai.cn/v1\n"
        "AGNES_TEXT_MODEL=agnes-2.5-flash\n",
        encoding="utf-8",
    )
    assert AUTHORITY._load_env(env_file)["AGNES_API_KEY"] == secret

    env_file.write_text(
        "AGNES_API_KEY=" + secret + "\n"
        "AGNES_BASE_URL=https://example.invalid/v1\n"
        "AGNES_TEXT_MODEL=agnes-2.5-flash\n",
        encoding="utf-8",
    )
    with pytest.raises(AUTHORITY.ProviderAuthorityBlocked) as captured:
        AUTHORITY._load_env(env_file)
    assert captured.value.code == "AGNES_BASE_URL_DRIFTED"
    assert secret not in str(captured.value)


def test_keychain_write_uses_private_input_and_never_places_secret_in_argv():
    secret = "never-place-in-process-list"
    received = []

    AUTHORITY._install_keychain_secret(secret, writer=received.append)

    assert received == [secret]
    argv = AUTHORITY._keychain_write_argv()
    assert argv[-1] == "-w"
    assert "-U" in argv
    assert secret not in argv


def test_keychain_write_maps_private_tty_failure_without_secret():
    secret = "never-report-this"

    def blocked(_secret):
        raise AUTHORITY.ProviderAuthorityBlocked("KEYCHAIN_WRITE_TIMEOUT")

    with pytest.raises(AUTHORITY.ProviderAuthorityBlocked) as captured:
        AUTHORITY._install_keychain_secret(secret, writer=blocked)
    assert captured.value.code == "KEYCHAIN_WRITE_TIMEOUT"
    assert secret not in str(captured.value)


@pytest.mark.parametrize(("returncode", "expected"), [(0, True), (44, False)])
def test_keychain_probe_has_exact_non_secret_coordinates(returncode, expected):
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, returncode)

    assert AUTHORITY._keychain_exists(runner=runner) is expected
    argv, kwargs = calls[0]
    assert argv == [
        "/usr/bin/security",
        "find-generic-password",
        "-s",
        "com.aos.llm",
        "-a",
        "agnes-text/org-org/dev-project/a0v-agnes-text-readonly-dev/api-key/a0v-v1",
    ]
    assert kwargs["shell"] is False


@pytest.mark.parametrize("returncode", [0, 44])
def test_exact_keychain_delete_accepts_deleted_or_already_absent(returncode):
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, returncode)

    AUTHORITY._delete_keychain_item(runner=runner)
    argv, kwargs = calls[0]
    assert argv == [
        "/usr/bin/security",
        "delete-generic-password",
        "-s",
        "com.aos.llm",
        "-a",
        "agnes-text/org-org/dev-project/a0v-agnes-text-readonly-dev/api-key/a0v-v1",
    ]
    assert kwargs["shell"] is False
