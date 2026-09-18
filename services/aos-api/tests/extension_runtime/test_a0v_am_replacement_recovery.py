from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_am_replacement_recovery.py"


def test_am_replacement_is_bound_to_al_detach_and_ordered_lifecycle():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AL_ID = "071e1c31-c464-4735-952e-17adf0ac97f7"' in source
    assert 'AL_GENERATION = "d50a7eed-18e1-491a-9323-ab3ca693dc3a"' in source
    assert 'AL_DISABLE_OPERATION = "c9328938-3b56-4a8d-ac38-54f7abf70416"' in source
    assert 'AL_DETACH_RECEIPT = "bd92aa48-77b6-4c34-82f9-0ede171083b3"' in source
    assert 'AL_DETACH_HASH = "sha256:b8990ed467aed1bdfc40e5fb56e4455e2ece7114045f37a15f8f4099a313e1df"' in source
    assert '(bindings[0]["revision"], bindings[0]["execution_epoch"]) != (8, 4)' in source
    assert 'row["revision"] != 89' in source and 'row["cutover_group_revision"] != 116' in source
    assert 'current_installation_ref=predecessor' in source
    assert '"preflight", "create-am", "prepare-am", "verify-am", "stage-am"' in source
    assert '"configure-am", "enable-am", "observe"' in source
    assert 'action.removesuffix("-am")' in source
    assert "run_definition" not in source
