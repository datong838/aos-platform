from datetime import datetime, timezone, timedelta
import json
from uuid import uuid4
import psycopg
import pytest
from aos_api.asset_registry.canonical_json import canonical_json
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_assignee_resolution import ResolveAssigneeRequest
from aos_api.aip_assignee_resolution_store import AipAssigneeResolutionStore
from aos_api.aip_production_contracts import AssigneeKind, AssigneeRef, ResponsibilitySlot, CreateResponsibilityPlanRequest
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractDependencyBlocked
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_stage_review_authority import (
    read_stage_review_responsibility_authority,require_stage_review_authority)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_growth_plan_full_graph import disposable_database, insert, SCOPE

ACTOR='human:stage-reviewer'


def slot(**changes):
    body=dict(slotId='analyst.portrait.review', responsibilityType='independent_review', requiredCapabilityIds=[],
        inputSchemaRef=dict(resourceType='Schema',resourceId='input',revision='1',authority='postgresql'),
        outputSchemaRef=dict(resourceType='Schema',resourceId='output',revision='1',authority='postgresql'),
        returnStage='portrait',assignee=dict(kind='human_principal',resourceId=ACTOR,version=1))
    body.update(changes)
    return ResponsibilitySlot.model_validate(body)


def test_human_without_machine_capability_and_existing_shape():
    assert slot().required_capability_ids==[]
    original=slot(requiredCapabilityIds=['review'])
    assert original.model_dump(mode='json',by_alias=True)['requiredCapabilityIds']==['review']


def test_resolution_receipt_for_another_subject_cannot_authorize_plan_slot():
    with disposable_database() as connect:
        with connect(SCOPE) as conn:
            conn.execute('''INSERT INTO meta_membership(org_id,project_id,subject,role)
                VALUES(%s,%s,%s,'member') ON CONFLICT DO NOTHING''',(*SCOPE.key,ACTOR))
            factory=TransactionBoundConnectFactory(HostTransaction(conn),SCOPE)
            receipt=AipAssigneeResolutionStore(factory).resolve(
                SCOPE,
                ResolveAssigneeRequest(subjectId='analyst.portrait.review',assignee=slot().assignee),
                ACTOR,now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'])
            assert receipt.status.value=='resolved'
            store=AipProductionContractStore(factory,responsibility_template_resolver=lambda scope,ref:True)
            plan_key=f'plan-subject-drift-{uuid4().hex[:10]}'
            before=conn.execute('''SELECT count(*) AS n FROM aip_responsibility_plan_head
                WHERE org_id=%s AND project_id=%s''',SCOPE.key).fetchone()['n']
            with pytest.raises(ProductionContractDependencyBlocked,match='ASSIGNEE_RESOLUTION_SUBJECT_DRIFTED'):
                store.create_responsibility_plan(
                    SCOPE,ACTOR,plan_key,CreateResponsibilityPlanRequest(
                        profile='TEST_HUMAN_REVIEW',
                        templateRef=dict(resourceType='ResponsibilityTemplateRevision',resourceId='test-template',revision=1,contentHash='a'*64),
                        slots=[slot(slotId='analyst.other.review',assigneeResolutionReceiptId=receipt.receipt_id)]))
            assert conn.execute('''SELECT count(*) AS n FROM aip_production_contract_receipt
                WHERE org_id=%s AND project_id=%s AND operation='responsibility_plan.create'
                  AND idempotency_key=%s''',(*SCOPE.key,plan_key)).fetchone()['n']==0
            assert conn.execute('''SELECT count(*) AS n FROM aip_responsibility_plan_head
                WHERE org_id=%s AND project_id=%s''',SCOPE.key).fetchone()['n']==before


def test_revoked_human_membership_blocks_unexpired_resolution_plan_freeze():
    with disposable_database() as connect:
        with connect(SCOPE) as conn:
            conn.execute('''INSERT INTO meta_membership(org_id,project_id,subject,role)
                VALUES(%s,%s,%s,'member') ON CONFLICT DO NOTHING''',(*SCOPE.key,ACTOR))
            factory=TransactionBoundConnectFactory(HostTransaction(conn),SCOPE)
            receipt=AipAssigneeResolutionStore(factory).resolve(
                SCOPE,
                ResolveAssigneeRequest(subjectId='analyst.portrait.review',assignee=slot().assignee),
                ACTOR,now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'])
            assert receipt.status.value=='resolved'
            owner=AipProductionContractStore(factory,responsibility_template_resolver=lambda scope,ref:True)
            draft=owner.create_responsibility_plan(SCOPE,ACTOR,f'pre-revoke-{uuid4().hex[:10]}',
                CreateResponsibilityPlanRequest(profile='TEST_HUMAN_REVIEW',
                    templateRef=dict(resourceType='ResponsibilityTemplateRevision',resourceId='test-template',revision=1,contentHash='a'*64),
                    slots=[slot(assigneeResolutionReceiptId=receipt.receipt_id)]))
            assert draft.readiness.value=='ready'
            conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                (*SCOPE.key,ACTOR))
            current=owner.get_responsibility_plan(SCOPE,draft.plan_id,draft.revision,conn=conn)
            assert current.readiness.value=='blocked'
            assert 'ASSIGNEE_RESOLUTION_MEMBERSHIP_REVOKED' in current.blockers[0].message
            with pytest.raises(ProductionContractDependencyBlocked,match='ASSIGNEE_RESOLUTION_MEMBERSHIP_REVOKED'):
                owner.freeze_responsibility_plan(SCOPE,ACTOR,draft.plan_id,draft.version,
                    f'freeze-after-revoke-{uuid4().hex[:10]}')
            assert conn.execute('''SELECT current_revision AS revision FROM aip_responsibility_plan_head
                WHERE org_id=%s AND project_id=%s AND plan_id=%s''',(*SCOPE.key,draft.plan_id)).fetchone()['revision']==draft.revision
            assert conn.execute('''SELECT count(*) AS n FROM aip_production_contract_receipt
                WHERE org_id=%s AND project_id=%s AND operation='responsibility_plan.freeze'
                  AND result_ref->>'resourceId'=%s''',(*SCOPE.key,draft.plan_id)).fetchone()['n']==0


def test_plan_write_admission_holds_member_until_freeze_commit_without_locking_read_only_get():
    with disposable_database() as connect:
        with connect(SCOPE) as seed:
            seed.execute('''INSERT INTO meta_membership(org_id,project_id,subject,role)
                VALUES(%s,%s,%s,'member') ON CONFLICT DO NOTHING''',(*SCOPE.key,ACTOR))
            factory=TransactionBoundConnectFactory(HostTransaction(seed),SCOPE)
            receipt=AipAssigneeResolutionStore(factory).resolve(SCOPE,
                ResolveAssigneeRequest(subjectId='analyst.portrait.review',assignee=slot().assignee),
                ACTOR,now=seed.execute('SELECT clock_timestamp() AS now').fetchone()['now'])
            owner=AipProductionContractStore(factory,responsibility_template_resolver=lambda scope,ref:True)
            draft=owner.create_responsibility_plan(SCOPE,ACTOR,f'lock-draft-{uuid4().hex[:10]}',
                CreateResponsibilityPlanRequest(profile='TEST_HUMAN_REVIEW',
                    templateRef=dict(resourceType='ResponsibilityTemplateRevision',resourceId='test-template',revision=1,contentHash='a'*64),
                    slots=[slot(assigneeResolutionReceiptId=receipt.receipt_id)]))
            assert draft.readiness.value=='ready'
        with connect(SCOPE) as writer:
            owner=AipProductionContractStore(responsibility_template_resolver=lambda scope,ref:True)
            owner._require_responsibility_dependencies(writer,SCOPE,draft)
            with connect(SCOPE) as revoker:
                revoker.execute("SET LOCAL lock_timeout = '250ms'")
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    revoker.execute('''DELETE FROM meta_membership
                        WHERE org_id=%s AND project_id=%s AND subject=%s''',(*SCOPE.key,ACTOR))
                revoker.rollback()
            frozen=owner.freeze_responsibility_plan_in_transaction(writer,SCOPE,ACTOR,
                draft.plan_id,draft.version,f'lock-freeze-{uuid4().hex[:10]}')
            assert frozen.lifecycle.value=='frozen'
        with connect(SCOPE) as reader:
            reader.read_only=True
            assert owner.get_responsibility_plan(SCOPE,draft.plan_id,conn=reader).readiness.value=='ready'
        with connect(SCOPE) as revoker:
            revoker.execute('''DELETE FROM meta_membership
                WHERE org_id=%s AND project_id=%s AND subject=%s''',(*SCOPE.key,ACTOR))
        with connect(SCOPE) as reader:
            reader.read_only=True
            current=owner.get_responsibility_plan(SCOPE,draft.plan_id,conn=reader)
            assert current.readiness.value=='blocked'
            assert 'ASSIGNEE_RESOLUTION_MEMBERSHIP_REVOKED' in current.blockers[0].message


def _provider_plan(conn):
    now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    binding_id=f'provider-revoke-{uuid4().hex[:10]}'
    capability=VersionedAssetRef(asset_type='CapabilityRevision',
        asset_id='capability.content.review',revision=1,content_hash='a'*64)
    insert(conn,'aip_capability_binding',binding_id=binding_id,
        capability_ref=capability.model_dump(mode='json',by_alias=True),
        secret_ref='secret://pytest/provider',health='healthy',
        network_policy_revision='network-1',quota_policy_revision='quota-1',
        timeout_ms=30000,max_concurrency=1,status='active',version=1,
        operational_readiness='available',allow_degraded=False,
        dependency_snapshot_hash='e'*64,last_evaluated_at=now,
        readiness_expires_at=now+timedelta(hours=1),observed_at=now)
    factory=TransactionBoundConnectFactory(HostTransaction(conn),SCOPE)
    assignee=AssigneeRef(kind=AssigneeKind.PROVIDER_CAPABILITY_BINDING,
        resource_id=binding_id,version=1)
    receipt=AipAssigneeResolutionStore(factory).resolve(SCOPE,
        ResolveAssigneeRequest(subjectId='analyst.portrait.review',
            candidates=[assignee],requiredCapabilities=[capability]),
        ACTOR,now=now)
    assert receipt.status.value=='resolved'
    owner=AipProductionContractStore(factory,
        responsibility_template_resolver=lambda scope,ref:True)
    draft=owner.create_responsibility_plan(SCOPE,ACTOR,
        f'provider-plan-{uuid4().hex[:10]}',CreateResponsibilityPlanRequest(
            profile='TEST_PROVIDER_REVIEW',
            templateRef=dict(resourceType='ResponsibilityTemplateRevision',
                resourceId='test-template',revision=1,contentHash='a'*64),
            slots=[slot(requiredCapabilityIds=[capability.asset_id],
                assignee=assignee.model_dump(mode='json',by_alias=True),
                assigneeResolutionReceiptId=receipt.receipt_id)]))
    assert draft.readiness.value=='ready'
    return owner,draft,binding_id


@pytest.mark.parametrize('drift,blocker',[
    ('status','REVOKED'),('health','REVOKED'),('version','REVOKED'),
    ('freshness','REVOKED'),('policy','DRIFTED'),
])
def test_revoked_provider_binding_blocks_unexpired_resolution_plan_freeze(drift,blocker):
    with disposable_database() as connect:
        with connect(SCOPE) as conn:
            owner,draft,binding_id=_provider_plan(conn)
            updates={
                'status':"status='suspended'",
                'health':"health='unavailable'",
                'version':'version=version+1',
                'freshness':"readiness_expires_at=NOW()-INTERVAL '1 second'",
                'policy':"network_policy_revision='network-2'",
            }
            conn.execute(f'''UPDATE aip_capability_binding SET {updates[drift]}
                WHERE org_id=%s AND project_id=%s AND binding_id=%s''',
                (*SCOPE.key,binding_id))
            current=owner.get_responsibility_plan(SCOPE,draft.plan_id,draft.revision,conn=conn)
            assert current.readiness.value=='blocked'
            with pytest.raises(ProductionContractDependencyBlocked,
                match=f'ASSIGNEE_RESOLUTION_PROVIDER_BINDING_{blocker}'):
                owner.freeze_responsibility_plan(SCOPE,ACTOR,draft.plan_id,draft.version,
                    f'provider-freeze-{uuid4().hex[:10]}')
            assert conn.execute('''SELECT count(*) AS n FROM aip_production_contract_receipt
                WHERE org_id=%s AND project_id=%s AND operation='responsibility_plan.freeze'
                  AND result_ref->>'resourceId'=%s''',
                (*SCOPE.key,draft.plan_id)).fetchone()['n']==0


def test_provider_write_admission_locks_current_binding_until_freeze_commit():
    with disposable_database() as connect:
        with connect(SCOPE) as seed:
            _,draft,binding_id=_provider_plan(seed)
        with connect(SCOPE) as writer:
            owner=AipProductionContractStore(responsibility_template_resolver=lambda scope,ref:True)
            owner._require_responsibility_dependencies(writer,SCOPE,draft)
            with connect(SCOPE) as revoker:
                revoker.execute("SET LOCAL lock_timeout = '250ms'")
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    revoker.execute('''UPDATE aip_capability_binding SET status='suspended'
                        WHERE org_id=%s AND project_id=%s AND binding_id=%s''',
                        (*SCOPE.key,binding_id))
                revoker.rollback()
            frozen=owner.freeze_responsibility_plan_in_transaction(writer,SCOPE,ACTOR,
                draft.plan_id,draft.version,f'provider-lock-freeze-{uuid4().hex[:10]}')
            assert frozen.lifecycle.value=='frozen'
        with connect(SCOPE) as reader:
            reader.read_only=True
            assert owner.get_responsibility_plan(SCOPE,draft.plan_id,conn=reader).readiness.value=='ready'
        with connect(SCOPE) as revoker:
            revoker.execute('''UPDATE aip_capability_binding SET status='suspended'
                WHERE org_id=%s AND project_id=%s AND binding_id=%s''',
                (*SCOPE.key,binding_id))
        with connect(SCOPE) as reader:
            reader.read_only=True
            assert owner.get_responsibility_plan(SCOPE,draft.plan_id,conn=reader).readiness.value=='blocked'


def _tool_plan(conn):
    _,_,cap_binding_id=_provider_plan(conn)
    suffix=uuid4().hex[:10]
    template_id=f'template-tool-{suffix}'
    instance_id=f'instance-tool-{suffix}'
    tool_binding_id=f'tool-binding-{suffix}'
    conn.execute('''INSERT INTO aip_agent_template_revision
        (template_id,revision,display_name,role_key,lifecycle,source_ref,
         source_license,manifest,content_hash,created_by)
        VALUES(%s,1,'Tool owner',%s,'published','{}','internal','{}',%s,%s)''',
        (template_id,f'role-{suffix}','b'*64,ACTOR))
    insert(conn,'aip_agent_instance',instance_id=instance_id,
        template_id=template_id,template_revision=1,status='active',overlay={},
        version=1,created_by=ACTOR)
    insert(conn,'aip_tool_binding',binding_id=tool_binding_id,tool_id='tool.review',
        version=1,agent_instance_id=instance_id,status='active',
        capability_binding_ids=[cap_binding_id],policy_refs=[])
    factory=TransactionBoundConnectFactory(HostTransaction(conn),SCOPE)
    assignee=AssigneeRef(kind=AssigneeKind.TOOL_BINDING,
        resource_id=tool_binding_id,version=1)
    capability=VersionedAssetRef(asset_type='CapabilityRevision',
        asset_id='capability.content.review',revision=1,content_hash='a'*64)
    receipt=AipAssigneeResolutionStore(factory).resolve(SCOPE,
        ResolveAssigneeRequest(subjectId='analyst.portrait.review',
            candidates=[assignee],requiredCapabilities=[capability]),
        ACTOR,now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'])
    assert receipt.status.value=='resolved'
    owner=AipProductionContractStore(factory,
        responsibility_template_resolver=lambda scope,ref:True)
    draft=owner.create_responsibility_plan(SCOPE,ACTOR,
        f'tool-plan-{suffix}',CreateResponsibilityPlanRequest(
            profile='TEST_TOOL_REVIEW',
            templateRef=dict(resourceType='ResponsibilityTemplateRevision',
                resourceId='test-template',revision=1,contentHash='a'*64),
            slots=[slot(requiredCapabilityIds=[capability.asset_id],
                assignee=assignee.model_dump(mode='json',by_alias=True),
                assigneeResolutionReceiptId=receipt.receipt_id)]))
    assert draft.readiness.value=='ready'
    return owner,draft,tool_binding_id,instance_id,cap_binding_id


@pytest.mark.parametrize('drift,blocker',[
    ('tool_status','REVOKED'),('tool_version','REVOKED'),
    ('instance_status','REVOKED'),('instance_owner','REVOKED'),
    ('capability_status','REVOKED'),('capability_policy','DRIFTED'),
])
def test_revoked_tool_binding_blocks_unexpired_resolution_plan_freeze(drift,blocker):
    with disposable_database() as connect:
        with connect(SCOPE) as conn:
            owner,draft,tool_id,instance_id,cap_id=_tool_plan(conn)
            updates={
                'tool_status':('aip_tool_binding',tool_id,"status='disabled'",'binding_id'),
                'tool_version':('aip_tool_binding',tool_id,'version=version+1','binding_id'),
                'instance_status':('aip_agent_instance',instance_id,"status='suspended'",'instance_id'),
                'instance_owner':('aip_tool_binding',tool_id,"agent_instance_id='missing-instance'",'binding_id'),
                'capability_status':('aip_capability_binding',cap_id,"status='suspended'",'binding_id'),
                'capability_policy':('aip_capability_binding',cap_id,
                    "network_policy_revision='network-2'",'binding_id'),
            }
            table,identifier,change,key=updates[drift]
            conn.execute(f'''UPDATE {table} SET {change}
                WHERE org_id=%s AND project_id=%s AND {key}=%s''',
                (*SCOPE.key,identifier))
            current=owner.get_responsibility_plan(SCOPE,draft.plan_id,conn=conn)
            assert current.readiness.value=='blocked'
            with pytest.raises(ProductionContractDependencyBlocked,
                match=f'ASSIGNEE_RESOLUTION_TOOL_BINDING_{blocker}'):
                owner.freeze_responsibility_plan(SCOPE,ACTOR,draft.plan_id,draft.version,
                    f'tool-freeze-{uuid4().hex[:10]}')
            assert conn.execute('''SELECT count(*) AS n FROM aip_production_contract_receipt
                WHERE org_id=%s AND project_id=%s AND operation='responsibility_plan.freeze'
                  AND result_ref->>'resourceId'=%s''',
                (*SCOPE.key,draft.plan_id)).fetchone()['n']==0


@pytest.mark.parametrize('target',['tool','instance','capability'])
def test_tool_write_admission_locks_current_dependencies_until_freeze_commit(target):
    with disposable_database() as connect:
        with connect(SCOPE) as seed:
            _,draft,tool_id,instance_id,cap_id=_tool_plan(seed)
        with connect(SCOPE) as writer:
            owner=AipProductionContractStore(responsibility_template_resolver=lambda scope,ref:True)
            owner._require_responsibility_dependencies(writer,SCOPE,draft)
            table,field,identity,change={
                'tool':('aip_tool_binding','binding_id',tool_id,"status='disabled'"),
                'instance':('aip_agent_instance','instance_id',instance_id,"status='suspended'"),
                'capability':('aip_capability_binding','binding_id',cap_id,"status='suspended'"),
            }[target]
            with connect(SCOPE) as revoker:
                revoker.execute("SET LOCAL lock_timeout = '250ms'")
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    revoker.execute(f'''UPDATE {table} SET {change}
                        WHERE org_id=%s AND project_id=%s AND {field}=%s''',
                        (*SCOPE.key,identity))
                revoker.rollback()
            frozen=owner.freeze_responsibility_plan_in_transaction(writer,SCOPE,ACTOR,
                draft.plan_id,draft.version,f'tool-lock-freeze-{uuid4().hex[:10]}')
            assert frozen.lifecycle.value=='frozen'
        with connect(SCOPE) as reader:
            reader.read_only=True
            assert owner.get_responsibility_plan(SCOPE,draft.plan_id,conn=reader).readiness.value=='ready'
        with connect(SCOPE) as revoker:
            revoker.execute(f'''UPDATE {table} SET {change}
                WHERE org_id=%s AND project_id=%s AND {field}=%s''',
                (*SCOPE.key,identity))
        with connect(SCOPE) as reader:
            reader.read_only=True
            assert owner.get_responsibility_plan(SCOPE,draft.plan_id,conn=reader).readiness.value=='blocked'


def _agent_inputs(conn, *, sourced=False, missing_receipt=None):
    _,_,_,instance_id,cap_id=_tool_plan(conn)
    suffix=uuid4().hex[:10]
    skill_id=f'skill-agent-{suffix}'
    binding_id=f'skill-binding-agent-{suffix}'
    now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    conn.execute('''INSERT INTO aip_skill_template_revision
        (skill_id,revision,canonical_logic_id,lifecycle,input_schema,output_schema,
         tool_allowlist,required_capabilities,risk_level,memory_policy_ref,
         handoff_policy_ref,source_ref,source_license,content_hash,created_by,
         parent_ref,publication_tenant,release_gate_ref,publication_ref,
         model_route_ref,runtime_policy_ref,logic_revision_ref)
        VALUES(%s,1,%s,%s,'{}','{}','[]','[]','low','{}','{}','{}',
            'internal',%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
            %s::jsonb,%s::jsonb,%s::jsonb)''',
        (skill_id,f'logic-{suffix}','published' if sourced else 'draft','c'*64,
         ACTOR,json.dumps({'assetType':'SkillTemplate'}) if sourced else None,
         json.dumps({'orgId':SCOPE.org_id,'projectId':SCOPE.project_id})
         if sourced else None,
         json.dumps({'assetType':'EvalGateDecision'}) if sourced else None,
         json.dumps({'resourceType':'PublicationEvent'}) if sourced else None,
         json.dumps({'assetType':'ModelRouteRevision'}) if sourced else None,
         json.dumps({'assetType':'RuntimePolicyRevision'}) if sourced else None,
         json.dumps({'assetType':'LogicRevision','assetId':f'logic-{suffix}',
                     'revision':1,'contentHash':'c'*64}) if sourced else None))
    insert(conn,'aip_skill_binding',binding_id=binding_id,instance_id=instance_id,
        skill_id=skill_id,skill_revision=1,capability_refs=[cap_id],
        budget_policy_ref={},status='active',version=1,readiness='available',
        dependency_snapshot_hash='d'*64,last_evaluated_at=now,
        readiness_expires_at=now+timedelta(hours=1))
    if sourced:
        for operation in ('skill_binding.create','skill_binding.evaluate','skill_binding.update'):
            if operation == missing_receipt:
                continue
            insert(conn,'aip_agent_registry_receipt',receipt_id=f'{operation}-{suffix}',
                operation=operation,idempotency_key=f'{operation}-{suffix}',
                request_hash='f'*64,resource_ref={},
                result_ref={'resourceId':binding_id},status='applied',
                created_by=ACTOR,created_at=now)
    factory=TransactionBoundConnectFactory(HostTransaction(conn),SCOPE)
    assignee=AssigneeRef(kind=AssigneeKind.AGENT_INSTANCE,
        resource_id=instance_id,version=1)
    capability=VersionedAssetRef(asset_type='CapabilityRevision',
        asset_id='capability.content.review',revision=1,content_hash='a'*64)
    receipt=AipAssigneeResolutionStore(factory).resolve(SCOPE,
        ResolveAssigneeRequest(subjectId='analyst.portrait.review',
            candidates=[assignee],requiredCapabilities=[capability]),
        ACTOR,now=now)
    assert receipt.status.value=='resolved'
    owner=AipProductionContractStore(factory,
        responsibility_template_resolver=lambda scope,ref:True)
    body=CreateResponsibilityPlanRequest(profile='TEST_AGENT_REVIEW',
        templateRef=dict(resourceType='ResponsibilityTemplateRevision',
            resourceId='test-template',revision=1,contentHash='a'*64),
        slots=[slot(requiredCapabilityIds=[capability.asset_id],
            assignee=assignee.model_dump(mode='json',by_alias=True),
            assigneeResolutionReceiptId=receipt.receipt_id)])
    return owner,body,instance_id,binding_id,cap_id


def test_agent_receipt_cannot_bypass_skill_publication_and_binding_source():
    with disposable_database() as connect:
        with connect(SCOPE) as conn:
            owner,body,_,_,_=_agent_inputs(conn)
            key=f'agent-unsourced-{uuid4().hex[:10]}'
            with pytest.raises(ProductionContractDependencyBlocked,
                match='ASSIGNEE_RESOLUTION_AGENT_SOURCE_INVALID'):
                owner.create_responsibility_plan(SCOPE,ACTOR,key,body)
            assert conn.execute('''SELECT count(*) AS n FROM aip_production_contract_receipt
                WHERE org_id=%s AND project_id=%s
                  AND operation='responsibility_plan.create' AND idempotency_key=%s''',
                (*SCOPE.key,key)).fetchone()['n']==0


@pytest.mark.parametrize('missing_operation',[
    'skill_binding.create','skill_binding.evaluate','skill_binding.update',
])
def test_agent_receipt_requires_each_original_binding_source(missing_operation):
    with disposable_database() as connect:
        with connect(SCOPE) as conn:
            owner,body,_,_,_=_agent_inputs(conn,sourced=True,
                missing_receipt=missing_operation)
            with pytest.raises(ProductionContractDependencyBlocked,
                match='ASSIGNEE_RESOLUTION_AGENT_SOURCE_INVALID'):
                owner.create_responsibility_plan(SCOPE,ACTOR,
                    f'agent-missing-source-{uuid4().hex[:10]}',body)


@pytest.mark.parametrize('drift,blocker',[
    ('instance_status','AGENT_BINDING_REVOKED'),
    ('instance_version','AGENT_BINDING_REVOKED'),
    ('skill_status','AGENT_SOURCE_INVALID'),
    ('skill_freshness','AGENT_BINDING_REVOKED'),
    ('capability_status','AGENT_BINDING_REVOKED'),
    ('capability_policy','AGENT_BINDING_DRIFTED'),
])
def test_agent_resolution_current_dependencies_block_plan_freeze(drift,blocker):
    with disposable_database() as connect:
        with connect(SCOPE) as conn:
            owner,body,instance_id,skill_id,cap_id=_agent_inputs(conn,sourced=True)
            draft=owner.create_responsibility_plan(SCOPE,ACTOR,
                f'agent-ready-{uuid4().hex[:10]}',body)
            assert draft.readiness.value=='ready'
            updates={
                'instance_status':('aip_agent_instance','instance_id',instance_id,"status='suspended'"),
                'instance_version':('aip_agent_instance','instance_id',instance_id,'version=version+1'),
                'skill_status':('aip_skill_binding','binding_id',skill_id,"status='suspended'"),
                'skill_freshness':('aip_skill_binding','binding_id',skill_id,
                    "readiness_expires_at=NOW()-INTERVAL '1 second'"),
                'capability_status':('aip_capability_binding','binding_id',cap_id,"status='suspended'"),
                'capability_policy':('aip_capability_binding','binding_id',cap_id,
                    "network_policy_revision='network-2'"),
            }
            table,field,identifier,change=updates[drift]
            conn.execute(f'''UPDATE {table} SET {change}
                WHERE org_id=%s AND project_id=%s AND {field}=%s''',
                (*SCOPE.key,identifier))
            current=owner.get_responsibility_plan(SCOPE,draft.plan_id,conn=conn)
            assert current.readiness.value=='blocked'
            with pytest.raises(ProductionContractDependencyBlocked,
                match=f'ASSIGNEE_RESOLUTION_{blocker}'):
                owner.freeze_responsibility_plan(SCOPE,ACTOR,draft.plan_id,draft.version,
                    f'agent-freeze-{uuid4().hex[:10]}')
            assert conn.execute('''SELECT count(*) AS n FROM aip_production_contract_receipt
                WHERE org_id=%s AND project_id=%s AND operation='responsibility_plan.freeze'
                  AND result_ref->>'resourceId'=%s''',
                (*SCOPE.key,draft.plan_id)).fetchone()['n']==0


@pytest.mark.parametrize('target',['instance','skill','capability'])
def test_agent_write_admission_locks_current_dependencies_until_freeze_commit(target):
    with disposable_database() as connect:
        with connect(SCOPE) as seed:
            owner,body,instance_id,skill_id,cap_id=_agent_inputs(seed,sourced=True)
            draft=owner.create_responsibility_plan(SCOPE,ACTOR,
                f'agent-lock-plan-{uuid4().hex[:10]}',body)
            assert draft.readiness.value=='ready'
        with connect(SCOPE) as writer:
            owner=AipProductionContractStore(responsibility_template_resolver=lambda scope,ref:True)
            owner._require_responsibility_dependencies(writer,SCOPE,draft)
            table,field,identity,change={
                'instance':('aip_agent_instance','instance_id',instance_id,"status='suspended'"),
                'skill':('aip_skill_binding','binding_id',skill_id,"status='suspended'"),
                'capability':('aip_capability_binding','binding_id',cap_id,"status='suspended'"),
            }[target]
            with connect(SCOPE) as revoker:
                revoker.execute("SET LOCAL lock_timeout = '250ms'")
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    revoker.execute(f'''UPDATE {table} SET {change}
                        WHERE org_id=%s AND project_id=%s AND {field}=%s''',
                        (*SCOPE.key,identity))
                revoker.rollback()
            frozen=owner.freeze_responsibility_plan_in_transaction(writer,SCOPE,ACTOR,
                draft.plan_id,draft.version,f'agent-lock-freeze-{uuid4().hex[:10]}')
            assert frozen.lifecycle.value=='frozen'
        with connect(SCOPE) as reader:
            reader.read_only=True
            assert owner.get_responsibility_plan(SCOPE,draft.plan_id,conn=reader).readiness.value=='ready'
        with connect(SCOPE) as revoker:
            revoker.execute(f'''UPDATE {table} SET {change}
                WHERE org_id=%s AND project_id=%s AND {field}=%s''',
                (*SCOPE.key,identity))
        with connect(SCOPE) as reader:
            reader.read_only=True
            assert owner.get_responsibility_plan(SCOPE,draft.plan_id,conn=reader).readiness.value=='blocked'


@pytest.mark.parametrize('kind',['agent_instance','tool_binding','provider_capability_binding'])
def test_machine_still_requires_capability(kind):
    with pytest.raises(ValueError,match='non-human responsibilities require'):slot(assignee=dict(kind=kind,resourceId='machine',version=1))


def setup(conn):
    conn.execute('''INSERT INTO meta_membership(org_id,project_id,subject,role)
        VALUES(%s,%s,%s,'member') ON CONFLICT DO NOTHING''',(*SCOPE.key,ACTOR))
    factory=TransactionBoundConnectFactory(HostTransaction(conn),SCOPE)
    receipt=AipAssigneeResolutionStore(factory).resolve(SCOPE,
        ResolveAssigneeRequest(subjectId='analyst.portrait.review',assignee=slot().assignee),
        ACTOR,now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'])
    owner=AipProductionContractStore(factory,responsibility_template_resolver=lambda scope,ref:True)
    body=CreateResponsibilityPlanRequest(profile='TEST_HUMAN_REVIEW',
        templateRef=dict(resourceType='ResponsibilityTemplateRevision',resourceId='test-template',revision=1,contentHash='a'*64),
        slots=[slot(assigneeResolutionReceiptId=receipt.receipt_id)])
    draft=owner.create_responsibility_plan(SCOPE,ACTOR,'human-plan',body)
    plan=owner.freeze_responsibility_plan(SCOPE,ACTOR,draft.plan_id,draft.version,'freeze-human-plan')
    ref=AnalystExactRef(resourceType='ResponsibilityPlanRevision',resourceId=plan.plan_id,revision=plan.revision,contentHash=plan.content_hash)
    return ref,receipt.receipt_id


def check(conn,ref,**changes):
    args=dict(responsibility_plan_ref=ref,stage='portrait',actor=ACTOR)
    scope=changes.pop('scope',SCOPE)
    args.update(changes)
    return require_stage_review_authority(HostTransaction(conn),scope,**args)


def test_actual_human_resolution_and_frozen_plan_current_checks():
    with disposable_database() as connect:
        with connect(SCOPE) as conn:
            ref,_=setup(conn)
            assert check(conn,ref)==slot().assignee
            proof=read_stage_review_responsibility_authority(HostTransaction(conn),SCOPE,
                responsibility_plan_ref=ref,stage='portrait',actor=ACTOR)
            assert proof['reviewer']==slot().assignee
            assert proof['payload']['kind']=='validate_review_slot'
            assert proof['payload']['assignee']==proof['expected']['assignee']
            assert proof['snapshot']['responsibilityPlanRef']==ref.model_dump(mode='json',by_alias=True)
            canonical_json(proof['snapshot']);canonical_json(proof['payload']);canonical_json(proof['expected'])
            for args in [dict(actor='other'),dict(stage='diagnosis'),dict(scope=TenantScope('dev-org','dev-project')),
                dict(responsibility_plan_ref=ref.model_copy(update={'content_hash':'b'*64})),
                dict(responsibility_plan_ref=ref.model_copy(update={'revision':1}))]:
                with pytest.raises((ValueError,RuntimeError)):check(conn,ref,**args)
        with connect(SCOPE) as conn:
            conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',(*SCOPE.key,ACTOR))
            owner=AipProductionContractStore(TransactionBoundConnectFactory(HostTransaction(conn),SCOPE))
            current=owner.get_responsibility_plan(SCOPE,ref.resource_id,ref.revision,conn=conn)
            assert current.readiness.value=='blocked'
            assert 'ASSIGNEE_RESOLUTION_MEMBERSHIP_REVOKED' in current.blockers[0].message
            with pytest.raises(ValueError,match='responsibility plan is stale'):check(conn,ref)


@pytest.mark.parametrize('field',['expires_at','snapshot_hash','content_hash'])
def test_resolution_expiry_or_hash_drift_blocks(field):
    with disposable_database() as connect:
        with connect(SCOPE) as conn:
            ref,receipt_id=setup(conn)
            if field=='expires_at':
                conn.execute("UPDATE aip_assignee_resolution_receipt SET created_at=NOW()-INTERVAL '2 days', expires_at=NOW()-INTERVAL '1 day' WHERE receipt_id=%s",(receipt_id,))
            else:
                conn.execute(f'UPDATE aip_assignee_resolution_receipt SET {field}=%s WHERE receipt_id=%s',('b'*64,receipt_id))
            with pytest.raises((ValueError,RuntimeError)):check(conn,ref)
