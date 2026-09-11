"""Tenant-bound host port for authorized ecommerce analyst source material."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping

from aos_api.ecommerce_analyst_analysis_sources import (
    AnalysisBundleSourceRequest,
    read_analysis_bundle,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


class BoundEcommerceGrowthAnalysisSourcePort:
    """Keep tenant and transaction authority outside the solution package."""

    __slots__ = ("_transaction", "_scope")

    def __init__(self, transaction: HostTransaction, scope: TenantScope) -> None:
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("host transaction and tenant scope are required")
        self._transaction = transaction
        self._scope = scope

    def read(
        self,
        *,
        task_id: str,
        actor: str,
        request: Mapping[str, Any],
        markings: tuple[str, ...],
        now: datetime,
        max_source_age_seconds: int,
        max_bytes: int,
    ) -> Mapping[str, Any]:
        if (
            type(task_id) is not str
            or not 1 <= len(task_id.strip()) <= 240
            or type(actor) is not str
            or not 1 <= len(actor.strip()) <= 240
            or not isinstance(request, Mapping)
            or type(markings) is not tuple
            or not markings
            or len(markings) != len(set(markings))
            or any(type(item) is not str or not 1 <= len(item.strip()) <= 120 for item in markings)
            or not isinstance(now, datetime)
            or now.utcoffset() is None
            or type(max_source_age_seconds) is not int
            or not 1 <= max_source_age_seconds <= 2_678_400
            or type(max_bytes) is not int
            or not 1 <= max_bytes <= 2_097_152
        ):
            raise ValueError("invalid analysis source read boundary")
        body = AnalysisBundleSourceRequest.model_validate(dict(request))
        return read_analysis_bundle(
            conn=self._transaction,
            scope=self._scope,
            task_id=task_id,
            actor=actor,
            request=body,
            markings=markings,
            now=now,
            max_source_age=timedelta(seconds=max_source_age_seconds),
            max_bytes=max_bytes,
        )


__all__ = ["BoundEcommerceGrowthAnalysisSourcePort"]
