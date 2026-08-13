"""Pure, fail-closed evaluation for governed knowledge retrieval."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aos_api.aip_contracts import ResourceRef
from aos_api.aip_memory_contracts import KnowledgeCitation


REQUIRED_ROLES = frozenset(
    {
        "private_domain_manager",
        "shopping_advisor",
        "content_officer",
        "customer_service_specialist",
        "campaign_planner",
        "data_strategist",
    }
)


class NegativeExpectation(StrEnum):
    FORBIDDEN = "forbidden"
    STALE = "stale"
    REVOKED = "revoked"
    CONFLICT = "conflict"
    NONE = "none"


class GoldCitationRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_item_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class KnowledgeSearchGoldCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str = Field(min_length=1, max_length=200)
    query: str = Field(min_length=2, max_length=500)
    skill_ref: ResourceRef
    role_dependencies: list[str] = Field(min_length=1, max_length=6)
    gold: GoldCitationRef
    negative_expectation: NegativeExpectation

    @field_validator("role_dependencies")
    @classmethod
    def _roles_are_known_and_unique(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(value not in REQUIRED_ROLES for value in cleaned):
            raise ValueError("gold case contains an unknown role dependency")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("role dependencies must be unique")
        return cleaned


class KnowledgeSearchGoldSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gold_set_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewer: str = Field(min_length=1, max_length=200)
    approved_at: datetime | None = None
    cases: list[KnowledgeSearchGoldCase] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_cases(self) -> KnowledgeSearchGoldSet:
        ids = [case.query_id for case in self.cases]
        gold = [
            (case.gold.memory_item_id, case.gold.revision, case.gold.content_hash)
            for case in self.cases
        ]
        if len(ids) != len(set(ids)):
            raise ValueError("gold query ids must be unique")
        if len(gold) != len(set(gold)):
            raise ValueError("gold citations must be unique")
        return self


class KnowledgeSearchEvalObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str = Field(min_length=1, max_length=200)
    citations: list[KnowledgeCitation] = Field(default_factory=list, max_length=50)
    returned_content_without_citation: bool = False


class KnowledgeSearchEvalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern=r"^(green|red|blocked)$")
    blocked_reasons: list[str] = Field(default_factory=list)
    case_count: int = Field(ge=0)
    role_coverage: dict[str, int]
    top1_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    citation_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    negative_leaks: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _metrics_are_gated(self) -> KnowledgeSearchEvalReport:
        metrics = (self.top1_rate, self.citation_coverage, self.negative_leaks)
        if self.status == "blocked" and (any(value is not None for value in metrics) or not self.blocked_reasons):
            raise ValueError("blocked eval report requires reasons and no metrics")
        if self.status != "blocked" and any(value is None for value in metrics):
            raise ValueError("evaluated report requires all metrics")
        return self


class KnowledgeSearchEvalRunner:
    def evaluate(
        self,
        gold_set: KnowledgeSearchGoldSet,
        observations: list[KnowledgeSearchEvalObservation],
    ) -> KnowledgeSearchEvalReport:
        coverage = Counter(
            role for case in gold_set.cases for role in case.role_dependencies
        )
        role_coverage = {role: coverage[role] for role in sorted(REQUIRED_ROLES)}
        blockers: list[str] = []
        if gold_set.approved_at is None:
            blockers.append("gold_set_unapproved")
        if len(gold_set.cases) < 50:
            blockers.append("gold_set_below_50")
        positive_cases = [
            case
            for case in gold_set.cases
            if case.negative_expectation is NegativeExpectation.NONE
        ]
        if not positive_cases:
            blockers.append("positive_gold_missing")
        missing_roles = [role for role, count in role_coverage.items() if count == 0]
        if missing_roles:
            blockers.append("role_coverage_incomplete")
        by_query = {observation.query_id: observation for observation in observations}
        if len(by_query) != len(observations):
            blockers.append("observation_query_duplicate")
        if set(by_query) != {case.query_id for case in gold_set.cases}:
            blockers.append("observation_set_incomplete")
        if blockers:
            return KnowledgeSearchEvalReport(
                status="blocked",
                blocked_reasons=list(dict.fromkeys(blockers)),
                case_count=len(gold_set.cases),
                role_coverage=role_coverage,
            )
        top1 = 0
        cited = 0
        leaks = 0
        for case in gold_set.cases:
            observation = by_query[case.query_id]
            is_positive = case.negative_expectation is NegativeExpectation.NONE
            if is_positive and observation.citations:
                cited += 1
                first = observation.citations[0]
                if (
                    first.memory_item_id == case.gold.memory_item_id
                    and first.revision == case.gold.revision
                    and first.content_hash == case.gold.content_hash
                ):
                    top1 += 1
            if observation.returned_content_without_citation:
                leaks += 1
            if not is_positive and observation.citations:
                leaks += 1
        total = len(gold_set.cases)
        positive_total = len(positive_cases)
        top1_rate = top1 / positive_total
        citation_coverage = cited / positive_total
        green = top1_rate >= 0.8 and citation_coverage == 1.0 and leaks == 0
        return KnowledgeSearchEvalReport(
            status="green" if green else "red",
            blocked_reasons=[],
            case_count=total,
            role_coverage=role_coverage,
            top1_rate=top1_rate,
            citation_coverage=citation_coverage,
            negative_leaks=leaks,
        )


__all__ = [
    "GoldCitationRef",
    "KnowledgeSearchEvalObservation",
    "KnowledgeSearchEvalReport",
    "KnowledgeSearchEvalRunner",
    "KnowledgeSearchGoldCase",
    "KnowledgeSearchGoldSet",
    "NegativeExpectation",
    "REQUIRED_ROLES",
]
