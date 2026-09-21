from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_cq_configuration_successor_refresh.py"


def test_cq_configuration_refresh_is_exact_and_zero_effect():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'INSTALLATION = "fff0b0d3-bf8f-44b0-b1b7-6a2972daeb80"' in source
    assert 'GENERATION = "ae8a1005-99fb-48c5-9dfe-8f76590bc0c8"' in source
    assert '"configurationId": "85103076-e401-4624-8141-4dc8374db731"' in source
    assert "revision=252" in source
    assert "cutover_group_revision=279" in source
    assert "expected_binding_revision=6" in source
    assert "ConfigurationDocument.model_validate_json" in source
    assert "previous_ref=SOURCE_CONFIG" in source
    assert 'ref["revision"] != 2' in source
    assert "routes != 9 or attempts or in_flight or canary" in source
    assert "dispatch_configuration_refresh" not in source
    assert "run_definition" not in source
