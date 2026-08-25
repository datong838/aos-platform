"""Tenant-scoped append-only persistence for W6-07 customer lifecycle authority."""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import psycopg

from aos_api.db import connect
from aos_api.ecommerce_workshop_customer_contracts import CustomerExactRef
from aos_api.ecommerce_workshop_customer_lifecycle import (
    CustomerConsentPolicyRevision,
    CustomerDialogueBatchRevision,
    CustomerDialogueStrategyRevision,
    CustomerJourneyRevision,
    CustomerLifecycleBlocked,
    CustomerSegmentRevision,
)
from aos_api.tenant_scope import TenantScope


class EcommerceWorkshopCustomerLifecycleStore:
    def __init__(self, connect_factory: Callable[[TenantScope], Any] = connect) -> None:
        self._connect = connect_factory

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    @staticmethod
    def _assert_tenant(scope: TenantScope, item: Any) -> None:
        if (item.tenant.org_id, item.tenant.project_id) != scope.key:
            raise CustomerLifecycleBlocked("CUSTOMER_LIFECYCLE_TENANT_DRIFT")

    def _append(self, scope: TenantScope, table: str, identity_column: str, identity: str, revision: int, content_hash: str, item: Any, created_at: Any) -> Any:
        self._assert_tenant(scope, item)
        payload = item.model_dump(mode="json", by_alias=True)
        with self._connect(scope) as conn:
            conn.execute(
                f"INSERT INTO {table}(org_id,project_id,{identity_column},revision,content_hash,authority_data,created_at) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s) ON CONFLICT DO NOTHING",
                (*scope.key, identity, revision, content_hash, self._json(payload), created_at),
            )
            row = conn.execute(
                f"SELECT authority_data,content_hash FROM {table} WHERE org_id=%s AND project_id=%s AND {identity_column}=%s AND revision=%s",
                (*scope.key, identity, revision),
            ).fetchone()
            if row is None or row["content_hash"] != content_hash:
                raise CustomerLifecycleBlocked("CUSTOMER_LIFECYCLE_IDEMPOTENCY_CONFLICT")
            conn.commit()
        return type(item).model_validate(row["authority_data"])

    def _require(self, scope: TenantScope, table: str, identity_column: str, ref: CustomerExactRef, model: type[Any]) -> Any:
        with self._connect(scope) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            row = conn.execute(
                f"SELECT authority_data,content_hash FROM {table} WHERE org_id=%s AND project_id=%s AND {identity_column}=%s AND revision=%s",
                (*scope.key, ref.resource_id, ref.revision),
            ).fetchone()
        if row is None or f"sha256:{row['content_hash']}" != ref.content_hash:
            raise CustomerLifecycleBlocked(f"{ref.resource_type.upper()}_MISSING_OR_DRIFTED")
        item = model.model_validate(row["authority_data"])
        self._assert_tenant(scope, item)
        return item

    def append_consent_policy(self, scope: TenantScope, item: CustomerConsentPolicyRevision) -> CustomerConsentPolicyRevision:
        return self._append(scope, "ecommerce_customer_consent_policy_revision", "policy_id", item.policy_id, item.revision, item.content_hash, item, item.created_at)

    def append_segment(self, scope: TenantScope, item: CustomerSegmentRevision) -> CustomerSegmentRevision:
        return self._append(scope, "ecommerce_customer_segment_revision", "segment_id", item.segment_id, item.revision, item.content_hash, item, item.created_at)

    def append_journey(self, scope: TenantScope, item: CustomerJourneyRevision) -> CustomerJourneyRevision:
        return self._append(scope, "ecommerce_customer_journey_revision", "journey_id", item.journey_id, item.revision, item.content_hash, item, item.created_at)

    def append_dialogue(self, scope: TenantScope, item: CustomerDialogueStrategyRevision) -> CustomerDialogueStrategyRevision:
        return self._append(scope, "ecommerce_customer_dialogue_strategy_revision", "dialogue_id", item.dialogue_id, item.revision, item.content_hash, item, item.created_at)

    def append_batch(self, scope: TenantScope, item: CustomerDialogueBatchRevision) -> CustomerDialogueBatchRevision:
        return self._append(scope, "ecommerce_customer_dialogue_batch_revision", "batch_id", item.batch_id, item.revision, item.content_hash, item, item.created_at)

    def require_consent_policy(self, scope: TenantScope, ref: CustomerExactRef) -> CustomerConsentPolicyRevision:
        return self._require(scope, "ecommerce_customer_consent_policy_revision", "policy_id", ref, CustomerConsentPolicyRevision)

    def require_segment(self, scope: TenantScope, ref: CustomerExactRef) -> CustomerSegmentRevision:
        return self._require(scope, "ecommerce_customer_segment_revision", "segment_id", ref, CustomerSegmentRevision)

    def require_journey(self, scope: TenantScope, ref: CustomerExactRef) -> CustomerJourneyRevision:
        return self._require(scope, "ecommerce_customer_journey_revision", "journey_id", ref, CustomerJourneyRevision)

    def require_dialogue(self, scope: TenantScope, ref: CustomerExactRef) -> CustomerDialogueStrategyRevision:
        return self._require(scope, "ecommerce_customer_dialogue_strategy_revision", "dialogue_id", ref, CustomerDialogueStrategyRevision)

    def latest_batch(self, scope: TenantScope, batch_id: str) -> CustomerDialogueBatchRevision:
        with self._connect(scope) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            row = conn.execute(
                "SELECT authority_data FROM ecommerce_customer_dialogue_batch_revision WHERE org_id=%s AND project_id=%s AND batch_id=%s ORDER BY revision DESC LIMIT 1",
                (*scope.key, batch_id),
            ).fetchone()
        if row is None:
            raise CustomerLifecycleBlocked("CUSTOMER_DIALOGUE_BATCH_NOT_FOUND")
        item = CustomerDialogueBatchRevision.model_validate(row["authority_data"])
        self._assert_tenant(scope, item)
        return item

    def latest_batch_or_none(self, scope: TenantScope, batch_id: str) -> CustomerDialogueBatchRevision | None:
        try:
            return self.latest_batch(scope, batch_id)
        except CustomerLifecycleBlocked as exc:
            if str(exc) == "CUSTOMER_DIALOGUE_BATCH_NOT_FOUND":
                return None
            raise

    def latest_batch_or_none_any(self, scope: TenantScope) -> CustomerDialogueBatchRevision | None:
        try:
            with self._connect(scope) as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                row = conn.execute(
                    "SELECT authority_data FROM ecommerce_customer_dialogue_batch_revision WHERE org_id=%s AND project_id=%s ORDER BY created_at DESC,revision DESC LIMIT 1",
                    scope.key,
                ).fetchone()
        except psycopg.Error as exc:
            raise CustomerLifecycleBlocked("CUSTOMER_LIFECYCLE_AUTHORITY_UNAVAILABLE") from exc
        if row is None:
            return None
        item = CustomerDialogueBatchRevision.model_validate(row["authority_data"])
        self._assert_tenant(scope, item)
        return item

    def authority_counts(self, scope: TenantScope) -> dict[str, int]:
        tables = {
            "consent_policy": "ecommerce_customer_consent_policy_revision",
            "segment": "ecommerce_customer_segment_revision",
            "journey": "ecommerce_customer_journey_revision",
            "dialogue": "ecommerce_customer_dialogue_strategy_revision",
        }
        try:
            with self._connect(scope) as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                return {key: conn.execute(f"SELECT COUNT(*) AS count FROM {table} WHERE org_id=%s AND project_id=%s", scope.key).fetchone()["count"] for key, table in tables.items()}
        except psycopg.Error as exc:
            raise CustomerLifecycleBlocked("CUSTOMER_LIFECYCLE_AUTHORITY_UNAVAILABLE") from exc

    def require_external_policy_authorities(self, scope: TenantScope, frequency_policy_ref: CustomerExactRef, channel_capability_ref: CustomerExactRef) -> None:
        del scope, frequency_policy_ref, channel_capability_ref
        # Caller-shaped refs are never treated as authority. A production resolver
        # must bind both refs at one cutoff before prepare can proceed.
        raise CustomerLifecycleBlocked("CUSTOMER_BATCH_EXTERNAL_POLICY_AUTHORITY_RESOLVER_UNAVAILABLE")


__all__ = ["EcommerceWorkshopCustomerLifecycleStore"]
