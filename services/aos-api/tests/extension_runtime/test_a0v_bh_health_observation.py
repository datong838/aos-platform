from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bh_health_observation.py"


def test_bh_health_observation_is_read_only_and_exact():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'health.INSTALLATION_ID = "7b7d4319-e639-48c9-971b-0efbfb9251ef"' in source
    assert 'health.GENERATION = "f6023b7c-ca6f-49ac-b9ff-4dcbca62745c"' in source
    assert 'health.ROUTE_REVISION = 150' in source
    assert 'health.GROUP_REVISION = 177' in source
    assert 'health.DEFINITION_REVISION = 103' in source
    assert "run_definition" not in source
