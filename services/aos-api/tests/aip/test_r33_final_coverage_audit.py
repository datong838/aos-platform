from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "aip" / "audit_r33_final_coverage.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("audit_r33_final_coverage", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r33_final_coverage_is_exact_and_fails_closed_operationally() -> None:
    report = _load_audit_module().build_report(
        REPO_ROOT,
        checked_at="2026-08-22T12:00:00+08:00",
    )

    assert report["verdict"] == "STRUCTURAL_GREEN_OPERATIONAL_BLOCKED"
    assert report["referenceErrors"] == {
        "logicAgentRefs": [],
        "logicCapabilityRefs": [],
        "harnessLogicRefs": [],
        "harnessCapabilityRefs": [],
        "scenarioLogicRefs": [],
    }
    dimensions = {row["id"]: row for row in report["dimensions"]}
    assert {key: row["actual"] for key, row in dimensions.items()} == {
        "agents": 6,
        "logics": 37,
        "capabilities": 10,
        "knowledgePipelines": 7,
        "reflectionRules": 26,
        "platformHarnesses": 14,
        "scenarios": 9,
    }
    assert dimensions["agents"]["operationalStatus"] == "BLOCKED"
    assert dimensions["knowledgePipelines"]["operationalStatus"] == "BLOCKED_EXTERNAL"
    assert dimensions["platformHarnesses"]["unverifiedRuleAuthorityCount"] == 14
    assert report["blockers"]["scenarioStatuses"] == [
        "code_control_draft_real_tenant_evidence_blocked"
    ]
