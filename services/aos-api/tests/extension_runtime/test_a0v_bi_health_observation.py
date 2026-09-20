from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bi_health_observation.py"


def test_bi_health_observation_is_read_only_and_exact():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'health.INSTALLATION_ID = "8ca245a1-8420-4590-b9e4-f92256fc22ce"' in source
    assert 'health.GENERATION = "6f527122-a4a5-4056-a4e6-ca888f4b64d7"' in source
    assert 'health.ROUTE_REVISION = 153' in source
    assert 'health.GROUP_REVISION = 180' in source
    assert 'health.DEFINITION_REVISION = 106' in source
    assert "run_definition" not in source
