"""Fresh event admission must install its scoped internal action without global seeds."""
import pytest
from test_product_event_control_host_service import host_case,control_governed,governed,service_case,stored,pair,body,call,SCOPE
from aos_api.ecommerce_growth_host_ports import HostTransaction


def test_enable_installs_scoped_action_without_global_action(host_case):
    from aos_api.ecommerce_installed_bootstrap_action import InstalledBootstrapActionCatalog
    conn,_,tx,dispatch,_=host_case
    assert conn.execute("SELECT count(*) n FROM meta_action_type WHERE id='ecommerce_analysis_bootstrap'").fetchone()['n']==0
    result=call(host_case)
    catalog=InstalledBootstrapActionCatalog(tx,SCOPE)
    snapshot=catalog.read_current(installation_id=dispatch.installation_id,generation=dispatch.generation,execution_epoch=dispatch.execution_epoch)
    assert snapshot['id']=='ecommerce_analysis_bootstrap'
    assert snapshot['installedActionRef']['resourceType']=='InstalledActionTypeRevision'
    assert snapshot['objectType']=='Task'
    assert conn.execute("SELECT count(*) n FROM meta_action_type WHERE id='ecommerce_analysis_bootstrap'").fetchone()['n']==0
    assert call(host_case)['replayed']
    assert conn.execute('SELECT count(*) n FROM ecommerce_installed_bootstrap_action').fetchone()['n']==1
    catalog.verify_snapshot(snapshot)


def test_enable_action_catalog_rolls_back_with_transaction(host_case):
    conn,*_=host_case
    with pytest.raises(RuntimeError),conn.transaction():
        call(host_case)
        raise RuntimeError('fail after enable')
    assert conn.execute('SELECT count(*) n FROM ecommerce_installed_bootstrap_action').fetchone()['n']==0
    assert conn.execute('SELECT count(*) n FROM automation_schedule_binding').fetchone()['n']==0


def test_action_definition_is_tenant_bound_and_immutable(host_case):
    from aos_api.ecommerce_installed_bootstrap_action import InstalledBootstrapActionCatalog
    from aos_api.tenant_scope import TenantScope
    conn,_,tx,dispatch,_=host_case;call(host_case)
    with pytest.raises((PermissionError,ValueError)):
        InstalledBootstrapActionCatalog(tx,TenantScope('dev-org','dev-project')).read_current(
            installation_id=dispatch.installation_id,generation=dispatch.generation,execution_epoch=dispatch.execution_epoch)
    with pytest.raises(Exception),conn.transaction():
        conn.execute("UPDATE ecommerce_installed_bootstrap_action SET content_hash='changed'")


@pytest.mark.parametrize('fault',['hash','entry','epoch','fenced','disabled'])
def test_installed_snapshot_rejects_drift(host_case,fault):
    from copy import deepcopy
    from uuid import uuid4
    from aos_api.ecommerce_installed_bootstrap_action import InstalledBootstrapActionCatalog
    conn,_,tx,dispatch,_=host_case
    call(host_case)
    catalog=InstalledBootstrapActionCatalog(tx,SCOPE)
    snapshot=catalog.read_current(installation_id=dispatch.installation_id,generation=dispatch.generation,execution_epoch=dispatch.execution_epoch)
    snapshot=deepcopy(snapshot)
    if fault=='hash': snapshot['installedActionRef']['contentHash']='sha256:'+'0'*64
    elif fault=='entry': snapshot['installedActionRef']['resourceId']=str(uuid4())
    else:
        conn.execute('RESET ROLE')
        statement={'epoch':'execution_epoch=execution_epoch+1','fenced':'operation_fence=true,enabled=false','disabled':'enabled=false'}[fault]
        conn.execute('UPDATE extension_runtime_binding SET '+statement+' WHERE org_id=%s AND project_id=%s',SCOPE.key)
        conn.execute('SET LOCAL ROLE aos_runtime')
    with pytest.raises(ValueError):catalog.verify_snapshot(snapshot)


def test_disabled_historical_enable_replay_is_read_only(host_case):
    conn,_,_,_,command=host_case
    call(host_case)
    call(host_case,dict(command,intent='disable',approvalRef=None,idempotencyKey='stop',expectedBindingRevision=1))
    before=conn.execute('SELECT * FROM ecommerce_installed_bootstrap_action').fetchall()
    assert call(host_case)['replayed']
    assert conn.execute('SELECT * FROM ecommerce_installed_bootstrap_action').fetchall()==before
    assert conn.execute('SELECT enabled FROM automation_schedule_binding').fetchone()['enabled'] is False
