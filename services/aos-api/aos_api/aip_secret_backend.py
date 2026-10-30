"""Fail-closed secret resolution for exact AIP model-runtime providers.

This module intentionally has no environment-variable or legacy-store fallback.
It resolves only an exact opaque reference after tenant, plugin and provider
identity have been matched.  It does not publish runtime authority or imply
that a provider is healthy or runnable.
"""

from __future__ import annotations

import hashlib
import os
import platform
import re
import stat
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
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
_MAX_SECRET_BYTES = 65_536


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
    if (
        len(parts) != 5
        or parts[0] != ""
        or any(not _safe_segment(part) for part in parts[1:])
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

    def __init__(
        self, *, runner: Runner = subprocess.run, timeout: float = 5.0
    ) -> None:
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


class MountedSecretFileClient:
    """Read an exact secret from a protected Linux/container mount.

    Every path component is opened relative to an already verified directory
    descriptor.  Symlinks, writable parents and non-private files therefore
    fail closed instead of silently redirecting the lookup.
    """

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self._root = Path(root)
        self._root_identity = self._validate_root()

    @staticmethod
    def _trusted_owner(metadata: os.stat_result) -> bool:
        return metadata.st_uid in {0, os.geteuid()}

    def _validate_root(self) -> tuple[int, int]:
        try:
            metadata = self._root.lstat()
        except OSError:
            raise SecretBackendError("secret_mount_unavailable") from None
        if (
            not self._root.is_absolute()
            or not stat.S_ISDIR(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) & 0o022
            or not self._trusted_owner(metadata)
        ):
            raise SecretBackendError("secret_mount_invalid")
        return metadata.st_dev, metadata.st_ino

    @staticmethod
    def _segments(locator: KeychainLocator) -> tuple[str, ...]:
        if (
            type(locator) is not KeychainLocator
            or type(locator.service) is not str
            or type(locator.account) is not str
        ):
            raise SecretBackendError("secret_locator_invalid")
        account = locator.account.split("/")
        segments = (locator.service, *account)
        if not segments or any(not _safe_segment(item) for item in segments):
            raise SecretBackendError("secret_locator_invalid")
        return segments

    @staticmethod
    def _directory_flags() -> int:
        return (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0)
        )

    @staticmethod
    def _file_flags() -> int:
        return os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)

    def _open_secret(self, locator: KeychainLocator) -> int | None:
        segments = self._segments(locator)
        descriptors: list[int] = []
        file_descriptor = -1
        try:
            root_fd = os.open(self._root, self._directory_flags())
            descriptors.append(root_fd)
            root_metadata = os.fstat(root_fd)
            if (
                (root_metadata.st_dev, root_metadata.st_ino) != self._root_identity
                or not stat.S_ISDIR(root_metadata.st_mode)
                or stat.S_IMODE(root_metadata.st_mode) & 0o022
                or not self._trusted_owner(root_metadata)
            ):
                raise SecretBackendError("secret_mount_changed")

            current_fd = root_fd
            for segment in segments[:-1]:
                next_fd = os.open(segment, self._directory_flags(), dir_fd=current_fd)
                descriptors.append(next_fd)
                metadata = os.fstat(next_fd)
                if (
                    not stat.S_ISDIR(metadata.st_mode)
                    or stat.S_IMODE(metadata.st_mode) & 0o022
                    or not self._trusted_owner(metadata)
                ):
                    raise SecretBackendError("secret_mount_invalid")
                current_fd = next_fd

            file_descriptor = os.open(
                segments[-1], self._file_flags(), dir_fd=current_fd
            )
            metadata = os.fstat(file_descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
                or stat.S_IMODE(metadata.st_mode) & 0o077
                or not self._trusted_owner(metadata)
                or not 0 < metadata.st_size <= _MAX_SECRET_BYTES
            ):
                raise SecretBackendError("secret_file_invalid")
            result = file_descriptor
            file_descriptor = -1
            return result
        except FileNotFoundError:
            return None
        except SecretBackendError:
            raise
        except OSError:
            raise SecretBackendError("secret_mount_unavailable") from None
        finally:
            if file_descriptor >= 0:
                os.close(file_descriptor)
            for descriptor in reversed(descriptors):
                os.close(descriptor)

    def exists(self, locator: KeychainLocator) -> bool:
        descriptor = self._open_secret(locator)
        if descriptor is None:
            return False
        os.close(descriptor)
        return True

    def read(self, locator: KeychainLocator) -> str:
        descriptor = self._open_secret(locator)
        if descriptor is None:
            raise SecretBackendError("secret_file_unavailable")
        try:
            before = os.fstat(descriptor)
            chunks: list[bytes] = []
            length = 0
            while length <= _MAX_SECRET_BYTES:
                chunk = os.read(
                    descriptor,
                    min(8192, _MAX_SECRET_BYTES + 1 - length),
                )
                if not chunk:
                    break
                chunks.append(chunk)
                length += len(chunk)
            payload = b"".join(chunks)
            after = os.fstat(descriptor)
        except OSError:
            raise SecretBackendError("secret_file_read_failed") from None
        finally:
            os.close(descriptor)
        if (
            len(payload) != before.st_size
            or len(payload) > _MAX_SECRET_BYTES
            or (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
        ):
            raise SecretBackendError("secret_file_changed")
        try:
            value = payload.decode("utf-8").rstrip("\r\n")
        except UnicodeDecodeError:
            raise SecretBackendError("secret_file_encoding_invalid") from None
        if not value or "\x00" in value:
            raise SecretBackendError("secret_file_empty")
        return value


def default_secret_client(
    *,
    system_name: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> SecretClient:
    """Select the platform backend without accepting secret payloads in env."""

    current_system = system_name or platform.system()
    if current_system == "Darwin":
        return MacOSKeychainClient()
    if current_system == "Linux":
        return DeferredMountedSecretFileClient(environ)
    raise SecretBackendError("secret_backend_unsupported")


class DeferredMountedSecretFileClient:
    """Delay Linux mount validation until a secret operation is requested."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = None if environ is None else dict(environ)
        self._backend: MountedSecretFileClient | None = None

    def _client(self) -> MountedSecretFileClient:
        if self._backend is not None:
            return self._backend
        values = os.environ if self._environ is None else self._environ
        root = values.get("AOS_SECRET_MOUNT_ROOT", "")
        if not root or root != root.strip():
            raise SecretBackendError("secret_mount_required")
        backend = MountedSecretFileClient(root)
        self._backend = backend
        return backend

    def exists(self, locator: KeychainLocator) -> bool:
        return self._client().exists(locator)

    def read(self, locator: KeychainLocator) -> str:
        return self._client().read(locator)


class ExactSecretResolver:
    """Resolve a secret only after exact model-runtime identity validation."""

    def __init__(self, *, client: SecretClient | None = None) -> None:
        self._client = client or default_secret_client()

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
