"""Source join on disposable PG; fixture decisions are not human authority proof."""
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
import os
from uuid import uuid4
from psycopg.conninfo import conninfo_to_dict
import pytest
from aos_api.db import connect
from aos_api.ecommerce_analyst_authority_contracts import GrowthPlanLifecycle
from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore, canonical_hash
from aos_api.ecommerce_analyst_growth_plan_approval import ApproveGrowthPlanRequest, EcommerceAnalystGrowthPlanApprovalService
from aos_api.ecommerce_analyst_stage_decision_store import AnalystStageDecisionStore, stage_decision_id
from aos_api.ecommerce_analyst_stage_handoff_source import read_approved_stage_handoff_source
from aos_api.ecommerce_analyst_stage_review_command import read_stage_review_eval_source_authority
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import ReviewAdvanceHostService
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_growth_plan_approval import plan
from test_ecommerce_analyst_stage_decision import decision, ref
from test_ecommerce_review_advance_host import accepted_stage_command, command_hash
SCOPE=TenantScope('org-org','dev-project')

def hashed(value):
    return value.model_copy(update={'content_hash':canonical_hash(value.model_dump(mode='json',by_alias=True,exclude={'content_hash'}))})

@pytest.fixture()
def source(request):
    fault=getattr(request, "param", None)
    database=conninfo_to_dict(os.environ['AOS_DATABASE_URL'])['dbname']
    assert database.startswith('aos_test_') and database.endswith('_ti4_test')
    name='gwd-'+uuid4().hex
    with connect(SCOPE) as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','isolated fixture') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','isolated fixture') ON CONFLICT DO NOTHING")
        now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    draft=hashed(plan(plan_id=name).model_copy(update={'created_at':now-timedelta(hours=3),'generation_artifact_ref':ref('Artifact',name+'-text')}))
    owner=EcommerceAnalystAuthorityStore()
    draft_ref=owner.publish_plan(SCOPE,draft.created_by,name+':draft',draft,expected_version=0)
    item=decision(stage='solution-design',subject_ref=draft_ref,artifact_ref=draft.generation_artifact_ref,
        task_run_id=name,stage_attempt_ref=dict(resourceType='StepRunAttempt',runId=name,stepKey='solution-design',stepRunId=name+'-step',attempt=1,inputHash='b'*64),
        created_at=now-timedelta(hours=2),expires_at=now+timedelta(hours=-1 if fault=='expired' else 1))
    item=hashed(item.model_copy(update={'decision_id':stage_decision_id(item)}))
    with connect(SCOPE) as conn:
        decision_ref=AnalystStageDecisionStore(HostTransaction(conn),SCOPE).put(item,actor=item.created_by,key=name+':accept',expected_version=0)
    if fault=='content_changed':
        # Valid Owner publication with altered business body: must never inherit draft acceptance.
        changed=hashed(draft.model_copy(update={'revision':2,'version':2,'prior_ref':draft_ref,
            'lifecycle':GrowthPlanLifecycle.APPROVED,'approved_at':now,'created_at':now,'created_by':'fixture-approver',
            'objective':'different objective'}))
        approved_ref=owner.publish_plan(SCOPE,changed.created_by,name+':changed',changed,expected_version=1)
    else:
        approval=EcommerceAnalystGrowthPlanApprovalService(owner).approve(SCOPE,name,ApproveGrowthPlanRequest(draftRef=draft_ref),expected_version=1,idempotency_key=name+':approve',actor='fixture-approver')
        approved_ref=approval.approved_ref
    args=dict(approved_ref=approved_ref,decision_ref=decision_ref,task_run_id=item.task_run_id,plan_ref=item.plan_ref,stage_attempt_ref=item.stage_attempt_ref)
    return owner,draft,item,args

def read(args,scope=SCOPE):
    with connect(scope) as conn:
        conn.execute('SET LOCAL ROLE aos_runtime')
        return read_approved_stage_handoff_source(HostTransaction(conn),scope,**args)

def test_exact_historical_draft_and_approved_successor(source):
    owner,draft,item,args=source
    result=read(args)
    assert result.draft==draft and result.decision==item
    assert result.approved.prior_ref==item.subject_ref
    assert not owner.is_current_plan(SCOPE,item.subject_ref)
    assert result.approved.generation_artifact_ref==item.artifact_ref


def test_approved_successor_anchors_historical_draft_for_handoff_eval(source):
    _owner, _draft, item, args = source
    with connect(SCOPE) as conn:
        conn.execute('SET LOCAL ROLE aos_runtime')
        transaction = HostTransaction(conn)
        approved_source = read_approved_stage_handoff_source(transaction, SCOPE, **args)
        with pytest.raises(ValueError, match='current growth draft unavailable'):
            read_stage_review_eval_source_authority(transaction, SCOPE, item, {}, ['internal'])
        with pytest.raises(ValueError, match='current analyst exact source unavailable'):
            read_stage_review_eval_source_authority(
                transaction, SCOPE, item, {}, ['internal'],
                approved_stage_source=approved_source,
            )
        drifted_source = replace(
            approved_source,
            draft=approved_source.draft.model_copy(update={'content_hash': '0' * 64}),
        )
        with pytest.raises(ValueError, match='approved Handoff stage draft source drifted'):
            read_stage_review_eval_source_authority(
                transaction, SCOPE, item, {}, ['internal'],
                approved_stage_source=drifted_source,
            )


def test_handoff_stage_runtime_sources_reject_missing_original_task_run(source):
    _owner, _draft, item, args = source
    with connect(SCOPE) as conn:
        conn.execute('SET LOCAL ROLE aos_runtime')
        transaction = HostTransaction(conn)
        approved_source = read_approved_stage_handoff_source(transaction, SCOPE, **args)
        with pytest.raises(ValueError, match='stage review run unavailable'):
            ReviewAdvanceHostService._revalidate_accepted_stage_runtime_sources(
                transaction=transaction, scope=SCOPE,
                command={'markings': ['internal']}, stage_source=approved_source,
            )


def host_command(item, args):
    approved = args['approved_ref'].model_dump(mode='json', by_alias=True)
    return {
        'growthPlanRef': {**approved, 'contentHash': 'sha256:' + approved['contentHash']},
        'stageDecisionRef': args['decision_ref'].model_dump(mode='json', by_alias=True),
        'stageTaskRunId': item.task_run_id,
        'stagePlanRef': item.plan_ref.model_dump(mode='json', by_alias=True),
        'stageAttemptRef': item.stage_attempt_ref.model_dump(mode='json', by_alias=True),
        'stageArtifactRef': item.artifact_ref.model_dump(mode='json', by_alias=True),
        'evalReportRef': {'resourceType': 'EvalReportRevision',
                          'resourceId': item.eval_report_ref.resource_id,
                          'revision': item.eval_report_ref.revision,
                          'contentHash': 'sha256:' + item.eval_report_ref.content_hash},
        'responsibilityPlanRef': item.responsibility_plan_ref.model_dump(mode='json', by_alias=True),
        'cutoffAt': item.created_at.isoformat(),
        'expiresAt': item.expires_at.isoformat(),
    }


def test_review_host_reads_original_accepted_stage_owner_in_same_transaction(source):
    _owner, _draft, item, args = source
    command = host_command(item, args)
    with connect(SCOPE) as conn:
        conn.execute('SET LOCAL ROLE aos_runtime')
        result = ReviewAdvanceHostService._revalidate_accepted_stage_source(
            transaction=HostTransaction(conn), scope=SCOPE, command=command)
    assert result.decision == item
    assert result.approved.prior_ref == item.subject_ref


@pytest.mark.parametrize('fault', ['artifact', 'eval', 'responsibility', 'expiry', 'tenant'])
def test_review_host_rejects_accepted_stage_source_drift(source, fault):
    _owner, _draft, item, args = source
    command = host_command(item, args)
    scope = SCOPE
    if fault == 'artifact':
        command['stageArtifactRef'] = {**command['stageArtifactRef'], 'resourceId': 'other-artifact'}
    elif fault == 'eval':
        command['evalReportRef'] = {**command['evalReportRef'], 'resourceId': 'other-report'}
    elif fault == 'responsibility':
        command['responsibilityPlanRef'] = {**command['responsibilityPlanRef'], 'resourceId': 'other-plan'}
    elif fault == 'expiry':
        command['expiresAt'] = (item.expires_at + timedelta(seconds=1)).isoformat()
    else:
        scope = TenantScope('dev-org', 'dev-project')
    with connect(scope) as conn:
        conn.execute('SET LOCAL ROLE aos_runtime')
        with pytest.raises(ValueError):
            ReviewAdvanceHostService._revalidate_accepted_stage_source(
                transaction=HostTransaction(conn), scope=scope, command=command)


def test_host_parses_owner_source_then_rejects_missing_current_occurrence(source):
    _owner, _draft, item, args = source
    exact = host_command(item, args)
    command = accepted_stage_command()
    command.update(exact)
    command['currentPlanRef'] = {**exact['stagePlanRef'],
                                 'contentHash': 'sha256:' + exact['stagePlanRef']['contentHash']}
    command['taskSpec']['growthPlanRef'] = exact['growthPlanRef']
    command['taskSpec']['artifactRefs'] = [{**exact['stageArtifactRef'],
                                           'contentHash': 'sha256:' + exact['stageArtifactRef']['contentHash']}]
    command['requestHash'] = command_hash({k: v for k, v in command.items() if k != 'requestHash'})
    with connect(SCOPE) as conn:
        conn.execute('SET LOCAL ROLE aos_runtime')
        with pytest.raises(ValueError, match='AutomationOccurrence authority is missing'):
            ReviewAdvanceHostService().revalidate(
                transaction=HostTransaction(conn), scope=SCOPE,
                dispatch=SimpleNamespace(operation_id='ecommerce_growth_review_advance'),
                command=command)

@pytest.mark.parametrize('fault',['run','plan','attempt','approved_hash','tenant'])
def test_other_lineage_is_not_accepted(source,fault):
    _,_,_,original=source;args=dict(original);scope=SCOPE
    if fault=='run':args['task_run_id']='another-run'
    elif fault=='plan':args['plan_ref']=ref('PlanRevision','another-plan')
    elif fault=='attempt':args['stage_attempt_ref']=args['stage_attempt_ref'].model_copy(update={'attempt':2})
    elif fault=='approved_hash':args['approved_ref']=args['approved_ref'].model_copy(update={'content_hash':'0'*64})
    else:scope=TenantScope('dev-org','dev-project')
    with pytest.raises(ValueError):read(args,scope)

def test_current_revocation_and_old_receipt_cannot_authorize(source):
    _,_,item,args=source
    with connect(SCOPE) as conn:
        now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        revoked=hashed(item.model_copy(update={'revision':2,'version':2,'prior_ref':args['decision_ref'],'decision':'revoke','expires_at':None,'created_at':now}))
        current=AnalystStageDecisionStore(HostTransaction(conn),SCOPE).put(revoked,actor=item.created_by,key=item.decision_id+':revoke',expected_version=1)
    with pytest.raises(ValueError):read(args)
    with pytest.raises(ValueError):read(dict(args,decision_ref=current))

def test_changed_approved_body_cannot_inherit_old_accept(source):
    owner,_,item,args=source
    approved=owner.get_plan_exact(SCOPE,args['approved_ref'])
    changed=hashed(approved.model_copy(update={'revision':3,'version':3,'prior_ref':args['approved_ref'],'objective':'different objective'}))
    changed_ref=owner.publish_plan(SCOPE,changed.created_by,item.decision_id+':changed',changed,expected_version=2)
    with pytest.raises(ValueError):read(dict(args,approved_ref=changed_ref))

@pytest.mark.parametrize('source',['content_changed','expired'],indirect=True)
def test_adjacent_body_change_and_expired_accept_rejected(source):
    _,_,_,args=source
    with pytest.raises(ValueError,match='business content|accepted current'):
        read(args)
