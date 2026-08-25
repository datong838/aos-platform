"""PostgreSQL authority for W6-02 profile recommendation and merge receipts."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_runtime_contracts import ModelPriceSnapshotRevision
from aos_api.aip_production_contract_store import (
    ProductionContractDependencyBlocked,
    ProductionContractIdempotencyConflict,
)
from aos_api.aip_responsibility_profile import (
    ConfirmResponsibilityProfileRequest,
    CreateMergeDecisionRequest,
    CreateMergePolicyRequest,
    MergeDecisionReceipt,
    MergePolicyRevision,
    PROFILE_ORDER,
    ProfileConfirmationListResponse,
    ProfileConfirmationReceipt,
    ProfileRecommendationListResponse,
    ProfileRecommendationRevision,
    ProjectedCostRange,
    RecommendMediaResponsibilityProfileRequest,
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
        price_resolver: Callable[
            [TenantScope, Any, datetime], ModelPriceSnapshotRevision | None
        ]
        | None = None,
    ) -> None:
        self._connect = connect_factory
        self._template_resolver = template_resolver
        self._price_resolver = price_resolver or self._resolve_price_snapshot

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

    def recommend_media(
        self,
        scope: TenantScope,
        request: RecommendMediaResponsibilityProfileRequest,
        actor: str,
        *,
        now: datetime,
    ) -> ProfileRecommendationRevision:
        template_refs = [
            *request.candidate_template_refs.values(),
            *request.stage_template_refs.values(),
        ]
        if any(not self._template_resolver(scope, ref) for ref in template_refs):
            raise ProductionContractDependencyBlocked(
                "MEDIA_PROFILE_TEMPLATE_MISSING_OR_DRIFTED"
            )
        projected_cost_ranges = self._project_cost_ranges(scope, request, now)
        blockers = sorted(
            {
                *request.unknown_codes,
                *(
                    code
                    for item in projected_cost_ranges
                    for code in item.unknown_codes
                ),
                *request.projected_duration.unknown_codes,
            }
        )
        readiness = "blocked" if blockers else "ready"
        confidence = "unknown" if blockers else "medium"
        dependency_refs = [
            request.subject_ref,
            request.evidence_bundle_ref,
            request.eval_contract_ref,
            request.policy_ref,
            *request.candidate_template_refs.values(),
            *request.stage_template_refs.values(),
            *(
                item.price_snapshot_ref
                for item in request.cost_inputs
                if item.price_snapshot_ref is not None
            ),
            *(ref for item in request.cost_inputs for ref in item.license_refs),
        ]
        unique_dependencies = {
            (item.resource_type, item.resource_id, item.revision, item.content_hash): item
            for item in dependency_refs
        }
        dependency_refs = [
            unique_dependencies[key] for key in sorted(unique_dependencies)
        ]
        with self._connect(scope) as conn:
            policy = self._require_policy(conn, scope, request.policy_ref, now)
            floor = ResponsibilityProfile(policy["minimum_profile"])
            recommended = floor
            reasons = [f"POLICY_FLOOR_{floor.value}"]
            if request.risk_level >= 2 or request.channel_count >= 3 or blockers:
                recommended = max(
                    recommended, ResponsibilityProfile.STANDARD, key=PROFILE_ORDER.get
                )
                reasons.append("RISK_COMPLEXITY_OR_UNKNOWN_REQUIRES_STANDARD")
            if request.risk_level >= 3 or request.channel_count >= 8:
                recommended = ResponsibilityProfile.FULL
                reasons.append("HIGH_RISK_OR_CHANNEL_SPAN_REQUIRES_FULL")
            if request.requested_profile is not None:
                recommended = max(
                    recommended, request.requested_profile, key=PROFILE_ORDER.get
                )
                reasons.append("REQUESTED_PROFILE_FLOOR_APPLIED")
            snapshot = {
                **request.model_dump(mode="json", by_alias=True),
                "recommendedProfile": recommended.value,
                "reasonCodes": sorted(set(reasons)),
                "policyContentHash": policy["content_hash"],
                "dependencyRefs": [
                    item.model_dump(mode="json", by_alias=True)
                    for item in dependency_refs
                ],
                "projectedCostRanges": [
                    item.model_dump(mode="json", by_alias=True)
                    for item in projected_cost_ranges
                ],
                "readiness": readiness,
                "blockers": blockers,
            }
            snapshot_hash = _hash(snapshot)
            recommendation_id = _identifier("media-profile-rec", scope, snapshot_hash)
            content_hash = _hash({**snapshot, "snapshotHash": snapshot_hash})
            expires_at = min(
                now + timedelta(seconds=request.freshness_seconds),
                policy["expires_at"],
                *(item.expires_at for item in projected_cost_ranges),
            )
            conn.execute(
                """INSERT INTO aip_profile_recommendation_revision(
                  org_id,project_id,recommendation_id,revision,subject_ref,recommended_profile,
                  candidate_template_refs,selected_template_ref,policy_ref,risk_level,channel_count,
                  reason_codes,unknown_codes,dependency_refs,projected_cost_ranges,
                  projected_duration,assumptions,confidence,readiness,blockers,
                  snapshot_hash,content_hash,expires_at,created_by,created_at)
                  VALUES(%s,%s,%s,1,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,
                  %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,
                  %s::jsonb,%s,%s,%s,%s,%s)
                  ON CONFLICT (org_id,project_id,recommendation_id,revision) DO NOTHING""",
                (
                    *scope.key,
                    recommendation_id,
                    _json(snapshot["subjectRef"]),
                    recommended.value,
                    _json(snapshot["candidateTemplateRefs"]),
                    _json(snapshot["candidateTemplateRefs"][recommended.value]),
                    _json(snapshot["policyRef"]),
                    request.risk_level,
                    request.channel_count,
                    _json(sorted(set(reasons))),
                    _json(request.unknown_codes),
                    _json(snapshot["dependencyRefs"]),
                    _json(snapshot["projectedCostRanges"]),
                    _json(
                        request.projected_duration.model_dump(
                            mode="json", by_alias=True
                        )
                    ),
                    _json(request.assumptions),
                    confidence,
                    readiness,
                    _json(blockers),
                    snapshot_hash,
                    content_hash,
                    expires_at,
                    actor,
                    now,
                ),
            )
            row = conn.execute(
                """SELECT * FROM aip_profile_recommendation_revision
                   WHERE org_id=%s AND project_id=%s
                     AND recommendation_id=%s AND revision=1""",
                (*scope.key, recommendation_id),
            ).fetchone()
            if row["content_hash"] != content_hash:
                raise ProductionContractDependencyBlocked(
                    "MEDIA_PROFILE_RECOMMENDATION_IDEMPOTENCY_CONFLICT"
                )
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

    def confirm_media(
        self,
        scope: TenantScope,
        request: ConfirmResponsibilityProfileRequest,
        actor: str,
        *,
        now: datetime,
        idempotency_key: str,
        expected_etag: str,
    ) -> ProfileConfirmationReceipt:
        command = {
            **request.model_dump(mode="json", by_alias=True),
            "actor": actor,
            "idempotencyKey": idempotency_key,
            "expectedEtag": expected_etag,
        }
        command_hash = _hash(command)
        with self._connect(scope) as conn:
            existing = conn.execute(
                """SELECT * FROM aip_profile_confirmation_receipt
                   WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
                (*scope.key, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing.get("command_hash") != command_hash:
                    raise ProductionContractIdempotencyConflict(
                        "PROFILE_CONFIRMATION_IDEMPOTENCY_CONFLICT"
                    )
                return self._confirmation(scope, existing)
            row = conn.execute(
                """SELECT * FROM aip_profile_recommendation_revision
                   WHERE org_id=%s AND project_id=%s
                     AND recommendation_id=%s AND revision=%s""",
                (
                    *scope.key,
                    request.recommendation_id,
                    request.recommendation_revision,
                ),
            ).fetchone()
            if (
                row is None
                or row["content_hash"] != request.recommendation_hash
                or expected_etag != request.recommendation_hash
            ):
                raise ProductionContractDependencyBlocked(
                    "PROFILE_RECOMMENDATION_MISSING_OR_DRIFTED"
                )
            if row["expires_at"] <= now:
                raise ProductionContractDependencyBlocked(
                    "PROFILE_RECOMMENDATION_STALE"
                )
            if row.get("readiness") != "ready" or self._load(
                row.get("blockers") or []
            ):
                raise ProductionContractDependencyBlocked(
                    "PROFILE_RECOMMENDATION_NOT_READY"
                )
            recommended = ResponsibilityProfile(row["recommended_profile"])
            if PROFILE_ORDER[request.selected_profile] < PROFILE_ORDER[recommended]:
                raise ProductionContractDependencyBlocked(
                    "PROFILE_DOWNGRADE_BELOW_RECOMMENDATION_FORBIDDEN"
                )
            templates = self._load(row["candidate_template_refs"])
            selected_template = templates[request.selected_profile.value]
            selected_costs = [
                item
                for item in self._load(row.get("projected_cost_ranges") or [])
                if item.get("profile") == request.selected_profile.value
            ]
            if not selected_costs or any(item.get("unknownCodes") for item in selected_costs):
                raise ProductionContractDependencyBlocked(
                    "SELECTED_PROFILE_PROJECTED_COST_NOT_READY"
                )
            payload = {
                **request.model_dump(mode="json", by_alias=True),
                "selectedTemplateRef": selected_template,
                "policyRef": self._load(row["policy_ref"]),
                "selectedProjectedCostRanges": selected_costs,
                "recommendationEtag": expected_etag,
                "actor": actor,
            }
            content_hash = _hash(payload)
            confirmation_id = _identifier(
                "media-profile-confirm", scope, idempotency_key
            )
            conn.execute(
                """INSERT INTO aip_profile_confirmation_receipt(
                  org_id,project_id,confirmation_id,recommendation_id,
                  recommendation_revision,recommendation_hash,selected_profile,
                  selected_template_ref,policy_ref,recommendation_etag,idempotency_key,
                  command_hash,selected_projected_cost_ranges,actor,reason,
                  content_hash,created_at)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,
                  %s::jsonb,%s,%s,%s,%s)
                  ON CONFLICT (org_id,project_id,idempotency_key) DO NOTHING""",
                (
                    *scope.key,
                    confirmation_id,
                    request.recommendation_id,
                    request.recommendation_revision,
                    request.recommendation_hash,
                    request.selected_profile.value,
                    _json(selected_template),
                    _json(self._load(row["policy_ref"])),
                    expected_etag,
                    idempotency_key,
                    command_hash,
                    _json(selected_costs),
                    actor,
                    request.reason,
                    content_hash,
                    now,
                ),
            )
            receipt = conn.execute(
                """SELECT * FROM aip_profile_confirmation_receipt
                   WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
                (*scope.key, idempotency_key),
            ).fetchone()
            if receipt.get("command_hash") != command_hash:
                raise ProductionContractIdempotencyConflict(
                    "PROFILE_CONFIRMATION_IDEMPOTENCY_CONFLICT"
                )
            conn.commit()
            return self._confirmation(scope, receipt)

    def list_recommendations(
        self, scope: TenantScope
    ) -> ProfileRecommendationListResponse:
        with self._connect(scope) as conn:
            rows = conn.execute(
                """SELECT * FROM aip_profile_recommendation_revision
                   WHERE org_id=%s AND project_id=%s
                   ORDER BY created_at DESC,recommendation_id,revision DESC""",
                scope.key,
            ).fetchall()
        items = [self._recommendation(scope, row) for row in rows]
        return ProfileRecommendationListResponse(
            tenant=self._tenant(scope), items=items, count=len(items)
        )

    def list_confirmations(
        self, scope: TenantScope
    ) -> ProfileConfirmationListResponse:
        with self._connect(scope) as conn:
            rows = conn.execute(
                """SELECT * FROM aip_profile_confirmation_receipt
                   WHERE org_id=%s AND project_id=%s
                   ORDER BY created_at DESC,confirmation_id""",
                scope.key,
            ).fetchall()
        items = [self._confirmation(scope, row) for row in rows]
        return ProfileConfirmationListResponse(
            tenant=self._tenant(scope), items=items, count=len(items)
        )

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

    def _project_cost_ranges(
        self,
        scope: TenantScope,
        request: RecommendMediaResponsibilityProfileRequest,
        now: datetime,
    ) -> list[ProjectedCostRange]:
        groups: dict[tuple[ResponsibilityProfile, str], dict[str, Any]] = {}
        for item in request.cost_inputs:
            if item.expires_at <= now:
                raise ProductionContractDependencyBlocked(
                    "PROJECTED_COST_INPUT_STALE"
                )
            key = (item.profile, item.currency)
            group = groups.setdefault(
                key,
                {
                    "count": 0,
                    "refs": [],
                    "lower": Decimal("0"),
                    "upper": Decimal("0"),
                    "assumptions": set(),
                    "unknown": set(),
                    "expiresAt": item.expires_at,
                },
            )
            group["count"] += 1
            group["assumptions"].update(item.assumptions)
            group["unknown"].update(item.unknown_codes)
            group["expiresAt"] = min(group["expiresAt"], item.expires_at)
            if item.unknown_codes:
                continue
            if (
                item.price_snapshot_ref is None
                or item.quantity_lower is None
                or item.quantity_upper is None
            ):
                raise ProductionContractDependencyBlocked(
                    "PROJECTED_COST_INPUT_INCOMPLETE"
                )
            snapshot = self._price_resolver(scope, item.price_snapshot_ref, now)
            if snapshot is None:
                raise ProductionContractDependencyBlocked(
                    "MODEL_PRICE_SNAPSHOT_MISSING_OR_DRIFTED"
                )
            if snapshot.currency != item.currency:
                raise ProductionContractDependencyBlocked(
                    "PROJECTED_COST_CURRENCY_DRIFTED"
                )
            price = {
                "input_tokens": snapshot.input_token_price,
                "output_tokens": snapshot.output_token_price,
                "cached_tokens": snapshot.cached_token_price,
            }[item.usage_basis]
            if price is None:
                raise ProductionContractDependencyBlocked(
                    "PROJECTED_COST_USAGE_PRICE_UNKNOWN"
                )
            unit_price = Decimal(str(price)) / Decimal(snapshot.token_unit)
            group["lower"] += (
                item.quantity_lower * unit_price
                + item.tax_lower
                + item.platform_fee_lower
                + item.license_fee_lower
                + item.redundancy_lower
            )
            group["upper"] += (
                item.quantity_upper * unit_price
                + item.tax_upper
                + item.platform_fee_upper
                + item.license_fee_upper
                + item.redundancy_upper
            )
            group["refs"].append(item.price_snapshot_ref)
            if snapshot.effective_until is not None:
                group["expiresAt"] = min(
                    group["expiresAt"], snapshot.effective_until
                )
        result: list[ProjectedCostRange] = []
        for (profile, currency), group in sorted(
            groups.items(), key=lambda item: (PROFILE_ORDER[item[0][0]], item[0][1])
        ):
            unknown_codes = sorted(group["unknown"])
            result.append(
                ProjectedCostRange(
                    profile=profile,
                    currency=currency,
                    componentCount=group["count"],
                    priceSnapshotRefs=group["refs"],
                    lowerAmount=None if unknown_codes else group["lower"],
                    upperAmount=None if unknown_codes else group["upper"],
                    assumptions=sorted(group["assumptions"]),
                    unknownCodes=unknown_codes,
                    confidence="unknown" if unknown_codes else "medium",
                    expiresAt=group["expiresAt"],
                )
            )
        return result

    def _resolve_price_snapshot(
        self, scope: TenantScope, ref: Any, now: datetime
    ) -> ModelPriceSnapshotRevision | None:
        if ref.resource_type != "ModelPriceSnapshotRevision":
            return None
        try:
            with self._connect(scope) as conn:
                row = conn.execute(
                    """SELECT content_hash,lifecycle,payload
                       FROM aip_model_price_snapshot_revision
                       WHERE org_id=%s AND project_id=%s
                         AND model_price_snapshot_id=%s AND revision=%s""",
                    (*scope.key, ref.resource_id, ref.revision),
                ).fetchone()
            if (
                row is None
                or row["content_hash"] != ref.content_hash
                or row["lifecycle"] != "active"
            ):
                return None
            snapshot = ModelPriceSnapshotRevision.model_validate(
                self._load(row["payload"])
            )
            if (
                snapshot.content_hash != ref.content_hash
                or snapshot.effective_from > now
                or (
                    snapshot.effective_until is not None
                    and snapshot.effective_until <= now
                )
            ):
                return None
            return snapshot
        except Exception:
            return None

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
            unknownCodes=self._load(row["unknown_codes"]),
            dependencyRefs=self._load(row.get("dependency_refs") or []),
            projectedCostRanges=self._load(row.get("projected_cost_ranges") or []),
            projectedDuration=(
                self._load(row.get("projected_duration"))
                if row.get("projected_duration")
                else None
            ),
            assumptions=self._load(row.get("assumptions") or []),
            confidence=row.get("confidence") or "unknown",
            readiness=row.get("readiness") or "unknown",
            blockers=self._load(row.get("blockers") or []),
            snapshotHash=row["snapshot_hash"], contentHash=row["content_hash"],
            expiresAt=row["expires_at"], createdBy=row["created_by"], createdAt=row["created_at"],
        )

    def _confirmation(self, scope: TenantScope, row: Any) -> ProfileConfirmationReceipt:
        return ProfileConfirmationReceipt(
            tenant=self._tenant(scope), confirmationId=row["confirmation_id"], recommendationId=row["recommendation_id"],
            recommendationRevision=row["recommendation_revision"], recommendationHash=row["recommendation_hash"],
            selectedProfile=row["selected_profile"], selectedTemplateRef=self._load(row["selected_template_ref"]),
            policyRef=self._load(row["policy_ref"]), actor=row["actor"], reason=row["reason"],
            recommendationEtag=row.get("recommendation_etag"),
            idempotencyKey=row.get("idempotency_key"),
            selectedProjectedCostRanges=self._load(
                row.get("selected_projected_cost_ranges") or []
            ),
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
