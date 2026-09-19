from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_aw_replacement_recovery.py"


def test_aw_replacement_locks_exact_av_retirement():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "5f01eda8-ca5f-4892-8510-385704ccddb2"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "badb43f6-cb04-48ae-88ac-07f09122e872"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "eed47855-2a96-4709-be2b-8283422a180a"' in source
    assert "sha256:9b60c491ad0476127c95740ab7f32276de6bb1ebeaf063326e70fe5a28f757ca" in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 119" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 146" in source
    assert "replacement.DEFINITION_REVISION = 76" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 8" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 4" in source
    assert 'replacement.INSTALLATION_LABEL = "aw"' in source
    assert "a0v-qyh-clean-aw-20260919" in source
    assert "run_definition" not in source
