"""Package authority DTO parity; these contracts do not grant business authority."""

from __future__ import annotations

from datetime import UTC, datetime
import importlib
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

from aos_api import ecommerce_analyst_authority_contracts as host


ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / "bundles/solutions/ecommerce-growth/backend"
HASH = "a" * 64
NOW = datetime(2026, 9, 12, tzinfo=UTC)
TENANT = {"orgId": "org-org", "projectId": "dev-project"}
MODEL_NAMES = (
    "AnalystExactRef",
    "MethodRevision",
    "InsightRevision",
    "DecisionSummaryRevision",
    "GrowthPlanItem",
    "GrowthPlanRevision",
    "TaskGraphMapping",
    "TaskGraphRevision",
    "EcommerceEffectReviewRevision",
    "AnalystAuthorityReceipt",
)


@pytest.fixture
def package(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND))
    return importlib.import_module("ecommerce_growth.ecommerce_analyst_authority_contracts")


def ref(kind: str, identity: str) -> dict[str, object]:
    return {
        "resourceType": kind,
        "resourceId": identity,
        "revision": 1,
        "contentHash": HASH,
    }


def insight() -> dict[str, object]:
    return {
        "tenant": TENANT,
        "insightId": "insight-1",
        "revision": 1,
        "version": 1,
        "kind": "observation",
        "summary": "可回源的经营观察",
        "metricRefs": [ref("MetricObservationRevision", "metric-1")],
        "evidenceRefs": [ref("EvidenceBundleRevision", "evidence-1")],
        "methodRef": ref("MethodRevision", "method-1"),
        "evalRef": ref("EvalContractRevision", "eval-1"),
        "cutoffAt": NOW,
        "assumptions": ["同一截止时间"],
        "uncertainty": "尚未证明因果",
        "contentHash": HASH,
        "createdBy": "user:operator",
        "createdAt": NOW,
    }


def plan() -> dict[str, object]:
    return {
        "tenant": TENANT,
        "planId": "plan-1",
        "revision": 1,
        "version": 1,
        "lifecycle": "draft",
        "decisionRef": ref("DecisionSummaryRevision", "decision-1"),
        "objective": "形成有来源的内部内容任务",
        "constraints": ["禁止外部发布"],
        "budget": "100.00",
        "expectedEffect": "待真实效果窗口核验",
        "confidence": 0.5,
        "stopConditions": ["来源失效"],
        "items": [
            {
                "itemId": "item-1",
                "taskType": "content",
                "title": "准备商品介绍",
                "objective": "核对商品事实后形成草稿",
                "evidenceRefs": [ref("EvidenceBundleRevision", "evidence-1")],
            }
        ],
        "contentHash": HASH,
        "createdBy": "user:operator",
        "createdAt": NOW,
    }


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_every_package_model_has_exact_host_json_schema(package, name: str) -> None:
    assert getattr(package, name).model_json_schema() == getattr(host, name).model_json_schema()


@pytest.mark.parametrize(
    ("name", "payload"),
    (("InsightRevision", insight()), ("GrowthPlanRevision", plan())),
)
def test_representative_objects_serialize_exactly_like_host(package, name: str, payload: dict) -> None:
    package_value = getattr(package, name).model_validate(payload)
    host_value = getattr(host, name).model_validate(payload)
    assert package_value.model_dump(mode="json", by_alias=True) == host_value.model_dump(
        mode="json", by_alias=True
    )


def test_package_rejects_wrong_reference_and_naive_timestamps(package) -> None:
    wrong = insight()
    wrong["methodRef"] = ref("EvidenceBundleRevision", "wrong")
    with pytest.raises(ValidationError, match="methodRef"):
        package.InsightRevision.model_validate(wrong)

    naive = insight()
    naive["createdAt"] = datetime(2026, 9, 12)
    with pytest.raises(ValidationError, match="createdAt"):
        package.InsightRevision.model_validate(naive)


def test_standalone_import_never_loads_platform_modules() -> None:
    program = """
import sys
class DenyPlatform:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "aos_api" or fullname.startswith("aos_api."):
            raise AssertionError("platform import forbidden: " + fullname)
sys.meta_path.insert(0, DenyPlatform())
sys.path.insert(0, sys.argv[1])
from ecommerce_growth.ecommerce_analyst_authority_contracts import GrowthPlanRevision
assert GrowthPlanRevision.model_json_schema()["title"] == "GrowthPlanRevision"
assert not any(name.startswith("aos_api") for name in sys.modules)
"""
    subprocess.run(
        [sys.executable, "-I", "-c", program, str(BACKEND)],
        check=True,
        capture_output=True,
        text=True,
    )
