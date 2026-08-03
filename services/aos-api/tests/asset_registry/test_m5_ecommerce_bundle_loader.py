"""M5-1 runtime signing tests over the four repository bundle skeletons."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.contracts import BundleEvidenceStatus
from aos_api.asset_registry.manifest_loader import SIGNATURE_FILENAME
from tests.asset_registry.m5_bundle_support import (
    M5_BUNDLE_FIXTURES,
    M5_SOURCE_ROOT,
    copy_and_sign_m5_bundles,
)


def test_runtime_signing_preserves_unsigned_source_and_content_hash(
    tmp_path: Path,
) -> None:
    prepared = copy_and_sign_m5_bundles(tmp_path / "runtime-bundles")

    assert prepared.source_refs == tuple(
        fixture.source_ref for fixture in M5_BUNDLE_FIXTURES
    )
    assert prepared.trust_roots.snapshot() is prepared.trust_roots
    assert (
        prepared.trust_roots.get_trust_root(
            publisher="aos", key_id=prepared.trust_root.key_id
        )
        == prepared.trust_root
    )
    for item in prepared.bundles:
        assert not (
            M5_SOURCE_ROOT / item.fixture.relative_path / SIGNATURE_FILENAME
        ).exists()
        assert (item.bundle_path / SIGNATURE_FILENAME).is_file()
        assert item.unsigned.signature is None
        assert item.signed.signature is not None
        assert item.unsigned.content_hash == item.signed.content_hash
        assert item.unsigned.artifacts == item.signed.artifacts
        assert SIGNATURE_FILENAME not in {
            artifact.relative_path for artifact in item.signed.artifacts
        }
        assert {
            (evidence.type.value, evidence.status.value)
            for evidence in item.signed.evidence
        } == {
            ("manifest_validation", "valid"),
            ("content_hash", "valid"),
            ("signature_verification", "valid"),
            ("sbom", "valid"),
            ("bundle_evals", "valid"),
        }
        signature_evidence = next(
            evidence
            for evidence in item.signed.evidence
            if evidence.type.value == "signature_verification"
        )
        assert signature_evidence.metadata["trustRootRevision"] == (
            prepared.trust_root.revision
        )
        assert signature_evidence.metadata["signatureHashProfile"] == (
            "canonical-envelope-v1"
        )
        assert signature_evidence.artifact_hash == canonical_sha256(
            item.signed.signature.model_dump(
                mode="json", by_alias=True, exclude_none=False
            )
        )


def test_runtime_key_and_signatures_are_new_for_each_preparation(
    tmp_path: Path,
) -> None:
    first = copy_and_sign_m5_bundles(tmp_path / "first")
    second = copy_and_sign_m5_bundles(tmp_path / "second")

    assert first.trust_root.public_key != second.trust_root.public_key
    assert first.trust_root.revision != second.trust_root.revision
    assert [item.signed.content_hash for item in first.bundles] == [
        item.signed.content_hash for item in second.bundles
    ]
    assert [item.signed.signature.signature for item in first.bundles] != [
        item.signed.signature.signature for item in second.bundles
    ]


def test_tampered_controlled_content_fails_signature_verification(
    tmp_path: Path,
) -> None:
    prepared = copy_and_sign_m5_bundles(tmp_path / "tampered")
    target = prepared.by_id("domain.ecommerce.core")
    sbom_path = target.bundle_path / "evidence/sbom.json"
    sbom_path.write_text(
        json.dumps(
            {"format": "CycloneDX", "components": [{"type": "fixture"}]},
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    reloaded = prepared.loader.load(target.fixture.source_ref)
    signature_evidence = next(
        evidence
        for evidence in reloaded.evidence
        if evidence.type.value == "signature_verification"
    )

    assert reloaded.content_hash != target.signed.content_hash
    assert signature_evidence.status == BundleEvidenceStatus.INVALID
    assert signature_evidence.metadata["reason"] == "verification_failed"


def test_runtime_destination_must_be_new_and_signing_time_must_be_aware(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(ValueError, match="must not already exist"):
        copy_and_sign_m5_bundles(existing)
    with pytest.raises(ValueError, match="must include a timezone"):
        copy_and_sign_m5_bundles(
            tmp_path / "naive-time",
            signed_at=datetime(2026, 8, 4, 12, 0, tzinfo=UTC).replace(tzinfo=None),
        )
