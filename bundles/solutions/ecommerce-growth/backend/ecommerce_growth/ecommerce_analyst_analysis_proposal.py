"""Untrusted D01/D02 answers, not authoritative analyst revisions.

Indices refer only to caller-verified inventories. The trusted receiver must
bind actual metrics/method/evaluation/evidence and the original execution hash.
An attribution summary is readable evidence synthesis, not a causal proof or
private chain of thought. No kind, permission or reference is model-assigned.
"""
from __future__ import annotations

import json
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .ecommerce_analyst_growth_plan_draft import _unique_object, _reject_constant

Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=2000)]
Summary = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=4000)]
Index = Annotated[int, Field(strict=True, ge=0)]


class _AnalysisProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    uncertainty: Text
    source_indices: list[Index] = Field(alias="sourceIndices", min_length=1, max_length=100)


class PortraitProposal(_AnalysisProposal):
    summary: Summary
    assumptions: list[Text] = Field(max_length=50)
    metric_indices: list[Index] = Field(alias="metricIndices", min_length=1, max_length=100)


class DiagnosisProposal(_AnalysisProposal):
    conclusion: Summary
    attribution_path: list[Text] = Field(alias="attributionPath", min_length=1, max_length=100)
    key_assumptions: list[Text] = Field(alias="keyAssumptions", max_length=50)
    counter_evidence: list[Text] = Field(alias="counterEvidence", max_length=50)
    alternative_explanations: list[Text] = Field(alias="alternativeExplanations", max_length=50)


def _inventory_size(value: int) -> None:
    if type(value) is not int or not 1 <= value <= 100:
        raise ValueError("one to one hundred verified inventory items required")


def _bounded_payload(answer: str):
    if not isinstance(answer, str) or len(answer.encode("utf-8")) > 131072:
        raise ValueError("analysis answer exceeds 128 KiB")
    try:
        return json.loads(answer, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except RecursionError as exc:
        raise ValueError("analysis answer nesting exceeds parser limit") from exc


def _bound_indices(indices: list[int], count: int) -> None:
    if len(set(indices)) != len(indices) or any(index >= count for index in indices):
        raise ValueError("analysis indices must be unique and reference supplied inventory")


def parse_portrait_answer(answer: str, *, source_count: int, metric_count: int) -> PortraitProposal:
    _inventory_size(source_count)
    _inventory_size(metric_count)
    proposal = PortraitProposal.model_validate(_bounded_payload(answer))
    _bound_indices(proposal.source_indices, source_count)
    _bound_indices(proposal.metric_indices, metric_count)
    return proposal


def parse_diagnosis_answer(answer: str, *, source_count: int) -> DiagnosisProposal:
    _inventory_size(source_count)
    proposal = DiagnosisProposal.model_validate(_bounded_payload(answer))
    _bound_indices(proposal.source_indices, source_count)
    return proposal
