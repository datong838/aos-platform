"""Compose media versions/review/export and create an internal publish Proposal only."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Callable

from aos_api.aip_action_models import CreateActionProposalRequest
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.auth import Principal
from aos_api.ecommerce_media_delivery_contracts import (
    MediaDeliveryCandidate,
    MediaDeliveryExactRef,
    MediaDeliveryExportRequest,
    MediaDeliveryExportResponse,
    MediaDeliveryProposalRef,
    MediaDeliveryPublishProposalRequest,
    MediaDeliveryPublishProposalResponse,
    MediaDeliveryReviewIssue,
    MediaDeliverySelection,
    MediaDeliverySideEffects,
    MediaDeliveryWorkspaceResponse,
)
from aos_api.ecommerce_media_internal_workflow_contracts import MediaInternalWorkflowDraft
from aos_api.tenant_scope import TenantScope


class MediaDeliveryError(RuntimeError):
    code = "MEDIA_DELIVERY_ERROR"


class MediaDeliveryConflict(MediaDeliveryError):
    code = "MEDIA_DELIVERY_CONFLICT"


def _value(value):
    return getattr(value, "value", value)


class EcommerceMediaDelivery:
    def __init__(self, *, brief_store, production_store, action_service, action_store, clock: Callable[[], datetime] | None = None) -> None:
        self._briefs = brief_store
        self._production = production_store
        self._actions = action_service
        self._action_store = action_store
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def media_schema_ref() -> ResourceRef:
        return ResourceRef(
            resource_type="MediaInternalWorkflowSchema",
            resource_id="schema://aos/ecommerce/media-internal-workflow/v1",
            revision="1",
            authority="aos://ecommerce-workshop/media-studio",
        )

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    def workspace(self, scope: TenantScope, brief_id: str) -> MediaDeliveryWorkspaceResponse:
        try:
            current = self._briefs.get_brief(scope, brief_id)
            self._require_media_brief(current)
            history = []
            for revision in range(1, current.revision + 1):
                item = self._briefs.get_brief(scope, brief_id, revision)
                self._require_media_brief(item)
                history.append(self._draft(item))
            candidates = self._candidates(scope, current)
        except MediaDeliveryError:
            raise
        except Exception as exc:
            raise MediaDeliveryConflict(str(exc)) from exc
        blockers = [] if candidates else ["MEDIA_ARTIFACT_FAMILY_NOT_AVAILABLE"]
        return MediaDeliveryWorkspaceResponse(
            tenant=self._tenant(scope), currentDraft=self._draft(current), history=history,
            historyCount=len(history), candidates=candidates, blockerCodes=blockers,
        )

    def export(self, scope: TenantScope, body: MediaDeliveryExportRequest) -> MediaDeliveryExportResponse:
        try:
            current = self._exact_brief(scope, body.draft_ref, body.expected_version)
            workspace = self.workspace(scope, current.brief_id)
            if body.selection is not None:
                self._select_candidate(workspace, body.selection, require_ready=False)
            manifest = {
                "schemaVersion": "aos.ecommerce-workshop.media-delivery-export/v1",
                "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
                "currentDraft": workspace.current_draft.model_dump(mode="json", by_alias=True),
                "history": [item.model_dump(mode="json", by_alias=True) for item in workspace.history],
                "selection": body.selection.model_dump(mode="json", by_alias=True) if body.selection else None,
                "externalEffectsAllowed": False,
            }
            content = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except MediaDeliveryError:
            raise
        except Exception as exc:
            raise MediaDeliveryConflict(str(exc)) from exc
        return MediaDeliveryExportResponse(
            tenant=self._tenant(scope), fileName=f"media-{current.brief_id}-r{current.revision}.json",
            content=content, contentHash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            sideEffects=MediaDeliverySideEffects(),
        )

    def create_publish_proposal(self, principal: Principal, idempotency_key: str, body: MediaDeliveryPublishProposalRequest) -> MediaDeliveryPublishProposalResponse:
        scope = TenantScope(principal.org_id, principal.project_id)
        key = idempotency_key.strip()
        if not key or len(key) > 120:
            raise MediaDeliveryConflict("Idempotency-Key must be 1..120 characters")
        try:
            current = self._exact_brief(scope, body.draft_ref, body.expected_version)
            workspace = self.workspace(scope, current.brief_id)
            candidate = self._select_candidate(workspace, body.selection, require_ready=True)
            preview = next(
                item for item in self._production.list_impact_previews(scope).items
                if item.preview_id == body.selection.impact_preview_ref.resource_id
                and item.revision == body.selection.impact_preview_ref.revision
            )
            if (
                preview.content_hash != body.selection.impact_preview_ref.content_hash
                or preview.task_id != current.task_id
                or preview.brief_ref.resource_id != current.brief_id
                or preview.brief_ref.revision != current.revision
                or preview.brief_ref.content_hash != current.content_hash
                or _value(preview.lifecycle) != "frozen"
                or _value(preview.readiness) != "ready"
                or preview.expires_at <= self._clock()
            ):
                raise MediaDeliveryConflict("ImpactPreview exact binding is stale or not ready")
            selection = body.selection
            request = CreateActionProposalRequest(
                actionTypeId="content.publish", taskId=current.task_id,
                objectRef=ResourceRef(resourceType="Artifact", resourceId=selection.variant_ref.resource_id, revision=str(selection.variant_ref.revision), authority="aos://aip/artifacts"),
                purpose=body.purpose,
                payload={"publishCandidate": {
                    "familyId": selection.family_id,
                    "familyVersion": selection.family_version,
                    "selectedVariantRef": {"artifactId": selection.variant_ref.resource_id, "contentHash": selection.variant_ref.content_hash},
                    "gateSetRef": {"gateSetId": selection.gate_set_ref.resource_id, "contentHash": selection.gate_set_ref.content_hash},
                }},
                impactPreviewRef=ExactRevisionRef.model_validate(selection.impact_preview_ref.model_dump(mode="json", by_alias=True)),
                expiresAt=preview.expires_at,
            )
            created = self._actions.create_proposal(principal, key, request)
            readback = self._action_store.get_proposal(scope, created.proposal.id)
            if (
                readback.proposal.id != created.proposal.id
                or readback.proposal.version != created.proposal.version
                or readback.proposal.proposal_hash != created.proposal.proposal_hash
                or readback.proposal.payload != request.payload
            ):
                raise MediaDeliveryConflict("publish Proposal canonical readback drifted")
        except MediaDeliveryError:
            raise
        except Exception as exc:
            raise MediaDeliveryConflict(str(exc)) from exc
        return MediaDeliveryPublishProposalResponse(
            tenant=self._tenant(scope),
            proposal=MediaDeliveryProposalRef(
                proposalId=readback.proposal.id, version=readback.proposal.version,
                proposalHash=readback.proposal.proposal_hash, status=_value(readback.proposal.status),
            ),
            sideEffects=MediaDeliverySideEffects(),
            message=f"发布 Proposal 已创建；当前仍未执行外部发布。候选 {candidate.variant_ref.resource_id}。",
        )

    def _candidates(self, scope: TenantScope, current) -> list[MediaDeliveryCandidate]:
        gates = list(self._production.list_media_gate_sets(scope).items)
        issues = list(self._production.list_review_issues(scope).items)
        decisions = list(self._production.list_return_decisions(scope).items)
        previews = [
            item for item in self._production.list_impact_previews(scope).items
            if item.task_id == current.task_id
            and item.brief_ref.resource_id == current.brief_id
            and item.brief_ref.revision == current.revision
            and item.brief_ref.content_hash == current.content_hash
        ]
        result = []
        for family in self._production.list_artifact_families(scope).items:
            if _value(family.topology_status) != "current":
                continue
            for group in family.candidate_groups:
                selected = group.selected_ref
                if selected is None:
                    continue
                member = next((item for item in family.members if item.artifact_ref.artifact_id == selected.artifact_id and item.artifact_ref.content_hash == selected.content_hash), None)
                if member is None:
                    continue
                gate = next((item for item in gates if item.family_id == family.family_id and item.artifact_ref.artifact_id == selected.artifact_id and item.artifact_ref.content_hash == selected.content_hash), None)
                related_issues = [item for item in issues if item.artifact_ref.artifact_id == selected.artifact_id and item.artifact_ref.content_hash == selected.content_hash]
                issue_ids = {item.issue_id for item in related_issues}
                blocker_codes = []
                if gate is None:
                    blocker_codes.append("MEDIA_GATE_SET_NOT_AVAILABLE")
                elif _value(gate.readiness) != "ready" or not gate.eligible_for_approval:
                    blocker_codes.append("MEDIA_GATE_SET_NOT_READY")
                if any(_value(item.status) in {"open", "returned"} for item in related_issues):
                    blocker_codes.append("MEDIA_REVIEW_ISSUE_UNRESOLVED")
                current_previews = [item for item in previews if _value(item.lifecycle) == "frozen" and _value(item.readiness) == "ready" and item.expires_at > self._clock()]
                if not current_previews:
                    blocker_codes.append("MEDIA_IMPACT_PREVIEW_NOT_CURRENT_READY")
                result.append(MediaDeliveryCandidate(
                    familyId=family.family_id, familyVersion=family.version,
                    variantRef=MediaDeliveryExactRef(resourceType="ArtifactRevision", resourceId=selected.artifact_id, revision=member.family_revision, contentHash=selected.content_hash),
                    gateSetRef=None if gate is None else MediaDeliveryExactRef(resourceType="MediaGateSetDecision", resourceId=gate.gate_set_id, revision=1, contentHash=gate.content_hash),
                    gateReadiness=None if gate is None else _value(gate.readiness),
                    impactPreviewRefs=[MediaDeliveryExactRef(resourceType="ImpactPreviewRevision", resourceId=item.preview_id, revision=item.revision, contentHash=item.content_hash) for item in current_previews],
                    reviewIssues=[MediaDeliveryReviewIssue(issueId=item.issue_id, version=item.version, status=_value(item.status), severity=_value(item.severity), returnStage=item.return_stage) for item in related_issues],
                    returnDecisionCount=sum(1 for item in decisions if item.issue_id in issue_ids),
                    publishReady=not blocker_codes, blockerCodes=sorted(blocker_codes),
                ))
        return result

    @staticmethod
    def _select_candidate(workspace: MediaDeliveryWorkspaceResponse, selection: MediaDeliverySelection, *, require_ready: bool) -> MediaDeliveryCandidate:
        candidate = next((item for item in workspace.candidates if item.family_id == selection.family_id and item.family_version == selection.family_version and item.variant_ref == selection.variant_ref and item.gate_set_ref == selection.gate_set_ref and selection.impact_preview_ref in item.impact_preview_refs), None)
        if candidate is None:
            raise MediaDeliveryConflict("delivery selection exact refs are stale or unavailable")
        if require_ready and not candidate.publish_ready:
            raise MediaDeliveryConflict("delivery selection is not ready for publish Proposal")
        return candidate

    def _exact_brief(self, scope: TenantScope, exact: MediaDeliveryExactRef, expected_version: int):
        current = self._briefs.get_brief(scope, exact.resource_id)
        self._require_media_brief(current)
        if current.brief_id != exact.resource_id or current.revision != exact.revision or current.content_hash != exact.content_hash or current.version != expected_version:
            raise MediaDeliveryConflict("draft exact ref or expectedVersion is stale")
        return current

    def _require_media_brief(self, value) -> None:
        if value.brief_type != "media_internal_workflow" or value.schema_ref != self.media_schema_ref():
            raise MediaDeliveryConflict("task brief is not a media internal workflow")
        spec = value.spec
        if not isinstance(spec, dict) or spec.get("externalEffectsAllowed") is not False or spec.get("mediaType") not in {"planting_copy", "short_video", "digital_human_live"}:
            raise MediaDeliveryConflict("media workflow safety authority is invalid")

    @staticmethod
    def _draft(value) -> MediaInternalWorkflowDraft:
        return MediaInternalWorkflowDraft(
            resourceId=value.brief_id, revision=value.revision, version=value.version,
            contentHash=value.content_hash, mediaType=value.spec["mediaType"], title=value.spec["title"],
            summary=value.spec["summary"], details=value.spec["details"], status=value.spec["status"],
        )


__all__ = ["EcommerceMediaDelivery", "MediaDeliveryConflict", "MediaDeliveryError"]
