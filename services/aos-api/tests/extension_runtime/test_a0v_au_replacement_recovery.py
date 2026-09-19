from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "scripts/a0v_au_replacement_recovery.py"


def tree():
    return ast.parse(SOURCE.read_text(encoding="utf-8"))


def test_au_replacement_locks_exact_at_retirement_and_disabled_definition():
    source = SOURCE.read_text(encoding="utf-8")
    assert 'AT_DISABLE_OPERATION = "5d69615c-2e9f-4ad5-8725-14a9e1fefd76"' in source
    assert 'AT_DETACH_RECEIPT = "3046e81b-fedb-4431-9493-ff79bc50820b"' in source
    assert 'AT_DETACH_HASH = "sha256:dc09ee0ceb07994f37641f6fa7b9a8f2caec0229faaf58028c00a6bb83297322"' in source
    assert 'row["revision"] != 113' in source
    assert 'row["cutover_group_revision"] != 140' in source
    assert '{"revision": 73, "state": "disabled"}' in source
    assert "pipeline_snapshot_schedule_definition_head" in source
    assert "pipeline_snapshot_schedule_definition_revision" in source


def test_au_replacement_uses_owner_issued_identity_and_has_no_definition_runner():
    source = SOURCE.read_text(encoding="utf-8")
    assert 'value = json.loads((AU_DIR / "create-result.json")' in source
    assert 'profile.configure("au", action)' in source
    assert "run_definition" not in source
    assert isinstance(tree(), ast.Module)
