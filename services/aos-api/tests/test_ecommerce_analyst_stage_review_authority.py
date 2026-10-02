from datetime import datetime, timezone
from uuid import uuid4
import pytest
from aos_api.asset_registry.canonical_json import canonical_json
from aos_api.aip_assignee_resolution import ResolveAssigneeRequest
from aos_api.aip_assignee_resolution_store import AipAssigneeResolutionStore
from aos_api.aip_production_contracts import ResponsibilitySlot, CreateResponsibilityPlanRequest
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractDependencyBlocked
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_stage_review_authority import (
    read_stage_review_responsibility_authority,require_stage_review_authority)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_growth_plan_full_graph import disposable_database, SCOPE

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
