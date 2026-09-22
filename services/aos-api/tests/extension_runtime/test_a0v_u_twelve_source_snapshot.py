"""U twelve-source executor issues fresh authority and never directly runs a definition."""

import importlib.util
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_u_twelve_source_snapshot.py"
SPEC = importlib.util.spec_from_file_location("a0v_u_twelve_source_snapshot", PATH)
snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(snapshot)


def test_u_definition_and_keys_are_independent_from_s():
    assert snapshot.current.U_ID == "277fe01c-ece7-4c8f-9500-fc1ba0d5f050"
    assert snapshot.DEFINITION_ID != "ece2c4cb-743e-56ab-b1d7-41055e606136"
    source = PATH.read_text(encoding="utf-8")
    assert snapshot.CONTROL_PREFIX == "a0v-u-snapshot"
    assert "a0v-u-twelve-source-definition-v1" in source
    assert "a0v-u-twelve-source-enable-v1" in source
    assert snapshot.PREDECESSOR_DEFINITION_ID == "ece2c4cb-743e-56ab-b1d7-41055e606136"
    assert 'load("release-predecessor")' in source


def test_all_twelve_controls_are_fresh_and_schedule_binding_uses_previous_ref():
    source = PATH.read_text(encoding="utf-8")
    assert 'if not overall_intent.exists()' in source
    assert 'preview.confirm_once(' in source
    assert '"previousBindingRef": previous_binding' in source
    assert 'previous_ref=previous_binding' in source
    assert 'if pipeline ==' not in source


def test_execution_is_worker_only_and_inspect_is_repeatable():
    source = PATH.read_text(encoding="utf-8")
    assert "run_definition" not in source
    assert 'if args.action != "inspect":' in source
    assert 'groups[0]["succeeded_members"] != 12' in source
    assert 'groups[0]["saved_inputs"] != 12' in source
    assert 'cron="* * * * *"' in source
    assert 'service.read_recovery_context(' in source
    assert 'service.renew_saved_group(' in source
    assert '"sourceReads": 0' in source
    assert 'expected_ref=definition_ref' in source
    assert 'expected_ref=enabled["ref"]' not in source
    assert 'a0v-u-twelve-source-pause-released-recovery-v1' in source
    assert '"released_resources": 3' in source
