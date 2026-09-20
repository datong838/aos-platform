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
