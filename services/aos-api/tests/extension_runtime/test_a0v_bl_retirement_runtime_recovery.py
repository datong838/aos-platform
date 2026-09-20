from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bl_retirement_runtime_recovery.py"


def test_recovery_uses_original_disable_owner_and_exact_intent():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "RuntimeDisableService" in source
    assert "PostgresInstallationStore" in source
    assert "CurrentControlPermission" in source
    assert '"bindingRevision": 6' in source
    assert 'if_match=\'"5"\'' in source
    assert "request-disable-intent.json" in source
    assert "RuntimeDisableConsumer" in source
    assert "finish_claimed" in source
    assert "process-disable-intent.json" in source
    assert '"resendDisable": False' in source
    assert "RuntimeUninstallCleanupExecutor" in source
    assert "CleanupOnlyOciDriver" in source
    assert 'OciDriver(context="colima-aos-extension")' in source
    assert 'state != "released"' in source
    assert "ExpiredResourceRecovery" in source
    assert "confirm_released" in source
    assert "settle_committed_cleanup" in source
    assert 'operation_id = "319f1b2b-1cdf-49de-bc0c-b9779f018200"' in source
    assert '"PREPARED_RUNTIME_RELEASED"' in source
    assert "run_definition" not in source


def test_recovery_has_no_direct_database_mutation():
    source = SCRIPT.read_text(encoding="utf-8").lower()
    assert "insert into" not in source
    assert "update " not in source
    assert "delete from" not in source
