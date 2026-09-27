#!/usr/bin/env python3
"""Persistently sign the exact current ecommerce build without deleting inputs."""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
import stat
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services/aos-api"
PROFILE = ROOT / "scripts/build_ecommerce_current_candidates.py"
KEY_ID = "a0v-local-ecommerce-current-v1"


class SigningBlocked(RuntimeError):
    pass


def _builder():
    spec = importlib.util.spec_from_file_location("current_ecommerce_sign_profile", PROFILE)
    if spec is None or spec.loader is None:
        raise SigningBlocked("CURRENT_PROFILE_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_builder()


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def validate_build(*, build: Path, receipt_path: Path, state: Path):
    build = build.resolve(strict=True)
    receipt_path = receipt_path.resolve(strict=True)
    state = state.resolve()
    if any(path == ROOT or path.is_relative_to(ROOT) for path in (build, state)):
        raise SigningBlocked("PATH_MUST_BE_OUTSIDE_REPOSITORY")
    if state == build or state.is_relative_to(build) or build.is_relative_to(state):
        raise SigningBlocked("STATE_AND_BUILD_OVERLAP")
    builder = _builder()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (receipt.get("outcome") != "BUILD_GREEN"
            or receipt.get("output") != str(build)
            or receipt.get("outputTreeHash") != builder._tree_hash(build)
            or receipt.get("contentHashes") != builder._content_hashes(build)):
        raise SigningBlocked("BUILD_RECEIPT_MISMATCH")
    expected = {bundle_id: version for _, bundle_id, version, _ in builder.ALL_CASES}
    versions = {item["id"]: item["version"] for item in receipt.get("bundles", [])}
    if versions != expected or receipt.get("moduleCount") != 8 or receipt.get("operationCount") != 15:
        raise SigningBlocked("BUILD_PROFILE_MISMATCH")
    fresh = builder.preflight()
    source_hashes = {item["id"]: item["sourceTreeHash"] for item in fresh["bundles"]}
    receipt_hashes = {item["id"]: item["sourceTreeHash"] for item in receipt["bundles"]}
    if source_hashes != receipt_hashes:
        raise SigningBlocked("SOURCE_CHANGED_AFTER_BUILD")
    if receipt.get("effects") != {
        "registryPublishCount": 0, "installationMutationCount": 0,
        "providerInvocationCount": 0, "externalPublicationCount": 0,
    }:
        raise SigningBlocked("BUILD_EFFECTS_MISMATCH")
    base = receipt.get("gitHead")
    if not isinstance(base, str) or len(base) != 40:
        raise SigningBlocked("BUILD_SOURCE_REVISION_INVALID")
    _git("merge-base", "--is-ancestor", base, "HEAD")
    if any((build / relative / "bundle.signature.json").exists()
           for relative, _, _, _ in builder.ALL_CASES):
        raise SigningBlocked("BUILD_INPUT_ALREADY_SIGNED")
    return builder, receipt


def _key(path: Path) -> Ed25519PrivateKey:
    if not path.exists():
        key = Ed25519PrivateKey.generate()
        raw = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise SigningBlocked("SIGNING_KEY_PERMISSIONS_INVALID")
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SigningBlocked("SIGNING_KEY_INVALID")
    return key


def sign(*, build: Path, receipt_path: Path, state: Path) -> dict[str, object]:
    builder, receipt = validate_build(build=build, receipt_path=receipt_path, state=state)
    build = build.resolve(strict=True)
    state = state.resolve()
    if state.exists():
        raise SigningBlocked("STATE_ALREADY_EXISTS_RECONCILE_READ_ONLY")
    state.mkdir(mode=0o700)
    if stat.S_IMODE(state.stat().st_mode) != 0o700:
        raise SigningBlocked("STATE_PERMISSIONS_INVALID")
    key = _key(state / "registry-ed25519.pem")
    sys.path.insert(0, str(API_ROOT))
    try:
        from aos_api.asset_registry.canonical_json import canonical_sha256
        from aos_api.asset_registry.manifest_loader import ManifestLoader
        from aos_api.asset_registry.release_policy import ReleasePolicy
        from aos_api.asset_registry.signature import FileTrustRootProvider

        public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        fields = {
            "publisher": "aos", "keyId": KEY_ID, "algorithm": "Ed25519",
            "publicKey": base64.b64encode(public).decode("ascii"),
            "notBefore": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
            "notAfter": datetime(2036, 1, 1, tzinfo=UTC).isoformat(),
            "revokedAt": None,
        }
        fields["revision"] = canonical_sha256(fields)
        trust_path = state / "trust-roots.json"
        descriptor = os.open(trust_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"trustRoots": [fields]}, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
        signed = state / "signed-bundles"
        import shutil
        shutil.copytree(build, signed)
        unsigned = ManifestLoader({"a0v-current": signed})
        signed_at = datetime.now(UTC)
        for relative, _, _, _ in builder.ALL_CASES:
            loaded = unsigned.load(f"bundle://a0v-current/{relative}")
            envelope = {
                "algorithm": "Ed25519", "keyId": KEY_ID,
                "signature": base64.b64encode(key.sign(builder._signature_payload(loaded))).decode("ascii"),
                "signedAt": signed_at.isoformat(),
            }
            (signed / relative / "bundle.signature.json").write_text(
                json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        trust = FileTrustRootProvider(trust_path).snapshot()
        loader = ManifestLoader({"a0v-current": signed}, trust_roots=trust)
        policy = ReleasePolicy(trust_roots=trust)
        content_hashes = {}
        for relative, bundle_id, _, _ in builder.ALL_CASES:
            loaded = loader.load(f"bundle://a0v-current/{relative}")
            # Loader derives observedAt at read time; evaluate after that read.
            policy.evaluate(builder._release_record(loaded), checked_at=datetime.now(UTC))
            content_hashes[bundle_id] = loaded.content_hash
        if content_hashes != receipt["contentHashes"]:
            raise SigningBlocked("SIGNED_CONTENT_HASH_MISMATCH")
        return {
            "outcome": "SIGNED_TREE_GREEN", "keyId": KEY_ID,
            "trustRootRevision": fields["revision"], "signedTree": str(signed),
            "signedTreeHash": builder._tree_hash(signed), "contentHashes": content_hashes,
            "buildTreeHash": receipt["outputTreeHash"],
            "effects": {"registryPublishCount": 0, "installationMutationCount": 0,
                        "providerInvocationCount": 0, "externalPublicationCount": 0},
        }
    finally:
        sys.path.remove(str(API_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--build-receipt", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(ROOT):
        raise SigningBlocked("OUTPUT_INVALID")
    result = sign(build=args.build_dir, receipt_path=args.build_receipt, state=args.state_dir)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
