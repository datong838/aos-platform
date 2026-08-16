"""PostgreSQL authority for AIP-7 exact model runtime revisions."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any, TypeVar

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_model_runtime_contracts import (
    ModelRuntimeAssetSummary,
    ModelRuntimeCapacityPoolSummary,
    ModelRuntimeEvalGateSummary,
    ModelRouteRevision,
    ModelPriceSnapshotRevision,
    ProviderHealthObservation,
    ProviderInstanceRevision,
    RegisteredModelRevision,
    RuntimePolicyRevision,
)
from aos_api.db import connect as db_connect
from aos_api.aip_runtime_guard_policy_store import (
    AipRuntimeGuardPolicyStore,
    GuardPolicyDependencyBlocked,
)
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]
RevisionT = TypeVar(
    "RevisionT",
    ProviderInstanceRevision,
    RegisteredModelRevision,
    RuntimePolicyRevision,
    ModelRouteRevision,
    ModelPriceSnapshotRevision,
)


class ModelRuntimeStoreError(RuntimeError):
    code = "AIP_MODEL_RUNTIME_STORE_ERROR"


class ModelRuntimeNotFound(ModelRuntimeStoreError):
    code = "AIP_RESOURCE_NOT_FOUND"


class ModelRuntimeConflict(ModelRuntimeStoreError):
    code = "AIP_VERSION_CONFLICT"


class ModelRuntimeIdempotencyConflict(ModelRuntimeStoreError):
    code = "AIP_IDEMPOTENCY_CONFLICT"


class ModelRuntimeDependencyBlocked(ModelRuntimeStoreError):
    code = "AIP_DEPENDENCY_BLOCKED"


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class AipModelRuntimeStore:
    _META_FIELDS = {"tenant", "revision", "contentHash", "createdBy", "createdAt"}
    _SPECS = {
        "provider_instance": ("providerInstanceId", ProviderInstanceRevision),
        "registered_model": ("registeredModelId", RegisteredModelRevision),
        "runtime_policy": ("policyId", RuntimePolicyRevision),
        "model_route": ("routeId", ModelRouteRevision),
        "model_price_snapshot": ("priceSnapshotId", ModelPriceSnapshotRevision),
    }

    def __init__(self, connect_factory: ConnectFactory | None = None, *, guard_policy_store=None) -> None:
        self._connect_factory = connect_factory or db_connect
        self._guard_policy_store = guard_policy_store or AipRuntimeGuardPolicyStore(
            connect_factory or db_connect
        )

    def publish_provider(self, scope: TenantScope, actor: str, key: str, item: ProviderInstanceRevision, *, expected_version: int = 0) -> ProviderInstanceRevision:
        try:
            self._guard_policy_store.require_provider_dependencies(scope, item)
        except GuardPolicyDependencyBlocked as exc:
            raise ModelRuntimeDependencyBlocked(str(exc)) from None
        return self._publish("provider_instance", scope, actor, key, item, expected_version)

    def publish_model(self, scope: TenantScope, actor: str, key: str, item: RegisteredModelRevision, *, expected_version: int = 0) -> RegisteredModelRevision:
        return self._publish("registered_model", scope, actor, key, item, expected_version)

    def publish_policy(self, scope: TenantScope, actor: str, key: str, item: RuntimePolicyRevision, *, expected_version: int = 0) -> RuntimePolicyRevision:
        return self._publish("runtime_policy", scope, actor, key, item, expected_version)

    def publish_route(self, scope: TenantScope, actor: str, key: str, item: ModelRouteRevision, *, expected_version: int = 0) -> ModelRouteRevision:
        return self._publish("model_route", scope, actor, key, item, expected_version)

    def publish_price_snapshot(self, scope: TenantScope, actor: str, key: str, item: ModelPriceSnapshotRevision, *, expected_version: int = 0) -> ModelPriceSnapshotRevision:
        return self._publish("model_price_snapshot", scope, actor, key, item, expected_version)

    def get_provider(self, scope: TenantScope, asset_id: str, revision: int | None = None) -> ProviderInstanceRevision:
        return self._get("provider_instance", scope, asset_id, revision)

    def get_model(self, scope: TenantScope, asset_id: str, revision: int | None = None) -> RegisteredModelRevision:
        return self._get("registered_model", scope, asset_id, revision)

    def get_policy(self, scope: TenantScope, asset_id: str, revision: int | None = None) -> RuntimePolicyRevision:
        return self._get("runtime_policy", scope, asset_id, revision)

    def get_route(self, scope: TenantScope, asset_id: str, revision: int | None = None) -> ModelRouteRevision:
        return self._get("model_route", scope, asset_id, revision)

    def get_price_snapshot(self, scope: TenantScope, asset_id: str, revision: int | None = None) -> ModelPriceSnapshotRevision:
        return self._get("model_price_snapshot", scope, asset_id, revision)

    def list_current_assets(self, scope: TenantScope, kind: str) -> list[ModelRuntimeAssetSummary]:
        if kind not in self._SPECS:
            raise ModelRuntimeStoreError("unsupported model runtime asset kind")
        id_alias, model = self._SPECS[kind]
        id_column = f"{kind}_id"
        with self._connect_factory(scope) as conn:
            rows = conn.execute(
                f"""SELECT r.payload FROM aip_{kind}_head h
                JOIN aip_{kind}_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id
                  AND r.{id_column}=h.{id_column} AND r.revision=h.current_revision
                WHERE h.org_id=%s AND h.project_id=%s ORDER BY h.{id_column}""",
                scope.key,
            ).fetchall()
        result: list[ModelRuntimeAssetSummary] = []
        asset_type = model.__name__
        for row in rows:
            item = model.model_validate(self._load(row["payload"]))
            payload = item.model_dump(mode="json", by_alias=False)
            refs = self._dependency_refs(payload)
            result.append(ModelRuntimeAssetSummary(
                ref={"assetType": asset_type, "assetId": payload[self._snake(id_alias)],
                     "revision": item.revision, "contentHash": item.content_hash},
                lifecycle=item.lifecycle, dependencyRefs=refs,
            ))
        return result

    def list_eval_gates(self, scope: TenantScope, refs: list[VersionedAssetRef]) -> list[ModelRuntimeEvalGateSummary]:
        unique = {(ref.asset_id, ref.revision, ref.content_hash): ref for ref in refs if ref.asset_type == "EvalGateDecision"}
        result: list[ModelRuntimeEvalGateSummary] = []
        with self._connect_factory(scope) as conn:
            for key, ref in sorted(unique.items()):
                row = conn.execute(
                    "SELECT status,decision_hash FROM aip_release_gate_decision WHERE org_id=%s AND project_id=%s AND decision_id=%s",
                    (*scope.key, ref.asset_id),
                ).fetchone()
                gate_status = "unknown"
                if row and row["decision_hash"] == ref.content_hash:
                    gate_status = row["status"] if row["status"] in {"passed", "failed", "blocked"} else "unknown"
                result.append(ModelRuntimeEvalGateSummary(ref=ref, status=gate_status))
        return result

    def list_capacity_pools(self, scope: TenantScope) -> list[ModelRuntimeCapacityPoolSummary]:
        with self._connect_factory(scope) as conn:
            rows = conn.execute("""SELECT r.*,
                COUNT(a.reservation_id) FILTER (WHERE a.status IN ('reserved','consumed') AND a.expires_at>NOW()) active_reservations,
                COALESCE(SUM(a.token_units) FILTER (WHERE a.status IN ('reserved','consumed') AND a.expires_at>NOW()),0) reserved_token_units
              FROM aip_model_capacity_pool_head h
              JOIN aip_model_capacity_pool_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id
                AND r.pool_id=h.pool_id AND r.revision=h.current_revision
              LEFT JOIN aip_model_capacity_reservation a ON a.org_id=r.org_id AND a.project_id=r.project_id
                AND a.pool_id=r.pool_id AND a.pool_revision=r.revision
              WHERE h.org_id=%s AND h.project_id=%s
              GROUP BY r.org_id,r.project_id,r.pool_id,r.revision
              ORDER BY r.pool_id""", scope.key).fetchall()
        return [ModelRuntimeCapacityPoolSummary(
            poolId=row["pool_id"], revision=row["revision"], contentHash=row["content_hash"],
            routeRef=self._load(row["route_ref"]), modelRef=self._load(row["model_ref"]),
            providerRef=self._load(row["provider_ref"]), maxConcurrency=row["max_concurrency"],
            maxTokenUnits=row["max_token_units"], tokenUnitPerReservation=row["token_unit_per_reservation"],
            leaseSeconds=row["lease_seconds"], activeReservations=row["active_reservations"],
            reservedTokenUnits=row["reserved_token_units"], lifecycle=row["lifecycle"],
        ) for row in rows]

    def record_health(self, scope: TenantScope, actor: str, key: str, observation: ProviderHealthObservation) -> ProviderHealthObservation:
        self._check_scope(scope, observation)
        payload = observation.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(payload)
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "provider_health.record", key, request_hash)
            if replay:
                return self._health(conn, scope, replay["resourceId"])
            self._require_ref(conn, scope, "provider_instance", observation.provider)
            conn.execute("""INSERT INTO aip_provider_health_observation(
                org_id,project_id,observation_id,provider_ref,status,availability_pct,p50_latency_ms,observed_at,expires_at)
                VALUES(%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)""", (
                *scope.key, observation.observation_id, self._json(payload["provider"]),
                observation.status, observation.availability_pct, observation.p50_latency_ms,
                observation.observed_at, observation.expires_at,
            ))
            self._receipt(conn, scope, "provider_health.record", key, request_hash, {
                "resourceType": "ProviderHealthObservation", "resourceId": observation.observation_id
            }, actor)
            conn.commit()
            return self._health(conn, scope, observation.observation_id)

    def _publish(self, kind: str, scope: TenantScope, actor: str, key: str, item: RevisionT, expected_version: int) -> RevisionT:
        self._check_scope(scope, item)
        id_alias, _ = self._SPECS[kind]
        payload = item.model_dump(mode="json", by_alias=True)
        asset_id = payload[id_alias]
        content = {name: value for name, value in payload.items() if name not in self._META_FIELDS}
        expected_hash = canonical_hash(content)
        if item.content_hash != expected_hash:
            raise ModelRuntimeConflict("content hash does not match canonical revision payload")
        request_hash = canonical_hash({"expectedVersion": expected_version, "revision": payload})
        head_table = f"aip_{kind}_head"
        revision_table = f"aip_{kind}_revision"
        id_column = f"{kind}_id"
        operation = f"{kind}.publish"
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, operation, key, request_hash)
            if replay:
                return self._get(kind, scope, asset_id, int(replay["revision"]), conn=conn)
            head = conn.execute(
                f"SELECT * FROM {head_table} WHERE org_id=%s AND project_id=%s AND {id_column}=%s FOR UPDATE",
                (*scope.key, asset_id),
            ).fetchone()
            version = int(head["version"]) if head else 0
            if version != expected_version:
                raise ModelRuntimeConflict("stale authority head version")
            next_revision = int(head["current_revision"]) + 1 if head else 1
            if item.revision != next_revision:
                raise ModelRuntimeConflict("revision is not the next authority revision")
            self._validate_dependencies(conn, scope, kind, item)
            if head:
                conn.execute(
                    f"UPDATE {head_table} SET current_revision=%s,version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND {id_column}=%s",
                    (item.revision, *scope.key, asset_id),
                )
            else:
                conn.execute(
                    f"INSERT INTO {head_table}(org_id,project_id,{id_column},current_revision,version) VALUES(%s,%s,%s,%s,1)",
                    (*scope.key, asset_id, item.revision),
                )
            conn.execute(
                f"""INSERT INTO {revision_table}(org_id,project_id,{id_column},revision,content_hash,lifecycle,payload,created_by,created_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                (*scope.key, asset_id, item.revision, item.content_hash, item.lifecycle.value, self._json(payload), actor, item.created_at),
            )
            result = {"resourceType": type(item).__name__, "resourceId": asset_id, "revision": item.revision, "contentHash": item.content_hash}
            self._receipt(conn, scope, operation, key, request_hash, result, actor)
            conn.commit()
            return self._get(kind, scope, asset_id, item.revision, conn=conn)

    def _get(self, kind: str, scope: TenantScope, asset_id: str, revision: int | None, *, conn: Any | None = None) -> RevisionT:
        id_alias, model = self._SPECS[kind]
        del id_alias
        id_column = f"{kind}_id"
        head_table = f"aip_{kind}_head"
        revision_table = f"aip_{kind}_revision"

        def read(connection: Any) -> RevisionT:
            target_revision = revision
            if target_revision is None:
                head = connection.execute(
                    f"SELECT current_revision FROM {head_table} WHERE org_id=%s AND project_id=%s AND {id_column}=%s",
                    (*scope.key, asset_id),
                ).fetchone()
                if not head:
                    raise ModelRuntimeNotFound(f"{kind} not found")
                target_revision = int(head["current_revision"])
            row = connection.execute(
                f"SELECT payload FROM {revision_table} WHERE org_id=%s AND project_id=%s AND {id_column}=%s AND revision=%s",
                (*scope.key, asset_id, target_revision),
            ).fetchone()
            if not row:
                raise ModelRuntimeNotFound(f"{kind} revision not found")
            return model.model_validate(self._load(row["payload"]))

        if conn is not None:
            return read(conn)
        with self._connect_factory(scope) as connection:
            return read(connection)

    def _validate_dependencies(self, conn: Any, scope: TenantScope, kind: str, item: RevisionT) -> None:
        if kind == "registered_model":
            self._require_ref(conn, scope, "provider_instance", item.provider)
            self._require_ref(conn, scope, "model_price_snapshot", item.price_snapshot_ref)
        elif kind == "model_route":
            self._require_ref(conn, scope, "runtime_policy", item.runtime_policy_ref)
            for candidate in item.candidates:
                self._require_ref(conn, scope, "registered_model", candidate.model)

    def _require_ref(self, conn: Any, scope: TenantScope, kind: str, ref: VersionedAssetRef) -> None:
        id_column = f"{kind}_id"
        row = conn.execute(
            f"SELECT content_hash,lifecycle FROM aip_{kind}_revision WHERE org_id=%s AND project_id=%s AND {id_column}=%s AND revision=%s",
            (*scope.key, ref.asset_id, ref.revision),
        ).fetchone()
        if not row or row["content_hash"] != ref.content_hash or row["lifecycle"] in {"suspended", "revoked"}:
            raise ModelRuntimeDependencyBlocked(f"exact {kind} dependency missing, drifted, or unavailable")

    @staticmethod
    def _check_scope(scope: TenantScope, item: Any) -> None:
        if (item.tenant.org_id, item.tenant.project_id) != scope.key:
            raise ModelRuntimeDependencyBlocked("payload tenant does not match transaction scope")

    def _health(self, conn: Any, scope: TenantScope, observation_id: str) -> ProviderHealthObservation:
        row = conn.execute(
            "SELECT * FROM aip_provider_health_observation WHERE org_id=%s AND project_id=%s AND observation_id=%s",
            (*scope.key, observation_id),
        ).fetchone()
        if not row:
            raise ModelRuntimeNotFound("provider health observation not found")
        return ProviderHealthObservation(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            observationId=row["observation_id"], provider=self._load(row["provider_ref"]),
            status=row["status"], availabilityPct=row["availability_pct"],
            p50LatencyMs=row["p50_latency_ms"], observedAt=row["observed_at"], expiresAt=row["expires_at"],
        )

    def _replay(self, conn: Any, scope: TenantScope, operation: str, key: str, request_hash: str) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT request_hash,result_ref FROM aip_model_runtime_receipt WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s",
            (*scope.key, operation, key),
        ).fetchone()
        if row and row["request_hash"] != request_hash:
            raise ModelRuntimeIdempotencyConflict("idempotency key payload drift")
        return self._load(row["result_ref"]) if row else None

    def _receipt(self, conn: Any, scope: TenantScope, operation: str, key: str, request_hash: str, result: dict[str, Any], actor: str) -> None:
        conn.execute(
            """INSERT INTO aip_model_runtime_receipt(org_id,project_id,receipt_id,operation,idempotency_key,request_hash,result_ref,created_by)
            VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
            (*scope.key, f"aip7r-{uuid.uuid4().hex[:20]}", operation, key, request_hash, self._json(result), actor),
        )

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

    @staticmethod
    def _load(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value

    @staticmethod
    def _snake(value: str) -> str:
        return "".join(("_" + char.lower()) if char.isupper() else char for char in value)

    @classmethod
    def _dependency_refs(cls, value: Any) -> list[VersionedAssetRef]:
        refs: list[VersionedAssetRef] = []
        if isinstance(value, dict):
            if {"asset_type", "asset_id", "revision", "content_hash"} <= set(value):
                refs.append(VersionedAssetRef.model_validate(value))
            else:
                for item in value.values():
                    refs.extend(cls._dependency_refs(item))
        elif isinstance(value, list):
            for item in value:
                refs.extend(cls._dependency_refs(item))
        return refs
