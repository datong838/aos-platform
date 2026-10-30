"""Protected, atomic installation state for the Route worker identity.

Only non-secret coordinates are stored here.  The exact secret version stays
in the configured secret backend and is merely probed before publication.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aos_api.aip_secret_backend import KeychainLocator, SecretClient

_MAX_BYTES = 65_536
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SERVICE = "com.aos.oidc.route-worker"
_EXPECTED_SCOPE = ("org-org", "dev-project")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


class RouteWorkerInstallationBlocked(RuntimeError):
    """Stable non-secret installation failure category."""


class RouteWorkerSignedRelease(BaseModel):
    """One exact signed release selected by the current installation lock."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    publisher: str = Field(min_length=1, max_length=160)
    bundleId: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=80)
    contentHash: str
    signatureFingerprint: str
    releaseEvidenceRevision: str = Field(min_length=1, max_length=160)

    @field_validator("publisher", "bundleId", "version", "releaseEvidenceRevision")
    @classmethod
    def canonical_coordinate(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("canonical release coordinate required")
        return value

    @field_validator("contentHash", "signatureFingerprint")
    @classmethod
    def nonzero_hash(cls, value: str) -> str:
        if not _SHA256.fullmatch(value) or value == "sha256:" + "0" * 64:
            raise ValueError("exact nonzero sha256 required")
        return value

    def sort_key(self) -> tuple[str, str, str, str]:
        return self.publisher, self.bundleId, self.version, self.contentHash


class RouteWorkerIdentityInstallation(BaseModel):
    """Complete non-secret installation document for one worker identity."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )
    schemaVersion: Literal["aos.route-worker-identity-installation/v1"] = (
        "aos.route-worker-identity-installation/v1"
    )
    orgId: str = Field(min_length=1, max_length=160)
    projectId: str = Field(min_length=1, max_length=160)
    issuer: str = Field(min_length=1, max_length=2048)
    audience: str = Field(min_length=1, max_length=128)
    tokenEndpoint: str = Field(min_length=1, max_length=2048)
    clientId: str = Field(min_length=1, max_length=128)
    expectedSubject: str = Field(min_length=1, max_length=128)
    secretVersion: str = Field(min_length=1, max_length=128)
    installationId: str
    installationRevision: int = Field(ge=1)
    installationEtag: int = Field(ge=1)
    lockHash: str
    releases: tuple[RouteWorkerSignedRelease, ...] = Field(min_length=1, max_length=64)
    releaseSetHash: str

    @field_validator(
        "orgId", "projectId", "audience", "clientId", "expectedSubject", "secretVersion"
    )
    @classmethod
    def safe_identity(cls, value: str) -> str:
        if not _SAFE_ID.fullmatch(value) or value in {".", ".."}:
            raise ValueError("canonical worker identity required")
        return value

    @field_validator("releases", mode="before")
    @classmethod
    def canonical_release_sequence(cls, value):
        # JSON has arrays only; normalize that one wire representation before
        # the strict immutable tuple and nested release models are validated.
        if type(value) is list:
            return tuple(value)
        return value

    @model_validator(mode="after")
    def exact_installation(self) -> RouteWorkerIdentityInstallation:
        if (self.orgId, self.projectId) != _EXPECTED_SCOPE:
            raise ValueError("positive tenant installation required")
        issuer = urlsplit(self.issuer)
        endpoint = urlsplit(self.tokenEndpoint)
        loopback = endpoint.hostname in {"127.0.0.1", "::1"}
        expected = self.issuer.rstrip("/") + "/protocol/openid-connect/token"
        if (
            issuer.scheme not in {"http", "https"}
            or endpoint.scheme not in {"http", "https"}
            or (endpoint.scheme != "https" and not loopback)
            or issuer.scheme != endpoint.scheme
            or issuer.hostname != endpoint.hostname
            or issuer.port != endpoint.port
            or issuer.username is not None
            or issuer.password is not None
            or endpoint.username is not None
            or endpoint.password is not None
            or issuer.query
            or issuer.fragment
            or endpoint.query
            or endpoint.fragment
            or self.tokenEndpoint != expected
        ):
            raise ValueError("exact OIDC authority required")
        try:
            if str(UUID(self.installationId)) != self.installationId:
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise ValueError("canonical installation UUID required") from None
        if self.installationRevision != self.installationEtag:
            raise ValueError("current installation revision required")
        if (
            not _SHA256.fullmatch(self.lockHash)
            or self.lockHash == "sha256:" + "0" * 64
            or not _SHA256.fullmatch(self.releaseSetHash)
            or self.releaseSetHash == "sha256:" + "0" * 64
        ):
            raise ValueError("exact installation hashes required")
        keys = tuple(item.sort_key() for item in self.releases)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("unique sorted signed releases required")
        if self.releaseSetHash != release_set_hash(self.releases):
            raise ValueError("signed release set hash mismatch")
        return self

    def wire(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def canonical_bytes(self) -> bytes:
        return (
            json.dumps(
                self.wire(), ensure_ascii=True, sort_keys=True, separators=(",", ":")
            )
            + "\n"
        ).encode("utf-8")

    def content_hash(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_bytes()).hexdigest()

    def locator(self) -> KeychainLocator:
        raw = (
            f"{_SERVICE}/{self.orgId}/{self.projectId}/"
            f"{self.clientId}/{self.secretVersion}"
        )
        return KeychainLocator(
            service=_SERVICE,
            account=(
                f"{self.orgId}/{self.projectId}/{self.clientId}/"
                f"client-secret/{self.secretVersion}"
            ),
            ref_fingerprint=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        )


def release_set_hash(releases: tuple[RouteWorkerSignedRelease, ...]) -> str:
    raw = json.dumps(
        [item.model_dump(mode="json") for item in releases],
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


class RouteWorkerIdentityInstallationStore:
    """Publish or remove one protected document without partial visibility."""

    def __init__(self, *, secret_client: SecretClient) -> None:
        self._secret_client = secret_client

    @staticmethod
    def _path(value: str | os.PathLike[str]) -> Path:
        path = Path(value)
        try:
            parent = path.parent.stat()
        except OSError:
            parent = None
        if (
            not path.is_absolute()
            or parent is None
            or not stat.S_ISDIR(parent.st_mode)
            or stat.S_IMODE(parent.st_mode) & 0o022
        ):
            raise RouteWorkerInstallationBlocked(
                "ROUTE_WORKER_INSTALLATION_PATH_INVALID"
            )
        return path

    @classmethod
    @contextmanager
    def _exclusive_lock(cls, path: Path):
        lock_path = path.parent / f".{path.name}.lock"
        descriptor = -1
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
                0o600,
            )
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_uid != os.getuid()
            ):
                raise ValueError
            fcntl.flock(descriptor, fcntl.LOCK_EX)
        except Exception:
            if descriptor >= 0:
                os.close(descriptor)
                descriptor = -1
            raise RouteWorkerInstallationBlocked(
                "ROUTE_WORKER_INSTALLATION_LOCK_UNAVAILABLE"
            ) from None
        try:
            yield
        finally:
            if descriptor >= 0:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                finally:
                    os.close(descriptor)

    @staticmethod
    def _sync_directory(parent: Path) -> None:
        descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @classmethod
    def _read_raw(cls, path: Path) -> bytes:
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "rb") as handle:
                before = os.fstat(handle.fileno())
                if (
                    not stat.S_ISREG(before.st_mode)
                    or stat.S_IMODE(before.st_mode) != 0o600
                    or before.st_uid != os.getuid()
                    or not 0 < before.st_size <= _MAX_BYTES
                ):
                    raise ValueError
                raw = handle.read(_MAX_BYTES + 1)
                after = os.fstat(handle.fileno())

                def generation(item):
                    return (
                        item.st_dev,
                        item.st_ino,
                        item.st_size,
                        item.st_mtime_ns,
                        item.st_ctime_ns,
                    )

                if len(raw) > _MAX_BYTES or generation(before) != generation(after):
                    raise ValueError
                return raw
        except Exception:
            raise RouteWorkerInstallationBlocked(
                "ROUTE_WORKER_INSTALLATION_UNAVAILABLE"
            ) from None

    @classmethod
    def load(cls, value: str | os.PathLike[str]) -> RouteWorkerIdentityInstallation:
        path = cls._path(value)
        try:
            payload = json.loads(cls._read_raw(path))
            if type(payload) is not dict:
                raise ValueError
            document = RouteWorkerIdentityInstallation.model_validate(payload)
            if cls._read_raw(path) != document.canonical_bytes():
                raise ValueError
            return document
        except RouteWorkerInstallationBlocked:
            raise
        except Exception:
            raise RouteWorkerInstallationBlocked(
                "ROUTE_WORKER_INSTALLATION_UNAVAILABLE"
            ) from None

    @classmethod
    def _atomic_publish(cls, path: Path, raw: bytes) -> None:
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", dir=path.parent
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            cls._sync_directory(path.parent)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def install(
        self,
        value: str | os.PathLike[str],
        document: RouteWorkerIdentityInstallation | dict[str, Any],
        *,
        expected_current_hash: str | None = None,
        post_publish_check: Callable[[RouteWorkerIdentityInstallation], bool]
        | None = None,
    ) -> str:
        path = self._path(value)
        try:
            with self._exclusive_lock(path):
                installed = RouteWorkerIdentityInstallation.model_validate(document)
                if not self._secret_client.exists(installed.locator()):
                    raise ValueError
                previous = self._read_raw(path) if path.exists() else None
                if previous is None:
                    if expected_current_hash is not None:
                        raise ValueError
                else:
                    current = self.load(path)
                    if expected_current_hash != current.content_hash():
                        raise ValueError
                raw = installed.canonical_bytes()
                self._atomic_publish(path, raw)
                try:
                    if self.load(path) != installed:
                        raise ValueError
                    if (
                        post_publish_check is not None
                        and post_publish_check(installed) is not True
                    ):
                        raise ValueError
                except Exception:
                    if previous is None:
                        path.unlink(missing_ok=True)
                        self._sync_directory(path.parent)
                    else:
                        self._atomic_publish(path, previous)
                    raise
                return installed.content_hash()
        except RouteWorkerInstallationBlocked:
            raise
        except Exception:
            raise RouteWorkerInstallationBlocked(
                "ROUTE_WORKER_INSTALLATION_REJECTED"
            ) from None

    def uninstall(
        self,
        value: str | os.PathLike[str],
        *,
        expected_current_hash: str,
    ) -> RouteWorkerIdentityInstallation:
        path = self._path(value)
        try:
            with self._exclusive_lock(path):
                current = self.load(path)
                if current.content_hash() != expected_current_hash:
                    raise ValueError
                descriptor, retired = tempfile.mkstemp(
                    prefix=f".{path.name}.uninstall.", dir=path.parent
                )
                os.close(descriptor)
                os.unlink(retired)
                committed = False
                try:
                    os.replace(path, retired)
                    self._sync_directory(path.parent)
                    committed = True
                except Exception:
                    if Path(retired).exists() and not path.exists():
                        os.replace(retired, path)
                        self._sync_directory(path.parent)
                    raise
                finally:
                    if committed:
                        try:
                            os.unlink(retired)
                            self._sync_directory(path.parent)
                        except OSError:
                            # The active path is already durably absent.  A private
                            # non-secret retired file is cleanup, not active state.
                            pass
                return current
        except RouteWorkerInstallationBlocked:
            raise
        except Exception:
            raise RouteWorkerInstallationBlocked(
                "ROUTE_WORKER_UNINSTALL_REJECTED"
            ) from None


def load_route_worker_identity_installation(
    value: str | os.PathLike[str],
) -> RouteWorkerIdentityInstallation:
    """Runtime read entry point; never creates, updates, or repairs state."""

    return RouteWorkerIdentityInstallationStore.load(value)
