"""Fail-closed Ed25519 verification against publisher-scoped trust roots."""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ED25519_ALGORITHM = "Ed25519"
ED25519_PUBLIC_KEY_LENGTH = 32
ED25519_SIGNATURE_LENGTH = 64
TRUST_ROOTS_ENV = "AOS_BUNDLE_TRUST_ROOTS_FILE"
_MAX_TRUST_ROOTS_FILE_BYTES = 1024 * 1024
_MAX_TRUST_ROOTS = 10_000
_REVISION_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_CONFIG_FIELDS = frozenset({"trustRoots"})
_ROOT_FIELDS = frozenset(
    {
        "publisher",
        "keyId",
        "algorithm",
        "publicKey",
        "notBefore",
        "notAfter",
        "revokedAt",
        "revision",
    }
)


@dataclass(frozen=True)
class TrustRoot:
    """Public verification material and its validity controls."""

    publisher: str
    key_id: str
    public_key: bytes
    revision: str
    not_before: datetime | None = None
    not_after: datetime | None = None
    revoked_at: datetime | None = None


class TrustRootProvider(Protocol):
    """Retrieves a public trust root for an exact publisher and key id."""

    def get_trust_root(self, *, publisher: str, key_id: str) -> TrustRoot | None: ...


class TrustRootConfigurationError(ValueError):
    """Raised when the server-controlled trust-root snapshot is unsafe."""


class FileTrustRootProvider:
    """Strict, fail-closed provider backed by a server-mounted JSON snapshot.

    The file is opened and parsed for every lookup.  This deliberately avoids a
    process-lifetime cache that could keep an expired or revoked key trusted.
    """

    def __init__(self, path: Path | str) -> None:
        if isinstance(path, str):
            if not path or path != path.strip() or "\x00" in path:
                raise TrustRootConfigurationError("trust-root file path is invalid")
            configured_path = Path(path)
        elif isinstance(path, Path):
            configured_path = path
        else:
            raise TypeError("trust-root file path must be a path")
        if not configured_path.is_absolute():
            raise TrustRootConfigurationError("trust-root file path must be absolute")
        self._path = configured_path

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> FileTrustRootProvider:
        source = os.environ if environ is None else environ
        path = source.get(TRUST_ROOTS_ENV)
        if path is None or not path.strip():
            raise TrustRootConfigurationError(
                f"{TRUST_ROOTS_ENV} must identify a trust-root JSON file"
            )
        return cls(path)

    @property
    def path(self) -> Path:
        return self._path

    def get_trust_root(self, *, publisher: str, key_id: str) -> TrustRoot | None:
        if not _is_exact_identifier(publisher) or not _is_exact_identifier(key_id):
            return None
        roots = self._read_roots()
        return roots.get((publisher, key_id))

    def _read_roots(self) -> dict[tuple[str, str], TrustRoot]:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor: int | None = None
        try:
            descriptor = os.open(self._path, flags)
            file_stat = os.fstat(descriptor)
            if not stat.S_ISREG(file_stat.st_mode):
                raise TrustRootConfigurationError(
                    "trust-root configuration must be a regular file"
                )
            if file_stat.st_size > _MAX_TRUST_ROOTS_FILE_BYTES:
                raise TrustRootConfigurationError(
                    "trust-root configuration exceeds the size limit"
                )
            with os.fdopen(descriptor, "rb") as handle:
                descriptor = None
                content = handle.read(_MAX_TRUST_ROOTS_FILE_BYTES + 1)
                final_stat = os.fstat(handle.fileno())
                if (
                    final_stat.st_dev,
                    final_stat.st_ino,
                    final_stat.st_size,
                    final_stat.st_mtime_ns,
                    final_stat.st_ctime_ns,
                ) != (
                    file_stat.st_dev,
                    file_stat.st_ino,
                    file_stat.st_size,
                    file_stat.st_mtime_ns,
                    file_stat.st_ctime_ns,
                ):
                    raise TrustRootConfigurationError(
                        "trust-root configuration changed while reading"
                    )
        except TrustRootConfigurationError:
            raise
        except OSError as exc:
            raise TrustRootConfigurationError(
                "trust-root configuration could not be read safely"
            ) from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
        if len(content) > _MAX_TRUST_ROOTS_FILE_BYTES:
            raise TrustRootConfigurationError(
                "trust-root configuration exceeds the size limit"
            )
        return _parse_trust_roots(content)


def verify_ed25519(
    *,
    payload: bytes,
    signature_b64: str,
    publisher: str,
    key_id: str,
    trust_roots: TrustRootProvider,
    algorithm: str = ED25519_ALGORITHM,
    verified_at: datetime | None = None,
) -> bool:
    """Verify an Ed25519 signature, returning ``False`` for every unsafe state."""

    try:
        if algorithm != ED25519_ALGORITHM:
            return False
        if not isinstance(payload, bytes):
            return False
        if not _is_exact_identifier(publisher) or not _is_exact_identifier(key_id):
            return False
        if not isinstance(signature_b64, str) or not signature_b64:
            return False

        checked_at = verified_at or datetime.now(UTC)
        if not _is_aware(checked_at):
            return False

        trust_root = trust_roots.get_trust_root(
            publisher=publisher,
            key_id=key_id,
        )
        if trust_root is None or not _is_usable_trust_root(
            trust_root,
            publisher=publisher,
            key_id=key_id,
            checked_at=checked_at,
        ):
            return False

        signature = base64.b64decode(signature_b64, validate=True)
        if len(signature) != ED25519_SIGNATURE_LENGTH:
            return False

        public_key = Ed25519PublicKey.from_public_bytes(trust_root.public_key)
        public_key.verify(signature, payload)
        return True
    except (InvalidSignature, ValueError, TypeError, binascii.Error, AttributeError):
        return False
    except Exception:  # noqa: BLE001 - trust-store outages must fail closed
        # Trust-root adapters may fail because their durable source is unavailable.
        # Verification must never turn that operational failure into trust.
        return False


def _is_usable_trust_root(
    trust_root: TrustRoot,
    *,
    publisher: str,
    key_id: str,
    checked_at: datetime,
) -> bool:
    if trust_root.publisher != publisher or trust_root.key_id != key_id:
        return False
    if not isinstance(trust_root.revision, str) or not _REVISION_PATTERN.fullmatch(
        trust_root.revision
    ):
        return False
    if not isinstance(trust_root.public_key, bytes):
        return False
    if len(trust_root.public_key) != ED25519_PUBLIC_KEY_LENGTH:
        return False

    boundaries = (
        trust_root.not_before,
        trust_root.not_after,
        trust_root.revoked_at,
    )
    if any(value is not None and not _is_aware(value) for value in boundaries):
        return False
    if trust_root.not_before is not None and checked_at < trust_root.not_before:
        return False
    if trust_root.not_after is not None and checked_at >= trust_root.not_after:
        return False
    return trust_root.revoked_at is None or checked_at < trust_root.revoked_at


def _is_exact_identifier(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and "\x00" not in value
        and len(value) <= 240
    )


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _parse_trust_roots(content: bytes) -> dict[tuple[str, str], TrustRoot]:
    try:
        payload = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise TrustRootConfigurationError(
            "trust-root configuration is not strict JSON"
        ) from exc
    if not isinstance(payload, dict) or set(payload) != _CONFIG_FIELDS:
        raise TrustRootConfigurationError("trust-root configuration fields are invalid")
    entries = payload["trustRoots"]
    if not isinstance(entries, list) or len(entries) > _MAX_TRUST_ROOTS:
        raise TrustRootConfigurationError("trustRoots must be a bounded array")

    roots: dict[tuple[str, str], TrustRoot] = {}
    for entry in entries:
        root = _parse_trust_root(entry)
        identity = (root.publisher, root.key_id)
        if identity in roots:
            raise TrustRootConfigurationError(
                "duplicate publisher and keyId in trust-root configuration"
            )
        roots[identity] = root
    return roots


def _parse_trust_root(entry: object) -> TrustRoot:
    if not isinstance(entry, dict) or set(entry) != _ROOT_FIELDS:
        raise TrustRootConfigurationError("trust-root fields are invalid")
    publisher = entry["publisher"]
    key_id = entry["keyId"]
    algorithm = entry["algorithm"]
    public_key_b64 = entry["publicKey"]
    revision = entry["revision"]
    if not _is_exact_identifier(publisher) or not _is_exact_identifier(key_id):
        raise TrustRootConfigurationError("trust-root identity is invalid")
    if algorithm != ED25519_ALGORITHM:
        raise TrustRootConfigurationError("trust-root algorithm is invalid")
    if not isinstance(revision, str) or not _REVISION_PATTERN.fullmatch(revision):
        raise TrustRootConfigurationError("trust-root revision is invalid")
    if not isinstance(public_key_b64, str) or not public_key_b64:
        raise TrustRootConfigurationError("trust-root public key is invalid")
    try:
        public_key = base64.b64decode(public_key_b64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise TrustRootConfigurationError("trust-root public key is invalid") from exc
    if len(public_key) != ED25519_PUBLIC_KEY_LENGTH:
        raise TrustRootConfigurationError("trust-root public key is invalid")

    not_before = _parse_required_time(entry["notBefore"], "notBefore")
    not_after = _parse_required_time(entry["notAfter"], "notAfter")
    revoked_at = _parse_optional_time(entry["revokedAt"], "revokedAt")
    if not_before >= not_after:
        raise TrustRootConfigurationError("trust-root notBefore must precede notAfter")
    return TrustRoot(
        publisher=publisher,
        key_id=key_id,
        public_key=public_key,
        revision=revision,
        not_before=not_before,
        not_after=not_after,
        revoked_at=revoked_at,
    )


def _parse_required_time(value: object, field: str) -> datetime:
    parsed = _parse_optional_time(value, field)
    if parsed is None:
        raise TrustRootConfigurationError(f"trust-root {field} is required")
    return parsed


def _parse_optional_time(value: object, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or value != value.strip():
        raise TrustRootConfigurationError(f"trust-root {field} is invalid")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise TrustRootConfigurationError(f"trust-root {field} is invalid") from exc
    if not _is_aware(parsed):
        raise TrustRootConfigurationError(f"trust-root {field} must include timezone")
    return parsed


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value
