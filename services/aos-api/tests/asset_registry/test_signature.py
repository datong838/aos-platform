from __future__ import annotations

import base64
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aos_api.asset_registry.signature import (
    TRUST_ROOTS_ENV,
    FileTrustRootProvider,
    TrustRoot,
    TrustRootConfigurationError,
    verify_ed25519,
)

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
        revision="sha256:" + "a" * 64,
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


def test_file_provider_loads_exact_root_from_environment(
    tmp_path: Path,
    signed_bundle: tuple[TrustRoot, str],
) -> None:
    root, signature = signed_bundle
    config = tmp_path / "trust-roots.json"
    _write_config(config, [_root_entry(root)])

    provider = FileTrustRootProvider.from_environment({TRUST_ROOTS_ENV: str(config)})

    assert provider.path == config
    assert provider.get_trust_root(publisher=root.publisher, key_id=root.key_id) == root
    assert provider.get_trust_root(publisher="other", key_id=root.key_id) is None
    assert verify_ed25519(
        payload=PAYLOAD,
        signature_b64=signature,
        publisher=root.publisher,
        key_id=root.key_id,
        trust_roots=provider,
        verified_at=NOW,
    )


def test_file_provider_reloads_revocation_without_process_cache(
    tmp_path: Path,
    signed_bundle: tuple[TrustRoot, str],
) -> None:
    root, signature = signed_bundle
    config = tmp_path / "trust-roots.json"
    _write_config(config, [_root_entry(root)])
    provider = FileTrustRootProvider(config)
    assert _verify_with_provider(provider, root, signature)

    revoked = replace(
        root,
        revision="sha256:" + "b" * 64,
        revoked_at=NOW,
    )
    _write_config(config, [_root_entry(revoked)])

    assert (
        provider.get_trust_root(publisher=root.publisher, key_id=root.key_id) == revoked
    )
    assert not _verify_with_provider(provider, root, signature)


def test_file_provider_rejects_duplicate_json_keys_and_symlinks(
    tmp_path: Path,
    signed_bundle: tuple[TrustRoot, str],
) -> None:
    root, _ = signed_bundle
    config = tmp_path / "trust-roots.json"
    config.write_text('{"trustRoots":[],"trustRoots":[]}', encoding="utf-8")
    provider = FileTrustRootProvider(config)
    with pytest.raises(TrustRootConfigurationError, match="strict JSON"):
        provider.get_trust_root(publisher=root.publisher, key_id=root.key_id)

    target = tmp_path / "target.json"
    _write_config(target, [_root_entry(root)])
    config.unlink()
    config.symlink_to(target)
    with pytest.raises(TrustRootConfigurationError, match="read safely"):
        provider.get_trust_root(publisher=root.publisher, key_id=root.key_id)


def test_file_provider_missing_environment_fails_closed() -> None:
    with pytest.raises(TrustRootConfigurationError, match=TRUST_ROOTS_ENV):
        FileTrustRootProvider.from_environment({})


def test_file_provider_rejects_every_unsafe_root_snapshot(
    tmp_path: Path,
    signed_bundle: tuple[TrustRoot, str],
) -> None:
    root, signature = signed_bundle
    valid = _root_entry(root)
    invalid_entries = [
        {**valid, "unknown": True},
        {**valid, "algorithm": "RSA"},
        {**valid, "publicKey": "not-base64!"},
        {**valid, "publicKey": base64.b64encode(b"short").decode("ascii")},
        {**valid, "notBefore": "2026-08-03T12:00:00"},
        {**valid, "notAfter": valid["notBefore"]},
        {**valid, "revokedAt": "not-a-time"},
        {**valid, "revision": "mutable-revision"},
    ]
    payloads = [{"trustRoots": [entry]} for entry in invalid_entries] + [
        {"trustRoots": [valid, valid]},
        {"trustRoots": [valid], "unknown": True},
    ]

    config = tmp_path / "trust-roots.json"
    provider = FileTrustRootProvider(config)
    for payload in payloads:
        _write_config(config, payload["trustRoots"], extra=payload.get("unknown"))
        assert not _verify_with_provider(provider, root, signature)


def _root_entry(root: TrustRoot) -> dict[str, object]:
    return {
        "publisher": root.publisher,
        "keyId": root.key_id,
        "algorithm": "Ed25519",
        "publicKey": base64.b64encode(root.public_key).decode("ascii"),
        "notBefore": root.not_before.isoformat() if root.not_before else None,
        "notAfter": root.not_after.isoformat() if root.not_after else None,
        "revokedAt": root.revoked_at.isoformat() if root.revoked_at else None,
        "revision": root.revision,
    }


def _write_config(
    path: Path,
    roots: list[dict[str, object]],
    *,
    extra: object | None = None,
) -> None:
    payload: dict[str, object] = {"trustRoots": roots}
    if extra is not None:
        payload["unknown"] = extra
    path.write_text(json.dumps(payload), encoding="utf-8")


def _verify_with_provider(
    provider: FileTrustRootProvider,
    root: TrustRoot,
    signature: str,
) -> bool:
    return verify_ed25519(
        payload=PAYLOAD,
        signature_b64=signature,
        publisher=root.publisher,
        key_id=root.key_id,
        trust_roots=provider,
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
