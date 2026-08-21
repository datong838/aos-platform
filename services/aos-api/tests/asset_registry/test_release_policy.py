from __future__ import annotations

import base64
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
from aos_api.asset_registry.contracts import (
    BundleEvidence,
    BundleEvidenceStatus,
    BundleEvidenceType,
    BundleManifest,
    BundleSignature,
    BundleVersionStatus,
)
from aos_api.asset_registry.errors import AssetRegistryError, AssetRegistryErrorCode
from aos_api.asset_registry.release_policy import (
    REQUIRED_RELEASE_EVIDENCE,
    ReleasePolicy,
)
from aos_api.asset_registry.signature import TrustRoot

NOW = datetime(2026, 8, 3, 12, tzinfo=UTC)
ROOT_REVISION = "sha256:" + "1" * 64


@dataclass
class Record:
    publisher: str
    manifest: BundleManifest
    content_hash: str
    signature: BundleSignature | None
    status: BundleVersionStatus
    evidence: list[BundleEvidence]
    artifacts: list[dict[str, object]]
    persisted_manifest: dict[str, object] | None = None


class Roots:
    def __init__(self, root: TrustRoot, private_key: Ed25519PrivateKey | None = None) -> None:
        self.root = root
        self.private_key = private_key
        self.failure: Exception | None = None

    def get_trust_root(self, *, publisher: str, key_id: str) -> TrustRoot | None:
        if self.failure is not None:
            raise self.failure
        if (publisher, key_id) == (self.root.publisher, self.root.key_id):
            return self.root
        return None


def _manifest() -> BundleManifest:
    return BundleManifest.model_validate(
        {
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
                "exports": {},
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
    )


def _record() -> tuple[Record, Roots]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    root = TrustRoot(
        publisher="aos",
        key_id="release-key",
        public_key=public_key,
        revision=ROOT_REVISION,
        not_before=NOW - timedelta(days=1),
        not_after=NOW + timedelta(days=1),
    )
    manifest = _manifest()
    descriptor = {
        "manifest": manifest.model_dump(mode="json", by_alias=True, exclude_none=False),
        "artifacts": [],
    }
    content_hash = canonical_sha256(descriptor)
    signature = BundleSignature.model_validate(
        {
            "algorithm": "Ed25519",
            "keyId": "release-key",
            "signature": base64.b64encode(
                private_key.sign(canonical_json(descriptor))
            ).decode("ascii"),
            "signedAt": NOW,
        }
    )
    signature_hash = canonical_sha256(
        signature.model_dump(mode="json", by_alias=True, exclude_none=False)
    )
    evidence = []
    for evidence_type in REQUIRED_RELEASE_EVIDENCE:
        artifact_hash = "sha256:" + evidence_type.value.encode().hex()[:16].ljust(
            64, "a"
        )
        if evidence_type == BundleEvidenceType.CONTENT_HASH:
            artifact_hash = content_hash
        elif evidence_type == BundleEvidenceType.SIGNATURE_VERIFICATION:
            artifact_hash = signature_hash
        evidence.append(
            BundleEvidence.model_validate(
                {
                    "type": evidence_type,
                    "artifactRef": f"bundle://fixture/{evidence_type.value}.json",
                    "artifactHash": artifact_hash,
                    "status": "valid",
                    "observedAt": NOW - timedelta(hours=1),
                    "expiresAt": (
                        root.not_after
                        if evidence_type == BundleEvidenceType.SIGNATURE_VERIFICATION
                        else NOW + timedelta(days=2)
                    ),
                    "revokedAt": None,
                    "metadata": (
                        {"trustRootRevision": ROOT_REVISION}
                        if evidence_type == BundleEvidenceType.SIGNATURE_VERIFICATION
                        else {}
                    ),
                }
            )
        )
    return (
        Record(
            publisher="aos",
            manifest=manifest,
            content_hash=content_hash,
            signature=signature,
            status=BundleVersionStatus.PUBLISHED,
            evidence=evidence,
            artifacts=[],
        ),
        Roots(root, private_key),
    )


def test_snapshot_policy_accepts_only_signed_semantics_equivalent_legacy_manifest() -> None:
    record, roots = _record()
    assert roots.private_key is not None and record.signature is not None
    persisted = record.manifest.model_dump(mode="json", by_alias=True, exclude_none=False)
    persisted["spec"]["exports"].pop("knowledge")
    descriptor = {"manifest": persisted, "artifacts": record.artifacts}
    record.persisted_manifest = persisted
    record.content_hash = canonical_sha256(descriptor)
    record.signature = BundleSignature.model_validate({
        **record.signature.model_dump(mode="python", by_alias=True),
        "signature": base64.b64encode(roots.private_key.sign(canonical_json(descriptor))).decode("ascii"),
    })
    for index, evidence in enumerate(record.evidence):
        payload = evidence.model_dump(mode="python", by_alias=True)
        if evidence.type == BundleEvidenceType.CONTENT_HASH:
            payload["artifactHash"] = record.content_hash
        elif evidence.type == BundleEvidenceType.SIGNATURE_VERIFICATION:
            payload["artifactHash"] = canonical_sha256(
                record.signature.model_dump(mode="json", by_alias=True, exclude_none=False)
            )
        record.evidence[index] = BundleEvidence.model_validate(payload)

    assert ReleasePolicy(trust_roots=roots).evaluate_snapshot_candidate(record, checked_at=NOW)

    record.persisted_manifest = {**persisted, "kind": "DomainPack"}
    with pytest.raises(AssetRegistryError) as caught:
        ReleasePolicy(trust_roots=roots).evaluate_snapshot_candidate(record, checked_at=NOW)
    assert caught.value.code == AssetRegistryErrorCode.MANIFEST_INVALID


def test_release_policy_returns_stable_signature_and_evidence_revision() -> None:
    record, roots = _record()
    policy = ReleasePolicy(trust_roots=roots)

    first = policy.evaluate(record, checked_at=NOW)
    changed_evidence = list(reversed(record.evidence))
    sbom_index = next(
        index
        for index, item in enumerate(changed_evidence)
        if item.type == BundleEvidenceType.SBOM
    )
    sbom = changed_evidence[sbom_index].model_dump(mode="python", by_alias=True)
    sbom["artifactRef"] = "bundle://fixture/renamed-sbom.json"
    sbom["metadata"] = {"ignoredByMinimalRevision": True}
    changed_evidence[sbom_index] = BundleEvidence.model_validate(sbom)
    second = policy.evaluate(replace(record, evidence=changed_evidence), checked_at=NOW)

    signature_evidence = next(
        item
        for item in record.evidence
        if item.type == BundleEvidenceType.SIGNATURE_VERIFICATION
    )
    assert first.signature_fingerprint == signature_evidence.artifact_hash
    assert first.release_evidence_revision == second.release_evidence_revision


@pytest.mark.parametrize(
    "status",
    [BundleVersionStatus.DEPRECATED, BundleVersionStatus.REVOKED],
)
def test_release_policy_requires_an_exact_published_status(
    status: BundleVersionStatus,
) -> None:
    record, roots = _record()

    with pytest.raises(AssetRegistryError) as caught:
        ReleasePolicy(trust_roots=roots).evaluate(
            replace(record, status=status), checked_at=NOW
        )

    assert caught.value.code == AssetRegistryErrorCode.VERIFICATION_FAILED


@pytest.mark.parametrize("evidence_type", REQUIRED_RELEASE_EVIDENCE)
def test_release_policy_requires_all_five_evidence_types(
    evidence_type: BundleEvidenceType,
) -> None:
    record, roots = _record()
    record.evidence = [item for item in record.evidence if item.type != evidence_type]

    with pytest.raises(AssetRegistryError):
        ReleasePolicy(trust_roots=roots).evaluate(record, checked_at=NOW)


@pytest.mark.parametrize("change", ["expired", "future", "revoked"])
def test_release_policy_rejects_non_current_evidence(change: str) -> None:
    record, roots = _record()
    index = next(
        index
        for index, item in enumerate(record.evidence)
        if item.type == BundleEvidenceType.SBOM
    )
    payload = record.evidence[index].model_dump(mode="python", by_alias=True)
    if change == "expired":
        payload["expiresAt"] = NOW
    elif change == "future":
        payload["observedAt"] = NOW + timedelta(seconds=1)
        payload["expiresAt"] = NOW + timedelta(days=1)
    else:
        payload["status"] = BundleEvidenceStatus.REVOKED
        payload["revokedAt"] = NOW
    record.evidence[index] = BundleEvidence.model_validate(payload)

    with pytest.raises(AssetRegistryError) as caught:
        ReleasePolicy(trust_roots=roots).evaluate(record, checked_at=NOW)

    assert caught.value.code == AssetRegistryErrorCode.VERIFICATION_FAILED


def test_release_policy_rejects_stale_expected_release_identifiers() -> None:
    record, roots = _record()
    policy = ReleasePolicy(trust_roots=roots)
    current = policy.evaluate(record, checked_at=NOW)

    with pytest.raises(AssetRegistryError) as stale_revision:
        policy.evaluate(
            record,
            checked_at=NOW,
            expected_evidence_revision="sha256:" + "f" * 64,
        )
    with pytest.raises(AssetRegistryError) as stale_signature:
        policy.evaluate(
            record,
            checked_at=NOW,
            expected_signature_fingerprint="sha256:" + "e" * 64,
        )

    assert current.release_evidence_revision.startswith("sha256:")
    assert stale_revision.value.code == AssetRegistryErrorCode.VERIFICATION_FAILED
    assert stale_signature.value.code == AssetRegistryErrorCode.SIGNATURE_INVALID


def test_release_policy_rejects_content_evidence_hash_mismatch() -> None:
    record, roots = _record()
    index = next(
        index
        for index, item in enumerate(record.evidence)
        if item.type == BundleEvidenceType.CONTENT_HASH
    )
    payload = record.evidence[index].model_dump(mode="python", by_alias=True)
    payload["artifactHash"] = "sha256:" + "f" * 64
    record.evidence[index] = BundleEvidence.model_validate(payload)

    with pytest.raises(AssetRegistryError) as caught:
        ReleasePolicy(trust_roots=roots).evaluate(record, checked_at=NOW)

    assert caught.value.code == AssetRegistryErrorCode.MANIFEST_INVALID


def test_release_policy_rejects_signature_envelope_tampering() -> None:
    record, roots = _record()
    assert record.signature is not None
    payload = record.signature.model_dump(mode="python", by_alias=True)
    payload["signature"] = base64.b64encode(b"x" * 64).decode("ascii")
    record.signature = BundleSignature.model_validate(payload)

    with pytest.raises(AssetRegistryError) as caught:
        ReleasePolicy(trust_roots=roots).evaluate(record, checked_at=NOW)

    assert caught.value.code == AssetRegistryErrorCode.SIGNATURE_INVALID


def test_release_policy_fails_closed_for_revoked_current_trust_root() -> None:
    record, roots = _record()
    roots.root = replace(roots.root, revoked_at=NOW)

    with pytest.raises(AssetRegistryError) as caught:
        ReleasePolicy(trust_roots=roots).evaluate(record, checked_at=NOW)

    assert caught.value.code == AssetRegistryErrorCode.SIGNATURE_INVALID


def test_release_policy_preserves_trust_root_outage_priority() -> None:
    record, roots = _record()
    roots.failure = RuntimeError("internal provider failure")
    record.evidence = []

    with pytest.raises(AssetRegistryError) as caught:
        ReleasePolicy(trust_roots=roots).evaluate(record, checked_at=NOW)

    assert caught.value.code == AssetRegistryErrorCode.TRUST_ROOT_UNAVAILABLE
    assert "internal provider failure" not in str(caught.value)


@pytest.mark.parametrize(
    "root_state",
    ["missing", "not-yet-valid", "expired", "revoked", "rotated"],
)
def test_snapshot_policy_excludes_candidate_for_current_root_eligibility(
    root_state: str,
) -> None:
    record, roots = _record()
    root = roots.root
    if root_state == "missing":
        roots.root = replace(root, key_id="replacement-key")
    elif root_state == "not-yet-valid":
        roots.root = replace(root, not_before=NOW + timedelta(seconds=1))
    elif root_state == "expired":
        roots.root = replace(root, not_after=NOW)
    elif root_state == "revoked":
        roots.root = replace(root, revoked_at=NOW)
    else:
        roots.root = replace(root, revision="sha256:" + "2" * 64)

    result = ReleasePolicy(trust_roots=roots).evaluate_snapshot_candidate(
        record,
        checked_at=NOW,
    )

    assert result is None


@pytest.mark.parametrize("evidence_state", ["missing", "expired", "revoked"])
def test_snapshot_policy_excludes_candidate_for_invalid_release_evidence(
    evidence_state: str,
) -> None:
    record, roots = _record()
    index = next(
        index
        for index, item in enumerate(record.evidence)
        if item.type == BundleEvidenceType.SBOM
    )
    if evidence_state == "missing":
        record.evidence.pop(index)
    else:
        payload = record.evidence[index].model_dump(mode="python", by_alias=True)
        if evidence_state == "expired":
            payload["expiresAt"] = NOW
        else:
            payload["status"] = BundleEvidenceStatus.REVOKED
            payload["revokedAt"] = NOW
        record.evidence[index] = BundleEvidence.model_validate(payload)

    result = ReleasePolicy(trust_roots=roots).evaluate_snapshot_candidate(
        record,
        checked_at=NOW,
    )

    assert result is None


def test_snapshot_policy_duplicate_signature_evidence_fails_closed() -> None:
    record, roots = _record()
    signature_evidence = next(
        item
        for item in record.evidence
        if item.type == BundleEvidenceType.SIGNATURE_VERIFICATION
    )
    record.evidence.append(signature_evidence)

    with pytest.raises(AssetRegistryError) as caught:
        ReleasePolicy(trust_roots=roots).evaluate_snapshot_candidate(
            record,
            checked_at=NOW,
        )

    assert caught.value.code == AssetRegistryErrorCode.SIGNATURE_INVALID


def test_snapshot_policy_same_revision_crypto_failure_fails_closed() -> None:
    record, roots = _record()
    assert record.signature is not None
    sbom_index = next(
        index
        for index, item in enumerate(record.evidence)
        if item.type == BundleEvidenceType.SBOM
    )
    sbom = record.evidence[sbom_index].model_dump(mode="python", by_alias=True)
    sbom["expiresAt"] = NOW
    record.evidence[sbom_index] = BundleEvidence.model_validate(sbom)
    payload = record.signature.model_dump(mode="python", by_alias=True)
    payload["signature"] = base64.b64encode(b"x" * 64).decode("ascii")
    record.signature = BundleSignature.model_validate(payload)

    with pytest.raises(AssetRegistryError) as caught:
        ReleasePolicy(trust_roots=roots).evaluate_snapshot_candidate(
            record,
            checked_at=NOW,
        )

    assert caught.value.code == AssetRegistryErrorCode.SIGNATURE_INVALID


@pytest.mark.parametrize("damage", ["manifest", "artifact", "content-hash"])
def test_snapshot_policy_descriptor_damage_precedes_candidate_expiry(
    damage: str,
) -> None:
    record, roots = _record()
    sbom_index = next(
        index
        for index, item in enumerate(record.evidence)
        if item.type == BundleEvidenceType.SBOM
    )
    sbom = record.evidence[sbom_index].model_dump(mode="python", by_alias=True)
    sbom["expiresAt"] = NOW
    record.evidence[sbom_index] = BundleEvidence.model_validate(sbom)
    if damage == "manifest":
        manifest = record.manifest.model_dump(mode="python", by_alias=True)
        manifest["metadata"]["displayName"] = "Tampered"
        record.manifest = BundleManifest.model_validate(manifest)
    elif damage == "artifact":
        record.artifacts = [{"relativePath": "tampered.json"}]
    else:
        record.content_hash = "sha256:" + "f" * 64

    with pytest.raises(AssetRegistryError) as caught:
        ReleasePolicy(trust_roots=roots).evaluate_snapshot_candidate(
            record,
            checked_at=NOW,
        )

    assert caught.value.code == AssetRegistryErrorCode.MANIFEST_INVALID
