"""Package stage-decision parity; current decision authority remains host-owned."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from aos_api.aip_eval_contracts import EvalStageAttemptRef as HostAttemptRef
from aos_api.aip_production_contracts import AssigneeRef as HostAssigneeRef
from aos_api.ecommerce_analyst_stage_decision import (
    AnalystStageDecisionRevision as HostDecision,
    require_stage_decision_applicable as require_host,
)
from aos_api.tenant_scope import TenantScope


ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / "bundles/solutions/ecommerce-growth/backend"
NOW = datetime(2026, 9, 12, 3, 0, tzinfo=UTC)
HASH = "a" * 64


@pytest.fixture
def package(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND))
    return importlib.import_module("ecommerce_growth.ecommerce_analyst_stage_decision")


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


def decision_payload(**changes) -> dict[str, object]:
    stage = changes.get("stage", "portrait")
    subject = {
        "portrait": "InsightRevision",
        "diagnosis": "DecisionSummaryRevision",
        "solution-design": "GrowthPlanRevision",
    }.get(stage, "InsightRevision")
    body = {
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "decisionId": "review-1",
        "revision": 1,
        "version": 1,
        "contentHash": "0" * 64,
        "createdBy": "human:reviewer",
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
        "responsibilityPlanRef": ref("ResponsibilityPlanRevision", "responsibility-1"),
        "reviewer": {
            "kind": "human_principal",
            "resourceId": "human:reviewer",
            "version": 1,
        },
        "decision": "accept",
        "reason": "核对来源后接受此版本",
        "expiresAt": NOW + timedelta(hours=1),
    }
    body.update(changes)
    return body


def package_decision(package, **changes):
    item = package.AnalystStageDecisionRevision.model_validate(decision_payload(**changes))
    return item.model_copy(
        update={
            "content_hash": canonical_hash(
                item.model_dump(mode="json", by_alias=True, exclude={"content_hash"})
            )
        }
    )


@pytest.mark.parametrize(
    ("package_name", "host_type"),
    [
        ("EvalStageAttemptRef", HostAttemptRef),
        ("AssigneeRef", HostAssigneeRef),
        ("AnalystStageDecisionRevision", HostDecision),
    ],
)
def test_package_models_match_host_json_schema(package, package_name, host_type) -> None:
    assert getattr(package, package_name).model_json_schema() == host_type.model_json_schema()


@pytest.mark.parametrize("stage", ["portrait", "diagnosis", "solution-design"])
def test_valid_package_decision_serializes_like_host(package, stage: str) -> None:
    payload = decision_payload(stage=stage)
    package_item = package.AnalystStageDecisionRevision.model_validate(payload)
    host_item = HostDecision.model_validate(payload)
    assert package_item.model_dump(mode="json", by_alias=True) == host_item.model_dump(
        mode="json", by_alias=True
    )


def test_package_applicability_matches_host_for_exact_accept(package) -> None:
    package_item = package_decision(package)
    host_item = HostDecision.model_validate(
        package_item.model_dump(mode="json", by_alias=True)
    )
    host_values = {
        key: getattr(host_item, key)
        for key in (
            "task_run_id",
            "plan_ref",
            "stage",
            "stage_attempt_ref",
            "subject_ref",
            "artifact_ref",
            "eval_report_ref",
            "responsibility_plan_ref",
        )
    }
    assert require_host(
        scope=TenantScope("org-org", "dev-project"),
        decision=host_item,
        now=NOW,
        **host_values,
    ) is None
    package_values = {
        key: getattr(package_item, key)
        for key in host_values
    }
    tenant = package_item.tenant
    assert package.require_stage_decision_applicable(
        tenant=tenant,
        decision=package_item,
        now=NOW,
        **package_values,
    ) is None


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("expired", "unavailable"),
        ("wrong_tenant", "unavailable"),
        ("changed_hash", "unavailable"),
        ("wrong_subject", "different inputs"),
        ("non_accept", "unavailable"),
    ],
)
def test_package_applicability_rejects_expiry_and_substitution(package, change, message) -> None:
    item = package_decision(
        package,
        **({"decision": "return", "expiresAt": None} if change == "non_accept" else {}),
    )
    values = {
        key: getattr(item, key)
        for key in (
            "task_run_id",
            "plan_ref",
            "stage",
            "stage_attempt_ref",
            "subject_ref",
            "artifact_ref",
            "eval_report_ref",
            "responsibility_plan_ref",
        )
    }
    tenant, now, decision = item.tenant, NOW, item
    if change == "expired":
        now = item.expires_at
    elif change == "wrong_tenant":
        tenant = package.TenantContext(orgId="dev-org", projectId="dev-project")
    elif change == "changed_hash":
        decision = item.model_copy(update={"reason": "被替换"})
    elif change == "wrong_subject":
        values["subject_ref"] = item.subject_ref.model_copy(
            update={"content_hash": "d" * 64}
        )
    with pytest.raises(ValueError, match=message):
        package.require_stage_decision_applicable(
            tenant=tenant,
            decision=decision,
            now=now,
            **values,
        )


@pytest.mark.parametrize("field", ["planRef", "subjectRef", "stageAttemptRef", "reviewer"])
def test_package_rejects_boolean_nested_versions(package, field: str) -> None:
    payload = decision_payload()
    nested = dict(payload[field])
    nested[
        "attempt" if field == "stageAttemptRef" else "version" if field == "reviewer" else "revision"
    ] = True
    payload[field] = nested
    with pytest.raises(ValueError):
        package.AnalystStageDecisionRevision.model_validate(payload)


def test_standalone_import_never_loads_platform_modules() -> None:
    program = """
import sys
class DenyPlatform:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "aos_api" or fullname.startswith("aos_api."):
            raise AssertionError("platform import forbidden: " + fullname)
sys.meta_path.insert(0, DenyPlatform())
sys.path.insert(0, sys.argv[1])
from ecommerce_growth.ecommerce_analyst_stage_decision import AnalystStageDecisionRevision
assert AnalystStageDecisionRevision.model_json_schema()["title"] == "AnalystStageDecisionRevision"
assert not any(name.startswith("aos_api") for name in sys.modules)
"""
    subprocess.run(
        [sys.executable, "-I", "-c", program, str(BACKEND)],
        check=True,
        capture_output=True,
        text=True,
    )
