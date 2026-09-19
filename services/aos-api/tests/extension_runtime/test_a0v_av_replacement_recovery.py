from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "scripts/a0v_av_replacement_recovery.py"


def tree():
    return ast.parse(SOURCE.read_text(encoding="utf-8"))


def test_av_replacement_locks_exact_at_retirement_and_disabled_definition():
    source = SOURCE.read_text(encoding="utf-8")
    assert 'AU_DISABLE_OPERATION = "51bdbc84-901f-448d-87e8-5a655790e0d3"' in source
    assert 'AU_DETACH_RECEIPT = "7e223943-906f-4efe-8d4b-da7fc2424e48"' in source
    assert 'AU_DETACH_HASH = "sha256:a3155cdf8c5fe13995faac9de8f6d8eedbf83609239303f09d9fcee8119bdfb1"' in source
    assert "PREDECESSOR_ROUTE_REVISION = 116" in source
    assert "PREDECESSOR_GROUP_REVISION = 143" in source
    assert "DEFINITION_REVISION = 73" in source
    assert "PREDECESSOR_BINDING_REVISION = 9" in source
    assert "PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "pipeline_snapshot_schedule_definition_head" in source
    assert "pipeline_snapshot_schedule_definition_revision" in source


def test_av_replacement_uses_owner_issued_identity_and_has_no_definition_runner():
    source = SOURCE.read_text(encoding="utf-8")
    assert 'value = json.loads((AV_DIR / "create-result.json")' in source
    assert 'INSTALLATION_LABEL = "av"' in source
    assert "profile.configure(INSTALLATION_LABEL, action)" in source
    assert "run_definition" not in source
    assert isinstance(tree(), ast.Module)
