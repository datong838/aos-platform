"""Trusted per-entry adapter for governed VerticalPack knowledge packages."""

from __future__ import annotations

import hashlib

from aos_api.aip_memory_contracts import (
    KnowledgeScope,
    KnowledgeSourceKind,
    RuntimeMemoryLayer,
)
from aos_api.aip_memory_pipeline_contracts import (
    KnowledgePipelineInputReceipt,
    KnowledgePipelineKind,
    TrustedKnowledgeAdapterDefinition,
    TrustedKnowledgeCandidateDraft,
)
from aos_api.aip_memory_pipeline_service import AipMemoryPipelinePolicyBlocked
from aos_api.asset_registry.knowledge_contracts import (
    KnowledgeLicenseDecision,
    KnowledgePackageManifest,
)

BUNDLE_SEED_ADAPTER_ID = "aos.knowledge.vertical-pack-seed"
BUNDLE_SEED_ADAPTER_REVISION = 1


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:40]}"


class VerticalPackSeedAdapter:
    """Map one exact package entry Receipt to one deterministic Candidate draft."""

    def __init__(
        self,
        package: KnowledgePackageManifest,
        *,
        entry_id: str,
        source_revision: int,
        knowledge_scope: KnowledgeScope = KnowledgeScope.WORKSPACE,
    ) -> None:
        if source_revision < 1:
            raise ValueError("source revision must be positive")
        if knowledge_scope is KnowledgeScope.PUBLIC_PACKAGE:
            raise ValueError("public package publication requires a separate release authority")
        self._package = package.model_copy(deep=True)
        self._entry = self._package.entry_by_id(entry_id).model_copy(deep=True)
        self._source_revision = source_revision
        self._knowledge_scope = knowledge_scope

    def adapt(
        self,
        receipt: KnowledgePipelineInputReceipt,
        *,
        pipeline_kind: KnowledgePipelineKind,
    ) -> list[TrustedKnowledgeCandidateDraft]:
        if pipeline_kind is not KnowledgePipelineKind.SEED_IMPORT:
            raise AipMemoryPipelinePolicyBlocked("bundle_seed_kind_not_allowed")
        source = next(
            item
            for item in self._package.source_inventory
            if item.source_id == self._entry.source_id
        )
        reasons: list[str] = []
        expected_payload_hash = self._entry.payload_hash.removeprefix("sha256:")
        if receipt.artifact.artifact_id != self._entry.entry_id:
            reasons.append("bundle_entry_artifact_id_mismatch")
        if receipt.artifact.content_hash != expected_payload_hash:
            reasons.append("bundle_entry_payload_hash_mismatch")
        if receipt.source.source_kind is not KnowledgeSourceKind.AUTHORIZED_DOCUMENT:
            reasons.append("bundle_entry_source_kind_invalid")
        if source.license_decision is KnowledgeLicenseDecision.UNKNOWN:
            reasons.append("bundle_entry_license_unknown")
        elif source.license_decision is KnowledgeLicenseDecision.DENIED:
            reasons.append("bundle_entry_license_denied")
        if receipt.source.license_id != source.license_id:
            reasons.append("bundle_entry_license_drift")
        if receipt.source.usage_policy != source.usage_policy:
            reasons.append("bundle_entry_usage_policy_drift")
        if receipt.source.provider != source.provider:
            reasons.append("bundle_entry_provider_drift")
        if receipt.source.provider_version != source.provider_version:
            reasons.append("bundle_entry_provider_version_drift")
        if receipt.source.applicability != self._entry.applicability:
            reasons.append("bundle_entry_applicability_drift")
        if receipt.source.observed_at != source.observed_at:
            reasons.append("bundle_entry_observed_at_drift")
        if receipt.source.freshness_expires_at != source.freshness_expires_at:
            reasons.append("bundle_entry_freshness_drift")
        if reasons:
            raise AipMemoryPipelinePolicyBlocked(list(dict.fromkeys(reasons)))

        identity = (
            self._package.package_id,
            self._package.package_version,
            self._entry.entry_id,
            self._entry.payload_hash,
        )
        return [
            TrustedKnowledgeCandidateDraft(
                candidate_id=_stable_id("knowledge-candidate", *identity),
                source_id=_stable_id("knowledge-source", *identity),
                source_revision=self._source_revision,
                knowledge_scope=self._knowledge_scope,
                candidate_layer=RuntimeMemoryLayer.SEMANTIC,
                subject=self._entry.subject,
                confidence=self._entry.confidence,
                marking=self._entry.markings,
            )
        ]


def vertical_pack_seed_adapter_definition(
    *, contract_hash: str
) -> TrustedKnowledgeAdapterDefinition:
    return TrustedKnowledgeAdapterDefinition(
        adapter_id=BUNDLE_SEED_ADAPTER_ID,
        revision=BUNDLE_SEED_ADAPTER_REVISION,
        contract_hash=contract_hash,
        pipeline_kinds=[KnowledgePipelineKind.SEED_IMPORT],
        receipt_types=["aip.artifact_receipt"],
        source_kinds=[KnowledgeSourceKind.AUTHORIZED_DOCUMENT],
    )


__all__ = [
    "BUNDLE_SEED_ADAPTER_ID",
    "BUNDLE_SEED_ADAPTER_REVISION",
    "VerticalPackSeedAdapter",
    "vertical_pack_seed_adapter_definition",
]
