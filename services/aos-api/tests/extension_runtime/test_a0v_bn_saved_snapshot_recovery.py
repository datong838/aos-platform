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


def test_bn_released_retirement_uses_formal_detach_owner():
    source = (ROOT / "scripts/a0v_bn_released_retirement.py").read_text(encoding="utf-8")
    assert '"revision": 7, "execution_epoch": 4' in source
    assert '"revision": 9, "execution_epoch": 5' in source
    assert 'row["revision"] != 167' in source
    assert 'row["cutover_group_revision"] != 194' in source
    assert '"attempts": 0' in source
    assert "retirement.snapshot = snapshot" in source
    assert 'intent.get("resendDisable") is not False' in source
    assert '"recoveredAfterCommit": True' in source
    assert "value.TRUST_STATE = bn_replacement.TRUST_STATE" in source
    assert "module.DEFAULT_CREDENTIALS = bn_replacement.CREDENTIALS" in source
    assert "run_definition" not in source


def test_bo_replacement_uses_exact_bn_detach():
    source = (ROOT / "scripts/a0v_bo_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "d89bca67-4472-4b43-b0bd-ae8a2e0459f5"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "ff01e6a5-436a-46b1-a757-8e78b3344748"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "f581970a-fcff-403b-ad64-57c26e38831e"' in source
    assert 'replacement.PREDECESSOR_ROUTE_REVISION = 167' in source
    assert 'replacement.PREDECESSOR_GROUP_REVISION = 194' in source
    assert 'replacement.PREDECESSOR_BINDING_REVISION = 9' in source
    assert 'replacement.PREDECESSOR_EXECUTION_EPOCH = 5' in source
    assert "run_definition" not in source


def test_bo_registration_targets_exact_detached_bn():
    source = (ROOT / "scripts/a0v_bo_successor_business.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "307399a0-21bb-4d55-95b2-8b0fee238913"' in source
    assert 'successor.AU_ID = "d89bca67-4472-4b43-b0bd-ae8a2e0459f5"' in source
    assert 'successor.DETACH = "f581970a-fcff-403b-ad64-57c26e38831e"' in source
    assert "successor.PREDECESSOR_ROUTE_REVISION = 167" in source
    assert "successor.PREDECESSOR_GROUP_REVISION = 194" in source
    assert 'os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"]' in source
    assert "run_definition" not in source


def test_bo_cutover_advances_exact_bn_group_once():
    source = (ROOT / "scripts/a0v_bo_successor_cutover.py").read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "66528958-480d-4e5d-a439-5093e51b31d9"' in source
    assert "cutover.PREDECESSOR_GROUP_REVISION = 194" in source
    assert 'cutover.PREFIX = "a0v-qyh-clean-generation-bo-cutover-v1"' in source
    assert "a0v_bo_successor_business" in source
    assert "run_definition" not in source


def test_bo_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_bo_health_observation.py").read_text(encoding="utf-8")
    assert 'health.OPERATION = "878d3c80-038a-43f7-b011-61ceb8ad0ae0"' in source
    assert "health.ROUTE_REVISION = 168" in source
    assert "health.GROUP_REVISION = 195" in source
    assert "health.DEFINITION_REVISION = 118" in source
    assert "return health.snapshot()" in source
    assert "run_definition" not in source


def test_bo_pure_http_profile_disables_all_in_process_background_execution():
    source = (ROOT / "scripts/a0v_bo_product_controlled_api.py").read_text(encoding="utf-8")
    assert 'AOS_QYH_CRON_ENABLED="false"' in source
    assert 'AOS_SNAPSHOT_GROUP_WORKER_ENABLED="false"' in source
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in source
    assert "bm-runtime-credentials/runtime-host-identities.json" in source
    assert "bn-canonical-alias-registry/signed-bundles" in source
    assert "run_definition" not in source


def test_bo_saved_snapshot_recovery_uses_exact_unconsumed_revision_chain():
    source = (ROOT / "scripts/a0v_bo_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_DEFINITION_REVISION = 118' in source
    assert 'recovery.TRANSFERRED_DEFINITION_REVISION = 119' in source
    assert 'recovery.RECOVERY_REVISION = 39' in source
    assert 'recovery.ENABLED_DEFINITION_REVISION = 120' in source
    assert 'recovery.PAUSED_DEFINITION_REVISION = 121' in source
    assert 'recovery.PREDECESSOR_RECOVERY_STATE = "bl-saved-snapshot-recovery-v1"' in source
    assert "recovery.snapshot.baseline.setup = _setup" in source
    assert "runtime_host.DEFAULT_CREDENTIALS = bo_replacement.canonical.CREDENTIALS" in source
    assert "product_api.BUNDLE_ROOT = bo_replacement.replacement.BUNDLE_ROOT" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:9f81de0cdf898e3ea316c9d58ba20c95103741c1401af771b2379fe9ced22be7"' in source
    assert "recovery.transfer = transfer" in source
    assert 'or recovery_ref.get("revision") != 38' in source
    assert "run_definition" not in source


def test_bo_terminal_supervisor_allows_only_one_natural_attempt():
    source = (ROOT / "scripts/a0v_bo_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "successor.BO_ID, successor.BO_GENERATION, OPERATION_KEY" in source
    assert 'raise RuntimeError("BO attempt must be zero before supervisor starts worker")' in source
    assert '"SAFE_BLOCKED_MULTIPLE_ATTEMPTS"' in source
    assert 'parser.add_argument("--interval-seconds", type=int, default=50)' in source
    assert 'parser.add_argument("--budget-seconds", type=int, default=1800)' in source
    assert "successor.setup()" in source
    assert 'WORKER = ROOT / "scripts/a0v_bo_snapshot_product_api.py"' in source
    assert "run_definition" not in source


def test_bo_snapshot_worker_uses_exact_bo_lease_and_state():
    source = (ROOT / "scripts/a0v_bo_snapshot_product_api.py").read_text(encoding="utf-8")
    assert "successor.setup()" in source
    assert 'worker.STATE = successor.STATE.parent / "snapshot-worker"' in source
    assert 'worker.TASK = "A0V-BO-SNAPSHOT-WORKER-20260920"' in source
    assert "worker.main()" in source
    assert "run_definition" not in source


def test_bo_terminal_pause_is_exact_stop_only_recovery():
    source = (ROOT / "scripts/a0v_bo_terminal_pause_recovery.py").read_text(encoding="utf-8")
    assert '"57881020-86fe-44cc-be3e-2cd90787205e"' in source
    assert '"9d1fc481-7eb2-426f-8b0b-65627f06ec97"' in source
    assert '"attemptCount": 2' in source
    assert '"definitionRevision": 120' in source
    assert 'result["ref"]["revision"] != 121' in source
    assert "PipelineSnapshotScheduleDefinitionOwner" in source
    assert "run_definition" not in source


def test_bo_terminal_retirement_uses_exact_two_failed_attempts():
    source = (ROOT / "scripts/a0v_bo_terminal_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = successor.BO_ID" in source
    assert '"57881020-86fe-44cc-be3e-2cd90787205e", 2, "failed"' in source
    assert '"9d1fc481-7eb2-426f-8b0b-65627f06ec97", 2, "failed"' in source
    assert source.count('"RECOVERABLE_EXECUTION_EXCEPTION", "RuntimeConflict"') == 2
    assert "retirement.DEFINITION_REVISION = 121" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 168" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 170" in source
    assert "retirement.DETACHED_GROUP_REVISION = 197" in source
    assert "retirement.profile = profile" in source
    assert "a0v_ar_released_retirement" in source
    assert "run_definition" not in source


def test_released_retirement_revisions_are_injectable():
    source = (ROOT / "scripts/a0v_ar_released_retirement.py").read_text(encoding="utf-8")
    assert "DEFINITION_REVISION = 67" in source
    assert "ACTIVE_ROUTE_REVISION = 105" in source
    assert "DETACHED_ROUTE_REVISION = 107" in source
    assert '{"revision": DEFINITION_REVISION, "state": "disabled"}' in source
    assert 'row["revision"] != ACTIVE_ROUTE_REVISION' in source
    assert 'row["revision"] != DETACHED_ROUTE_REVISION' in source


def test_bp_replacement_uses_exact_bo_detach():
    source = (ROOT / "scripts/a0v_bp_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "307399a0-21bb-4d55-95b2-8b0fee238913"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "70cb9fec-1a8c-477c-bbdf-8134931ff3f6"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "01853eba-d3d7-4e2a-a5c5-a6c346e1679c"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 170" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 197" in source
    assert "replacement.DEFINITION_REVISION = 121" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 9" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "run_definition" not in source


def test_bp_registration_targets_exact_detached_bo():
    source = (ROOT / "scripts/a0v_bp_successor_business.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "17ba9792-9f24-42e4-9557-4d84547c7d97"' in source
    assert 'successor.AU_ID = "307399a0-21bb-4d55-95b2-8b0fee238913"' in source
    assert 'successor.DETACH = "01853eba-d3d7-4e2a-a5c5-a6c346e1679c"' in source
    assert "successor.PREDECESSOR_ROUTE_REVISION = 170" in source
    assert "successor.PREDECESSOR_GROUP_REVISION = 197" in source
    assert 'os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"]' in source
    assert "run_definition" not in source


def test_bp_cutover_advances_exact_bo_group_once():
    source = (ROOT / "scripts/a0v_bp_successor_cutover.py").read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "46da254e-6842-4a33-9540-e6a47065a65a"' in source
    assert "cutover.PREDECESSOR_GROUP_REVISION = 197" in source
    assert 'cutover.PREFIX = "a0v-qyh-clean-generation-bp-cutover-v1"' in source
    assert "a0v_bp_successor_business" in source
    assert "run_definition" not in source


def test_bp_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_bp_health_observation.py").read_text(encoding="utf-8")
    assert 'health.OPERATION = "4fd9f7d4-71ba-4451-8e60-1357f63b17ce"' in source
    assert "health.ROUTE_REVISION = 171" in source
    assert "health.GROUP_REVISION = 198" in source
    assert "health.DEFINITION_REVISION = 121" in source
    assert "return health.snapshot()" in source
    assert "run_definition" not in source
