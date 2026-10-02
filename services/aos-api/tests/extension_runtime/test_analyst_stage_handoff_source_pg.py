"""Source join on disposable PG; fixture decisions are not human authority proof."""
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
import os
from uuid import UUID, uuid4
import psycopg
from psycopg.conninfo import conninfo_to_dict
import pytest
from aos_api.asset_registry.composition_contracts import CreateInstallationRequest
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.automation_occurrence_store import AutomationOccurrenceStore, ScheduleBinding
from aos_api.db import connect
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseLifecycle, BusinessInvestigationCaseStore
from aos_api.ecommerce_analyst_authority_contracts import GrowthPlanLifecycle
from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore, canonical_hash
from aos_api.ecommerce_analyst_growth_plan_approval import ApproveGrowthPlanRequest, EcommerceAnalystGrowthPlanApprovalService
from aos_api.ecommerce_analyst_stage_decision_store import AnalystStageDecisionStore, stage_decision_id
from aos_api.ecommerce_analyst_stage_handoff_source import read_approved_stage_handoff_source
from aos_api.ecommerce_analyst_stage_review_command import read_stage_review_eval_source_authority
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import ContentGenerateHostService, ReviewAdvanceHostService, _case_ref, _occurrence_payload, _occurrence_ref
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_growth_plan_approval import plan
from test_ecommerce_analyst_stage_decision import decision, ref
from tests.test_ecommerce_business_investigation_lifecycle import draft_case
from test_ecommerce_review_advance_host import accepted_stage_command, command_hash
from test_ecommerce_content_generate_handoff_lineage import accepted_stage_content_command
from tests.asset_registry.test_m2_core_integration import _composition_input
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
        conn.execute("INSERT INTO meta_org(id,name) VALUES('org-org','isolated fixture') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES('org-org','dev-project','isolated fixture') ON CONFLICT DO NOTHING")
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
        with connect(SCOPE) as conn:
            approval_time=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        approval=EcommerceAnalystGrowthPlanApprovalService(owner, clock=lambda: approval_time).approve(SCOPE,name,ApproveGrowthPlanRequest(draftRef=draft_ref),expected_version=1,idempotency_key=name+':approve',actor='fixture-approver')
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


def test_content_generate_rebuilds_stage_refs_from_original_owner(source):
    _owner, _draft, item, args = source
    candidate = {'sourceKind': 'accepted-stage-v1', **host_command(item, args)}
    with connect(SCOPE) as conn:
        conn.execute('SET LOCAL ROLE aos_runtime')
        transaction = HostTransaction(conn)
        expected = ContentGenerateHostService._accepted_stage_owner_refs(
            transaction=transaction, scope=SCOPE, candidate=candidate)
        assert expected['stageDecisionRef'] == candidate['stageDecisionRef']
        assert expected['growthPlanRef'] == candidate['growthPlanRef']
        assert expected['stageArtifactRef'] == candidate['stageArtifactRef']
        assert expected['stageTaskRunId'] == item.task_run_id
        drift = {**candidate, 'stageArtifactRef': {
            **candidate['stageArtifactRef'], 'resourceId': 'other-artifact'}}
        with pytest.raises(ValueError):
            ContentGenerateHostService._accepted_stage_owner_refs(
                transaction=transaction, scope=SCOPE, candidate=drift)
        with pytest.raises(ValueError):
            ContentGenerateHostService._accepted_stage_owner_refs(
                transaction=transaction, scope=SCOPE,
                candidate={**candidate, 'sourceKind': 'issue-review-v1'})


def test_content_generate_revalidate_requires_persisted_stage_review_before_execution(source):
    _owner, _draft, _item, _args = source
    command = accepted_stage_content_command()
    with connect(SCOPE) as conn:
        conn.execute('SET LOCAL ROLE aos_runtime')
        with pytest.raises(ValueError, match='accepted stage Review Receipt is not unique'):
            ContentGenerateHostService().revalidate(
                transaction=HostTransaction(conn), scope=SCOPE,
                dispatch=SimpleNamespace(operation_id='ecommerce_growth_content_generate'),
                command=command,
            )
        assert conn.execute(
            "SELECT count(*) AS n FROM public.ecommerce_growth_runtime_command_receipt "
            "WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_content_generate'",
            SCOPE.key,
        ).fetchone()['n'] == 0


def test_content_generate_revalidates_original_owner_before_missing_occurrence(source):
    _owner, _draft, item, args = source
    review_command = accepted_stage_command()
    review_command.update(host_command(item, args))
    lineage = {name: review_command[name] for name in (
        'sourceKind', 'cutoffAt', 'expiresAt', 'markings', 'occurrenceRef',
        'caseRef', 'runRef', 'analysisReceiptRef', 'currentPlanRef',
        'growthPlanRef', 'evalReportRef', 'stageDecisionRef', 'stageTaskRunId',
        'stagePlanRef', 'stageAttemptRef', 'stageArtifactRef',
        'responsibilityPlanRef',
    )}
    command = accepted_stage_content_command()

    class OneReceiptConnection:
        def __init__(self, connection, candidate):
            self.connection = connection
            self.candidate = candidate

        def execute(self, query, params=()):
            if 'SELECT response FROM public.ecommerce_growth_runtime_command_receipt' in query:
                assert params[:2] == SCOPE.key
                return SimpleNamespace(fetchall=lambda: [
                    {'response': {'sourceLineage': self.candidate}}
                ])
            return self.connection.execute(query, params)

    with connect(SCOPE) as conn:
        conn.execute('SET LOCAL ROLE aos_runtime')
        transaction = HostTransaction(OneReceiptConnection(conn, lineage))
        with pytest.raises(ValueError, match='AutomationOccurrence authority is missing'):
            ContentGenerateHostService().revalidate(
                transaction=transaction, scope=SCOPE,
                dispatch=SimpleNamespace(operation_id='ecommerce_growth_content_generate'),
                command=command,
            )
        drift = {**lineage, 'stageArtifactRef': {
            **lineage['stageArtifactRef'], 'resourceId': 'other-artifact'}}
        transaction = HostTransaction(OneReceiptConnection(conn, drift))
        with pytest.raises(ValueError, match='accepted stage Handoff differs from current source'):
            ContentGenerateHostService().revalidate(
                transaction=transaction, scope=SCOPE,
                dispatch=SimpleNamespace(operation_id='ecommerce_growth_content_generate'),
                command=command,
            )


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


def test_original_case_and_occurrence_producers_reach_missing_analysis(source):
    _owner, _draft, item, args = source
    case_store = BusinessInvestigationCaseStore(connect)
    case = draft_case('handoff-case-' + uuid4().hex)
    case_store.create_draft(SCOPE, case, idempotency_key=case.case_id + ':draft')
    with connect(SCOPE) as conn:
        now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    now = now.replace(microsecond=0)
    active = case_store.transition(
        SCOPE, case.case_id, BusinessInvestigationCaseLifecycle.ACTIVE,
        expected_version=1, idempotency_key=case.case_id + ':active',
        actor='owner', occurred_at=now,
    ).authority

    # A valid isolated draft satisfies installation FKs; binding/dispatch below
    # remain test control-plane setup, not a signed current installation.
    composition_request, snapshot, payload = _composition_input()
    lock = PostgresCompositionStore(connect).create_or_get(
        org_id=SCOPE.org_id, project_id=SCOPE.project_id,
        request=composition_request, snapshot=snapshot, payload=payload,
        created_by='isolated-test',
    )
    installation = PostgresInstallationStore(connect).create_draft(
        org_id=SCOPE.org_id, project_id=SCOPE.project_id,
        request=CreateInstallationRequest(
            compositionId=lock.composition_id, lockRevision=lock.revision,
            overlayRevision='isolated-handoff', displayName='isolated Handoff producer test',
        ),
        requested_by='isolated-test',
    )
    installation_id, generation, group_id = UUID(str(installation.installation_id)), uuid4(), uuid4()
    with psycopg.connect(os.environ['AOS_DATABASE_URL']) as setup:
        setup.execute('''INSERT INTO extension_runtime_binding(org_id,project_id,installation_id,
            generation,installation_revision,package_lock_ref,profile_ref,execution_epoch,
            desired_state,observed_state,enabled,operation_fence,config_ref)
            VALUES(%s,%s,%s,%s,1,'{}','internal-python-v1',1,'enabled','ready',true,false,'{}')''',
            (*SCOPE.key, installation_id, generation))
        setup.execute('''INSERT INTO extension_operation_dispatch_binding(org_id,project_id,
            operation_id,handler_kind,installation_id,generation,execution_epoch,
            operation_fence,revision,cutover_group_id,cutover_group_revision,updated_by)
            VALUES(%s,%s,'ecommerce_growth_review_advance','extension',%s,%s,1,false,1,%s,1,'fixture')''',
            (*SCOPE.key, installation_id, generation, group_id))
    binding = ScheduleBinding(
        policy_id='handoff-' + uuid4().hex, policy_revision=1,
        policy_hash='sha256:' + 'a' * 64,
        operation_id='ecommerce_growth_review_advance',
        installation_id=installation_id, generation=generation,
        execution_epoch=1, cadence='once', effective_from=now - timedelta(days=1),
        approved=True, enabled=True,
    )
    occurrence_store = AutomationOccurrenceStore(connect)
    occurrence_store.put_binding(SCOPE, binding)
    occurrence = occurrence_store.record_scheduled(
        SCOPE, binding, scheduled_at=now - timedelta(minutes=1),
        local_slot='isolated-handoff', deadline=now + timedelta(hours=1),
    )
    exact = host_command(item, args)
    command = accepted_stage_command()
    command.update(exact)
    command['currentPlanRef'] = {**exact['stagePlanRef'],
                                 'contentHash': 'sha256:' + exact['stagePlanRef']['contentHash']}
    command['taskSpec']['growthPlanRef'] = exact['growthPlanRef']
    command['taskSpec']['artifactRefs'] = [{**exact['stageArtifactRef'],
                                           'contentHash': 'sha256:' + exact['stageArtifactRef']['contentHash']}]
    command['caseRef'] = _case_ref(active)
    with connect(SCOPE) as conn:
        transaction = HostTransaction(conn)
        command['occurrenceRef'] = _occurrence_ref(_occurrence_payload(transaction, SCOPE, occurrence.occurrence_id))
    command['requestHash'] = command_hash({k: v for k, v in command.items() if k != 'requestHash'})
    with connect(SCOPE) as conn:
        conn.execute('SET LOCAL ROLE aos_runtime')
        with pytest.raises(ValueError, match='AnalysisRuntimeReceipt authority is not unique'):
            ReviewAdvanceHostService().revalidate(
                transaction=HostTransaction(conn), scope=SCOPE,
                dispatch=SimpleNamespace(operation_id='ecommerce_growth_review_advance'),
                command=command,
            )
        stage_lineage = {name: command[name] for name in (
            'sourceKind', 'cutoffAt', 'expiresAt', 'markings', 'occurrenceRef',
            'caseRef', 'runRef', 'analysisReceiptRef', 'currentPlanRef',
            'growthPlanRef', 'evalReportRef', 'stageDecisionRef', 'stageTaskRunId',
            'stagePlanRef', 'stageAttemptRef', 'stageArtifactRef',
            'responsibilityPlanRef',
        )}

        class ReviewCandidateConnection:
            def execute(self, query, params=()):
                if 'SELECT response FROM public.ecommerce_growth_runtime_command_receipt' in query:
                    assert params[:2] == SCOPE.key
                    return SimpleNamespace(fetchall=lambda: [
                        {'response': {'sourceLineage': stage_lineage}}
                    ])
                return conn.execute(query, params)

        with pytest.raises(ValueError, match='AnalysisRuntimeReceipt authority is not unique'):
            ContentGenerateHostService().revalidate(
                transaction=HostTransaction(ReviewCandidateConnection()), scope=SCOPE,
                dispatch=SimpleNamespace(operation_id='ecommerce_growth_content_generate'),
                command=accepted_stage_content_command(),
            )

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
