"""Package stage-review slot matching; live plan and Receipt authority stay host-owned."""

from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys

import pytest

from aos_api.aip_production_contracts import ResponsibilitySlot


ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / "bundles/solutions/ecommerce-growth/backend"
ACTOR = "human:stage-reviewer"


@pytest.fixture
def package(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND))
    return importlib.import_module(
        "ecommerce_growth.ecommerce_analyst_stage_review_authority"
    )


def host_slot(stage: str = "portrait", **changes) -> ResponsibilitySlot:
    body = {
        "slotId": f"analyst.{stage}.review",
        "responsibilityType": "independent_review",
        "requiredCapabilityIds": [],
        "inputSchemaRef": {
            "resourceType": "Schema",
            "resourceId": "input",
            "revision": "1",
            "authority": "postgresql",
        },
        "outputSchemaRef": {
            "resourceType": "Schema",
            "resourceId": "output",
            "revision": "1",
            "authority": "postgresql",
        },
        "returnStage": stage,
        "assignee": {
            "kind": "human_principal",
            "resourceId": ACTOR,
            "version": 1,
        },
        "assigneeResolutionReceiptId": "resolution-1",
    }
    body.update(changes)
    return ResponsibilitySlot.model_validate(body)


def package_values(package, stage: str = "portrait") -> dict[str, object]:
    slot = host_slot(stage)
    return {
        "stage": stage,
        "actor": ACTOR,
        "slot_id": slot.slot_id,
        "responsibility_type": slot.responsibility_type,
        "required_capability_ids": slot.required_capability_ids,
        "return_stage": slot.return_stage,
        "assignee": package.AssigneeRef.model_validate(
            slot.assignee.model_dump(mode="json", by_alias=True)
        ),
        "assignee_resolution_receipt_id": slot.assignee_resolution_receipt_id,
    }


@pytest.mark.parametrize("stage", ["portrait", "diagnosis", "solution-design"])
def test_package_accepts_each_exact_host_slot(package, stage: str) -> None:
    values = package_values(package, stage)
    matched = package.require_stage_review_slot(**values)
    assert matched.model_dump(mode="json", by_alias=True) == host_slot(
        stage
    ).assignee.model_dump(mode="json", by_alias=True)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"stage": "unknown"}, "exact stage reviewer"),
        ({"actor": " human:stage-reviewer"}, "exact stage reviewer"),
        ({"slot_id": "analyst.diagnosis.review"}, "does not hold"),
        ({"responsibility_type": "execute"}, "does not hold"),
        ({"required_capability_ids": ["review"]}, "does not hold"),
        ({"required_capability_ids": ()}, "does not hold"),
        ({"return_stage": "diagnosis"}, "does not hold"),
        ({"assignee_resolution_receipt_id": ""}, "does not hold"),
        ({"assignee_resolution_receipt_id": " resolution-1"}, "does not hold"),
        ({"assignee_resolution_receipt_id": "x" * 241}, "does not hold"),
    ],
)
def test_package_rejects_slot_field_drift(package, change, message: str) -> None:
    values = package_values(package)
    values.update(change)
    with pytest.raises(ValueError, match=message):
        package.require_stage_review_slot(**values)


@pytest.mark.parametrize(
    "assignee",
    [
        {"kind": "human_principal", "resourceId": "human:other", "version": 1},
        {"kind": "human_principal", "resourceId": ACTOR, "version": 2},
        {"kind": "agent_instance", "resourceId": ACTOR, "version": 1},
    ],
)
def test_package_rejects_wrong_assignee(package, assignee) -> None:
    values = package_values(package)
    values["assignee"] = package.AssigneeRef.model_validate(assignee)
    with pytest.raises(ValueError, match="does not hold"):
        package.require_stage_review_slot(**values)


def test_package_rejects_boolean_assignee_version(package) -> None:
    values = package_values(package)
    values["assignee"] = package.AssigneeRef.model_construct(
        kind="human_principal", resource_id=ACTOR, version=True
    )
    with pytest.raises(ValueError, match="does not hold"):
        package.require_stage_review_slot(**values)


def test_standalone_import_never_loads_platform_modules() -> None:
    program = """
import sys
class DenyPlatform:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "aos_api" or fullname.startswith("aos_api."):
            raise AssertionError("platform import forbidden: " + fullname)
sys.meta_path.insert(0, DenyPlatform())
sys.path.insert(0, sys.argv[1])
from ecommerce_growth.ecommerce_analyst_stage_review_authority import require_stage_review_slot
assert callable(require_stage_review_slot)
assert not any(name.startswith("aos_api") for name in sys.modules)
"""
    subprocess.run(
        [sys.executable, "-I", "-c", program, str(BACKEND)],
        check=True,
        capture_output=True,
        text=True,
    )
