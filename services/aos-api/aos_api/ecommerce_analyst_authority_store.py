"""PostgreSQL authority Store for W3-13 ecommerce analyst revisions."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from aos_api.db import connect as db_connect
from aos_api.ecommerce_analyst_authority_contracts import (
    AnalystExactRef,
    DecisionSummaryRevision,
    EcommerceEffectReviewRevision,
    GrowthPlanRevision,
    InsightRevision,
    TaskGraphRevision,
)
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class AnalystAuthorityStoreError(RuntimeError):
    code = "ECOMMERCE_ANALYST_AUTHORITY_ERROR"


class AnalystAuthorityConflict(AnalystAuthorityStoreError):
    code = "ECOMMERCE_ANALYST_AUTHORITY_VERSION_CONFLICT"


class AnalystAuthorityIdempotencyConflict(AnalystAuthorityStoreError):
    code = "ECOMMERCE_ANALYST_AUTHORITY_IDEMPOTENCY_CONFLICT"


class AnalystAuthorityNotFound(AnalystAuthorityStoreError):
    code = "ECOMMERCE_ANALYST_AUTHORITY_NOT_FOUND"


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class EcommerceAnalystAuthorityStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def publish_insight(self, scope: TenantScope, actor: str, key: str, item: InsightRevision, *, expected_version: int) -> AnalystExactRef:
        return self._publish(scope, actor, key, item, expected_version=expected_version, identity=item.insight_id, identity_column="insight_id", resource_type="InsightRevision", head_table="ecommerce_analyst_insight_head", revision_table="ecommerce_analyst_insight_revision", operation="analyst.insight_publish")

    def publish_decision(self, scope: TenantScope, actor: str, key: str, item: DecisionSummaryRevision, *, expected_version: int) -> AnalystExactRef:
        return self._publish(scope, actor, key, item, expected_version=expected_version, identity=item.decision_id, identity_column="decision_id", resource_type="DecisionSummaryRevision", head_table="ecommerce_analyst_decision_head", revision_table="ecommerce_analyst_decision_revision", operation="analyst.decision_publish")

    def publish_plan(self, scope: TenantScope, actor: str, key: str, item: GrowthPlanRevision, *, expected_version: int) -> AnalystExactRef:
        return self._publish(scope, actor, key, item, expected_version=expected_version, identity=item.plan_id, identity_column="plan_id", resource_type="GrowthPlanRevision", head_table="ecommerce_analyst_growth_plan_head", revision_table="ecommerce_analyst_growth_plan_revision", operation="analyst.growth_plan_publish")

    def publish_task_graph(self, scope: TenantScope, actor: str, key: str, item: TaskGraphRevision, *, expected_version: int) -> AnalystExactRef:
        return self._publish(scope, actor, key, item, expected_version=expected_version, identity=item.graph_id, identity_column="graph_id", resource_type="TaskGraphRevision", head_table="ecommerce_analyst_task_graph_head", revision_table="ecommerce_analyst_task_graph_revision", operation="analyst.task_graph_publish")

    def publish_effect_review(self, scope: TenantScope, actor: str, key: str, item: EcommerceEffectReviewRevision, *, expected_version: int) -> AnalystExactRef:
        return self._publish(scope, actor, key, item, expected_version=expected_version, identity=item.review_id, identity_column="review_id", resource_type="EcommerceEffectReviewRevision", head_table="ecommerce_analyst_effect_review_head", revision_table="ecommerce_analyst_effect_review_revision", operation="analyst.effect_review_publish")

    def get_plan_exact(self, scope: TenantScope, ref: AnalystExactRef) -> GrowthPlanRevision:
        if ref.resource_type != "GrowthPlanRevision":
            raise AnalystAuthorityNotFound("exact ref is not a GrowthPlanRevision")
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                "SELECT payload,content_hash FROM ecommerce_analyst_growth_plan_revision WHERE org_id=%s AND project_id=%s AND plan_id=%s AND revision=%s",
                (*scope.key, ref.resource_id, ref.revision),
            ).fetchone()
        if row is None or row["content_hash"] != ref.content_hash:
            raise AnalystAuthorityNotFound("exact GrowthPlanRevision was not found in scope")
        item = GrowthPlanRevision.model_validate(row["payload"])
        self._require_scope(scope, item.tenant.org_id, item.tenant.project_id)
        if item.content_hash != row["content_hash"]:
            raise AnalystAuthorityNotFound("GrowthPlanRevision payload hash does not match authority")
        return item

    def find_plan_publication_receipt(
        self, scope: TenantScope, key: str
    ) -> AnalystExactRef | None:
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                "SELECT result_ref FROM ecommerce_analyst_authority_receipt WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s",
                (*scope.key, "analyst.growth_plan_publish", key),
            ).fetchone()
        if row is None:
            return None
        return AnalystExactRef.model_validate(row["result_ref"])

    def is_current_plan(self, scope: TenantScope, ref: AnalystExactRef) -> bool:
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                "SELECT current_revision FROM ecommerce_analyst_growth_plan_head WHERE org_id=%s AND project_id=%s AND plan_id=%s",
                (*scope.key, ref.resource_id),
            ).fetchone()
        return row is not None and int(row["current_revision"]) == ref.revision

    def _publish(self, scope: TenantScope, actor: str, key: str, item: Any, *, expected_version: int, identity: str, identity_column: str, resource_type: str, head_table: str, revision_table: str, operation: str) -> AnalystExactRef:
        self._require_scope(scope, item.tenant.org_id, item.tenant.project_id)
        if actor != item.created_by:
            raise AnalystAuthorityConflict("actor must match createdBy")
        payload = item.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash({"expectedVersion": expected_version, "revision": payload})
        with self._connect_factory(scope) as conn:
            replay = conn.execute(
                "SELECT request_hash,result_ref FROM ecommerce_analyst_authority_receipt WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s",
                (*scope.key, operation, key),
            ).fetchone()
            if replay is not None:
                if replay["request_hash"] != request_hash:
                    raise AnalystAuthorityIdempotencyConflict("idempotency key was reused for a different request")
                return AnalystExactRef.model_validate(replay["result_ref"])
            head = conn.execute(
                f"SELECT current_revision,version FROM {head_table} WHERE org_id=%s AND project_id=%s AND {identity_column}=%s FOR UPDATE",
                (*scope.key, identity),
            ).fetchone()
            version = int(head["version"]) if head else 0
            if version != expected_version or item.revision != version + 1 or item.version != version + 1:
                raise AnalystAuthorityConflict("stale version or non-linear revision")
            receipt_id = f"analyst-receipt-{uuid.uuid4().hex[:20]}"
            if head:
                updated = conn.execute(
                    f"UPDATE {head_table} SET current_revision=%s,version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND {identity_column}=%s AND version=%s",
                    (item.revision, *scope.key, identity, expected_version),
                )
                if updated.rowcount != 1:
                    raise AnalystAuthorityConflict("authority head CAS lost")
            else:
                conn.execute(
                    f"INSERT INTO {head_table}(org_id,project_id,{identity_column},current_revision,version) VALUES(%s,%s,%s,%s,1)",
                    (*scope.key, identity, item.revision),
                )
            conn.execute(
                f"INSERT INTO {revision_table}(org_id,project_id,{identity_column},revision,parent_revision,content_hash,receipt_id,payload,created_by,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
                (*scope.key, identity, item.revision, None if item.revision == 1 else item.revision - 1, item.content_hash, receipt_id, json.dumps(payload, ensure_ascii=False, separators=(",", ":")), actor, item.created_at),
            )
            result = AnalystExactRef(resource_type=resource_type, resource_id=identity, revision=item.revision, content_hash=item.content_hash)
            conn.execute(
                "INSERT INTO ecommerce_analyst_authority_receipt(org_id,project_id,receipt_id,operation,idempotency_key,request_hash,result_ref,created_by) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
                (*scope.key, receipt_id, operation, key, request_hash, json.dumps(result.model_dump(mode="json", by_alias=True), separators=(",", ":")), actor),
            )
            conn.commit()
            return result

    @staticmethod
    def _require_scope(scope: TenantScope, org_id: str, project_id: str) -> None:
        if scope.key != (org_id, project_id):
            raise AnalystAuthorityConflict("tenant scope mismatch")
