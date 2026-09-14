"""Original Binding PG rows; model and dependency authorities are named doubles."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone,timedelta
import pytest
from psycopg.rows import dict_row
from psycopg import sql
from psycopg.types.json import Jsonb
from test_lifecycle_pg import database,pytestmark
from aos_api.tenant_scope import TenantScope
from aos_api.aip_agent_registry_contracts import OperationalBindingDependencies,OperationalBindingReadiness,VersionedAssetRef
from aos_api.aip_binding_readiness_service import AipBindingReadinessService
from aos_api.ecommerce_analysis_query_binding import AnalysisQueryBinding

SCOPE=TenantScope('org-org','dev-project')


@pytest.fixture
def binding_case(database,monkeypatch):
    conn,_,schema=database;conn.row_factory=dict_row
    root=Path(__file__).resolve().parents[2]/'alembic/versions'
    conn.execute('CREATE TABLE twa_workspace(org_id text,project_id text,PRIMARY KEY(org_id,project_id))')
    conn.execute('INSERT INTO twa_workspace VALUES(%s,%s)',SCOPE.key)
    for file,prefix in [('aip6_001_agent_skill_registry.py','CREATE TABLE aip_capability_binding ('),
                        ('bind1_001_operational_bindings.py','ALTER TABLE aip_capability_binding\n        ADD COLUMN provider_ref')]:
        nodes=ast.walk(ast.parse((root/file).read_text()))
        statements=[n.value for n in nodes if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith(prefix)]
        assert len(statements)==1;conn.execute(statements[0])
    spec=importlib.util.spec_from_file_location('binding_original_scope',root/'aip6_001_agent_skill_registry.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=SimpleNamespace(execute=conn.execute);module._scope('aip_capability_binding')
    conn.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO aos_runtime').format(sql.Identifier(schema)))
    conn.execute('GRANT SELECT,INSERT,UPDATE ON aip_capability_binding TO aos_runtime')
    conn.execute("SELECT set_config('aos.org_id',%s,false),set_config('aos.project_id',%s,false)",SCOPE.key)
    capability=VersionedAssetRef(asset_type='CapabilityRevision',asset_id='strategy.plan',revision=1,content_hash='1'*64)
    dependencies=OperationalBindingDependencies()
    digest=AipBindingReadinessService.snapshot_hash(capability,dependencies)
    now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    conn.execute('''INSERT INTO aip_capability_binding(org_id,project_id,binding_id,capability_ref,secret_ref,health,
        network_policy_revision,quota_policy_revision,timeout_ms,max_concurrency,status,version,observed_at,
        operational_readiness,readiness_reasons,dependency_snapshot_hash,last_evaluated_at,readiness_expires_at,created_at)
        VALUES(%s,%s,'query-fixture',%s,'vault://fixture-only','healthy','network','quota',1000,1,'active',2,%s,
        'available','[]',%s,%s,%s,%s)''',(*SCOPE.key,Jsonb(capability.model_dump(mode='json',by_alias=True)),now,digest,now,now+timedelta(hours=1),now-timedelta(seconds=1)))
    conn.execute('SET ROLE aos_runtime')
    state={'blocked':False,'revoked':False,'checks':0}
    import aos_api.ecommerce_analysis_query_binding as target
    monkeypatch.setattr(target.PostgresBindingDependencyAuthority,'capability',lambda self,ref:dict(
        lifecycle='published',content_hash=ref.content_hash,required_data_refs=[],required_tool_refs=[]))
    def evaluate(self,scope,ref,deps,*,evaluated_at):
        assert scope==SCOPE
        return OperationalBindingReadiness(readiness='blocked' if state['blocked'] else 'available',
            reasons=['MODEL_ROUTE_BLOCKED'] if state['blocked'] else [],dependencies=deps,
            dependency_snapshot_hash=self.snapshot_hash(ref,deps),evaluated_at=evaluated_at,expires_at=evaluated_at+timedelta(minutes=15))
    monkeypatch.setattr(target.AipBindingReadinessService,'evaluate_capability',evaluate)
    def strict(*args,**kwargs):
        state['checks']+=1
        if state['revoked']:raise ValueError('named dependency revoked')
    monkeypatch.setattr(target.ContentGenerateHostService,'_binding_dependency_authority',strict)
    return conn,state,AnalysisQueryBinding(SCOPE)


def test_current_binding_is_read_only_and_safe(binding_case):
    conn,state,owner=binding_case
    result=owner.run_current(conn,binding_id='query-fixture',execute=lambda x:x)
    assert result.binding_ref.resource_type=='CapabilityBinding'
    assert state['checks']==2 and 'vault' not in str(result)
    assert conn.execute('SELECT version FROM aip_capability_binding').fetchone()['version']==2


@pytest.mark.parametrize('fault',['suspended','unhealthy','stale','hash','canary','model','revoked'])
def test_current_binding_failure_prevents_consumption(binding_case,fault):
    conn,state,owner=binding_case
    if fault=='suspended':conn.execute("UPDATE aip_capability_binding SET status='suspended'")
    if fault=='unhealthy':conn.execute("UPDATE aip_capability_binding SET health='unavailable'")
    if fault=='stale':conn.execute("UPDATE aip_capability_binding SET readiness_expires_at=now()-interval '1 second'")
    if fault=='hash':conn.execute("UPDATE aip_capability_binding SET dependency_snapshot_hash=repeat('f',64)")
    if fault=='canary':conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    if fault=='model':state['blocked']=True
    if fault=='revoked':state['revoked']=True
    with pytest.raises((ValueError,PermissionError)):
        owner.run_current(conn,binding_id='query-fixture',execute=lambda x:pytest.fail('invalid binding consumed'))


@pytest.mark.parametrize('fault',['version','dependency','deferred','output'])
def test_late_binding_change_is_rejected_and_rolled_back(binding_case,fault):
    conn,state,owner=binding_case
    def consume(current):
        if fault=='version':conn.execute('UPDATE aip_capability_binding SET version=version+1')
        if fault=='dependency':state['revoked']=True
        if fault=='deferred':return (x for x in [current])
        if fault=='output':current.binding_ref.revision='999'
    with pytest.raises((ValueError,TypeError,PermissionError)):
        owner.run_current(conn,binding_id='query-fixture',execute=consume)
    assert conn.execute('SELECT version FROM aip_capability_binding').fetchone()['version']==2
