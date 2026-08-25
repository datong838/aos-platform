"""Tenant-scoped append-only persistence for W6-04 creator lifecycle."""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import psycopg

from aos_api.db import connect
from aos_api.ecommerce_workshop_creator_growth_authorities import CreatorExactRef
from aos_api.ecommerce_workshop_creator_lifecycle import (
    CreatorActionLaneRequest,
    CreatorBatchStartDecisionRevision,
    CreatorContractRevision,
    CreatorDeliveryObservation,
    CreatorLaneObservation,
    CreatorLifecycleBlocked,
    CreatorRelationshipRevision,
)
from aos_api.tenant_scope import TenantScope


class EcommerceWorkshopCreatorLifecycleStore:
    def __init__(self, connect_factory: Callable[[TenantScope], Any] = connect) -> None:
        self._connect = connect_factory

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    @staticmethod
    def _assert_tenant(scope: TenantScope, item: Any) -> None:
        if (item.tenant.org_id, item.tenant.project_id) != scope.key:
            raise CreatorLifecycleBlocked("CREATOR_LIFECYCLE_TENANT_DRIFT")

    def _append(self, scope: TenantScope, table: str, identity_column: str, identity: str, revision: int, content_hash: str, item: Any, created_at: Any, *, extra_columns: str = "", extra_values: tuple[Any, ...] = ()) -> Any:
        self._assert_tenant(scope, item)
        payload = item.model_dump(mode="json", by_alias=True)
        column_suffix = f",{extra_columns}" if extra_columns else ""
        value_suffix = "," + ",".join(["%s"] * len(extra_values)) if extra_values else ""
        with self._connect(scope) as conn:
            conn.execute(
                f"INSERT INTO {table}(org_id,project_id,{identity_column},revision,content_hash,authority_data,created_at{column_suffix}) "
                f"VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s{value_suffix}) ON CONFLICT DO NOTHING",
                (*scope.key, identity, revision, content_hash, self._json(payload), created_at, *extra_values),
            )
            row = conn.execute(
                f"SELECT authority_data,content_hash FROM {table} WHERE org_id=%s AND project_id=%s AND {identity_column}=%s AND revision=%s",
                (*scope.key, identity, revision),
            ).fetchone()
            if row is None or row["content_hash"] != content_hash:
                raise CreatorLifecycleBlocked("CREATOR_LIFECYCLE_IDEMPOTENCY_CONFLICT")
            conn.commit()
        return type(item).model_validate(row["authority_data"])

    def append_start(self, scope: TenantScope, batch_id: str, item: CreatorBatchStartDecisionRevision) -> CreatorBatchStartDecisionRevision:
        return self._append(scope, "ecommerce_creator_batch_start_decision_revision", "decision_id", item.decision_id, item.revision, item.content_hash, item, item.started_at, extra_columns="batch_id", extra_values=(batch_id,))

    def latest_start_or_none(self, scope: TenantScope, batch_id: str) -> CreatorBatchStartDecisionRevision | None:
        with self._connect(scope) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            row = conn.execute(
                "SELECT authority_data FROM ecommerce_creator_batch_start_decision_revision WHERE org_id=%s AND project_id=%s AND batch_id=%s ORDER BY revision DESC LIMIT 1",
                (*scope.key, batch_id),
            ).fetchone()
        return None if row is None else CreatorBatchStartDecisionRevision.model_validate(row["authority_data"])

    def latest_start_for_tenant_or_none(self, scope: TenantScope) -> CreatorBatchStartDecisionRevision | None:
        try:
            with self._connect(scope) as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                row = conn.execute(
                    "SELECT authority_data FROM ecommerce_creator_batch_start_decision_revision WHERE org_id=%s AND project_id=%s ORDER BY created_at DESC,revision DESC LIMIT 1",
                    scope.key,
                ).fetchone()
        except psycopg.Error as exc:
            raise CreatorLifecycleBlocked("CREATOR_LIFECYCLE_AUTHORITY_UNAVAILABLE") from exc
        return None if row is None else CreatorBatchStartDecisionRevision.model_validate(row["authority_data"])

    def require_start(self, scope: TenantScope, ref: CreatorExactRef) -> CreatorBatchStartDecisionRevision:
        with self._connect(scope) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            row = conn.execute(
                "SELECT authority_data,content_hash FROM ecommerce_creator_batch_start_decision_revision WHERE org_id=%s AND project_id=%s AND decision_id=%s AND revision=%s",
                (*scope.key, ref.resource_id, ref.revision),
            ).fetchone()
        if row is None or row["content_hash"] != ref.content_hash:
            raise CreatorLifecycleBlocked("CREATOR_START_DECISION_MISSING_OR_DRIFTED")
        return CreatorBatchStartDecisionRevision.model_validate(row["authority_data"])

    def require_action_receipt(self, scope: TenantScope, ref: CreatorExactRef, binding_hash: str) -> None:
        with self._connect(scope) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            row = conn.execute(
                "SELECT receipt_content_hash,action_binding_hash FROM aip_action_receipt WHERE org_id=%s AND project_id=%s AND receipt_id=%s",
                (*scope.key, ref.resource_id),
            ).fetchone()
        if row is None or row["receipt_content_hash"] != ref.content_hash or row["action_binding_hash"] != binding_hash:
            raise CreatorLifecycleBlocked("CREATOR_ACTION_RECEIPT_MISSING_OR_BINDING_DRIFTED")

    def require_lane_authorities(self, scope: TenantScope, lane: CreatorActionLaneRequest) -> None:
        """Fail closed until every W5 authority has one canonical exact resolver.

        W5 currently persists these facts across several stores and the budget
        reservation is intentionally unavailable for external action families.
        Treating well-shaped caller JSON as authority would be unsafe.
        """
        _ = (scope, lane)
        raise CreatorLifecycleBlocked("CREATOR_ACTION_LANE_AUTHORITY_RESOLVER_UNAVAILABLE")

    def append_lane_observation(self, scope: TenantScope, item: CreatorLaneObservation) -> CreatorLaneObservation:
        return self._append(scope, "ecommerce_creator_lane_observation", "observation_id", item.observation_id, item.revision, item.content_hash, item, item.observed_at, extra_columns="decision_id,lane_id", extra_values=(item.start_decision_ref.resource_id, item.lane_id))

    def list_lane_observations(self, scope: TenantScope, decision_id: str) -> list[CreatorLaneObservation]:
        with self._connect(scope) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            rows = conn.execute(
                "SELECT authority_data FROM ecommerce_creator_lane_observation WHERE org_id=%s AND project_id=%s AND decision_id=%s ORDER BY observed_at,observation_id",
                (*scope.key, decision_id),
            ).fetchall()
        return [CreatorLaneObservation.model_validate(row["authority_data"]) for row in rows]

    def append_contract(self, scope: TenantScope, item: CreatorContractRevision) -> CreatorContractRevision:
        return self._append(scope, "ecommerce_creator_contract_revision", "collaboration_id", item.collaboration_id, item.revision, item.content_hash, item, item.created_at)

    def require_contract(self, scope: TenantScope, ref: CreatorExactRef) -> CreatorContractRevision:
        with self._connect(scope) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            row = conn.execute(
                "SELECT authority_data,content_hash FROM ecommerce_creator_contract_revision WHERE org_id=%s AND project_id=%s AND collaboration_id=%s AND revision=%s",
                (*scope.key, ref.resource_id, ref.revision),
            ).fetchone()
        if row is None or row["content_hash"] != ref.content_hash:
            raise CreatorLifecycleBlocked("CREATOR_CONTRACT_MISSING_OR_DRIFTED")
        return CreatorContractRevision.model_validate(row["authority_data"])

    def append_delivery(self, scope: TenantScope, item: CreatorDeliveryObservation) -> CreatorDeliveryObservation:
        return self._append(scope, "ecommerce_creator_delivery_observation", "observation_id", item.observation_id, 1, item.content_hash, item, item.observed_at)

    def require_delivery(self, scope: TenantScope, ref: CreatorExactRef) -> CreatorDeliveryObservation:
        with self._connect(scope) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            row = conn.execute(
                "SELECT authority_data,content_hash FROM ecommerce_creator_delivery_observation WHERE org_id=%s AND project_id=%s AND observation_id=%s AND revision=%s",
                (*scope.key, ref.resource_id, ref.revision),
            ).fetchone()
        if row is None or row["content_hash"] != ref.content_hash:
            raise CreatorLifecycleBlocked("CREATOR_DELIVERY_MISSING_OR_DRIFTED")
        return CreatorDeliveryObservation.model_validate(row["authority_data"])

    def append_relationship(self, scope: TenantScope, item: CreatorRelationshipRevision) -> CreatorRelationshipRevision:
        return self._append(scope, "ecommerce_creator_relationship_revision", "relationship_id", item.relationship_id, item.revision, item.content_hash, item, item.created_at)

    def latest_relationship_or_none(self, scope: TenantScope, relationship_id: str) -> CreatorRelationshipRevision | None:
        with self._connect(scope) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            row = conn.execute(
                "SELECT authority_data FROM ecommerce_creator_relationship_revision WHERE org_id=%s AND project_id=%s AND relationship_id=%s ORDER BY revision DESC LIMIT 1",
                (*scope.key, relationship_id),
            ).fetchone()
        return None if row is None else CreatorRelationshipRevision.model_validate(row["authority_data"])

    def _list(self, scope: TenantScope, table: str, model: type[Any]) -> list[Any]:
        with self._connect(scope) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            rows = conn.execute(f"SELECT authority_data FROM {table} WHERE org_id=%s AND project_id=%s ORDER BY created_at", scope.key).fetchall()
        return [model.model_validate(row["authority_data"]) for row in rows]

    def list_contracts(self, scope: TenantScope) -> list[CreatorContractRevision]:
        return self._list(scope, "ecommerce_creator_contract_revision", CreatorContractRevision)

    def list_deliveries(self, scope: TenantScope) -> list[CreatorDeliveryObservation]:
        return self._list(scope, "ecommerce_creator_delivery_observation", CreatorDeliveryObservation)

    def list_relationships(self, scope: TenantScope) -> list[CreatorRelationshipRevision]:
        return self._list(scope, "ecommerce_creator_relationship_revision", CreatorRelationshipRevision)


__all__ = ["EcommerceWorkshopCreatorLifecycleStore"]
