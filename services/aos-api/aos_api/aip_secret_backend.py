"""Fail-closed secret resolution for exact AIP model-runtime providers.

This module intentionally has no environment-variable or legacy-store fallback.
It resolves only an exact opaque reference after tenant, plugin and provider
identity have been matched.  It does not publish runtime authority or imply
that a provider is healthy or runnable.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlsplit

from aos_api.aip_model_runtime_contracts import (
    ModelRuntimeLifecycle,
    ProviderInstanceRevision,
)
from aos_api.tenant_scope import TenantScope


_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ALLOWED_PROVIDER_STATES = {
    ModelRuntimeLifecycle.VALIDATED,
    ModelRuntimeLifecycle.ACTIVE,
}


class SecretBackendError(RuntimeError):
    """Stable fail-closed error that never includes a secret or full ref."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class KeychainLocator:
    """Non-secret Keychain lookup coordinates.

    The original reference is deliberately not retained so dataclass repr and
    debugging tools cannot accidentally disclose it.
    """

    service: str
    account: str
    ref_fingerprint: str


@dataclass(frozen=True)
class SecretProbeResult:
    """Non-sensitive evidence that one exact secret version exists."""

    exists: bool
    ref_fingerprint: str
    secret_version: str


class SecretClient(Protocol):
    def read(self, locator: KeychainLocator) -> str: ...

    def exists(self, locator: KeychainLocator) -> bool: ...


def _safe_segment(value: str) -> bool:
    return bool(_SAFE_SEGMENT.fullmatch(value)) and value not in {".", ".."}


def parse_keychain_ref(
    secret_ref: str,
    scope: TenantScope,
    provider: ProviderInstanceRevision,
) -> KeychainLocator:
    """Validate and bind a Keychain ref to one exact tenant/provider identity."""

    cleaned = secret_ref.strip()
    if (
        not cleaned
        or cleaned != secret_ref
        or len(cleaned) > 512
        or "%" in cleaned
        or any(ord(char) < 32 or ord(char) == 127 for char in cleaned)
    ):
        raise SecretBackendError("invalid_secret_ref")
    try:
        parsed = urlsplit(cleaned)
    except ValueError:
        raise SecretBackendError("invalid_secret_ref") from None
    if (
        parsed.scheme != "keychain"
        or not parsed.netloc
        or parsed.query
        or parsed.fragment != "api-key"
        or not _safe_segment(parsed.netloc)
    ):
        raise SecretBackendError("invalid_secret_ref")

    parts = parsed.path.split("/")
    if len(parts) != 5 or parts[0] != "" or any(
        not _safe_segment(part) for part in parts[1:]
    ):
        raise SecretBackendError("invalid_secret_ref")
    plugin_id, org_id, project_id, provider_id = parts[1:]

    if (org_id, project_id) != scope.key:
        raise SecretBackendError("scope_mismatch")
    if (provider.tenant.org_id, provider.tenant.project_id) != scope.key:
        raise SecretBackendError("provider_tenant_mismatch")
    if provider.plugin_ref.asset_id != plugin_id:
        raise SecretBackendError("plugin_ref_mismatch")
    if provider.provider_instance_id != provider_id:
        raise SecretBackendError("provider_ref_mismatch")
    if provider.secret_ref != cleaned:
        raise SecretBackendError("provider_secret_ref_mismatch")
    if provider.lifecycle not in _ALLOWED_PROVIDER_STATES:
        raise SecretBackendError("provider_lifecycle_blocked")
    if not _safe_segment(provider.secret_version):
        raise SecretBackendError("invalid_secret_version")

    account = (
        f"{plugin_id}/{org_id}/{project_id}/{provider_id}/api-key/"
        f"{provider.secret_version}"
    )
    return KeychainLocator(
        service=parsed.netloc,
        account=account,
        ref_fingerprint=hashlib.sha256(cleaned.encode("utf-8")).hexdigest(),
    )


Runner = Callable[..., Any]


class MacOSKeychainClient:
    """Read a generic-password item without invoking a shell or logging output."""

    def __init__(self, *, runner: Runner = subprocess.run, timeout: float = 5.0) -> None:
        self._runner = runner
        self._timeout = timeout

    def read(self, locator: KeychainLocator) -> str:
        argv = [
            "/usr/bin/security",
            "find-generic-password",
            "-s",
            locator.service,
            "-a",
            locator.account,
            "-w",
        ]
        try:
            completed = self._runner(
                argv,
                capture_output=True,
                check=False,
                shell=False,
                text=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            raise SecretBackendError("keychain_timeout") from None
        except OSError:
            raise SecretBackendError("keychain_command_unavailable") from None

        if completed.returncode != 0:
            raise SecretBackendError("keychain_item_unavailable")
        value = completed.stdout.strip() if isinstance(completed.stdout, str) else ""
        if not value:
            raise SecretBackendError("keychain_empty")
        return value

    def exists(self, locator: KeychainLocator) -> bool:
        """Check an exact item without asking Keychain for its payload."""

        argv = [
            "/usr/bin/security",
            "find-generic-password",
            "-s",
            locator.service,
            "-a",
            locator.account,
        ]
        try:
            completed = self._runner(
                argv,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                shell=False,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            raise SecretBackendError("keychain_timeout") from None
        except OSError:
            raise SecretBackendError("keychain_command_unavailable") from None

        if completed.returncode == 0:
            return True
        if completed.returncode == 44:
            return False
        raise SecretBackendError("keychain_probe_failed")


class ExactSecretResolver:
    """Resolve a secret only after exact model-runtime identity validation."""

    def __init__(self, *, client: SecretClient | None = None) -> None:
        self._client = client or MacOSKeychainClient()

    def resolve(self, scope: TenantScope, provider: ProviderInstanceRevision) -> str:
        locator = parse_keychain_ref(provider.secret_ref, scope, provider)
        return self._client.read(locator)

    def probe(
        self,
        scope: TenantScope,
        provider: ProviderInstanceRevision,
    ) -> SecretProbeResult:
        locator = parse_keychain_ref(provider.secret_ref, scope, provider)
        return SecretProbeResult(
            exists=self._client.exists(locator),
            ref_fingerprint=locator.ref_fingerprint,
            secret_version=provider.secret_version,
        )
