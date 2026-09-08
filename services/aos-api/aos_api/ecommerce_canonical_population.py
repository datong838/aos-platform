"""Bounded current-store identities, never a historical or remote population."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from aos_api.aip_contracts import ResourceRef
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_case_selection import (
    PostgresCanonicalShopSelectionSource,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope


_OBJECT_TYPES = frozenset(
    {"Shop", "Product", "ProductSku", "Category", "Order", "OrderLine", "Shipment"}
)
_MAX_OBJECTS = 99


@dataclass(frozen=True, slots=True)
class CanonicalPopulationSnapshot:
    sources: tuple[ResourceRef, ...]
    # The legacy column mixes upstream version and ingestion times. It is not
    # evidence of observation freshness and must not populate observed_at.
    source_version_times: tuple[datetime, ...]
    collection_domain: Literal["current_canonical_store"] = "current_canonical_store"


class CanonicalPopulationReader:
    def __init__(self, transaction: HostTransaction, scope: TenantScope) -> None:
        self._connect = TransactionBoundConnectFactory(transaction, scope)
        self._transaction = transaction
        self._scope = scope

    def read(
        self,
        *,
        channel_ref: InvestigationExactRef,
        entity_ref: InvestigationExactRef,
        binding_ref: InvestigationExactRef,
        object_types: tuple[str, ...],
    ) -> CanonicalPopulationSnapshot:
        if (
            type(object_types) is not tuple
            or not object_types
            or any(type(item) is not str or item not in _OBJECT_TYPES for item in object_types)
            or len(set(object_types)) != len(object_types)
        ):
            raise ValueError("fixed canonical object types are required")
        if any(type(ref) is not InvestigationExactRef for ref in (channel_ref, entity_ref, binding_ref)):
            raise ValueError("exact selection references are required")
        isolation = self._transaction.execute("SHOW transaction_isolation").fetchone()
        if not isolation or isolation["transaction_isolation"] not in {"repeatable read", "serializable"}:
            raise ValueError("canonical population requires a stable transaction snapshot")
        bound = PostgresCanonicalShopSelectionSource(self._connect).read_bound(self._scope)
        if bound is None or (
            channel_ref, entity_ref, binding_ref
        ) != (
            bound.selection.channel_ref,
            bound.selection.business_entity_ref,
            bound.selection.entity_channel_binding_ref,
        ):
            raise ValueError("current canonical selection drifted or is unavailable")
        rows = self._transaction.execute(
            """SELECT org_id,workspace_id,platform,shop_or_marketplace_id,
                      object_type,external_id,payload_hash,source_updated_at
                 FROM public.ecom_object
                WHERE org_id=%s AND workspace_id=%s
                  AND platform=%s AND shop_or_marketplace_id=%s
                  AND object_type=ANY(%s)
                  AND deleted_at IS NULL AND canonical_status='active'
                ORDER BY object_type,external_id
                LIMIT %s""",
            (*self._scope.key, bound.platform, bound.shop_or_marketplace_id,
             sorted(object_types), _MAX_OBJECTS + 1),
        ).fetchall()
        if len(rows) > _MAX_OBJECTS:
            raise ValueError("canonical population exceeds complete source limit")
        sources: list[ResourceRef] = []
        times: list[datetime] = []
        seen: set[str] = set()
        for row in rows:
            identity = [row[field] for field in (
                "org_id", "workspace_id", "platform", "shop_or_marketplace_id",
                "object_type", "external_id",
            )]
            if (
                any(type(value) is not str or not value or value.strip() != value for value in identity)
                or tuple(identity[:4]) != (*self._scope.key, bound.platform, bound.shop_or_marketplace_id)
                or identity[4] not in object_types
            ):
                raise ValueError("canonical object identity or scope drifted")
            digest = row["payload_hash"]
            version_time = row["source_updated_at"]
            if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                raise ValueError("canonical object hash is invalid")
            if not isinstance(version_time, datetime) or version_time.utcoffset() is None:
                raise ValueError("canonical source version time requires timezone")
            resource_id = "ecom/v1:" + json.dumps(identity, ensure_ascii=False, separators=(",", ":"))
            if resource_id in seen:
                raise ValueError("duplicate canonical object identity")
            seen.add(resource_id)
            sources.append(ResourceRef(
                resource_type="EcommerceObjectRevision", resource_id=resource_id,
                revision=digest, authority="postgres:ecom_object",
            ))
            times.append(version_time)
        return CanonicalPopulationSnapshot(tuple(sources), tuple(times))
