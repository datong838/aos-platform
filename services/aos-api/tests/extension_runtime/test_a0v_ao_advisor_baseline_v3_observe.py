import importlib.util
from pathlib import Path
import sys


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ao_advisor_baseline_v3_observe.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_ao_advisor_baseline_v3_observe", PATH)
observer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(observer)


AO_ID = observer.v3.successor.AO_ID
AO_GENERATION = observer.v3.successor.AO_GENERATION


def _facts():
    occurrence_id = "occurrence-v3"
    target_key = "target-v3"
    return {
        "baseline": {"policy": {"revision": 3}},
        "controls": [{
            "policy_revision": 3,
            "case_id": observer.base.CASE_ID,
            "case_revision": 4,
            "approval_event_id": "approval-v3",
            "installation_id": AO_ID,
            "generation": AO_GENERATION,
            "execution_epoch": 3,
        }],
        "bindings": [{
            "policy_revision": 3,
            "operation_id": observer.AO_OPERATION,
            "approved": True,
            "enabled": True,
            "installation_id": AO_ID,
            "generation": AO_GENERATION,
            "execution_epoch": 3,
        }],
        "occurrences": [{
            "occurrence_id": occurrence_id,
            "policy_revision": 3,
            "operation_id": observer.AO_OPERATION,
            "status": "succeeded",
            "installation_id": AO_ID,
            "generation": AO_GENERATION,
            "execution_epoch": 3,
        }],
        "dispatchAttempts": [{
            "occurrence_id": occurrence_id,
            "target_idempotency_key": target_key,
            "status": "receipt_recorded",
        }],
        "targetReceipts": [{
            "idempotency_key": target_key,
            "operation_id": observer.AO_OPERATION,
            "installation_id": AO_ID,
            "generation": AO_GENERATION,
            "execution_epoch": 3,
        }],
        "runs": [{"run_id": "run-v3"}],
        "growthPlans": [{"plan_id": "plan-v3"}],
    }


def test_v3_observer_phase_order_is_deterministic():
    source = PATH.read_text(encoding="utf-8")
    phases = (
        "awaiting_policy_v3",
        "awaiting_control_v3",
        "awaiting_binding_v3",
        "awaiting_occurrence_v3",
        "occurrence_pending",
        "awaiting_dispatch_receipt",
        "awaiting_target_receipt",
        "awaiting_run",
        "analysis_running",
        "growth_plan_ready",
    )
    positions = [source.index(f'"{phase}"') for phase in phases]
    assert positions == sorted(positions)


def test_v3_observer_is_read_only_and_joins_authority_chain():
    source = PATH.read_text(encoding="utf-8")
    for table in (
        "ecommerce_schedule_policy_control_receipt",
        "automation_schedule_binding",
        "automation_occurrence_dispatch_attempt",
        "ecommerce_growth_runtime_command_receipt",
        "ecommerce_investigation_run_trigger_receipt",
        "ecommerce_investigation_run_state_head",
        "ecommerce_analyst_growth_plan_revision",
    ):
        assert table in source
    assert "generationArtifactRef,resourceId" in source
    assert "JOIN aip_agent_run" in source
    assert "JOIN aip_task_run" in source
    assert "goal#>>'{runRef,resourceId}'=ANY" in source
    assert '"sourceReads": 0' in source
    assert '"businessWrites": 0' in source
    assert "INSERT INTO" not in source
    assert "UPDATE " not in source
    assert "DELETE FROM" not in source
    assert "run_definition" not in source


def test_v3_observer_accepts_only_complete_ao_identity_chain():
    assert observer._phase(_facts()) == "growth_plan_ready"


def test_v3_observer_rejects_wrong_control_identity_and_case_revision():
    for field, value in (
        ("installation_id", "wrong-installation"),
        ("generation", "wrong-generation"),
        ("execution_epoch", 4),
        ("case_revision", 3),
        ("approval_event_id", ""),
    ):
        facts = _facts()
        facts["controls"][0][field] = value
        assert observer._phase(facts) == "awaiting_control_v3"


def test_v3_observer_rejects_wrong_binding_identity_or_operation():
    for field, value in (
        ("installation_id", "wrong-installation"),
        ("generation", "wrong-generation"),
        ("execution_epoch", 4),
        ("operation_id", "wrong-operation"),
        ("approved", False),
        ("enabled", False),
    ):
        facts = _facts()
        facts["bindings"][0][field] = value
        assert observer._phase(facts) == "awaiting_binding_v3"


def test_v3_observer_rejects_wrong_occurrence_and_receipt_identity():
    for field, value in (
        ("installation_id", "wrong-installation"),
        ("generation", "wrong-generation"),
        ("execution_epoch", 4),
        ("operation_id", "wrong-operation"),
    ):
        facts = _facts()
        facts["occurrences"][0][field] = value
        assert observer._phase(facts) == "awaiting_occurrence_v3"

        facts = _facts()
        facts["targetReceipts"][0][field] = value
        assert observer._phase(facts) == "awaiting_target_receipt"


def test_v3_observer_rejects_ambiguous_or_incomplete_occurrence_dispatch():
    facts = _facts()
    facts["occurrences"].append(dict(facts["occurrences"][0], occurrence_id="other"))
    assert observer._phase(facts) == "awaiting_occurrence_v3"

    facts = _facts()
    facts["dispatchAttempts"] = []
    assert observer._phase(facts) == "awaiting_dispatch_receipt"

    facts = _facts()
    facts["targetReceipts"][0]["idempotency_key"] = "wrong-target"
    assert observer._phase(facts) == "awaiting_target_receipt"
