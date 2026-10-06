"""Persist a bounded first Model Eval application without granting execution."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
from aos_api.aip_model_runtime_contracts import (
    ModelPriceSnapshotRevision, ProviderInstanceRevision, RegisteredModelRevision,
)
from aos_api.aip_model_governance_policy_contracts import (
    BudgetPolicyRevision, QuotaPolicyRevision,
)
from aos_api.aip_model_runtime_store import (
    AipModelRuntimeStore, ModelRuntimeConflict, canonical_hash,
)
from aos_api.db import connect_serializable
from aos_api.tenant_scope import TenantScope


class ModelEvalRequestBlocked(RuntimeError):
    code = "MODEL_EVAL_REQUEST_BLOCKED"


class ModelEvalRequestConflict(ModelEvalRequestBlocked):
    code = "MODEL_EVAL_REQUEST_IDEMPOTENCY_CONFLICT"


def _exact_ref(row: dict[str, Any] | None, ref: Any, *, id_column: str) -> bool:
    return bool(row and row[id_column] == ref.asset_id
                and int(row["revision"]) == ref.revision
                and row["content_hash"] == ref.content_hash)


class AipModelEvalRequestStore:
    """One serializable tenant transaction; no Provider, budget hold or Run call."""

    def __init__(self, connect_factory=connect_serializable) -> None:
        self._connect_factory = connect_factory
        self._models = AipModelRuntimeStore()

    @staticmethod
    def _current_revision(conn: Any, scope: TenantScope, kind: str, ref: Any) -> dict[str, Any]:
        specs = {
            "provider": ("aip_provider_instance", "provider_instance_id"),
            "price": ("aip_model_price_snapshot", "model_price_snapshot_id"),
        }
        prefix, id_column = specs[kind]
        row = conn.execute(
            f"""SELECT r.{id_column},r.revision,r.content_hash,r.lifecycle,r.payload
                FROM {prefix}_head h JOIN {prefix}_revision r
                  ON r.org_id=h.org_id AND r.project_id=h.project_id
                 AND r.{id_column}=h.{id_column} AND r.revision=h.current_revision
               WHERE h.org_id=%s AND h.project_id=%s AND h.{id_column}=%s
               FOR SHARE OF h""",
            (*scope.key, ref.asset_id),
        ).fetchone()
        if not _exact_ref(row, ref, id_column=id_column) or row["lifecycle"] != "active":
            raise ModelEvalRequestBlocked(f"current {kind} dependency required")
        model_type = ProviderInstanceRevision if kind == "provider" else ModelPriceSnapshotRevision
        try:
            item = model_type.model_validate(row["payload"])
        except (TypeError, ValueError) as exc:
            raise ModelEvalRequestBlocked(f"current {kind} payload required") from exc
        body = item.model_dump(mode="json", by_alias=True)
        if (item.content_hash != ref.content_hash
            or item.revision != ref.revision
            or (item.provider_instance_id if kind == "provider" else item.price_snapshot_id) != ref.asset_id
            or item.lifecycle.value != row["lifecycle"]
            or (item.tenant.org_id, item.tenant.project_id) != scope.key
            or canonical_hash({k: v for k, v in body.items()
                               if k not in AipModelRuntimeStore._META_FIELDS}) != ref.content_hash):
            raise ModelEvalRequestBlocked(f"current {kind} payload drifted")
        return row

    @staticmethod
    def _current_policy(conn: Any, scope: TenantScope, kind: str, ref: Any,
                        expiry: datetime) -> None:
        row = conn.execute(
            """SELECT r.policy_id,r.revision,r.content_hash,r.lifecycle,
                      r.effective_from,r.effective_until,r.payload
                 FROM aip_model_governance_policy_head h
                 JOIN aip_model_governance_policy_revision r
                   ON r.org_id=h.org_id AND r.project_id=h.project_id
                  AND r.policy_kind=h.policy_kind AND r.policy_id=h.policy_id
                  AND r.revision=h.current_revision
                WHERE h.org_id=%s AND h.project_id=%s
                  AND h.policy_kind=%s AND h.policy_id=%s FOR SHARE OF h""",
            (*scope.key, kind, ref.asset_id),
        ).fetchone()
        if (not _exact_ref(row, ref, id_column="policy_id")
            or row["lifecycle"] != "active"
            or row["effective_from"] > datetime.now(UTC)
            or row["effective_until"] < expiry):
            raise ModelEvalRequestBlocked(f"current {kind} policy window required")
        model_type = QuotaPolicyRevision if kind == "quota" else BudgetPolicyRevision
        try:
            item = model_type.model_validate(row["payload"])
        except (TypeError, ValueError) as exc:
            raise ModelEvalRequestBlocked(f"current {kind} policy payload required") from exc
        body = item.model_dump(mode="json", by_alias=True)
        if (item.content_hash != ref.content_hash
            or item.lifecycle.value != row["lifecycle"]
            or (item.tenant.org_id, item.tenant.project_id) != scope.key
            or canonical_hash({k: v for k, v in body.items()
                               if k not in {"tenant", "contentHash", "createdBy", "createdAt"}})
               != ref.content_hash):
            raise ModelEvalRequestBlocked(f"current {kind} policy payload drifted")

    @staticmethod
    def _eval_sources(conn: Any, scope: TenantScope, request: ModelEvalRequestCreate) -> None:
        suite = conn.execute(
            """SELECT suite_id,revision,content_hash,target_ref
                 FROM aip_eval_suite_revision
                WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s""",
            (*scope.key, request.suite_ref.asset_id, request.suite_ref.revision),
        ).fetchone()
        target = request.target_ref
        suite_target = {
            "assetType": "registered_model", "assetId": target.asset_id,
            "revision": str(target.revision), "contentHash": target.content_hash,
        }
        if (not _exact_ref(suite, request.suite_ref, id_column="suite_id")
            or suite["target_ref"] != suite_target):
            raise ModelEvalRequestBlocked("exact Model Eval Suite target required")
        contract = conn.execute(
            """SELECT r.contract_id,r.revision,r.content_hash,r.lifecycle,r.suite_ref
                 FROM aip_eval_contract_head h JOIN aip_eval_contract_revision r
                   ON r.org_id=h.org_id AND r.project_id=h.project_id
                  AND r.contract_id=h.contract_id AND r.revision=h.current_revision
                WHERE h.org_id=%s AND h.project_id=%s AND h.contract_id=%s
                FOR SHARE OF h""",
            (*scope.key, request.eval_contract_ref.asset_id),
        ).fetchone()
        exact_suite = {
            "resourceType": "EvalSuiteRevision", "resourceId": request.suite_ref.asset_id,
            "revision": request.suite_ref.revision,
            "contentHash": request.suite_ref.content_hash,
        }
        if (not _exact_ref(contract, request.eval_contract_ref, id_column="contract_id")
            or contract["lifecycle"] != "frozen"
            or contract["suite_ref"] != exact_suite):
            raise ModelEvalRequestBlocked("current frozen Eval Contract required")
        from aos_api.aip_production_contract_store import AipProductionContractStore
        original = AipProductionContractStore().get_eval_contract(
            scope, request.eval_contract_ref.asset_id, request.eval_contract_ref.revision, conn=conn)
        if (original.content_hash != request.eval_contract_ref.content_hash
            or original.lifecycle.value != "frozen" or original.readiness.value != "ready"
            or original.blockers):
            raise ModelEvalRequestBlocked("current ready frozen Eval Contract required")

    def require_current(self, conn: Any, scope: TenantScope,
                        request: ModelEvalRequestCreate) -> None:
        if (type(scope) is not TenantScope or type(request) is not ModelEvalRequestCreate
            or (request.tenant.org_id, request.tenant.project_id) != scope.key
            or request.expires_at <= datetime.now(UTC)):
            raise ModelEvalRequestBlocked("exact tenant and future application required")
        try:
            self._models.require_current_model_eval_candidate_for_update(
                conn, scope, request.source_ref, request.target_ref,
                expected_head_version=request.expected_head_version,
            )
        except ModelRuntimeConflict as exc:
            raise ModelEvalRequestBlocked("current Model Eval candidate required") from exc
        source = conn.execute(
            """SELECT payload FROM aip_registered_model_revision
                WHERE org_id=%s AND project_id=%s AND registered_model_id=%s
                  AND revision=%s""",
            (*scope.key, request.source_ref.asset_id, request.source_ref.revision),
        ).fetchone()
        try:
            model = RegisteredModelRevision.model_validate(source["payload"])
        except (TypeError, ValueError, KeyError) as exc:
            raise ModelEvalRequestBlocked("current Model payload required") from exc
        if (model.provider != request.provider_ref
            or model.price_snapshot_ref != request.price_ref
            or model.quota_policy_ref != request.quota_policy_ref
            or model.budget_policy_ref != request.budget_policy_ref):
            raise ModelEvalRequestBlocked("Model dependency refs drifted")
        self._eval_sources(conn, scope, request)
        self._current_revision(conn, scope, "provider", request.provider_ref)
        price_row = self._current_revision(conn, scope, "price", request.price_ref)
        try:
            price = ModelPriceSnapshotRevision.model_validate(price_row["payload"])
        except (TypeError, ValueError) as exc:
            raise ModelEvalRequestBlocked("current price payload required") from exc
        if (price.currency != request.currency
            or price.effective_from > datetime.now(UTC)
            or (price.effective_until is not None and price.effective_until < request.expires_at)):
            raise ModelEvalRequestBlocked("current price window required")
        self._current_policy(conn, scope, "quota", request.quota_policy_ref, request.expires_at)
        self._current_policy(conn, scope, "budget", request.budget_policy_ref, request.expires_at)

    def create(self, scope: TenantScope, actor: str, idempotency_key: str,
               request: ModelEvalRequestCreate) -> dict[str, Any]:
        if (type(scope) is not TenantScope or type(request) is not ModelEvalRequestCreate
            or not actor or actor.strip() != actor
            or not idempotency_key or idempotency_key.strip() != idempotency_key):
            raise ModelEvalRequestBlocked("exact application actor and key required")
        body = request.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(body)
        with self._connect_factory(scope) as conn:
            identity = conn.execute(
                "SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
                "current_setting('aos.project_id',true) AS project_id",
            ).fetchone()
            if (identity["role"], identity["org_id"], identity["project_id"]) != (
                "aos_runtime", *scope.key,
            ):
                raise ModelEvalRequestBlocked("tenant runtime DB role required")
            member = conn.execute(
                """SELECT role FROM meta_membership
                     WHERE org_id=%s AND project_id=%s AND subject=%s FOR SHARE""",
                (*scope.key, actor),
            ).fetchall()
            if len(member) != 1 or member[0]["role"].lower() not in {"owner", "admin"}:
                raise ModelEvalRequestBlocked("current Model Eval maker required")
            self.require_current(conn, scope, request)
            row = conn.execute(
                """INSERT INTO aip_model_eval_request (
                     org_id,project_id,request_id,idempotency_key,request_hash,request_json,
                     source_ref,target_ref,expected_head_version,eval_contract_ref,suite_ref,
                     provider_ref,price_ref,quota_policy_ref,budget_policy_ref,
                     purpose,currency,upper_bound_minor,expires_at,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb,
                           %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                           %s,%s,%s,%s,%s)
                   ON CONFLICT (org_id,project_id,idempotency_key) DO NOTHING
                   RETURNING request_id,request_hash,request_json,created_by,created_at""",
                (*scope.key, f"model-eval-request-{uuid.uuid4().hex[:20]}",
                 idempotency_key, request_hash, json.dumps(body),
                 json.dumps(body["sourceRef"]), json.dumps(body["targetRef"]),
                 request.expected_head_version, json.dumps(body["evalContractRef"]),
                 json.dumps(body["suiteRef"]), json.dumps(body["providerRef"]),
                 json.dumps(body["priceRef"]), json.dumps(body["quotaPolicyRef"]),
                 json.dumps(body["budgetPolicyRef"]), request.purpose, request.currency,
                 request.upper_bound_minor, request.expires_at, actor),
            ).fetchone()
            if row is None:
                row = conn.execute(
                    """SELECT request_id,request_hash,request_json,created_by,created_at
                         FROM aip_model_eval_request
                        WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
                    (*scope.key, idempotency_key),
                ).fetchone()
                if row is None or row["request_hash"] != request_hash or row["created_by"] != actor:
                    raise ModelEvalRequestConflict("Model Eval application key drifted")
            conn.commit()
            return dict(row)


__all__ = ["AipModelEvalRequestStore", "ModelEvalRequestBlocked", "ModelEvalRequestConflict"]
