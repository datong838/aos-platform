import pytest
from aos_api.ecommerce_growth_cutover import EcommerceGrowthCutoverStore
from aos_api.ecommerce_growth_registration import FirstDispatchRegistrationService
from aos_api.tenant_scope import TenantScope
from test_ecommerce_growth_cutover_pg import database,pytestmark,_seed,_connection


def control_type():
    from aos_api.ecommerce_growth_cutover_control import EcommerceGrowthCutoverControl
    return EcommerceGrowthCutoverControl


def test_control_requires_real_registration_service():
    store=EcommerceGrowthCutoverStore(lambda scope:pytest.fail('must not connect'))
    with pytest.raises(TypeError):control_type()(store)


@pytest.mark.parametrize('revoke_after_first',[False,True])
def test_current_permission_precedes_new_or_replayed_phase(database,monkeypatch,revoke_after_first):
    # This historical protocol fixture isolates the product caller gate.
    # Current approval consumption has separate rejection and authority tests.
    monkeypatch.setattr('aos_api.ecommerce_growth_cutover_current_approval.require_current_cutover_approval', lambda **kw: None)
    scope=TenantScope('org-org','dev-project');request=_seed(database,scope,pending_receipt=False)
    service=object.__new__(FirstDispatchRegistrationService);checks=[];denied=[]
    def permission(conn,current_scope,installation_id,actor):
        state=conn.execute('SELECT current_user AS role,pg_backend_pid() AS pid,txid_current() AS tx').fetchone()
        assert state['role']=='aos_runtime'
        assert current_scope==scope and installation_id==str(request.target_installation_id) and actor=='runtime-owner'
        checks.append(state)
        if denied:raise PermissionError('revoked')
    monkeypatch.setattr(service,'_authorize_receipt_access',permission)
    store=EcommerceGrowthCutoverStore(_connection(database),schema=database.schema,registration_service=service)
    stages=[]
    original=EcommerceGrowthCutoverStore._approval_authority
    def approval(self,conn,*args,**kwargs):
        stages.append(conn.execute('SELECT pg_backend_pid() AS pid,txid_current() AS tx').fetchone())
        return original(self,conn,*args,**kwargs)
    monkeypatch.setattr(EcommerceGrowthCutoverStore,'_approval_authority',approval)
    control=control_type()(store)
    if revoke_after_first:
        result=control.execute(scope=scope,phase='prepare',request=request,actor='runtime-owner')
        assert result.replayed is False
        again=control.execute(scope=scope,phase='prepare',request=request,actor='runtime-owner')
        assert again.replayed is True and again.receipt_id==result.receipt_id
        assert stages==[dict(pid=checks[0]['pid'],tx=checks[0]['tx'])]
        count=1
    else:count=0
    denied.append(True)
    with pytest.raises(PermissionError,match='revoked'):
        control.execute(scope=scope,phase='prepare',request=request,actor='runtime-owner')
    assert len(checks)==(3 if revoke_after_first else 1)
    assert database.owner.execute('SELECT count(*) AS n FROM extension_dispatch_cutover_operation').fetchone()['n']==count


@pytest.mark.parametrize('finish',['resume','rollback'])
def test_control_all_phases(database,monkeypatch,finish):
    # Phase orchestration with historical approval material, not real approval acceptance.
    monkeypatch.setattr('aos_api.ecommerce_growth_cutover_current_approval.require_current_cutover_approval', lambda **kw: None)
    from test_ecommerce_growth_cutover_pg import _commit_request,_finalize_request,_validate_ref,_rollback_request
    scope=TenantScope('org-org','dev-project');request=_seed(database,scope,pending_receipt=False)
    service=object.__new__(FirstDispatchRegistrationService);checks=[]
    def permission(conn,current_scope,installation_id,actor):
        assert conn.execute('SELECT current_user AS role').fetchone()['role']=='aos_runtime'
        assert current_scope==scope and installation_id==str(request.target_installation_id)
        checks.append(actor)
    monkeypatch.setattr(service,'_authorize_receipt_access',permission)
    control=control_type()(EcommerceGrowthCutoverStore(_connection(database),schema=database.schema,registration_service=service))
    def run(phase,request,**extra):return control.execute(scope=scope,phase=phase,request=request,actor='runtime-owner',**extra)
    prepare=run('prepare',request);command=_commit_request(prepare)
    run('pause',command);commit=run('commit',command)
    if finish=='resume':
        command=_finalize_request(commit);validated=run('validate',command)
        result=run('resume',command,validate_receipt_ref=_validate_ref(validated))
        assert result.status=='resumed'
    else:
        command=_rollback_request(database,scope,prepare,commit)
        run('rollback-prepare',command);result=run('rollback-commit',command)
        assert result.status=='rolled_back'
    assert checks==['runtime-owner']*5


@pytest.mark.parametrize('phase,invalid_request',[('arbitrary',None),('prepare',None),('resume',None)])
def test_invalid_call_never_opens_connection(phase,invalid_request):
    service=object.__new__(FirstDispatchRegistrationService)
    control=control_type()(EcommerceGrowthCutoverStore(lambda scope:pytest.fail('invalid call connected'),registration_service=service))
    with pytest.raises((ValueError,TypeError)):
        control.execute(scope=TenantScope('org-org','dev-project'),phase=phase,request=invalid_request,actor='runtime-owner')


@pytest.mark.parametrize('defect',['path','etag'])
def test_product_target_and_etag_block_before_phase(database,monkeypatch,defect):
    from uuid import uuid4
    from aos_api.ecommerce_growth_cutover import EcommerceGrowthCutoverConflict
    from aos_api.extension_runtime.lifecycle_store import RuntimeRevisionConflict
    scope=TenantScope('org-org','dev-project');request=_seed(database,scope,pending_receipt=False)
    database.owner.execute('UPDATE bundle_installation SET etag_version=5')
    database.owner.execute('GRANT SELECT ON bundle_installation TO aos_runtime')
    service=object.__new__(FirstDispatchRegistrationService)
    monkeypatch.setattr(service,'_authorize_receipt_access',lambda *args:None)
    control=control_type()(EcommerceGrowthCutoverStore(_connection(database),schema=database.schema,registration_service=service))
    with pytest.raises(EcommerceGrowthCutoverConflict if defect=='path' else RuntimeRevisionConflict):
        control.execute(scope=scope,phase='prepare',request=request,actor='runtime-owner',
            expected_installation_id=str(uuid4()) if defect=='path' else str(request.target_installation_id),
            expected_installation_etag=5 if defect=='path' else 6)
    assert database.owner.execute('SELECT count(*) AS n FROM extension_dispatch_cutover_operation').fetchone()['n']==0
