"""Fail-closed Ed25519 verification against publisher-scoped trust roots."""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ED25519_ALGORITHM = "Ed25519"
ED25519_PUBLIC_KEY_LENGTH = 32
ED25519_SIGNATURE_LENGTH = 64


@dataclass(frozen=True)
class TrustRoot:
    """Public verification material and its validity controls."""

    publisher: str
    key_id: str
    public_key: bytes
    not_before: datetime | None = None
    not_after: datetime | None = None
    revoked_at: datetime | None = None


class TrustRootProvider(Protocol):
    """Retrieves a public trust root for an exact publisher and key id."""

    def get_trust_root(self, *, publisher: str, key_id: str) -> TrustRoot | None: ...


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
    return isinstance(value, str) and bool(value) and value == value.strip()


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None
