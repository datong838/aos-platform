from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from aos_api.aip_model_runtime_contracts import ModelPriceSnapshotRevision
from aos_api.aip_production_contract_store import (
    ProductionContractDependencyBlocked,
    ProductionContractIdempotencyConflict,
)
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.aip_responsibility_profile import (
    ConfirmResponsibilityProfileRequest,
    CreateMergePolicyRequest,
    ProjectedDurationRange,
    RecommendMediaResponsibilityProfileRequest,
    ResponsibilityProfile,
)
from aos_api.aip_responsibility_profile_store import AipResponsibilityProfileStore
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")


def _ref(kind: str, resource_id: str, content_hash: str = "a" * 64):
    return ExactRevisionRef(
        resourceType=kind,
        resourceId=resource_id,
        revision=1,
        contentHash=content_hash,
    )


class Result:
    def __init__(self, row: Any = None, rows: list[Any] | None = None):
        self.row = row
        self.rows = rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self) -> None:
        self.policy: dict[str, Any] | None = None
        self.recommendation: dict[str, Any] | None = None
        self.confirmation: dict[str, Any] | None = None

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> Result:
        compact = " ".join(sql.split())
        values = params or ()
        if compact.startswith("INSERT INTO aip_merge_policy_revision"):
            self.policy = {
                "policy_id": values[2],
                "revision": values[3],
                "minimum_profile": values[4],
                "maximum_risk_level": values[5],
                "allowed_merge_groups": json.loads(values[6]),
                "protected_responsibility_types": json.loads(values[7]),
                "expires_at": values[8],
                "content_hash": values[9],
                "created_by": values[10],
                "created_at": values[11],
            }
            return Result()
        if "SELECT * FROM aip_merge_policy_revision" in compact:
            return Result(self.policy)
        if compact.startswith("INSERT INTO aip_profile_recommendation_revision"):
            self.recommendation = {
                "recommendation_id": values[2],
                "revision": 1,
                "subject_ref": json.loads(values[3]),
                "recommended_profile": values[4],
                "candidate_template_refs": json.loads(values[5]),
                "selected_template_ref": json.loads(values[6]),
                "policy_ref": json.loads(values[7]),
                "risk_level": values[8],
                "channel_count": values[9],
                "reason_codes": json.loads(values[10]),
                "unknown_codes": json.loads(values[11]),
                "dependency_refs": json.loads(values[12]),
                "projected_cost_ranges": json.loads(values[13]),
                "projected_duration": json.loads(values[14]),
                "assumptions": json.loads(values[15]),
                "confidence": values[16],
                "readiness": values[17],
                "blockers": json.loads(values[18]),
                "snapshot_hash": values[19],
                "content_hash": values[20],
                "expires_at": values[21],
                "created_by": values[22],
                "created_at": values[23],
            }
            return Result()
        if (
            "SELECT * FROM aip_profile_recommendation_revision" in compact
            and "ORDER BY" not in compact
        ):
            return Result(self.recommendation)
        if (
            "SELECT * FROM aip_profile_recommendation_revision" in compact
            and "ORDER BY" in compact
        ):
            return Result(rows=[self.recommendation] if self.recommendation else [])
        if (
            "SELECT * FROM aip_profile_confirmation_receipt" in compact
            and "ORDER BY" not in compact
        ):
            if (
                self.confirmation is not None
                and len(values) >= 3
                and values[2] != self.confirmation.get("idempotency_key")
            ):
                return Result()
            return Result(self.confirmation)
        if (
            "SELECT * FROM aip_profile_confirmation_receipt" in compact
            and "ORDER BY" in compact
        ):
            return Result(rows=[self.confirmation] if self.confirmation else [])
        if compact.startswith("INSERT INTO aip_profile_confirmation_receipt"):
            self.confirmation = {
                "confirmation_id": values[2],
                "recommendation_id": values[3],
                "recommendation_revision": values[4],
                "recommendation_hash": values[5],
                "selected_profile": values[6],
                "selected_template_ref": json.loads(values[7]),
                "policy_ref": json.loads(values[8]),
                "recommendation_etag": values[9],
                "idempotency_key": values[10],
                "command_hash": values[11],
                "selected_projected_cost_ranges": json.loads(values[12]),
                "actor": values[13],
                "reason": values[14],
                "content_hash": values[15],
                "created_at": values[16],
            }
            return Result()
        raise AssertionError(compact)

    def commit(self) -> None:
        return None


def _snapshot(currency: str, content_hash: str) -> ModelPriceSnapshotRevision:
    return ModelPriceSnapshotRevision(
        tenant={"orgId": "org-org", "projectId": "dev-project"},
        priceSnapshotId=f"price-{currency.lower()}",
        revision=1,
        contentHash=content_hash,
        currency=currency,
        inputTokenPrice=2,
        outputTokenPrice=4,
        cachedTokenPrice=1,
        tokenUnit=1000,
        effectiveFrom=NOW - timedelta(hours=1),
        effectiveUntil=NOW + timedelta(hours=1),
        lifecycle="active",
        createdBy="user:pricing",
        createdAt=NOW - timedelta(hours=1),
    )


def _store(connection: Connection, *, templates_ready: bool = True):
    @contextmanager
    def factory(_scope: TenantScope):
        yield connection

    def prices(_scope: TenantScope, ref: ExactRevisionRef, _now: datetime):
        currency = "CNY" if ref.resource_id.endswith("cny") else "USD"
        return _snapshot(currency, ref.content_hash)

    return AipResponsibilityProfileStore(
        factory,
        template_resolver=lambda _scope, _ref: templates_ready,
        price_resolver=prices,
    )


def _policy(store: AipResponsibilityProfileStore):
    return store.create_policy(
        SCOPE,
        CreateMergePolicyRequest(
            policyId="media-policy",
            revision=1,
            minimumProfile="LITE",
            expiresAt=NOW + timedelta(hours=2),
        ),
        "user:policy",
        now=NOW,
    )


def _request(policy_hash: str, *, unknown: bool = False):
    templates = {
        profile: _ref(
            "ResponsibilityTemplateRevision",
            f"bundle://aos/media/{profile.value.lower()}.responsibility",
        )
        for profile in ResponsibilityProfile
    }
    stages = {
        profile: _ref(
            "StageTemplateRevision",
            f"bundle://aos/media/{profile.value.lower()}.stage",
        )
        for profile in ResponsibilityProfile
    }
    inputs = []
    for index, profile in enumerate(ResponsibilityProfile, start=1):
        unknown_codes = ["MEDIA_PRICE_UNKNOWN"] if unknown and profile.value == "FULL" else []
        inputs.append(
            {
                "profile": profile.value,
                "stageId": "generate",
                "currency": "USD",
                "usageBasis": "input_tokens",
                "priceSnapshotRef": (
                    None
                    if unknown_codes
                    else _ref(
                        "ModelPriceSnapshotRevision",
                        f"price-usd-{profile.value.lower()}",
                        str(index) * 64,
                    ).model_dump(mode="json", by_alias=True)
                ),
                "quantityLower": None if unknown_codes else 1000 * index,
                "quantityUpper": None if unknown_codes else 2000 * index,
                "platformFeeLower": 1,
                "platformFeeUpper": 2,
                "unknownCodes": unknown_codes,
                "expiresAt": (NOW + timedelta(minutes=30)).isoformat(),
            }
        )
    inputs.append(
        {
            "profile": "FULL",
            "stageId": "live",
            "currency": "CNY",
            "usageBasis": "output_tokens",
            "priceSnapshotRef": _ref(
                "ModelPriceSnapshotRevision", "price-cny", "c" * 64
            ).model_dump(mode="json", by_alias=True),
            "quantityLower": 1000,
            "quantityUpper": 1500,
            "licenseFeeLower": 10,
            "licenseFeeUpper": 20,
            "unknownCodes": [],
            "expiresAt": (NOW + timedelta(minutes=20)).isoformat(),
        }
    )
    return RecommendMediaResponsibilityProfileRequest(
        subjectRef=_ref("TaskBriefRevision", "brief-1"),
        evidenceBundleRef=_ref("EvidenceBundleRevision", "evidence-1"),
        evalContractRef=_ref("EvalContractRevision", "eval-1"),
        candidateTemplateRefs=templates,
        stageTemplateRefs=stages,
        policyRef=_ref("MergePolicyRevision", "media-policy", policy_hash),
        riskLevel=2,
        channelCount=3,
        costInputs=inputs,
        projectedDuration=ProjectedDurationRange(
            lowerSeconds=600,
            upperSeconds=1800,
            assumptions=["队列容量保持稳定"],
        ),
        assumptions=["原子 Skill 输入质量满足当前 Eval"],
    )


def test_media_recommendation_is_deterministic_and_keeps_currencies_separate():
    connection = Connection()
    store = _store(connection)
    policy = _policy(store)
    request = _request(policy.content_hash)

    first = store.recommend_media(SCOPE, request, "user:advisor", now=NOW)
    second = store.recommend_media(SCOPE, request, "user:advisor", now=NOW)

    assert first.recommendation_id == second.recommendation_id
    assert first.snapshot_hash == second.snapshot_hash
    assert first.readiness == "ready"
    assert {(item.profile.value, item.currency) for item in first.projected_cost_ranges} == {
        ("LITE", "USD"),
        ("STANDARD", "USD"),
        ("FULL", "USD"),
        ("FULL", "CNY"),
    }
    lite = next(item for item in first.projected_cost_ranges if item.profile.value == "LITE")
    assert lite.lower_amount == 3
    assert lite.upper_amount == 6
    assert len(first.dependency_refs) >= 10


def test_unknown_cost_is_visible_and_confirmation_fails_closed():
    connection = Connection()
    store = _store(connection)
    policy = _policy(store)
    recommendation = store.recommend_media(
        SCOPE, _request(policy.content_hash, unknown=True), "user:advisor", now=NOW
    )
    assert recommendation.readiness == "blocked"
    full = next(
        item
        for item in recommendation.projected_cost_ranges
        if item.profile.value == "FULL" and item.currency == "USD"
    )
    assert full.lower_amount is None
    assert full.upper_amount is None
    with pytest.raises(ProductionContractDependencyBlocked, match="NOT_READY"):
        store.confirm_media(
            SCOPE,
            ConfirmResponsibilityProfileRequest(
                recommendationId=recommendation.recommendation_id,
                recommendationRevision=1,
                recommendationHash=recommendation.content_hash,
                selectedProfile="FULL",
                reason="确认前必须补齐价格",
            ),
            "user:approver",
            now=NOW,
            idempotency_key="confirm-unknown",
            expected_etag=recommendation.content_hash,
        )


def test_confirmation_uses_cas_and_idempotency_without_start_side_effect():
    connection = Connection()
    store = _store(connection)
    policy = _policy(store)
    recommendation = store.recommend_media(
        SCOPE, _request(policy.content_hash), "user:advisor", now=NOW
    )
    request = ConfirmResponsibilityProfileRequest(
        recommendationId=recommendation.recommendation_id,
        recommendationRevision=1,
        recommendationHash=recommendation.content_hash,
        selectedProfile="STANDARD",
        reason="接受当前方案与预计成本",
    )
    first = store.confirm_media(
        SCOPE,
        request,
        "user:approver",
        now=NOW,
        idempotency_key="confirm-1",
        expected_etag=recommendation.content_hash,
    )
    replay = store.confirm_media(
        SCOPE,
        request,
        "user:approver",
        now=NOW,
        idempotency_key="confirm-1",
        expected_etag=recommendation.content_hash,
    )
    assert replay.confirmation_id == first.confirmation_id
    assert replay.selected_projected_cost_ranges
    with pytest.raises(ProductionContractIdempotencyConflict):
        store.confirm_media(
            SCOPE,
            request.model_copy(update={"reason": "同键不同命令"}),
            "user:approver",
            now=NOW,
            idempotency_key="confirm-1",
            expected_etag=recommendation.content_hash,
        )
    with pytest.raises(ProductionContractDependencyBlocked, match="DRIFTED"):
        store.confirm_media(
            SCOPE,
            request,
            "user:approver",
            now=NOW,
            idempotency_key="confirm-2",
            expected_etag="f" * 64,
        )


def test_template_drift_and_cross_tenant_listing_fail_closed():
    connection = Connection()
    store = _store(connection, templates_ready=False)
    policy = _policy(store)
    with pytest.raises(ProductionContractDependencyBlocked, match="TEMPLATE"):
        store.recommend_media(
            SCOPE, _request(policy.content_hash), "user:advisor", now=NOW
        )

    empty = Connection()
    assert _store(empty).list_recommendations(
        TenantScope("dev-org", "dev-project")
    ).count == 0
