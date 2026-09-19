from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_aw_configuration_successor_refresh.py"


def test_aw_configuration_refresh_is_exact_and_zero_effect():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'INSTALLATION = "f94b9425-9bc4-4369-8ae3-138c50c9ab81"' in source
    assert 'GENERATION = "a92f7bb2-3d90-4d88-9632-5fc9a70bd650"' in source
    assert '"configurationId": "ad97cf60-eeb3-4938-803e-31ca8b7458f1"' in source
    assert 'expected_binding_revision=6' in source
    assert 'ConfigurationDocument.model_validate_json' in source
    assert 'previous_ref=SOURCE_CONFIG' in source
    assert 'ref["revision"] != 2' in source
    assert 'routes != 9 or attempts or in_flight or canary' in source
    assert "run_definition" not in source
