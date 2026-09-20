from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bn_canonical_alias_registry_repair.py"


def test_bn_repair_uses_production_alias_and_new_immutable_versions():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'repair.SOURCE_ALIAS = "a0v-canonical"' in source
    assert '("domain.ecommerce.core", "1.4.1", "1.4.2", "ecommerce_core")' in source
    assert '("platform.ecommerce.niushop", "1.23.1", "1.23.2", "ecommerce_niushop")' in source
    assert '("solution.ecommerce.growth", "1.10.1", "1.10.2", "ecommerce_growth")' in source
    assert '("solution.ecommerce.operations-base", "1.2.1", "1.2.2", None)' in source
    assert 'repair.KEY = PREVIOUS / "signing/registry-ed25519.pem"' in source
    assert "run_definition" not in source


def test_bm_failed_preparation_retirement_is_clean_never_active_uninstall():
    source = (ROOT / "scripts/a0v_bm_failed_preparation_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.INSTALLATION_ID = "370d4287-3402-40bb-b3da-d479633da7c4"' in source
    assert 'a0v-bm-failed-preparation-uninstall-v1' in source
    assert 'terminal runtime artifact alias rejection' in source
    assert "request-disable" not in source
    assert "run_definition" not in source


def test_bn_replacement_uses_exact_bl_and_canonical_patch_material():
    source = (ROOT / "scripts/a0v_bn_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc"' in source
    assert 'replacement.INSTALLATION_LABEL = "bn"' in source
    assert 'bn-canonical-alias-registry/signed-bundles' in source
    assert '"domain.ecommerce.core": "1.4.2"' in source
    assert '"solution.ecommerce.operations-base": "1.2.2"' in source
    assert 'module.TRUST_STATE = TRUST_STATE' in source
    assert 'nested.DEFAULT_CREDENTIALS = CREDENTIALS' in source
    assert "run_definition" not in source


def test_bn_registration_targets_expected_route_successor():
    source = (ROOT / "scripts/a0v_bn_successor_business.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "d89bca67-4472-4b43-b0bd-ae8a2e0459f5"' in source
    assert 'successor.PREDECESSOR_ROUTE_REVISION = 164' in source
    assert 'successor.PREDECESSOR_GROUP_REVISION = 191' in source
    assert 'successor.AU_ID = "ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc"' in source
    assert "launcher.DEFAULT_CREDENTIALS = bn_replacement.CREDENTIALS" in source
    assert "launcher.BUNDLE_ROOT = bn_replacement.replacement.BUNDLE_ROOT" in source
    assert 'launcher.TRUST_ROOTS = bn_replacement.TRUST_STATE / "signing/trust-roots.json"' in source
    assert 'os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"]' in source
    assert "priorAttemptReconciledAbsent" in source
    assert "service.read_successor_receipt(" in source
    assert "run_definition" not in source


def test_bn_registration_credential_recovery_preserves_duty_separation():
    source = (ROOT / "scripts/a0v_bn_registration_credential_recovery.py").read_text(encoding="utf-8")
    assert 'ROLE = "aos_ecommerce_registration_control"' in source
    assert 'EXPECTED_MEMBERS = {"aos_runtime", "aos_extension_maintainer"}' in source
    assert '"rolinherit": False' in source
    assert 'sql.Identifier(ROLE), sql.Literal(password)' in source
    assert '"businessWriteCount": 0' in source
    assert "run_definition" not in source


def test_bn_cutover_is_exact_group_successor():
    source = (ROOT / "scripts/a0v_bn_successor_cutover.py").read_text(encoding="utf-8")
    assert "cutover.successor = bn_successor" in source
    assert 'cutover.PREDECESSOR_GROUP_REVISION = 191' in source
    assert 'cutover.PREFIX = "a0v-qyh-clean-generation-bn-cutover-v1"' in source
    assert '"outcome": "CURRENT_AV_SUCCESSOR_REGISTERED"' in source
    assert "run_definition" not in source


def test_bn_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_bn_health_observation.py").read_text(encoding="utf-8")
    assert 'health.OPERATION = "4d4a686f-b32f-432d-a89d-dc1965cfa126"' in source
    assert "health.ROUTE_REVISION = 165" in source
    assert "health.GROUP_REVISION = 192" in source
    assert "health.DEFINITION_REVISION = 118" in source
    assert "run_definition" not in source
