from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_au_successor_business.py"


def test_au_successor_consumes_exact_at_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'AU_ID = "eddc89f9-1e91-4e42-be4e-7d81dc941c1d"' in source
    assert 'AU_GENERATION = "01a5eb0a-f41f-40f7-ba00-b5db23a7806f"' in source
    assert 'AT_ID = "631e6d01-a5bb-4865-95eb-07d5665ed957"' in source
    assert 'DETACH = "3046e81b-fedb-4431-9493-ff79bc50820b"' in source
    assert '(old[0]["revision"], old[0]["execution_epoch"]) != (8, 4)' in source
    assert '"expectedGroupRevision": 140' in source
    assert 'row["revision"] != 113' in source
    assert 'row["cutover_group_revision"] != 140' in source
    assert '"bindingRevision": 4, "executionEpoch": 3' in source
    assert "run_definition" not in source
