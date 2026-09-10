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


class _FakeFunction:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        return self.result


class _FakeSecurity:
    def __init__(self, find_status):
        self.SecKeychainFindGenericPassword = _FakeFunction(find_status)
        self.SecKeychainItemModifyAttributesAndData = _FakeFunction(0)
        self.SecKeychainAddGenericPassword = _FakeFunction(0)


class _FakeCore:
    def __init__(self):
        self.CFRelease = _FakeFunction(None)


def test_keychain_write_uses_security_framework_memory_not_subprocess():
    secret = "never-place-in-process-list"
    security = _FakeSecurity(-25300)
    core = _FakeCore()

    AUTHORITY._install_keychain_secret(secret, frameworks=(security, core))

    assert not security.SecKeychainItemModifyAttributesAndData.calls
    call = security.SecKeychainAddGenericPassword.calls[0]
    assert call[6] == secret.encode("utf-8")
    assert not any(isinstance(value, str) and secret in value for value in call)


def test_keychain_write_repairs_same_identity_item_in_place():
    security = _FakeSecurity(0)
    core = _FakeCore()
    AUTHORITY._install_keychain_secret("replacement", frameworks=(security, core))
    assert security.SecKeychainItemModifyAttributesAndData.calls
    assert not security.SecKeychainAddGenericPassword.calls


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
