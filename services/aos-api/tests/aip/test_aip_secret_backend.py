from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from aos_api import aip_secret_backend
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_model_runtime_contracts import (
    ModelRuntimeLifecycle,
    ProviderEndpointProfile,
    ProviderInstanceRevision,
)
from aos_api.aip_secret_backend import (
    DeferredMountedSecretFileClient,
    ExactSecretResolver,
    KeychainLocator,
    MacOSKeychainClient,
    MountedSecretFileClient,
    SecretBackendError,
    SecretProbeResult,
    default_secret_client,
    parse_keychain_ref,
)
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 17, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
SECRET_REF = (
    "keychain://com.aos.llm/agnes-text/org-org/dev-project/agnes-text-qyh-dev#api-key"
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
        return subprocess.CompletedProcess(
            argv, 0, stdout="sensitive-value\n", stderr=""
        )

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


def mounted_secret(tmp_path: Path, *, mode: int = 0o400, value: bytes = b"secret\n"):
    locator = parse_keychain_ref(SECRET_REF, SCOPE, provider())
    path = tmp_path / locator.service
    for segment in locator.account.split("/")[:-1]:
        path /= segment
    path.mkdir(parents=True)
    target = path / locator.account.split("/")[-1]
    target.write_bytes(value)
    target.chmod(mode)
    return locator, target


@pytest.mark.parametrize("mode", [0o400, 0o600])
def test_mounted_secret_reads_one_exact_private_file(tmp_path: Path, mode: int) -> None:
    locator, _ = mounted_secret(tmp_path, mode=mode)
    client = MountedSecretFileClient(tmp_path)

    assert client.exists(locator) is True
    assert client.read(locator) == "secret"


def test_mounted_secret_missing_probe_does_not_read_payload(tmp_path: Path) -> None:
    locator = parse_keychain_ref(SECRET_REF, SCOPE, provider())
    client = MountedSecretFileClient(tmp_path)

    assert client.exists(locator) is False


@pytest.mark.parametrize("mode", [0o440, 0o404, 0o666])
def test_mounted_secret_rejects_non_private_file(tmp_path: Path, mode: int) -> None:
    locator, _ = mounted_secret(tmp_path, mode=mode)

    with pytest.raises(SecretBackendError, match="secret_file_invalid"):
        MountedSecretFileClient(tmp_path).read(locator)


def test_mounted_secret_rejects_symlink_file(tmp_path: Path) -> None:
    locator, target = mounted_secret(tmp_path)
    private = tmp_path / "private"
    target.rename(private)
    target.symlink_to(private)

    with pytest.raises(SecretBackendError, match="secret_mount_unavailable"):
        MountedSecretFileClient(tmp_path).read(locator)


def test_mounted_secret_rejects_multiple_hard_links(tmp_path: Path) -> None:
    locator, target = mounted_secret(tmp_path)
    (tmp_path / "second-link").hardlink_to(target)

    with pytest.raises(SecretBackendError, match="secret_file_invalid"):
        MountedSecretFileClient(tmp_path).read(locator)


def test_mounted_secret_rejects_writable_intermediate_directory(
    tmp_path: Path,
) -> None:
    locator, _ = mounted_secret(tmp_path)
    (tmp_path / locator.service).chmod(0o777)

    with pytest.raises(SecretBackendError, match="secret_mount_invalid"):
        MountedSecretFileClient(tmp_path).read(locator)


def test_mounted_secret_rejects_invalid_locator_without_type_leak(
    tmp_path: Path,
) -> None:
    locator = KeychainLocator(
        service="com.aos.safe", account="../secret", ref_fingerprint="x" * 64
    )
    with pytest.raises(SecretBackendError, match="secret_locator_invalid"):
        MountedSecretFileClient(tmp_path).exists(locator)

    invalid = KeychainLocator(
        service=123,
        account="safe",
        ref_fingerprint="x" * 64,  # type: ignore[arg-type]
    )
    with pytest.raises(SecretBackendError, match="secret_locator_invalid"):
        MountedSecretFileClient(tmp_path).exists(invalid)


def test_mounted_secret_rejects_writable_root_and_symlink_root(tmp_path: Path) -> None:
    tmp_path.chmod(0o777)
    with pytest.raises(SecretBackendError, match="secret_mount_invalid"):
        MountedSecretFileClient(tmp_path)
    tmp_path.chmod(0o700)
    alias = tmp_path.parent / f"{tmp_path.name}-alias"
    alias.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(SecretBackendError, match="secret_mount_invalid"):
        MountedSecretFileClient(alias)


def test_mounted_secret_rejects_relative_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path.parent)
    with pytest.raises(SecretBackendError, match="secret_mount_invalid"):
        MountedSecretFileClient(tmp_path.name)


@pytest.mark.parametrize(
    ("value", "code"),
    [
        (b"", "secret_file_invalid"),
        (b"\xff", "secret_file_encoding_invalid"),
        (b"\x00", "secret_file_empty"),
    ],
)
def test_mounted_secret_rejects_invalid_payload(
    tmp_path: Path, value: bytes, code: str
) -> None:
    locator, _ = mounted_secret(tmp_path, value=value)
    with pytest.raises(SecretBackendError, match=code):
        MountedSecretFileClient(tmp_path).read(locator)


def test_mounted_secret_rejects_oversized_payload(tmp_path: Path) -> None:
    locator, _ = mounted_secret(tmp_path, value=b"x" * 65_537)
    with pytest.raises(SecretBackendError, match="secret_file_invalid"):
        MountedSecretFileClient(tmp_path).read(locator)


def test_mounted_secret_rejects_file_changed_during_read(
    tmp_path: Path, monkeypatch
) -> None:
    locator, target = mounted_secret(tmp_path, mode=0o600)
    original_read = aip_secret_backend.os.read
    changed = False

    def read_and_touch(descriptor: int, size: int) -> bytes:
        nonlocal changed
        payload = original_read(descriptor, size)
        if payload and not changed:
            changed = True
            metadata = target.stat()
            aip_secret_backend.os.utime(
                target,
                ns=(metadata.st_atime_ns, metadata.st_mtime_ns + 1_000_000_000),
            )
        return payload

    monkeypatch.setattr(aip_secret_backend.os, "read", read_and_touch)
    with pytest.raises(SecretBackendError, match="secret_file_changed"):
        MountedSecretFileClient(tmp_path).read(locator)


def test_default_secret_client_keeps_macos_and_requires_linux_mount(
    tmp_path: Path,
) -> None:
    assert isinstance(default_secret_client(system_name="Darwin"), MacOSKeychainClient)
    deferred = default_secret_client(system_name="Linux", environ={})
    assert isinstance(deferred, DeferredMountedSecretFileClient)
    locator = parse_keychain_ref(SECRET_REF, SCOPE, provider())
    with pytest.raises(SecretBackendError, match="secret_mount_required"):
        deferred.exists(locator)
    configured = default_secret_client(
        system_name="Linux", environ={"AOS_SECRET_MOUNT_ROOT": str(tmp_path)}
    )
    assert isinstance(configured, DeferredMountedSecretFileClient)
    with pytest.raises(SecretBackendError, match="secret_backend_unsupported"):
        default_secret_client(system_name="Windows", environ={})
