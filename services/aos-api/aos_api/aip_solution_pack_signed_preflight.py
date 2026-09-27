"""Read-only exact source preflight for current ecommerce AIP definitions.

This is not a publication command. A later writer must repeat the checks at
its own commit boundary; a past proof never grants lasting authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from aos_api.aip_solution_pack_publisher import (
    AipSolutionPackPublisher,
    CURRENT_SIGNED_CANDIDATE_VERSION,
    SOLUTION_PACK_ID,
)
from aos_api.asset_registry.composition_contracts import RegistrySnapshot
from aos_api.asset_registry.contracts import BundleEvidenceStatus, BundleEvidenceType, LoadedBundle


CURRENT_SOURCE_REF = f"bundle://a0v-current/{SOLUTION_PACK_ID}/{CURRENT_SIGNED_CANDIDATE_VERSION}"


class SnapshotReader(Protocol):
    def read(self) -> RegistrySnapshot: ...


class BundleLoader(Protocol):
    def load(self, source_ref: str) -> LoadedBundle: ...


class CurrentDefinitionSourceBlocked(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CurrentDefinitionSourceProof:
    source_ref: str
    content_hash: str
    signature_fingerprint: str
    registry_snapshot_hash: str
    agent_count: int
    skill_count: int
    capability_count: int


def inspect_current_signed_source(
    *, reader: SnapshotReader, loader: BundleLoader, signed_root: Path,
) -> CurrentDefinitionSourceProof:
    """Require a current published snapshot and two identical signed loads."""
    snapshot = reader.read()
    matches = [item for item in snapshot.candidates if
        (item.publisher, item.id, item.version) == ("aos", SOLUTION_PACK_ID, CURRENT_SIGNED_CANDIDATE_VERSION)]
    if len(matches) != 1:
        raise CurrentDefinitionSourceBlocked("CURRENT_REGISTRY_CANDIDATE_UNAVAILABLE")
    candidate = matches[0]

    def checked_load() -> LoadedBundle:
        loaded = loader.load(CURRENT_SOURCE_REF)
        if loaded.source_ref != CURRENT_SOURCE_REF or loaded.manifest.metadata.id != SOLUTION_PACK_ID \
                or loaded.manifest.metadata.version != CURRENT_SIGNED_CANDIDATE_VERSION \
                or loaded.manifest.metadata.publisher != "aos" \
                or loaded.content_hash != candidate.content_hash:
            raise CurrentDefinitionSourceBlocked("CURRENT_SIGNED_BUNDLE_IDENTITY_DRIFT")
        signature_evidence = [item for item in loaded.evidence if item.type == BundleEvidenceType.SIGNATURE_VERIFICATION]
        if len(signature_evidence) != 1 or signature_evidence[0].status != BundleEvidenceStatus.VALID \
                or signature_evidence[0].artifact_hash != candidate.signature_fingerprint:
            raise CurrentDefinitionSourceBlocked("CURRENT_SIGNED_BUNDLE_SIGNATURE_DRIFT")
        return loaded

    checked_load()
    bundle_dir = signed_root.resolve(strict=True) / SOLUTION_PACK_ID / CURRENT_SIGNED_CANDIDATE_VERSION
    if not bundle_dir.is_dir() or bundle_dir.is_symlink():
        raise CurrentDefinitionSourceBlocked("CURRENT_SIGNED_BUNDLE_DIRECTORY_UNAVAILABLE")
    inspection = AipSolutionPackPublisher.inspect_current_candidate(bundle_dir)
    checked_load()
    return CurrentDefinitionSourceProof(
        source_ref=CURRENT_SOURCE_REF, content_hash=candidate.content_hash,
        signature_fingerprint=candidate.signature_fingerprint,
        registry_snapshot_hash=snapshot.snapshot_hash,
        agent_count=inspection.agent_count, skill_count=inspection.skill_count,
        capability_count=inspection.capability_count,
    )
