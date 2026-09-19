from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ay_replacement_recovery.py"


def test_ay_replacement_locks_exact_ax_detach_and_disabled_definition():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "be884663-0dba-4d9b-aa56-84caaf01147d"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "8589a12c-aec2-4035-8937-f358dd1a8488"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "622c8e25-ec0f-40dd-bf1f-ea57d180a800"' in source
    assert "sha256:583954da94992d30f7c5f9133c235eb3b17e0d8d190c27d61fe47621d41a6870" in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 125" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 152" in source
    assert "replacement.DEFINITION_REVISION = 79" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 8" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 4" in source
    assert 'replacement.INSTALLATION_LABEL = "ay"' in source
    assert "run_definition" not in source
