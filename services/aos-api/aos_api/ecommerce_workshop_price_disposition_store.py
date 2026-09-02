"""Tenant-scoped append-only persistence for W6-06 price dispositions."""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import psycopg

from aos_api.db import connect
from aos_api.db import connect_read_only
from aos_api.ecommerce_workshop_price_disposition import (
    PriceCaseRevision,
    PriceDispositionBlocked,
    PriceDispositionContractRevision,
    PriceDispositionObservation,
    PriceDispositionRevision,
)
from aos_api.ecommerce_workshop_price_governance_contracts import PriceExactRef
from aos_api.tenant_scope import TenantScope


class EcommerceWorkshopPriceDispositionStore:
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
            raise PriceDispositionBlocked("PRICE_DISPOSITION_TENANT_DRIFT")

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
                raise PriceDispositionBlocked("PRICE_DISPOSITION_IDEMPOTENCY_CONFLICT")
            conn.commit()
        return type(item).model_validate(row["authority_data"])

    def _require(self, scope: TenantScope, table: str, identity_column: str, ref: PriceExactRef, model: type[Any]) -> Any:
        with self._read_connect(scope) as conn:
            row = conn.execute(
                f"SELECT authority_data,content_hash FROM {table} WHERE org_id=%s AND project_id=%s AND {identity_column}=%s AND revision=%s",
                (*scope.key, ref.resource_id, ref.revision),
            ).fetchone()
        if row is None or f"sha256:{row['content_hash']}" != ref.content_hash:
            raise PriceDispositionBlocked(f"{ref.resource_type.upper()}_MISSING_OR_DRIFTED")
        item = model.model_validate(row["authority_data"])
        self._assert_tenant(scope, item)
        return item

    def append_case(self, scope: TenantScope, item: PriceCaseRevision) -> PriceCaseRevision:
        return self._append(scope, "ecommerce_price_case_revision", "case_id", item.case_id, item.revision, item.content_hash, item, item.created_at)

    def append_contract(self, scope: TenantScope, item: PriceDispositionContractRevision) -> PriceDispositionContractRevision:
        return self._append(scope, "ecommerce_price_disposition_contract_revision", "contract_id", item.contract_id, item.revision, item.content_hash, item, item.created_at)

    def append_disposition(self, scope: TenantScope, item: PriceDispositionRevision) -> PriceDispositionRevision:
        return self._append(scope, "ecommerce_price_disposition_revision", "disposition_id", item.disposition_id, item.revision, item.content_hash, item, item.created_at)

    def append_observation(self, scope: TenantScope, item: PriceDispositionObservation) -> PriceDispositionObservation:
        return self._append(scope, "ecommerce_price_disposition_observation", "observation_id", item.observation_id, item.revision, item.content_hash, item, item.observed_at)

    def require_case(self, scope: TenantScope, ref: PriceExactRef) -> PriceCaseRevision:
        return self._require(scope, "ecommerce_price_case_revision", "case_id", ref, PriceCaseRevision)

    def require_contract(self, scope: TenantScope, ref: PriceExactRef) -> PriceDispositionContractRevision:
        return self._require(scope, "ecommerce_price_disposition_contract_revision", "contract_id", ref, PriceDispositionContractRevision)

    def require_disposition(self, scope: TenantScope, ref: PriceExactRef) -> PriceDispositionRevision:
        return self._require(scope, "ecommerce_price_disposition_revision", "disposition_id", ref, PriceDispositionRevision)

    def latest_disposition(self, scope: TenantScope, disposition_id: str) -> PriceDispositionRevision:
        with self._read_connect(scope) as conn:
            row = conn.execute(
                "SELECT authority_data FROM ecommerce_price_disposition_revision WHERE org_id=%s AND project_id=%s AND disposition_id=%s ORDER BY revision DESC LIMIT 1",
                (*scope.key, disposition_id),
            ).fetchone()
        if row is None:
            raise PriceDispositionBlocked("PRICE_DISPOSITION_NOT_FOUND")
        item = PriceDispositionRevision.model_validate(row["authority_data"])
        self._assert_tenant(scope, item)
        return item

    def latest_disposition_or_none(self, scope: TenantScope, disposition_id: str) -> PriceDispositionRevision | None:
        try:
            return self.latest_disposition(scope, disposition_id)
        except PriceDispositionBlocked as exc:
            if str(exc) == "PRICE_DISPOSITION_NOT_FOUND":
                return None
            raise

    def _list(self, scope: TenantScope, table: str, model: type[Any]) -> list[Any]:
        try:
            with self._read_connect(scope) as conn:
                rows = conn.execute(
                    f"SELECT authority_data FROM {table} WHERE org_id=%s AND project_id=%s ORDER BY created_at,revision",
                    scope.key,
                ).fetchall()
        except psycopg.Error as exc:
            raise PriceDispositionBlocked("PRICE_DISPOSITION_AUTHORITY_UNAVAILABLE") from exc
        items = [model.model_validate(row["authority_data"]) for row in rows]
        for item in items:
            self._assert_tenant(scope, item)
        return items

    def list_cases(self, scope: TenantScope) -> list[PriceCaseRevision]:
        return self._list(scope, "ecommerce_price_case_revision", PriceCaseRevision)

    def list_dispositions(self, scope: TenantScope) -> list[PriceDispositionRevision]:
        return self._list(scope, "ecommerce_price_disposition_revision", PriceDispositionRevision)

    def list_observations(self, scope: TenantScope) -> list[PriceDispositionObservation]:
        return self._list(scope, "ecommerce_price_disposition_observation", PriceDispositionObservation)

    def require_gate_authorities(
        self,
        scope: TenantScope,
        contract: PriceDispositionContractRevision,
        gate_refs: dict[str, PriceExactRef],
    ) -> None:
        del scope, contract, gate_refs
        # Caller-shaped exact refs are not authority. Canonical per-gate resolvers
        # must be wired before the production store may prepare a disposition.
        raise PriceDispositionBlocked("PRICE_DISPOSITION_GATE_AUTHORITY_RESOLVER_UNAVAILABLE")

    def require_outcome_receipt(self, scope: TenantScope, ref: PriceExactRef, binding_hash: str) -> None:
        if ref.resource_type != "ActionReceipt":
            raise PriceDispositionBlocked("PRICE_DISPOSITION_RECEIPT_AUTHORITY_RESOLVER_UNAVAILABLE")
        with self._read_connect(scope) as conn:
            row = conn.execute(
                "SELECT receipt_content_hash,action_binding_hash FROM aip_action_receipt WHERE org_id=%s AND project_id=%s AND receipt_id=%s",
                (*scope.key, ref.resource_id),
            ).fetchone()
        if row is None or f"sha256:{row['receipt_content_hash']}" != ref.content_hash or row["action_binding_hash"] != binding_hash:
            raise PriceDispositionBlocked("PRICE_DISPOSITION_ACTION_RECEIPT_MISSING_OR_BINDING_DRIFTED")


__all__ = ["EcommerceWorkshopPriceDispositionStore"]
