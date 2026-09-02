"""Tenant authority store and canonical resolvers for W6-09."""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from aos_api.db import connect
from aos_api.db import connect_read_only, connect_serializable
from aos_api.ecommerce_workshop_three_module_closure import (
    CanonicalItemOutcome,
    ClosureExactRef,
    ThreeModule,
    ThreeModuleClosureBlocked,
    ThreeModuleClosureRevision,
    ThreeModuleEffectBindingRevision,
    ThreeModuleHandoffBindingRevision,
    ThreeModuleItemOutcome,
    ThreeModuleUsageBindingRevision,
    canonical_hash,
)
from aos_api.tenant_scope import TenantScope


_STATUS = {
    "prepared": CanonicalItemOutcome.IN_PROGRESS,
    "reserved": CanonicalItemOutcome.IN_PROGRESS,
    "accepted": CanonicalItemOutcome.IN_PROGRESS,
    "frozen": CanonicalItemOutcome.IN_PROGRESS,
    "applied": CanonicalItemOutcome.SUCCEEDED,
    "adopted": CanonicalItemOutcome.SUCCEEDED,
    "failed": CanonicalItemOutcome.FAILED,
    "rejected": CanonicalItemOutcome.FAILED,
    "cancelled": CanonicalItemOutcome.FAILED,
    "unknown": CanonicalItemOutcome.UNKNOWN,
    "disputed": CanonicalItemOutcome.DISPUTED,
    "skipped_withdrawn": CanonicalItemOutcome.SKIPPED,
}


class EcommerceWorkshopThreeModuleClosureStore:
    def __init__(
        self,
        connect_factory: Callable[[TenantScope], Any] = connect,
        read_connect_factory: Callable[[TenantScope], Any] | None = None,
        serializable_connect_factory: Callable[[TenantScope], Any] | None = None,
    ) -> None:
        self._connect = connect_factory
        self._read_connect = read_connect_factory or (
            connect_factory if connect_factory is not connect else connect_read_only
        )
        self._serial_connect = serializable_connect_factory or (
            connect_factory if connect_factory is not connect else connect_serializable
        )

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    @staticmethod
    def _assert_tenant(scope: TenantScope, item: Any) -> None:
        if (item.tenant.org_id, item.tenant.project_id) != scope.key:
            raise ThreeModuleClosureBlocked("THREE_MODULE_TENANT_DRIFTED")

    @staticmethod
    def _value(value: Any) -> Any:
        if isinstance(value, str):
            return json.loads(value)
        return value

    @staticmethod
    def _ref(value: dict[str, Any] | None) -> ClosureExactRef | None:
        if value is None:
            return None
        return ClosureExactRef.model_validate(value)

    @staticmethod
    def _original_ref(source: ClosureExactRef, item_key: str) -> ClosureExactRef:
        return ClosureExactRef(
            resourceType=source.resource_type,
            resourceId=f"{source.resource_id}:{item_key}",
            revision=source.revision,
            contentHash=source.content_hash,
            receiptId=source.receipt_id,
        )

    def _append(self, scope: TenantScope, table: str, identity: str, item: Any, created_at: Any) -> Any:
        self._assert_tenant(scope, item)
        content_hash = item.content_hash
        with self._serial_connect(scope) as conn:
            conn.execute(
                f"INSERT INTO {table}(org_id,project_id,binding_id,revision,module,closure_id,content_hash,authority_data,created_at) VALUES (%s,%s,%s,1,%s,%s,%s,%s::jsonb,%s) ON CONFLICT DO NOTHING",
                (*scope.key, identity, getattr(item, "module", None), getattr(item, "closure_id", None) or item.closure_ref.resource_id, content_hash, self._json(item.model_dump(mode="json", by_alias=True)), created_at),
            )
            row = conn.execute(
                f"SELECT authority_data,content_hash FROM {table} WHERE org_id=%s AND project_id=%s AND binding_id=%s AND revision=1",
                (*scope.key, identity),
            ).fetchone()
            if row is None or row["content_hash"] != content_hash:
                raise ThreeModuleClosureBlocked("THREE_MODULE_BINDING_IDEMPOTENCY_CONFLICT")
            conn.commit()
        return type(item).model_validate(row["authority_data"])

    def append_closure(self, scope: TenantScope, item: ThreeModuleClosureRevision) -> ThreeModuleClosureRevision:
        self._assert_tenant(scope, item)
        with self._serial_connect(scope) as conn:
            conn.execute(
                "INSERT INTO ecommerce_three_module_closure_revision(org_id,project_id,closure_id,revision,module,source_id,content_hash,authority_data,created_at) VALUES (%s,%s,%s,1,%s,%s,%s,%s::jsonb,%s) ON CONFLICT DO NOTHING",
                (*scope.key, item.closure_id, item.module.value, item.source_ref.resource_id, item.content_hash, self._json(item.model_dump(mode="json", by_alias=True)), item.compiled_at),
            )
            row = conn.execute(
                "SELECT authority_data,content_hash FROM ecommerce_three_module_closure_revision WHERE org_id=%s AND project_id=%s AND closure_id=%s AND revision=1",
                (*scope.key, item.closure_id),
            ).fetchone()
            if row is None or row["content_hash"] != item.content_hash:
                raise ThreeModuleClosureBlocked("THREE_MODULE_CLOSURE_IDEMPOTENCY_CONFLICT")
            conn.commit()
        return ThreeModuleClosureRevision.model_validate(row["authority_data"])

    def append_usage_binding(self, scope: TenantScope, item: ThreeModuleUsageBindingRevision) -> ThreeModuleUsageBindingRevision:
        return self._append(scope, "ecommerce_three_module_usage_binding_revision", item.binding_id, item, item.bound_at)

    def append_effect_binding(self, scope: TenantScope, item: ThreeModuleEffectBindingRevision) -> ThreeModuleEffectBindingRevision:
        return self._append(scope, "ecommerce_three_module_effect_binding_revision", item.binding_id, item, item.bound_at)

    def append_handoff_binding(self, scope: TenantScope, item: ThreeModuleHandoffBindingRevision) -> ThreeModuleHandoffBindingRevision:
        return self._append(scope, "ecommerce_three_module_handoff_binding_revision", item.binding_id, item, item.bound_at)

    def _source_row(self, scope: TenantScope, table: str, identity: str, source: ClosureExactRef) -> dict[str, Any]:
        with self._read_connect(scope) as conn:
            row = conn.execute(
                f"SELECT authority_data,content_hash FROM {table} WHERE org_id=%s AND project_id=%s AND {identity}=%s AND revision=%s",
                (*scope.key, source.resource_id, source.revision),
            ).fetchone()
        if row is None or f"sha256:{row['content_hash']}" != source.content_hash:
            raise ThreeModuleClosureBlocked("THREE_MODULE_SOURCE_MISSING_OR_DRIFTED")
        return self._value(row["authority_data"])

    def _observations(self, scope: TenantScope, table: str, decision_column: str, decision_id: str, item_column: str) -> dict[str, dict[str, Any]]:
        with self._read_connect(scope) as conn:
            rows = conn.execute(
                f"SELECT authority_data FROM {table} WHERE org_id=%s AND project_id=%s AND {decision_column}=%s ORDER BY created_at,revision",
                (*scope.key, decision_id),
            ).fetchall()
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            value = self._value(row["authority_data"])
            result[str(value[item_column])] = value
        return result

    def resolve_domain_items(self, scope: TenantScope, module: ThreeModule, source: ClosureExactRef) -> list[ThreeModuleItemOutcome]:
        if module is ThreeModule.CREATOR:
            data = self._source_row(scope, "ecommerce_creator_batch_start_decision_revision", "decision_id", source)
            observations = self._observations(scope, "ecommerce_creator_lane_observation", "decision_id", source.resource_id, "laneId")
            raw = []
            for lane in data.get("lanes", []):
                key = str(lane["laneId"])
                observation = observations.get(key)
                status = str((observation or lane).get("resolvedOutcome") or (observation or lane).get("outcome"))
                receipt = (observation or lane).get("actionReceiptRef")
                raw.append((key, status, receipt))
        elif module is ThreeModule.PRICE:
            data = self._source_row(scope, "ecommerce_price_disposition_revision", "disposition_id", source)
            with self._read_connect(scope) as conn:
                row = conn.execute(
                    "SELECT authority_data FROM ecommerce_price_disposition_observation WHERE org_id=%s AND project_id=%s AND authority_data->'dispositionRef'->>'resourceId'=%s ORDER BY created_at DESC LIMIT 1",
                    (*scope.key, source.resource_id),
                ).fetchone()
            observation = None if row is None else self._value(row["authority_data"])
            status = str((observation or {}).get("resolvedOutcome") or (observation or {}).get("outcome") or data.get("lifecycle", "prepared"))
            receipt = (observation or {}).get("receiptRef")
            raw = [(str(ref["resourceId"]), status, receipt) for ref in data.get("targetRefs", [])]
        else:
            data = self._source_row(scope, "ecommerce_customer_batch_start_decision_revision", "decision_id", source)
            observations = self._observations(scope, "ecommerce_customer_dispatch_observation", "decision_id", source.resource_id, "itemKey")
            raw = []
            for binding in data.get("items", []):
                key = str(binding["itemKey"])
                observation = observations.get(key)
                status = str((observation or binding).get("resolvedState") or (observation or binding).get("state"))
                receipt = (observation or binding).get("actionReceiptRef")
                raw.append((key, status, receipt))
        items: list[ThreeModuleItemOutcome] = []
        for key, status, receipt in sorted(raw):
            outcome = _STATUS.get(status)
            if outcome is None:
                raise ThreeModuleClosureBlocked("THREE_MODULE_ORIGINAL_STATUS_UNMAPPED")
            items.append(ThreeModuleItemOutcome(
                itemKey=key, originalStatus=status, canonicalOutcome=outcome,
                originalRef=self._original_ref(source, key), receiptRef=self._ref(receipt),
            ))
        return items

    def require_closure(self, scope: TenantScope, ref: ClosureExactRef) -> ThreeModuleClosureRevision:
        with self._connect(scope) as conn:
            row = conn.execute(
                "SELECT authority_data,content_hash FROM ecommerce_three_module_closure_revision WHERE org_id=%s AND project_id=%s AND closure_id=%s AND revision=%s",
                (*scope.key, ref.resource_id, ref.revision),
            ).fetchone()
        if row is None or f"sha256:{row['content_hash']}" != ref.content_hash:
            raise ThreeModuleClosureBlocked("THREE_MODULE_CLOSURE_MISSING_OR_DRIFTED")
        return ThreeModuleClosureRevision.model_validate(row["authority_data"])

    def resolve_usage(self, scope: TenantScope, receipt_id: str) -> dict[str, Any]:
        with self._connect(scope) as conn:
            row = conn.execute(
                "SELECT * FROM aip_usage_receipt WHERE org_id=%s AND project_id=%s AND receipt_id=%s",
                (*scope.key, receipt_id),
            ).fetchone()
            adjustments = conn.execute(
                "SELECT COALESCE(SUM(delta),0) AS total FROM aip_usage_adjustment WHERE org_id=%s AND project_id=%s AND receipt_id=%s",
                (*scope.key, receipt_id),
            ).fetchone()
        if row is None:
            raise ThreeModuleClosureBlocked("THREE_MODULE_USAGE_RECEIPT_NOT_FOUND")
        value = dict(row)
        digest = canonical_hash(value)
        quality = str(value["quality"])
        return {
            "usageReceiptRef": ClosureExactRef(resourceType="UsageReceipt", resourceId=receipt_id, revision=1, contentHash=f"sha256:{digest}", receiptId=receipt_id),
            "lineageId": value["lineage_id"], "quality": quality,
            "quantity": None if quality == "unknown" else float(value["quantity"]),
            "unit": value["unit"], "adjustmentTotal": float(adjustments["total"]),
            "settlement": quality,
        }

    def resolve_effect(self, scope: TenantScope, review_id: str, source_ref: ClosureExactRef) -> dict[str, Any]:
        with self._connect(scope) as conn:
            review = conn.execute(
                "SELECT * FROM aip_effect_review_revision WHERE org_id=%s AND project_id=%s AND review_id=%s",
                (*scope.key, review_id),
            ).fetchone()
            decision = conn.execute(
                "SELECT * FROM aip_effect_maturity_decision WHERE org_id=%s AND project_id=%s AND review_id=%s ORDER BY observed_at DESC LIMIT 1",
                (*scope.key, review_id),
            ).fetchone()
        if review is None:
            raise ThreeModuleClosureBlocked("THREE_MODULE_EFFECT_REVIEW_NOT_FOUND")
        subject = self._value(review["subject_ref"])
        if subject.get("resourceId") != source_ref.resource_id:
            raise ThreeModuleClosureBlocked("THREE_MODULE_EFFECT_SUBJECT_DRIFTED")
        value = dict(review if decision is None else decision)
        maturity = str(value["maturity_status"])
        observed_at = value.get("observed_at") or review["created_at"]
        return {
            "effectReviewRef": ClosureExactRef(resourceType="EffectReviewRevision", resourceId=review_id, revision=int(review["revision"]), contentHash=f"sha256:{review['content_hash']}", receiptId=f"receipt-{review_id}"),
            "maturityStatus": maturity, "accepted": bool(value["accepted"]),
            "effectCompleted": bool(value["effect_completed"]), "sampleCount": int(value["sample_count"]),
            "minSample": int(value["min_sample"]), "cutoffAt": value["cutoff_at"], "observedAt": observed_at,
        }

    def resolve_handoff(self, scope: TenantScope, handoff_id: str) -> dict[str, Any]:
        with self._connect(scope) as conn:
            envelope = conn.execute(
                "SELECT * FROM aip_handoff_envelope WHERE org_id=%s AND project_id=%s AND handoff_id=%s",
                (*scope.key, handoff_id),
            ).fetchone()
            decision = conn.execute(
                "SELECT decision FROM aip_handoff_decision_revision WHERE org_id=%s AND project_id=%s AND handoff_id=%s ORDER BY revision DESC LIMIT 1",
                (*scope.key, handoff_id),
            ).fetchone()
        if envelope is None:
            raise ThreeModuleClosureBlocked("THREE_MODULE_HANDOFF_NOT_FOUND")
        value = dict(envelope)
        task_ref = self._value(value["task_ref"])
        run_ref = self._value(value["task_run_ref"])
        disclosure_count = sum(len(self._value(value[name]) or []) for name in ("object_refs", "artifact_refs", "evidence_refs"))
        digest = canonical_hash({key: value.get(key) for key in ("handoff_id", "status", "version", "task_ref", "task_run_ref", "object_refs", "artifact_refs", "evidence_refs")})
        return {
            "handoffRef": ClosureExactRef(resourceType="HandoffEnvelope", resourceId=handoff_id, revision=int(value["version"]), contentHash=f"sha256:{digest}", receiptId=f"receipt-{handoff_id}"),
            "transportStatus": value["status"], "businessDecision": None if decision is None else decision["decision"],
            "taskRef": task_ref, "taskRunRef": run_ref, "disclosureRefCount": disclosure_count,
        }

    def latest_bindings(self, scope: TenantScope, module: ThreeModule) -> dict[str, Any]:
        with self._connect(scope) as conn:
            closure_row = conn.execute(
                "SELECT authority_data FROM ecommerce_three_module_closure_revision WHERE org_id=%s AND project_id=%s AND module=%s ORDER BY created_at DESC LIMIT 1",
                (*scope.key, module.value),
            ).fetchone()
            if closure_row is None:
                return {"closure": None, "usage": None, "effect": None, "handoff": None}
            closure = ThreeModuleClosureRevision.model_validate(closure_row["authority_data"])
            result: dict[str, Any] = {"closure": closure}
            for key, table, model in (
                ("usage", "ecommerce_three_module_usage_binding_revision", ThreeModuleUsageBindingRevision),
                ("effect", "ecommerce_three_module_effect_binding_revision", ThreeModuleEffectBindingRevision),
                ("handoff", "ecommerce_three_module_handoff_binding_revision", ThreeModuleHandoffBindingRevision),
            ):
                row = conn.execute(
                    f"SELECT authority_data FROM {table} WHERE org_id=%s AND project_id=%s AND closure_id=%s ORDER BY created_at DESC LIMIT 1",
                    (*scope.key, closure.closure_id),
                ).fetchone()
                result[key] = None if row is None else model.model_validate(row["authority_data"])
        return result


__all__ = ["EcommerceWorkshopThreeModuleClosureStore"]
