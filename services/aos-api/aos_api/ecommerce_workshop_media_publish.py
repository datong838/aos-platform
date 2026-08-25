"""Compose canonical W7-10 publication facts without offering a write path."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from aos_api.aip_action_models import ActionDraftBundle, ActionExecutionView
from aos_api.aip_production_contracts import ArtifactFamilyView, ImpactPreviewRevision, MediaGateSetDecision
from aos_api.ecommerce_workshop_media_publish_contracts import (
    MediaPublishActionContribution,
    MediaPublishCandidateContribution,
    MediaPublishContribution,
    MediaPublishExactRef,
    MediaPublishHandoffRequirement,
    MediaPublishImpactContribution,
    MediaPublishReceiptContribution,
)
from aos_api.tenant_scope import TenantScope


class MediaPublishReadSource(Protocol):
    def list_artifact_families(self, scope: TenantScope): ...
    def list_media_gate_sets(self, scope: TenantScope): ...
    def list_impact_previews(self, scope: TenantScope): ...
    def list_proposals(self, scope: TenantScope, limit: int = 100) -> list[ActionDraftBundle]: ...
    def get_execution_view_for_scope(self, scope: TenantScope, proposal_id: str) -> ActionExecutionView: ...


def _ref(resource_type: str, resource_id: str, revision: int, content_hash: str) -> MediaPublishExactRef:
    return MediaPublishExactRef(resourceType=resource_type, resourceId=resource_id, revision=revision, contentHash=content_hash)


class EcommerceWorkshopMediaPublish:
    """Read a bounded tenant projection over existing production and Action authorities."""

    def __init__(self, *, production_store, action_store, action_execution) -> None:
        self._production_store = production_store
        self._action_store = action_store
        self._action_execution = action_execution

    def read(self, scope: TenantScope, *, cutoff: datetime, limit: int = 100) -> tuple[list[MediaPublishContribution], list[str]]:
        families = {item.family_id: item for item in self._production_store.list_artifact_families(scope).items}
        gates = {item.gate_set_id: item for item in self._production_store.list_media_gate_sets(scope).items}
        previews = {(item.preview_id, item.revision): item for item in self._production_store.list_impact_previews(scope).items}
        contributions: list[MediaPublishContribution] = []
        global_blockers: set[str] = set()
        proposals = self._action_store.list_proposals(scope, limit=limit)
        publish_proposals = [item for item in proposals if item.proposal.action_type.action_type_id == "content.publish"]
        if not publish_proposals:
            return [], ["MEDIA_PUBLISH_ACTION_PROPOSAL_NOT_AVAILABLE"]
        for bundle in publish_proposals:
            proposal = bundle.proposal
            try:
                contribution = self._compose(scope, cutoff, bundle, families, gates, previews)
            except (KeyError, TypeError, ValueError):
                global_blockers.add("MEDIA_PUBLISH_BINDING_INVALID_OR_DRIFTED")
                continue
            contributions.append(contribution)
        if not contributions:
            global_blockers.add("MEDIA_PUBLISH_CONTRIBUTION_NOT_AVAILABLE")
        return contributions, sorted(global_blockers)

    def _compose(
        self,
        scope: TenantScope,
        cutoff: datetime,
        bundle: ActionDraftBundle,
        families: dict[str, ArtifactFamilyView],
        gates: dict[str, MediaGateSetDecision],
        previews: dict[tuple[str, int], ImpactPreviewRevision],
    ) -> MediaPublishContribution:
        proposal = bundle.proposal
        preview_ref = proposal.impact_preview_ref
        if preview_ref is None or proposal.action_binding_hash is None:
            raise ValueError("publish proposal requires frozen preview binding")
        preview = previews[(preview_ref.resource_id, preview_ref.revision)]
        if preview.content_hash != preview_ref.content_hash or preview.action_binding_hash != proposal.action_binding_hash:
            raise ValueError("publish preview binding drifted")
        raw = proposal.payload.get("publishCandidate")
        if not isinstance(raw, dict) or set(raw) != {"familyId", "familyVersion", "selectedVariantRef", "gateSetRef"}:
            raise ValueError("publish candidate payload drifted")
        family = families[str(raw["familyId"])]
        if int(raw["familyVersion"]) != family.version:
            raise ValueError("artifact family version drifted")
        variant_raw = raw["selectedVariantRef"]
        gate_raw = raw["gateSetRef"]
        if not isinstance(variant_raw, dict) or set(variant_raw) != {"artifactId", "contentHash"}:
            raise ValueError("selected variant ref drifted")
        if not isinstance(gate_raw, dict) or set(gate_raw) != {"gateSetId", "contentHash"}:
            raise ValueError("gate set ref drifted")
        gate = gates[str(gate_raw["gateSetId"])]
        if gate.content_hash != gate_raw["contentHash"] or gate.readiness.value != "ready" or not gate.eligible_for_approval:
            raise ValueError("gate set is not exact ready")
        variant_id, variant_hash = str(variant_raw["artifactId"]), str(variant_raw["contentHash"])
        if gate.artifact_ref.artifact_id != variant_id or gate.artifact_ref.content_hash != variant_hash:
            raise ValueError("gate set variant drifted")
        selected = [group for group in family.candidate_groups if group.selected_ref is not None]
        if not any(group.selected_ref.artifact_id == variant_id and group.selected_ref.content_hash == variant_hash for group in selected):
            raise ValueError("variant is not selected by family authority")
        external = preview.external_action_binding
        if external is None:
            raise ValueError("external action binding is required")
        execution = self._action_execution.get_execution_view_for_scope(scope, proposal.id)
        receipt = execution.receipts[-1] if execution.receipts else None
        blockers: set[str] = set()
        if preview.readiness.value != "ready" or preview.lifecycle.value != "frozen" or preview.expires_at <= cutoff:
            blockers.add("MEDIA_PUBLISH_IMPACT_NOT_CURRENT_READY")
        if receipt is None:
            blockers.add("MEDIA_PUBLISH_RECEIPT_NOT_AVAILABLE")
        elif receipt.provider_outcome in {"unknown", "partial"} or receipt.reconciliation_status in {"pending", "unresolved"}:
            blockers.add("MEDIA_PUBLISH_OUTCOME_REQUIRES_RECONCILIATION")
        blockers.add("MEDIA_PUBLISH_EXTERNAL_EFFECT_NOT_AUTHORIZED")
        skill_refs = [
            _ref(
                external.capability_ref.resource_type,
                external.capability_ref.resource_id,
                external.capability_ref.revision,
                external.capability_ref.content_hash,
            ),
            _ref(
                external.capability_binding_ref.resource_type,
                external.capability_binding_ref.resource_id,
                external.capability_binding_ref.revision,
                external.capability_binding_ref.content_hash,
            ),
        ]
        colleague_refs: list[MediaPublishExactRef] = []
        receipt_contribution = None if receipt is None else MediaPublishReceiptContribution(
            receiptId=receipt.id,
            receiptKind=receipt.receipt_kind,
            status=receipt.status.value,
            providerOutcome=receipt.provider_outcome,
            reconciliationStatus=receipt.reconciliation_status,
            requestFingerprint=receipt.request_fingerprint,
            responseHash=receipt.response_hash,
            actionBindingHash=receipt.action_binding_hash or "",
            usageReceiptCount=len(receipt.usage_receipt_refs),
            lineageAttached=receipt.lineage_source_ref is not None,
        )
        uncertain = receipt is None or receipt.provider_outcome in {"unknown", "partial"} or receipt.reconciliation_status in {"pending", "unresolved"}
        return MediaPublishContribution(
            candidate=MediaPublishCandidateContribution(
                familyId=family.family_id,
                familyVersion=family.version,
                variantRef=_ref(
                    "ArtifactRevision",
                    variant_id,
                    next(
                        item.family_revision
                        for item in family.members
                        if item.artifact_ref.artifact_id == variant_id
                        and item.artifact_ref.content_hash == variant_hash
                    ),
                    variant_hash,
                ),
                gateSetRef=_ref("MediaGateSetDecision", gate.gate_set_id, 1, gate.content_hash),
                platform=gate.variant_platform,
                profile=gate.variant_profile,
            ),
            impact=MediaPublishImpactContribution(
                previewRef=_ref("ImpactPreviewRevision", preview.preview_id, preview.revision, preview.content_hash),
                actionBindingHash=preview.action_binding_hash,
                readiness="ready" if preview.readiness.value == "ready" and preview.lifecycle.value == "frozen" and preview.expires_at > cutoff else "blocked",
                expiresAt=preview.expires_at,
                atomicSkillRefs=sorted(skill_refs, key=lambda item: (item.resource_type, item.resource_id, item.revision)),
                logicRef=_ref(preview.plan_ref.resource_type, preview.plan_ref.resource_id, preview.plan_ref.revision, preview.plan_ref.content_hash),
                colleagueBindingRefs=sorted(colleague_refs, key=lambda item: (item.resource_type, item.resource_id, item.revision)),
            ),
            action=MediaPublishActionContribution(
                proposalId=proposal.id,
                proposalVersion=proposal.version,
                proposalHash=proposal.proposal_hash,
                status=proposal.status.value,
                actionBindingHash=proposal.action_binding_hash,
                approvalCount=len(bundle.approvals),
                leaseId=execution.lease.id if execution.lease else None,
                attemptId=execution.attempt.id if execution.attempt else None,
            ),
            receipt=receipt_contribution,
            handoff=MediaPublishHandoffRequirement(
                status="required" if uncertain else "not_required",
                reasonCode="MEDIA_PUBLISH_MANUAL_EVIDENCE_REQUIRED" if uncertain else "MEDIA_PUBLISH_RECEIPT_CONFIRMED",
                requiredFacts=(["provider object identity", "observed status", "observation cutoff", "completion receipt"] if uncertain else []),
            ),
            blockerCodes=sorted(blockers),
        )


__all__ = ["EcommerceWorkshopMediaPublish", "MediaPublishReadSource"]
