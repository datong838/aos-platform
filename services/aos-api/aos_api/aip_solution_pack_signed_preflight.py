"""Read-only exact source preflight for current ecommerce AIP definitions.

This is not a publication command. A later writer must repeat the checks at
its own commit boundary; a past proof never grants lasting authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re
from types import MappingProxyType
from typing import Protocol

from aos_api.aip_solution_pack_publisher import (
    AipSolutionPackPublisher,
    CURRENT_SIGNED_CANDIDATE_VERSION,
    SOLUTION_PACK_ID,
    _exact_definition_version,
    AipSolutionPackInvalid,
    _DEFINITION_FILES,
    COMPATIBILITY_MAP_PATH,
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


@dataclass(frozen=True, slots=True)
class ExactDefinitionSourceProof:
    """Read-only evidence for an explicit source, not a writer authorization."""

    source_ref: str
    content_hash: str
    signature_fingerprint: str
    registry_snapshot_hash: str
    agent_count: int
    skill_count: int
    capability_count: int
    bundle_version: str


def inspect_current_signed_source(
    *, reader: SnapshotReader, loader: BundleLoader, signed_root: Path,
) -> CurrentDefinitionSourceProof:
    """Require a current published snapshot and two identical signed loads."""
    return _inspect_signed_source(
        reader=reader, loader=loader, signed_root=signed_root,
        source_ref=CURRENT_SOURCE_REF, expected_version=CURRENT_SIGNED_CANDIDATE_VERSION,
        inspect_candidate=AipSolutionPackPublisher.inspect_current_candidate,
    )


def inspect_exact_signed_source(
    *, reader: SnapshotReader, loader: BundleLoader, signed_root: Path, source_ref: str,
) -> ExactDefinitionSourceProof:
    """Select one explicit signed version; never fall back to current or legacy."""
    match = (re.fullmatch(
        r"bundle://[a-z0-9][a-z0-9._-]{0,80}/solution\.ecommerce\.growth/([^/]+)",
        source_ref,
    ) if type(source_ref) is str else None)
    try:
        if match is None:
            raise ValueError()
        version = _exact_definition_version(match.group(1))
    except (ValueError, AipSolutionPackInvalid):
        raise CurrentDefinitionSourceBlocked("EXACT_DEFINITION_SOURCE_REQUIRED") from None
    if signed_root.is_symlink():
        raise CurrentDefinitionSourceBlocked("CURRENT_SIGNED_BUNDLE_DIRECTORY_UNAVAILABLE")
    proof = _inspect_signed_source(
        reader=reader, loader=loader, signed_root=signed_root,
        source_ref=source_ref, expected_version=version,
        inspect_candidate=lambda path: AipSolutionPackPublisher.inspect_exact_candidate(
            path, expected_version=version,
        ),
    )
    return ExactDefinitionSourceProof(
        source_ref=proof.source_ref, content_hash=proof.content_hash,
        signature_fingerprint=proof.signature_fingerprint,
        registry_snapshot_hash=proof.registry_snapshot_hash,
        agent_count=proof.agent_count, skill_count=proof.skill_count,
        capability_count=proof.capability_count, bundle_version=version,
    )


def _inspect_signed_source(
    *, reader: SnapshotReader, loader: BundleLoader, signed_root: Path,
    source_ref: str, expected_version: str, inspect_candidate,
) -> CurrentDefinitionSourceProof:
    snapshot = reader.read()
    matches = [item for item in snapshot.candidates if
        (item.publisher, item.id, item.version) == ("aos", SOLUTION_PACK_ID, expected_version)]
    if len(matches) != 1:
        raise CurrentDefinitionSourceBlocked("CURRENT_REGISTRY_CANDIDATE_UNAVAILABLE")
    candidate = matches[0]

    def checked_load() -> LoadedBundle:
        return _checked_definition_load(loader, source_ref, expected_version, candidate)

    checked_load()
    bundle_dir = signed_root.resolve(strict=True) / SOLUTION_PACK_ID / expected_version
    if not bundle_dir.is_dir() or bundle_dir.is_symlink():
        raise CurrentDefinitionSourceBlocked("CURRENT_SIGNED_BUNDLE_DIRECTORY_UNAVAILABLE")
    inspection = inspect_candidate(bundle_dir)
    checked_load()
    return CurrentDefinitionSourceProof(
        source_ref=source_ref, content_hash=candidate.content_hash,
        signature_fingerprint=candidate.signature_fingerprint,
        registry_snapshot_hash=snapshot.snapshot_hash,
        agent_count=inspection.agent_count, skill_count=inspection.skill_count,
        capability_count=inspection.capability_count,
    )


def _checked_definition_load(loader, source_ref, expected_version, candidate):
    loaded = loader.load(source_ref)
    if (loaded.source_ref != source_ref or loaded.manifest.metadata.id != SOLUTION_PACK_ID
            or loaded.manifest.metadata.version != expected_version
            or loaded.manifest.metadata.publisher != "aos"
            or loaded.content_hash != candidate.content_hash):
        raise CurrentDefinitionSourceBlocked("CURRENT_SIGNED_BUNDLE_IDENTITY_DRIFT")
    evidence = [x for x in loaded.evidence
                if x.type == BundleEvidenceType.SIGNATURE_VERIFICATION]
    if (len(evidence) != 1 or evidence[0].status != BundleEvidenceStatus.VALID
            or evidence[0].artifact_hash != candidate.signature_fingerprint):
        raise CurrentDefinitionSourceBlocked("CURRENT_SIGNED_BUNDLE_SIGNATURE_DRIFT")
    return loaded


def read_exact_definition_documents(*, reader, loader, signed_root: Path, source_ref: str):
    """Capture only verified definition bytes; no temporary mirror or database write."""
    proof = inspect_exact_signed_source(reader=reader, loader=loader,
        signed_root=signed_root, source_ref=source_ref)
    loaded = _checked_definition_load(loader, source_ref, proof.bundle_version, proof)
    if type(loaded) is not LoadedBundle or not callable(getattr(loader, "read_verified_artifact", None)):
        raise CurrentDefinitionSourceBlocked("VERIFIED_DEFINITION_READER_REQUIRED")
    documents = {"bundle.yaml": json.dumps(loaded.manifest.model_dump(
        mode="json", by_alias=True, exclude_none=False), sort_keys=True).encode()}
    paths = list(_DEFINITION_FILES[1:])
    if any(a.relative_path == str(COMPATIBILITY_MAP_PATH) for a in loaded.artifacts):
        paths.append(str(COMPATIBILITY_MAP_PATH))
    for name in paths:
        matches = [a for a in loaded.artifacts if a.relative_path == name]
        if (len(matches) != 1 or matches[0].artifact_ref != source_ref + "/" + name
                or matches[0].size > 1024 * 1024):
            raise CurrentDefinitionSourceBlocked("EXACT_DEFINITION_ARTIFACT_REQUIRED")
        artifact = matches[0]
        raw = loader.read_verified_artifact(source_ref, name,
            expected_digest=artifact.digest, limit=1024 * 1024)
        if (type(raw) is not bytes or len(raw) != artifact.size
                or "sha256:" + hashlib.sha256(raw).hexdigest() != artifact.digest):
            raise CurrentDefinitionSourceBlocked("EXACT_DEFINITION_ARTIFACT_DRIFTED")
        documents[name] = raw
    if sum(map(len, documents.values())) > 8 * 1024 * 1024:
        raise CurrentDefinitionSourceBlocked("EXACT_DEFINITION_DOCUMENT_LIMIT")
    current = inspect_exact_signed_source(reader=reader, loader=loader,
        signed_root=signed_root, source_ref=source_ref)
    if ((current.source_ref, current.content_hash, current.signature_fingerprint)
            != (proof.source_ref, proof.content_hash, proof.signature_fingerprint)):
        raise CurrentDefinitionSourceBlocked("EXACT_DEFINITION_SOURCE_DRIFTED")
    return current, MappingProxyType(documents)
