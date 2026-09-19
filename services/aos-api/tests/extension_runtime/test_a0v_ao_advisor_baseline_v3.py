from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys

import pytest


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ao_advisor_baseline_v3.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("a0v_ao_advisor_baseline_v3_tested", SCRIPT)
v3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v3)


def test_ao_policy_v3_executor_is_exact_and_fail_closed():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "67c2331d-b73f-4863-b881-0d67e6c55508"' in text
    assert 'expectedPolicyRevision": 2' in text
    assert 'expectedCaseVersion": 4' in text
    assert '"revision": 59' in text
    assert 'recovery.get("revision") != 19' in text
    assert "a0v-s-baseline-v2-pre-target-close-20260917" in text
    assert '"store_receipts": 1' in text
    assert '"live_links": 1168' in text
    assert '"routes": 9' in text
    assert 'binding.get("revision") != 6' in text
    assert 'binding.get("execution_epoch") != 3' in text
    assert 'current_occurrences[0]["status"] != "succeeded"' in text
    assert 'observed["phase"] != "growth_plan_ready"' in text
    assert 'observed["growthPlans"][0]["payload"].get("lifecycle") != "draft"' in text
    assert "run_definition" not in text
    assert "sourceRowsRead" not in text
    assert "INSERT INTO" not in text
    assert "UPDATE " not in text


def test_ao_policy_v3_uses_fresh_idempotency_and_approval():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "a0v-ao-advisor-baseline-policy-put-20260919-v3" in text
    assert "a0v-ao-advisor-baseline-schedule-approval-20260919-v3" in text
    assert "a0v-ao-advisor-baseline-policy-disable-20260919-v4" in text
    assert "a0v-ao-advisor-baseline-disable-approval-20260919-v4" in text
    assert '"expectedPolicyRevision": 3' in text
    assert "AipActionStore" in text
    assert "ActionApprovalEvent" in (ROOT / "scripts/a0v_q_advisor_baseline.py").read_text(
        encoding="utf-8"
    )
    assert "EcommerceGrowthCanonicalRouter" in (
        ROOT / "scripts/a0v_q_advisor_baseline.py"
    ).read_text(encoding="utf-8")


def terminal_observation(**changes):
    value = {
        "phase": "growth_plan_ready",
        "baseline": {
            "policy": {"revision": 3, "enabled": True},
            "case": {"revision": 4, "contentHash": "sha256:" + "a" * 64},
            "activeRuns": 0,
        },
        "occurrences": [{"occurrence_id": "occ-v3", "policy_revision": 3, "status": "succeeded"}],
        "dispatchAttempts": [{
            "occurrence_id": "occ-v3", "target_idempotency_key": "target-v3",
            "status": "receipt_recorded",
        }],
        "targetReceipts": [{"idempotency_key": "target-v3"}],
        "runs": [{"run_id": "run-v3", "trigger_key": "target-v3", "lifecycle": "SUCCEEDED"}],
        "growthPlans": [{"plan_id": "plan-v3", "payload": {"lifecycle": "draft"}}],
        "canary": {"bindings": 0, "occurrences": 0, "runs": 0},
    }
    value.update(changes)
    return value


def test_disable_readiness_requires_exact_successful_natural_chain(monkeypatch):
    monkeypatch.setitem(sys.modules, "a0v_ao_advisor_baseline_v3_observe", SimpleNamespace(
        observe=lambda _previous: terminal_observation()
    ))
    result = v3.disable(object(), None, None)
    assert result["outcome"] == "AO_ADVISOR_BASELINE_V3_DISABLE_READY"
    assert result["policy"]["enabled"] is False
    assert result["growthPlan"]["plan_id"] == "plan-v3"


def test_disable_readiness_rejects_unrelated_or_unfinished_plan(monkeypatch):
    monkeypatch.setitem(sys.modules, "a0v_ao_advisor_baseline_v3_observe", SimpleNamespace(
        observe=lambda _previous: terminal_observation(
            growthPlans=[{"plan_id": "other", "payload": {"lifecycle": "approved"}}]
        )
    ))
    with pytest.raises(RuntimeError, match="terminal AO Policy v3 occurrence"):
        v3.disable(object(), None, None)
