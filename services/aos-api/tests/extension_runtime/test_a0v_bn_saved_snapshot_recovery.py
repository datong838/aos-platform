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


def test_bp_pure_http_profile_disables_all_in_process_background_execution():
    source = (ROOT / "scripts/a0v_bp_product_controlled_api.py").read_text(encoding="utf-8")
    assert 'AOS_QYH_CRON_ENABLED="false"' in source
    assert 'AOS_SNAPSHOT_GROUP_WORKER_ENABLED="false"' in source
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in source
    assert "bm-runtime-credentials/runtime-host-identities.json" in source
    assert "bn-canonical-alias-registry/signed-bundles" in source
    assert "run_definition" not in source


def test_bp_saved_snapshot_recovery_uses_exact_unconsumed_revision_chain():
    source = (ROOT / "scripts/a0v_bp_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_DEFINITION_REVISION = 121' in source
    assert 'recovery.TRANSFERRED_DEFINITION_REVISION = 122' in source
    assert 'recovery.RECOVERY_REVISION = 40' in source
    assert 'recovery.ENABLED_DEFINITION_REVISION = 123' in source
    assert 'recovery.PAUSED_DEFINITION_REVISION = 124' in source
    assert 'recovery.PREDECESSOR_RECOVERY_STATE = "bo-saved-snapshot-recovery-v1"' in source
    assert "recovery.snapshot.baseline.setup = _setup" in source
    assert "runtime_host.DEFAULT_CREDENTIALS = bp_replacement.canonical.CREDENTIALS" in source
    assert "product_api.BUNDLE_ROOT = bp_replacement.replacement.BUNDLE_ROOT" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:39ca604ec957db0f8a7b20fedecd11f25e3ed8d60e3cc0feea56d6568d8cc2ec"' in source
    assert "recovery.transfer = transfer" in source
    assert 'or recovery_ref.get("revision") != 39' in source
    assert "run_definition" not in source


def test_bp_terminal_supervisor_allows_only_one_natural_attempt():
    source = (ROOT / "scripts/a0v_bp_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "successor.BP_ID, successor.BP_GENERATION, OPERATION_KEY" in source
    assert 'raise RuntimeError("BP attempt must be zero before supervisor starts worker")' in source
    assert '"SAFE_BLOCKED_MULTIPLE_ATTEMPTS"' in source
    assert 'parser.add_argument("--interval-seconds", type=int, default=50)' in source
    assert 'parser.add_argument("--budget-seconds", type=int, default=1800)' in source
    assert "successor.setup()" in source
    assert 'WORKER = ROOT / "scripts/a0v_bp_snapshot_product_api.py"' in source
    assert "result = classify(read_rows(), budget_seconds)" in source
    assert 'if worker.poll() is not None:' in source
    assert source.index("result = classify(read_rows(), budget_seconds)") < source.index(
        'raise RuntimeError(f"BP worker exited before attempt boundary: {worker.returncode}")')
    assert "run_definition" not in source


def test_bp_snapshot_worker_uses_exact_bp_lease_and_state():
    source = (ROOT / "scripts/a0v_bp_snapshot_product_api.py").read_text(encoding="utf-8")
    assert "successor.setup()" in source
    assert 'worker.STATE = successor.STATE.parent / "snapshot-worker"' in source
    assert 'worker.TASK = "A0V-BP-SNAPSHOT-WORKER-20260920"' in source
    assert "worker.main()" in source
    assert "run_definition" not in source


def test_bp_attempt_guard_freezes_exact_single_terminal_failure():
    source = (ROOT / "scripts/a0v_bp_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "051397ad-7027-4ee5-9d4c-f32374841cd9"' in source
    assert '"attemptCount": 1' in source
    assert '"state": "failed", "revision": 5' in source
    assert '"terminalErrorType": "IngressJournalConflict"' in source
    assert '"definitionRevision": 124' in source
    assert '"definitionState": "disabled"' in source
    assert '"recoveryRevision": 40' in source
    assert '"outcome": "FAILED_FREEZE_BOUNDARY"' in source
    assert "run_definition" not in source


def test_bp_terminal_retirement_uses_exact_single_failed_attempt():
    source = (ROOT / "scripts/a0v_bp_terminal_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = successor.BP_ID" in source
    assert '"051397ad-7027-4ee5-9d4c-f32374841cd9", 5, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 124" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 171" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 173" in source
    assert "retirement.DETACHED_GROUP_REVISION = 200" in source
    assert "retirement.profile = profile" in source
    assert "a0v_ar_released_retirement" in source
    assert "run_definition" not in source


def test_bq_replacement_uses_exact_bp_detach():
    source = (ROOT / "scripts/a0v_bq_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "17ba9792-9f24-42e4-9557-4d84547c7d97"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "90021097-2b72-4ecc-94dc-54dd571e1bfd"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "ae6695f9-42bf-41a3-a09d-0f3c092e4793"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 173" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 200" in source
    assert "replacement.DEFINITION_REVISION = 124" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 9" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "run_definition" not in source


def test_bq_registration_targets_exact_detached_bp():
    source = (ROOT / "scripts/a0v_bq_successor_business.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "4faaf3b7-2d10-4961-99db-5bf52b7b8a63"' in source
    assert 'successor.AU_ID = "17ba9792-9f24-42e4-9557-4d84547c7d97"' in source
    assert 'successor.DETACH = "ae6695f9-42bf-41a3-a09d-0f3c092e4793"' in source
    assert "successor.PREDECESSOR_ROUTE_REVISION = 173" in source
    assert "successor.PREDECESSOR_GROUP_REVISION = 200" in source
    assert 'os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"]' in source
    assert "run_definition" not in source


def test_bq_cutover_advances_exact_bp_group_once():
    source = (ROOT / "scripts/a0v_bq_successor_cutover.py").read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "fc19b7bd-d506-4e85-a528-a3b0ce9e6ff4"' in source
    assert "cutover.PREDECESSOR_GROUP_REVISION = 200" in source
    assert 'cutover.PREFIX = "a0v-qyh-clean-generation-bq-cutover-v1"' in source
    assert "a0v_bq_successor_business" in source
    assert "run_definition" not in source


def test_bq_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_bq_health_observation.py").read_text(encoding="utf-8")
    assert 'health.OPERATION = "8ede7aca-fcb4-47ba-9493-ea917c334fb1"' in source
    assert "health.ROUTE_REVISION = 174" in source
    assert "health.GROUP_REVISION = 201" in source
    assert "health.DEFINITION_REVISION = 124" in source
    assert "return health.snapshot()" in source
    assert "run_definition" not in source


def test_bq_saved_snapshot_profile_and_revision_chain_are_exact():
    api = (ROOT / "scripts/a0v_bq_product_controlled_api.py").read_text(encoding="utf-8")
    source = (ROOT / "scripts/a0v_bq_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'AOS_QYH_CRON_ENABLED="false"' in api
    assert 'AOS_SNAPSHOT_GROUP_WORKER_ENABLED="false"' in api
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in api
    assert 'recovery.PREDECESSOR_DEFINITION_REVISION = 124' in source
    assert 'recovery.TRANSFERRED_DEFINITION_REVISION = 125' in source
    assert 'recovery.RECOVERY_REVISION = 41' in source
    assert 'recovery.ENABLED_DEFINITION_REVISION = 126' in source
    assert 'recovery.PAUSED_DEFINITION_REVISION = 127' in source
    assert 'or recovery_ref.get("revision") != 40' in source
    assert "run_definition" not in api + source


def test_bq_released_retirement_uses_exact_pre_transfer_boundary():
    source = (ROOT / "scripts/a0v_bq_released_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = bq_successor.BQ_ID" in source
    assert "retirement.GENERATION = bq_successor.BQ_GENERATION" in source
    assert "retirement.FAILED_ATTEMPTS = ()" in source
    assert "retirement.DEFINITION_REVISION = 124" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 174" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 201" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 176" in source
    assert "retirement.DETACHED_GROUP_REVISION = 203" in source
    assert "retirement.profile = profile" in source
    assert "retirement.setup = setup" in source
    assert "a0v_ar_released_retirement" in source
    assert "run_definition" not in source


def test_br_replacement_uses_exact_bq_detach():
    source = (ROOT / "scripts/a0v_br_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "4faaf3b7-2d10-4961-99db-5bf52b7b8a63"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "126a0ab8-6fa0-464b-b97c-dfe47862db0a"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "82c3e7a5-64ad-4d4d-9cd1-d7c2c2f8fa3b"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:ae12194af3b1991fe3ba7e148d67d90a47d7213d33cb707ad7956380bdf98e4f"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 176" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 203" in source
    assert "replacement.DEFINITION_REVISION = 124" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 9" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "run_definition" not in source


def test_br_registration_targets_exact_detached_bq():
    source = (ROOT / "scripts/a0v_br_successor_business.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "fddfa0b0-158c-4271-b1ea-dc4e1e36e293"' in source
    assert 'successor.AV_GENERATION = "981d7a2d-3bbe-4cc1-a8d9-c872be0147d3"' in source
    assert 'successor.AU_ID = "4faaf3b7-2d10-4961-99db-5bf52b7b8a63"' in source
    assert 'successor.DETACH = "82c3e7a5-64ad-4d4d-9cd1-d7c2c2f8fa3b"' in source
    assert "successor.PREDECESSOR_ROUTE_REVISION = 176" in source
    assert "successor.PREDECESSOR_GROUP_REVISION = 203" in source
    assert 'os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"]' in source
    assert "run_definition" not in source


def test_br_cutover_advances_exact_bq_group_once():
    source = (ROOT / "scripts/a0v_br_successor_cutover.py").read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "3d585d56-1d8b-4211-b1d3-dfc06c96b8ca"' in source
    assert "cutover.PREDECESSOR_GROUP_REVISION = 203" in source
    assert 'cutover.PREFIX = "a0v-qyh-clean-generation-br-cutover-v1"' in source
    assert "a0v_br_successor_business" in source
    assert "run_definition" not in source


def test_br_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_br_health_observation.py").read_text(encoding="utf-8")
    assert 'health.OPERATION = "d607842f-311c-4f88-a49b-d09b66e419da"' in source
    assert "health.ROUTE_REVISION = 177" in source
    assert "health.GROUP_REVISION = 204" in source
    assert "health.DEFINITION_REVISION = 124" in source
    assert "_cache_read_only_connection()" in source
    assert "conn.read_only = True" in source
    assert "IsolationLevel.REPEATABLE_READ" in source
    assert "return health.snapshot()" in source
    assert "run_definition" not in source


def test_br_saved_snapshot_profile_and_revision_chain_are_exact():
    api = (ROOT / "scripts/a0v_br_product_controlled_api.py").read_text(encoding="utf-8")
    source = (ROOT / "scripts/a0v_br_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'AOS_QYH_CRON_ENABLED="false"' in api
    assert 'AOS_SNAPSHOT_GROUP_WORKER_ENABLED="false"' in api
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in api
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "17ba9792-9f24-42e4-9557-4d84547c7d97"' in source
    assert 'recovery.PREDECESSOR_DEFINITION_REVISION = 124' in source
    assert 'recovery.TRANSFERRED_DEFINITION_REVISION = 125' in source
    assert 'recovery.RECOVERY_REVISION = 41' in source
    assert 'recovery.ENABLED_DEFINITION_REVISION = 126' in source
    assert 'recovery.PAUSED_DEFINITION_REVISION = 127' in source
    assert 'or recovery_ref.get("revision") != 40' in source
    assert "run_definition" not in api + source


def test_br_terminal_supervisor_allows_only_one_natural_attempt():
    source = (ROOT / "scripts/a0v_br_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "successor.BR_ID, successor.BR_GENERATION, OPERATION_KEY" in source
    assert 'raise RuntimeError("BR attempt must be zero before supervisor starts worker")' in source
    assert 'TERMINAL_STATES = {"succeeded", "failed", "abandoned"}' in source
    assert 'time.sleep(interval_seconds)' in source
    assert 'os.killpg(worker.pid, signal.SIGTERM)' in source
    assert 'WORKER = ROOT / "scripts/a0v_br_snapshot_product_api.py"' in source
    assert "run_definition" not in source


def test_br_snapshot_worker_uses_exact_br_lease_and_state():
    source = (ROOT / "scripts/a0v_br_snapshot_product_api.py").read_text(encoding="utf-8")
    assert "import a0v_br_successor_business as successor" in source
    assert 'worker.TASK = "A0V-BR-SNAPSHOT-WORKER-20260920"' in source
    assert 'worker.STATE = successor.STATE.parent / "snapshot-worker"' in source
    assert "run_definition" not in source


def test_br_attempt_guard_freezes_exact_single_terminal_failure():
    source = (ROOT / "scripts/a0v_br_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "256207c9-4bc4-4c89-b00f-146f58012011"' in source
    assert '"state": "failed", "revision": 8' in source
    assert '"terminalReason": "RECOVERABLE_EXECUTION_EXCEPTION"' in source
    assert '"terminalErrorType": "IngressJournalConflict"' in source
    assert '"definitionRevision": 127, "definitionState": "disabled", "recoveryRevision": 41' in source
    assert 'AND revision=177 AND cutover_group_revision=204' in source
    assert '"attemptCount": 1' in source
    assert "run_definition" not in source


def test_br_terminal_retirement_uses_exact_single_failed_attempt():
    source = (ROOT / "scripts/a0v_br_terminal_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = successor.BR_ID" in source
    assert '"256207c9-4bc4-4c89-b00f-146f58012011", 8, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 127" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 177" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 204" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 179" in source
    assert "retirement.DETACHED_GROUP_REVISION = 206" in source
    assert "run_definition" not in source


def test_bs_replacement_uses_exact_br_detach():
    source = (ROOT / "scripts/a0v_bs_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "fddfa0b0-158c-4271-b1ea-dc4e1e36e293"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "91705b53-691b-4ebc-bab5-ba21945c9ec9"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "f4ca1d45-b002-47d2-b56a-15f6b57f7b3b"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:2a476a8b1e9f22247726c75ef5dae82eb043b339a501e7ea13b776324c6b48bc"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 179" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 206" in source
    assert "replacement.DEFINITION_REVISION = 127" in source
    assert "run_definition" not in source


def test_bs_registration_targets_exact_detached_br():
    source = (ROOT / "scripts/a0v_bs_successor_business.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "c5a95204-c379-4763-b697-b4417349d204"' in source
    assert 'successor.AV_GENERATION = "6f8bcb56-5717-4d7a-9a9e-97c1982db053"' in source
    assert 'successor.DETACH = "f4ca1d45-b002-47d2-b56a-15f6b57f7b3b"' in source
    assert 'successor.KEY = "a0v-qyh-clean-generation-bs-successor-v1"' in source
    assert "successor.PREDECESSOR_ROUTE_REVISION = 179" in source
    assert "successor.PREDECESSOR_GROUP_REVISION = 206" in source
    assert "run_definition" not in source


def test_bs_cutover_advances_exact_br_group_once():
    source = (ROOT / "scripts/a0v_bs_successor_cutover.py").read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "b193f4ac-449b-494b-a401-800d5699ce59"' in source
    assert 'cutover.PREFIX = "a0v-qyh-clean-generation-bs-cutover-v1"' in source
    assert "cutover.PREDECESSOR_GROUP_REVISION = 206" in source
    assert "a0v_bs_successor_business" in source
    assert "run_definition" not in source


def test_bs_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_bs_health_observation.py").read_text(encoding="utf-8")
    assert 'health.INSTALLATION_ID = "c5a95204-c379-4763-b697-b4417349d204"' in source
    assert "health.ROUTE_REVISION = 180" in source
    assert "health.GROUP_REVISION = 207" in source
    assert "health.DEFINITION_REVISION = 127" in source
    assert "a0v_av_health_observation" in source
    assert "_cache_read_only_connection()" in source
    assert "conn.read_only = True" in source
    assert "IsolationLevel.REPEATABLE_READ" in source
    assert "run_definition" not in source


def test_bs_uncertain_cleanup_uses_exact_resource_and_committed_cas():
    source = (ROOT / "scripts/a0v_bs_uncertain_cleanup_recovery.py").read_text(encoding="utf-8")
    assert 'OPERATION = "0587d5e6-1f14-4406-a1e4-95e8e556c583"' in source
    assert 'RESOURCE = "accb54dc-6341-4dc7-b8da-40202a102569"' in source
    assert '"status": "needs_attention", "revision": 20' in source
    assert 'failure_code": "RESOURCE_CLEANUP_UNCERTAIN"' in source
    assert source.count("with consumer_connection(connect,") == 3
    assert "expected_revision=21" in source
    assert '(OPERATION, "failed", 22)' in source
    assert "ExpiredResourceRecovery" in source
    assert "run_definition" not in source


def test_bs_released_retirement_uses_exact_cleanup_boundary():
    source = (ROOT / "scripts/a0v_bs_released_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = bs_successor.BS_ID" in source
    assert "retirement.FAILED_ATTEMPTS = ()" in source
    assert "retirement.DEFINITION_REVISION = 127" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 180" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 207" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 182" in source
    assert "retirement.DETACHED_GROUP_REVISION = 209" in source
    assert "run_definition" not in source


def test_bt_replacement_is_bound_to_exact_bs_detach_receipt():
    source = (ROOT / "scripts/a0v_bt_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "c5a95204-c379-4763-b697-b4417349d204"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "0d5bbaa8-b5b4-4e12-b4cd-13b9ac00669f"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "ddd1e074-b90d-411e-93a3-0595d6e86d8b"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:2995a8a4d8d2a74ddbde34a521de984af0afad13844303f6883befe48fe58242"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 182" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 209" in source
    assert "run_definition" not in source


def test_bt_registration_is_bound_to_exact_enabled_generation_and_detach():
    source = (ROOT / "scripts/a0v_bt_successor_business.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "b05b7f06-67a0-4ea1-bc7c-1ba2108653d5"' in source
    assert 'successor.AV_GENERATION = "2c2d4cd5-d9bd-45b4-86d9-72a979eb0a58"' in source
    assert 'successor.DETACH = "ddd1e074-b90d-411e-93a3-0595d6e86d8b"' in source
    assert "successor.PREDECESSOR_ROUTE_REVISION = 182" in source
    assert "successor.PREDECESSOR_GROUP_REVISION = 209" in source
    assert "read_successor_receipt" in source
    assert "run_definition" not in source


def test_bt_cutover_has_fixed_operation_and_group209_predecessor():
    source = (ROOT / "scripts/a0v_bt_successor_cutover.py").read_text(encoding="utf-8")
    assert 'cutover.OPERATION = "18eda226-e087-4342-bfc6-21def9226112"' in source
    assert "cutover.PREDECESSOR_GROUP_REVISION = 209" in source
    assert 'cutover.STATE = bt_successor.STATE.parent / "cutover-bt"' in source
    assert "run_definition" not in source


def test_bt_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_bt_health_observation.py").read_text(encoding="utf-8")
    assert 'health.OPERATION = "db62985a-616d-4dca-9a1b-44234d5e47f0"' in source
    assert 'health.INSTALLATION_ID = "b05b7f06-67a0-4ea1-bc7c-1ba2108653d5"' in source
    assert "health.ROUTE_REVISION = 183" in source
    assert "health.GROUP_REVISION = 210" in source
    assert "IsolationLevel.REPEATABLE_READ" in source
    assert "run_definition" not in source


def test_bt_released_retirement_uses_exact_safe_stop_boundary():
    source = (ROOT / "scripts/a0v_bt_released_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = bt_successor.BT_ID" in source
    assert "retirement.FAILED_ATTEMPTS = ()" in source
    assert "retirement.DEFINITION_REVISION = 127" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 183" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 210" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 185" in source
    assert "retirement.DETACHED_GROUP_REVISION = 212" in source
    assert "run_definition" not in source


def test_bu_replacement_is_bound_to_exact_bt_detach_receipt():
    source = (ROOT / "scripts/a0v_bu_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "b05b7f06-67a0-4ea1-bc7c-1ba2108653d5"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "84699050-9e0a-48b7-8dc3-99e2d7dbc669"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "3c4c44d3-7f5f-4829-951a-5ba5c4c37aaa"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:49271deaba3745fe1f75f7e041b058f285f6706364cda4d8afddb0315b9c5528"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 185" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 212" in source
    assert "run_definition" not in source


def test_bu_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_bu_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_bu_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "d1dcf5c2-f6ff-48b2-b6f1-fb05d17b7895"' in business
    assert 'successor.AV_GENERATION = "cb8ace71-ba8d-4e08-816b-8d6bbc0f0281"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 185" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 212" in business
    assert 'cutover.OPERATION = "ec731e19-1161-451c-8585-9c59849ea6c0"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 212" in cutover
    assert "run_definition" not in business + cutover


def test_bu_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_bu_health_observation.py").read_text(encoding="utf-8")
    assert 'health.OPERATION = "a36f4a07-d71b-4f8b-bf12-5569a5c08fba"' in source
    assert 'health.INSTALLATION_ID = "d1dcf5c2-f6ff-48b2-b6f1-fb05d17b7895"' in source
    assert "health.ROUTE_REVISION = 186" in source
    assert "health.GROUP_REVISION = 213" in source
    assert "IsolationLevel.REPEATABLE_READ" in source
    assert "run_definition" not in source


def test_bu_saved_snapshot_recovery_is_exact_and_has_no_source_read_or_manual_run():
    source = (ROOT / "scripts/a0v_bu_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "fddfa0b0-158c-4271-b1ea-dc4e1e36e293"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 127" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 128" in source
    assert "recovery.RECOVERY_REVISION = 42" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 129" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 130" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:400cf5d221f28501d763b194fb412a18a2c23c872057fe6e5f4c896a7721935d"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_bu_product_controlled_api_is_pure_http():
    source = (ROOT / "scripts/a0v_bu_product_controlled_api.py").read_text(encoding="utf-8")
    assert 'AOS_QYH_CRON_ENABLED="false"' in source
    assert 'AOS_SNAPSHOT_GROUP_WORKER_ENABLED="false"' in source
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in source
    assert "bm-runtime-credentials/runtime-host-identities.json" in source


def test_bu_worker_and_supervisor_are_single_attempt_bounded():
    worker = (ROOT / "scripts/a0v_bu_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_bu_terminal_supervisor.py").read_text(encoding="utf-8")
    assert 'worker.TASK = "A0V-BU-SNAPSHOT-WORKER-20260920"' in worker
    assert 'WORKER = ROOT / "scripts/a0v_bu_snapshot_product_api.py"' in supervisor
    assert "len(rows) != 1" in supervisor
    assert "budget_seconds: int = 1800" in supervisor
    assert 'parser.add_argument("--interval-seconds", type=int, default=50)' in supervisor
    assert "run_definition" not in worker + supervisor


def test_bu_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_bu_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "617da078-f4ef-4ad9-9ac6-bd764468fa67"' in source
    assert '"state": "failed", "revision": 4' in source
    assert '"terminalReason": "RECOVERABLE_EXECUTION_EXCEPTION"' in source
    assert '"terminalErrorType": "IngressJournalConflict"' in source
    assert '"definitionRevision": 130' in source
    assert '"definitionState": "disabled"' in source
    assert '"recoveryRevision": 42' in source
    assert "revision=186 AND cutover_group_revision=213" in source
    assert "run_definition" not in source


def test_bu_terminal_retirement_uses_exact_failed_boundary():
    source = (ROOT / "scripts/a0v_bu_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.BU_ID' in source
    assert '"617da078-f4ef-4ad9-9ac6-bd764468fa67", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 130" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 186" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 213" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 188" in source
    assert "retirement.DETACHED_GROUP_REVISION = 215" in source
    assert "run_definition" not in source


def test_bv_replacement_is_bound_to_exact_bu_detach_receipt():
    source = (ROOT / "scripts/a0v_bv_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "d1dcf5c2-f6ff-48b2-b6f1-fb05d17b7895"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "55fab898-08ac-4548-9f07-a3e1a40485e9"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "b071b45a-1e66-4898-b79c-49f1fdcd69ea"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:1eba5bd30d384de6ab165e9a617c7963fda5216775506d0341adfd1b63488163"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 188" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 215" in source
    assert "replacement.DEFINITION_REVISION = 130" in source
    assert "run_definition" not in source


def test_bv_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_bv_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_bv_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "2b1aa826-b595-40d4-aeb2-9a7ce9d33c36"' in business
    assert 'successor.AV_GENERATION = "e8a5b32b-9a29-41bf-9c7f-87c7cd96b359"' in business
    assert 'successor.DETACH = "b071b45a-1e66-4898-b79c-49f1fdcd69ea"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 188" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 215" in business
    assert 'cutover.OPERATION = "e8ab9b59-d00e-43d5-9eef-2e3e0da06a37"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 215" in cutover
    assert "run_definition" not in business + cutover


def test_bv_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_bv_health_observation.py").read_text(encoding="utf-8")
    assert 'health.OPERATION = "d5764616-1ee0-4cd8-b7a6-8d52350a6d77"' in source
    assert 'health.INSTALLATION_ID = "2b1aa826-b595-40d4-aeb2-9a7ce9d33c36"' in source
    assert "health.ROUTE_REVISION = 189" in source
    assert "health.GROUP_REVISION = 216" in source
    assert "health.DEFINITION_REVISION = 130" in source
    assert "IsolationLevel.REPEATABLE_READ" in source
    assert "run_definition" not in source


def test_bv_saved_snapshot_recovery_is_exact_and_has_no_source_read_or_manual_run():
    source = (ROOT / "scripts/a0v_bv_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "d1dcf5c2-f6ff-48b2-b6f1-fb05d17b7895"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 130" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 131" in source
    assert "recovery.RECOVERY_REVISION = 43" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 132" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 133" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:2f137e718e768aa98116af8dfa8c28a5eb66d2f3270fe8ac4c1f87b16d7cd963"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_bv_product_controlled_api_is_pure_http():
    source = (ROOT / "scripts/a0v_bv_product_controlled_api.py").read_text(encoding="utf-8")
    assert 'AOS_QYH_CRON_ENABLED="false"' in source
    assert 'AOS_SNAPSHOT_GROUP_WORKER_ENABLED="false"' in source
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in source
    assert "bm-runtime-credentials/runtime-host-identities.json" in source


def test_bv_worker_and_supervisor_are_single_attempt_bounded():
    worker = (ROOT / "scripts/a0v_bv_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_bv_terminal_supervisor.py").read_text(encoding="utf-8")
    assert 'worker.TASK = "A0V-BV-SNAPSHOT-WORKER-20260920"' in worker
    assert 'WORKER = ROOT / "scripts/a0v_bv_snapshot_product_api.py"' in supervisor
    assert "len(rows) != 1" in supervisor
    assert "budget_seconds: int = 1800" in supervisor
    assert 'parser.add_argument("--interval-seconds", type=int, default=50)' in supervisor
    assert "run_definition" not in worker + supervisor


def test_bv_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_bv_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "3afcfcae-b78c-4d15-8c64-4ec4e53325f3"' in source
    assert '"state": "failed", "revision": 4' in source
    assert '"terminalReason": "RECOVERABLE_EXECUTION_EXCEPTION"' in source
    assert '"terminalErrorType": "IngressJournalConflict"' in source
    assert '"definitionRevision": 132' in source
    assert '"definitionState": "enabled"' in source
    assert '"recoveryRevision": 43' in source
    assert "revision=189 AND cutover_group_revision=216" in source
    assert "run_definition" not in source


def test_bv_terminal_retirement_uses_exact_failed_boundary():
    source = (ROOT / "scripts/a0v_bv_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.BV_ID' in source
    assert '"3afcfcae-b78c-4d15-8c64-4ec4e53325f3", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 133" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 189" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 216" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 191" in source
    assert "retirement.DETACHED_GROUP_REVISION = 218" in source
    assert "run_definition" not in source


def test_bw_replacement_is_bound_to_exact_bv_detach_receipt():
    source = (ROOT / "scripts/a0v_bw_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "2b1aa826-b595-40d4-aeb2-9a7ce9d33c36"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "abea8903-916f-4d60-ba24-3453aeb4e8a9"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "76145710-3ec6-4271-a8b7-248e045645f7"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:dc20911dba0fe1792b1a881f215109d8bf6f4db2754bdf12d3cc3fdab0e58608"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 191" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 218" in source
    assert "replacement.DEFINITION_REVISION = 133" in source
    assert "run_definition" not in source


def test_bw_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_bw_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_bw_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "9b6e1277-a0a2-447d-9062-a98adfed3f22"' in business
    assert 'successor.AV_GENERATION = "62cf014b-9ce5-4512-8a34-b55a79e053c3"' in business
    assert 'successor.DETACH = "76145710-3ec6-4271-a8b7-248e045645f7"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 191" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 218" in business
    assert 'cutover.OPERATION = "8fb2907d-0142-409d-b725-19aa53487f3d"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 218" in cutover
    assert "run_definition" not in business + cutover


def test_bw_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_bw_health_observation.py").read_text(encoding="utf-8")
    assert 'health.OPERATION = "7ae84086-f149-44ac-969a-9fca54d17243"' in source
    assert 'health.INSTALLATION_ID = "9b6e1277-a0a2-447d-9062-a98adfed3f22"' in source
    assert "health.ROUTE_REVISION = 192" in source
    assert "health.GROUP_REVISION = 219" in source
    assert "health.DEFINITION_REVISION = 133" in source
    assert "IsolationLevel.REPEATABLE_READ" in source
    assert "run_definition" not in source


def test_bw_saved_snapshot_recovery_is_exact_and_has_no_source_read_or_manual_run():
    source = (ROOT / "scripts/a0v_bw_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "2b1aa826-b595-40d4-aeb2-9a7ce9d33c36"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 133" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 134" in source
    assert "recovery.RECOVERY_REVISION = 44" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 135" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 136" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:4a14bb3109516487c5ede4ee27a131f0c27043ce6daed1e880fcd1222b303625"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_bw_product_controlled_api_is_pure_http():
    source = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    assert 'AOS_QYH_CRON_ENABLED="false"' in source
    assert 'AOS_SNAPSHOT_GROUP_WORKER_ENABLED="false"' in source
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in source
    assert "bm-runtime-credentials/runtime-host-identities.json" in source


def test_bw_worker_and_supervisor_are_single_attempt_bounded():
    worker = (ROOT / "scripts/a0v_bw_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_bw_terminal_supervisor.py").read_text(encoding="utf-8")
    assert 'worker.TASK = "A0V-BW-SNAPSHOT-WORKER-20260921"' in worker
    assert 'WORKER = ROOT / "scripts/a0v_bw_snapshot_product_api.py"' in supervisor
    assert "len(rows) != 1" in supervisor
    assert "budget_seconds: int = 1800" in supervisor
    assert 'parser.add_argument("--interval-seconds", type=int, default=50)' in supervisor
    assert "run_definition" not in worker + supervisor


def test_bw_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_bw_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "4e3846d8-28b2-4c50-934b-8383df598956"' in source
    assert '"state": "failed", "revision": 4' in source
    assert '"terminalReason": "RECOVERABLE_EXECUTION_EXCEPTION"' in source
    assert '"terminalErrorType": "IngressJournalConflict"' in source
    assert '"definitionRevision": 135' in source
    assert '"definitionState": "enabled"' in source
    assert '"recoveryRevision": 44' in source
    assert "revision=192 AND cutover_group_revision=219" in source
    assert "run_definition" not in source


def test_bw_terminal_retirement_uses_exact_failed_boundary():
    source = (ROOT / "scripts/a0v_bw_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.BW_ID' in source
    assert '"4e3846d8-28b2-4c50-934b-8383df598956", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 136" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 192" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 219" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 194" in source
    assert "retirement.DETACHED_GROUP_REVISION = 221" in source
    assert "run_definition" not in source


def test_bx_replacement_is_bound_to_exact_bw_detach_receipt():
    source = (ROOT / "scripts/a0v_bx_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "9b6e1277-a0a2-447d-9062-a98adfed3f22"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "08730e81-28b4-4931-9670-9056259a69ff"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "d3ca6ecb-5fea-4dda-8a30-3ac9f5ce047c"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:e1365bbc1f87d42997df4c04b5167d75895de232e69f81f9412e4ffaf9cebb5e"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 194" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 221" in source
    assert "replacement.DEFINITION_REVISION = 136" in source
    assert "run_definition" not in source


def test_bx_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_bx_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_bx_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "45db7b1e-6463-40f2-bf3c-c4e64ce3fd78"' in business
    assert 'successor.AV_GENERATION = "9beb5c99-aba7-4bec-9a10-4f98415aed2f"' in business
    assert 'successor.DETACH = "d3ca6ecb-5fea-4dda-8a30-3ac9f5ce047c"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 194" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 221" in business
    assert 'cutover.OPERATION = "b3c173dc-ea28-41a8-b02c-702ac71ac456"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 221" in cutover
    assert "run_definition" not in business + cutover


def test_bx_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'health.OPERATION = "d3f509a2-0891-4348-b659-978694955721"' in source
    assert 'health.INSTALLATION_ID = "45db7b1e-6463-40f2-bf3c-c4e64ce3fd78"' in source
    assert "health.ROUTE_REVISION = 195" in source
    assert "health.GROUP_REVISION = 222" in source
    assert "health.DEFINITION_REVISION = 136" in source
    assert "IsolationLevel.REPEATABLE_READ" in source
    assert "run_definition" not in source


def test_bx_saved_snapshot_recovery_is_exact_and_has_no_source_read_or_manual_run():
    source = (ROOT / "scripts/a0v_bx_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "9b6e1277-a0a2-447d-9062-a98adfed3f22"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 136" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 137" in source
    assert "recovery.RECOVERY_REVISION = 45" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 138" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 139" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:f7517614d7a73f7d3cb3c8e9e55ee5db995c95841147ecd2edcb91817fca64fe"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_bx_product_controlled_api_is_pure_http():
    source = (ROOT / "scripts/a0v_bx_product_controlled_api.py").read_text(encoding="utf-8")
    inherited = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in source
    assert 'AOS_QYH_CRON_ENABLED="false"' in inherited
    assert 'AOS_SNAPSHOT_GROUP_WORKER_ENABLED="false"' in inherited
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in inherited


def test_bx_worker_and_supervisor_are_single_attempt_bounded():
    worker = (ROOT / "scripts/a0v_bx_snapshot_product_api.py").read_text(encoding="utf-8")
    wrapper = (ROOT / "scripts/a0v_bx_terminal_supervisor.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bw_terminal_supervisor.py").read_text(encoding="utf-8")
    assert 'worker.TASK = "A0V-BX-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_bx_snapshot_product_api.py"' in wrapper
    assert "len(rows) != 1" in shared
    assert "budget_seconds: int = 1800" in shared
    assert 'parser.add_argument("--interval-seconds", type=int, default=50)' in shared


def test_bx_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_bx_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "dedb3bf6-46ef-4b25-9733-1197ea043d26"' in source
    assert '"state": "failed", "revision": 4' in source
    assert '"terminalReason": "RECOVERABLE_EXECUTION_EXCEPTION"' in source
    assert '"terminalErrorType": "IngressJournalConflict"' in source
    assert '"definitionRevision": 138' in source
    assert '"definitionState": "enabled"' in source
    assert '"recoveryRevision": 45' in source
    assert "revision=195 AND cutover_group_revision=222" in source
    assert "run_definition" not in source


def test_bx_terminal_retirement_uses_exact_failed_boundary():
    source = (ROOT / "scripts/a0v_bx_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.BX_ID' in source
    assert '"dedb3bf6-46ef-4b25-9733-1197ea043d26", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 139" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 195" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 222" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 197" in source
    assert "retirement.DETACHED_GROUP_REVISION = 224" in source
    assert "run_definition" not in source


def test_by_replacement_is_bound_to_exact_bx_detach_receipt():
    source = (ROOT / "scripts/a0v_by_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "45db7b1e-6463-40f2-bf3c-c4e64ce3fd78"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "05d32449-7543-4136-afec-9ce7c78c7365"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "608d36a3-198b-46e2-bc5b-d653e44d44c8"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:1862820a36540eb75b301673e8c5e4553cd1c2f05facf602a35dda4c20754e9c"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 197" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 224" in source
    assert "replacement.DEFINITION_REVISION = 139" in source
    assert "run_definition" not in source


def test_by_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_by_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_by_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "ed64db1a-45eb-442e-8f1b-49ed899731dc"' in business
    assert 'successor.AV_GENERATION = "01f99334-0515-4c73-b442-a293709b3cc2"' in business
    assert 'successor.DETACH = "608d36a3-198b-46e2-bc5b-d653e44d44c8"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 197" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 224" in business
    assert 'cutover.OPERATION = "335da3b8-6101-4f42-9235-0623b9dda80c"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 224" in cutover
    assert "run_definition" not in business + cutover


def test_by_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_by_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "5e67db87-80a8-40cc-8a55-38e292f4f7a4"' in source
    assert 'observer.health.INSTALLATION_ID = "ed64db1a-45eb-442e-8f1b-49ed899731dc"' in source
    assert "observer.health.ROUTE_REVISION = 198" in source
    assert "observer.health.GROUP_REVISION = 225" in source
    assert "observer.health.DEFINITION_REVISION = 139" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_by_saved_snapshot_recovery_is_exact_and_has_no_source_read_or_manual_run():
    source = (ROOT / "scripts/a0v_by_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "45db7b1e-6463-40f2-bf3c-c4e64ce3fd78"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 139" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 140" in source
    assert "recovery.RECOVERY_REVISION = 46" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 141" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 142" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:f00d142e1b579f6452bd7aa57ffdde273454ce2a4ed6a8cf6fe564f1ff0463da"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_by_product_controlled_api_is_pure_http():
    source = (ROOT / "scripts/a0v_by_product_controlled_api.py").read_text(encoding="utf-8")
    inherited = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in source
    assert 'AOS_QYH_CRON_ENABLED="false"' in inherited
    assert 'AOS_SNAPSHOT_GROUP_WORKER_ENABLED="false"' in inherited
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in inherited


def test_by_worker_and_supervisor_are_single_attempt_bounded():
    worker = (ROOT / "scripts/a0v_by_snapshot_product_api.py").read_text(encoding="utf-8")
    wrapper = (ROOT / "scripts/a0v_by_terminal_supervisor.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bw_terminal_supervisor.py").read_text(encoding="utf-8")
    assert 'worker.TASK = "A0V-BY-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_by_snapshot_product_api.py"' in wrapper
    assert "len(rows) != 1" in shared
    assert "budget_seconds: int = 1800" in shared
    assert 'parser.add_argument("--interval-seconds", type=int, default=50)' in shared
    assert "run_definition" not in worker + wrapper + shared


def test_by_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_by_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "72876c75-a853-488a-b1e6-4c334b635f91"' in source
    assert '"state": "failed", "revision": 4' in source
    assert '"terminalReason": "RECOVERABLE_EXECUTION_EXCEPTION"' in source
    assert '"terminalErrorType": "IngressJournalConflict"' in source
    assert '"definitionRevision": 141' in source
    assert '"definitionState": "enabled"' in source
    assert '"recoveryRevision": 46' in source
    assert "revision=198 AND cutover_group_revision=225" in source
    assert "run_definition" not in source


def test_by_terminal_retirement_uses_exact_failed_boundary():
    source = (ROOT / "scripts/a0v_by_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.BY_ID' in source
    assert '("72876c75-a853-488a-b1e6-4c334b635f91", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 142" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 198" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 225" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 200" in source
    assert "retirement.DETACHED_GROUP_REVISION = 227" in source
    assert "run_definition" not in source


def test_bz_replacement_is_bound_to_exact_by_detach_receipt():
    source = (ROOT / "scripts/a0v_bz_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "ed64db1a-45eb-442e-8f1b-49ed899731dc"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "53104614-eeaf-4c87-a5fa-97f0e518f207"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "476431d3-9cb4-4e5f-bd4b-02ac2c9fd978"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:d65a5f35ed1e32e2db5e71e93e2a201eff195fe8e0ce6a859cceee468da3dbcb"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 200" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 227" in source
    assert "replacement.DEFINITION_REVISION = 142" in source
    assert "run_definition" not in source


def test_bz_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_bz_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_bz_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "9b30837c-da4d-4cfd-b438-de40aa5e3d7a"' in business
    assert 'successor.AV_GENERATION = "6f1e6e77-24aa-4052-9102-88e4a432fe55"' in business
    assert 'successor.DETACH = "476431d3-9cb4-4e5f-bd4b-02ac2c9fd978"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 200" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 227" in business
    assert 'cutover.OPERATION = "76130027-8f29-4eaf-bd2f-ca21863b13e1"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 227" in cutover
    assert "run_definition" not in business + cutover


def test_bz_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_bz_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "71d642ec-f53a-46f2-94b7-9500babfc594"' in source
    assert 'observer.health.INSTALLATION_ID = "9b30837c-da4d-4cfd-b438-de40aa5e3d7a"' in source
    assert "observer.health.ROUTE_REVISION = 201" in source
    assert "observer.health.GROUP_REVISION = 228" in source
    assert "observer.health.DEFINITION_REVISION = 142" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_bz_saved_snapshot_recovery_is_exact_and_has_no_source_read_or_manual_run():
    source = (ROOT / "scripts/a0v_bz_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "ed64db1a-45eb-442e-8f1b-49ed899731dc"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 142" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 143" in source
    assert "recovery.RECOVERY_REVISION = 47" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 144" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 145" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:a0e1a232f699d30d97c95cf7143665c6976033b6cf011b55ff783e20bc586142"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_bz_product_controlled_api_is_pure_http():
    source = (ROOT / "scripts/a0v_bz_product_controlled_api.py").read_text(encoding="utf-8")
    inherited = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in source
    assert 'AOS_QYH_CRON_ENABLED="false"' in inherited
    assert 'AOS_SNAPSHOT_GROUP_WORKER_ENABLED="false"' in inherited
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in inherited


def test_bz_worker_and_supervisor_are_single_attempt_bounded():
    worker = (ROOT / "scripts/a0v_bz_snapshot_product_api.py").read_text(encoding="utf-8")
    wrapper = (ROOT / "scripts/a0v_bz_terminal_supervisor.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bw_terminal_supervisor.py").read_text(encoding="utf-8")
    assert 'worker.TASK = "A0V-BZ-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_bz_snapshot_product_api.py"' in wrapper
    assert "len(rows) != 1" in shared
    assert "budget_seconds: int = 1800" in shared
    assert 'parser.add_argument("--interval-seconds", type=int, default=50)' in shared
    assert "run_definition" not in worker + wrapper + shared


def test_bz_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_bz_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "b7044a35-43f8-4089-ba79-4da3d92cbf64"' in source
    assert '"state": "failed", "revision": 4' in source
    assert '"terminalReason": "RECOVERABLE_EXECUTION_EXCEPTION"' in source
    assert '"terminalErrorType": "IngressJournalConflict"' in source
    assert '"definitionRevision": 144' in source
    assert '"definitionState": "enabled"' in source
    assert '"recoveryRevision": 47' in source
    assert "revision=201 AND cutover_group_revision=228" in source
    assert "run_definition" not in source


def test_bz_terminal_retirement_uses_exact_failed_boundary():
    source = (ROOT / "scripts/a0v_bz_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.BZ_ID' in source
    assert '("b7044a35-43f8-4089-ba79-4da3d92cbf64", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 145" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 201" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 228" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 203" in source
    assert "retirement.DETACHED_GROUP_REVISION = 230" in source
    assert "run_definition" not in source


def test_ca_replacement_is_bound_to_exact_bz_detach_receipt():
    source = (ROOT / "scripts/a0v_ca_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "9b30837c-da4d-4cfd-b438-de40aa5e3d7a"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "447af99f-fbb2-4142-971d-e5458a90b468"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "a5ab50b1-aa8a-4418-9ed9-59a454d9055d"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:3f234f4c5d965b0b824383ff20f980c2f4ed2555c0aab59aac037289b4bfd9eb"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 203" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 230" in source
    assert "replacement.DEFINITION_REVISION = 145" in source
    assert "run_definition" not in source


def test_ca_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_ca_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_ca_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "0d834ab1-fd2b-4dbc-b9a5-0f0dee712647"' in business
    assert 'successor.AV_GENERATION = "1f18a077-12c6-4242-982a-0c3fa1159540"' in business
    assert 'successor.DETACH = "a5ab50b1-aa8a-4418-9ed9-59a454d9055d"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 203" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 230" in business
    assert 'cutover.OPERATION = "551a9424-2d4c-4d0e-88e1-151bb85effd0"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 230" in cutover
    assert "run_definition" not in business + cutover


def test_ca_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_ca_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "69cda7b1-dd65-4fee-b3c1-30225a7a8f3f"' in source
    assert 'observer.health.INSTALLATION_ID = "0d834ab1-fd2b-4dbc-b9a5-0f0dee712647"' in source
    assert "observer.health.ROUTE_REVISION = 204" in source
    assert "observer.health.GROUP_REVISION = 231" in source
    assert "observer.health.DEFINITION_REVISION = 145" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_ca_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_ca_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CA_ID' in source
    assert '("4a3ca4e5-db9f-47a0-a283-2adf23d25e84", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 148" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 204" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 231" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 206" in source
    assert "retirement.DETACHED_GROUP_REVISION = 233" in source
    assert "run_definition" not in source


def test_cb_replacement_is_bound_to_exact_ca_detach_receipt():
    source = (ROOT / "scripts/a0v_cb_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "0d834ab1-fd2b-4dbc-b9a5-0f0dee712647"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "077c473a-dd7c-463b-87d3-eafb228cfbc5"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "bfffc7e7-5606-4101-9b5e-bc729ddb26ef"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:f4178b7c27dc9addc0fe17a13f446302af66d291960cd1c7a8aae6aab98554ce"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 206" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 233" in source
    assert "replacement.DEFINITION_REVISION = 148" in source
    assert "run_definition" not in source


def test_cb_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cb_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cb_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "3d6df614-5a05-4c6f-823e-688d81e84096"' in business
    assert 'successor.AV_GENERATION = "0cceac8c-c831-4b3f-92c3-fc35240c5414"' in business
    assert 'successor.DETACH = "bfffc7e7-5606-4101-9b5e-bc729ddb26ef"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 206" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 233" in business
    assert 'cutover.OPERATION = "8da61041-939b-4cb9-a1e9-fbc8ac87effd"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 233" in cutover
    assert "run_definition" not in business + cutover


def test_cb_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cb_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "c2645b92-40b0-41e4-a383-d76bdc772017"' in source
    assert 'observer.health.INSTALLATION_ID = "3d6df614-5a05-4c6f-823e-688d81e84096"' in source
    assert "observer.health.ROUTE_REVISION = 207" in source
    assert "observer.health.GROUP_REVISION = 234" in source
    assert "observer.health.DEFINITION_REVISION = 148" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cb_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cb_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CB_ID' in source
    assert '("727af369-a8ce-4500-86a7-1cf412a42cb3", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 151" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 207" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 234" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 209" in source
    assert "retirement.DETACHED_GROUP_REVISION = 236" in source
    assert "run_definition" not in source


def test_cc_replacement_is_bound_to_exact_cb_detach_receipt():
    source = (ROOT / "scripts/a0v_cc_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "3d6df614-5a05-4c6f-823e-688d81e84096"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "6695a5a7-e5e6-4662-ad06-9495f9ed3e9a"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "087eed56-f46c-4a9b-bc57-ba24e2e78d04"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:ab3661056826d5a9998c8ba55d278317429fcb9286b7efa65fca467c2615be49"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 209" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 236" in source
    assert "replacement.DEFINITION_REVISION = 151" in source
    assert "run_definition" not in source


def test_cc_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cc_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cc_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "03942567-0f78-4530-b9dd-634bec59c780"' in business
    assert 'successor.AV_GENERATION = "c1ffee4f-c13b-4d1a-93d2-c3b35bd66ca2"' in business
    assert 'successor.DETACH = "087eed56-f46c-4a9b-bc57-ba24e2e78d04"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 209" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 236" in business
    assert 'cutover.OPERATION = "7cd9744d-fdee-46a9-b152-1bfa6129c77d"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 236" in cutover
    assert "run_definition" not in business + cutover


def test_cc_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cc_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "d3bcdc60-c9b8-4afa-84d8-fe9441abafc1"' in source
    assert 'observer.health.INSTALLATION_ID = "03942567-0f78-4530-b9dd-634bec59c780"' in source
    assert "observer.health.ROUTE_REVISION = 210" in source
    assert "observer.health.GROUP_REVISION = 237" in source
    assert "observer.health.DEFINITION_REVISION = 151" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_ca_saved_snapshot_recovery_is_exact_and_has_no_source_read_or_manual_run():
    source = (ROOT / "scripts/a0v_ca_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "9b30837c-da4d-4cfd-b438-de40aa5e3d7a"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 145" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 146" in source
    assert "recovery.RECOVERY_REVISION = 48" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 147" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 148" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:76faf4a8280a9d078e510ec3ddba0dd03048f4e0ea7689b8695652791f2002ee"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_ca_product_controlled_api_is_pure_http():
    source = (ROOT / "scripts/a0v_ca_product_controlled_api.py").read_text(encoding="utf-8")
    inherited = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in source
    assert 'AOS_QYH_CRON_ENABLED="false"' in inherited
    assert 'AOS_SNAPSHOT_GROUP_WORKER_ENABLED="false"' in inherited
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in inherited


def test_ca_worker_and_supervisor_are_single_attempt_bounded():
    worker = (ROOT / "scripts/a0v_ca_snapshot_product_api.py").read_text(encoding="utf-8")
    wrapper = (ROOT / "scripts/a0v_ca_terminal_supervisor.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bw_terminal_supervisor.py").read_text(encoding="utf-8")
    assert 'worker.TASK = "A0V-CA-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_ca_snapshot_product_api.py"' in wrapper
    assert "len(rows) != 1" in shared
    assert "budget_seconds: int = 1800" in shared
    assert 'parser.add_argument("--interval-seconds", type=int, default=50)' in shared


def test_cb_saved_snapshot_recovery_is_exact_and_has_no_source_read_or_manual_run():
    source = (ROOT / "scripts/a0v_cb_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "0d834ab1-fd2b-4dbc-b9a5-0f0dee712647"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 148" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 149" in source
    assert "recovery.RECOVERY_REVISION = 49" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 150" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 151" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:d6549653845e2e3bad2766bc8dbbdf5b43ff9497efc72e455d4d5fa75b25e728"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cb_product_controlled_api_is_pure_http():
    source = (ROOT / "scripts/a0v_cb_product_controlled_api.py").read_text(encoding="utf-8")
    inherited = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in source
    assert 'AOS_QYH_CRON_ENABLED="false"' in inherited
    assert 'AOS_SNAPSHOT_GROUP_WORKER_ENABLED="false"' in inherited
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in inherited


def test_cb_worker_and_supervisor_are_single_attempt_bounded():
    worker = (ROOT / "scripts/a0v_cb_snapshot_product_api.py").read_text(encoding="utf-8")
    wrapper = (ROOT / "scripts/a0v_cb_terminal_supervisor.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bw_terminal_supervisor.py").read_text(encoding="utf-8")
    guard = (ROOT / "scripts/a0v_cb_attempt_guard.py").read_text(encoding="utf-8")
    assert 'worker.TASK = "A0V-CB-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cb_snapshot_product_api.py"' in wrapper
    assert 'ATTEMPT_ID = "727af369-a8ce-4500-86a7-1cf412a42cb3"' in guard
    assert '"definitionRevision": 150' in guard
    assert '"recoveryRevision": 49' in guard
    assert "revision=207 AND cutover_group_revision=234" in guard
    assert "len(rows) != 1" in shared
    assert "budget_seconds: int = 1800" in shared
    assert 'parser.add_argument("--interval-seconds", type=int, default=50)' in shared
    assert "run_definition" not in worker + wrapper + guard


def test_cc_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_cc_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 151" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 152" in source
    assert "recovery.RECOVERY_REVISION = 50" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 153" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 154" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:6a5673ae858453ca9a525d0759bf29b63c681f9f07eb1aa07d347fd7d116bf5b"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cc_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_cc_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_cc_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_cc_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CC-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cc_snapshot_product_api.py"' in supervisor


def test_cc_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_cc_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "74ee33d8-b0d4-444a-9c01-ba31e9358552"' in source
    assert 'facts.get("definitionRevision") != 153' in source
    assert 'facts.get("recoveryRevision") != 50' in source
    assert "revision=210 AND cutover_group_revision=237" in source
    assert "run_definition" not in source


def test_ca_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_ca_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "4a3ca4e5-db9f-47a0-a283-2adf23d25e84"' in source
    assert '"state": "failed", "revision": 4' in source
    assert '"terminalReason": "RECOVERABLE_EXECUTION_EXCEPTION"' in source
    assert '"terminalErrorType": "IngressJournalConflict"' in source
    assert '"definitionRevision": 147' in source
    assert '"definitionState": "enabled"' in source
    assert '"recoveryRevision": 48' in source
    assert "revision=204 AND cutover_group_revision=231" in source
    assert "run_definition" not in source


def test_cc_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cc_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CC_ID' in source
    assert '("74ee33d8-b0d4-444a-9c01-ba31e9358552", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 154" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 210" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 237" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 212" in source
    assert "retirement.DETACHED_GROUP_REVISION = 239" in source
    assert "run_definition" not in source


def test_cd_replacement_is_bound_to_exact_cc_detach_receipt():
    source = (ROOT / "scripts/a0v_cd_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "03942567-0f78-4530-b9dd-634bec59c780"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "9cf43145-2578-4815-9d14-7ac7430c6327"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "af7f0b34-1279-4ca7-972b-ef0e31fd53b3"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:848870b0fd047ebf70beb0361ba99e9e4b72375138d66b2df8aeda9ee6c11ea3"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 212" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 239" in source
    assert "replacement.DEFINITION_REVISION = 154" in source
    assert "run_definition" not in source


def test_cd_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cd_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cd_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "01b41c17-fce2-4bcf-8d9e-a48d2d4bf743"' in business
    assert 'successor.AV_GENERATION = "22639b06-1211-424d-9f64-696822e0add4"' in business
    assert 'successor.DETACH = "af7f0b34-1279-4ca7-972b-ef0e31fd53b3"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 212" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 239" in business
    assert 'cutover.OPERATION = "71d85398-64db-4cfe-8df6-b5f83fdc7ebb"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 239" in cutover
    assert "run_definition" not in business + cutover


def test_cd_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cd_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "0450e182-c811-4282-bccc-203a918a9561"' in source
    assert 'observer.health.INSTALLATION_ID = "01b41c17-fce2-4bcf-8d9e-a48d2d4bf743"' in source
    assert "observer.health.ROUTE_REVISION = 213" in source
    assert "observer.health.GROUP_REVISION = 240" in source
    assert "observer.health.DEFINITION_REVISION = 154" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cd_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_cd_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "03942567-0f78-4530-b9dd-634bec59c780"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 154" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 155" in source
    assert "recovery.RECOVERY_REVISION = 51" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 156" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 157" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:bd94a859c10729c3b988c714a29441c823dcaab85f33c005f69d7aecdd25cad8"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cd_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_cd_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_cd_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_cd_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CD-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cd_snapshot_product_api.py"' in supervisor


def test_cd_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_cd_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "3eae682d-fddb-4b3b-a7b0-da0eb91152d2"' in source
    assert 'facts.get("definitionRevision") != 156' in source
    assert 'facts.get("recoveryRevision") != 51' in source
    assert "revision=213 AND cutover_group_revision=240" in source
    assert "run_definition" not in source


def test_cd_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cd_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CD_ID' in source
    assert '("3eae682d-fddb-4b3b-a7b0-da0eb91152d2", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 157" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 213" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 240" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 215" in source
    assert "retirement.DETACHED_GROUP_REVISION = 242" in source
    assert "run_definition" not in source


def test_ce_replacement_is_bound_to_exact_cd_detach_receipt():
    source = (ROOT / "scripts/a0v_ce_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "01b41c17-fce2-4bcf-8d9e-a48d2d4bf743"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "858ed397-2cc6-40dd-b312-3faf129cb0c1"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "b1d1dc98-268c-484c-a0f6-25502b4e8193"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:5f250085b837c6e59cba62e55de38e59785dc06a3ec63c384158aec9148df75d"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 215" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 242" in source
    assert "replacement.DEFINITION_REVISION = 157" in source
    assert "run_definition" not in source


def test_ce_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_ce_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_ce_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "29d1b06d-3baa-4476-9cf8-5ea345d134c7"' in business
    assert 'successor.AV_GENERATION = "e51d0010-d57f-4f5c-8f7e-7a1d732bebf7"' in business
    assert 'successor.DETACH = "b1d1dc98-268c-484c-a0f6-25502b4e8193"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 215" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 242" in business
    assert 'cutover.OPERATION = "024169d1-9a17-4530-a745-33aac90053ac"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 242" in cutover
    assert "run_definition" not in business + cutover


def test_ce_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_ce_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "706dfb14-3c55-472e-9d69-ea49866727ad"' in source
    assert 'observer.health.INSTALLATION_ID = "29d1b06d-3baa-4476-9cf8-5ea345d134c7"' in source
    assert "observer.health.ROUTE_REVISION = 216" in source
    assert "observer.health.GROUP_REVISION = 243" in source
    assert "observer.health.DEFINITION_REVISION = 157" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_ce_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_ce_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "01b41c17-fce2-4bcf-8d9e-a48d2d4bf743"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 157" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 158" in source
    assert "recovery.RECOVERY_REVISION = 52" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 159" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 160" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:b7855ac0261f076c33b84af83a3b2b0f05348033c394238a71cfa05e7350daeb"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_ce_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_ce_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_ce_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_ce_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CE-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_ce_snapshot_product_api.py"' in supervisor


def test_ce_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_ce_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "c1b948a7-faf2-4b92-8e8d-1f9d66b51201"' in source
    assert 'facts.get("definitionRevision") != 159' in source
    assert 'facts.get("recoveryRevision") != 52' in source
    assert "revision=216 AND cutover_group_revision=243" in source
    assert "run_definition" not in source


def test_ce_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_ce_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CE_ID' in source
    assert '("c1b948a7-faf2-4b92-8e8d-1f9d66b51201", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 160" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 216" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 243" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 218" in source
    assert "retirement.DETACHED_GROUP_REVISION = 245" in source
    assert "run_definition" not in source


def test_cf_replacement_is_bound_to_exact_ce_detach_receipt():
    source = (ROOT / "scripts/a0v_cf_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "29d1b06d-3baa-4476-9cf8-5ea345d134c7"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "077d774d-7614-4270-ad29-7f90871c3e9f"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "d626046d-ceae-402e-8fbe-51ebe87b1409"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:ffa929f43cc570edf7029abec398fe03c52cd06b4d3fd8fdb7a0a7fd5ede3981"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 218" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 245" in source
    assert "replacement.DEFINITION_REVISION = 160" in source
    assert "run_definition" not in source


def test_cf_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cf_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cf_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "8cf0c597-cf81-4fa5-b1ff-f27e3537a94c"' in business
    assert 'successor.AV_GENERATION = "88996259-ad79-4aa6-962c-c29a24559db8"' in business
    assert 'successor.DETACH = "d626046d-ceae-402e-8fbe-51ebe87b1409"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 218" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 245" in business
    assert 'cutover.OPERATION = "41853ebd-b68f-4db6-aeda-ac9c765be324"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 245" in cutover
    assert "run_definition" not in business + cutover


def test_cf_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cf_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "f8c49bee-1e87-4d64-be32-e683e84dbb59"' in source
    assert 'observer.health.INSTALLATION_ID = "8cf0c597-cf81-4fa5-b1ff-f27e3537a94c"' in source
    assert "observer.health.ROUTE_REVISION = 219" in source
    assert "observer.health.GROUP_REVISION = 246" in source
    assert "observer.health.DEFINITION_REVISION = 160" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cf_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_cf_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "29d1b06d-3baa-4476-9cf8-5ea345d134c7"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 160" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 161" in source
    assert "recovery.RECOVERY_REVISION = 53" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 162" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 163" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:77be40f32ad75219d8b763b1c1b07c06867989a5783a92dd516bd44361d44ffd"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cf_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_cf_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_cf_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_cf_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CF-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cf_snapshot_product_api.py"' in supervisor


def test_cf_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_cf_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "d16e9452-0f4b-40cc-97f0-316841dfee29"' in source
    assert 'facts.get("definitionRevision") != 162' in source
    assert 'facts.get("recoveryRevision") != 53' in source
    assert "revision=219 AND cutover_group_revision=246" in source
    assert "run_definition" not in source


def test_cf_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cf_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CF_ID' in source
    assert '("d16e9452-0f4b-40cc-97f0-316841dfee29", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 163" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 219" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 246" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 221" in source
    assert "retirement.DETACHED_GROUP_REVISION = 248" in source
    assert "run_definition" not in source


def test_cg_replacement_is_bound_to_exact_cf_detach_receipt():
    source = (ROOT / "scripts/a0v_cg_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "8cf0c597-cf81-4fa5-b1ff-f27e3537a94c"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "0858ea02-0d34-49dc-b2c4-4276b31c72b7"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "829cd86a-bf4e-4b62-a0e8-e3a89c34b9e0"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:0f2adfef50c42ed684a0ccdedf737a9a13a9e31b55d7b778b08f3f49e1bb2f6b"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 221" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 248" in source
    assert "replacement.DEFINITION_REVISION = 163" in source
    assert "run_definition" not in source


def test_cg_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cg_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cg_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "8f42819c-0fc7-48cf-a5c4-9ba96894a6f5"' in business
    assert 'successor.AV_GENERATION = "3ed300fa-5fff-4949-9fb0-1926412e51ae"' in business
    assert 'successor.DETACH = "829cd86a-bf4e-4b62-a0e8-e3a89c34b9e0"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 221" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 248" in business
    assert 'cutover.OPERATION = "d8dbb6b2-7fdf-424a-b95f-63513ca37e06"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 248" in cutover
    assert "run_definition" not in business + cutover


def test_cg_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cg_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "a5b894bb-0a51-4487-a738-651c60ac7505"' in source
    assert 'observer.health.INSTALLATION_ID = "8f42819c-0fc7-48cf-a5c4-9ba96894a6f5"' in source
    assert "observer.health.ROUTE_REVISION = 222" in source
    assert "observer.health.GROUP_REVISION = 249" in source
    assert "observer.health.DEFINITION_REVISION = 163" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cg_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_cg_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "8cf0c597-cf81-4fa5-b1ff-f27e3537a94c"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 163" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 164" in source
    assert "recovery.RECOVERY_REVISION = 54" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 165" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 166" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:de7600063dce230701986d346b616e9b4a9bbe185d01998541cb67128b300a42"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cg_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_cg_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_cg_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_cg_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CG-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cg_snapshot_product_api.py"' in supervisor


def test_cg_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_cg_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "f7b2fc7f-9bce-4102-8f5b-48ec8879ae55"' in source
    assert 'facts.get("definitionRevision") != 165' in source
    assert 'facts.get("recoveryRevision") != 54' in source
    assert "revision=222 AND cutover_group_revision=249" in source
    assert "run_definition" not in source


def test_cg_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cg_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CG_ID' in source
    assert '("f7b2fc7f-9bce-4102-8f5b-48ec8879ae55", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 166" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 222" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 249" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 224" in source
    assert "retirement.DETACHED_GROUP_REVISION = 251" in source
    assert "run_definition" not in source


def test_ch_replacement_is_bound_to_exact_cg_detach_receipt():
    source = (ROOT / "scripts/a0v_ch_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "8f42819c-0fc7-48cf-a5c4-9ba96894a6f5"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "bd5e0164-fefb-4751-a7bd-5019a20dd3b5"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "3d65b065-8ad4-4a97-983f-f14ca0ada8cb"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:bbf8fb158183e1821129384611658468d0a6d28838068c6ad45960b2b36dc025"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 224" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 251" in source
    assert "replacement.DEFINITION_REVISION = 166" in source
    assert "run_definition" not in source


def test_ch_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_ch_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_ch_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "990f96f7-764e-4002-b691-fc5eb8d4335c"' in business
    assert 'successor.AV_GENERATION = "0521ccf8-304a-45b3-b820-dc6ebd64b51b"' in business
    assert 'successor.DETACH = "3d65b065-8ad4-4a97-983f-f14ca0ada8cb"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 224" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 251" in business
    assert 'cutover.OPERATION = "c0f54fd5-dcc3-4c4e-873c-e06518620b2b"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 251" in cutover
    assert "run_definition" not in business + cutover


def test_ch_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_ch_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "efed6af4-3243-47fd-83ef-8d870cddc3ea"' in source
    assert 'observer.health.INSTALLATION_ID = "990f96f7-764e-4002-b691-fc5eb8d4335c"' in source
    assert "observer.health.ROUTE_REVISION = 225" in source
    assert "observer.health.GROUP_REVISION = 252" in source
    assert "observer.health.DEFINITION_REVISION = 166" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_ch_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_ch_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "8f42819c-0fc7-48cf-a5c4-9ba96894a6f5"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 166" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 167" in source
    assert "recovery.RECOVERY_REVISION = 55" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 168" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 169" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:c9536786347d902ff87a9a06613df5644dfb6d9597afbf39733cc6aa0539ed58"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_ch_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_ch_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_ch_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_ch_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CH-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_ch_snapshot_product_api.py"' in supervisor


def test_ch_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_ch_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "0be8900c-4e4f-41c7-a93b-7dbfecb2bfe6"' in source
    assert 'facts.get("definitionRevision") != 168' in source
    assert 'facts.get("recoveryRevision") != 55' in source
    assert "revision=225 AND cutover_group_revision=252" in source
    assert "run_definition" not in source


def test_ch_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_ch_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CH_ID' in source
    assert '("0be8900c-4e4f-41c7-a93b-7dbfecb2bfe6", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 169" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 225" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 252" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 227" in source
    assert "retirement.DETACHED_GROUP_REVISION = 254" in source
    assert "run_definition" not in source


def test_ci_replacement_is_bound_to_exact_ch_detach_receipt():
    source = (ROOT / "scripts/a0v_ci_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "990f96f7-764e-4002-b691-fc5eb8d4335c"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "2c28623c-d418-4123-8846-89f4c4d905e9"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "bef972d2-2c5f-4cd3-9448-b7e94ff7594d"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:c1537c4af534489422e2fbe819d7ed079db9c25c9d1702d214c77097af8ffdac"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 227" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 254" in source
    assert "replacement.DEFINITION_REVISION = 169" in source
    assert "run_definition" not in source


def test_ci_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_ci_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_ci_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "1b9f500d-48a0-4f2c-8284-3db26e5cd4e7"' in business
    assert 'successor.AV_GENERATION = "8de8994b-ad87-4039-a851-d944153bca08"' in business
    assert 'successor.DETACH = "bef972d2-2c5f-4cd3-9448-b7e94ff7594d"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 227" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 254" in business
    assert 'cutover.OPERATION = "92bdd589-90d4-4e66-817d-1cb05ebfbd1d"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 254" in cutover
    assert "run_definition" not in business + cutover


def test_ci_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_ci_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "473dc4ab-42af-4dbd-95bf-67beaa6a1f3e"' in source
    assert 'observer.health.INSTALLATION_ID = "1b9f500d-48a0-4f2c-8284-3db26e5cd4e7"' in source
    assert "observer.health.ROUTE_REVISION = 228" in source
    assert "observer.health.GROUP_REVISION = 255" in source
    assert "observer.health.DEFINITION_REVISION = 169" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_ci_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_ci_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "990f96f7-764e-4002-b691-fc5eb8d4335c"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 169" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 170" in source
    assert "recovery.RECOVERY_REVISION = 56" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 171" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 172" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:9b479ea57323740d9fc9afd4a74474a32e405dbbe0b68cc675edbc2bcefc7ebb"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_ci_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_ci_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_ci_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_ci_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CI-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_ci_snapshot_product_api.py"' in supervisor


def test_ci_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_ci_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "4c67a2b5-34a6-47f7-9cc6-e59ce718d491"' in source
    assert 'facts.get("definitionRevision") != 171' in source
    assert 'facts.get("recoveryRevision") != 56' in source
    assert "revision=228 AND cutover_group_revision=255" in source
    assert "run_definition" not in source


def test_ci_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_ci_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CI_ID' in source
    assert '("4c67a2b5-34a6-47f7-9cc6-e59ce718d491", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 172" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 228" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 255" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 230" in source
    assert "retirement.DETACHED_GROUP_REVISION = 257" in source
    assert "run_definition" not in source


def test_cj_replacement_is_bound_to_exact_ci_detach_receipt():
    source = (ROOT / "scripts/a0v_cj_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "1b9f500d-48a0-4f2c-8284-3db26e5cd4e7"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "33240efc-8111-49ef-ac0c-759ae37868cc"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "700c9914-c3ed-4360-8769-5f8d09307352"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:5cc5d6e9cf6a284f6e9533438f225291042162573aee209ff9b9cbc20893c4dd"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 230" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 257" in source
    assert "replacement.DEFINITION_REVISION = 172" in source
    assert "run_definition" not in source


def test_cj_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cj_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cj_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "184e0d1d-128a-462c-b677-d19bc5bf0891"' in business
    assert 'successor.AV_GENERATION = "f45f46a9-56ae-49b5-966d-083cdf19282b"' in business
    assert 'successor.DETACH = "700c9914-c3ed-4360-8769-5f8d09307352"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 230" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 257" in business
    assert 'cutover.OPERATION = "82b2884f-7625-47d5-a531-ea32c9ed6f14"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 257" in cutover
    assert "run_definition" not in business + cutover


def test_cj_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cj_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "8a148985-7582-4c10-b514-cc7e01359ac0"' in source
    assert 'observer.health.INSTALLATION_ID = "184e0d1d-128a-462c-b677-d19bc5bf0891"' in source
    assert "observer.health.ROUTE_REVISION = 231" in source
    assert "observer.health.GROUP_REVISION = 258" in source
    assert "observer.health.DEFINITION_REVISION = 172" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cj_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_cj_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "1b9f500d-48a0-4f2c-8284-3db26e5cd4e7"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 172" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 173" in source
    assert "recovery.RECOVERY_REVISION = 57" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 174" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 175" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:d32b15b1aa187d82bbd8fc190c565c560e6e155217d9f1a5f127200bc6f0fd99"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cj_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_cj_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_cj_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_cj_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CJ-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cj_snapshot_product_api.py"' in supervisor


def test_cj_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_cj_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "d0326f13-2ccb-49c0-ade9-0729dc188717"' in source
    assert 'facts.get("revision") != 5' in source
    assert 'facts.get("definitionRevision") != 174' in source
    assert 'facts.get("recoveryRevision") != 57' in source
    assert "revision=231 AND cutover_group_revision=258" in source
    assert '"revision": 4' in source
    assert "run_definition" not in source


def test_cj_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cj_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CJ_ID' in source
    assert '("d0326f13-2ccb-49c0-ade9-0729dc188717", 5, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 175" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 231" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 258" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 233" in source
    assert "retirement.DETACHED_GROUP_REVISION = 260" in source
    assert "run_definition" not in source


def test_ck_replacement_is_bound_to_exact_cj_detach_receipt():
    source = (ROOT / "scripts/a0v_ck_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "184e0d1d-128a-462c-b677-d19bc5bf0891"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "69469d23-01f1-41e1-8263-14dbbde43595"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "54b8272c-dae1-4dca-833e-90a40bc77fba"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:9d8812adc4d156ee37149d5791920669c5684915f0399be6030cb358eb14e09d"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 233" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 260" in source
    assert "replacement.DEFINITION_REVISION = 175" in source
    assert "run_definition" not in source


def test_ck_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_ck_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_ck_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "c1cb44ba-68ae-4d32-9974-5f031554fed2"' in business
    assert 'successor.AV_GENERATION = "1edb1688-e2b6-42f0-b513-849ae372859e"' in business
    assert 'successor.DETACH = "54b8272c-dae1-4dca-833e-90a40bc77fba"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 233" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 260" in business
    assert 'cutover.OPERATION = "4d7f869d-15bd-4246-8f92-7c52e59c7c23"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 260" in cutover
    assert "run_definition" not in business + cutover


def test_ck_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_ck_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "e60b3ca6-bdc2-40a6-9928-5ec574f35917"' in source
    assert 'observer.health.INSTALLATION_ID = "c1cb44ba-68ae-4d32-9974-5f031554fed2"' in source
    assert "observer.health.ROUTE_REVISION = 234" in source
    assert "observer.health.GROUP_REVISION = 261" in source
    assert "observer.health.DEFINITION_REVISION = 175" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_ck_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_ck_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "184e0d1d-128a-462c-b677-d19bc5bf0891"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 175" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 176" in source
    assert "recovery.RECOVERY_REVISION = 58" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 177" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 178" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:01c5506cb0d32daa41cba70de767ca676924ccb6b596aaf524f24979ead7ce40"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_ck_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_ck_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_ck_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_ck_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CK-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_ck_snapshot_product_api.py"' in supervisor


def test_ck_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_ck_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "7c99b249-fc1e-4844-abc5-8b7cc268fd39"' in source
    assert 'facts.get("revision") != 5' in source
    assert 'facts.get("definitionRevision") != 177' in source
    assert 'facts.get("recoveryRevision") != 58' in source
    assert "revision=234 AND cutover_group_revision=261" in source
    assert '"revision": 4' in source
    assert "run_definition" not in source


def test_ck_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_ck_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CK_ID' in source
    assert '("7c99b249-fc1e-4844-abc5-8b7cc268fd39", 5, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 178" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 234" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 261" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 236" in source
    assert "retirement.DETACHED_GROUP_REVISION = 263" in source
    assert "run_definition" not in source


def test_cl_replacement_is_bound_to_exact_ck_detach_receipt():
    source = (ROOT / "scripts/a0v_cl_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "c1cb44ba-68ae-4d32-9974-5f031554fed2"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "87aa9a73-329e-42df-ac89-0e24bd8e4780"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "8ed70360-4e39-4a96-992f-d70f3222b541"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:812e9450e64a730d13b34db809903cbd61d3c537c4bc4fb3ba06eb09aaa15144"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 236" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 263" in source
    assert "replacement.DEFINITION_REVISION = 178" in source
    assert "run_definition" not in source


def test_cl_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cl_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cl_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "64e49f66-b0ef-4676-91c1-eb05f6d1d0b1"' in business
    assert 'successor.AV_GENERATION = "a583218d-f65b-4697-9e60-7281a0bff66e"' in business
    assert 'successor.DETACH = "8ed70360-4e39-4a96-992f-d70f3222b541"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 236" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 263" in business
    assert 'cutover.OPERATION = "e381a022-f80b-4d45-9e98-91a51077213e"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 263" in cutover
    assert "run_definition" not in business + cutover


def test_cl_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cl_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "1db4380b-64f4-4d65-96e6-349258c57d4a"' in source
    assert 'observer.health.INSTALLATION_ID = "64e49f66-b0ef-4676-91c1-eb05f6d1d0b1"' in source
    assert "observer.health.ROUTE_REVISION = 237" in source
    assert "observer.health.GROUP_REVISION = 264" in source
    assert "observer.health.DEFINITION_REVISION = 178" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cl_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_cl_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "c1cb44ba-68ae-4d32-9974-5f031554fed2"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 178" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 179" in source
    assert "recovery.RECOVERY_REVISION = 59" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 180" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 181" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:b2a6a614463c337ec75e54dcedd7269332f9f54c33c3005c2296b72965081eb8"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cl_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_cl_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_cl_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_cl_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CL-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cl_snapshot_product_api.py"' in supervisor


def test_cl_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_cl_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "bf2ff936-6c93-4712-93cb-30dd312f11eb"' in source
    assert 'facts.get("revision") != 5' in source
    assert 'facts.get("definitionRevision") != 180' in source
    assert 'facts.get("recoveryRevision") != 59' in source
    assert "revision=237 AND cutover_group_revision=264" in source
    assert '"revision": 4' in source
    assert "run_definition" not in source


def test_cl_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cl_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CL_ID' in source
    assert '("bf2ff936-6c93-4712-93cb-30dd312f11eb", 5, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 181" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 237" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 264" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 239" in source
    assert "retirement.DETACHED_GROUP_REVISION = 266" in source
    assert "run_definition" not in source


def test_cm_replacement_is_bound_to_exact_cl_detach_receipt():
    source = (ROOT / "scripts/a0v_cm_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "64e49f66-b0ef-4676-91c1-eb05f6d1d0b1"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "a4b94187-2a96-4779-af57-02e4b659a90d"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "03e11531-9fb5-4453-80dd-2d2d07051bec"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:b93907af1a3ace36e10d83da4e199da17c80aaa0b9cdbc557b88a54fed721992"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 239" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 266" in source
    assert "replacement.DEFINITION_REVISION = 181" in source
    assert "run_definition" not in source


def test_cm_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cm_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cm_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "b52c8e1c-a343-4ef4-b106-38d859ba9677"' in business
    assert 'successor.AV_GENERATION = "d3ec88cc-a05a-4895-bc27-c983a367a9a8"' in business
    assert 'successor.DETACH = "03e11531-9fb5-4453-80dd-2d2d07051bec"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 239" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 266" in business
    assert 'cutover.OPERATION = "d6900aae-ce9e-4334-b440-6a337de63dbc"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 266" in cutover
    assert "run_definition" not in business + cutover


def test_cm_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cm_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "29cb2549-e72b-40df-bb46-7709a763da4c"' in source
    assert 'observer.health.INSTALLATION_ID = "b52c8e1c-a343-4ef4-b106-38d859ba9677"' in source
    assert "observer.health.ROUTE_REVISION = 240" in source
    assert "observer.health.GROUP_REVISION = 267" in source
    assert "observer.health.DEFINITION_REVISION = 181" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cm_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_cm_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "64e49f66-b0ef-4676-91c1-eb05f6d1d0b1"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 181" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 182" in source
    assert "recovery.RECOVERY_REVISION = 60" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 183" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 184" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:398205f8a032adc5af6fad259ba7780f600340382a7b542530725c0d78fd426f"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cm_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_cm_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_cm_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_cm_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CM-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cm_snapshot_product_api.py"' in supervisor


def test_cm_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_cm_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "da4fed10-4cdc-4147-8595-d2f40c568419"' in source
    assert 'facts.get("revision") != 4' in source
    assert 'facts.get("definitionRevision") != 184' in source
    assert 'facts.get("recoveryRevision") != 60' in source
    assert "revision=240 AND cutover_group_revision=267" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_cm_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cm_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CM_ID' in source
    assert '("da4fed10-4cdc-4147-8595-d2f40c568419", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 184" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 240" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 267" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 242" in source
    assert "retirement.DETACHED_GROUP_REVISION = 269" in source
    assert "run_definition" not in source


def test_cn_replacement_is_bound_to_exact_cm_detach_receipt():
    source = (ROOT / "scripts/a0v_cn_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "b52c8e1c-a343-4ef4-b106-38d859ba9677"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "cc32921f-27a2-43a0-94e4-23b84992e278"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "a118ae49-92de-477a-92f3-0d855c48a472"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:5074648fad39e4be7040cac99fc18cc0748a6d162e2700ea0d78aa19c80803af"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 242" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 269" in source
    assert "replacement.DEFINITION_REVISION = 184" in source
    assert "run_definition" not in source


def test_cn_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cn_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cn_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "1366f4dd-47d9-42c1-b26a-759c7bd556da"' in business
    assert 'successor.AV_GENERATION = "cd0601e0-2668-496d-9f93-561d2e69a170"' in business
    assert 'successor.DETACH = "a118ae49-92de-477a-92f3-0d855c48a472"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 242" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 269" in business
    assert 'cutover.OPERATION = "abfafc4b-9a00-433e-af6c-54636f8e5983"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 269" in cutover
    assert "run_definition" not in business + cutover


def test_cn_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cn_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "4ba3f9c1-7480-48f5-ab79-e4f167968012"' in source
    assert 'observer.health.INSTALLATION_ID = "1366f4dd-47d9-42c1-b26a-759c7bd556da"' in source
    assert "observer.health.ROUTE_REVISION = 243" in source
    assert "observer.health.GROUP_REVISION = 270" in source
    assert "observer.health.DEFINITION_REVISION = 184" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cn_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_cn_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "b52c8e1c-a343-4ef4-b106-38d859ba9677"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 184" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 185" in source
    assert "recovery.RECOVERY_REVISION = 61" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 186" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 187" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:f372ccc196603b610e1a32c0323e3deb2bb43ef1dae561123adc6b7cfdc3b083"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cn_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_cn_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_cn_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_cn_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CN-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cn_snapshot_product_api.py"' in supervisor


def test_cn_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_cn_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "1cf52d77-baa9-49a5-9315-d705b864c8a0"' in source
    assert 'facts.get("revision") != 5' in source
    assert 'facts.get("definitionRevision") != 186' in source
    assert 'facts.get("recoveryRevision") != 61' in source
    assert "revision=243 AND cutover_group_revision=270" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_cn_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cn_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CN_ID' in source
    assert '("1cf52d77-baa9-49a5-9315-d705b864c8a0", 5, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 187" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 243" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 270" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 245" in source
    assert "retirement.DETACHED_GROUP_REVISION = 272" in source
    assert "run_definition" not in source


def test_co_replacement_is_bound_to_exact_cn_detach_receipt():
    source = (ROOT / "scripts/a0v_co_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "1366f4dd-47d9-42c1-b26a-759c7bd556da"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "993d8b13-fcf5-4a14-9410-b601d6f7a891"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "5f72b40e-543f-49e6-947c-a636a41cee99"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:46f951422c2f99c4cc63103b202ae83c8b04bff574282204f5f89f90d3fff09c"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 245" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 272" in source
    assert "replacement.DEFINITION_REVISION = 187" in source
    assert "run_definition" not in source


def test_co_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_co_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_co_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "648b267b-bb8f-4582-ab29-288279f534c7"' in business
    assert 'successor.AV_GENERATION = "db428c1b-2fe4-4869-8a69-ddffaa909ba7"' in business
    assert 'successor.DETACH = "5f72b40e-543f-49e6-947c-a636a41cee99"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 245" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 272" in business
    assert 'cutover.OPERATION = "7e21a322-9f77-4d5b-baa2-f6d7ba19da13"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 272" in cutover
    assert "run_definition" not in business + cutover


def test_co_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_co_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "d05101eb-707f-45b2-84f8-f43a5c80d69c"' in source
    assert 'observer.health.INSTALLATION_ID = "648b267b-bb8f-4582-ab29-288279f534c7"' in source
    assert "observer.health.ROUTE_REVISION = 246" in source
    assert "observer.health.GROUP_REVISION = 273" in source
    assert "observer.health.DEFINITION_REVISION = 187" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_co_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_co_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "1366f4dd-47d9-42c1-b26a-759c7bd556da"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 187" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 188" in source
    assert "recovery.RECOVERY_REVISION = 62" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 189" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 190" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:73a5a3bcbf2812dc4bddff81f8ef4cf62f712769286db3cfcebd26eb28cc04cb"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_co_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_co_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_co_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_co_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CO-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_co_snapshot_product_api.py"' in supervisor


def test_co_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_co_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "f3061da8-baee-4b3a-8307-88d835d42cca"' in source
    assert 'facts.get("revision") != 4' in source
    assert 'facts.get("definitionRevision") != 189' in source
    assert 'facts.get("recoveryRevision") != 62' in source
    assert "revision=246 AND cutover_group_revision=273" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_co_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_co_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CO_ID' in source
    assert '("f3061da8-baee-4b3a-8307-88d835d42cca", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 190" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 246" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 273" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 248" in source
    assert "retirement.DETACHED_GROUP_REVISION = 275" in source
    assert "run_definition" not in source


def test_cp_replacement_is_bound_to_exact_co_detach_receipt():
    source = (ROOT / "scripts/a0v_cp_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "648b267b-bb8f-4582-ab29-288279f534c7"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "25fa94bf-b376-4c44-9ce9-147dc89c96d3"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "d392b12f-9523-487e-aa9c-f473450e95cf"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:cccb32032a1403cfd5e5da25875f026330e2f95f743c6d78ba669f9ab576db96"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 248" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 275" in source
    assert "replacement.DEFINITION_REVISION = 190" in source
    assert "run_definition" not in source


def test_cp_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cp_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cp_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "1d8b71c5-1cde-4d16-b16f-835f92bf8663"' in business
    assert 'successor.AV_GENERATION = "9b0201fc-9822-4527-b63c-23cbd416057d"' in business
    assert 'successor.DETACH = "d392b12f-9523-487e-aa9c-f473450e95cf"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 248" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 275" in business
    assert 'cutover.OPERATION = "ec6199e0-1a5f-4d63-a44b-bd1e8cfe69bd"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 275" in cutover
    assert "run_definition" not in business + cutover


def test_cp_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cp_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "ca822e5b-c389-4609-8ca7-4dcdcb7c016c"' in source
    assert 'observer.health.INSTALLATION_ID = "1d8b71c5-1cde-4d16-b16f-835f92bf8663"' in source
    assert "observer.health.ROUTE_REVISION = 249" in source
    assert "observer.health.GROUP_REVISION = 276" in source
    assert "observer.health.DEFINITION_REVISION = 190" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cp_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_cp_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "648b267b-bb8f-4582-ab29-288279f534c7"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 190" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 191" in source
    assert "recovery.RECOVERY_REVISION = 63" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 192" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 193" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:d5159f331c3565a2968fe183945c952784060e6c16950a054443eb4f0665fccb"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cp_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_cp_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_cp_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_cp_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CP-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cp_snapshot_product_api.py"' in supervisor


def test_cp_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_cp_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "4c63e9fd-6f11-461d-a753-87962f5306ad"' in source
    assert 'facts.get("revision") != 4' in source
    assert 'facts.get("definitionRevision") != 192' in source
    assert 'facts.get("recoveryRevision") != 63' in source
    assert "revision=249 AND cutover_group_revision=276" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_cp_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cp_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CP_ID' in source
    assert '("4c63e9fd-6f11-461d-a753-87962f5306ad", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 193" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 249" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 276" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 251" in source
    assert "retirement.DETACHED_GROUP_REVISION = 278" in source
    assert "run_definition" not in source


def test_cq_replacement_is_bound_to_exact_cp_detach_receipt():
    source = (ROOT / "scripts/a0v_cq_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "1d8b71c5-1cde-4d16-b16f-835f92bf8663"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "fc24ee2f-52cb-40e8-98e0-dd260db335d2"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "4603f48f-2d3a-4581-b837-b85658a2cf50"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:05a9ec8c3b477d23c0b329dded09c2d4ad08d686a2997fc36bb4bab46db95205"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 251" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 278" in source
    assert "replacement.DEFINITION_REVISION = 193" in source
    assert "run_definition" not in source


def test_cq_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cq_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cq_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "fff0b0d3-bf8f-44b0-b1b7-6a2972daeb80"' in business
    assert 'successor.AV_GENERATION = "ae8a1005-99fb-48c5-9dfe-8f76590bc0c8"' in business
    assert 'successor.DETACH = "4603f48f-2d3a-4581-b837-b85658a2cf50"' in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 251" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 278" in business
    assert 'cutover.OPERATION = "ebd2d074-9800-4ccb-9f91-0fed1beda3d1"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 278" in cutover
    assert "run_definition" not in business + cutover


def test_cq_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cq_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "2069f6d3-1b40-4f06-9aff-62febe156943"' in source
    assert 'observer.health.INSTALLATION_ID = "fff0b0d3-bf8f-44b0-b1b7-6a2972daeb80"' in source
    assert "observer.health.ROUTE_REVISION = 252" in source
    assert "observer.health.GROUP_REVISION = 279" in source
    assert "observer.health.DEFINITION_REVISION = 193" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cr_replacement_is_bound_to_exact_cq_detach_receipt():
    source = (ROOT / "scripts/a0v_cr_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "fff0b0d3-bf8f-44b0-b1b7-6a2972daeb80"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "36c3d6ca-db24-4553-a0ec-8748006b3dd8"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "2d8a382b-90f1-46c3-9100-c2310a949914"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:3b618e589557064bf049dd344fa9bdc345236d22a38ec2c1558d2a968d08b432"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 254" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 281" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 11" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 6" in source
    assert "replacement.DEFINITION_REVISION = 193" in source
    assert "run_definition" not in source


def test_cr_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cr_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cr_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "913cb7a1-4912-471a-abbf-452e3ce999a9"' in business
    assert 'successor.AV_GENERATION = "a4a16448-5581-4948-b962-777ff601e855"' in business
    assert 'successor.DETACH = "2d8a382b-90f1-46c3-9100-c2310a949914"' in business
    assert "successor.PREDECESSOR_BINDING_REVISION = 11" in business
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 6" in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 254" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 281" in business
    assert 'cutover.OPERATION = "59e26a0e-c144-479b-ba78-b8cba414b006"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 281" in cutover
    assert "run_definition" not in business + cutover


def test_cr_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cr_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "38aadd42-6693-467f-abde-cc36924fef2f"' in source
    assert 'observer.health.INSTALLATION_ID = "913cb7a1-4912-471a-abbf-452e3ce999a9"' in source
    assert "observer.health.ROUTE_REVISION = 255" in source
    assert "observer.health.GROUP_REVISION = 282" in source
    assert "observer.health.DEFINITION_REVISION = 193" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cr_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_cr_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "1d8b71c5-1cde-4d16-b16f-835f92bf8663"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 193" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 194" in source
    assert "recovery.RECOVERY_REVISION = 64" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 195" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 196" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:785823471c14d9eda4e67250e19f9b498116aaf510e62a77ff47d0275dfa24e6"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cr_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_cr_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_cr_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_cr_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CR-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cr_snapshot_product_api.py"' in supervisor


def test_cr_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_cr_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "11e98b8f-d898-4b1b-a6fc-c210bb44e5d7"' in source
    assert 'facts.get("revision") != 5' in source
    assert 'facts.get("definitionRevision") != 195' in source
    assert 'facts.get("recoveryRevision") != 64' in source
    assert "revision=255 AND cutover_group_revision=282" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_cr_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cr_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CR_ID' in source
    assert '("11e98b8f-d898-4b1b-a6fc-c210bb44e5d7", 5, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 196" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 255" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 282" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 257" in source
    assert "retirement.DETACHED_GROUP_REVISION = 284" in source
    assert "run_definition" not in source


def test_cs_replacement_is_bound_to_exact_cr_detach_receipt():
    source = (ROOT / "scripts/a0v_cs_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "913cb7a1-4912-471a-abbf-452e3ce999a9"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "0667be2f-3ebd-484b-99f0-dfb135a6f9c2"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "14c1b753-d557-4441-bf7f-89ad5ab48be5"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:bd7ff2a43c944fe8aed88f89e9af82b511a36a8e029d86bb2428369ba3f9cc06"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 257" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 284" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 9" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "replacement.DEFINITION_REVISION = 196" in source
    assert "run_definition" not in source


def test_cs_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cs_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cs_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "ff72acba-1e59-4da3-b92a-18737e18e9d2"' in business
    assert 'successor.AV_GENERATION = "01a1719d-1109-440f-a233-1c5a6adb0d81"' in business
    assert 'successor.DETACH = "14c1b753-d557-4441-bf7f-89ad5ab48be5"' in business
    assert "successor.PREDECESSOR_BINDING_REVISION = 9" in business
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 5" in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 257" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 284" in business
    assert 'cutover.OPERATION = "d4036350-f591-4064-abf2-4e2849115c57"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 284" in cutover
    assert "run_definition" not in business + cutover


def test_cs_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cs_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "7b8e60bf-8cb6-4e6a-9a50-05f6e3b4fc3c"' in source
    assert 'observer.health.INSTALLATION_ID = "ff72acba-1e59-4da3-b92a-18737e18e9d2"' in source
    assert "observer.health.ROUTE_REVISION = 258" in source
    assert "observer.health.GROUP_REVISION = 285" in source
    assert "observer.health.DEFINITION_REVISION = 196" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cs_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_cs_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "913cb7a1-4912-471a-abbf-452e3ce999a9"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 196" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 197" in source
    assert "recovery.RECOVERY_REVISION = 65" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 198" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 199" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:a7ac1581109526f9ebcf492ab38264a892ca6ec732bbfd773c1fa8a8b388b4dd"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cs_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_cs_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_cs_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_cs_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CS-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cs_snapshot_product_api.py"' in supervisor


def test_cs_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_cs_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "b7d12c25-6673-48b3-aaba-dc803edb9169"' in source
    assert 'facts.get("revision") != 5' in source
    assert 'facts.get("definitionRevision") != 198' in source
    assert 'facts.get("recoveryRevision") != 65' in source
    assert "revision=258 AND cutover_group_revision=285" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_cs_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cs_terminal_retirement.py").read_text(encoding="utf-8")
    assert 'retirement.AR_ID = successor.CS_ID' in source
    assert '("b7d12c25-6673-48b3-aaba-dc803edb9169", 5, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 199" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 258" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 285" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 260" in source
    assert "retirement.DETACHED_GROUP_REVISION = 287" in source
    assert "run_definition" not in source


def test_ct_replacement_is_bound_to_exact_cs_detach_receipt():
    source = (ROOT / "scripts/a0v_ct_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "ff72acba-1e59-4da3-b92a-18737e18e9d2"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "fa96b3bf-b140-466b-bb10-3a0d604dde1e"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "13c4d61c-ea9b-4f13-94d7-12e21e8a09a4"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:f745d09717dbf72734a3792e67b2f9b88c692f23fe7c03fd903291bccfcb99a6"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 260" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 287" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 9" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "replacement.DEFINITION_REVISION = 199" in source
    assert "run_definition" not in source


def test_ct_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_ct_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_ct_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "b4847c85-b452-4c87-bf56-8a57bc9f8d25"' in business
    assert 'successor.AV_GENERATION = "0d234db2-8b76-4ec8-a14a-a8c6eec9bbc6"' in business
    assert 'successor.DETACH = "13c4d61c-ea9b-4f13-94d7-12e21e8a09a4"' in business
    assert "successor.PREDECESSOR_BINDING_REVISION = 9" in business
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 5" in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 260" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 287" in business
    assert 'cutover.OPERATION = "057d41ab-6558-4946-b677-30152ed7046b"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 287" in cutover
    assert "run_definition" not in business + cutover


def test_ct_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_ct_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "31b9552d-d58f-48e8-a905-2534fe334ef5"' in source
    assert 'observer.health.INSTALLATION_ID = "b4847c85-b452-4c87-bf56-8a57bc9f8d25"' in source
    assert "observer.health.ROUTE_REVISION = 261" in source
    assert "observer.health.GROUP_REVISION = 288" in source
    assert "observer.health.DEFINITION_REVISION = 199" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_ct_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_ct_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "ff72acba-1e59-4da3-b92a-18737e18e9d2"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 199" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 200" in source
    assert "recovery.RECOVERY_REVISION = 66" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 201" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 202" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:d65a82d1bc3ffc049c3d0fe287707e894acd45456814575afdfa42b0290bf87c"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_ct_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_ct_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_ct_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_ct_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CT-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_ct_snapshot_product_api.py"' in supervisor


def test_ct_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_ct_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "5b22aca6-70b5-46e0-b5aa-0f477964df96"' in source
    assert 'facts.get("revision") != 5' in source
    assert 'facts.get("definitionRevision") != 201' in source
    assert 'facts.get("recoveryRevision") != 66' in source
    assert "revision=261 AND cutover_group_revision=288" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_ct_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_ct_terminal_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = successor.CT_ID" in source
    assert '("5b22aca6-70b5-46e0-b5aa-0f477964df96", 5, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 202" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 261" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 288" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 263" in source
    assert "retirement.DETACHED_GROUP_REVISION = 290" in source
    assert "run_definition" not in source


def test_cu_replacement_is_bound_to_exact_ct_detach_receipt():
    source = (ROOT / "scripts/a0v_cu_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "b4847c85-b452-4c87-bf56-8a57bc9f8d25"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "4704b467-5d69-4ee3-b4e5-e755c5e98eea"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "b1101390-ca5d-43bf-bc6a-c3bc0fc1d4f1"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:8809a0a0ff8a8e69291d737a28277a48ef6faea6b8520ae658c55b320ace7123"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 263" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 290" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 9" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "replacement.DEFINITION_REVISION = 202" in source
    assert "run_definition" not in source


def test_cu_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cu_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cu_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "2c2d5506-1f80-4557-bf4b-00ead0258002"' in business
    assert 'successor.AV_GENERATION = "bcaa7ea0-62b1-4238-8615-28db45e3014e"' in business
    assert 'successor.DETACH = "b1101390-ca5d-43bf-bc6a-c3bc0fc1d4f1"' in business
    assert "successor.PREDECESSOR_BINDING_REVISION = 9" in business
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 5" in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 263" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 290" in business
    assert 'cutover.OPERATION = "ef453252-1d89-4f02-8f3f-3a05c79d6293"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 290" in cutover
    assert "run_definition" not in business + cutover


def test_cu_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cu_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "1bc0569b-be26-4ee5-81d2-631f2ec26885"' in source
    assert 'observer.health.INSTALLATION_ID = "2c2d5506-1f80-4557-bf4b-00ead0258002"' in source
    assert "observer.health.ROUTE_REVISION = 264" in source
    assert "observer.health.GROUP_REVISION = 291" in source
    assert "observer.health.DEFINITION_REVISION = 202" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cu_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_cu_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "b4847c85-b452-4c87-bf56-8a57bc9f8d25"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 202" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 203" in source
    assert "recovery.RECOVERY_REVISION = 67" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 204" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 205" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:8090c986e3c22b2548a14e793dc8376230bdb262aedd84f10083e2139605230a"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cu_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_cu_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_cu_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_cu_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CU-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cu_snapshot_product_api.py"' in supervisor


def test_cu_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_cu_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "e845cb50-44dd-489c-a85d-85a8932b4d0f"' in source
    assert 'facts.get("revision") != 5' in source
    assert 'facts.get("definitionRevision") != 204' in source
    assert 'facts.get("recoveryRevision") != 67' in source
    assert "revision=264 AND cutover_group_revision=291" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_cu_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cu_terminal_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = successor.CU_ID" in source
    assert '("e845cb50-44dd-489c-a85d-85a8932b4d0f", 5, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 205" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 264" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 291" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 266" in source
    assert "retirement.DETACHED_GROUP_REVISION = 293" in source
    assert "run_definition" not in source


def test_cv_replacement_is_bound_to_exact_cu_detach_receipt():
    source = (ROOT / "scripts/a0v_cv_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "2c2d5506-1f80-4557-bf4b-00ead0258002"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "2acec273-b5c9-4fc6-8e55-943640f706f4"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "ee918fb3-05db-4ed0-a678-0554225bb427"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:bdb72a10abfd3412182543a079b8c4bc813d0c7641186f6558aaa66560eff36e"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 266" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 293" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 9" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "replacement.DEFINITION_REVISION = 205" in source
    assert "run_definition" not in source


def test_cv_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cv_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cv_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "f94149ca-a01e-4a20-836f-3f5132e0dbb7"' in business
    assert 'successor.AV_GENERATION = "82aec2b8-072d-4f2e-9624-f9539c8890a6"' in business
    assert 'successor.DETACH = "ee918fb3-05db-4ed0-a678-0554225bb427"' in business
    assert "successor.PREDECESSOR_BINDING_REVISION = 9" in business
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 5" in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 266" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 293" in business
    assert 'cutover.OPERATION = "f340ca4e-3cfd-43e7-ad7b-5b548dcf3bc8"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 293" in cutover
    assert "run_definition" not in business + cutover


def test_cv_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cv_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "29511d3b-0921-4ce3-9c55-34cbe531f678"' in source
    assert 'observer.health.INSTALLATION_ID = "f94149ca-a01e-4a20-836f-3f5132e0dbb7"' in source
    assert "observer.health.ROUTE_REVISION = 267" in source
    assert "observer.health.GROUP_REVISION = 294" in source
    assert "observer.health.DEFINITION_REVISION = 205" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cv_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_cv_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "2c2d5506-1f80-4557-bf4b-00ead0258002"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 205" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 206" in source
    assert "recovery.RECOVERY_REVISION = 68" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 207" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 208" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:7dcfc71097e84bc4b25529a1c70a98904768ea1655b037bb777c24cae51ab3b9"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cv_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_cv_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_cv_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_cv_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CV-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cv_snapshot_product_api.py"' in supervisor


def test_cv_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_cv_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "88c9a09f-e5f3-4c65-9f5c-dc35cc1252e6"' in source
    assert 'facts.get("revision") != 4' in source
    assert 'facts.get("definitionRevision") != 207' in source
    assert 'facts.get("recoveryRevision") != 68' in source
    assert "revision=267 AND cutover_group_revision=294" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_cv_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cv_terminal_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = successor.CV_ID" in source
    assert '("88c9a09f-e5f3-4c65-9f5c-dc35cc1252e6", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 208" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 267" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 294" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 269" in source
    assert "retirement.DETACHED_GROUP_REVISION = 296" in source
    assert "run_definition" not in source


def test_cw_replacement_is_bound_to_exact_cv_detach_receipt():
    source = (ROOT / "scripts/a0v_cw_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "f94149ca-a01e-4a20-836f-3f5132e0dbb7"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "17648f28-66dc-4c11-87d2-c32e3a016bcb"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "9add3bab-81be-417d-ab80-18f254ecf43f"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:a8bc901472293b85f1b6085e97ea673dbe3ea79216668d6b6c15ffb6a0fb9bea"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 269" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 296" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 9" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "replacement.DEFINITION_REVISION = 208" in source
    assert "run_definition" not in source


def test_cw_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cw_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cw_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "0d5d5a7f-6e40-4725-b337-b79acc7d896a"' in business
    assert 'successor.AV_GENERATION = "a60036f1-5887-4157-ad32-616925b547bf"' in business
    assert 'successor.DETACH = "9add3bab-81be-417d-ab80-18f254ecf43f"' in business
    assert "successor.PREDECESSOR_BINDING_REVISION = 9" in business
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 5" in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 269" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 296" in business
    assert 'cutover.OPERATION = "502876a9-ba7c-439d-83ad-e1124cc7e231"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 296" in cutover
    assert "run_definition" not in business + cutover


def test_cw_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cw_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "65d2b402-68f8-4294-b42c-5585894c6e57"' in source
    assert 'observer.health.INSTALLATION_ID = "0d5d5a7f-6e40-4725-b337-b79acc7d896a"' in source
    assert "observer.health.ROUTE_REVISION = 270" in source
    assert "observer.health.GROUP_REVISION = 297" in source
    assert "observer.health.DEFINITION_REVISION = 208" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cw_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_cw_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "f94149ca-a01e-4a20-836f-3f5132e0dbb7"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 208" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 209" in source
    assert "recovery.RECOVERY_REVISION = 69" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 210" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 211" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:741c9bffd2ee51a680fd7617638e35f32d461c241e0cd95692a660c49f68caa1"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cw_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_cw_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_cw_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_cw_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CW-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cw_snapshot_product_api.py"' in supervisor


def test_cw_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_cw_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "0f9c30e6-012d-4a08-9aed-f7b0e0492c31"' in source
    assert 'facts.get("revision") != 4' in source
    assert 'facts.get("definitionRevision") != 210' in source
    assert 'facts.get("recoveryRevision") != 69' in source
    assert "revision=270 AND cutover_group_revision=297" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_cw_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cw_terminal_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = successor.CW_ID" in source
    assert '("0f9c30e6-012d-4a08-9aed-f7b0e0492c31", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 211" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 270" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 297" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 272" in source
    assert "retirement.DETACHED_GROUP_REVISION = 299" in source
    assert "run_definition" not in source


def test_cx_replacement_is_bound_to_exact_cw_detach_receipt():
    source = (ROOT / "scripts/a0v_cx_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "0d5d5a7f-6e40-4725-b337-b79acc7d896a"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "e69aa8dc-45ab-4d4d-bb23-008fe3491524"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "5aa372a9-1a82-41ff-b25e-00e898cda82a"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:2f121bf22c69efb2e4f37e1df1c17202c5c695e6a378459a92d07054108af78c"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 272" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 299" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 9" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "replacement.DEFINITION_REVISION = 211" in source
    assert "run_definition" not in source


def test_cx_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cx_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cx_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "2e374e12-7523-466d-aed7-bdabe8b69aff"' in business
    assert 'successor.AV_GENERATION = "222870ba-ad3c-4cf5-a6de-e1b3a52ab5bc"' in business
    assert 'successor.DETACH = "5aa372a9-1a82-41ff-b25e-00e898cda82a"' in business
    assert "successor.PREDECESSOR_BINDING_REVISION = 9" in business
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 5" in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 272" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 299" in business
    assert 'cutover.OPERATION = "686de66e-fb8f-41c9-ad9d-188bca013a92"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 299" in cutover
    assert "run_definition" not in business + cutover


def test_cx_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cx_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "03652e8e-fb4d-4400-be26-3512ff374418"' in source
    assert 'observer.health.INSTALLATION_ID = "2e374e12-7523-466d-aed7-bdabe8b69aff"' in source
    assert "observer.health.ROUTE_REVISION = 273" in source
    assert "observer.health.GROUP_REVISION = 300" in source
    assert "observer.health.DEFINITION_REVISION = 211" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cx_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_cx_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "0d5d5a7f-6e40-4725-b337-b79acc7d896a"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 211" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 212" in source
    assert "recovery.RECOVERY_REVISION = 70" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 213" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 214" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:d03e6744c2d58040157332409945c6d67073eba4a5b5592a96459d6eeba276f5"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cx_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_cx_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_cx_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_cx_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CX-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cx_snapshot_product_api.py"' in supervisor


def test_cx_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_cx_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "715c69b5-db78-4503-9f6e-2e6a5f132b1d"' in source
    assert 'facts.get("revision") != 4' in source
    assert 'facts.get("definitionRevision") != 213' in source
    assert 'facts.get("recoveryRevision") != 70' in source
    assert "revision=273 AND cutover_group_revision=300" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_cx_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cx_terminal_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = successor.CX_ID" in source
    assert '("715c69b5-db78-4503-9f6e-2e6a5f132b1d", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 214" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 273" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 300" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 275" in source
    assert "retirement.DETACHED_GROUP_REVISION = 302" in source
    assert "run_definition" not in source


def test_cy_replacement_is_bound_to_exact_cx_detach_receipt():
    source = (ROOT / "scripts/a0v_cy_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "2e374e12-7523-466d-aed7-bdabe8b69aff"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "1a1bcf55-b7a9-4869-ac48-052919593d57"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "7753b075-1795-4435-a49c-1fb9f609f8f9"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:21a1c832c8b2b6c462db82efda362a311fb1980402bea9da441156d8fdca5c0c"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 275" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 302" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 9" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "replacement.DEFINITION_REVISION = 214" in source
    assert "run_definition" not in source


def test_cy_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cy_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cy_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "917cd341-96a5-4428-9508-03c716c587ad"' in business
    assert 'successor.AV_GENERATION = "a2fdbdb1-430c-417b-969d-6bd30874d38c"' in business
    assert 'successor.DETACH = "7753b075-1795-4435-a49c-1fb9f609f8f9"' in business
    assert "successor.PREDECESSOR_BINDING_REVISION = 9" in business
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 5" in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 275" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 302" in business
    assert 'cutover.OPERATION = "c7c81fae-1803-4c22-a664-49976472c138"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 302" in cutover
    assert "run_definition" not in business + cutover


def test_cy_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cy_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "37e60676-612b-4632-86a8-82e0869512c7"' in source
    assert 'observer.health.INSTALLATION_ID = "917cd341-96a5-4428-9508-03c716c587ad"' in source
    assert "observer.health.ROUTE_REVISION = 276" in source
    assert "observer.health.GROUP_REVISION = 303" in source
    assert "observer.health.DEFINITION_REVISION = 214" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cy_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_cy_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "2e374e12-7523-466d-aed7-bdabe8b69aff"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 214" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 215" in source
    assert "recovery.RECOVERY_REVISION = 71" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 216" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 217" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:46c6ad1eb001f60bbbb6028920be8457b5d99911d56e5e05411b11fd6cc3e068"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cy_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_cy_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_cy_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_cy_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CY-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cy_snapshot_product_api.py"' in supervisor


def test_cy_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_cy_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "35c2b886-7d38-4ca7-9db6-3f90815420a2"' in source
    assert 'facts.get("revision") != 4' in source
    assert 'facts.get("definitionRevision") != 216' in source
    assert 'facts.get("recoveryRevision") != 71' in source
    assert "revision=276 AND cutover_group_revision=303" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_cy_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cy_terminal_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = successor.CY_ID" in source
    assert '("35c2b886-7d38-4ca7-9db6-3f90815420a2", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 217" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 276" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 303" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 278" in source
    assert "retirement.DETACHED_GROUP_REVISION = 305" in source
    assert "run_definition" not in source


def test_cz_replacement_is_bound_to_exact_cy_detach_receipt():
    source = (ROOT / "scripts/a0v_cz_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "917cd341-96a5-4428-9508-03c716c587ad"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "40cd6259-298f-4aeb-96b1-3ef1cbe50d6e"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "90718b50-d3c8-4712-91c7-41b6ab0358bf"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:932ac829528ff8fa7da0d05239f70eee127df1f7e34e7da4a9d6b44d20899b03"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 278" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 305" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 9" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "replacement.DEFINITION_REVISION = 217" in source
    assert "run_definition" not in source


def test_cz_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_cz_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_cz_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "162e4c29-a24e-4c6b-8da7-9582d090d708"' in business
    assert 'successor.AV_GENERATION = "d1b0f7eb-9677-4d52-a656-a4ae28942976"' in business
    assert 'successor.DETACH = "90718b50-d3c8-4712-91c7-41b6ab0358bf"' in business
    assert "successor.PREDECESSOR_BINDING_REVISION = 9" in business
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 5" in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 278" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 305" in business
    assert 'cutover.OPERATION = "3b1ab629-3d48-4ae0-b685-f0dca64ae8cc"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 305" in cutover
    assert "run_definition" not in business + cutover


def test_cz_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_cz_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "b8bbb317-8b55-4fd4-994c-6a3ae33ccd65"' in source
    assert 'observer.health.INSTALLATION_ID = "162e4c29-a24e-4c6b-8da7-9582d090d708"' in source
    assert "observer.health.ROUTE_REVISION = 279" in source
    assert "observer.health.GROUP_REVISION = 306" in source
    assert "observer.health.DEFINITION_REVISION = 217" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_cz_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_cz_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "917cd341-96a5-4428-9508-03c716c587ad"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 217" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 218" in source
    assert "recovery.RECOVERY_REVISION = 72" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 219" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 220" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:3f085ba307099ce825c33f8b75c8a5a7f62da436ae0b134c3825e3e050ea8131"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_cz_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_cz_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_cz_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_cz_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-CZ-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_cz_snapshot_product_api.py"' in supervisor


def test_cz_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_cz_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "d5ca4825-decb-4263-ac0f-f87d2fe8a7b0"' in source
    assert 'facts.get("revision") != 4' in source
    assert 'facts.get("definitionRevision") != 219' in source
    assert 'facts.get("recoveryRevision") != 72' in source
    assert "revision=279 AND cutover_group_revision=306" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_cz_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_cz_terminal_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = successor.CZ_ID" in source
    assert '("d5ca4825-decb-4263-ac0f-f87d2fe8a7b0", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 220" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 279" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 306" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 281" in source
    assert "retirement.DETACHED_GROUP_REVISION = 308" in source
    assert "run_definition" not in source


def test_da_replacement_is_bound_to_exact_cz_detach_receipt():
    source = (ROOT / "scripts/a0v_da_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "162e4c29-a24e-4c6b-8da7-9582d090d708"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "00211d70-345e-4f90-8d06-81a9a19a4436"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "211b6762-550a-475f-aab6-9f6086786787"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:de79f4af293f2a159d0ac76ef47392761946cf2fb6d7203b8e89143e2b4b65b7"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 281" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 308" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 9" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "replacement.DEFINITION_REVISION = 220" in source
    assert "run_definition" not in source


def test_da_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_da_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_da_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "f4fcdf0b-a37b-419c-9de0-14b08cd7320d"' in business
    assert 'successor.AV_GENERATION = "dbcdd8cb-c6f4-47cc-91f9-1662f54044c0"' in business
    assert 'successor.DETACH = "211b6762-550a-475f-aab6-9f6086786787"' in business
    assert "successor.PREDECESSOR_BINDING_REVISION = 9" in business
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 5" in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 281" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 308" in business
    assert 'cutover.OPERATION = "96e377b4-e6a2-4a2b-be35-9e8a3fa054ce"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 308" in cutover
    assert "run_definition" not in business + cutover


def test_da_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_da_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "e00139ad-ae87-4047-8184-626e93d27b4f"' in source
    assert 'observer.health.INSTALLATION_ID = "f4fcdf0b-a37b-419c-9de0-14b08cd7320d"' in source
    assert "observer.health.ROUTE_REVISION = 282" in source
    assert "observer.health.GROUP_REVISION = 309" in source
    assert "observer.health.DEFINITION_REVISION = 220" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_da_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_da_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "162e4c29-a24e-4c6b-8da7-9582d090d708"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 220" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 221" in source
    assert "recovery.RECOVERY_REVISION = 73" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 222" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 223" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:acdd751b8801f066feb452481c31e6ab629719a7b6df431c82600204450027ce"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_da_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_da_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_da_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_da_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-DA-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_da_snapshot_product_api.py"' in supervisor


def test_da_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_da_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "f61804b2-7863-4371-ac66-80e0a6eb1d0d"' in source
    assert 'facts.get("revision") != 4' in source
    assert 'facts.get("definitionRevision") != 222' in source
    assert 'facts.get("recoveryRevision") != 73' in source
    assert "revision=282 AND cutover_group_revision=309" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_da_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_da_terminal_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = successor.DA_ID" in source
    assert '("f61804b2-7863-4371-ac66-80e0a6eb1d0d", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 223" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 282" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 309" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 284" in source
    assert "retirement.DETACHED_GROUP_REVISION = 311" in source
    assert "run_definition" not in source


def test_db_replacement_is_bound_to_exact_da_detach_receipt():
    source = (ROOT / "scripts/a0v_db_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "f4fcdf0b-a37b-419c-9de0-14b08cd7320d"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "d8d173ad-6d54-4002-b844-003fabf41b69"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "4285f549-aa8f-4d98-b370-ed2cdf040381"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:bf47d2487469ca9eb6092a68dd5ad980ace527d58615490dac59f4f8292b5ab7"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 284" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 311" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 9" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "replacement.DEFINITION_REVISION = 223" in source
    assert "run_definition" not in source


def test_db_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_db_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_db_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "aaaa1ac1-2c35-4c35-8e7b-3ed6cd47f9c8"' in business
    assert 'successor.AV_GENERATION = "c1ae6205-0743-483c-82e3-1d1c95b1ab31"' in business
    assert 'successor.DETACH = "4285f549-aa8f-4d98-b370-ed2cdf040381"' in business
    assert "successor.PREDECESSOR_BINDING_REVISION = 9" in business
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 5" in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 284" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 311" in business
    assert 'cutover.OPERATION = "a717c268-9025-4cd7-b635-0d65fec05e3c"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 311" in cutover
    assert "run_definition" not in business + cutover


def test_db_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_db_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "d9ec3d43-d5a3-46e6-b1f9-c9036a29c764"' in source
    assert 'observer.health.INSTALLATION_ID = "aaaa1ac1-2c35-4c35-8e7b-3ed6cd47f9c8"' in source
    assert "observer.health.ROUTE_REVISION = 285" in source
    assert "observer.health.GROUP_REVISION = 312" in source
    assert "observer.health.DEFINITION_REVISION = 223" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_db_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_db_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "f4fcdf0b-a37b-419c-9de0-14b08cd7320d"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 223" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 224" in source
    assert "recovery.RECOVERY_REVISION = 74" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 225" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 226" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:13d1f720afe37c554549a5c8605448fb3df7a85f519b92fdae367f0653477cdc"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_db_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_db_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_db_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_db_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-DB-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_db_snapshot_product_api.py"' in supervisor


def test_db_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_db_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "1679bef7-84fc-408c-9bb2-d202ba68dc91"' in source
    assert 'facts.get("revision") != 4' in source
    assert 'facts.get("definitionRevision") != 225' in source
    assert 'facts.get("recoveryRevision") != 74' in source
    assert "revision=285 AND cutover_group_revision=312" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_db_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_db_terminal_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = successor.DB_ID" in source
    assert '("1679bef7-84fc-408c-9bb2-d202ba68dc91", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 226" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 285" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 312" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 287" in source
    assert "retirement.DETACHED_GROUP_REVISION = 314" in source
    assert "run_definition" not in source


def test_dc_replacement_is_bound_to_exact_db_detach_receipt():
    source = (ROOT / "scripts/a0v_dc_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "aaaa1ac1-2c35-4c35-8e7b-3ed6cd47f9c8"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "d10cce0c-d412-4e29-95a4-68c010cb2522"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "eceafbf4-d492-43d5-b036-d49e054de133"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:4a74a25a361e745a41bddde502105c030399a716d2f5f6f9ed5f01fa36c4aa54"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 287" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 314" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 9" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "replacement.DEFINITION_REVISION = 226" in source
    assert "run_definition" not in source


def test_dc_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_dc_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_dc_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "02d39eb8-174e-432f-9776-57de7c4436c8"' in business
    assert 'successor.AV_GENERATION = "bd59503f-eb9e-4fe6-a09d-a92a3b924682"' in business
    assert 'successor.DETACH = "eceafbf4-d492-43d5-b036-d49e054de133"' in business
    assert "successor.PREDECESSOR_BINDING_REVISION = 9" in business
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 5" in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 287" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 314" in business
    assert 'cutover.OPERATION = "232d8e1e-9efb-4e26-99ce-e83872539a32"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 314" in cutover
    assert "run_definition" not in business + cutover


def test_dc_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_dc_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "66cdef5b-6105-40b1-ab79-7343f38f1438"' in source
    assert 'observer.health.INSTALLATION_ID = "02d39eb8-174e-432f-9776-57de7c4436c8"' in source
    assert "observer.health.ROUTE_REVISION = 288" in source
    assert "observer.health.GROUP_REVISION = 315" in source
    assert "observer.health.DEFINITION_REVISION = 226" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_dc_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_dc_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "aaaa1ac1-2c35-4c35-8e7b-3ed6cd47f9c8"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 226" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 227" in source
    assert "recovery.RECOVERY_REVISION = 75" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 228" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 229" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:b07f0b5552f66117e4006143999b5ccea65d49efe02b2c0d0d98389bbea405ab"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_dc_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_dc_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_dc_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_dc_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-DC-SNAPSHOT-WORKER-20260921"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_dc_snapshot_product_api.py"' in supervisor


def test_dc_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_dc_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "6092d972-5734-44f1-abe4-56020afb2b4d"' in source
    assert 'facts.get("revision") != 4' in source
    assert 'facts.get("definitionRevision") != 228' in source
    assert 'facts.get("recoveryRevision") != 75' in source
    assert "revision=288 AND cutover_group_revision=315" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_dc_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_dc_terminal_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = successor.DC_ID" in source
    assert '("6092d972-5734-44f1-abe4-56020afb2b4d", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 229" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 288" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 315" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 290" in source
    assert "retirement.DETACHED_GROUP_REVISION = 317" in source
    assert "run_definition" not in source


def test_dd_replacement_is_bound_to_exact_dc_detach_receipt():
    source = (ROOT / "scripts/a0v_dd_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "02d39eb8-174e-432f-9776-57de7c4436c8"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "2a9ad4a5-0da7-488a-a474-bcee64eaa08e"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "c1e5de00-55dc-4eb0-bb57-21524e784c53"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:35973282a15a5ee626e3ef2429b0a5935ec5ca37a0ec3e496bced3d6f91d4e4d"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 290" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 317" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 9" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "replacement.DEFINITION_REVISION = 229" in source
    assert "run_definition" not in source


def test_dd_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_dd_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_dd_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "6e05658b-5d0a-40ae-ab8e-81fcca5269db"' in business
    assert 'successor.AV_GENERATION = "422d2d5b-752a-4182-b1e8-831a8f63c2a1"' in business
    assert 'successor.DETACH = "c1e5de00-55dc-4eb0-bb57-21524e784c53"' in business
    assert "successor.PREDECESSOR_BINDING_REVISION = 9" in business
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 5" in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 290" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 317" in business
    assert 'cutover.OPERATION = "a6716200-8b3f-44d5-a2fc-abf423e970d1"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 317" in cutover
    assert "run_definition" not in business + cutover


def test_dd_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_dd_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "76d2a6e1-1e7a-41cc-bbe4-df3d50e3d346"' in source
    assert 'observer.health.INSTALLATION_ID = "6e05658b-5d0a-40ae-ab8e-81fcca5269db"' in source
    assert "observer.health.ROUTE_REVISION = 291" in source
    assert "observer.health.GROUP_REVISION = 318" in source
    assert "observer.health.DEFINITION_REVISION = 229" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_dd_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_dd_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "02d39eb8-174e-432f-9776-57de7c4436c8"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 229" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 230" in source
    assert "recovery.RECOVERY_REVISION = 76" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 231" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 232" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:21518179c91919d832a5130e47079fdf0395802e3f738be25df26436071df757"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_dd_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_dd_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_dd_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_dd_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-DD-SNAPSHOT-WORKER-20260922"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_dd_snapshot_product_api.py"' in supervisor


def test_dd_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_dd_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "a2396b18-ade6-4c91-912d-1c953d8e17b5"' in source
    assert 'facts.get("revision") != 4' in source
    assert 'facts.get("definitionRevision") != 231' in source
    assert 'facts.get("recoveryRevision") != 76' in source
    assert "revision=291 AND cutover_group_revision=318" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_dd_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_dd_terminal_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = successor.DD_ID" in source
    assert '("a2396b18-ade6-4c91-912d-1c953d8e17b5", 4, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 232" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 291" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 318" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 293" in source
    assert "retirement.DETACHED_GROUP_REVISION = 320" in source
    assert "run_definition" not in source


def test_de_replacement_is_bound_to_exact_dd_detach_receipt():
    source = (ROOT / "scripts/a0v_de_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "6e05658b-5d0a-40ae-ab8e-81fcca5269db"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "8e227c68-9a74-4951-827f-acfef75a948b"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "5211f8d4-e02a-4d06-b806-c1c5144505e8"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:ca77ede8b7156b5dc8a3c0de3598c0807a4cfb06719c94039c444a526eb58f16"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 293" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 320" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 9" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "replacement.DEFINITION_REVISION = 232" in source
    assert "run_definition" not in source


def test_de_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_de_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_de_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "5d993078-18ec-4302-9286-7081a1463cc0"' in business
    assert 'successor.AV_GENERATION = "f5181ad4-e304-4533-aa4a-0f30b3c6dac3"' in business
    assert 'successor.DETACH = "5211f8d4-e02a-4d06-b806-c1c5144505e8"' in business
    assert "successor.PREDECESSOR_BINDING_REVISION = 9" in business
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 5" in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 293" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 320" in business
    assert 'cutover.OPERATION = "2d1c92d1-a525-44a9-b41a-f71b9a9a4bb7"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 320" in cutover
    assert "run_definition" not in business + cutover


def test_de_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_de_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "b7f95379-29b4-419b-8360-c211387812e8"' in source
    assert 'observer.health.INSTALLATION_ID = "5d993078-18ec-4302-9286-7081a1463cc0"' in source
    assert "observer.health.ROUTE_REVISION = 294" in source
    assert "observer.health.GROUP_REVISION = 321" in source
    assert "observer.health.DEFINITION_REVISION = 232" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared


def test_de_saved_snapshot_recovery_is_exact_and_source_read_free():
    source = (ROOT / "scripts/a0v_de_saved_snapshot_recovery.py").read_text(encoding="utf-8")
    assert 'recovery.PREDECESSOR_INSTALLATION_ID = "6e05658b-5d0a-40ae-ab8e-81fcca5269db"' in source
    assert "recovery.PREDECESSOR_DEFINITION_REVISION = 232" in source
    assert "recovery.TRANSFERRED_DEFINITION_REVISION = 233" in source
    assert "recovery.RECOVERY_REVISION = 77" in source
    assert "recovery.ENABLED_DEFINITION_REVISION = 234" in source
    assert "recovery.PAUSED_DEFINITION_REVISION = 235" in source
    assert 'PREDECESSOR_RECOVERY_HASH = "sha256:8227326046fa3efd5f2449b35e0c497fe1b91b77ac253222e617969589879e2a"' in source
    assert '"sourceReads": 0' in source
    assert "run_definition" not in source


def test_de_product_api_and_worker_are_bounded():
    api = (ROOT / "scripts/a0v_de_product_controlled_api.py").read_text(encoding="utf-8")
    flags = (ROOT / "scripts/a0v_bw_product_controlled_api.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/a0v_de_snapshot_product_api.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "scripts/a0v_de_terminal_supervisor.py").read_text(encoding="utf-8")
    assert "controlled.load_launcher" in api
    assert 'AOS_QYH_CRON_ENABLED="false"' in flags
    assert 'AOS_EXTENSION_RUNTIME_HOST_ENABLED="0"' in flags
    assert 'worker.TASK = "A0V-DE-SNAPSHOT-WORKER-20260922"' in worker
    assert 'supervisor.WORKER = ROOT / "scripts/a0v_de_snapshot_product_api.py"' in supervisor


def test_de_attempt_guard_freezes_exact_terminal_boundary():
    source = (ROOT / "scripts/a0v_de_attempt_guard.py").read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "c8ff272f-9fd2-4b54-aef2-87df454e0251"' in source
    assert 'facts.get("revision") != 5' in source
    assert 'facts.get("definitionRevision") != 234' in source
    assert 'facts.get("recoveryRevision") != 77' in source
    assert "revision=294 AND cutover_group_revision=321" in source
    assert '"revision": 4' in source
    assert '"definitionState": "enabled"' in source
    assert "run_definition" not in source


def test_de_terminal_retirement_uses_exact_failed_snapshot_boundary():
    source = (ROOT / "scripts/a0v_de_terminal_retirement.py").read_text(encoding="utf-8")
    assert "retirement.AR_ID = successor.DE_ID" in source
    assert '("c8ff272f-9fd2-4b54-aef2-87df454e0251", 5, "failed"' in source
    assert '"RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"' in source
    assert "retirement.DEFINITION_REVISION = 235" in source
    assert "retirement.ACTIVE_ROUTE_REVISION = 294" in source
    assert "retirement.ACTIVE_GROUP_REVISION = 321" in source
    assert "retirement.DETACHED_ROUTE_REVISION = 296" in source
    assert "retirement.DETACHED_GROUP_REVISION = 323" in source
    assert "run_definition" not in source


def test_df_replacement_is_bound_to_exact_de_detach_receipt():
    source = (ROOT / "scripts/a0v_df_replacement_recovery.py").read_text(encoding="utf-8")
    assert 'replacement.AU_ID = "5d993078-18ec-4302-9286-7081a1463cc0"' in source
    assert 'replacement.AU_DISABLE_OPERATION = "ca18531e-9554-462c-ac76-c8e315d26a7b"' in source
    assert 'replacement.AU_DETACH_RECEIPT = "3cda5059-7651-42ec-8c2a-bf60e3e1dbc1"' in source
    assert 'replacement.AU_DETACH_HASH = "sha256:51d2e740fe62d7e614d73c1c3786b91d2f030d37882a7127f1db14070c884208"' in source
    assert "replacement.PREDECESSOR_ROUTE_REVISION = 296" in source
    assert "replacement.PREDECESSOR_GROUP_REVISION = 323" in source
    assert "replacement.PREDECESSOR_BINDING_REVISION = 9" in source
    assert "replacement.PREDECESSOR_EXECUTION_EPOCH = 5" in source
    assert "replacement.DEFINITION_REVISION = 235" in source
    assert "run_definition" not in source


def test_df_registration_and_cutover_are_exact():
    business = (ROOT / "scripts/a0v_df_successor_business.py").read_text(encoding="utf-8")
    cutover = (ROOT / "scripts/a0v_df_successor_cutover.py").read_text(encoding="utf-8")
    assert 'successor.AV_ID = "a0639f78-af04-4249-97f6-d8507de45f44"' in business
    assert 'successor.AV_GENERATION = "ec18c8c6-2694-44c1-a9c9-ea79ea606e45"' in business
    assert 'successor.DETACH = "3cda5059-7651-42ec-8c2a-bf60e3e1dbc1"' in business
    assert "successor.PREDECESSOR_BINDING_REVISION = 9" in business
    assert "successor.PREDECESSOR_EXECUTION_EPOCH = 5" in business
    assert "successor.PREDECESSOR_ROUTE_REVISION = 296" in business
    assert "successor.PREDECESSOR_GROUP_REVISION = 323" in business
    assert 'cutover.OPERATION = "579e9602-9686-4fba-bd44-8742119e9074"' in cutover
    assert "cutover.PREDECESSOR_GROUP_REVISION = 323" in cutover
    assert "run_definition" not in business + cutover


def test_df_health_observation_is_read_only_and_exact():
    source = (ROOT / "scripts/a0v_df_health_observation.py").read_text(encoding="utf-8")
    shared = (ROOT / "scripts/a0v_bx_health_observation.py").read_text(encoding="utf-8")
    assert 'observer.health.OPERATION = "a17c3056-4740-47d8-9452-b088fbc59dee"' in source
    assert 'observer.health.INSTALLATION_ID = "a0639f78-af04-4249-97f6-d8507de45f44"' in source
    assert "observer.health.ROUTE_REVISION = 297" in source
    assert "observer.health.GROUP_REVISION = 324" in source
    assert "observer.health.DEFINITION_REVISION = 235" in source
    assert "IsolationLevel.REPEATABLE_READ" in shared
    assert "run_definition" not in source + shared

