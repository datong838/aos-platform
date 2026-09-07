"""N1 command composition; execution remains fenced until AR2-7 cutover."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from aos_extension_sdk import DispatchRef

from .sdk_ports import GrowthWritePort


class EcommerceGrowthApplication:
    def __init__(self, write_port: GrowthWritePort) -> None:
        self._write_port = write_port

    def commit_case_or_schedule(
        self,
        *,
        dispatch_ref: DispatchRef,
        command: Mapping[str, Any],
        occurred_at: datetime,
    ) -> Mapping[str, Any]:
        if dispatch_ref.operation_id not in {
            "ecommerce_growth_case_put",
            "ecommerce_growth_schedule_put",
        }:
            raise ValueError("dispatch operation does not belong to N1")
        if occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must include timezone")
        if any(key in command for key in ("tenant", "dispatchRef", "installationId", "generation")):
            raise ValueError("command cannot override host authority")
        return self._write_port.commit(
            dispatch_ref=dispatch_ref,
            command=dict(command),
            occurred_at=occurred_at,
        )


__all__ = ["EcommerceGrowthApplication"]
