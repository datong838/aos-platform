from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ax_replacement_recovery.py"


def test_ax_replacement_locks_exact_aw_detach_and_disabled_definition():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "f94b9425-9bc4-4369-8ae3-138c50c9ab81"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "0b77ae08-9c8c-4453-9f2b-709bddaca312"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "0c50775b-62fe-4251-81f4-3c9a8709a90e"' in source
    assert "sha256:22b3fbf13e9fb92d3f7a4744a5f2787c9b0d3adf216727ed01439f1cb18d9226" in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 122" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 149" in source
    assert "replacement.DEFINITION_REVISION = 76" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 11" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 6" in source
    assert 'replacement.INSTALLATION_LABEL = "ax"' in source
    assert "run_definition" not in source
