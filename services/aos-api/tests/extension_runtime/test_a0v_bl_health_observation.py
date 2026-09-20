from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bl_health_observation.py"


def test_bl_health_observation_is_read_only_and_exact():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'health.INSTALLATION_ID = "ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc"' in source
    assert 'health.GENERATION = "116d12fc-93bc-4071-a973-fdc6830ea8b1"' in source
    assert 'health.ROUTE_REVISION = 162' in source
    assert 'health.GROUP_REVISION = 189' in source
    assert 'health.DEFINITION_REVISION = 115' in source
    assert "run_definition" not in source
