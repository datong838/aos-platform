from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bk_health_observation.py"


def test_bk_health_observation_is_read_only_and_exact():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'health.INSTALLATION_ID = "8c78f903-ebd8-4589-97a0-afad76e209e0"' in source
    assert 'health.GENERATION = "9ea4ba9d-1ef8-45a6-9060-1e4f37c87038"' in source
    assert 'health.ROUTE_REVISION = 159' in source
    assert 'health.GROUP_REVISION = 186' in source
    assert 'health.DEFINITION_REVISION = 112' in source
    assert "run_definition" not in source
