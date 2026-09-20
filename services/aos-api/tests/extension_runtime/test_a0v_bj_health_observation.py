from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bj_health_observation.py"


def test_bj_health_observation_is_read_only_and_exact():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'health.INSTALLATION_ID = "2c3972b1-67c1-400d-aa63-b90de369f5de"' in source
    assert 'health.GENERATION = "8dafd4ae-d42b-4f2f-accb-b5a49e7c9a3b"' in source
    assert 'health.ROUTE_REVISION = 156' in source
    assert 'health.GROUP_REVISION = 183' in source
    assert 'health.DEFINITION_REVISION = 109' in source
    assert "run_definition" not in source
