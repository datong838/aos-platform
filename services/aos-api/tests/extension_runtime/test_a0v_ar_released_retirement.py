"""AR host-release retirement uses the formal disable Owner and frozen boundaries."""
import importlib.util
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ar_released_retirement.py"
SPEC = importlib.util.spec_from_file_location("a0v_ar_released_retirement", PATH)
retirement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retirement)


def test_exact_ar_generation_definition_and_route_revisions_are_fixed():
    assert retirement.AR_ID == "90e9b84e-225c-4c91-a1d4-7d2751d7c7f2"
    assert retirement.GENERATION == "b41dc281-a6f7-4357-948b-88519e8b8146"
    assert retirement.FAILED_ATTEMPTS == ()
    assert retirement.DEFINITION_REVISION == 67
    assert retirement.ACTIVE_ROUTE_REVISION == 105
    assert retirement.ACTIVE_GROUP_REVISION == 132
    assert retirement.DETACHED_ROUTE_REVISION == 107
    assert retirement.DETACHED_GROUP_REVISION == 134
    source = PATH.read_text(encoding="utf-8")
    assert '{"revision": DEFINITION_REVISION, "state": "disabled"}' in source
    assert 'row["revision"] != ACTIVE_ROUTE_REVISION' in source
    assert 'row["cutover_group_revision"] != ACTIVE_GROUP_REVISION' in source
    assert 'row["revision"] != DETACHED_ROUTE_REVISION' in source
    assert 'row["cutover_group_revision"] != DETACHED_GROUP_REVISION' in source
    assert '"revision": 9, "execution_epoch": 5' in source


def test_executor_settles_released_owner_without_touching_snapshot_runs():
    source = PATH.read_text(encoding="utf-8")
    assert "require_released_owner_settlement" in source
    assert "service.request(" in source and "RuntimeDisableConsumer" in source
    assert "finish_claimed" in source
    assert "UPDATE meta_schedule_run" not in source
    assert "pipeline_snapshot_group_input" not in source
    assert '"saved_runs": 12' in source and '"dataset_receipts": 12' in source
