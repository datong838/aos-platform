"""M5-1 negative release gates for the four runtime-signed ecommerce skeletons."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from aos_api.asset_registry.contracts import (
    BundleEvidence,
    BundleEvidenceStatus,
    BundleEvidenceType,
    BundleManifest,
    BundleSignature,
    BundleVersionStatus,
    LoadedBundle,
)
from aos_api.asset_registry.errors import (
    AssetRegistryError,
    AssetRegistryErrorCode,
)
from aos_api.asset_registry.manifest_loader import (
    BUNDLE_EVALS_RELATIVE_PATH,
    SBOM_RELATIVE_PATH,
    SIGNATURE_FILENAME,
)
from aos_api.asset_registry.release_policy import (
    REQUIRED_RELEASE_EVIDENCE,
    ReleasePolicy,
)
from aos_api.asset_registry.signature import FrozenTrustRootProvider
from tests.asset_registry.m5_bundle_support import (
    M5_BUNDLE_FIXTURES,
    RuntimeSignedM5BundleSet,
    copy_and_sign_m5_bundles,
)


@dataclass
class _ReleaseRecord:
    publisher: str
    manifest: BundleManifest
    content_hash: str
    signature: BundleSignature | None
    status: BundleVersionStatus
    evidence: list[BundleEvidence]
    artifacts: list[dict[str, object]]


@pytest.fixture()
def signed_m5(tmp_path: Path) -> RuntimeSignedM5BundleSet:
    return copy_and_sign_m5_bundles(tmp_path / "runtime-m5")


def _evidence(
    bundle: LoadedBundle, evidence_type: BundleEvidenceType
) -> BundleEvidence:
    return next(item for item in bundle.evidence if item.type == evidence_type)


def _valid_release_evidence(bundle: LoadedBundle) -> set[BundleEvidenceType]:
    return {
        item.type
        for item in bundle.evidence
        if item.status == BundleEvidenceStatus.VALID
    }


def _assert_five_valid_evidence_cannot_form(bundle: LoadedBundle) -> None:
    assert not set(REQUIRED_RELEASE_EVIDENCE).issubset(_valid_release_evidence(bundle))


def _record(bundle: LoadedBundle) -> _ReleaseRecord:
    return _ReleaseRecord(
        publisher=bundle.manifest.metadata.publisher,
        manifest=bundle.manifest,
        content_hash=bundle.content_hash,
        signature=bundle.signature,
        status=BundleVersionStatus.VALIDATED,
        evidence=list(bundle.evidence),
        artifacts=[
            {
                "relativePath": artifact.relative_path,
                "digest": artifact.digest,
                "size": artifact.size,
                "mediaType": artifact.media_type,
            }
            for artifact in bundle.artifacts
        ],
    )


@pytest.mark.parametrize(
    "bundle_id",
    [fixture.bundle_id for fixture in M5_BUNDLE_FIXTURES],
)
def test_signed_controlled_artifact_tampering_invalidates_each_m5_bundle(
    signed_m5: RuntimeSignedM5BundleSet,
    bundle_id: str,
) -> None:
    target = signed_m5.by_id(bundle_id)
    sbom_path = target.bundle_path / SBOM_RELATIVE_PATH
    sbom_path.write_bytes(sbom_path.read_bytes() + b"\n")

    tampered = signed_m5.loader.load(target.fixture.source_ref)
    signature_evidence = _evidence(tampered, BundleEvidenceType.SIGNATURE_VERIFICATION)

    assert tampered.content_hash != target.signed.content_hash
    assert tampered.artifacts != target.signed.artifacts
    assert signature_evidence.status == BundleEvidenceStatus.INVALID
    assert signature_evidence.metadata["reason"] == "verification_failed"
    _assert_five_valid_evidence_cannot_form(tampered)


def test_signature_envelope_tampering_preserves_content_boundary_but_fails_trust(
    signed_m5: RuntimeSignedM5BundleSet,
) -> None:
    target = signed_m5.bundles[0]
    signature_path = target.bundle_path / SIGNATURE_FILENAME
    envelope = json.loads(signature_path.read_text(encoding="utf-8"))
    envelope["signature"] = base64.b64encode(b"x" * 64).decode("ascii")
    signature_path.write_text(json.dumps(envelope), encoding="utf-8")

    tampered = signed_m5.loader.load(target.fixture.source_ref)
    signature_evidence = _evidence(tampered, BundleEvidenceType.SIGNATURE_VERIFICATION)

    assert tampered.content_hash == target.signed.content_hash
    assert tampered.artifacts == target.signed.artifacts
    assert SIGNATURE_FILENAME not in {
        artifact.relative_path for artifact in tampered.artifacts
    }
    assert signature_evidence.status == BundleEvidenceStatus.INVALID
    assert signature_evidence.metadata["reason"] == "verification_failed"
    _assert_five_valid_evidence_cannot_form(tampered)


@pytest.mark.parametrize(
    ("evidence_path", "replacement", "evidence_type", "expected_status"),
    [
        (SBOM_RELATIVE_PATH, None, BundleEvidenceType.SBOM, None),
        (
            SBOM_RELATIVE_PATH,
            {"format": "CycloneDX"},
            BundleEvidenceType.SBOM,
            BundleEvidenceStatus.INVALID,
        ),
        (BUNDLE_EVALS_RELATIVE_PATH, None, BundleEvidenceType.BUNDLE_EVALS, None),
        (
            BUNDLE_EVALS_RELATIVE_PATH,
            {"status": "failed", "failed": 1},
            BundleEvidenceType.BUNDLE_EVALS,
            BundleEvidenceStatus.INVALID,
        ),
    ],
)
def test_missing_or_failed_standard_evidence_cannot_form_release_evidence_set(
    signed_m5: RuntimeSignedM5BundleSet,
    evidence_path: str,
    replacement: dict[str, object] | None,
    evidence_type: BundleEvidenceType,
    expected_status: BundleEvidenceStatus | None,
) -> None:
    target = signed_m5.bundles[0]
    path = target.bundle_path / evidence_path
    if replacement is None:
        path.unlink()
    else:
        path.write_text(json.dumps(replacement), encoding="utf-8")

    loaded = signed_m5.loader.load(target.fixture.source_ref)
    matching = [item for item in loaded.evidence if item.type == evidence_type]

    if expected_status is None:
        assert matching == []
    else:
        assert [item.status for item in matching] == [expected_status]
    assert (
        _evidence(loaded, BundleEvidenceType.SIGNATURE_VERIFICATION).status
        == BundleEvidenceStatus.INVALID
    )
    _assert_five_valid_evidence_cannot_form(loaded)


@pytest.mark.parametrize(
    "bundle_id",
    [fixture.bundle_id for fixture in M5_BUNDLE_FIXTURES],
)
@pytest.mark.parametrize("root_state", ("expired", "revoked", "revision-changed"))
def test_current_trust_root_changes_fail_closed_for_each_m5_bundle(
    signed_m5: RuntimeSignedM5BundleSet,
    bundle_id: str,
    root_state: str,
) -> None:
    bundle = signed_m5.by_id(bundle_id).signed
    record = _record(bundle)
    checked_at = bundle.loaded_at

    baseline = ReleasePolicy(trust_roots=signed_m5.trust_roots).evaluate(
        record,
        checked_at=checked_at,
        require_published=False,
    )
    assert (
        baseline.signature_fingerprint
        == _evidence(bundle, BundleEvidenceType.SIGNATURE_VERIFICATION).artifact_hash
    )

    root = signed_m5.trust_root
    if root_state == "expired":
        changed = replace(root, not_after=checked_at)
    elif root_state == "revoked":
        changed = replace(root, revoked_at=checked_at)
    else:
        changed = replace(root, revision="sha256:" + "f" * 64)
    changed_provider = FrozenTrustRootProvider(
        {(changed.publisher, changed.key_id): changed}
    )

    with pytest.raises(AssetRegistryError) as caught:
        ReleasePolicy(trust_roots=changed_provider).evaluate(
            record,
            checked_at=checked_at,
            require_published=False,
        )

    assert caught.value.code == AssetRegistryErrorCode.SIGNATURE_INVALID
