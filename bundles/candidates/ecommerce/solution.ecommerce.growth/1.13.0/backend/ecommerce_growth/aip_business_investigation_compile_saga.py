"""N4 start command construction; no runtime authority is created in-package."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping


def build_start_command(
    *,
    occurrence_ref: Mapping[str, object],
    case_ref: Mapping[str, object],
    profile_ref: Mapping[str, object],
    cutoff_at: datetime,
    idempotency_key: str,
) -> dict[str, object]:
    return {
        "operation": "runtime.analysis.start",
        "occurrenceRef": dict(occurrence_ref),
        "caseRef": dict(case_ref),
        "profileRef": dict(profile_ref),
        "cutoffAt": cutoff_at.isoformat(),
        "idempotencyKey": idempotency_key,
        "priorReceiptRef": None,
        "requirementRef": None,
        "fulfillmentRef": None,
        "checkpointRef": None,
    }


__all__ = ["build_start_command"]
