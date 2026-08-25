"""PostgreSQL authority for W6-02 profile recommendation and merge receipts."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from aos_api.aip_contracts import TenantContext
from aos_api.aip_production_contract_store import ProductionContractDependencyBlocked
from aos_api.aip_responsibility_profile import (
    ConfirmResponsibilityProfileRequest,
    CreateMergeDecisionRequest,
    CreateMergePolicyRequest,
    MergeDecisionReceipt,
    MergePolicyRevision,
    PROFILE_ORDER,
    ProfileConfirmationReceipt,
    ProfileRecommendationRevision,
    RecommendResponsibilityProfileRequest,
    ResponsibilityProfile,
)
from aos_api.aip_responsibility_template_authority import resolve_responsibility_template
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _identifier(prefix: str, scope: TenantScope, *parts: object) -> str:
    return f"{prefix}-{_hash([*scope.key, *parts])[:24]}"


class AipResponsibilityProfileStore:
    def __init__(
        self,
        connect_factory: Callable[[TenantScope], Any] = connect,
        template_resolver: Callable[[TenantScope, Any], bool] = resolve_responsibility_template,
    ) -> None:
        self._connect = connect_factory
        self._template_resolver = template_resolver

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    @staticmethod
    def _load(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value

    def create_policy(
        self, scope: TenantScope, request: CreateMergePolicyRequest, actor: str, *, now: datetime
    ) -> MergePolicyRevision:
        payload = request.model_dump(mode="json", by_alias=True)
        content_hash = _hash(payload)
        if request.expires_at <= now:
            raise ProductionContractDependencyBlocked("MERGE_POLICY_ALREADY_EXPIRED")
        with self._connect(scope) as conn:
            conn.execute(
                """INSERT INTO aip_merge_policy_revision(
                  org_id,project_id,policy_id,revision,minimum_profile,maximum_risk_level,
                  allowed_merge_groups,protected_responsibility_types,expires_at,content_hash,created_by,created_at)
                  VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s)
                  ON CONFLICT (org_id,project_id,policy_id,revision) DO NOTHING""",
                (*scope.key, request.policy_id, request.revision, request.minimum_profile.value,
                 request.maximum_risk_level, _json(request.allowed_merge_groups),
                 _json(request.protected_responsibility_types), request.expires_at,
                 content_hash, actor, now),
            )
            row = conn.execute(
                """SELECT * FROM aip_merge_policy_revision
                   WHERE org_id=%s AND project_id=%s AND policy_id=%s AND revision=%s""",
                (*scope.key, request.policy_id, request.revision),
            ).fetchone()
            if row["content_hash"] != content_hash:
                raise ProductionContractDependencyBlocked("MERGE_POLICY_IDEMPOTENCY_CONFLICT")
            conn.commit()
            return self._policy(scope, row)

    def recommend(
        self, scope: TenantScope, request: RecommendResponsibilityProfileRequest,
        actor: str, *, now: datetime,
    ) -> ProfileRecommendationRevision:
        if any(not self._template_resolver(scope, ref) for ref in request.candidate_template_refs.values()):
            raise ProductionContractDependencyBlocked("PROFILE_TEMPLATE_MISSING_OR_DRIFTED")
        with self._connect(scope) as conn:
            policy = self._require_policy(conn, scope, request.policy_ref, now)
            floor = ResponsibilityProfile(policy["minimum_profile"])
            recommended = floor
            reasons = [f"POLICY_FLOOR_{floor.value}"]
            if request.risk_level >= 2 or request.channel_count >= 3 or request.unknown_codes:
                recommended = max(
                    recommended, ResponsibilityProfile.STANDARD, key=PROFILE_ORDER.get
                )
                reasons.append("RISK_OR_COMPLEXITY_REQUIRES_STANDARD")
            if request.risk_level >= 3 or request.channel_count >= 8:
                recommended = ResponsibilityProfile.FULL
                reasons.append("HIGH_RISK_OR_CHANNEL_SPAN_REQUIRES_FULL")
            if request.requested_profile is not None:
                recommended = max(recommended, request.requested_profile, key=PROFILE_ORDER.get)
                reasons.append("REQUESTED_PROFILE_FLOOR_APPLIED")
            snapshot = {
                **request.model_dump(mode="json", by_alias=True),
                "recommendedProfile": recommended.value,
                "reasonCodes": sorted(set(reasons)),
                "policyContentHash": policy["content_hash"],
            }
            snapshot_hash = _hash(snapshot)
            recommendation_id = _identifier("profile-rec", scope, snapshot_hash)
            content_hash = _hash({**snapshot, "snapshotHash": snapshot_hash})
            expires_at = now + timedelta(seconds=request.freshness_seconds)
            conn.execute(
                """INSERT INTO aip_profile_recommendation_revision(
                  org_id,project_id,recommendation_id,revision,subject_ref,recommended_profile,
                  candidate_template_refs,selected_template_ref,policy_ref,risk_level,channel_count,
                  reason_codes,unknown_codes,snapshot_hash,content_hash,expires_at,created_by,created_at)
                  VALUES(%s,%s,%s,1,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s)
                  ON CONFLICT (org_id,project_id,recommendation_id,revision) DO NOTHING""",
                (*scope.key, recommendation_id, _json(snapshot["subjectRef"]), recommended.value,
                 _json(snapshot["candidateTemplateRefs"]),
                 _json(snapshot["candidateTemplateRefs"][recommended.value]),
                 _json(snapshot["policyRef"]), request.risk_level, request.channel_count,
                 _json(sorted(set(reasons))), _json(request.unknown_codes), snapshot_hash,
                 content_hash, expires_at, actor, now),
            )
            row = conn.execute(
                """SELECT * FROM aip_profile_recommendation_revision
                   WHERE org_id=%s AND project_id=%s AND recommendation_id=%s AND revision=1""",
                (*scope.key, recommendation_id),
            ).fetchone()
            if row["content_hash"] != content_hash:
                raise ProductionContractDependencyBlocked("PROFILE_RECOMMENDATION_IDEMPOTENCY_CONFLICT")
            conn.commit()
            return self._recommendation(scope, row)

    def confirm(
        self, scope: TenantScope, request: ConfirmResponsibilityProfileRequest,
        actor: str, *, now: datetime,
    ) -> ProfileConfirmationReceipt:
        with self._connect(scope) as conn:
            row = conn.execute(
                """SELECT * FROM aip_profile_recommendation_revision
                   WHERE org_id=%s AND project_id=%s AND recommendation_id=%s AND revision=%s""",
                (*scope.key, request.recommendation_id, request.recommendation_revision),
            ).fetchone()
            if row is None or row["content_hash"] != request.recommendation_hash:
                raise ProductionContractDependencyBlocked("PROFILE_RECOMMENDATION_MISSING_OR_DRIFTED")
            if row["expires_at"] <= now:
                raise ProductionContractDependencyBlocked("PROFILE_RECOMMENDATION_STALE")
            recommended = ResponsibilityProfile(row["recommended_profile"])
            if PROFILE_ORDER[request.selected_profile] < PROFILE_ORDER[recommended]:
                raise ProductionContractDependencyBlocked("PROFILE_DOWNGRADE_BELOW_RECOMMENDATION_FORBIDDEN")
            templates = self._load(row["candidate_template_refs"])
            selected_template = templates[request.selected_profile.value]
            payload = {
                **request.model_dump(mode="json", by_alias=True),
                "selectedTemplateRef": selected_template,
                "policyRef": self._load(row["policy_ref"]),
                "actor": actor,
            }
            content_hash = _hash(payload)
            confirmation_id = _identifier("profile-confirm", scope, content_hash)
            conn.execute(
                """INSERT INTO aip_profile_confirmation_receipt(
                  org_id,project_id,confirmation_id,recommendation_id,recommendation_revision,
                  recommendation_hash,selected_profile,selected_template_ref,policy_ref,actor,reason,content_hash,created_at)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s)
                  ON CONFLICT (org_id,project_id,confirmation_id) DO NOTHING""",
                (*scope.key, confirmation_id, request.recommendation_id,
                 request.recommendation_revision, request.recommendation_hash,
                 request.selected_profile.value, _json(selected_template),
                 _json(self._load(row["policy_ref"])), actor, request.reason, content_hash, now),
            )
            receipt = conn.execute(
                """SELECT * FROM aip_profile_confirmation_receipt
                   WHERE org_id=%s AND project_id=%s AND confirmation_id=%s""",
                (*scope.key, confirmation_id),
            ).fetchone()
            conn.commit()
            return self._confirmation(scope, receipt)

    def create_merge_decision(
        self, scope: TenantScope, request: CreateMergeDecisionRequest,
        actor: str, *, now: datetime,
    ) -> MergeDecisionReceipt:
        with self._connect(scope) as conn:
            policy = self._require_policy(conn, scope, request.policy_ref, now)
            confirmation = conn.execute(
                """SELECT * FROM aip_profile_confirmation_receipt
                   WHERE org_id=%s AND project_id=%s AND confirmation_id=%s""",
                (*scope.key, request.confirmation_id),
            ).fetchone()
            if confirmation is None or self._load(confirmation["policy_ref"]) != request.policy_ref.model_dump(mode="json", by_alias=True):
                raise ProductionContractDependencyBlocked("PROFILE_CONFIRMATION_MISSING_OR_POLICY_DRIFTED")
            plan = conn.execute(
                """SELECT slots,content_hash FROM aip_responsibility_plan_revision
                   WHERE org_id=%s AND project_id=%s AND plan_id=%s AND revision=%s""",
                (*scope.key, request.plan_ref.resource_id, request.plan_ref.revision),
            ).fetchone()
            if plan is None or plan["content_hash"] != request.plan_ref.content_hash:
                raise ProductionContractDependencyBlocked("RESPONSIBILITY_PLAN_MISSING_OR_DRIFTED")
            slots = {item["slotId"]: item for item in self._load(plan["slots"])}
            identities = [*request.source_slot_ids, request.target_slot_id]
            if any(item not in slots for item in identities):
                raise ProductionContractDependencyBlocked("MERGE_SLOT_MISSING")
            allowed = {tuple(sorted(group)) for group in self._load(policy["allowed_merge_groups"])}
            if tuple(sorted(identities)) not in allowed:
                raise ProductionContractDependencyBlocked("MERGE_GROUP_NOT_ALLOWED")
            protected = set(self._load(policy["protected_responsibility_types"]))
            responsibility_types = sorted({slots[item]["responsibilityType"] for item in identities})
            if protected.intersection(responsibility_types):
                raise ProductionContractDependencyBlocked("PROTECTED_RESPONSIBILITY_MERGE_FORBIDDEN")
            capability_union = sorted({cap for item in identities for cap in slots[item]["requiredCapabilityIds"]})
            assignee_receipt = conn.execute(
                """SELECT status,required_capability_refs,snapshot_hash,expires_at
                   FROM aip_assignee_resolution_receipt
                   WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
                (*scope.key, request.target_assignee_resolution_receipt_id),
            ).fetchone()
            if assignee_receipt is None or assignee_receipt["status"] != "resolved" or not assignee_receipt["snapshot_hash"] or assignee_receipt["expires_at"] <= now:
                raise ProductionContractDependencyBlocked("MERGE_TARGET_ASSIGNEE_NOT_EXACT_FRESH")
            covered = {
                item.get("assetId") for item in self._load(assignee_receipt["required_capability_refs"])
                if isinstance(item, dict) and item.get("assetType") == "CapabilityRevision"
            }
            if not set(capability_union) <= covered:
                raise ProductionContractDependencyBlocked("MERGE_CAPABILITY_UNION_NOT_COVERED")
            payload = {
                **request.model_dump(mode="json", by_alias=True),
                "mergedResponsibilityTypes": responsibility_types,
                "capabilityUnion": capability_union,
                "actor": actor,
            }
            content_hash = _hash(payload)
            receipt_id = _identifier("merge-decision", scope, content_hash)
            conn.execute(
                """INSERT INTO aip_merge_decision_receipt(
                  org_id,project_id,receipt_id,plan_ref,policy_ref,confirmation_id,source_slot_ids,
                  target_slot_id,merged_responsibility_types,capability_union,
                  target_assignee_resolution_receipt_id,actor,reason,content_hash,created_at)
                  VALUES(%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s)
                  ON CONFLICT (org_id,project_id,receipt_id) DO NOTHING""",
                (*scope.key, receipt_id, _json(payload["planRef"]), _json(payload["policyRef"]),
                 request.confirmation_id, _json(request.source_slot_ids), request.target_slot_id,
                 _json(responsibility_types), _json(capability_union),
                 request.target_assignee_resolution_receipt_id, actor, request.reason,
                 content_hash, now),
            )
            row = conn.execute(
                """SELECT * FROM aip_merge_decision_receipt
                   WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
                (*scope.key, receipt_id),
            ).fetchone()
            conn.commit()
            return self._merge_receipt(scope, row)

    def _require_policy(self, conn: Any, scope: TenantScope, ref: Any, now: datetime) -> Any:
        row = conn.execute(
            """SELECT * FROM aip_merge_policy_revision
               WHERE org_id=%s AND project_id=%s AND policy_id=%s AND revision=%s""",
            (*scope.key, ref.resource_id, ref.revision),
        ).fetchone()
        if row is None or row["content_hash"] != ref.content_hash:
            raise ProductionContractDependencyBlocked("MERGE_POLICY_MISSING_OR_DRIFTED")
        if row["expires_at"] <= now:
            raise ProductionContractDependencyBlocked("MERGE_POLICY_STALE")
        return row

    def _policy(self, scope: TenantScope, row: Any) -> MergePolicyRevision:
        return MergePolicyRevision(
            tenant=self._tenant(scope), policyId=row["policy_id"], revision=row["revision"],
            minimumProfile=row["minimum_profile"], maximumRiskLevel=row["maximum_risk_level"],
            allowedMergeGroups=self._load(row["allowed_merge_groups"]),
            protectedResponsibilityTypes=self._load(row["protected_responsibility_types"]),
            expiresAt=row["expires_at"], contentHash=row["content_hash"],
            createdBy=row["created_by"], createdAt=row["created_at"],
        )

    def _recommendation(self, scope: TenantScope, row: Any) -> ProfileRecommendationRevision:
        return ProfileRecommendationRevision(
            tenant=self._tenant(scope), recommendationId=row["recommendation_id"], revision=row["revision"],
            subjectRef=self._load(row["subject_ref"]), recommendedProfile=row["recommended_profile"],
            candidateTemplateRefs=self._load(row["candidate_template_refs"]),
            selectedTemplateRef=self._load(row["selected_template_ref"]), policyRef=self._load(row["policy_ref"]),
            riskLevel=row["risk_level"], channelCount=row["channel_count"], reasonCodes=self._load(row["reason_codes"]),
            unknownCodes=self._load(row["unknown_codes"]), snapshotHash=row["snapshot_hash"], contentHash=row["content_hash"],
            expiresAt=row["expires_at"], createdBy=row["created_by"], createdAt=row["created_at"],
        )

    def _confirmation(self, scope: TenantScope, row: Any) -> ProfileConfirmationReceipt:
        return ProfileConfirmationReceipt(
            tenant=self._tenant(scope), confirmationId=row["confirmation_id"], recommendationId=row["recommendation_id"],
            recommendationRevision=row["recommendation_revision"], recommendationHash=row["recommendation_hash"],
            selectedProfile=row["selected_profile"], selectedTemplateRef=self._load(row["selected_template_ref"]),
            policyRef=self._load(row["policy_ref"]), actor=row["actor"], reason=row["reason"],
            contentHash=row["content_hash"], createdAt=row["created_at"],
        )

    def _merge_receipt(self, scope: TenantScope, row: Any) -> MergeDecisionReceipt:
        return MergeDecisionReceipt(
            tenant=self._tenant(scope), receiptId=row["receipt_id"], planRef=self._load(row["plan_ref"]),
            policyRef=self._load(row["policy_ref"]), confirmationId=row["confirmation_id"],
            sourceSlotIds=self._load(row["source_slot_ids"]), targetSlotId=row["target_slot_id"],
            mergedResponsibilityTypes=self._load(row["merged_responsibility_types"]), capabilityUnion=self._load(row["capability_union"]),
            targetAssigneeResolutionReceiptId=row["target_assignee_resolution_receipt_id"], actor=row["actor"],
            reason=row["reason"], contentHash=row["content_hash"], createdAt=row["created_at"],
        )


__all__ = ["AipResponsibilityProfileStore"]
