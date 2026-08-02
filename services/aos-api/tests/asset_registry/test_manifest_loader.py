"""Filesystem security and evidence tests for the allowlisted manifest loader."""
from __future__ import annotations

import base64
import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from aos_api.asset_registry.canonical_json import canonical_json
from aos_api.asset_registry.contracts import BundleEvidenceStatus
from aos_api.asset_registry.errors import (
    AssetRegistryErrorCode,
    ManifestInvalidError,
)
from aos_api.asset_registry.manifest_loader import (
    BUNDLE_EVALS_RELATIVE_PATH,
    SBOM_RELATIVE_PATH,
    SIGNATURE_FILENAME,
    ManifestLoader,
)
from aos_api.asset_registry.signature import TrustRoot
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _manifest() -> dict:
    return {
        "apiVersion": "aos.dev/v1alpha1",
        "kind": "SolutionPack",
        "metadata": {
            "id": "solution.example",
            "version": "1.0.0",
            "displayName": "Example",
            "publisher": "aos",
            "license": "internal",
        },
        "spec": {
            "platformApi": ">=1.7.0 <2.0.0",
            "dependencies": [],
            "optionalDependencies": [],
            "conflicts": [],
            "exports": {"schemas": ["content/schema.json"]},
            "capabilities": {"provides": [], "requires": []},
            "permissions": {
                "roles": [],
                "markings": [],
                "dataScopes": [],
                "actionTypes": [],
            },
            "migrations": {
                "plan": None,
                "downgradePolicy": "retain-canonical",
            },
            "preflight": None,
            "regression": None,
            "rollback": None,
        },
    }


def _make_bundle(root: Path, *, name: str = "example", manifest: dict | None = None) -> Path:
    bundle = root / name
    (bundle / "content").mkdir(parents=True)
    (bundle / "bundle.yaml").write_text(
        yaml.safe_dump(manifest or _manifest(), sort_keys=False), encoding="utf-8"
    )
    (bundle / "content" / "schema.json").write_text(
        json.dumps({"type": "object"}), encoding="utf-8"
    )
    return bundle


def _loader(root: Path, trust_roots=None) -> ManifestLoader:
    return ManifestLoader({"fixtures": root}, trust_roots=trust_roots)


def _write_release_evidence(
    bundle: Path,
    *,
    sbom: object | None = None,
    evals: object | None = None,
) -> None:
    evidence_root = bundle / "evidence"
    evidence_root.mkdir(exist_ok=True)
    if sbom is not None:
        (bundle / SBOM_RELATIVE_PATH).write_text(json.dumps(sbom), encoding="utf-8")
    if evals is not None:
        (bundle / BUNDLE_EVALS_RELATIVE_PATH).write_text(
            json.dumps(evals), encoding="utf-8"
        )


def _signature_payload(loaded) -> bytes:
    return canonical_json(
        {
            "manifest": loaded.manifest.model_dump(
                mode="json", by_alias=True, exclude_none=False
            ),
            "artifacts": [
                {
                    "relativePath": item.relative_path,
                    "digest": item.digest,
                    "size": item.size,
                    "mediaType": item.media_type,
                }
                for item in loaded.artifacts
            ],
        }
    )


class StaticTrustRoots:
    def __init__(self, root: TrustRoot) -> None:
        self.root = root

    def get_trust_root(self, *, publisher: str, key_id: str) -> TrustRoot | None:
        if (publisher, key_id) == (self.root.publisher, self.root.key_id):
            return self.root
        return None


def _sign_bundle(bundle: Path, unsigned, *, wrong_payload: bool = False):
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    now = datetime.now(UTC)
    payload = _signature_payload(unsigned)
    if wrong_payload:
        payload += b"tampered"
    signature = base64.b64encode(private_key.sign(payload)).decode("ascii")
    envelope = {
        "algorithm": "Ed25519",
        "keyId": "fixture-key",
        "signature": signature,
        "signedAt": now.isoformat(),
    }
    (bundle / SIGNATURE_FILENAME).write_text(json.dumps(envelope), encoding="utf-8")
    return StaticTrustRoots(
        TrustRoot(
            publisher="aos",
            key_id="fixture-key",
            public_key=public_key,
            revision="sha256:" + "a" * 64,
            not_before=now - timedelta(minutes=1),
            not_after=now + timedelta(minutes=1),
        )
    )


def _signature_evidence(loaded):
    return next(item for item in loaded.evidence if item.type == "signature_verification")


def test_load_builds_sorted_server_derived_artifact_index_and_evidence(
    tmp_path: Path,
) -> None:
    root = tmp_path / "allowed"
    bundle = _make_bundle(root)
    (bundle / "z.txt").write_text("last", encoding="utf-8")
    (bundle / "a.txt").write_text("first", encoding="utf-8")

    loaded = _loader(root).load("bundle://fixtures/example")

    assert loaded.manifest.metadata.id == "solution.example"
    assert [item.relative_path for item in loaded.artifacts] == [
        "a.txt",
        "content/schema.json",
        "z.txt",
    ]
    assert all(item.digest.startswith("sha256:") for item in loaded.artifacts)
    assert loaded.content_hash.startswith("sha256:")
    assert loaded.signature is None
    assert {(item.type.value, item.status.value) for item in loaded.evidence} == {
        ("manifest_validation", "valid"),
        ("content_hash", "valid"),
    }
    content_evidence = next(item for item in loaded.evidence if item.type == "content_hash")
    assert content_evidence.artifact_hash == loaded.content_hash


def test_content_hash_is_deterministic_and_excludes_signature_envelope(
    tmp_path: Path,
) -> None:
    root = tmp_path / "allowed"
    bundle = _make_bundle(root)
    first = _loader(root).load("bundle://fixtures/example")
    trust_roots = _sign_bundle(bundle, first)
    second = _loader(root, trust_roots).load("bundle://fixtures/example")
    third = _loader(root, trust_roots).load("bundle://fixtures/example")

    assert first.content_hash == second.content_hash == third.content_hash
    assert first.artifacts == second.artifacts == third.artifacts
    assert SIGNATURE_FILENAME not in {item.relative_path for item in second.artifacts}
    assert second.signature is not None
    signature_evidence = _signature_evidence(second)
    assert signature_evidence.status == BundleEvidenceStatus.VALID
    assert signature_evidence.metadata["trustRootRevision"] == (
        trust_roots.root.revision
    )
    assert signature_evidence.expires_at == trust_roots.root.not_after
    assert _loader(root, trust_roots).trust_roots is trust_roots


def test_standard_sbom_and_bundle_evals_generate_hash_bound_valid_evidence(
    tmp_path: Path,
) -> None:
    root = tmp_path / "allowed"
    bundle = _make_bundle(root)
    _write_release_evidence(
        bundle,
        sbom={"format": "CycloneDX", "components": []},
        evals={"status": "passed", "failed": 0, "passed": 12},
    )

    loaded = _loader(root).load("bundle://fixtures/example")
    artifact_by_path = {item.relative_path: item for item in loaded.artifacts}
    evidence_by_type = {item.type.value: item for item in loaded.evidence}

    assert evidence_by_type["sbom"].status == BundleEvidenceStatus.VALID
    assert evidence_by_type["bundle_evals"].status == BundleEvidenceStatus.VALID
    assert evidence_by_type["sbom"].artifact_hash == artifact_by_path[
        SBOM_RELATIVE_PATH
    ].digest
    assert evidence_by_type["bundle_evals"].artifact_hash == artifact_by_path[
        BUNDLE_EVALS_RELATIVE_PATH
    ].digest


@pytest.mark.parametrize(
    ("sbom", "evals", "invalid_type"),
    [
        ({"format": "CycloneDX"}, {"status": "passed", "failed": 0}, "sbom"),
        (
            {"format": "CycloneDX", "components": []},
            {"status": "failed", "failed": 1},
            "bundle_evals",
        ),
        (
            {"format": "CycloneDX", "components": []},
            {"status": "passed", "failed": True},
            "bundle_evals",
        ),
    ],
)
def test_malformed_or_failed_standard_evidence_is_never_marked_valid(
    tmp_path: Path, sbom: object, evals: object, invalid_type: str
) -> None:
    root = tmp_path / "allowed"
    bundle = _make_bundle(root)
    _write_release_evidence(bundle, sbom=sbom, evals=evals)
    loaded = _loader(root).load("bundle://fixtures/example")
    evidence_by_type = {item.type.value: item for item in loaded.evidence}
    assert evidence_by_type[invalid_type].status == BundleEvidenceStatus.INVALID


@pytest.mark.parametrize(
    "source_ref",
    [
        "https://untrusted.invalid/example",
        "file:///tmp/example",
        "bundle://fixtures",
        "bundle://fixtures/../outside",
        "bundle://fixtures/nested//bundle",
        "bundle://fixtures/%2e%2e/outside",
        "bundle://unknown/example",
    ],
)
def test_source_reference_and_alias_fail_closed(tmp_path: Path, source_ref: str) -> None:
    root = tmp_path / "allowed"
    _make_bundle(root)
    with pytest.raises(ManifestInvalidError) as caught:
        _loader(root).load(source_ref)
    assert caught.value.code == AssetRegistryErrorCode.MANIFEST_INVALID


def test_bundle_root_and_nested_content_symlinks_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    real_bundle = _make_bundle(root, name="real")
    os.symlink(real_bundle, root / "linked")
    with pytest.raises(ManifestInvalidError, match="Symbolic links|symbolic links"):
        _loader(root).load("bundle://fixtures/linked")

    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    os.symlink(outside, real_bundle / "content" / "linked.txt")
    with pytest.raises(ManifestInvalidError, match="symbolic links"):
        _loader(root).load("bundle://fixtures/real")


def test_intermediate_directory_swap_to_symlink_cannot_escape_allowlist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "allowed"
    bundle = _make_bundle(root)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "schema.json").write_text(
        json.dumps({"outside": True}), encoding="utf-8"
    )
    loader = _loader(root)
    original_read = loader._read_regular_file
    swapped = False

    def swap_before_nested_read(bundle_descriptor, item, *, limit):
        nonlocal swapped
        if item.relative_path == "content/schema.json" and not swapped:
            swapped = True
            (bundle / "content").rename(bundle / "content-original")
            (bundle / "content").symlink_to(outside, target_is_directory=True)
        return original_read(bundle_descriptor, item, limit=limit)

    monkeypatch.setattr(loader, "_read_regular_file", swap_before_nested_read)

    with pytest.raises(ManifestInvalidError, match="read safely"):
        loader.load("bundle://fixtures/example")
    assert swapped


def test_manifest_and_bundle_size_limits_are_enforced(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    bundle = _make_bundle(root)

    loader = _loader(root)
    loader.MAX_MANIFEST_BYTES = 16
    with pytest.raises(ManifestInvalidError, match="size limit"):
        loader.load("bundle://fixtures/example")

    loader = _loader(root)
    loader.MAX_FILE_BYTES = 8
    with pytest.raises(ManifestInvalidError, match="size limit"):
        loader.load("bundle://fixtures/example")

    loader = _loader(root)
    loader.MAX_TOTAL_BYTES = (bundle / "bundle.yaml").stat().st_size
    with pytest.raises(ManifestInvalidError, match="total-size"):
        loader.load("bundle://fixtures/example")


def test_file_count_limit_includes_control_files(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    _make_bundle(root)
    loader = _loader(root)
    loader.MAX_BUNDLE_FILES = 1
    with pytest.raises(ManifestInvalidError, match="file-count"):
        loader.load("bundle://fixtures/example")


def test_manifest_references_must_exist_after_realpath_resolution(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    payload = _manifest()
    payload["spec"]["exports"] = {"schemas": ["missing/schema.json"]}
    _make_bundle(root, manifest=payload)
    with pytest.raises(ManifestInvalidError, match="missing bundle content"):
        _loader(root).load("bundle://fixtures/example")


def test_encoded_or_ambiguous_artifact_paths_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    bundle = _make_bundle(root)
    (bundle / "content" / "%2e%2e.txt").write_text("safe text", encoding="utf-8")
    with pytest.raises(ManifestInvalidError, match="unsafe file path"):
        _loader(root).load("bundle://fixtures/example")


@pytest.mark.parametrize(
    ("relative_path", "content"),
    [
        (".env", "APP_PASSWORD=not-a-real-value"),
        ("content/private.pem", "-----BEGIN PRIVATE KEY-----\nfixture"),
        ("content/settings.txt", "access_token = not-a-real-value"),
        ("content/database.txt", "postgresql://name:value@host/database"),
        ("content/request.txt", "Authorization: Bearer not-a-real-value"),
    ],
)
def test_hidden_sensitive_files_and_values_are_rejected(
    tmp_path: Path, relative_path: str, content: str
) -> None:
    root = tmp_path / "allowed"
    bundle = _make_bundle(root)
    target = bundle / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    with pytest.raises(ManifestInvalidError, match="sensitive|private key|database URL"):
        _loader(root).load("bundle://fixtures/example")


def test_real_secret_reference_inside_manifest_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    payload = _manifest()
    payload["spec"]["secretRef"] = "tenant-secret"
    _make_bundle(root, manifest=payload)
    with pytest.raises(ManifestInvalidError, match="sensitive"):
        _loader(root).load("bundle://fixtures/example")


def test_client_reported_hash_and_unsafe_yaml_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    payload = _manifest()
    payload["contentHash"] = "sha256:" + "0" * 64
    bundle = _make_bundle(root, manifest=payload)
    with pytest.raises(ManifestInvalidError, match="canonical manifest contract"):
        _loader(root).load("bundle://fixtures/example")

    (bundle / "bundle.yaml").write_text(
        "!!python/object/apply:os.system ['touch should-not-exist']",
        encoding="utf-8",
    )
    with pytest.raises(ManifestInvalidError, match="safe YAML"):
        _loader(root).load("bundle://fixtures/example")
    assert not (bundle / "should-not-exist").exists()


def test_duplicate_yaml_keys_are_rejected_instead_of_silently_overwritten(
    tmp_path: Path,
) -> None:
    root = tmp_path / "allowed"
    bundle = _make_bundle(root)
    manifest_text = (bundle / "bundle.yaml").read_text(encoding="utf-8")
    (bundle / "bundle.yaml").write_text(
        manifest_text.replace(
            "kind: SolutionPack", "kind: SolutionPack\nkind: PluginPack"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ManifestInvalidError, match="safe YAML"):
        _loader(root).load("bundle://fixtures/example")


def test_invalid_and_malformed_signatures_produce_invalid_evidence(
    tmp_path: Path,
) -> None:
    root = tmp_path / "allowed"
    bundle = _make_bundle(root)
    unsigned = _loader(root).load("bundle://fixtures/example")
    trust_roots = _sign_bundle(bundle, unsigned, wrong_payload=True)

    wrong = _loader(root, trust_roots).load("bundle://fixtures/example")
    assert wrong.signature is not None
    assert _signature_evidence(wrong).status == BundleEvidenceStatus.INVALID
    assert _signature_evidence(wrong).metadata["reason"] == "verification_failed"

    (bundle / SIGNATURE_FILENAME).write_text("{}", encoding="utf-8")
    malformed = _loader(root, trust_roots).load("bundle://fixtures/example")
    assert malformed.signature is None
    assert _signature_evidence(malformed).status == BundleEvidenceStatus.INVALID
    assert (
        _signature_evidence(malformed).metadata["reason"]
        == "malformed_signature_envelope"
    )


def test_present_signature_without_trust_roots_is_never_marked_valid(
    tmp_path: Path,
) -> None:
    root = tmp_path / "allowed"
    bundle = _make_bundle(root)
    unsigned = _loader(root).load("bundle://fixtures/example")
    _sign_bundle(bundle, unsigned)
    loaded = _loader(root).load("bundle://fixtures/example")
    assert _signature_evidence(loaded).status == BundleEvidenceStatus.INVALID
    assert _signature_evidence(loaded).metadata["reason"] == "trust_roots_unavailable"


def test_expired_trust_root_produces_invalid_signature_evidence(
    tmp_path: Path,
) -> None:
    root = tmp_path / "allowed"
    bundle = _make_bundle(root)
    unsigned = _loader(root).load("bundle://fixtures/example")
    trust_roots = _sign_bundle(bundle, unsigned)
    expired_roots = StaticTrustRoots(
        replace(trust_roots.root, not_after=datetime.now(UTC) - timedelta(seconds=1))
    )

    loaded = _loader(root, expired_roots).load("bundle://fixtures/example")
    evidence = _signature_evidence(loaded)

    assert evidence.status == BundleEvidenceStatus.INVALID
    assert evidence.expires_at is None
    assert evidence.metadata["trustRootRevision"] == expired_roots.root.revision


def test_loader_never_executes_bundle_files(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    bundle = _make_bundle(root)
    marker = bundle / "executed.marker"
    (bundle / "content" / "program.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
        encoding="utf-8",
    )
    loaded = _loader(root).load("bundle://fixtures/example")
    assert "content/program.py" in {
        artifact.relative_path for artifact in loaded.artifacts
    }
    assert not marker.exists()
