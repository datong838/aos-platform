from __future__ import annotations

import base64
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aos_api.asset_registry.signature import TrustRoot, verify_ed25519

NOW = datetime(2026, 8, 3, 12, tzinfo=UTC)
PAYLOAD = b'{"metadata":{"id":"solution.example","version":"1.0.0"}}'


class StaticTrustRoots:
    def __init__(self, *roots: TrustRoot) -> None:
        self._roots = {(root.publisher, root.key_id): root for root in roots}

    def get_trust_root(self, *, publisher: str, key_id: str) -> TrustRoot | None:
        return self._roots.get((publisher, key_id))


class UnavailableTrustRoots:
    def get_trust_root(self, *, publisher: str, key_id: str) -> TrustRoot | None:
        raise RuntimeError("trust-root store unavailable")


@pytest.fixture
def signed_bundle() -> tuple[TrustRoot, str]:
    # Tests generate ephemeral private material at runtime; no private key is persisted.
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    root = TrustRoot(
        publisher="aos",
        key_id="release-2026-01",
        public_key=public_key,
        not_before=NOW - timedelta(days=1),
        not_after=NOW + timedelta(days=1),
    )
    signature = base64.b64encode(private_key.sign(PAYLOAD)).decode("ascii")
    return root, signature


def test_valid_signature_is_accepted(signed_bundle: tuple[TrustRoot, str]) -> None:
    root, signature = signed_bundle

    assert verify_ed25519(
        payload=PAYLOAD,
        signature_b64=signature,
        publisher=root.publisher,
        key_id=root.key_id,
        trust_roots=StaticTrustRoots(root),
        verified_at=NOW,
    )


def test_wrong_key_and_tampered_payload_are_rejected(
    signed_bundle: tuple[TrustRoot, str],
) -> None:
    root, signature = signed_bundle
    other_private_key = Ed25519PrivateKey.generate()
    wrong_root = replace(
        root,
        public_key=other_private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ),
    )

    assert not _verify(root=wrong_root, signature=signature)
    assert not _verify(root=root, signature=signature, payload=PAYLOAD + b" ")


@pytest.mark.parametrize("signature", ["", "not-base64!", "YQ=="])
def test_malformed_signatures_fail_closed(
    signed_bundle: tuple[TrustRoot, str], signature: str
) -> None:
    root, _ = signed_bundle

    assert not _verify(root=root, signature=signature)


def test_unknown_or_unavailable_trust_root_fails_closed(
    signed_bundle: tuple[TrustRoot, str],
) -> None:
    root, signature = signed_bundle

    assert not verify_ed25519(
        payload=PAYLOAD,
        signature_b64=signature,
        publisher=root.publisher,
        key_id=root.key_id,
        trust_roots=StaticTrustRoots(),
        verified_at=NOW,
    )
    assert not verify_ed25519(
        payload=PAYLOAD,
        signature_b64=signature,
        publisher=root.publisher,
        key_id=root.key_id,
        trust_roots=UnavailableTrustRoots(),
        verified_at=NOW,
    )


@pytest.mark.parametrize(
    "root_change",
    [
        {"not_before": NOW + timedelta(seconds=1)},
        {"not_after": NOW},
        {"revoked_at": NOW},
        {"not_after": NOW.replace(tzinfo=None)},
    ],
)
def test_inactive_expired_revoked_or_ambiguous_roots_are_rejected(
    signed_bundle: tuple[TrustRoot, str], root_change: dict[str, datetime]
) -> None:
    root, signature = signed_bundle

    assert not _verify(root=replace(root, **root_change), signature=signature)


def test_algorithm_and_publisher_binding_prevent_signature_reuse(
    signed_bundle: tuple[TrustRoot, str],
) -> None:
    root, signature = signed_bundle

    assert not _verify(root=root, signature=signature, algorithm="RSA")
    assert not verify_ed25519(
        payload=PAYLOAD,
        signature_b64=signature,
        publisher="another-publisher",
        key_id=root.key_id,
        trust_roots=StaticTrustRoots(root),
        verified_at=NOW,
    )


def _verify(
    *,
    root: TrustRoot,
    signature: str,
    payload: bytes = PAYLOAD,
    algorithm: str = "Ed25519",
) -> bool:
    return verify_ed25519(
        payload=payload,
        signature_b64=signature,
        publisher=root.publisher,
        key_id=root.key_id,
        trust_roots=StaticTrustRoots(root),
        algorithm=algorithm,
        verified_at=NOW,
    )
