"""Package runtime matching; Task, Checkpoint, and Evidence authority stay host-owned."""

from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / "bundles/solutions/ecommerce-growth/backend"
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
    runtime = importlib.import_module(
        "ecommerce_growth.ecommerce_analyst_stage_review_runtime"
    )
    return contracts, decisions, runtime


def exact(contracts, kind: str, identity: str):
    return contracts.AnalystExactRef(
        resourceType=kind,
        resourceId=identity,
        revision=1,
        contentHash=HASH,
    )


def values(package, stage: str = "portrait") -> dict[str, object]:
    contracts, decisions, _ = package
    kind = {
        "portrait": "InsightRevision",
        "diagnosis": "DecisionSummaryRevision",
        "solution-design": "GrowthPlanRevision",
    }[stage]
    return {
        "task_run_id": "run-1",
        "plan_ref": exact(contracts, "PlanRevision", "plan-1"),
        "stage": stage,
        "stage_attempt_ref": decisions.EvalStageAttemptRef(
            runId="run-1",
            stepKey=stage,
            stepRunId="step-1",
            attempt=1,
            inputHash="b" * 64,
        ),
        "subject_ref": exact(contracts, kind, "subject-1"),
    }


def observation(values: dict[str, object]) -> dict[str, object]:
    key = {
        "portrait": "insightRef",
        "diagnosis": "decisionRef",
        "solution-design": "growthPlanRef",
    }[values["stage"]]
    return {
        "stepRunId": values["stage_attempt_ref"].step_run_id,
        "stepKey": values["stage"],
        "payload": {
            key: values["subject_ref"].model_dump(mode="json", by_alias=True)
        },
    }


@pytest.mark.parametrize("stage", ["portrait", "diagnosis", "solution-design"])
def test_package_matches_each_exact_runtime_and_observation(package, stage: str) -> None:
    values_ = values(package, stage)
    _, _, runtime = package
    assert runtime.require_stage_runtime_references(**values_) == values_["subject_ref"]
    assert runtime.require_observed_stage_subject(
        stage=stage,
        step_run_id=values_["stage_attempt_ref"].step_run_id,
        subject_ref=values_["subject_ref"],
        observation_payload=observation(values_),
    ) == values_["subject_ref"]


@pytest.mark.parametrize(
    "fault",
    [
        "stage",
        "blank_run",
        "plan_type",
        "subject_type",
        "attempt_run",
        "attempt_step",
        "solution_underscore",
        "boolean_attempt",
    ],
)
def test_package_rejects_runtime_reference_drift(package, fault: str) -> None:
    contracts, decisions, runtime = package
    stage = "solution-design" if fault == "solution_underscore" else "portrait"
    values_ = values(package, stage)
    if fault == "stage":
        values_["stage"] = "unknown"
    elif fault == "blank_run":
        values_["task_run_id"] = " "
    elif fault == "plan_type":
        values_["plan_ref"] = exact(contracts, "Artifact", "plan-1")
    elif fault == "subject_type":
        values_["subject_ref"] = exact(contracts, "Artifact", "subject-1")
    elif fault == "attempt_run":
        values_["stage_attempt_ref"] = values_["stage_attempt_ref"].model_copy(
            update={"run_id": "run-2"}
        )
    elif fault in {"attempt_step", "solution_underscore"}:
        values_["stage_attempt_ref"] = values_["stage_attempt_ref"].model_copy(
            update={"step_key": "solution_design"}
        )
    else:
        values_["stage_attempt_ref"] = decisions.EvalStageAttemptRef.model_construct(
            resource_type="StepRunAttempt",
            run_id="run-1",
            step_key="portrait",
            step_run_id="step-1",
            attempt=True,
            input_hash="b" * 64,
        )
    with pytest.raises(ValueError, match="exact stage runtime"):
        runtime.require_stage_runtime_references(**values_)


@pytest.mark.parametrize(
    "fault",
    [
        "body_type",
        "step_run",
        "stage",
        "payload_type",
        "missing_ref",
        "changed_ref",
    ],
)
def test_package_rejects_observation_subject_drift(package, fault: str) -> None:
    _, _, runtime = package
    values_ = values(package)
    body = observation(values_)
    if fault == "body_type":
        body = []
    elif fault == "step_run":
        body["stepRunId"] = "step-2"
    elif fault == "stage":
        body["stepKey"] = "diagnosis"
    elif fault == "payload_type":
        body["payload"] = []
    elif fault == "missing_ref":
        body["payload"] = {}
    else:
        body["payload"]["insightRef"]["contentHash"] = "c" * 64
    with pytest.raises(ValueError, match="different subject"):
        runtime.require_observed_stage_subject(
            stage="portrait",
            step_run_id="step-1",
            subject_ref=values_["subject_ref"],
            observation_payload=body,
        )


def test_standalone_import_never_loads_platform_modules() -> None:
    program = """
import sys
class DenyPlatform:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "aos_api" or fullname.startswith("aos_api."):
            raise AssertionError("platform import forbidden: " + fullname)
sys.meta_path.insert(0, DenyPlatform())
sys.path.insert(0, sys.argv[1])
from ecommerce_growth.ecommerce_analyst_stage_review_runtime import require_stage_runtime_references
assert callable(require_stage_runtime_references)
assert not any(name.startswith("aos_api") for name in sys.modules)
"""
    subprocess.run(
        [sys.executable, "-I", "-c", program, str(BACKEND)],
        check=True,
        capture_output=True,
        text=True,
    )
