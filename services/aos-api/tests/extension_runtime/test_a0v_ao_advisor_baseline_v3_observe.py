import importlib.util
from pathlib import Path
import sys


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ao_advisor_baseline_v3_observe.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("a0v_ao_advisor_baseline_v3_observe", PATH)
observer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(observer)


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
