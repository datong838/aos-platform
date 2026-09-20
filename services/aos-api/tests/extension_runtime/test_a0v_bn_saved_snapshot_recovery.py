from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def test_bn_pure_http_profile_disables_all_background_execution():
    source = (ROOT / "scripts/a0v_bn_product_controlled_api.py").read_text(encoding="utf-8")
    assert 'AOS_QYH_CRON_ENABLED="false"' in source
    assert 'AOS_SNAPSHOT_GROUP_WORKER_ENABLED="false"' in source
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in source
    assert "bm-runtime-credentials/runtime-host-identities.json" in source
    assert "bn-canonical-alias-registry/signed-bundles" in source
    assert "run_definition" not in source


def test_bn_saved_snapshot_recovery_uses_exact_revision_chain():
    source = (ROOT / "scripts/a0v_bn_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_DEFINITION_REVISION = 118' in source
    assert 'recovery.TRANSFERRED_DEFINITION_REVISION = 119' in source
    assert 'recovery.RECOVERY_REVISION = 39' in source
    assert 'recovery.ENABLED_DEFINITION_REVISION = 120' in source
    assert 'recovery.PAUSED_DEFINITION_REVISION = 121' in source
    assert 'recovery.PREDECESSOR_RECOVERY_STATE = "bl-saved-snapshot-recovery-v1"' in source
    assert "recovery.snapshot.baseline.setup = _setup" in source
    assert "runtime_host.DEFAULT_CREDENTIALS = bn_replacement.CREDENTIALS" in source
    assert "product_api.BUNDLE_ROOT = bn_replacement.replacement.BUNDLE_ROOT" in source
    assert 'current_preflight.TRUST_ROOTS = bn_replacement.TRUST_STATE / "signing/trust-roots.json"' in source
    assert "run_definition" not in source
