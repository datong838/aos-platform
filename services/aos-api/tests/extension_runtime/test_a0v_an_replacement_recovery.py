from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_an_replacement_recovery.py"


def test_an_replacement_is_bound_to_am_detach_and_ordered_lifecycle():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AM_ID = "fd28d180-db24-4568-a848-101fcd3aa3c5"' in source
    assert 'AM_GENERATION = "d6bc117e-d19d-4413-beb4-02884206e290"' in source
    assert 'AM_DISABLE_OPERATION = "6d94d641-6fc3-4edd-801c-69114d633c0c"' in source
    assert 'AM_DETACH_RECEIPT = "af6fe6a5-2e88-4b7d-8756-0bc977871a5d"' in source
    assert 'AM_DETACH_HASH = "sha256:6f20be3f146e1f126c110b367bc43ba685d9450c9317d5f4950d29d69e07a709"' in source
    assert '(bindings[0]["revision"], bindings[0]["execution_epoch"]) != (8, 4)' in source
    assert 'row["revision"] != 92' in source
    assert 'row["cutover_group_revision"] != 119' in source
    assert 'current_installation_ref=predecessor' in source
    assert '"preflight", "create-an", "prepare-an", "verify-an", "stage-an"' in source
    assert '"configure-an", "enable-an", "observe"' in source
    assert 'action.removesuffix("-an")' in source
    assert "run_definition" not in source
