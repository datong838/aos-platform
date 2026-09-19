from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_aw_successor_business.py"


def test_aw_successor_uses_owner_identity_and_exact_av_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'CREATE["installationId"]' in source
    assert 'STAGE["binding"]["generation"]' in source
    assert 'STAGE["staged"]["configRef"]' in source
    assert 'successor.DETACH = "eed47855-2a96-4709-be2b-8283422a180a"' in source
    assert "sha256:9b60c491ad0476127c95740ab7f32276de6bb1ebeaf063326e70fe5a28f757ca" in source
    assert "successor.PREDECESSOR_BINDING_REVISION = 8" in source
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 4" in source
    assert "successor.PREDECESSOR_ROUTE_REVISION = 119" in source
    assert "successor.PREDECESSOR_GROUP_REVISION = 146" in source
    assert "a0v-qyh-clean-generation-aw-successor-v1" in source
    assert "run_definition" not in source
