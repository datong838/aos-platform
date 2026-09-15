from datetime import datetime, timedelta, timezone
from uuid import uuid4
from types import SimpleNamespace

import pytest
from psycopg import sql

from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
from aos_api.extension_runtime.binding_store import RuntimeBindingStore
from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore
from aos_api.tenant_scope import TenantScope
from test_ecommerce_growth_cutover_pg import database, _connection, _migration, _resumed_activation, _complete_runtime_disable, _seed_pending_occurrence


@pytest.mark.parametrize('inflight', [None, 'occurrence', 'claimed', 'unknown'])
@pytest.mark.parametrize('extra_revisions,extra_epochs', [(1,1), (3,2)])
def test_released_generation_can_formally_retire_without_fixed_activation_offset(database, extra_revisions, extra_epochs, inflight):
    _migration(database.root, 'a0v_055_released_growth_retirement.py', database.owner, schema=database.schema)
    scope = TenantScope('org-org', 'dev-project')
    request, _ = _resumed_activation(database, scope)
    owner = database.owner
    owner.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(database.schema)))
    owner.execute('''UPDATE extension_runtime_binding SET revision=revision+%s,
        execution_epoch=execution_epoch+%s,enabled=false,operation_fence=true,observed_state='unknown'
        WHERE installation_id=%s AND generation=%s''',
        (extra_revisions, extra_epochs, request.target_installation_id, request.target_generation))
    current = owner.execute('SELECT revision FROM extension_runtime_binding WHERE installation_id=%s',
                            (request.target_installation_id,)).fetchone()['revision']
    with _connection(database, runtime=True)(scope) as conn:
        op = RuntimeOperationStore().accept(conn, org_id=scope.org_id, project_id=scope.project_id,
            installation_id=request.target_installation_id,kind='disable',idempotency_key='recovered-disable',
            requested_by='runtime-owner',expected_installation_etag=1,
            deadline=datetime.now(timezone.utc)+timedelta(minutes=5),
            binding_target={'generation':str(request.target_generation),'bindingRevision':current})
        fenced=RuntimeBindingStore().fence(conn,org_id=scope.org_id,project_id=scope.project_id,
            installation_id=request.target_installation_id,generation=request.target_generation,
            operation_id=op.operation_id,expected_operation_revision=op.revision,expected_binding_revision=current)
        receipt=EcommerceGrowthDisableDependent(schema=database.schema).after_runtime_fenced(
            conn,org_id=scope.org_id,project_id=scope.project_id,runtime_operation_id=op.operation_id)
        assert receipt is not None and receipt.status=='fenced'
        conn.commit()
    _complete_runtime_disable(database,scope,op.operation_id,fenced.revision)
    if inflight:
        occurrence_id, now = _seed_pending_occurrence(database, scope, SimpleNamespace(
            target_installation_id=request.target_installation_id,
            target_generation=request.target_generation,
            target_execution_epoch=request.target_execution_epoch + extra_epochs))
        if inflight == 'occurrence':
            owner.execute("UPDATE automation_occurrence SET status='claimed',claim_owner='probe',claim_until=%s WHERE occurrence_id=%s",
                          (now+timedelta(minutes=5),occurrence_id))
        else:
            owner.execute("""INSERT INTO automation_occurrence_dispatch_attempt(
                org_id,project_id,attempt_id,occurrence_id,claim_owner,target_idempotency_key,
                status,claimed_at,claim_until) VALUES(%s,%s,%s,%s,'probe','recovered-probe',%s,%s,%s)""",
                (*scope.key,uuid4(),occurrence_id,inflight,now,now+timedelta(minutes=5)))
        with pytest.raises(Exception, match='disable target execution is not drained'):
            with _connection(database,runtime=True)(scope) as conn:
                EcommerceGrowthDisableDependent(schema=database.schema).after_runtime_disabled(
                    conn,org_id=scope.org_id,project_id=scope.project_id,runtime_operation_id=op.operation_id)
        assert owner.execute("SELECT count(*) AS n FROM extension_dispatch_lifecycle_receipt WHERE phase='detach'").fetchone()['n']==0
        owner.execute("UPDATE automation_occurrence SET status='accepted',claim_owner=NULL,claim_until=NULL WHERE occurrence_id=%s", (occurrence_id,))
        owner.execute("UPDATE automation_occurrence_dispatch_attempt SET status='receipt_recorded',resolved_at=clock_timestamp() WHERE occurrence_id=%s", (occurrence_id,))
    with _connection(database,runtime=True)(scope) as conn:
        dependent=EcommerceGrowthDisableDependent(schema=database.schema)
        args=dict(org_id=scope.org_id,project_id=scope.project_id,runtime_operation_id=op.operation_id)
        receipt=dependent.after_runtime_disabled(conn,**args)
        replay=dependent.after_runtime_disabled(conn,**args)
        assert receipt.status=='detached' and replay.receipt_id==receipt.receipt_id and replay.replayed
        conn.commit()
    rows=owner.execute('SELECT handler_kind,installation_id FROM extension_operation_dispatch_binding').fetchall()
    assert len(rows)==9 and all(r['handler_kind']=='legacy' and r['installation_id'] is None for r in rows)
    assert owner.execute('SELECT count(*) AS n FROM extension_dispatch_claim_gate').fetchone()['n']==0


def test_attached_generation_with_regressed_epoch_cannot_silently_skip_retirement(database):
    _migration(database.root, 'a0v_055_released_growth_retirement.py', database.owner, schema=database.schema)
    scope=TenantScope('org-org','dev-project')
    request,_=_resumed_activation(database,scope)
    database.owner.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(database.schema)))
    database.owner.execute('UPDATE extension_runtime_binding SET execution_epoch=%s WHERE installation_id=%s',
                           (request.target_execution_epoch-1,request.target_installation_id))
    with pytest.raises(Exception,match='attached dispatch has no exact disable activation'):
        with _connection(database,runtime=True)(scope) as conn:
            op=RuntimeOperationStore().accept(conn,org_id=scope.org_id,project_id=scope.project_id,
                installation_id=request.target_installation_id,kind='disable',idempotency_key='regressed',
                requested_by='runtime-owner',expected_installation_etag=1,
                deadline=datetime.now(timezone.utc)+timedelta(minutes=5),
                binding_target={'generation':str(request.target_generation),'bindingRevision':15})
            RuntimeBindingStore().fence(conn,org_id=scope.org_id,project_id=scope.project_id,
                installation_id=request.target_installation_id,generation=request.target_generation,
                operation_id=op.operation_id,expected_operation_revision=op.revision,expected_binding_revision=15)
            EcommerceGrowthDisableDependent(schema=database.schema).after_runtime_fenced(
                conn,org_id=scope.org_id,project_id=scope.project_id,runtime_operation_id=op.operation_id)
    assert database.owner.execute('SELECT count(*) AS n FROM extension_dispatch_lifecycle_receipt').fetchone()['n']==0
