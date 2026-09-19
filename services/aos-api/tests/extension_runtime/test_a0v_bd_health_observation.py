from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bd_health_observation.py"


def test_bd_health_observer_is_read_only_and_fixed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'health.INSTALLATION_ID = "c2d6ef97-30ec-4980-9421-54a899607853"' in source
    assert 'health.OPERATION = "64e80251-affc-4155-82ae-faafc9cdcaa1"' in source
    assert "health.ROUTE_REVISION = 138" in source
    assert "health.GROUP_REVISION = 165" in source
    assert "health.DEFINITION_REVISION = 91" in source
    assert "run_definition" not in source
