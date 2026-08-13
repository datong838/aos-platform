from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_contracts import ArtifactRef, ResourceRef
from aos_api.aip_memory_contracts import KnowledgeCitation, KnowledgeSourceRef
from aos_api.aip_memory_search_eval import (
    KnowledgeSearchEvalObservation,
    KnowledgeSearchEvalRunner,
    KnowledgeSearchGoldCase,
    KnowledgeSearchGoldSet,
    REQUIRED_ROLES,
)

NOW = datetime(2026, 8, 13, 8, tzinfo=UTC)
HASH = "a" * 64


def ref(kind: str, identifier: str) -> ResourceRef:
    return ResourceRef(
        resource_type=kind,
        resource_id=identifier,
        revision="1",
        authority="postgresql",
    )


def gold_set(count: int, *, approved: bool = True) -> KnowledgeSearchGoldSet:
    roles = sorted(REQUIRED_ROLES)
    return KnowledgeSearchGoldSet(
        gold_set_id="beauty-search-v1",
        revision=1,
        content_hash=HASH,
        reviewer="beauty-domain-expert",
        approved_at=NOW if approved else None,
        cases=[
            KnowledgeSearchGoldCase(
                query_id=f"q-{index}",
                query=f"美妆问题 {index}",
                skill_ref=ref("aip.skill", "content"),
                role_dependencies=[roles[index % len(roles)]],
                gold={
                    "memory_item_id": f"memory-{index}",
                    "revision": 1,
                    "content_hash": f"{index:064x}",
                },
                negative_expectation="forbidden" if index == 0 else "none",
            )
            for index in range(count)
        ],
    )


def citation(index: int) -> KnowledgeCitation:
    content_hash = f"{index:064x}"
    return KnowledgeCitation(
        memory_item_id=f"memory-{index}",
        revision=1,
        scope="workspace",
        subject=ref("ecom.product", f"product-{index}"),
        payload=ArtifactRef(
            artifact_id=f"artifact-{index}",
            artifact_type="memory_payload",
            revision="1",
            content_hash=content_hash,
        ),
        content_hash=content_hash,
        source=KnowledgeSourceRef(
            source_kind="authorized_document",
            source_uri=f"https://example.invalid/source-{index}",
            observed_at=NOW,
            freshness_expires_at=NOW + timedelta(days=30),
            license_id="authorized",
            usage_policy="summary-and-citation",
            content_hash=HASH,
            provider="pytest",
            provider_version="1",
            applicability=["vertical:ecommerce"],
        ),
        freshness="active",
        confidence=0.9,
        applicability=["vertical:ecommerce"],
        markings=["internal"],
    )


def observations(count: int, *, leak_negative: bool = False):
    return [
        KnowledgeSearchEvalObservation(
            query_id=f"q-{index}",
            citations=(
                [citation(index)]
                if index != 0 or leak_negative
                else []
            ),
        )
        for index in range(count)
    ]


def test_unapproved_and_below_50_are_blocked_without_metrics() -> None:
    report = KnowledgeSearchEvalRunner().evaluate(
        gold_set(6, approved=False), observations(6)
    )
    assert report.status == "blocked"
    assert report.blocked_reasons == ["gold_set_unapproved", "gold_set_below_50"]
    assert report.top1_rate is None
    assert report.citation_coverage is None


def test_missing_observation_blocks_metric_calculation() -> None:
    report = KnowledgeSearchEvalRunner().evaluate(gold_set(50), observations(49))
    assert report.status == "blocked"
    assert report.blocked_reasons == ["observation_set_incomplete"]


def test_negative_forbidden_case_is_green_only_when_empty() -> None:
    report = KnowledgeSearchEvalRunner().evaluate(gold_set(50), observations(50))
    assert report.status == "green"
    assert report.top1_rate == 1.0
    assert report.citation_coverage == 1.0
    assert report.negative_leaks == 0


def test_any_negative_leak_forces_red() -> None:
    report = KnowledgeSearchEvalRunner().evaluate(
        gold_set(50), observations(50, leak_negative=True)
    )
    assert report.status == "red"
    assert report.top1_rate == 1.0
    assert report.citation_coverage == 1.0
    assert report.negative_leaks == 1


def test_gold_set_rejects_unknown_roles_and_duplicate_gold() -> None:
    with pytest.raises(ValueError, match="unknown role"):
        KnowledgeSearchGoldCase(
            query_id="q",
            query="美妆问题",
            skill_ref=ref("aip.skill", "content"),
            role_dependencies=["unknown"],
            gold={"memory_item_id": "m", "revision": 1, "content_hash": HASH},
            negative_expectation="none",
        )
    data = gold_set(2).model_dump(mode="python")
    data["cases"][1]["gold"] = data["cases"][0]["gold"]
    with pytest.raises(ValueError, match="citations must be unique"):
        KnowledgeSearchGoldSet.model_validate(data)


def test_all_negative_gold_set_is_blocked_without_metrics() -> None:
    data = gold_set(50).model_dump(mode="python")
    for case in data["cases"]:
        case["negative_expectation"] = "forbidden"
    report = KnowledgeSearchEvalRunner().evaluate(
        KnowledgeSearchGoldSet.model_validate(data),
        [
            KnowledgeSearchEvalObservation(query_id=f"q-{index}")
            for index in range(50)
        ],
    )
    assert report.status == "blocked"
    assert report.blocked_reasons == ["positive_gold_missing"]
    assert report.top1_rate is None
