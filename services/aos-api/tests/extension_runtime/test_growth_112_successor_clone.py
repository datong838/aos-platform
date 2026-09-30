"""Fail-closed clone-only guard for the growth 1.12 successor rehearsal."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_growth_112_successor_clone.py"


@pytest.fixture
def successor():
    spec = spec_from_file_location("a0v_growth_112_successor_clone", SCRIPT)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("changed", [
    {"context": "colima-aos-extension"},
    {"container": "aos-a0v-recovery-pg"},
    {"volume": "aos-a0v-recovery-pg-data"},
    {"port": 18435},
    {"database": "postgres"},
    {"org_id": "dev-org"},
    {"project_id": "other-project"},
])
def test_clone_target_rejects_current_or_wrong_identity(successor, changed):
    target = dict(context="colima-aos-a0v-test-only", container="aos-bg00dl-isolated-pg",
                  volume="aos-bg00dl-isolated-pg-data", port=18440,
                  database="aos_current_preview_20260927",
                  org_id="org-org", project_id="dev-project")
    target.update(changed)
    with pytest.raises(successor.SuccessorBlocked, match="CLONE_TARGET_DRIFT"):
        successor.check_clone_target(**target)


def test_same_maker_checker_rejected_before_database_access(successor):
    with pytest.raises(successor.SuccessorBlocked, match="DUTY_SEPARATION_REQUIRED"):
        successor.check_clone_actors("one-person", "one-person")


def test_receipt_with_wrong_growth_version_rejected(successor, tmp_path):
    receipt = tmp_path / "receipt.json"
    receipt.write_text('{"outcome":"SIGNED_TREE_GREEN","contentHashes":{}}\n')
    with pytest.raises(successor.SuccessorBlocked, match="SIGNING_RECEIPT_DRIFT"):
        successor.check_signed_receipt(receipt, expected_growth="1.12.0")


def test_existing_state_is_not_overwritten(successor, tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    (state / "keep").write_text("preserve")
    monkeypatch.setattr(successor, "check_live_clone", lambda: pytest.fail("clone read after existing state"))
    with pytest.raises(successor.SuccessorBlocked, match="STATE_MUST_BE_NEW_OUTSIDE_REPOSITORY"):
        successor.apply_clone(successor={}, current={}, state=state,
                              maker="maker", checker="checker")
    assert (state / "keep").read_text() == "preserve"
