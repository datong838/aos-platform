from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_az_health_observation.py"


def test_az_health_observer_is_read_only_and_fixed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'health.INSTALLATION_ID = "40eee6d9-fb03-4657-a83e-aeb38ec4aeeb"' in source
    assert 'health.OPERATION = "e56b9d90-1396-4fa4-9c5c-3e7cc0f204b1"' in source
    assert "health.ROUTE_REVISION = 126" in source
    assert "run_definition" not in source
