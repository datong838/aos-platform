"""Tenant-scoped append-only persistence for W6-05 price research authority."""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import psycopg

from aos_api.db import connect
from aos_api.ecommerce_workshop_price_governance_contracts import PriceExactRef
from aos_api.ecommerce_workshop_price_research import (
    MonitoringPolicyRevision,
    PriceObservationRevision,
    PriceResearchBatchRevision,
    PriceResearchBlocked,
    PriceResearchProfileRevision,
    ProductMatchDecisionRevision,
    ProductMatchObservation,
)
from aos_api.tenant_scope import TenantScope


class EcommerceWorkshopPriceResearchStore:
    def __init__(self, connect_factory: Callable[[TenantScope], Any] = connect) -> None:
        self._connect = connect_factory

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    @staticmethod
    def _assert_tenant(scope: TenantScope, item: Any) -> None:
        if (item.tenant.org_id, item.tenant.project_id) != scope.key:
            raise PriceResearchBlocked("PRICE_RESEARCH_TENANT_DRIFT")

    def _append(self, scope: TenantScope, table: str, identity_column: str, identity: str, revision: int, content_hash: str, item: Any, created_at: Any) -> Any:
        self._assert_tenant(scope, item)
        payload = item.model_dump(mode="json", by_alias=True)
        with self._connect(scope) as conn:
            conn.execute(
                f"INSERT INTO {table}(org_id,project_id,{identity_column},revision,content_hash,authority_data,created_at) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s) ON CONFLICT DO NOTHING",
                (*scope.key, identity, revision, content_hash, self._json(payload), created_at),
            )
            row = conn.execute(f"SELECT authority_data,content_hash FROM {table} WHERE org_id=%s AND project_id=%s AND {identity_column}=%s AND revision=%s", (*scope.key, identity, revision)).fetchone()
            if row is None or row["content_hash"] != content_hash:
                raise PriceResearchBlocked("PRICE_RESEARCH_IDEMPOTENCY_CONFLICT")
            conn.commit()
        return type(item).model_validate(row["authority_data"])

    def _require(self, scope: TenantScope, table: str, identity_column: str, ref: PriceExactRef, model: type[Any]) -> Any:
        with self._connect(scope) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            row = conn.execute(f"SELECT authority_data,content_hash FROM {table} WHERE org_id=%s AND project_id=%s AND {identity_column}=%s AND revision=%s", (*scope.key, ref.resource_id, ref.revision)).fetchone()
        if row is None or f"sha256:{row['content_hash']}" != ref.content_hash:
            raise PriceResearchBlocked(f"{ref.resource_type.upper()}_MISSING_OR_DRIFTED")
        item = model.model_validate(row["authority_data"])
        self._assert_tenant(scope, item)
        return item

    def append_profile(self, scope: TenantScope, item: PriceResearchProfileRevision) -> PriceResearchProfileRevision:
        return self._append(scope, "ecommerce_price_research_profile_revision", "profile_id", item.profile_id, item.revision, item.content_hash, item, item.created_at)

    def append_observation(self, scope: TenantScope, item: PriceObservationRevision) -> PriceObservationRevision:
        return self._append(scope, "ecommerce_price_observation_revision", "observation_id", item.observation_id, item.revision, item.content_hash, item, item.created_at)

    def append_match_observation(self, scope: TenantScope, item: ProductMatchObservation) -> ProductMatchObservation:
        return self._append(scope, "ecommerce_price_product_match_observation", "match_observation_id", item.match_observation_id, item.revision, item.content_hash, item, item.created_at)

    def append_match_decision(self, scope: TenantScope, item: ProductMatchDecisionRevision) -> ProductMatchDecisionRevision:
        return self._append(scope, "ecommerce_price_product_match_decision_revision", "decision_id", item.decision_id, item.revision, item.content_hash, item, item.decided_at)

    def append_policy(self, scope: TenantScope, item: MonitoringPolicyRevision) -> MonitoringPolicyRevision:
        return self._append(scope, "ecommerce_price_monitoring_policy_revision", "policy_id", item.policy_id, item.revision, item.content_hash, item, item.created_at)

    def append_batch(self, scope: TenantScope, item: PriceResearchBatchRevision) -> PriceResearchBatchRevision:
        return self._append(scope, "ecommerce_price_research_batch_revision", "batch_id", item.batch_id, item.revision, item.content_hash, item, item.created_at)

    def require_profile(self, scope: TenantScope, ref: PriceExactRef) -> PriceResearchProfileRevision:
        return self._require(scope, "ecommerce_price_research_profile_revision", "profile_id", ref, PriceResearchProfileRevision)

    def require_observation(self, scope: TenantScope, ref: PriceExactRef) -> PriceObservationRevision:
        return self._require(scope, "ecommerce_price_observation_revision", "observation_id", ref, PriceObservationRevision)

    def require_match_observation(self, scope: TenantScope, ref: PriceExactRef) -> ProductMatchObservation:
        return self._require(scope, "ecommerce_price_product_match_observation", "match_observation_id", ref, ProductMatchObservation)

    def require_match_decision(self, scope: TenantScope, ref: PriceExactRef) -> ProductMatchDecisionRevision:
        return self._require(scope, "ecommerce_price_product_match_decision_revision", "decision_id", ref, ProductMatchDecisionRevision)

    def require_policy(self, scope: TenantScope, ref: PriceExactRef) -> MonitoringPolicyRevision:
        return self._require(scope, "ecommerce_price_monitoring_policy_revision", "policy_id", ref, MonitoringPolicyRevision)

    def latest_batch(self, scope: TenantScope, batch_id: str) -> PriceResearchBatchRevision:
        with self._connect(scope) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            row = conn.execute("SELECT authority_data FROM ecommerce_price_research_batch_revision WHERE org_id=%s AND project_id=%s AND batch_id=%s ORDER BY revision DESC LIMIT 1", (*scope.key, batch_id)).fetchone()
        if row is None:
            raise PriceResearchBlocked("PRICE_RESEARCH_BATCH_NOT_FOUND")
        item = PriceResearchBatchRevision.model_validate(row["authority_data"])
        self._assert_tenant(scope, item)
        return item

    def latest_batch_or_none_by_id(self, scope: TenantScope, batch_id: str) -> PriceResearchBatchRevision | None:
        try:
            return self.latest_batch(scope, batch_id)
        except PriceResearchBlocked as exc:
            if str(exc) == "PRICE_RESEARCH_BATCH_NOT_FOUND":
                return None
            raise

    def latest_batch_or_none(self, scope: TenantScope) -> PriceResearchBatchRevision | None:
        try:
            with self._connect(scope) as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                row = conn.execute("SELECT authority_data FROM ecommerce_price_research_batch_revision WHERE org_id=%s AND project_id=%s ORDER BY created_at DESC,revision DESC LIMIT 1", scope.key).fetchone()
        except psycopg.Error as exc:
            raise PriceResearchBlocked("PRICE_RESEARCH_AUTHORITY_UNAVAILABLE") from exc
        if row is None:
            return None
        item = PriceResearchBatchRevision.model_validate(row["authority_data"])
        self._assert_tenant(scope, item)
        return item


__all__ = ["EcommerceWorkshopPriceResearchStore"]
