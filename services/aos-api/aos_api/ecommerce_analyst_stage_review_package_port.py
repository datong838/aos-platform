"""One-shot installed-runtime port for no-effect growth review validation."""

from __future__ import annotations

import inspect

from aos_api.asset_registry.canonical_json import canonical_json


_OPERATION = "ecommerce_growth_review_advance"
_KINDS = frozenset(
    {
        "validate_command_identity",
        "validate_review_slot",
        "validate_runtime",
        "validate_eval_proof",
    }
)


class InstalledGrowthStageReviewPort:
    def __init__(self, invoke_once):
        if not callable(invoke_once) or not inspect.iscoroutinefunction(invoke_once):
            raise TypeError("installed async runtime invocation required")
        self._invoke_once = invoke_once

    async def validate(self, *, payload: dict[str, object], expected: dict[str, object]):
        if (
            type(payload) is not dict
            or payload.get("kind") not in _KINDS
            or type(expected) is not dict
        ):
            raise ValueError("exact installed stage review request required")
        canonical_json(payload)
        canonical_json(expected)
        result = await self._invoke_once(_OPERATION, payload)
        if type(result) is not dict:
            raise ValueError("installed stage review response drifted")
        canonical_json(result)
        if result != expected:
            raise ValueError("installed stage review response drifted")
        return result


__all__ = ["InstalledGrowthStageReviewPort"]
