from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ax_terminal_retirement.py"


def test_terminal_ax_retirement_is_exact_and_single_delivery():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'retirement.AQ_ID = "be884663-0dba-4d9b-aa56-84caaf01147d"' in source
    assert '("e5b99486-ecf6-460e-b2d3-de40e372d7c9", 61, "failed"' in source
    assert '"RECOVERABLE_INGRESS_DEADLINE_EXCEEDED", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 79" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 123" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 150" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 125" in source
    assert "retirement.DETACHED_GROUP_REVISION = 152" in source
    assert "a0v-qyh-terminal-ax-retirement-20260919-v1" in source
    assert "a0v_ax_successor_business" in source
    assert "run_definition" not in source


def test_shared_retirement_keeps_single_delivery_and_zero_store_boundary():
    source = (ROOT / "scripts/a0v_aq_failed_retirement.py").read_text(encoding="utf-8")
    assert 'operation_kind="disable", installation_id=AQ_ID' in source
    assert '"resendDisable": False' in source
    assert '"dataset_receipts": 12, "store_receipts": 0' in source
