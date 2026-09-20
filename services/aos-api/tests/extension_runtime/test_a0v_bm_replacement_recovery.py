from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bm_replacement_recovery.py"


def test_bm_replacement_uses_exact_bl_detach():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "7e82992b-0f1b-429f-bcda-36d416ff9cdb"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "3a50db9a-2dec-4543-b37a-701a8e12ee36"' in source
    assert 'replacement.PREDECESSOR_ROUTE_REVISION = 164' in source
    assert 'replacement.PREDECESSOR_GROUP_REVISION = 191' in source
    assert 'replacement.DEFINITION_REVISION = 118' in source
    assert 'replacement.INSTALLATION_LABEL = "bm"' in source
    assert '"domain.ecommerce.core": "1.4.1"' in source
    assert '"platform.ecommerce.niushop": "1.23.1"' in source
    assert '"solution.ecommerce.growth": "1.10.1"' in source
    assert '"solution.ecommerce.operations-base": "1.2.1"' in source
    assert 'bm-trust-root-rotation' in source
    assert 'bm-runtime-credentials/runtime-host-identities.json' in source
    assert "run_definition" not in source


def test_first_installer_accepts_explicit_operations_patch_version():
    source = (ROOT / "scripts/a0v_canonical_ecommerce_first_install.py").read_text(encoding="utf-8")
    assert 'operations_version: str = "1.2.0"' in source
    assert '("solution.ecommerce.operations-base", operations_version)' in source
