"""M5-2 pure Resolver proof for the three-leaf ecommerce composition."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    CompositionLockPayload,
    CompositionRequest,
    RegistrySnapshot,
    RegistrySnapshotCandidate,
)
from aos_api.asset_registry.resolver import resolve
from tests.asset_registry.m5_bundle_support import (
    RuntimeSignedM5Bundle,
    copy_and_sign_m5_bundles,
)

CORE_ID = "domain.ecommerce.core"
LEAF_IDS = (
    "platform.ecommerce.niushop",
    "solution.ecommerce.growth",
    "solution.ecommerce.operations-base",
)
EXPECTED_RESOLVED_IDS = (CORE_ID, *LEAF_IDS)
DEPENDENCY_RANGE = ">=1.0.0 <2.0.0"


def _candidate(item: RuntimeSignedM5Bundle) -> RegistrySnapshotCandidate:
    bundle = item.signed
    manifest = bundle.manifest
    spec = manifest.spec
    signature_evidence = next(
        evidence
        for evidence in bundle.evidence
        if evidence.type.value == "signature_verification"
    )
    evidence_revision = canonical_sha256(
        sorted(
            (
                evidence.model_dump(mode="json", by_alias=True, exclude_none=False)
                for evidence in bundle.evidence
            ),
            key=lambda evidence: (
                evidence["type"],
                evidence["artifactRef"],
                evidence["artifactHash"],
            ),
        )
    )
    return RegistrySnapshotCandidate.model_validate(
        {
            "publisher": manifest.metadata.publisher,
            "id": manifest.metadata.id,
            "version": manifest.metadata.version,
            "kind": manifest.kind,
            "manifest": manifest,
            "contentHash": bundle.content_hash,
            "signatureFingerprint": signature_evidence.artifact_hash,
            "releaseEvidenceRevision": evidence_revision,
            "dependencies": [
                {
                    "publisher": dependency.publisher or manifest.metadata.publisher,
                    "id": dependency.id,
                    "version": dependency.version,
                }
                for dependency in spec.dependencies
            ],
            "optionalDependencies": [
                {
                    "publisher": dependency.publisher or manifest.metadata.publisher,
                    "id": dependency.id,
                    "version": dependency.version,
                }
                for dependency in spec.optional_dependencies
            ],
            "conflicts": [
                {
                    "publisher": conflict.publisher or manifest.metadata.publisher,
                    "id": conflict.id,
                    "version": conflict.version,
                }
                for conflict in spec.conflicts
            ],
            "capabilities": spec.capabilities.model_dump(mode="json", by_alias=True),
            "permissions": spec.permissions.model_dump(mode="json", by_alias=True),
            "migration": {
                "planRef": spec.migrations.plan,
                "downgradePolicy": spec.migrations.downgrade_policy,
            },
            "contributions": [
                contribution.model_dump(mode="json", by_alias=True)
                for contribution in spec.contributions
            ],
        }
    )


def _request(
    requested_ids: tuple[str, ...], snapshot: RegistrySnapshot
) -> CompositionRequest:
    versions = {item.id: item.version for item in snapshot.candidates}
    return CompositionRequest.model_validate(
        {
            "requested": [
                {
                    "publisher": "aos",
                    "id": bundle_id,
                    "version": versions[bundle_id],
                }
                for bundle_id in requested_ids
            ],
            "platformApiVersion": "1.7.0",
            "platformRelease": "aos-platform/1.7.0",
            "environment": "dev",
            "registrySnapshotHash": snapshot.snapshot_hash,
            "currentInstallationRef": None,
        }
    )


def _assert_composition_diffs(payload: CompositionLockPayload) -> None:
    permission_diff = payload.permission_diff.model_dump(mode="json", by_alias=True)
    assert all(
        values == []
        for permission_set in permission_diff.values()
        for values in permission_set.values()
    )
    assert payload.migration_plan.model_dump(mode="json", by_alias=True) == {
        "baseline": [],
        "target": [],
        "added": [],
        "removed": [],
        "changed": [],
    }
    contribution_diff = payload.contribution_diff.model_dump(
        mode="json", by_alias=True
    )
    assert contribution_diff["baseline"] == []
    assert contribution_diff["removed"] == []
    assert contribution_diff["unchanged"] == []
    assert contribution_diff["target"] == contribution_diff["added"]
    assert len(contribution_diff["target"]) == 16


def test_three_leaf_request_adds_one_core_and_three_required_edges(
    tmp_path: Path,
) -> None:
    prepared = copy_and_sign_m5_bundles(tmp_path / "runtime-bundles")
    candidates = [_candidate(item) for item in prepared.bundles]
    snapshot = RegistrySnapshot.build(
        candidates=candidates,
        checked_at=datetime.now(UTC),
    )

    payload = resolve(_request(LEAF_IDS, snapshot), snapshot, None)

    assert tuple(item.id for item in payload.resolved) == EXPECTED_RESOLVED_IDS
    assert sum(item.id == CORE_ID for item in payload.resolved) == 1
    assert {item.id: item.selection_reason for item in payload.resolved} == {
        CORE_ID: "dependency",
        **{bundle_id: "requested" for bundle_id in LEAF_IDS},
    }
    assert len(payload.edges) == 3
    assert {
        (
            edge.from_id,
            edge.to_id,
            edge.constraint,
            edge.optional,
        )
        for edge in payload.edges
    } == {(bundle_id, CORE_ID, DEPENDENCY_RANGE, False) for bundle_id in LEAF_IDS}
    assert payload.capability_providers == []
    _assert_composition_diffs(payload)


def test_request_and_candidate_permutations_keep_lock_and_selection_stable(
    tmp_path: Path,
) -> None:
    prepared = copy_and_sign_m5_bundles(tmp_path / "runtime-bundles")
    candidates = [_candidate(item) for item in prepared.bundles]
    checked_at = datetime.now(UTC)
    forward_snapshot = RegistrySnapshot.build(
        candidates=candidates,
        checked_at=checked_at,
    )
    reverse_snapshot = RegistrySnapshot.build(
        candidates=list(reversed(candidates)),
        checked_at=checked_at,
    )

    forward = resolve(_request(LEAF_IDS, forward_snapshot), forward_snapshot, None)
    repeated = resolve(_request(LEAF_IDS, forward_snapshot), forward_snapshot, None)
    reversed_inputs = resolve(
        _request(tuple(reversed(LEAF_IDS)), reverse_snapshot),
        reverse_snapshot,
        None,
    )

    assert forward_snapshot.snapshot_hash == reverse_snapshot.snapshot_hash
    assert (
        canonical_json(forward.hash_payload_dump())
        == canonical_json(repeated.hash_payload_dump())
        == canonical_json(reversed_inputs.hash_payload_dump())
    )
    assert (
        canonical_sha256(forward.hash_payload_dump())
        == canonical_sha256(repeated.hash_payload_dump())
        == canonical_sha256(reversed_inputs.hash_payload_dump())
    )
    assert tuple(item.id for item in forward.resolved) == tuple(
        item.id for item in reversed_inputs.resolved
    )
    assert tuple(item.selection_reason for item in forward.resolved) == tuple(
        item.selection_reason for item in reversed_inputs.resolved
    )
    assert forward.edges == repeated.edges == reversed_inputs.edges
    assert (
        forward.permission_diff
        == repeated.permission_diff
        == (reversed_inputs.permission_diff)
    )
    assert (
        forward.migration_plan
        == repeated.migration_plan
        == (reversed_inputs.migration_plan)
    )
    assert (
        forward.contribution_diff
        == repeated.contribution_diff
        == (reversed_inputs.contribution_diff)
    )
