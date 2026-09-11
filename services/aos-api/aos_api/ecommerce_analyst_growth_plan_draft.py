"""Strict parsing of untrusted D03 proposals; this module grants no authority.

A parsed answer is not a persisted GrowthPlan. The receiving service must still
verify the tenant, exact input sources, completed attempt and artifact hash.
"""
from __future__ import annotations

import json
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=2000)]
SourceIndex = Annotated[int, Field(strict=True, ge=0)]


class _Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class GrowthPlanProposalItem(_Proposal):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    objective: Text
    source_indices: list[SourceIndex] = Field(alias="sourceIndices", min_length=1, max_length=100)


class GrowthPlanProposal(_Proposal):
    objective: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    constraints: list[Text] = Field(max_length=100)
    expected_effect: Text = Field(alias="expectedEffect")
    confidence: float = Field(ge=0, le=1)
    stop_conditions: list[Text] = Field(alias="stopConditions", min_length=1, max_length=100)
    items: list[GrowthPlanProposalItem] = Field(min_length=1, max_length=100)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate model response field")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("nonfinite model response number")


def parse_growth_plan_answer(answer: str, *, source_count: int) -> GrowthPlanProposal:
    """Accept bounded JSON only, with zero-based references to verified sources."""
    if type(source_count) is not int or not 1 <= source_count <= 100:
        raise ValueError("one to one hundred verified sources required")
    if not isinstance(answer, str) or len(answer.encode("utf-8")) > 131072:
        raise ValueError("model response exceeds 128 KiB")
    try:
        payload = json.loads(answer, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except RecursionError as exc:
        raise ValueError("model response nesting exceeds parser limit") from exc
    proposal = GrowthPlanProposal.model_validate(payload)
    for item in proposal.items:
        if len(set(item.source_indices)) != len(item.source_indices):
            raise ValueError("item source indices must be unique")
        if any(index >= source_count for index in item.source_indices):
            raise ValueError("item references an unavailable source")
    return proposal
