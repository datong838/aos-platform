import ast
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from psycopg.errors import LockNotAvailable
from psycopg import sql
from psycopg.types.json import Jsonb

from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.tenant_scope import TenantScope
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
from test_ecommerce_growth_cutover_pg import database, _connection, _migration, _seed_pending_occurrence
from test_ecommerce_growth_cutover_pg import _resumed_activation, _begin_runtime_disable, _complete_runtime_disable


@pytest.fixture
def dispatch_db(database):
    owner = database.owner
    owner.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
    owner.execute("""CREATE TABLE meta_membership(org_id text NOT NULL,project_id text NOT NULL,
        subject text NOT NULL,role text NOT NULL,PRIMARY KEY(org_id,project_id,subject))""")
    owner.execute("GRANT SELECT ON meta_membership TO aos_extension_maintainer")
    root = Path(__file__).resolve().parents[2]
    source = ast.parse((root / 'alembic/versions/228asset0_evidence_snapshot.py').read_text())
    definitions = [node.value for node in ast.walk(source) if isinstance(node, ast.Constant)
                   and isinstance(node.value, str)
                   and 'CREATE OR REPLACE FUNCTION canonical_asset_registry_jsonb' in node.value]
    assert len(definitions) == 1
    owner.execute(definitions[0])
    owner.execute(sql.SQL('ALTER FUNCTION {}.canonical_asset_registry_jsonb(jsonb) '
                         'SET search_path TO pg_catalog, {}').format(
        sql.Identifier(database.schema), sql.Identifier(database.schema)))
    spec = importlib.util.spec_from_file_location("a0v_054_test", root / "alembic/versions/a0v_054_event_control_dispatch_lifecycle.py")
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    def execute(statement):
        body = statement.replace("public.", database.schema + ".")
        return owner.execute(body)
    migration.op = SimpleNamespace(execute=execute)
    migration.upgrade()
    owner.execute("""CREATE TABLE extension_dispatch_configuration_refresh_receipt(
        org_id text NOT NULL,project_id text NOT NULL,cutover_group_id uuid NOT NULL,
        receipt_id uuid NOT NULL,revision bigint NOT NULL,installation_id uuid NOT NULL,
        generation uuid NOT NULL,activation_operation_id uuid,request jsonb NOT NULL,
        request_hash text NOT NULL,body jsonb NOT NULL,content_hash text NOT NULL,
        PRIMARY KEY(org_id,project_id,cutover_group_id,revision))""")
    owner.execute("GRANT SELECT ON extension_dispatch_configuration_refresh_receipt TO aos_runtime,aos_extension_maintainer")
    spec = importlib.util.spec_from_file_location(
        "a0v_070_test", root / "alembic/versions/a0v_070_event_control_after_configuration_refresh.py")
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=execute)
    migration.upgrade()
    return database


def _seed(database, scope):
    owner = database.owner
    owner.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database.schema)))
    installation, generation, group = uuid4(), uuid4(), uuid4()
    owner.execute("INSERT INTO bundle_installation(org_id,project_id,installation_id) VALUES(%s,%s,%s)",
                  (*scope.key, installation))
    owner.execute("""INSERT INTO bundle_installation_revision(org_id,project_id,installation_pk,revision,state)
        SELECT org_id,project_id,installation_pk,1,'active' FROM bundle_installation
        WHERE org_id=%s AND project_id=%s AND installation_id=%s""", (*scope.key, installation))
    owner.execute("""INSERT INTO extension_runtime_binding(org_id,project_id,installation_id,generation,
        installation_revision,package_lock_ref,profile_ref,config_ref,execution_epoch,desired_state,
        observed_state,enabled,operation_fence,revision)
        VALUES(%s,%s,%s,%s,1,'{}','internal-python-v1','{}',3,'enabled','ready',true,false,6)""",
        (*scope.key, installation, generation))
    owner.execute("INSERT INTO meta_membership VALUES(%s,%s,'fixture-operator','admin')", scope.key)
    for operation in ECOMMERCE_GROWTH_OPERATIONS:
        owner.execute("""INSERT INTO extension_operation_dispatch_binding(org_id,project_id,operation_id,
            handler_kind,installation_id,generation,execution_epoch,operation_fence,revision,
            cutover_group_id,cutover_group_revision,updated_by)
            VALUES(%s,%s,%s,'extension',%s,%s,3,false,2,%s,11,'fixture-operator')""",
            (*scope.key, operation, installation, generation, group))
    return str(installation), str(generation), str(group)


def _request(ids, phase, expected, key):
    installation, generation, group = ids
    return {
        "schemaVersion": "aos.ecommerce.event-control-dispatch/v1",
        "phase": phase,
        "installationRef": {"installationId": installation, "revision": 1,
                            "lockHash": "sha256:" + "b" * 64, "overlayRevision": "overlay-1"},
        "generation": generation,
        "executionEpoch": 3,
        "runtimeRevision": 6,
        "cutoverGroupId": group,
        "expectedGroupRevision": expected,
        "caseId": "case-current",
        "schedulePolicyId": "product-change-current",
        "approvalRef": {"resourceType": "ActionApprovalEvent", "resourceId": "approval-" + phase,
                        "revision": 1, "contentHash": "sha256:" + "a" * 64},
        "idempotencyKey": key,
    }


def _transition(database, scope, request, *, runtime=False):
    with _connection(database, runtime=runtime)(scope) as conn:
        row = conn.execute("SELECT extension_event_control_dispatch_transition_a0v_054(%s,%s) AS receipt",
                           (Jsonb(request), "fixture-operator")).fetchone()
        receipt = row['receipt']
        assert receipt['requestHash'] == canonical_sha256(request)
        assert receipt['contentHash'] == canonical_sha256({
            key: value for key, value in receipt.items() if key not in {'contentHash', 'replayed'}})
        conn.commit()
        return row["receipt"]


def _refresh_transition(database, scope, ids):
    installation, generation, group = ids
    request = {
        'schemaVersion': 'aos.ecommerce.dispatch-configuration-refresh/v1',
        'orgId': scope.org_id, 'projectId': scope.project_id,
        'installationRef': {'installationId': installation},
        'generation': generation, 'cutoverGroupId': group,
        'sourceExecutionEpoch': 3, 'targetExecutionEpoch': 5,
        'targetRuntimeRevision': 9, 'expectedGroupRevision': 12,
        'targetConfigurationRef': {'resourceType': 'ConfigurationRevision',
                                   'resourceId': 'configuration-current', 'revision': 2,
                                   'contentHash': 'sha256:' + 'c' * 64},
        'externalEffectsAllowed': False, 'resumeBusinessRuns': False,
    }
    owner = database.owner
    owner.execute("""UPDATE extension_runtime_binding SET execution_epoch=5,revision=9,
        config_ref=%s WHERE installation_id=%s AND generation=%s""",
        (Jsonb(request['targetConfigurationRef']), installation, generation))
    owner.execute("""UPDATE extension_operation_dispatch_binding SET execution_epoch=5,
        revision=revision+1,cutover_group_revision=13
        WHERE operation_id<>'ecommerce_growth_event_control'""")
    receipt_id = uuid4()
    body = {'request': request}
    owner.execute("""INSERT INTO extension_dispatch_configuration_refresh_receipt(
        org_id,project_id,cutover_group_id,receipt_id,revision,installation_id,generation,
        request,request_hash,body,content_hash) VALUES(%s,%s,%s,%s,1,%s,%s,%s,%s,%s,%s)""",
        (*scope.key, group, receipt_id, installation, generation, Jsonb(request),
         canonical_sha256(request), Jsonb(body), canonical_sha256(body)))
    return request, str(receipt_id), canonical_sha256(body)


def test_expand_replay_fence_and_shrink_are_exact_and_receipted(dispatch_db):
    scope = TenantScope("org-org", "dev-project")
    ids = _seed(dispatch_db, scope)
    expanded = _transition(dispatch_db, scope, _request(ids, "expand", 11, "expand-1"))
    assert expanded["phase"] == "expand" and expanded["targetGroupRevision"] == 12
    assert len(expanded["beforeSnapshot"]) == 9 and len(expanded["afterSnapshot"]) == 10
    replay = _transition(dispatch_db, scope, _request(ids, "expand", 11, "expand-1"))
    assert replay["receiptId"] == expanded["receiptId"] and replay["replayed"] is True
    fenced = _transition(dispatch_db, scope, _request(ids, "fence", 12, "fence-1"))
    control = [row for row in fenced["afterSnapshot"] if row["operationId"] == "ecommerce_growth_event_control"]
    assert len(control) == 1 and control[0]["operationFence"] is True and control[0]["revision"] == 2
    shrunk = _transition(dispatch_db, scope, _request(ids, "shrink", 13, "shrink-1"))
    assert shrunk['priorFenceReceiptRef'] == {
        'receiptId': fenced['receiptId'], 'contentHash': fenced['contentHash']}
    replay_shrink = _transition(dispatch_db, scope, _request(ids, "shrink", 13, "shrink-1"))
    assert replay_shrink['receiptId'] == shrunk['receiptId'] and replay_shrink['replayed']
    assert shrunk["targetGroupRevision"] == 14 and len(shrunk["afterSnapshot"]) == 9
    rows = dispatch_db.owner.execute(sql.SQL("SELECT phase FROM {}.extension_event_control_dispatch_receipt \
        WHERE org_id='org-org' ORDER BY created_at").format(sql.Identifier(dispatch_db.schema))).fetchall()
    assert [row["phase"] for row in rows] == ["expand", "fence", "shrink"]


def test_fence_and_shrink_accept_only_latest_refresh_proven_mixed_epoch(dispatch_db):
    scope = TenantScope('org-org', 'dev-project')
    ids = _seed(dispatch_db, scope)
    _transition(dispatch_db, scope, _request(ids, 'expand', 11, 'refresh-expand'))
    refresh, refresh_id, refresh_hash = _refresh_transition(dispatch_db, scope, ids)
    fence_request = _request(ids, 'fence', 13, 'refresh-fence')
    fence_request['runtimeRevision'] = 9
    fenced = _transition(dispatch_db, scope, fence_request)
    assert fenced['configurationRefreshReceiptRef'] == {
        'resourceType': 'DispatchConfigurationRefreshReceipt', 'resourceId': refresh_id,
        'revision': 1, 'contentHash': refresh_hash}
    business = [row for row in fenced['afterSnapshot']
                if row['operationId'] != 'ecommerce_growth_event_control']
    control = [row for row in fenced['afterSnapshot']
               if row['operationId'] == 'ecommerce_growth_event_control']
    assert len(business) == 9 and all(row['executionEpoch'] == 5
                                      and row['cutoverGroupRevision'] == 14 for row in business)
    assert len(control) == 1 and control[0]['executionEpoch'] == 3
    assert control[0]['operationFence'] is True and control[0]['cutoverGroupRevision'] == 14
    shrink_request = _request(ids, 'shrink', 14, 'refresh-shrink')
    shrink_request['runtimeRevision'] = 9
    shrunk = _transition(dispatch_db, scope, shrink_request)
    assert len(shrunk['afterSnapshot']) == 9
    assert all(row['executionEpoch'] == 5 and row['cutoverGroupRevision'] == 15
               for row in shrunk['afterSnapshot'])
    assert shrunk['drainEvidence']['executionEpoch'] == refresh['sourceExecutionEpoch']


def test_refresh_transition_rejects_business_or_control_drift_without_write(dispatch_db):
    scope = TenantScope('org-org', 'dev-project')
    ids = _seed(dispatch_db, scope)
    _transition(dispatch_db, scope, _request(ids, 'expand', 11, 'refresh-drift-expand'))
    _refresh_transition(dispatch_db, scope, ids)
    request = _request(ids, 'fence', 13, 'refresh-drift-fence')
    request['runtimeRevision'] = 9
    dispatch_db.owner.execute("""UPDATE extension_operation_dispatch_binding
        SET execution_epoch=4 WHERE operation_id='ecommerce_growth_case_put'""")
    before = dispatch_db.owner.execute(
        'SELECT * FROM extension_operation_dispatch_binding ORDER BY operation_id').fetchall()
    with pytest.raises(Exception, match='complete current event dispatch group required'):
        _transition(dispatch_db, scope, request)
    assert dispatch_db.owner.execute(
        'SELECT * FROM extension_operation_dispatch_binding ORDER BY operation_id').fetchall() == before
    assert dispatch_db.owner.execute("""SELECT count(*) AS n
        FROM extension_event_control_dispatch_receipt WHERE phase='fence'""").fetchone()['n'] == 0


def test_phase_drift_canary_and_direct_runtime_call_fail_closed(dispatch_db):
    scope = TenantScope("org-org", "dev-project")
    ids = _seed(dispatch_db, scope)
    with pytest.raises(Exception):
        _transition(dispatch_db, scope, _request(ids, "shrink", 11, "early-shrink"))
    _transition(dispatch_db, scope, _request(ids, "expand", 11, "same-key"))
    drift = _request(ids, "fence", 12, "same-key")
    with pytest.raises(Exception):
        _transition(dispatch_db, scope, drift)
    with pytest.raises(Exception):
        _transition(dispatch_db, TenantScope("dev-org", "dev-project"),
                    _request(ids, "fence", 12, "canary"))
    with pytest.raises(Exception):
        _transition(dispatch_db, scope, _request(ids, "fence", 12, "runtime-direct"), runtime=True)
    count = dispatch_db.owner.execute(sql.SQL("SELECT count(*) AS n FROM {}.extension_event_control_dispatch_receipt \
        WHERE org_id='dev-org'").format(sql.Identifier(dispatch_db.schema))).fetchone()["n"]
    assert count == 0


def test_receipt_hash_preserves_unicode_and_nested_installation(dispatch_db):
    scope = TenantScope('org-org', 'dev-project')
    request = _request(_seed(dispatch_db, scope), 'expand', 11, '真实首链-1')
    request['caseId'] = '栖月汇商品分析'
    request['installationRef']['overlayRevision'] = '租户配置-2'
    receipt = _transition(dispatch_db, scope, request)
    assert receipt['caseId'] == request['caseId']
    assert receipt['installationRef'] == request['installationRef']


def test_receipt_is_immutable(dispatch_db):
    scope = TenantScope("org-org", "dev-project")
    ids = _seed(dispatch_db, scope)
    receipt = _transition(dispatch_db, scope, _request(ids, "expand", 11, "immutable"))
    with pytest.raises(Exception):
        dispatch_db.owner.execute(sql.SQL("UPDATE {}.extension_event_control_dispatch_receipt SET actor='other' \
            WHERE receipt_id=%s").format(sql.Identifier(dispatch_db.schema)), (receipt["receiptId"],))


@pytest.mark.parametrize('drift', ['missing_receipt', 'case', 'snapshot'])
def test_shrink_requires_exact_current_fence_receipt(dispatch_db, drift):
    scope = TenantScope('org-org', 'dev-project')
    ids = _seed(dispatch_db, scope)
    _transition(dispatch_db, scope, _request(ids, 'expand', 11, 'expand-exact'))
    if drift == 'missing_receipt':
        dispatch_db.owner.execute("UPDATE extension_operation_dispatch_binding SET operation_fence=true, "
            "revision=revision+1 WHERE operation_id='ecommerce_growth_event_control'")
        dispatch_db.owner.execute("UPDATE extension_operation_dispatch_binding SET cutover_group_revision=13")
    else:
        _transition(dispatch_db, scope, _request(ids, 'fence', 12, 'fence-exact'))
    request = _request(ids, 'shrink', 13, 'shrink-exact')
    if drift == 'case':
        request['caseId'] = 'different-case'
    if drift == 'snapshot':
        dispatch_db.owner.execute("UPDATE extension_operation_dispatch_binding SET revision=revision+1 "
            "WHERE operation_id='ecommerce_growth_event_control'")
    before = dispatch_db.owner.execute('SELECT * FROM extension_operation_dispatch_binding ORDER BY operation_id').fetchall()
    with pytest.raises(Exception, match='exact fence receipt required'):
        _transition(dispatch_db, scope, request)
    assert dispatch_db.owner.execute('SELECT * FROM extension_operation_dispatch_binding ORDER BY operation_id').fetchall() == before
    assert dispatch_db.owner.execute("SELECT count(*) AS n FROM extension_event_control_dispatch_receipt WHERE phase='shrink'").fetchone()['n'] == 0


def test_fence_waits_for_current_host_transaction_then_retries(dispatch_db):
    scope = TenantScope('org-org', 'dev-project')
    ids = _seed(dispatch_db, scope)
    _transition(dispatch_db, scope, _request(ids, 'expand', 11, 'expand-drain'))
    for filename in ('a0v_028_dispatch_read_lock.py', 'a0v_044_event_control_dispatch_group.py'):
        _migration(dispatch_db.root, filename, dispatch_db.owner, schema=dispatch_db.schema)
    request = _request(ids, 'fence', 12, 'fence-drain')
    with _connection(dispatch_db, runtime=True)(scope) as executing:
        locked = executing.execute('SELECT * FROM extension_dispatch_lock_group_a0v_028(%s)',
                                   (ids[2],)).fetchall()
        assert len(locked) == 10
        with pytest.raises(LockNotAvailable):
            with _connection(dispatch_db)(scope) as fencing:
                fencing.execute("SET LOCAL lock_timeout='100ms'")
                fencing.execute('SELECT extension_event_control_dispatch_transition_a0v_054(%s,%s)',
                                (Jsonb(request), 'fixture-operator'))
        assert dispatch_db.owner.execute("SELECT count(*) AS n FROM extension_event_control_dispatch_receipt WHERE phase='fence'").fetchone()['n'] == 0
        assert dispatch_db.owner.execute("SELECT operation_fence FROM extension_operation_dispatch_binding WHERE operation_id='ecommerce_growth_event_control'").fetchone()['operation_fence'] is False
        executing.commit()
    receipt = _transition(dispatch_db, scope, request)
    assert receipt['phase'] == 'fence' and receipt['replayed'] is False
    assert dispatch_db.owner.execute("SELECT count(*) AS n FROM extension_event_control_dispatch_receipt WHERE phase='fence'").fetchone()['n'] == 1


@pytest.mark.parametrize('lease_minutes', [-5, 5])
def test_shrink_waits_for_persisted_attempt_terminal_state(dispatch_db, lease_minutes):
    scope = TenantScope('org-org', 'dev-project')
    ids = _seed(dispatch_db, scope)
    _transition(dispatch_db, scope, _request(ids, 'expand', 11, 'expand-async'))
    _transition(dispatch_db, scope, _request(ids, 'fence', 12, 'fence-async'))
    owner = dispatch_db.owner
    owner.execute("SELECT set_config('aos.org_id',%s,false),set_config('aos.project_id',%s,false)", scope.key)
    attempt_id = uuid4()
    owner.execute('''INSERT INTO extension_runtime_execution_attempt(
        org_id,project_id,attempt_id,installation_id,generation,execution_epoch,
        operation_kind,operation_key,idempotency_key,request_hash,owner_token_hash,state,lease_until)
        VALUES(%s,%s,%s,%s,%s,3,'signed_read','drain-read','drain-read',%s,%s,'running',%s)''',
        (*scope.key, attempt_id, ids[0], ids[1], 'sha256:'+'7'*64, 'sha256:'+'8'*64,
         datetime.now(timezone.utc)+timedelta(minutes=lease_minutes)))
    request = _request(ids, 'shrink', 13, 'shrink-async')
    before = owner.execute('SELECT * FROM extension_operation_dispatch_binding ORDER BY operation_id').fetchall()
    with pytest.raises(Exception, match='event dispatch target is not drained'):
        _transition(dispatch_db, scope, request)
    assert owner.execute('SELECT * FROM extension_operation_dispatch_binding ORDER BY operation_id').fetchall() == before
    assert owner.execute("SELECT count(*) AS n FROM extension_event_control_dispatch_receipt WHERE phase='shrink'").fetchone()['n'] == 0
    owner.execute("UPDATE extension_runtime_execution_attempt SET state='succeeded',revision=2,completed_at=clock_timestamp() WHERE attempt_id=%s", (attempt_id,))
    receipt = _transition(dispatch_db, scope, request)
    assert receipt['drainEvidence']['runningExecutionAttempts'] == 0
    assert receipt['drainEvidence']['generation'] == ids[1]


@pytest.mark.parametrize('inflight', ['occurrence', 'claimed', 'unknown'])
def test_shrink_waits_for_occurrence_and_dispatch_resolution(dispatch_db, inflight):
    scope = TenantScope('org-org', 'dev-project')
    ids = _seed(dispatch_db, scope)
    _transition(dispatch_db, scope, _request(ids, 'expand', 11, 'expand-occurrence'))
    _transition(dispatch_db, scope, _request(ids, 'fence', 12, 'fence-occurrence'))
    occurrence_id, now = _seed_pending_occurrence(dispatch_db, scope, SimpleNamespace(
        target_installation_id=ids[0], target_generation=ids[1], target_execution_epoch=3))
    owner = dispatch_db.owner
    if inflight == 'occurrence':
        owner.execute("UPDATE automation_occurrence SET status='claimed',claim_owner='test-worker',claim_until=%s WHERE occurrence_id=%s",
                      (now + timedelta(minutes=5), occurrence_id))
    else:
        owner.execute('''INSERT INTO automation_occurrence_dispatch_attempt(
            org_id,project_id,attempt_id,occurrence_id,claim_owner,target_idempotency_key,
            status,claimed_at,claim_until) VALUES(%s,%s,%s,%s,'test-worker','test-dispatch',%s,%s,%s)''',
            (*scope.key, uuid4(), occurrence_id, inflight, now, now+timedelta(minutes=5)))
    request = _request(ids, 'shrink', 13, 'shrink-occurrence')
    with pytest.raises(Exception, match='event dispatch target is not drained'):
        _transition(dispatch_db, scope, request)
    assert owner.execute("SELECT count(*) AS n FROM extension_event_control_dispatch_receipt WHERE phase='shrink'").fetchone()['n'] == 0
    assert owner.execute('SELECT count(*) AS n FROM extension_operation_dispatch_binding').fetchone()['n'] == 10
    owner.execute("UPDATE automation_occurrence SET status='accepted',claim_owner=NULL,claim_until=NULL WHERE occurrence_id=%s", (occurrence_id,))
    owner.execute("UPDATE automation_occurrence_dispatch_attempt SET status='receipt_recorded',resolved_at=clock_timestamp() WHERE occurrence_id=%s", (occurrence_id,))
    receipt = _transition(dispatch_db, scope, request)
    assert receipt['drainEvidence']['claimedOccurrences'] == 0
    assert receipt['drainEvidence']['unresolvedDispatchAttempts'] == 0


def test_optional_expansion_and_shrink_preserve_resumed_disable_detach(dispatch_db):
    scope = TenantScope('org-org', 'dev-project')
    original, _ = _resumed_activation(dispatch_db, scope)
    owner = dispatch_db.owner
    owner.execute("INSERT INTO meta_membership VALUES(%s,%s,'fixture-operator','admin')", scope.key)
    runtime = owner.execute('SELECT * FROM extension_runtime_binding WHERE installation_id=%s AND generation=%s',
                            (original.target_installation_id, original.target_generation)).fetchone()
    group = owner.execute('SELECT cutover_group_id,cutover_group_revision FROM extension_operation_dispatch_binding LIMIT 1').fetchone()
    ids = (str(original.target_installation_id), str(original.target_generation), str(group['cutover_group_id']))
    group_revision = group['cutover_group_revision']
    for offset, phase in enumerate(('expand', 'fence', 'shrink')):
        request = _request(ids, phase, group_revision+offset, 'retirement-'+phase)
        request['installationRef']['revision'] = runtime['installation_revision']
        request['executionEpoch'] = runtime['execution_epoch']
        request['runtimeRevision'] = runtime['revision']
        _transition(dispatch_db, scope, request)
    operation_id, revision = _begin_runtime_disable(dispatch_db, scope, original)
    _complete_runtime_disable(dispatch_db, scope, operation_id, revision)
    with _connection(dispatch_db, runtime=True)(scope) as conn:
        dependent = EcommerceGrowthDisableDependent(schema=dispatch_db.schema)
        args = dict(org_id=scope.org_id, project_id=scope.project_id, runtime_operation_id=operation_id)
        detached = dependent.after_runtime_disabled(conn, **args)
        replay = dependent.after_runtime_disabled(conn, **args)
        conn.commit()
    assert detached.status == 'detached'
    assert replay.replayed and replay.receipt_id == detached.receipt_id
    rows = owner.execute('SELECT * FROM extension_operation_dispatch_binding').fetchall()
    assert len(rows) == 9
    assert all(row['handler_kind'] == 'legacy' and row['installation_id'] is None
               and row['operation_fence'] is False
               and row['cutover_group_revision'] == group_revision+5 for row in rows)
    assert owner.execute('SELECT count(*) AS n FROM extension_dispatch_claim_gate').fetchone()['n'] == 0
