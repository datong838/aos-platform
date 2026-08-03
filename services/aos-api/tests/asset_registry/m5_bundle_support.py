"""Runtime-only signing support for the four M5 ecommerce bundle skeletons."""

from __future__ import annotations

import base64
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
from aos_api.asset_registry.contracts import LoadedBundle
from aos_api.asset_registry.manifest_loader import SIGNATURE_FILENAME, ManifestLoader
from aos_api.asset_registry.signature import FrozenTrustRootProvider, TrustRoot

REPO_ROOT = Path(__file__).resolve().parents[4]
M5_SOURCE_ROOT = REPO_ROOT / "bundles"
M5_ALLOWLIST_ALIAS = "m5-fixtures"
M5_RUNTIME_KEY_ID = "m5-runtime-fixture"


@dataclass(frozen=True, slots=True)
class M5BundleFixture:
    relative_path: str
    bundle_id: str

    @property
    def source_ref(self) -> str:
        return f"bundle://{M5_ALLOWLIST_ALIAS}/{self.relative_path}"


M5_BUNDLE_FIXTURES = (
    M5BundleFixture("domains/ecommerce-core", "domain.ecommerce.core"),
    M5BundleFixture(
        "solutions/ecommerce-operations-base",
        "solution.ecommerce.operations-base",
    ),
    M5BundleFixture("solutions/ecommerce-growth", "solution.ecommerce.growth"),
    M5BundleFixture(
        "platforms/ecommerce-niushop",
        "platform.ecommerce.niushop",
    ),
)


@dataclass(frozen=True, slots=True)
class RuntimeSignedM5Bundle:
    fixture: M5BundleFixture
    bundle_path: Path
    unsigned: LoadedBundle
    signed: LoadedBundle


@dataclass(frozen=True, slots=True)
class RuntimeSignedM5BundleSet:
    root: Path
    loader: ManifestLoader
    trust_roots: FrozenTrustRootProvider
    trust_root: TrustRoot
    bundles: tuple[RuntimeSignedM5Bundle, ...]

    @property
    def source_refs(self) -> tuple[str, ...]:
        return tuple(item.fixture.source_ref for item in self.bundles)

    def by_id(self, bundle_id: str) -> RuntimeSignedM5Bundle:
        for item in self.bundles:
            if item.fixture.bundle_id == bundle_id:
                return item
        raise KeyError(bundle_id)


def canonical_bundle_signature_payload(bundle: LoadedBundle) -> bytes:
    """Build the exact canonical descriptor signed by ``ManifestLoader``."""

    return canonical_json(
        {
            "manifest": bundle.manifest.model_dump(
                mode="json", by_alias=True, exclude_none=False
            ),
            "artifacts": [
                {
                    "relativePath": item.relative_path,
                    "digest": item.digest,
                    "size": item.size,
                    "mediaType": item.media_type,
                }
                for item in bundle.artifacts
            ],
        }
    )


def copy_and_sign_m5_bundles(
    destination: Path,
    *,
    signed_at: datetime | None = None,
) -> RuntimeSignedM5BundleSet:
    """Copy and runtime-sign all M5 bundles without persisting signing material."""

    if destination.exists():
        raise ValueError("M5 runtime bundle destination must not already exist")
    checked_at = signed_at or datetime.now(UTC)
    if checked_at.utcoffset() is None:
        raise ValueError("M5 runtime signing time must include a timezone")

    shutil.copytree(M5_SOURCE_ROOT, destination)
    unsigned_loader = ManifestLoader({M5_ALLOWLIST_ALIAS: destination})
    unsigned_bundles = tuple(
        unsigned_loader.load(fixture.source_ref) for fixture in M5_BUNDLE_FIXTURES
    )

    runtime_key = Ed25519PrivateKey.generate()
    public_key = runtime_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_key_b64 = base64.b64encode(public_key).decode("ascii")
    trust_root = TrustRoot(
        publisher="aos",
        key_id=M5_RUNTIME_KEY_ID,
        public_key=public_key,
        revision=canonical_sha256(
            {
                "publisher": "aos",
                "keyId": M5_RUNTIME_KEY_ID,
                "algorithm": "Ed25519",
                "publicKey": public_key_b64,
            }
        ),
        not_before=checked_at - timedelta(minutes=5),
        not_after=checked_at + timedelta(hours=1),
    )
    trust_roots = FrozenTrustRootProvider(
        {(trust_root.publisher, trust_root.key_id): trust_root}
    )

    for fixture, unsigned in zip(M5_BUNDLE_FIXTURES, unsigned_bundles, strict=True):
        envelope = {
            "algorithm": "Ed25519",
            "keyId": M5_RUNTIME_KEY_ID,
            "signature": base64.b64encode(
                runtime_key.sign(canonical_bundle_signature_payload(unsigned))
            ).decode("ascii"),
            "signedAt": checked_at.isoformat(),
        }
        signature_path = destination / fixture.relative_path / SIGNATURE_FILENAME
        signature_path.write_text(
            json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    signed_loader = ManifestLoader(
        {M5_ALLOWLIST_ALIAS: destination}, trust_roots=trust_roots
    )
    signed_bundles = tuple(
        signed_loader.load(fixture.source_ref) for fixture in M5_BUNDLE_FIXTURES
    )
    return RuntimeSignedM5BundleSet(
        root=destination,
        loader=signed_loader,
        trust_roots=trust_roots,
        trust_root=trust_root,
        bundles=tuple(
            RuntimeSignedM5Bundle(
                fixture=fixture,
                bundle_path=destination / fixture.relative_path,
                unsigned=unsigned,
                signed=signed,
            )
            for fixture, unsigned, signed in zip(
                M5_BUNDLE_FIXTURES,
                unsigned_bundles,
                signed_bundles,
                strict=True,
            )
        ),
    )
