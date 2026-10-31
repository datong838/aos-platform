"""Offline prospective Source bridge; no native, OIDC or actual Source proof."""
from copy import deepcopy
from datetime import timedelta
import hashlib
import re

import pytest

from aos_api import aip_model_route_eval_source_bridge as bridge
from aos_api import aip_model_route_eval_owner as owner
from aos_api import aip_provider_capacity_source_consumer as consumer
from aos_api.aip_provider_capacity_catalog_audit_profile import catalog_occupation_statements
from aos_api.asset_registry.canonical_json import canonical_json
from test_model_route_eval_owner_pg import inputs,OfflineConnection,NOW
from test_model_route_eval_manifest import dump


def test_new_source_compiler_only_creates_two_new_functions_and_narrow_execute_acl():
    before=catalog_occupation_statements();compiled=bridge.source_bridge_statements()
    assert catalog_occupation_statements()==before
    assert len(compiled)==7
    assert all('CREATE OR REPLACE' not in s for s in compiled)
    assert compiled[0].startswith('CREATE FUNCTION '+bridge.READER.split('(')[0]+'(p_raw bytea,p_ref jsonb)')
    assert compiled[4].startswith('CREATE FUNCTION '+bridge.AUDITOR)
    assert all('aos_provider_capacity_occupation' not in s for s in compiled)
    assert all('read_capacity_source_for_occupation' not in s for s in compiled)
    assert all('require_capacity_occupation_source_installation' not in s for s in compiled)
    assert compiled[3]=='GRANT EXECUTE ON FUNCTION '+bridge.READER+' TO aos_runtime'
    assert all(not s.startswith(('GRANT SELECT','GRANT UPDATE','CREATE ROLE','ALTER ROLE','GRANT USAGE')) for s in compiled)
    body=re.search(r'AS \$consumer\$(.*?)\$consumer\$;',compiled[0],re.S)[1]
    assert hashlib.sha256(body.encode()).hexdigest() in compiled[4]
    assert 'PERFORM aos_capacity_publication_private.require_current_source_installation();' in body
    assert 'CAPACITY_OCCUPATION_PROTOCOL_REQUIRED' in body
    assert bridge.SESSION in body


def test_compiler_restores_exact_legacy_bytes_after_only_reviewed_substitutions():
    old=catalog_occupation_statements();new=bridge.source_bridge_statements()
    before=re.search(r'AS \$consumer\$(.*?)\$consumer\$;',old[0],re.S)[1]
    after=re.search(r'AS \$consumer\$(.*?)\$consumer\$;',new[0],re.S)[1]
    original_hash=hashlib.sha256(before.encode()).hexdigest();new_hash=hashlib.sha256(after.encode()).hexdigest()
    restored=tuple(s.replace(bridge.SESSION,'aos_provider_capacity_occupation')
        .replace(bridge.READER.split('(')[0].split('.')[1],'read_capacity_source_for_occupation')
        .replace(bridge.AUDITOR.split('(')[0].split('.')[1],'require_capacity_occupation_source_installation')
        .replace(new_hash,original_hash) for s in new)
    assert restored==old


def test_compiler_refuses_trusted_original_body_drift(monkeypatch):
    original=catalog_occupation_statements()
    monkeypatch.setattr(bridge,'catalog_occupation_statements',lambda:('/* drift */'+original[0],*original[1:]))
    with pytest.raises(bridge.ModelRouteSourceRejected,match='MODEL_ROUTE_SOURCE_COMPILER_DRIFTED'):
        bridge.source_bridge_statements()


class BridgeRows:
    def __init__(self,row):self.row=row
    def fetchone(self):return deepcopy(self.row)


def offline(monkeypatch):
    _,commands,sources=inputs();command=commands[0];source=sources[command.source_ref.asset_id]
    conn=OfflineConnection();conn.context.update(login=bridge.SESSION,time_zone='UTC',replication='origin')
    source_row=dict(asset_id=source.asset_id,revision=source.revision,content_hash=command.source_ref.content_hash,
        source_raw=canonical_json(dump(source)),signature=b'synthetic-signature')
    auth={'calls':0,'changed':False,'error':False,'deadline':NOW+timedelta(hours=1),'bad_packet':False}
    def packet(c):
        auth['calls']+=1
        if auth['error']:raise RuntimeError('secret-should-not-leak')
        if auth['bad_packet']:return b'invalid-auth-packet'
        return canonical_json(dict(protocol='aos-provider-capacity-source-consumption/v1',
            tenant={'orgId':'org-org','projectId':'dev-project'},sourceRef=dump(c.source_ref),
            authentication={'consumerSubject':'synthetic-checker','authenticationExpiresAt':auth['deadline'].isoformat(),
                'nonce':'changed' if auth['changed'] and auth['calls']>1 else 'fixed'}))
    def execute(sql,params=()):
        assert sql.lstrip().startswith('SELECT ')
        conn.calls.append((sql,params))
        if 'FROM public.read_capacity_source_for_model_route_eval' in sql:return BridgeRows(source_row)
        return BridgeRows(conn.context if conn.after is None or len(conn.calls)==1 else conn.after)
    conn.execute=execute
    monkeypatch.setattr(owner,'_require_native_connection',lambda c:None)
    monkeypatch.setattr(bridge,'_require_definitions',lambda c:None)
    monkeypatch.setattr(consumer,'_consumption_packet',packet)
    return conn,command,source,source_row,auth


def test_synthetic_bridge_retains_same_caller_and_reauthenticates_without_returning_credentials(monkeypatch):
    conn,command,source,_,auth=offline(monkeypatch)
    result=bridge.consume_route_eval_capacity_source(conn,command)
    assert result==source and auth['calls']==2
    assert len(conn.calls)==3
    assert 'secret' not in repr(result) and result.execution_allowed is False


@pytest.mark.parametrize('fault',['old_login','wrong_role','cross_tenant','read_only','isolation','xid','pid',
    'database','database_oid','clock','expired','not_yet_valid','hash','reference','row_missing','auth_change','auth_error',
    'auth_expired_db_clock','auth_expired_after_wait','bad_packet'])
def test_synthetic_bridge_refuses_caller_source_or_auth_drift_without_side_effects(monkeypatch,fault):
    conn,command,source,row,auth=offline(monkeypatch)
    if fault=='old_login':conn.context['login']='aos_provider_capacity_occupation'
    elif fault=='wrong_role':conn.context['role']='aos_app'
    elif fault=='cross_tenant':conn.context['org_id']='dev-org'
    elif fault=='read_only':conn.context['readonly']='on'
    elif fault=='isolation':conn.context['isolation']='repeatable read'
    elif fault in ('xid','pid','database','database_oid','clock'):
        conn.after={**conn.context}
        conn.after[{'clock':'now'}.get(fault,fault)]={'xid':'124','pid':100,'database':'other','database_oid':124,'clock':NOW-timedelta(seconds=1)}[fault]
    elif fault=='expired':conn.after={**conn.context,'now':source.valid_until}
    elif fault=='not_yet_valid':conn.context['now']=source.valid_from-timedelta(seconds=1)
    elif fault=='hash':row['content_hash']='0'*64
    elif fault=='reference':row['asset_id']='other'
    elif fault=='row_missing':row.clear()
    elif fault=='auth_change':auth['changed']=True
    elif fault=='auth_error':auth['error']=True
    elif fault=='auth_expired_db_clock':auth['deadline']=NOW
    elif fault=='auth_expired_after_wait':conn.after={**conn.context,'now':auth['deadline']}
    elif fault=='bad_packet':auth['bad_packet']=True
    with pytest.raises(bridge.ModelRouteSourceRejected,match='MODEL_ROUTE_CURRENT_SOURCE_REQUIRED') as error:
        bridge.consume_route_eval_capacity_source(conn,command)
    assert 'secret-should-not-leak' not in str(error.value)


def test_native_source_entry_refuses_fake_connection_before_any_auth(monkeypatch):
    _,commands,_=inputs()
    monkeypatch.setattr(consumer,'_consumption_packet',lambda c:pytest.fail('authenticate only after native boundary'))
    with pytest.raises(bridge.ModelRouteSourceRejected):
        bridge.consume_route_eval_capacity_source(object(),commands[0])


@pytest.mark.parametrize('outside_judge',[False,True])
def test_native_source_prefix_uses_new_fixed_reader_and_original_full_actor_source_checks(monkeypatch,outside_judge):
    import json
    from test_model_route_eval_owner_pg import offline as old_offline,offline_membership
    conn,manifest,commands,sources,seen=old_offline(monkeypatch,outside_judge=outside_judge)
    conn.context.update(login=bridge.SESSION,time_zone='UTC',replication='origin')
    offline_membership(monkeypatch,conn,seen)
    monkeypatch.setattr(bridge,'consume_route_eval_capacity_source',owner.consume_capacity_source_for_occupation)
    monkeypatch.setattr(owner,'consume_capacity_source_for_occupation',lambda *a:pytest.fail('new entry must not borrow old consumer'))
    body=json.loads(manifest.split(b'\n',1)[1]);raw=b'AOS-MODEL-ROUTE-EVAL-CONTEXT-v1\n'+canonical_json(body['context'])
    result=owner.prepare_route_eval_native_sources(conn,expected_database=conn.context['database'],context_bytes=raw,
        application=body['routeApplication'],actor_id='synthetic-consumer',commands=tuple(reversed(commands)))
    assert result.startswith(b'AOS-ROUTE-EVAL-NATIVE-SOURCE-PREFIX-v1\n')
    facts=json.loads(result.split(b'\n',1)[1]);assert facts['executionAllowed'] is False
    assert facts['applicationHash']==hashlib.sha256(canonical_json(body['routeApplication'])).hexdigest()
    assert seen==sorted(sources)+['membership'] and len(facts['sources'])==2
    assert b'a.b.c' not in result and b'synthetic-consumer' not in result


@pytest.mark.parametrize('fault',['old_session','wrong_database','wrong_actor','missing_command','source_coverage','member_denied','after_wait_expired'])
def test_native_source_prefix_cannot_bypass_source_actor_or_membership(monkeypatch,fault):
    import json
    from aos_api.aip_model_eval_action import ModelEvalActionGuard
    from test_model_route_eval_owner_pg import offline as old_offline,offline_membership
    conn,manifest,commands,sources,seen=old_offline(monkeypatch)
    conn.context.update(login=bridge.SESSION,time_zone='UTC',replication='origin')
    offline_membership(monkeypatch,conn,seen)
    monkeypatch.setattr(bridge,'consume_route_eval_capacity_source',owner.consume_capacity_source_for_occupation)
    body=json.loads(manifest.split(b'\n',1)[1]);raw=b'AOS-MODEL-ROUTE-EVAL-CONTEXT-v1\n'+canonical_json(body['context'])
    database=conn.context['database'];actor='synthetic-consumer'
    if fault=='old_session':conn.context['login']='aos_provider_capacity_occupation'
    elif fault=='wrong_database':database='other'
    elif fault=='wrong_actor':actor='other'
    elif fault=='missing_command':commands=commands[:1]
    elif fault=='source_coverage':
        key=commands[0].source_ref.asset_id;sources[key]=sources[key].model_copy(update={'provider_refs':[]})
    elif fault=='member_denied':
        def denied(*a):raise RuntimeError('opaque-source-credential')
        monkeypatch.setattr(ModelEvalActionGuard,'_role',staticmethod(denied))
    elif fault=='after_wait_expired':
        def delayed(*a):conn.after={**conn.context,'now':NOW+timedelta(hours=5)};return 'owner'
        monkeypatch.setattr(ModelEvalActionGuard,'_role',staticmethod(delayed))
    with pytest.raises(owner.GovernedEvalOwnerRejected,match='ROUTE_EVAL_PREAPPROVAL_SOURCE_REQUIRED') as error:
        owner.prepare_route_eval_native_sources(conn,expected_database=database,context_bytes=raw,
            application=body['routeApplication'],actor_id=actor,commands=commands)
    assert 'opaque-source-credential' not in str(error.value)


class CatalogFixture:
    def __init__(self):
        statements=bridge.source_bridge_statements();self.calls=[];self.rows={};self.acls={}
        for signature,index,delimiter,secdef,result_type in ((bridge.READER,0,'consumer',True,2249),(bridge.AUDITOR,4,'occupation',False,2278)):
            self.rows[signature]=dict(prosrc=bridge._body(statements[index],delimiter),rolname=bridge.OWNER,
                prosecdef=secdef,proconfig=['search_path=pg_catalog'],proisstrict=False,provolatile='v',proparallel='u',
                prokind='f',proretset=secdef,prorettype=result_type,args='17 3802' if secdef else '',
                pronargdefaults=0,provariadic=0,proleakproof=False,support=0,lanname='plpgsql')
            self.acls[signature]=[dict(grantee=role,grantor=bridge.OWNER,privilege_type='EXECUTE',is_grantable=False)
                for role in ([bridge.OWNER,'aos_runtime'] if secdef else [bridge.OWNER])]
    def execute(self,sql,params):
        assert sql.lstrip().startswith('SELECT ')
        self.calls.append((sql,params))
        if 'aclexplode' in sql:
            class All:
                def fetchall(inner):return deepcopy(self.acls[params[0]])
            return All()
        return BridgeRows(self.rows[params[0]])


def test_catalog_checks_both_exact_functions_and_all_execute_grants():
    conn=CatalogFixture();bridge._require_definitions(conn)
    assert len(conn.calls)==4


@pytest.mark.parametrize('target',[bridge.READER,bridge.AUDITOR])
@pytest.mark.parametrize('field,value',[
    ('prosrc','drift'),('rolname','aos_app'),('proconfig',['search_path=public']),('proisstrict',True),
    ('provolatile','i'),('proparallel','s'),('prokind','p'),('prorettype',25),('args','25'),
    ('pronargdefaults',1),('provariadic',25),('proleakproof',True),('support',1),('lanname','sql'),
])
def test_catalog_refuses_definition_or_metadata_drift(target,field,value):
    conn=CatalogFixture();conn.rows[target][field]=value
    with pytest.raises(ValueError,match='exact original bridge definition required'):
        bridge._require_definitions(conn)


@pytest.mark.parametrize('fault',['public_execute','grant_option','wrong_grantor','missing_runtime','missing_auditor_owner'])
def test_catalog_refuses_execute_permission_expansion_or_missing_authority(fault):
    conn=CatalogFixture()
    if fault=='public_execute':conn.acls[bridge.READER].append(dict(grantee='PUBLIC',grantor=bridge.OWNER,privilege_type='EXECUTE',is_grantable=False))
    elif fault=='grant_option':conn.acls[bridge.READER][0]['is_grantable']=True
    elif fault=='wrong_grantor':conn.acls[bridge.READER][0]['grantor']='aos_app'
    elif fault=='missing_runtime':conn.acls[bridge.READER]=conn.acls[bridge.READER][:1]
    else:conn.acls[bridge.AUDITOR]=[]
    with pytest.raises(ValueError,match='exact bridge execute privilege required'):
        bridge._require_definitions(conn)


@pytest.mark.parametrize('kind',['route','model2','model3'])
def test_complete_both_model_and_route_manifest_sources_use_dedicated_native_caller(monkeypatch,kind):
    import json
    from test_model_route_eval_owner_pg import offline as old_offline
    conn,manifest,commands,sources,seen=old_offline(monkeypatch,kind)
    conn.context.update(login=bridge.SESSION,time_zone='UTC',replication='origin')
    monkeypatch.setattr(bridge,'consume_route_eval_capacity_source',owner.consume_capacity_source_for_occupation)
    monkeypatch.setattr(owner,'consume_capacity_source_for_occupation',lambda *a:pytest.fail('cannot borrow old consumer'))
    result=owner.prepare_governed_eval_native_sources(conn,expected_database=conn.context['database'],manifest_bytes=manifest,commands=commands)
    assert result.startswith(b'AOS-GOVERNED-EVAL-NATIVE-SOURCE-PREFIX-v1\n')
    facts=json.loads(result.split(b'\n',1)[1]);assert facts['executionAllowed'] is False
    assert facts['manifestHash']==hashlib.sha256(manifest).hexdigest()
    assert seen==sorted(sources) and len(facts['sources'])==2
