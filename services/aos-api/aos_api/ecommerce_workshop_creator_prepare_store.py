"""Tenant-scoped append-only persistence for W6-03 creator preparation."""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import psycopg

from aos_api.db import connect
from aos_api.db import connect_read_only
from aos_api.ecommerce_workshop_creator_growth_authorities import CreatorExactRef
from aos_api.ecommerce_workshop_creator_prepare import (
    CreatorBatchPreparationRevision,
    CreatorDiscoveryProfileRevision,
    CreatorNormalizerReceipt,
    CreatorPreparedMatchDecision,
    CreatorPreparedMatchObservation,
    CreatorPrepareBlocked,
)
from aos_api.tenant_scope import TenantScope


class EcommerceWorkshopCreatorPrepareStore:
    def __init__(
        self,
        connect_factory: Callable[[TenantScope], Any] = connect,
        read_connect_factory: Callable[[TenantScope], Any] | None = None,
    ) -> None:
        self._connect = connect_factory
        self._read_connect = read_connect_factory or (
            connect_factory if connect_factory is not connect else connect_read_only
        )

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    @staticmethod
    def _assert_tenant(scope: TenantScope, item: Any) -> None:
        if (item.tenant.org_id, item.tenant.project_id) != scope.key:
            raise CreatorPrepareBlocked("CREATOR_PREPARE_TENANT_DRIFT")

    def _append(self, scope: TenantScope, table: str, identity_column: str, identity: str, revision: int, content_hash: str, item: Any, created_at: Any) -> Any:
        self._assert_tenant(scope, item)
        payload = item.model_dump(mode="json", by_alias=True)
        with self._connect(scope) as conn:
            conn.execute(
                f"INSERT INTO {table}(org_id,project_id,{identity_column},revision,content_hash,authority_data,created_at) "
                "VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s) ON CONFLICT DO NOTHING",
                (*scope.key, identity, revision, content_hash, self._json(payload), created_at),
            )
            row = conn.execute(
                f"SELECT authority_data,content_hash FROM {table} WHERE org_id=%s AND project_id=%s AND {identity_column}=%s AND revision=%s",
                (*scope.key, identity, revision),
            ).fetchone()
            if row is None or row["content_hash"] != content_hash:
                raise CreatorPrepareBlocked("CREATOR_PREPARE_IDEMPOTENCY_CONFLICT")
            conn.commit()
        return type(item).model_validate(row["authority_data"])

    def append_profile(self, scope: TenantScope, item: CreatorDiscoveryProfileRevision) -> CreatorDiscoveryProfileRevision:
        return self._append(scope, "ecommerce_creator_discovery_profile_revision", "profile_id", item.profile_id, item.revision, item.content_hash, item, item.created_at)

    def append_normalizer_receipt(self, scope: TenantScope, item: CreatorNormalizerReceipt) -> CreatorNormalizerReceipt:
        return self._append(scope, "ecommerce_creator_normalizer_receipt", "receipt_id", item.receipt_id, item.revision, item.content_hash, item, item.created_at)

    def append_match_observation(self, scope: TenantScope, item: CreatorPreparedMatchObservation) -> CreatorPreparedMatchObservation:
        return self._append(scope, "ecommerce_creator_prepared_match_observation", "observation_id", item.observation_id, item.revision, item.content_hash, item, item.created_at)

    def append_match_decision(self, scope: TenantScope, item: CreatorPreparedMatchDecision) -> CreatorPreparedMatchDecision:
        return self._append(scope, "ecommerce_creator_prepared_match_decision", "decision_id", item.decision_id, item.revision, item.content_hash, item, item.decided_at)

    def append_batch(self, scope: TenantScope, item: CreatorBatchPreparationRevision) -> CreatorBatchPreparationRevision:
        return self._append(scope, "ecommerce_creator_batch_preparation_revision", "batch_id", item.batch_id, item.revision, item.content_hash, item, item.created_at)

    def _require(self, scope: TenantScope, table: str, identity_column: str, ref: CreatorExactRef, model: type[Any]) -> Any:
        with self._read_connect(scope) as conn:
            row = conn.execute(
                f"SELECT authority_data,content_hash FROM {table} WHERE org_id=%s AND project_id=%s AND {identity_column}=%s AND revision=%s",
                (*scope.key, ref.resource_id, ref.revision),
            ).fetchone()
        if row is None or row["content_hash"] != ref.content_hash:
            raise CreatorPrepareBlocked(f"{ref.resource_type.upper()}_MISSING_OR_DRIFTED")
        item = model.model_validate(row["authority_data"])
        self._assert_tenant(scope, item)
        return item

    def require_profile(self, scope: TenantScope, ref: CreatorExactRef) -> CreatorDiscoveryProfileRevision:
        return self._require(scope, "ecommerce_creator_discovery_profile_revision", "profile_id", ref, CreatorDiscoveryProfileRevision)

    def require_match_observation(self, scope: TenantScope, ref: CreatorExactRef) -> CreatorPreparedMatchObservation:
        return self._require(scope, "ecommerce_creator_prepared_match_observation", "observation_id", ref, CreatorPreparedMatchObservation)

    def require_match_decision(self, scope: TenantScope, ref: CreatorExactRef) -> CreatorPreparedMatchDecision:
        return self._require(scope, "ecommerce_creator_prepared_match_decision", "decision_id", ref, CreatorPreparedMatchDecision)

    def next_batch_revision(self, scope: TenantScope, batch_id: str) -> int:
        with self._read_connect(scope) as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(revision),0) AS revision FROM ecommerce_creator_batch_preparation_revision WHERE org_id=%s AND project_id=%s AND batch_id=%s",
                (*scope.key, batch_id),
            ).fetchone()
        return int(row["revision"]) + 1

    def latest_batch(self, scope: TenantScope, batch_id: str) -> CreatorBatchPreparationRevision:
        with self._read_connect(scope) as conn:
            row = conn.execute(
                "SELECT authority_data FROM ecommerce_creator_batch_preparation_revision WHERE org_id=%s AND project_id=%s AND batch_id=%s ORDER BY revision DESC LIMIT 1",
                (*scope.key, batch_id),
            ).fetchone()
        if row is None:
            raise CreatorPrepareBlocked("CREATOR_BATCH_NOT_FOUND")
        item = CreatorBatchPreparationRevision.model_validate(row["authority_data"])
        self._assert_tenant(scope, item)
        return item

    def latest_batch_or_none_by_id(self, scope: TenantScope, batch_id: str) -> CreatorBatchPreparationRevision | None:
        try:
            return self.latest_batch(scope, batch_id)
        except CreatorPrepareBlocked as exc:
            if str(exc) == "CREATOR_BATCH_NOT_FOUND":
                return None
            raise

    def latest_batch_or_none(self, scope: TenantScope) -> CreatorBatchPreparationRevision | None:
        try:
            with self._read_connect(scope) as conn:
                row = conn.execute(
                    "SELECT authority_data FROM ecommerce_creator_batch_preparation_revision WHERE org_id=%s AND project_id=%s ORDER BY created_at DESC,revision DESC LIMIT 1",
                    scope.key,
                ).fetchone()
        except psycopg.Error as exc:
            raise CreatorPrepareBlocked("CREATOR_PREPARE_AUTHORITY_UNAVAILABLE") from exc
        if row is None:
            return None
        item = CreatorBatchPreparationRevision.model_validate(row["authority_data"])
        self._assert_tenant(scope, item)
        return item


__all__ = ["EcommerceWorkshopCreatorPrepareStore"]
