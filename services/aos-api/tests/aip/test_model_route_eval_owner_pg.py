"""Offline Owner composition. These cases do NOT prove native SCRAM/OIDC/PG.

Actual native execution requires a new resource/fixture plan and separate tests.
Only the private native-connection guard and original Source/auth dependencies
are substituted in these composition cases. Shared psycopg classes are intact.
"""
from datetime import timedelta
import hashlib
import json
from types import SimpleNamespace

import pytest
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySourceV2
from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityConsumptionCommand
from aos_api.asset_registry.canonical_json import canonical_json
from aos_api import aip_model_route_eval_owner as owner
from aos_api.aip_model_route_eval_manifest import compile_eval_execution_manifest
from test_model_route_eval_manifest import route_inputs,model_inputs,NOW,TENANT,dump
from test_provider_capacity_publication_pg import published_v2


def inputs(kind='route',*,outside_judge=False):
    raw,app,budgets=route_inputs(outside_judge=outside_judge) if kind=='route' else (*model_inputs(2 if kind=='model2' else 3),None)
    legs=list(app.calls) if kind=='route' else [app.cases[0].target,app.cases[0].judge]
    sources={};commands=[]
    for i,leg in enumerate(legs):
        data=published_v2();data.update(assetId=leg.source_ref.asset_id,revision=leg.source_ref.revision,
            validFrom=NOW-timedelta(hours=1),validUntil=NOW+timedelta(hours=2),issuedAt=NOW,observedAt=NOW,
            providerRefs=[dump(leg.provider_ref)],accountCandidateRef=dump(leg.physical_account_ref))
        data['deploymentTarget'].update(database='aos_test_owner_source',databaseOid=123)
        data['issuanceContext']['authenticationExpiresAt']=NOW+timedelta(hours=1)
        source=PublishedProviderCapacitySourceV2.model_validate(data);h=hashlib.sha256(canonical_json(dump(source))).hexdigest()
        updated=leg.model_copy(update={'source_ref':leg.source_ref.model_copy(update={'content_hash':h})})
        if kind=='route':app.calls[i]=updated
        else:setattr(app.cases[0],'target' if i==0 else 'judge',updated)
        sources[source.asset_id]=source
        commands.append(ProviderCapacityConsumptionCommand(schemaVersion=1,tenant=TENANT,bearerToken='a.b.c',sourceRef=dump(updated.source_ref)))
    manifest=compile_eval_execution_manifest(raw,execution_id=app.execution_id,checked_at=NOW,
        **({'route_application':app,'route_budget_bindings':budgets} if kind=='route' else {'model_plan':app}))
    return manifest,tuple(commands),sources


class Row:
    def __init__(self,value):self.value=value
    def fetchone(self):return dict(self.value)


class OfflineConnection:
    def __init__(self):
        self.autocommit=False;self.read_only=False;self.closed=False;self.row_factory=dict_row
        self.pgconn=SimpleNamespace(used_password=True)
        self.info=SimpleNamespace(transaction_status=TransactionStatus.INTRANS,get_parameters=lambda:{'require_auth':'scram-sha-256'})
        self.context=dict(database='aos_test_owner_source',database_oid=123,login='aos_provider_capacity_occupation',role='aos_runtime',
            org_id='org-org',project_id='dev-project',isolation='serializable',readonly='off',xid='123',pid=99,now=NOW)
        self.calls=[];self.after=None
    def execute(self,sql,params=()):
        assert sql.lstrip().startswith('SELECT '),'offline Source prefix must only SELECT'
        assert 'pg_control_system' not in sql,'no new runtime control-file privilege'
        self.calls.append((sql,params));value=self.context if len(self.calls)==1 or self.after is None else self.after
        return Row(value)
    def commit(self):raise AssertionError('caller transaction retained')
    rollback=commit
    close=commit


def offline(monkeypatch,kind='route',*,outside_judge=False):
    manifest,commands,sources=inputs(kind,outside_judge=outside_judge);conn=OfflineConnection();seen=[]
    monkeypatch.setattr(owner,'_require_native_connection',lambda value:None)
    def original_consumer(c,command):
        assert c is conn;seen.append(command.source_ref.asset_id);return sources[command.source_ref.asset_id]
    def original_auth(command):
        return canonical_json(dict(protocol='aos-provider-capacity-source-consumption/v1',tenant=TENANT,
            sourceRef=dump(command.source_ref),authentication=dict(consumerSubject='synthetic-consumer',oidcIssuer='https://identity.example.test',
                oidcAudience='capacity-source',authenticationExpiresAt=(NOW+timedelta(hours=1)).isoformat())))
    monkeypatch.setattr(owner,'consume_capacity_source_for_occupation',original_consumer)
    monkeypatch.setattr(owner,'_consumption_packet',original_auth)
    return conn,manifest,commands,sources,seen


def prepare(conn,manifest,commands):
    return owner.prepare_governed_eval_sources(conn,expected_database='aos_test_owner_source',manifest_bytes=manifest,commands=commands)


@pytest.mark.parametrize('kind',['route','model2','model3'])
def test_offline_full_source_set_keeps_original_consumer_and_caller_without_authority(monkeypatch,kind):
    conn,manifest,commands,sources,seen=offline(monkeypatch,kind);original=tuple(dump(c.source_ref) for c in commands)
    result=prepare(conn,manifest,tuple(reversed(commands)));body=json.loads(result.split(b'\n',1)[1])
    assert body['executionAllowed'] is False and body['manifestHash']==hashlib.sha256(manifest).hexdigest()
    assert body['callerXid']=='123' and body['callerPid']==99 and len(body['sources'])==2
    assert seen==sorted(sources) and len(conn.calls)==2
    assert tuple(dump(c.source_ref) for c in commands)==original
    for forbidden in (b'a.b.c',b'bearer',b'synthetic-consumer',b'identity.example.test',b'supplierAccountFingerprint'):
        assert forbidden not in result


@pytest.mark.parametrize('fault',['missing','duplicate','extra','not_tuple','command_extra','command_hash','command_bool_revision','command_tenant'])
def test_offline_source_commands_must_be_complete_exact_native_set(monkeypatch,fault):
    conn,manifest,commands,sources,seen=offline(monkeypatch)
    if fault=='missing':commands=commands[:-1]
    elif fault=='duplicate':commands=(commands[0],commands[0])
    elif fault=='extra':commands=(*commands,commands[0])
    elif fault=='not_tuple':commands=list(commands)
    elif fault=='command_extra':commands=(commands[0].model_copy(update={'approved':True}),commands[1])
    elif fault=='command_hash':commands=(commands[0].model_copy(update={'source_ref':commands[0].source_ref.model_copy(update={'content_hash':'0'*64})}),commands[1])
    elif fault=='command_bool_revision':commands=(commands[0].model_copy(update={'source_ref':commands[0].source_ref.model_copy(update={'revision':True})}),commands[1])
    else:commands=(commands[0].model_copy(update={'tenant':dict(orgId='dev-org',projectId='dev-project')}),commands[1])
    with pytest.raises(owner.GovernedEvalOwnerRejected) as error:prepare(conn,manifest,commands)
    assert 'a.b.c' not in str(error.value) and not seen


@pytest.mark.parametrize('field,value',[('database','wrong'),('database_oid',True),('login','aos_app'),('role','aos_app'),
    ('org_id','dev-org'),('project_id','other'),('isolation','repeatable read'),('readonly','on'),('xid','0'),('pid',True)])
def test_offline_native_context_metadata_boundaries_reject_before_source(monkeypatch,field,value):
    conn,manifest,commands,_,seen=offline(monkeypatch);conn.context[field]=value
    with pytest.raises(owner.GovernedEvalOwnerRejected):prepare(conn,manifest,commands)
    assert not seen


@pytest.mark.parametrize('fault',['source_hash','source_extra','provider','physical_account','future','expired_after_wait','auth_expired','caller_xid','caller_pid','caller_role','caller_database','clock_backwards'])
def test_offline_source_return_and_final_wait_boundaries_reject(monkeypatch,fault):
    conn,manifest,commands,sources,_=offline(monkeypatch);source=sources[commands[0].source_ref.asset_id]
    if fault in {'source_hash','source_extra','provider','physical_account','future'}:
        if fault=='source_hash':change={'asset_id':'other'}
        elif fault=='source_extra':change={'verified':True}
        elif fault=='provider':change={'provider_refs':[source.provider_refs[0].model_copy(update={'asset_id':'other'})]}
        elif fault=='physical_account':change={'account_candidate_ref':source.account_candidate_ref.model_copy(update={'asset_id':'other'})}
        else:change={'issued_at':NOW+timedelta(seconds=1)}
        sources[source.asset_id]=source.model_copy(update=change)
    else:
        conn.after={**conn.context}
        if fault=='expired_after_wait':conn.after['now']=NOW+timedelta(hours=3)
        elif fault=='auth_expired':
            original_auth=owner._consumption_packet
            def expired(command):
                body=json.loads(original_auth(command));body['authentication']['authenticationExpiresAt']=NOW.isoformat();return canonical_json(body)
            monkeypatch.setattr(owner,'_consumption_packet',expired)
        elif fault=='clock_backwards':conn.after['now']=NOW-timedelta(seconds=1)
        else:conn.after[{'caller_xid':'xid','caller_pid':'pid','caller_role':'role','caller_database':'database'}[fault]]='other'
    with pytest.raises(owner.GovernedEvalOwnerRejected) as error:prepare(conn,manifest,commands)
    assert 'a.b.c' not in str(error.value)


def test_unmodified_native_connection_guard_rejects_all_offline_connection_objects():
    conn=OfflineConnection()
    with pytest.raises(owner.GovernedEvalOwnerRejected):owner._require_native_connection(conn)


def reseal_source(manifest,commands,sources,change):
    """Recompile a fresh descriptor using the changed Source's genuine byte hash."""
    body=json.loads(manifest.split(b'\n',1)[1]);ident=commands[0].source_ref.asset_id
    source=PublishedProviderCapacitySourceV2.model_validate(dump(sources[ident].model_copy(update=change)))
    sources[ident]=source;h=hashlib.sha256(canonical_json(dump(source))).hexdigest()
    legs=body['routeApplication']['calls'] if 'routeApplication' in body else [c[p] for c in body['modelPlan']['cases'] for p in ('target','judge')]
    for leg in legs:
        if leg['sourceRef']['assetId']==ident:leg['sourceRef']['contentHash']=h
    commands=tuple(c.model_copy(update={'source_ref':c.source_ref.model_copy(update={'content_hash':h})}) if c.source_ref.asset_id==ident else c for c in commands)
    raw=b'AOS-MODEL-ROUTE-EVAL-CONTEXT-v1\n'+json.dumps(body['context'],sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    kwargs={'model_plan':body['modelPlan']} if 'modelPlan' in body else {'route_application':body['routeApplication'],'route_budget_bindings':body['routeBudgetBindings']}
    return compile_eval_execution_manifest(raw,execution_id=body['executionId'],checked_at=NOW,**kwargs),commands


@pytest.mark.parametrize('fault',['provider','account','deployment','future','source_expiry_after_wait','auth_expiry_after_wait'])
def test_self_consistent_source_hash_cannot_hide_leg_binding_or_wait_expiry(monkeypatch,fault):
    conn,manifest,commands,sources,_=offline(monkeypatch);source=sources[commands[0].source_ref.asset_id]
    if fault=='provider':change={'provider_refs':[source.provider_refs[0].model_copy(update={'asset_id':'other'})]}
    elif fault=='account':change={'account_candidate_ref':source.account_candidate_ref.model_copy(update={'asset_id':'other'})}
    elif fault=='deployment':change={'deployment_target':source.deployment_target.model_copy(update={'database_oid':124})}
    elif fault=='future':change={'issued_at':NOW+timedelta(seconds=1)}
    elif fault=='source_expiry_after_wait':
        change={'valid_until':NOW+timedelta(microseconds=500000)};conn.after={**conn.context,'now':NOW+timedelta(seconds=1)}
    else:
        change={};conn.after={**conn.context,'now':NOW+timedelta(seconds=1)}
        original_auth=owner._consumption_packet
        def deadline(command):
            body=json.loads(original_auth(command));body['authentication']['authenticationExpiresAt']=(NOW+timedelta(microseconds=500000)).isoformat();return canonical_json(body)
        monkeypatch.setattr(owner,'_consumption_packet',deadline)
    manifest,commands=reseal_source(manifest,commands,sources,change)
    with pytest.raises(owner.GovernedEvalOwnerRejected):prepare(conn,manifest,commands)


@pytest.mark.parametrize('fault',['closed','autocommit','readonly','row_factory','transaction','password','require_auth'])
def test_offline_native_guard_property_branches_without_patching_shared_psycopg(monkeypatch,fault):
    real_connection=owner.psycopg.Connection;conn=OfflineConnection()
    # Local dependency substitution tests individual property branches only.
    # The real psycopg module/class is never changed and no native pass is claimed.
    monkeypatch.setattr(owner,'psycopg',SimpleNamespace(Connection=OfflineConnection,Error=owner.psycopg.Error))
    if fault=='closed':conn.closed=True
    elif fault=='autocommit':conn.autocommit=True
    elif fault=='readonly':conn.read_only=True
    elif fault=='row_factory':conn.row_factory=None
    elif fault=='transaction':conn.info.transaction_status=TransactionStatus.IDLE
    elif fault=='password':conn.pgconn.used_password=False
    else:conn.info.get_parameters=lambda:{'require_auth':'none'}
    with pytest.raises(owner.GovernedEvalOwnerRejected):owner._require_native_connection(conn)
    import psycopg
    assert psycopg.Connection is real_connection


def change_second_source(manifest,*,shared):
    body=json.loads(manifest.split(b'\n',1)[1]);legs=body['routeApplication']['calls'] if 'routeApplication' in body else [body['modelPlan']['cases'][0][p] for p in ('target','judge')]
    if shared:
        legs[1]['sourceRef']=dict(legs[0]['sourceRef']);legs[1]['physicalAccountRef']=dict(legs[0]['physicalAccountRef'])
    else:legs[1]['sourceRef']['assetId']=legs[0]['sourceRef']['assetId']
    raw=b'AOS-MODEL-ROUTE-EVAL-CONTEXT-v1\n'+json.dumps(body['context'],sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    kwargs={'model_plan':body['modelPlan']} if 'modelPlan' in body else {'route_application':body['routeApplication'],'route_budget_bindings':body['routeBudgetBindings']}
    return compile_eval_execution_manifest(raw,execution_id=body['executionId'],checked_at=NOW,**kwargs)


@pytest.mark.parametrize('kind',['route','model2','model3'])
def test_offline_shared_exact_source_covers_both_purposes_without_duplicate_consumption(monkeypatch,kind):
    conn,manifest,commands,_,seen=offline(monkeypatch,kind);manifest=change_second_source(manifest,shared=True)
    result=prepare(conn,manifest,(commands[0],));body=json.loads(result.split(b'\n',1)[1])
    assert len(body['sources'])==1 and len(body['sources'][0]['calls'])==2
    assert {c['purpose'] for c in body['sources'][0]['calls']}=={'target','judge'}
    assert seen==[commands[0].source_ref.asset_id]


@pytest.mark.parametrize('kind',['route','model2','model3'])
def test_offline_same_source_identity_cannot_have_conflicting_hashes(monkeypatch,kind):
    conn,manifest,commands,_,seen=offline(monkeypatch,kind);manifest=change_second_source(manifest,shared=False)
    with pytest.raises(owner.GovernedEvalOwnerRejected):prepare(conn,manifest,commands)
    assert not seen


@pytest.mark.parametrize('kind',['runtime','api'])
def test_offline_auth_recheck_exception_never_leaks_opaque_authentication_values(monkeypatch,kind):
    from aos_api.errors import ApiError
    conn,manifest,commands,_,_=offline(monkeypatch)
    def fail(command):
        if kind=='runtime':raise RuntimeError('a.b.c synthetic-consumer authentication backend failed')
        raise ApiError(code='AUTH_INVALID',message='a.b.c synthetic-consumer',status_code=401)
    monkeypatch.setattr(owner,'_consumption_packet',fail)
    with pytest.raises(owner.GovernedEvalOwnerRejected) as error:prepare(conn,manifest,commands)
    assert 'a.b.c' not in str(error.value) and 'synthetic-consumer' not in str(error.value)


def test_offline_external_secret_wrapper_mutation_cannot_change_local_source_command(monkeypatch):
    conn,manifest,commands,_,_=offline(monkeypatch);consumer=owner.consume_capacity_source_for_occupation
    def mutate_original(c,command):
        for original in commands:original.bearer_token._secret_value='d.e.f'
        assert command.bearer_token.get_secret_value()=='a.b.c'
        return consumer(c,command)
    monkeypatch.setattr(owner,'consume_capacity_source_for_occupation',mutate_original)
    prepare(conn,manifest,commands)


def preapproval(conn,manifest,commands,*,actor='synthetic-consumer'):
    body=json.loads(manifest.split(b'\n',1)[1])
    raw=b'AOS-MODEL-ROUTE-EVAL-CONTEXT-v1\n'+canonical_json(body['context'])
    return owner.prepare_route_eval_preapproval_sources(conn,expected_database='aos_test_owner_source',
        context_bytes=raw,application=body.get('routeApplication'),actor_id=actor,commands=commands)


def offline_membership(monkeypatch,conn,seen):
    # This substitutes the original current-membership query only for offline
    # composition; neither a genuine OIDC principal nor native PG is proved.
    from aos_api.aip_model_eval_action import ModelEvalActionGuard
    def role(c,scope,actor):
        assert c is conn and scope.key==('org-org','dev-project') and actor=='synthetic-consumer'
        seen.append('membership');return 'owner'
    monkeypatch.setattr(ModelEvalActionGuard,'_role',staticmethod(role))


@pytest.mark.parametrize('outside_judge',[False,True])
def test_offline_preapproval_sources_bind_real_auth_path_without_held_manifest(monkeypatch,outside_judge):
    conn,manifest,commands,sources,seen=offline(monkeypatch,outside_judge=outside_judge)
    offline_membership(monkeypatch,conn,seen)
    monkeypatch.setattr(owner,'_manifest',lambda _:pytest.fail('preapproval must never require post-approval Manifest'))
    result=preapproval(conn,manifest,tuple(reversed(commands)));body=json.loads(result.split(b'\n',1)[1])
    assert result.startswith(b'AOS-ROUTE-EVAL-PREAPPROVAL-SOURCE-PREFIX-v1\n')
    app=json.loads(manifest.split(b'\n',1)[1])['routeApplication']
    assert body['applicationHash']==hashlib.sha256(canonical_json(app)).hexdigest()
    assert body['contextBindingHash']==app['contextBindingHash'] and body['executionAllowed'] is False
    assert len(body['sources'])==2 and seen==sorted(sources)+['membership']
    assert body['callerXid']=='123' and len(conn.calls)==2
    for forbidden in (b'a.b.c',b'bearer',b'synthetic-consumer',b'identity.example.test',b'supplierAccountFingerprint',b'approvalRef',b'reservationRef'):
        assert forbidden not in result


@pytest.mark.parametrize('actor',['',' unknown','unknown','maker ',True,None,'x'*201,'another-consumer'])
def test_offline_preapproval_rejects_actor_shape_or_verified_oidc_subject_mismatch(monkeypatch,actor):
    conn,manifest,commands,_,seen=offline(monkeypatch)
    with pytest.raises(owner.GovernedEvalOwnerRejected):preapproval(conn,manifest,commands,actor=actor)
    assert not seen


@pytest.mark.parametrize('fault',['member_denied','subject_after_member_wait','auth_after_member_wait',
    'app_after_wait','source_after_wait','xid_after_wait','clock_backwards','bad_packet','auth_exception'])
def test_offline_preapproval_rechecks_source_actor_membership_and_clock_after_waits(monkeypatch,fault):
    from aos_api.aip_model_eval_action import ModelEvalActionGuard
    conn,manifest,commands,sources,seen=offline(monkeypatch);state={'member':False};auth=owner._consumption_packet
    def role(c,scope,actor):
        state['member']=True
        if fault=='member_denied':raise RuntimeError('a.b.c synthetic-consumer denied')
        return 'owner'
    monkeypatch.setattr(ModelEvalActionGuard,'_role',staticmethod(role))
    def current_auth(command):
        if fault=='auth_exception':raise RuntimeError('a.b.c synthetic-consumer failed')
        packet=json.loads(auth(command))
        if fault=='bad_packet':packet['sourceRef']['assetId']='other'
        if state['member'] and fault=='subject_after_member_wait':packet['authentication']['consumerSubject']='other'
        if state['member'] and fault=='auth_after_member_wait':packet['authentication']['authenticationExpiresAt']=NOW.isoformat()
        return canonical_json(packet)
    monkeypatch.setattr(owner,'_consumption_packet',current_auth)
    if fault in {'app_after_wait','source_after_wait'}:
        conn.after={**conn.context,'now':NOW+timedelta(hours=3 if fault=='source_after_wait' else 1)}
    elif fault=='xid_after_wait':conn.after={**conn.context,'xid':'124'}
    elif fault=='clock_backwards':conn.after={**conn.context,'now':NOW-timedelta(seconds=1)}
    with pytest.raises(owner.GovernedEvalOwnerRejected) as error:preapproval(conn,manifest,commands)
    assert 'a.b.c' not in str(error.value) and 'synthetic-consumer' not in str(error.value)


@pytest.mark.parametrize('fault',['missing','extra','not_tuple','provider','account','deployment','future_source','model_context'])
def test_offline_preapproval_keeps_complete_source_and_original_body_binding(monkeypatch,fault):
    conn,manifest,commands,sources,seen=offline(monkeypatch,'model2' if fault=='model_context' else 'route')
    offline_membership(monkeypatch,conn,seen)
    if fault=='missing':commands=commands[:1]
    elif fault=='extra':commands=(*commands,commands[0])
    elif fault=='not_tuple':commands=list(commands)
    elif fault in {'provider','account','deployment','future_source'}:
        src=sources[commands[0].source_ref.asset_id]
        if fault=='provider':change={'provider_refs':[src.provider_refs[0].model_copy(update={'asset_id':'other'})]}
        elif fault=='account':change={'account_candidate_ref':src.account_candidate_ref.model_copy(update={'asset_id':'other'})}
        elif fault=='deployment':change={'deployment_target':src.deployment_target.model_copy(update={'database_oid':124})}
        else:change={'issued_at':NOW+timedelta(seconds=1)}
        manifest,commands=reseal_source(manifest,commands,sources,change)
    with pytest.raises(owner.GovernedEvalOwnerRejected):preapproval(conn,manifest,commands)
    assert 'membership' not in seen or fault=='future_source'


def test_offline_preapproval_shared_source_retains_both_purposes_and_opaque_secret_copy(monkeypatch):
    conn,manifest,commands,_,seen=offline(monkeypatch);manifest=change_second_source(manifest,shared=True)
    offline_membership(monkeypatch,conn,seen);consumer=owner.consume_capacity_source_for_occupation
    def mutate_original(c,command):
        commands[0].bearer_token._secret_value='d.e.f'
        assert command.bearer_token.get_secret_value()=='a.b.c'
        return consumer(c,command)
    monkeypatch.setattr(owner,'consume_capacity_source_for_occupation',mutate_original)
    result=preapproval(conn,manifest,(commands[0],));body=json.loads(result.split(b'\n',1)[1])
    assert len(body['sources'])==1 and len(body['sources'][0]['calls'])==2
    assert seen==[commands[0].source_ref.asset_id,'membership']


def test_preapproval_unmodified_native_guard_rejects_fake_before_any_sql_or_source():
    manifest,commands,_=inputs();conn=OfflineConnection()
    with pytest.raises(owner.GovernedEvalOwnerRejected):preapproval(conn,manifest,commands)
    assert not conn.calls


def material_ref():
    return dict(tenant=TENANT,resourceType='ActionDraftRevision',resourceId='route-material',
        revision=1,headVersion=1,contentHash='a'*64)


@pytest.mark.parametrize('outside_judge',[False,True])
def test_route_action_protocol_reuses_whole_material_and_original_per_operation_budget_contracts(outside_judge):
    from aos_api.aip_model_route_eval_action import (
        build_route_eval_material_draft,build_route_eval_call_proposal,build_route_eval_call_budget_request,
    )
    raw,app,budgets=route_inputs(outside_judge=outside_judge)
    draft=build_route_eval_material_draft(raw,application=app,checked_at=NOW)
    assert draft.action_type_id=='aip_prepare_route_eval_application'
    assert draft.task_id==app.task_ref.resource_id and draft.run_id is None
    assert draft.purpose=='route-eval-material' and draft.expires_at==app.expires_at
    assert draft.payload['application']==dump(app)
    assert draft.payload['context']==json.loads(raw.split(b'\n',1)[1])
    for call,b in zip(app.calls,budgets):
        proposal=build_route_eval_call_proposal(raw,application=app,recipe=call,material_ref=material_ref(),checked_at=NOW)
        request=build_route_eval_call_budget_request(raw,application=app,recipe=call,approval_ref=b.request.approval_ref,checked_at=NOW)
        assert proposal.action_type_id==request.operation_id=='aip_route_eval_'+call.purpose+'_call'
        assert proposal.task_id==request.task_ref.resource_id==app.task_ref.resource_id
        assert dump(request)==dump(b.request)
        assert proposal.payload['callKey']==request.invocation_key
        assert proposal.payload['budgetUpperBoundMinor']==request.upper_bound_minor
        assert proposal.payload['materialRef']==material_ref()
        assert 'application' not in proposal.payload and 'context' not in proposal.payload
        assert not proposal.diff and not proposal.evidence_refs and proposal.risk_hint is None
        assert proposal.expires_at==app.expires_at and proposal.run_id is None
    draft.payload['application']['calls'][0]['identityId']='mutated-returned-description'
    assert app.calls[0].identity_id=='target-executor'


@pytest.mark.parametrize('fault',['tenant','kind','missing_kind','bool_revision','string_revision','bool_head','string_head','hash','extra','resource_whitespace'])
def test_route_action_material_ref_is_complete_strict_and_same_tenant(fault):
    from aos_api.aip_model_route_eval_action import build_route_eval_call_proposal
    raw,app,_=route_inputs();ref=material_ref()
    if fault=='tenant':ref['tenant']={'orgId':'dev-org','projectId':'dev-project'}
    elif fault=='kind':ref['resourceType']='ActionApprovalEvent'
    elif fault=='missing_kind':ref.pop('resourceType')
    elif fault=='bool_revision':ref['revision']=True
    elif fault=='string_revision':ref['revision']='1'
    elif fault=='bool_head':ref['headVersion']=True
    elif fault=='string_head':ref['headVersion']='1'
    elif fault=='hash':ref['contentHash']='sha256:'+'a'*64
    elif fault=='extra':ref['approved']=True
    else:ref['resourceId']=' route-material'
    with pytest.raises(ValueError):
        build_route_eval_call_proposal(raw,application=app,recipe=app.calls[0],material_ref=ref,checked_at=NOW)


@pytest.mark.parametrize('fault',['kind','bool_revision','string_revision','extra','hash'])
def test_route_action_budget_request_never_normalizes_or_invents_an_approval_reference(fault):
    from aos_api.aip_model_route_eval_action import build_route_eval_call_budget_request
    raw,app,budgets=route_inputs();ref=dump(budgets[0].request.approval_ref)
    if fault=='kind':ref['resourceType']='BudgetReservationRevision'
    elif fault=='bool_revision':ref['revision']=True
    elif fault=='string_revision':ref['revision']='1'
    elif fault=='extra':ref['trusted']=True
    else:ref['contentHash']='a'*64
    with pytest.raises(ValueError):
        build_route_eval_call_budget_request(raw,application=app,recipe=app.calls[0],approval_ref=ref,checked_at=NOW)


@pytest.mark.parametrize('fault',['foreign_case','other_provider','extra_recipe','wrong_context','expired'])
def test_route_action_builders_require_complete_currently_descriptive_recipe_inputs(fault):
    from aos_api.aip_model_route_eval_action import build_route_eval_call_proposal,build_route_eval_call_budget_request
    raw,app,budgets=route_inputs();call=app.calls[0]
    if fault=='foreign_case':call=call.model_copy(update={'case_id':'not-this-Suite-case'})
    elif fault=='other_provider':call=call.model_copy(update={'provider_ref':call.provider_ref.model_copy(update={'asset_id':'other'})})
    elif fault=='extra_recipe':call=call.model_copy(update={'approved':True})
    elif fault=='wrong_context':app=app.model_copy(update={'context_binding_hash':'0'*64})
    else:app=app.model_copy(update={'expires_at':NOW})
    with pytest.raises(ValueError):build_route_eval_call_proposal(raw,application=app,recipe=call,material_ref=material_ref(),checked_at=NOW)
    with pytest.raises(ValueError):build_route_eval_call_budget_request(raw,application=app,recipe=call,approval_ref=budgets[0].request.approval_ref,checked_at=NOW)


def offline_original_budget_approval(proposal):
    """Synthetic rows only, while running the unchanged original checker code."""
    from aos_api.aip_budget_reservation_store import canonical_hash
    stable=dict(tenantScope=TENANT,createdBy='synthetic-maker',actionType={'id':proposal.action_type_id},
        taskId=proposal.task_id,runId=None,objectRef=None,purpose=proposal.purpose,riskLevel='R2',
        policy={'makerChecker':True},approvalPolicyHash='b'*64,payload=proposal.payload,diff={},
        evidenceRefs=[],impactPreviewRef=None,actionBindingHash='c'*64,sourceDraftRef=None,
        expiresAt=proposal.expires_at.isoformat())
    h=canonical_hash(stable)
    row=dict(approval_event_id='synthetic-event',proposal_id='synthetic-proposal',proposal_version=1,
        proposal_hash=h,decision='approved',actor_id='synthetic-checker',reason='offline fixture',
        expires_at=proposal.expires_at,created_at=NOW,action_binding_hash='c'*64)
    record=dict(proposal_id='synthetic-proposal',action_type_id=proposal.action_type_id,
        action_type_snapshot=stable['actionType'],task_id=proposal.task_id,run_id=None,object_ref=None,
        purpose=proposal.purpose,risk_level='R2',policy_snapshot=stable['policy'],payload=proposal.payload,
        diff={},evidence_refs=[],impact_preview_id=None,action_binding_hash='c'*64,
        source_draft_id=None,approval_policy_hash='b'*64,proposal_hash=h,status='approved',
        expires_at=proposal.expires_at,created_by='synthetic-maker')
    class OnlySelect:
        def execute(self,sql,params=()):
            assert sql.lstrip().startswith('SELECT ')
            if 'FROM public.aip_action_approval_event' in sql:return Row(row)
            if 'FROM public.aip_action_proposal' in sql:return Row(record)
            if 'FROM public.aip_action_draft' in sql:return Row(dict(proposal_hash=h,snapshot=stable))
            raise AssertionError('unexpected query')
    ref=dict(resourceType='ActionApprovalEvent',resourceId=row['approval_event_id'],revision=1,
        contentHash=canonical_hash(row,prefixed=True))
    return OnlySelect(),ref


@pytest.mark.parametrize('purpose',['target','judge'])
@pytest.mark.parametrize('wrong_action',[False,True])
def test_original_budget_checker_requires_operation_specific_action_without_weakening_original_rule(purpose,wrong_action):
    from aos_api.aip_model_route_eval_action import build_route_eval_call_proposal
    from aos_api.aip_budget_reservation_contracts import BudgetExactRef
    from aos_api.aip_budget_reservation_store import AipBudgetReservationStore,BudgetReservationBlocked
    from aos_api.tenant_scope import TenantScope
    raw,app,_=route_inputs();call=next(c for c in app.calls if c.purpose==purpose)
    proposal=build_route_eval_call_proposal(raw,application=app,recipe=call,material_ref=material_ref(),checked_at=NOW)
    if wrong_action:proposal=proposal.model_copy(update={'action_type_id':'aip_request_route_eval'})
    conn,ref=offline_original_budget_approval(proposal);store=AipBudgetReservationStore()
    def check():
        store._approval_authority(conn,TenantScope('org-org','dev-project'),BudgetExactRef.model_validate(ref),NOW,
            task_ref=app.task_ref,operation_id='aip_route_eval_'+purpose+'_call',upper_bound_minor=call.upper_bound_minor)
    if wrong_action:
        with pytest.raises(BudgetReservationBlocked,match='approval must bind'):check()
    else:check()


def test_route_action_protocol_binds_all_cases_without_collapsing_same_purpose_calls():
    from copy import deepcopy
    from aos_api.aip_model_route_eval_action import build_route_eval_material_draft,build_route_eval_call_proposal
    from aos_api.aip_model_route_eval_manifest import eval_context_binding_hash,route_eval_call_key
    from test_model_route_eval_manifest import context,reseal_context,read
    conn,_=context();second=deepcopy(conn.suite['cases'][0]);second['caseId']='second-case'
    second['inputArtifact'].update(artifactId='input-2',contentHash='d'*64)
    conn.suite['cases'].append(second);reseal_context(conn);raw=read(conn);h=eval_context_binding_hash(raw)
    _,app,_=route_inputs();calls=[]
    for case in conn.suite['cases']:
        for original in app.calls:
            calls.append(original.model_copy(update={'case_id':case['caseId'],
                'input_hash':case['inputArtifact']['contentHash'],
                'target_call_key':route_eval_call_key(app.execution_id,h,case['caseId'],'target') if original.purpose=='judge' else None}))
    app=app.model_copy(update={'context_binding_hash':h,'calls':calls,'upper_bound_minor':12})
    material=build_route_eval_material_draft(raw,application=app,checked_at=NOW)
    proposals=[build_route_eval_call_proposal(raw,application=app,recipe=c,material_ref=material_ref(),checked_at=NOW) for c in app.calls]
    assert len(material.payload['application']['calls'])==len(proposals)==4
    assert len({p.payload['callKey'] for p in proposals})==4
    assert len({p.payload['recipeHash'] for p in proposals})==4
    assert len({p.payload['applicationHash'] for p in proposals})==1
    assert proposals[0].action_type_id==proposals[2].action_type_id
    assert proposals[0].payload!=proposals[2].payload
    assert all('application' not in p.payload and 'context' not in p.payload for p in proposals)


# Reserved Route approval protocol: pure original API boundaries, no DB/Provider.
_ROUTE_MATERIAL='aip_prepare_route_eval_application'
_ROUTE_CALLS=('aip_route_eval_target_call','aip_route_eval_judge_call')
_ROUTE_IDS=(_ROUTE_MATERIAL,*_ROUTE_CALLS)


def _route_ids_at(action,placement):
    return (action,action) if placement=='both' else ((action,'ordinary') if placement=='request' else ('ordinary',action))


@pytest.mark.parametrize('action',_ROUTE_IDS)
@pytest.mark.parametrize('placement',['both','request','snapshot'])
@pytest.mark.parametrize('hint',[None,'R0','R1','R2','R3','R4'])
def test_reserved_route_risk_is_nonexecuting_and_cannot_be_lowered_by_id_or_hint(action,placement,hint):
    from aos_api.aip_action_policy import classify_action_risk
    from aos_api.aip_contracts import ActionRiskLevel
    request_id,snapshot_id=_route_ids_at(action,placement)
    risk=classify_action_risk(request_id,{'id':snapshot_id,'name':'read query'}, {},ActionRiskLevel(hint) if hint else None)
    floor='R1' if action==_ROUTE_MATERIAL else 'R2'
    assert risk.floor.value==floor
    assert risk.level.value>=floor and (hint is None or risk.level.value>=hint)
    assert risk.approval_policy['executionAllowed'] is False
    if action==_ROUTE_MATERIAL:assert risk.approval_policy['draftOnly'] is True
    else:assert risk.approval_policy['makerChecker'] is True


@pytest.mark.parametrize('leaf',_ROUTE_CALLS)
@pytest.mark.parametrize('reverse',[False,True])
def test_contradictory_material_and_call_ids_keep_higher_risk_and_draft_only(leaf,reverse):
    from aos_api.aip_action_policy import classify_action_risk
    pair=(leaf,_ROUTE_MATERIAL) if reverse else (_ROUTE_MATERIAL,leaf)
    risk=classify_action_risk(pair[0],{'id':pair[1]}, {},None)
    assert risk.floor.value=='R2' and risk.approval_policy['executionAllowed'] is False
    assert risk.approval_policy['draftOnly'] is True


@pytest.mark.parametrize('action',_ROUTE_IDS)
@pytest.mark.parametrize('placement',['both','request','snapshot'])
def test_route_request_cannot_enter_original_store_without_complete_dedicated_guard(action,placement):
    from aos_api.aip_action_models import CreateActionProposalRequest
    from aos_api.aip_action_policy import classify_action_risk
    from aos_api.aip_action_store import AipActionStore,AipActionTransitionBlocked
    from aos_api.tenant_scope import TenantScope
    request_id,snapshot_id=_route_ids_at(action,placement)
    body=CreateActionProposalRequest(actionTypeId=request_id,purpose='route-eval',payload={})
    snapshot={'id':snapshot_id};risk=classify_action_risk(request_id,snapshot,{},None)
    class NoSQL:
        def execute(self,*args,**kwargs):raise AssertionError('Route request must be rejected before any SQL')
    with pytest.raises(AipActionTransitionBlocked,match='ROUTE_EVAL_ACTION_PRODUCER_REQUIRED'):
        AipActionStore()._internal_request_binding(NoSQL(),TenantScope('org-org','dev-project'),'maker',body,snapshot,risk)


@pytest.mark.parametrize('action',_ROUTE_IDS)
@pytest.mark.parametrize('placement',['both','request','snapshot'])
@pytest.mark.parametrize('checker',[False,True])
def test_route_replay_or_checker_cannot_fall_back_to_generic_proposal_guard(action,placement,checker):
    from aos_api.aip_action_store import AipActionStore,AipActionTransitionBlocked
    from aos_api.tenant_scope import TenantScope
    request_id,snapshot_id=_route_ids_at(action,placement)
    row={'action_type_id':request_id,'action_type_snapshot':{'id':snapshot_id},'payload':{}}
    class NoSQL:
        def execute(self,*args,**kwargs):raise AssertionError('Route proposal must be rejected before any SQL')
    with pytest.raises(AipActionTransitionBlocked,match='ROUTE_EVAL_ACTION_PRODUCER_REQUIRED'):
        AipActionStore()._internal_proposal_guard(NoSQL(),TenantScope('org-org','dev-project'),'checker' if checker else 'maker',row,checker=checker)


@pytest.mark.parametrize('action',_ROUTE_IDS)
@pytest.mark.parametrize('placement',['both','request','snapshot'])
@pytest.mark.parametrize('entry',['acquire','execute','reconcile','manual_create','manual_decide','compensate'])
def test_generic_route_mutation_entries_reject_before_write_or_adapter(monkeypatch,action,placement,entry):
    from contextlib import contextmanager
    from aos_api import aip_action_execution as execution
    from aos_api.auth import Principal
    from aos_api.aip_action_models import (AcquireExecutionLeaseRequest,CreateManualReconcileCaseRequest,
        DecideManualReconcileCaseRequest,CreateCompensationRequest)
    from aos_api.aip_action_store import AipActionTransitionBlocked
    request_id,snapshot_id=_route_ids_at(action,placement)
    proposal={'proposal_id':'route-proposal','action_type_id':request_id,'action_type_snapshot':{'id':snapshot_id},'risk_level':'R2'}
    receipt={'receipt_id':'r','proposal_id':'route-proposal','lease_id':'lease','status':'unknown','receipt_kind':'initial'}
    case={'case_id':'case','proposal_id':'route-proposal','original_receipt_id':'r','status':'pending','version':1,'maker_id':'other'}
    lease={'lease_id':'lease','proposal_id':'route-proposal','owner_id':'executor','proposal_hash':'a'*64}
    calls=[]
    class Result:
        def __init__(self,value):self.value=value
        def fetchone(self):return self.value
    class Connection:
        def execute(self,statement,params=()):
            calls.append(statement)
            assert statement.lstrip().startswith('SELECT '),'no new Route write is allowed'
            if 'supersedes_receipt_id' in statement:return Result(None)
            if 'FROM aip_action_proposal' in statement:return Result(proposal)
            if 'FROM aip_action_receipt' in statement:return Result(receipt)
            if 'FROM aip_action_execution_lease' in statement:return Result(lease)
            if 'FROM aip_action_manual_reconcile_case' in statement:return Result(case)
            raise AssertionError('Route reached a later generic SQL stage')
        def commit(self):raise AssertionError('Route generic mutation cannot commit')
    @contextmanager
    def connect(scope):yield Connection()
    class NoAdapter:
        def get(self,*args):raise AssertionError('Route cannot resolve generic adapter')
        get_conformant=get
    monkeypatch.setattr(execution,'connect',connect)
    store=SimpleNamespace(_idempotency_lock=lambda *args:None)
    service=execution.AipActionExecutionService(store,NoAdapter())
    principal=Principal('executor','org-org','dev-project',roles=['executor'])
    with pytest.raises(AipActionTransitionBlocked,match='ROUTE_EVAL_DEDICATED_OWNER_REQUIRED'):
        if entry=='acquire':service.acquire_lease(principal,'route-proposal','key',AcquireExecutionLeaseRequest(expectedProposalVersion=1,expectedProposalHash='a'*64))
        elif entry=='execute':service.execute(principal,'lease','a'*64)
        elif entry=='reconcile':service.reconcile(principal,'r','synthetic')
        elif entry=='manual_create':service.create_manual_reconcile_case(principal,'r',CreateManualReconcileCaseRequest())
        elif entry=='manual_decide':service.decide_manual_reconcile_case(principal,'case',DecideManualReconcileCaseRequest(expectedVersion=1,decision='unresolved'))
        else:service.create_compensation(principal,'route-proposal','key',CreateCompensationRequest(receiptId='r',purpose='synthetic',actionTypeId='ordinary'))
    assert all(s.lstrip().startswith('SELECT ') for s in calls)


@pytest.mark.parametrize('action',_ROUTE_IDS)
@pytest.mark.parametrize('placement',['both','request','snapshot'])
@pytest.mark.parametrize('entry',['resolve','attempt','reconcile'])
def test_route_cannot_enter_generic_adapter_resolution_directly(action,placement,entry):
    from aos_api.aip_action_execution import AipActionExecutionService
    from aos_api.aip_action_store import AipActionTransitionBlocked
    request_id,snapshot_id=_route_ids_at(action,placement)
    proposal={'action_type_id':request_id,'action_type_snapshot':{'id':snapshot_id}}
    class NoAdapter:
        def get(self,*args):raise AssertionError('no Route adapter lookup')
        get_conformant=get
    service=AipActionExecutionService(None,NoAdapter())
    with pytest.raises(AipActionTransitionBlocked,match='ROUTE_EVAL_DEDICATED_OWNER_REQUIRED'):
        if entry=='resolve':service._resolve_adapter(proposal,{})
        elif entry=='attempt':service._adapter_for_attempt(proposal,{'adapter_revision_ref':None})
        else:service._adapter_for_reconcile(proposal,{'adapter_revision_ref':None})


def test_original_unreserved_adapter_fallback_is_preserved():
    from aos_api.aip_action_execution import AipActionExecutionService
    adapter=SimpleNamespace(adapter_revision_ref=None);seen=[]
    registry=SimpleNamespace(get=lambda action:seen.append(action) or adapter)
    service=AipActionExecutionService(None,registry);proposal={'action_type_id':'ordinary'}
    assert service._resolve_adapter(proposal,{})==(adapter,{})
    assert service._adapter_for_attempt(proposal,{'adapter_revision_ref':None}) is adapter
    assert service._adapter_for_reconcile(proposal,{'adapter_revision_ref':None}) is adapter
    assert seen==['ordinary']*3


def test_original_model_judge_provider_and_ordinary_risk_decisions_keep_preedit_hash():
    from aos_api.aip_action_policy import classify_action_risk
    from aos_api.aip_contracts import ActionRiskLevel
    cases=[('aip_request_model_eval',{'data':1}),('aip_request_model_judge_call',{'data':1}),
        ('aip_request_provider_capacity',{'data':1}),('aip_review_provider_capacity_source',{'data':1}),
        ('ordinary_draft',{'data':1}),('refund_payment',{'data':1}),('price_discount',{'data':1}),
        ('read_query',{}),('ecommerce_growth_content_generate',{'firstContentReviewKey':'synthetic','firstContentSources':[]})]
    rows=[]
    for ident,payload in cases:
        for hint in [None,ActionRiskLevel.R0,ActionRiskLevel.R3,ActionRiskLevel.R4]:
            x=classify_action_risk(ident,{'id':ident},payload,hint)
            rows.append(dict(action=ident,hint=hint.value if hint else None,level=x.level.value,
                floor=x.floor.value,reasons=list(x.reasons),policy=x.approval_policy))
    assert hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()=='be6776afc2259c6a2730d59cabe2a6774d00efd72d9b383d0138e189780ce646'


def test_route_guard_injection_requires_exact_type_and_routes_request_and_proposal(monkeypatch):
    from aos_api import aip_model_route_eval_action as route_action
    from aos_api.aip_action_store import AipActionStore
    from aos_api.tenant_scope import TenantScope
    with pytest.raises(TypeError,match='exact Route Eval Action guard required'):
        AipActionStore(route_eval_guard=object())
    guard=route_action.RouteEvalActionGuard();seen=[]
    def request(self,conn,scope,actor,body,snapshot,risk):
        seen.append(('request',conn,scope,actor,body.action_type_id,snapshot['id']))
        return 'route-binding'
    def proposal(self,conn,scope,actor,row,*,checker):
        seen.append(('proposal',conn,scope,actor,row['action_type_id'],checker))
        return ('owner',) if checker else None
    monkeypatch.setattr(route_action.RouteEvalActionGuard,'check_request',request)
    monkeypatch.setattr(route_action.RouteEvalActionGuard,'check_proposal',proposal)
    store=AipActionStore(route_eval_guard=guard);scope=TenantScope('org-org','dev-project');conn=object()
    body=SimpleNamespace(action_type_id='aip_route_eval_target_call')
    snapshot={'id':'aip_route_eval_target_call'}
    assert store._internal_request_binding(conn,scope,'maker',body,snapshot,object())=='route-binding'
    row={'action_type_id':'aip_route_eval_judge_call','action_type_snapshot':{'id':'aip_route_eval_judge_call'}}
    assert store._internal_proposal_guard(conn,scope,'checker',row,checker=True)==('owner',)
    assert [item[0] for item in seen]==['request','proposal']


def test_route_guard_prelock_runs_before_action_idempotency_or_proposal_lock(monkeypatch):
    from contextlib import contextmanager
    from aos_api import aip_model_route_eval_action as route_action
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_action_store import AipActionStore,AipActionTransitionBlocked
    from aos_api.tenant_scope import TenantScope
    guard=route_action.RouteEvalActionGuard();calls=[]
    def prelock(self,conn,scope,actor_id,proposal_id):
        calls.append(('prelock',actor_id,proposal_id))
        raise AipActionTransitionBlocked('ROUTE_PRELOCK_SENTINEL')
    monkeypatch.setattr(route_action.RouteEvalActionGuard,'prelock_decision',prelock)
    class NoSQL:
        def execute(self,*args,**kwargs):raise AssertionError('prelock sentinel must stop before Action SQL')
    @contextmanager
    def connect(scope):yield NoSQL()
    store=AipActionStore(connect,route_eval_guard=guard)
    monkeypatch.setattr(store,'_idempotency_lock',lambda *args:calls.append(('idempotency',)))
    with pytest.raises(AipActionTransitionBlocked,match='ROUTE_PRELOCK_SENTINEL'):
        store.decide(TenantScope('org-org','dev-project'),'checker','proposal','key',
            DecideActionProposalRequest(decision='approved',expectedProposalVersion=1,expectedProposalHash='a'*64))
    assert calls==[('prelock','checker','proposal')]


def test_route_guard_asserts_prelocked_fingerprint_after_proposal_row_lock(monkeypatch):
    from contextlib import contextmanager
    from aos_api import aip_model_route_eval_action as route_action
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_action_store import AipActionStore,AipActionTransitionBlocked
    from aos_api.tenant_scope import TenantScope
    guard=route_action.RouteEvalActionGuard();calls=[]
    monkeypatch.setattr(route_action.RouteEvalActionGuard,'prelock_decision',
        lambda self,conn,scope,actor_id,proposal_id:
            calls.append(('prelock',actor_id,proposal_id)) or ('fingerprint',))
    def checked(self,row,fingerprint):
        calls.append(('assert',fingerprint,row['proposal_id']))
        raise AipActionTransitionBlocked('ROUTE_ASSERT_SENTINEL')
    monkeypatch.setattr(route_action.RouteEvalActionGuard,'assert_prelocked_proposal',checked)
    class Result:
        def fetchone(self):return {'proposal_id':'proposal'}
    class Connection:
        def execute(self,sql,params=()):
            calls.append(('sql',sql))
            assert 'FOR UPDATE' in sql
            return Result()
    @contextmanager
    def connect(scope):yield Connection()
    store=AipActionStore(connect,route_eval_guard=guard)
    monkeypatch.setattr(store,'_idempotency_lock',lambda *args:calls.append(('idempotency',)))
    with pytest.raises(AipActionTransitionBlocked,match='ROUTE_ASSERT_SENTINEL'):
        store.decide(TenantScope('org-org','dev-project'),'checker','proposal','key',
            DecideActionProposalRequest(decision='approved',expectedProposalVersion=1,expectedProposalHash='a'*64))
    assert calls[0]==('prelock','checker','proposal') and calls[1]==('idempotency',)
    assert calls[2][0]=='sql' and calls[3]==('assert',('fingerprint',),'proposal')


def test_route_guard_g4a_allows_only_exact_idempotent_replay_after_one_approved_event(monkeypatch):
    from contextlib import contextmanager
    from datetime import datetime,timezone,timedelta
    from aos_api import aip_model_route_eval_action as route_action
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_action_store import AipActionStore,AipActionTransitionBlocked
    from aos_api.tenant_scope import TenantScope
    guard=route_action.RouteEvalActionGuard();now=datetime.now(timezone.utc)
    row={'proposal_id':'proposal','action_type_id':'aip_route_eval_target_call',
        'action_type_snapshot':{'id':'aip_route_eval_target_call'},'created_by':'maker',
        'status':'approved','expires_at':now+timedelta(hours=1),'version':2,
        'proposal_hash':'a'*64,'policy_snapshot':{'minimumApprovals':1,'maxApprovalSeconds':900},
        'source_draft_id':None,'action_binding_hash':'b'*64,'approval_policy_hash':None}
    existing={'approval_event_id':'approval-existing','actor_id':'checker-1','slot_id':'checker.1'}
    class Result:
        def __init__(self,one=None,many=None):self.one=one;self.many=many
        def fetchone(self):return self.one
        def fetchall(self):return self.many or []
    class Connection:
        def execute(self,sql,params=()):
            if 'FROM aip_action_proposal' in sql and 'FOR UPDATE' in sql:return Result(row)
            if 'FROM aip_action_approval_event' in sql and 'idempotency_key' in sql:return Result(None)
            if "actor_id=%s AND decision='approved'" in sql:return Result(None)
            if 'SELECT approval_event_id,actor_id,slot_id' in sql:return Result(many=[existing])
            raise AssertionError('a second Route approval event must not be written: '+sql)
    @contextmanager
    def connect(scope):yield Connection()
    store=AipActionStore(connect,route_eval_guard=guard)
    monkeypatch.setattr(route_action.RouteEvalActionGuard,'prelock_decision',
        lambda *args:'fingerprint')
    monkeypatch.setattr(route_action.RouteEvalActionGuard,'assert_prelocked_proposal',
        lambda *args:None)
    monkeypatch.setattr(store,'_idempotency_lock',lambda *args:None)
    monkeypatch.setattr(store,'_internal_proposal_guard',lambda *args,**kwargs:('owner',))
    monkeypatch.setattr(store,'assert_bound_impact_preview_current',lambda *args:None)
    with pytest.raises(AipActionTransitionBlocked,match='ROUTE_EVAL_UNIQUE_APPROVAL_REQUIRED'):
        store.decide(TenantScope('org-org','dev-project'),'checker-2','proposal','new-key',
            DecideActionProposalRequest(decision='approved',expectedProposalVersion=2,
                expectedProposalHash='a'*64))


@pytest.mark.parametrize('actor,allowed',[('checker-1',True),('checker-2',False)])
def test_route_guard_g4a_idempotent_approval_replay_is_bound_to_original_checker(monkeypatch,actor,allowed):
    from contextlib import contextmanager
    from datetime import datetime,timezone,timedelta
    from aos_api import aip_model_route_eval_action as route_action
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_action_store import AipActionStore,AipActionTransitionBlocked,canonical_hash
    from aos_api.tenant_scope import TenantScope
    guard=route_action.RouteEvalActionGuard();body=DecideActionProposalRequest(
        decision='approved',expectedProposalVersion=2,expectedProposalHash='a'*64)
    row={'proposal_id':'proposal','action_type_id':'aip_route_eval_target_call',
        'action_type_snapshot':{'id':'aip_route_eval_target_call'},'created_by':'maker'}
    replay={'proposal_id':'proposal','request_hash':canonical_hash(
        body.model_dump(mode='json',by_alias=True)),'actor_id':'checker-1'}
    class Result:
        def __init__(self,value):self.value=value
        def fetchone(self):return self.value
    class Connection:
        def execute(self,sql,params=()):
            if 'FROM aip_action_proposal' in sql:return Result(row)
            if 'FROM aip_action_approval_event' in sql and 'idempotency_key' in sql:return Result(replay)
            raise AssertionError('exact replay must return before new event SQL')
    @contextmanager
    def connect(scope):yield Connection()
    store=AipActionStore(connect,route_eval_guard=guard)
    monkeypatch.setattr(route_action.RouteEvalActionGuard,'prelock_decision',lambda *args:'fingerprint')
    monkeypatch.setattr(route_action.RouteEvalActionGuard,'assert_prelocked_proposal',lambda *args:None)
    monkeypatch.setattr(store,'_idempotency_lock',lambda *args:None)
    monkeypatch.setattr(store,'_internal_proposal_guard',lambda *args,**kwargs:('owner',))
    monkeypatch.setattr(store,'_bundle',lambda *args:'original-bundle')
    if allowed:
        assert store.decide(TenantScope('org-org','dev-project'),actor,'proposal','same-key',body)=='original-bundle'
    else:
        with pytest.raises(AipActionTransitionBlocked,match='ROUTE_EVAL_CHECKER_REPLAY_DRIFTED'):
            store.decide(TenantScope('org-org','dev-project'),actor,'proposal','same-key',body)


def test_route_guard_budget_refactor_keeps_original_reserve_store_semantics(monkeypatch):
    from aos_api import aip_model_route_eval_action as route_action
    from aos_api.aip_budget_reservation_store import AipBudgetReservationStore
    from aos_api.tenant_scope import TenantScope
    guard=route_action.RouteEvalActionGuard();scope=TenantScope('org-org','dev-project')
    request=SimpleNamespace(invocation_key='exact-call');conn=object();seen=[]
    monkeypatch.setattr(route_action.RouteEvalActionGuard,'_current_call_budget_request',
        lambda self,actual_conn,actual_scope,approval:
            (request,'maker') if (actual_conn,actual_scope,approval)==(conn,scope,'approval')
            else pytest.fail('exact current request inputs required'))
    monkeypatch.setattr(AipBudgetReservationStore,'reserve_in_transaction',
        lambda self,actual_conn,actual_scope,actual_request,*,actor:
            seen.append((actual_conn,actual_scope,actual_request,actor)) or 'original-reservation')
    assert guard.reserve_current_call_budget(conn,scope,'approval')=='original-reservation'
    assert seen==[(conn,scope,request,'maker')]


def _current_admission_fixture(monkeypatch,*,missing=False):
    from aos_api.aip_budget_reservation_store import AipBudgetReservationStore
    from aos_api.aip_model_route_eval_action import RouteEvalActionGuard
    from aos_api.aip_model_route_eval_manifest import RouteEvalBudgetBinding
    from aos_api.tenant_scope import TenantScope
    raw,application,budgets=route_inputs()
    manifest=compile_eval_execution_manifest(raw,execution_id=application.execution_id,
        checked_at=NOW,route_application=application,route_budget_bindings=budgets)
    body=json.loads(manifest.split(b'\n',1)[1])
    bindings=[RouteEvalBudgetBinding.model_validate(item)
        for item in body['routeBudgetBindings']]
    by_approval={item.request.approval_ref.resource_id:item.request for item in bindings}
    by_key={item.call_key:item for item in bindings};scope=TenantScope('org-org','dev-project')
    guard=RouteEvalActionGuard();events=[]
    monkeypatch.setattr(owner,'_context',lambda conn,database:
        dict(database=database,database_oid=123,login='aos_provider_capacity_occupation',
            role='aos_runtime',org_id='org-org',project_id='dev-project',
            isolation='serializable',readonly='off',xid='123',pid=99,now=NOW))
    monkeypatch.setattr(RouteEvalActionGuard,'_current_call_budget_request',
        lambda self,conn,actual_scope,approval:(by_approval[approval],'maker'))
    monkeypatch.setattr(AipBudgetReservationStore,'_lock_invocation',
        lambda self,conn,actual_scope,operation,key:events.append(('lock',key)))
    def reservation(self,conn,actual_scope,operation,key,*,lock):
        events.append(('reservation',key,lock))
        if missing and not events.count(('missing-used',)):
            events.append(('missing-used',));return None
        item=by_key[key]
        return {'reservation_id':item.reservation.reservation_ref.resource_id,
            'invocation_key':key}
    monkeypatch.setattr(AipBudgetReservationStore,'_reservation_by_key',reservation)
    monkeypatch.setattr(AipBudgetReservationStore,'_view',lambda self,conn,actual_scope,row,*,replayed:
        by_key[row['invocation_key']].reservation)
    monkeypatch.setattr(AipBudgetReservationStore,'_budget_authority',
        lambda self,*args,**kwargs:{'revision':args[2].revision})
    for name in ('_task_authority','_price_authority','_approval_authority','_cost_risk_authority'):
        monkeypatch.setattr(AipBudgetReservationStore,name,
            lambda self,*args,_name=name,**kwargs:events.append((_name,)))
    monkeypatch.setattr(AipBudgetReservationStore,'reserve_in_transaction',
        lambda *args,**kwargs:pytest.fail('current admission must never create or replay a hold'))
    monkeypatch.setattr(owner,'prepare_route_eval_presented_case_bundle',
        lambda actual_manifest,**kwargs:b'presented-green')
    class Result:
        def __init__(self,one=None,many=None):self.one=one;self.many=many
        def fetchone(self):return self.one
        def fetchall(self):return self.many
    class Connection:
        def execute(self,sql,params=()):
            assert sql.lstrip().startswith('SELECT '),'current admission must remain read-only'
            if 'clock_timestamp() AS now' in sql:return Result(one={'now':NOW})
            if 'aip_budget_reservation_bucket' in sql:
                reservation_id=str(params[-1]);item=next(value for value in bindings
                    if value.reservation.reservation_ref.resource_id==reservation_id)
                rows=[{'bucket_kind':bucket.kind,'account_id':bucket.account_id,
                    'period_start':bucket.period_start,'currency':bucket.currency,
                    'reserved_minor':item.request.upper_bound_minor,
                    'period_end':bucket.period_end,'limit_minor':bucket.limit_minor,
                    'held_minor':item.request.upper_bound_minor}
                    for bucket in item.reservation.buckets]
                return Result(many=rows)
            raise AssertionError('unexpected current admission SQL: '+sql)
    return Connection(),scope,guard,manifest,bindings,events


def test_current_admission_reads_all_existing_held_bindings_without_writes(monkeypatch):
    conn,scope,guard,manifest,bindings,events=_current_admission_fixture(monkeypatch)
    result=owner.prepare_route_eval_current_admission_bundle(conn,
        expected_database='aos_test_owner_source',scope=scope,manifest_bytes=manifest,
        guard=guard,revoked_identity_ids=frozenset(),cases=())
    body=json.loads(result.split(b'\n',1)[1])
    assert body['executionAllowed'] is False and len(body['calls'])==len(bindings)
    assert [item['callKey'] for item in body['calls']]==[item.call_key for item in bindings]
    assert sum(event[0]=='reservation' for event in events)==len(bindings)


def test_current_admission_missing_reservation_fails_without_creating_hold(monkeypatch):
    conn,scope,guard,manifest,_,events=_current_admission_fixture(monkeypatch,missing=True)
    with pytest.raises(owner.GovernedEvalOwnerRejected,
            match='ROUTE_EVAL_CURRENT_ADMISSION_REQUIRED'):
        owner.prepare_route_eval_current_admission_bundle(conn,
            expected_database='aos_test_owner_source',scope=scope,
            manifest_bytes=manifest,guard=guard,
            revoked_identity_ids=frozenset(),cases=())
    assert ('missing-used',) in events


@pytest.mark.parametrize('fault',['request','reservation','bucket','caller','presented'])
def test_current_admission_rejects_current_authority_or_backing_drift(monkeypatch,fault):
    from aos_api.aip_budget_reservation_store import AipBudgetReservationStore
    from aos_api.aip_model_route_eval_action import RouteEvalActionGuard
    conn,scope,guard,manifest,bindings,_=_current_admission_fixture(monkeypatch)
    if fault=='request':
        requests={item.request.approval_ref.resource_id:item.request for item in bindings}
        first=bindings[0].request.approval_ref.resource_id
        monkeypatch.setattr(RouteEvalActionGuard,'_current_call_budget_request',
            lambda self,actual_conn,actual_scope,approval:
                (requests[approval].model_copy(update={'upper_bound_minor':
                    requests[approval].upper_bound_minor+(1 if approval==first else 0)}),'maker'))
    elif fault=='reservation':
        by_key={item.call_key:item for item in bindings}
        monkeypatch.setattr(AipBudgetReservationStore,'_view',
            lambda self,actual_conn,actual_scope,row,*,replayed:
                by_key[row['invocation_key']].reservation.model_copy(
                    update={'request_hash':'0'*64}))
    elif fault=='bucket':
        original=type(conn).execute
        def drifted(self,sql,params=()):
            result=original(self,sql,params)
            if 'aip_budget_reservation_bucket' in sql:
                result.many[0]['reserved_minor']+=1
            return result
        monkeypatch.setattr(type(conn),'execute',drifted)
    elif fault=='caller':
        count={'value':0}
        def context(actual_conn,database):
            count['value']+=1
            return dict(database=database,database_oid=123,
                login='aos_provider_capacity_occupation',role='aos_runtime',
                org_id='org-org',project_id='dev-project',isolation='serializable',
                readonly='off',xid='123' if count['value']==1 else '124',
                pid=99,now=NOW)
        monkeypatch.setattr(owner,'_context',context)
    else:
        monkeypatch.setattr(owner,'prepare_route_eval_presented_case_bundle',
            lambda *args,**kwargs:(_ for _ in ()).throw(
                owner.GovernedEvalOwnerRejected(
                    'ROUTE_EVAL_COMPLETE_PRESENTED_CASE_BUNDLE_REQUIRED')))
    with pytest.raises(owner.GovernedEvalOwnerRejected,
            match='ROUTE_EVAL_CURRENT_ADMISSION_REQUIRED'):
        owner.prepare_route_eval_current_admission_bundle(conn,
            expected_database='aos_test_owner_source',scope=scope,
            manifest_bytes=manifest,guard=guard,
            revoked_identity_ids=frozenset(),cases=())


def test_current_admission_rejects_non_route_or_non_exact_guard_before_budget(monkeypatch):
    conn,scope,_,route_manifest,_,events=_current_admission_fixture(monkeypatch)
    with pytest.raises(owner.GovernedEvalOwnerRejected):
        owner.prepare_route_eval_current_admission_bundle(conn,
            expected_database='aos_test_owner_source',scope=scope,
            manifest_bytes=route_manifest,guard=object(),
            revoked_identity_ids=frozenset(),cases=())
    raw,plan=model_inputs(2)
    model_manifest=compile_eval_execution_manifest(raw,
        execution_id=plan.execution_id,checked_at=NOW,model_plan=plan)
    from aos_api.aip_model_route_eval_action import RouteEvalActionGuard
    with pytest.raises(owner.GovernedEvalOwnerRejected):
        owner.prepare_route_eval_current_admission_bundle(conn,
            expected_database='aos_test_owner_source',scope=scope,
            manifest_bytes=model_manifest,guard=RouteEvalActionGuard(),
            revoked_identity_ids=frozenset(),cases=())
    assert not events
