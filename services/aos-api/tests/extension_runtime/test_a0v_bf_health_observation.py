from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bf_health_observation.py"


def test_bf_health_observation_is_read_only_and_exact():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'health.OPERATION = "ccd5456d-cbc8-4ab7-a98b-8542a627b6b3"' in source
    assert 'health.INSTALLATION_ID = "98a16beb-6342-48bd-9e12-989f3612ca00"' in source
    assert 'health.ROUTE_REVISION = 144' in source
    assert 'health.GROUP_REVISION = 171' in source
    assert 'health.DEFINITION_REVISION = 97' in source
    assert "run_definition" not in source
