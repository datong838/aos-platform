from __future__ import annotations

import subprocess
from datetime import UTC, datetime

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_model_runtime_contracts import (
    ModelRuntimeLifecycle,
    ProviderEndpointProfile,
    ProviderInstanceRevision,
)
from aos_api.aip_secret_backend import (
    ExactSecretResolver,
    MacOSKeychainClient,
    SecretBackendError,
    SecretProbeResult,
    parse_keychain_ref,
)
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 17, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
SECRET_REF = (
    "keychain://com.aos.llm/agnes-text/org-org/dev-project/"
    "agnes-text-qyh-dev#api-key"
)


def ref(kind: str, asset_id: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        assetType=kind,
        assetId=asset_id,
        revision=1,
        contentHash="a" * 64,
    )


def provider(
    *,
    org_id: str = "org-org",
    project_id: str = "dev-project",
    plugin_id: str = "agnes-text",
    provider_id: str = "agnes-text-qyh-dev",
    secret_ref: str = SECRET_REF,
    secret_version: str = "v1",
) -> ProviderInstanceRevision:
    return ProviderInstanceRevision(
        tenant={"orgId": org_id, "projectId": project_id},
        providerInstanceId=provider_id,
        revision=1,
        contentHash="b" * 64,
        pluginRef=ref("ProviderPluginRevision", plugin_id),
        endpointProfile=ProviderEndpointProfile(
            baseUrl="https://apihub.agnes-ai.com/v1",
            region="development-external-unspecified",
            timeoutMs=30_000,
        ),
        secretRef=secret_ref,
        secretVersion=secret_version,
        egressPolicyRef=ref("EgressPolicyRevision", "agnes-egress-dev"),
        dataClassificationPolicyRef=ref(
            "DataClassificationPolicyRevision", "agnes-data-dev"
        ),
        lifecycle=ModelRuntimeLifecycle.VALIDATED,
        createdBy="owner",
        createdAt=NOW,
    )


def test_parse_approved_keychain_ref_derives_stable_non_secret_locator() -> None:
    locator = parse_keychain_ref(SECRET_REF, SCOPE, provider())

    assert locator.service == "com.aos.llm"
    assert locator.account == (
        "agnes-text/org-org/dev-project/agnes-text-qyh-dev/api-key/v1"
    )
    assert len(locator.ref_fingerprint) == 64
    assert SECRET_REF not in repr(locator)


@pytest.mark.parametrize("version", ["", ".", "..", "v1/other", "v%31", "v\n1"])
def test_secret_version_must_be_a_safe_exact_account_segment(version: str) -> None:
    item = provider().model_copy(update={"secret_version": version})

    with pytest.raises(SecretBackendError, match="invalid_secret_version"):
        parse_keychain_ref(SECRET_REF, SCOPE, item)


@pytest.mark.parametrize(
    ("scope", "item", "code"),
    [
        (TenantScope("dev-org", "dev-project"), provider(), "scope_mismatch"),
        (SCOPE, provider(org_id="dev-org"), "provider_tenant_mismatch"),
        (SCOPE, provider(plugin_id="other-plugin"), "plugin_ref_mismatch"),
        (SCOPE, provider(provider_id="other-provider"), "provider_ref_mismatch"),
    ],
)
def test_exact_identity_drift_is_fail_closed(
    scope: TenantScope,
    item: ProviderInstanceRevision,
    code: str,
) -> None:
    with pytest.raises(SecretBackendError) as captured:
        parse_keychain_ref(SECRET_REF, scope, item)

    assert captured.value.code == code
    assert SECRET_REF not in str(captured.value)


@pytest.mark.parametrize(
    "secret_ref",
    [
        "vault://com.aos.llm/agnes-text/org-org/dev-project/agnes-text-qyh-dev#api-key",
        "keychain://user@com.aos.llm/agnes-text/org-org/dev-project/agnes-text-qyh-dev#api-key",
        "keychain://com.aos.llm/agnes-text/org-org/dev-project/agnes-text-qyh-dev?x=1#api-key",
        "keychain://com.aos.llm/agnes-text/org-org/dev-project/agnes-text-qyh-dev#token",
        "keychain://com.aos.llm/agnes-text/org-org/../agnes-text-qyh-dev#api-key",
        "keychain://com.aos.llm/agnes-text/org-org/dev-project/%2e%2e#api-key",
        "keychain://com.aos.llm/agnes-text/org-org/dev-project/agnes%0atext#api-key",
        "keychain://com.aos.llm/agnes-text/org-org/dev-project#api-key",
    ],
)
def test_malformed_or_ambiguous_ref_is_rejected(secret_ref: str) -> None:
    with pytest.raises(SecretBackendError) as captured:
        parse_keychain_ref(secret_ref, SCOPE, provider(secret_ref=secret_ref))

    assert captured.value.code == "invalid_secret_ref"
    assert secret_ref not in str(captured.value)


def test_macos_client_uses_fixed_argv_without_shell() -> None:
    calls: list[tuple[list[str], dict]] = []

    def runner(argv: list[str], **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="sensitive-value\n", stderr="")

    locator = parse_keychain_ref(SECRET_REF, SCOPE, provider())
    result = MacOSKeychainClient(runner=runner).read(locator)

    assert result == "sensitive-value"
    assert calls == [
        (
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                "com.aos.llm",
                "-a",
                "agnes-text/org-org/dev-project/agnes-text-qyh-dev/api-key/v1",
                "-w",
            ],
            {
                "capture_output": True,
                "check": False,
                "shell": False,
                "text": True,
                "timeout": 5.0,
            },
        )
    ]


@pytest.mark.parametrize(("returncode", "exists"), [(0, True), (44, False)])
def test_macos_probe_checks_versioned_item_without_reading_output(
    returncode: int,
    exists: bool,
) -> None:
    calls: list[tuple[list[str], dict]] = []

    def runner(argv: list[str], **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, returncode)

    locator = parse_keychain_ref(SECRET_REF, SCOPE, provider())
    assert MacOSKeychainClient(runner=runner).exists(locator) is exists
    assert calls == [
        (
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                "com.aos.llm",
                "-a",
                "agnes-text/org-org/dev-project/agnes-text-qyh-dev/api-key/v1",
            ],
            {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "check": False,
                "shell": False,
                "timeout": 5.0,
            },
        )
    ]


@pytest.mark.parametrize("failure", ["timeout", "unavailable", "unexpected"])
def test_macos_probe_fails_closed_on_operational_errors(failure: str) -> None:
    secret = "must-never-leak"

    def runner(argv: list[str], **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"], output=secret)
        if failure == "unavailable":
            raise OSError(secret)
        return subprocess.CompletedProcess(argv, 1)

    locator = parse_keychain_ref(SECRET_REF, SCOPE, provider())
    with pytest.raises(SecretBackendError) as captured:
        MacOSKeychainClient(runner=runner).exists(locator)

    assert captured.value.code in {
        "keychain_timeout",
        "keychain_command_unavailable",
        "keychain_probe_failed",
    }
    assert secret not in str(captured.value)
    assert SECRET_REF not in str(captured.value)


@pytest.mark.parametrize("failure", ["missing", "timeout", "empty", "unavailable"])
def test_keychain_client_maps_failures_without_leaking_payload(failure: str) -> None:
    secret = "must-never-leak"

    def runner(argv: list[str], **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"], output=secret)
        if failure == "unavailable":
            raise OSError(secret)
        if failure == "empty":
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr=secret)
        return subprocess.CompletedProcess(argv, 44, stdout="", stderr=secret)

    locator = parse_keychain_ref(SECRET_REF, SCOPE, provider())
    with pytest.raises(SecretBackendError) as captured:
        MacOSKeychainClient(runner=runner).read(locator)

    assert captured.value.code in {
        "keychain_item_unavailable",
        "keychain_timeout",
        "keychain_empty",
        "keychain_command_unavailable",
    }
    assert secret not in str(captured.value)
    assert SECRET_REF not in str(captured.value)
    assert captured.value.__cause__ is None
    if failure in {"timeout", "unavailable"}:
        assert captured.value.__suppress_context__ is True
    else:
        assert captured.value.__context__ is None


def test_exact_resolver_returns_secret_only_after_identity_validation() -> None:
    class Client:
        def __init__(self) -> None:
            self.locator = None

        def read(self, locator):
            self.locator = locator
            return "resolved-secret"

    client = Client()
    resolver = ExactSecretResolver(client=client)

    assert resolver.resolve(SCOPE, provider()) == "resolved-secret"
    assert client.locator.account.endswith("agnes-text-qyh-dev/api-key/v1")

    with pytest.raises(SecretBackendError, match="scope_mismatch"):
        resolver.resolve(TenantScope("dev-org", "dev-project"), provider())


def test_probe_returns_only_non_sensitive_exact_metadata() -> None:
    class Client:
        def __init__(self) -> None:
            self.locator = None

        def exists(self, locator):
            self.locator = locator
            return True

    client = Client()
    result = ExactSecretResolver(client=client).probe(SCOPE, provider())

    assert result == SecretProbeResult(
        exists=True,
        ref_fingerprint=client.locator.ref_fingerprint,
        secret_version="v1",
    )
    assert SECRET_REF not in repr(result)
    assert "top-secret" not in repr(result)


def test_probe_rejects_negative_tenant_before_keychain_command() -> None:
    class Client:
        def exists(self, _locator):
            raise AssertionError("Keychain must not be called")

    resolver = ExactSecretResolver(client=Client())
    with pytest.raises(SecretBackendError, match="scope_mismatch"):
        resolver.probe(TenantScope("dev-org", "dev-project"), provider())
