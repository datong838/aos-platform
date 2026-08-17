"""Append-only exact authority for AIP-7 model capacity pools."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, ModelRuntimeStoreError
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class CapacityPoolAuthorityError(RuntimeError):
    code = "AIP_CAPACITY_POOL_AUTHORITY_ERROR"


class CapacityPoolAuthorityNotFound(CapacityPoolAuthorityError):
    code = "AIP_CAPACITY_POOL_NOT_FOUND"


class CapacityPoolAuthorityConflict(CapacityPoolAuthorityError):
    code = "AIP_CAPACITY_POOL_CONFLICT"


class CapacityPoolAuthorityDependencyBlocked(CapacityPoolAuthorityError):
    code = "AIP_CAPACITY_POOL_DEPENDENCY_BLOCKED"


class CapacityPoolRevisionCreate(AipContractModel):
    pool_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    route_ref: VersionedAssetRef
    model_ref: VersionedAssetRef
    provider_ref: VersionedAssetRef
    max_concurrency: int = Field(ge=1)
    max_token_units: int = Field(ge=1)
    token_unit_per_reservation: int = Field(ge=1)
    lease_seconds: int = Field(ge=1, le=86400)
    lifecycle: Literal["draft", "active", "suspended", "revoked"]

    @model_validator(mode="after")
    def _exact_refs(self) -> "CapacityPoolRevisionCreate":
        expected = {
            "route_ref": "ModelRouteRevision",
            "model_ref": "RegisteredModelRevision",
            "provider_ref": "ProviderInstanceRevision",
        }
        for name, kind in expected.items():
            if getattr(self, name).asset_type != kind:
                raise ValueError(f"{name} must reference {kind}")
        if self.token_unit_per_reservation > self.max_token_units:
            raise ValueError("token_unit_per_reservation exceeds max_token_units")
        return self


class CapacityPoolRevision(CapacityPoolRevisionCreate):
    tenant: TenantContext
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def materialize_capacity_pool(
    scope: TenantScope,
    actor: str,
    item: CapacityPoolRevisionCreate,
    *,
    created_at: datetime | None = None,
) -> CapacityPoolRevision:
    content = item.model_dump(mode="json", by_alias=True)
    return CapacityPoolRevision.model_validate({
        **content,
        "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
        "contentHash": canonical_hash(content),
        "createdBy": actor,
        "createdAt": created_at or datetime.now(UTC),
    })


class AipModelCapacityAuthorityStore:
    def __init__(
        self,
        connect_factory: ConnectFactory | None = None,
        *,
        model_store: Any | None = None,
    ) -> None:
        self._connect_factory = connect_factory or db_connect
        self._model_store = model_store or AipModelRuntimeStore(connect_factory)

    def publish(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        item: CapacityPoolRevisionCreate,
        *,
        expected_version: int = 0,
    ) -> CapacityPoolRevision:
        self._require_dependencies(scope, item)
        request_hash = canonical_hash({
            "expectedVersion": expected_version,
            "revision": item.model_dump(mode="json", by_alias=True),
        })
        operation = "model_capacity_pool.publish"
        with self._connect_factory(scope) as conn:
            replay = conn.execute(
                "SELECT request_hash,result_ref FROM aip_model_runtime_receipt "
                "WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s",
                (*scope.key, operation, key),
            ).fetchone()
            if replay:
                if replay["request_hash"] != request_hash:
                    raise CapacityPoolAuthorityConflict("idempotency key payload drifted")
                result_ref = self._load(replay["result_ref"])
                return self.get(scope, result_ref["resourceId"], int(result_ref["revision"]), conn=conn)

            head = conn.execute(
                "SELECT current_revision,version FROM aip_model_capacity_pool_head "
                "WHERE org_id=%s AND project_id=%s AND pool_id=%s FOR UPDATE",
                (*scope.key, item.pool_id),
            ).fetchone()
            version = int(head["version"]) if head else 0
            if version != expected_version:
                raise CapacityPoolAuthorityConflict("stale capacity pool head version")
            next_revision = int(head["current_revision"]) + 1 if head else 1
            if item.revision != next_revision:
                raise CapacityPoolAuthorityConflict("revision is not the next capacity pool revision")
            result = materialize_capacity_pool(scope, actor, item)
            if head:
                conn.execute(
                    "UPDATE aip_model_capacity_pool_head SET current_revision=%s,version=version+1,updated_at=NOW() "
                    "WHERE org_id=%s AND project_id=%s AND pool_id=%s",
                    (result.revision, *scope.key, result.pool_id),
                )
            else:
                conn.execute(
                    "INSERT INTO aip_model_capacity_pool_head(org_id,project_id,pool_id,current_revision,version) "
                    "VALUES(%s,%s,%s,%s,1)",
                    (*scope.key, result.pool_id, result.revision),
                )
            refs = [
                result.route_ref.model_dump(mode="json", by_alias=True),
                result.model_ref.model_dump(mode="json", by_alias=True),
                result.provider_ref.model_dump(mode="json", by_alias=True),
            ]
            conn.execute(
                """INSERT INTO aip_model_capacity_pool_revision(
                org_id,project_id,pool_id,revision,content_hash,
                route_ref,model_ref,provider_ref,
                route_id,route_revision,route_hash,
                model_id,model_revision,model_hash,
                provider_id,provider_revision,provider_hash,
                max_concurrency,max_token_units,token_unit_per_reservation,
                lease_seconds,lifecycle,created_by,created_at)
                VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    *scope.key, result.pool_id, result.revision, result.content_hash,
                    *(self._json(value) for value in refs),
                    result.route_ref.asset_id, result.route_ref.revision, result.route_ref.content_hash,
                    result.model_ref.asset_id, result.model_ref.revision, result.model_ref.content_hash,
                    result.provider_ref.asset_id, result.provider_ref.revision, result.provider_ref.content_hash,
                    result.max_concurrency, result.max_token_units,
                    result.token_unit_per_reservation, result.lease_seconds,
                    result.lifecycle, actor, result.created_at,
                ),
            )
            result_ref = {
                "resourceType": "ModelCapacityPoolRevision",
                "resourceId": result.pool_id,
                "revision": result.revision,
                "contentHash": result.content_hash,
            }
            conn.execute(
                """INSERT INTO aip_model_runtime_receipt(
                org_id,project_id,receipt_id,operation,idempotency_key,request_hash,result_ref,created_by)
                VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                (*scope.key, f"aip7cap-{uuid.uuid4().hex[:20]}", operation, key,
                 request_hash, self._json(result_ref), actor),
            )
            conn.commit()
            return self.get(scope, result.pool_id, result.revision)

    def get(
        self,
        scope: TenantScope,
        pool_id: str,
        revision: int | None = None,
        *,
        conn=None,
    ) -> CapacityPoolRevision:
        def read(connection) -> CapacityPoolRevision:
            target = revision
            if target is None:
                head = connection.execute(
                    "SELECT current_revision FROM aip_model_capacity_pool_head "
                    "WHERE org_id=%s AND project_id=%s AND pool_id=%s",
                    (*scope.key, pool_id),
                ).fetchone()
                if not head:
                    raise CapacityPoolAuthorityNotFound("capacity pool not found")
                target = int(head["current_revision"])
            row = connection.execute(
                "SELECT * FROM aip_model_capacity_pool_revision "
                "WHERE org_id=%s AND project_id=%s AND pool_id=%s AND revision=%s",
                (*scope.key, pool_id, target),
            ).fetchone()
            if not row:
                raise CapacityPoolAuthorityNotFound("capacity pool revision not found")
            return CapacityPoolRevision(
                tenant={"orgId": scope.org_id, "projectId": scope.project_id},
                poolId=row["pool_id"], revision=row["revision"], contentHash=row["content_hash"],
                routeRef=self._load(row["route_ref"]), modelRef=self._load(row["model_ref"]),
                providerRef=self._load(row["provider_ref"]), maxConcurrency=row["max_concurrency"],
                maxTokenUnits=row["max_token_units"],
                tokenUnitPerReservation=row["token_unit_per_reservation"],
                leaseSeconds=row["lease_seconds"], lifecycle=row["lifecycle"],
                createdBy=row["created_by"], createdAt=row["created_at"],
            )

        if conn is not None:
            return read(conn)
        with self._connect_factory(scope) as connection:
            return read(connection)

    def _require_dependencies(self, scope: TenantScope, item: CapacityPoolRevisionCreate) -> None:
        try:
            route = self._model_store.get_route(scope, item.route_ref.asset_id, item.route_ref.revision)
            model = self._model_store.get_model(scope, item.model_ref.asset_id, item.model_ref.revision)
            provider = self._model_store.get_provider(scope, item.provider_ref.asset_id, item.provider_ref.revision)
        except ModelRuntimeStoreError:
            raise CapacityPoolAuthorityDependencyBlocked("exact model runtime dependency unavailable") from None
        exact = (
            (route, "route_id", item.route_ref),
            (model, "registered_model_id", item.model_ref),
            (provider, "provider_instance_id", item.provider_ref),
        )
        for asset, id_field, ref in exact:
            if (
                getattr(asset, id_field) != ref.asset_id
                or asset.revision != ref.revision
                or asset.content_hash != ref.content_hash
                or asset.lifecycle.value != "active"
            ):
                raise CapacityPoolAuthorityDependencyBlocked("exact model runtime dependency drifted")
        if not any(candidate.model == item.model_ref for candidate in route.candidates):
            raise CapacityPoolAuthorityDependencyBlocked("route does not contain exact model")
        if model.provider != item.provider_ref:
            raise CapacityPoolAuthorityDependencyBlocked("model does not bind exact provider")

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

    @staticmethod
    def _load(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value

