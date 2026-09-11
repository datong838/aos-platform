"""Package stage-review command identity parity; persistence remains host-owned."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from aos_api.ecommerce_analyst_stage_decision import (
    AnalystStageDecisionRevision as HostDecision,
)
from aos_api.ecommerce_analyst_stage_decision_store import (
    stage_decision_id as host_stage_decision_id,
)


ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / "bundles/solutions/ecommerce-growth/backend"
NOW = datetime(2026, 9, 12, 4, 0, tzinfo=UTC)
ACTOR = "human:stage-reviewer"
HASH = "a" * 64


@pytest.fixture
def package(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND))
    contracts = importlib.import_module(
        "ecommerce_growth.ecommerce_analyst_authority_contracts"
    )
    decisions = importlib.import_module(
        "ecommerce_growth.ecommerce_analyst_stage_decision"
    )
    commands = importlib.import_module(
        "ecommerce_growth.ecommerce_analyst_stage_review_command"
    )
    return contracts, decisions, commands


def canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def ref(kind: str, identity: str) -> dict[str, object]:
    return {
        "resourceType": kind,
        "resourceId": identity,
        "revision": 1,
        "contentHash": HASH,
    }


def package_item(package, stage: str = "portrait"):
    _, decisions, commands = package
    subject = {
        "portrait": "InsightRevision",
        "diagnosis": "DecisionSummaryRevision",
        "solution-design": "GrowthPlanRevision",
    }[stage]
    item = decisions.AnalystStageDecisionRevision.model_validate(
        {
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "decisionId": "pending",
            "revision": 1,
            "version": 1,
            "contentHash": "0" * 64,
            "createdBy": ACTOR,
            "createdAt": NOW,
            "taskRunId": "run-1",
            "planRef": ref("PlanRevision", "plan-1"),
            "stage": stage,
            "stageAttemptRef": {
                "resourceType": "StepRunAttempt",
                "runId": "run-1",
                "stepKey": stage,
                "stepRunId": "step-1",
                "attempt": 1,
                "inputHash": "b" * 64,
            },
            "subjectRef": ref(subject, "subject-1"),
            "artifactRef": ref("Artifact", "artifact-1"),
            "evalReportRef": ref("EvalReportRevision", "eval-1"),
            "responsibilityPlanRef": ref(
                "ResponsibilityPlanRevision", "responsibility-1"
            ),
            "reviewer": {
                "kind": "human_principal",
                "resourceId": ACTOR,
                "version": 1,
            },
            "decision": "accept",
            "reason": "核对来源后接受此版本",
            "expiresAt": NOW + timedelta(hours=1),
        }
    )
    item = item.model_copy(update={"decision_id": commands.stage_decision_id(item)})
    return item.model_copy(
        update={
            "content_hash": canonical_hash(
                item.model_dump(mode="json", by_alias=True, exclude={"content_hash"})
            )
        }
    )


@pytest.mark.parametrize("stage", ["portrait", "diagnosis", "solution-design"])
def test_package_identity_matches_existing_host_algorithm(package, stage: str) -> None:
    _, _, commands = package
    item = package_item(package, stage)
    host = HostDecision.model_validate(item.model_dump(mode="json", by_alias=True))
    assert commands.stage_decision_id(item) == host_stage_decision_id(host)
    assert commands.require_stage_review_command_identity(
        tenant=item.tenant,
        item=item,
        actor=ACTOR,
        key="review-1",
        expected_version=0,
    ) == item


@pytest.mark.parametrize(
    "fault",
    [
        "tenant",
        "actor",
        "blank_actor",
        "blank_key",
        "spaced_key",
        "long_key",
        "negative_version",
        "boolean_version",
        "decision_id",
        "content_hash",
    ],
)
def test_package_rejects_command_identity_drift(package, fault: str) -> None:
    contracts, _, commands = package
    item = package_item(package)
    values = {
        "tenant": item.tenant,
        "item": item,
        "actor": ACTOR,
        "key": "review-1",
        "expected_version": 0,
    }
    if fault == "tenant":
        values["tenant"] = contracts.TenantContext(
            orgId="dev-org", projectId="dev-project"
        )
    elif fault == "actor":
        values["actor"] = "human:other"
    elif fault == "blank_actor":
        values["actor"] = " "
    elif fault == "blank_key":
        values["key"] = ""
    elif fault == "spaced_key":
        values["key"] = " review-1"
    elif fault == "long_key":
        values["key"] = "x" * 201
    elif fault == "negative_version":
        values["expected_version"] = -1
    elif fault == "boolean_version":
        values["expected_version"] = True
    elif fault == "decision_id":
        values["item"] = item.model_copy(update={"decision_id": "stage-review-other"})
    else:
        values["item"] = item.model_copy(update={"reason": "替换后的理由"})
    with pytest.raises(ValueError, match="command identity drifted"):
        commands.require_stage_review_command_identity(**values)


def test_standalone_import_never_loads_platform_modules() -> None:
    program = """
import sys
class DenyPlatform:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "aos_api" or fullname.startswith("aos_api."):
            raise AssertionError("platform import forbidden: " + fullname)
sys.meta_path.insert(0, DenyPlatform())
sys.path.insert(0, sys.argv[1])
from ecommerce_growth.ecommerce_analyst_stage_review_command import stage_decision_id
assert callable(stage_decision_id)
assert not any(name.startswith("aos_api") for name in sys.modules)
"""
    subprocess.run(
        [sys.executable, "-I", "-c", program, str(BACKEND)],
        check=True,
        capture_output=True,
        text=True,
    )
