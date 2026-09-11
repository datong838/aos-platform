"""Current canonical completion and observed subject, not execution permission."""
from aos_api.aip_task_store import AipTaskStore, _canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope

_STAGES = ('portrait','diagnosis','solution-design')
_OUTPUTS = dict(portrait=('InsightRevision','insightRef'),diagnosis=('DecisionSummaryRevision','decisionRef'),
    **{'solution-design':('GrowthPlanRevision','growthPlanRef')})


def read_stage_review_runtime_authority(transaction,scope,*,task_run_id,plan_ref,stage,stage_attempt_ref,subject_ref):
    if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
        raise TypeError('stage review runtime requires HostTransaction and TenantScope')
    if (stage not in _STAGES or plan_ref.resource_type!='PlanRevision'
        or subject_ref.resource_type!=_OUTPUTS[stage][0] or stage_attempt_ref.run_id!=task_run_id
        or stage_attempt_ref.step_key!=stage):
        raise ValueError('exact stage runtime references required')
    run=transaction.execute('SELECT * FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s FOR SHARE',(*scope.key,task_run_id)).fetchone()
    if run is None:raise ValueError('stage review run unavailable')
    task=transaction.execute('SELECT * FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s FOR SHARE',(*scope.key,run['task_id'])).fetchone()
    plan=transaction.execute('SELECT * FROM aip_plan_revision WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s FOR SHARE',(*scope.key,plan_ref.resource_id)).fetchone()
    if (task is None or plan is None or task['current_plan_revision_id']!=plan_ref.resource_id
        or run['plan_revision_id']!=plan_ref.resource_id or plan['task_id']!=task['task_id']
        or plan['revision']!=plan_ref.revision or plan['content_hash']!=plan_ref.content_hash
        or _canonical_hash({k:plan[k] for k in ('steps','dependencies','risk')})!=plan_ref.content_hash
        or plan['approval_status']!='approved' or run['status'] not in {'running','paused','succeeded'}
        or task['status']!={'running':'executing','paused':'paused','succeeded':'completed'}.get(run['status'])
        or [step['stepKey'] for step in plan['steps']]!=list(_STAGES)
        or any(step.get('applicability','applicable')!='applicable' for step in plan['steps'])):
        raise ValueError('stage review task or approved plan is not current')
    steps=transaction.execute('SELECT * FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s ORDER BY attempt DESC FOR SHARE',(*scope.key,task_run_id)).fetchall()
    current=next((step for step in steps if step['step_key']==stage),None)
    previous=[next((step for step in steps if step['step_key']==key),None) for key in _STAGES[:_STAGES.index(stage)]]
    if (current is None or current['step_run_id']!=stage_attempt_ref.step_run_id or current['attempt']!=stage_attempt_ref.attempt
        or current['input_hash']!=stage_attempt_ref.input_hash or current['status']!='succeeded'
        or any(step is None or step['status']!='succeeded' for step in previous)
        or any(step['step_key'] in _STAGES[_STAGES.index(stage)+1:] for step in steps)
        or current['input_hash']!=AipTaskStore._step_input_hash(run,plan,plan['steps'][_STAGES.index(stage)],current['attempt'])):
        raise ValueError('latest stage completion unavailable or successor already started')
    checkpoint=transaction.execute('SELECT * FROM aip_checkpoint WHERE org_id=%s AND project_id=%s AND checkpoint_id=%s FOR SHARE',(*scope.key,run['last_checkpoint_id'])).fetchone()
    if checkpoint is None:raise ValueError('stage completion checkpoint missing')
    state=checkpoint['state_snapshot_ref']
    dependency=AipTaskStore._runtime_dependency_snapshot(run,plan)
    if (checkpoint['run_id']!=task_run_id or checkpoint['step_key']!=stage or checkpoint['attempt']!=current['attempt']
        or checkpoint['plan_revision_id']!=plan_ref.resource_id or checkpoint['input_hash']!=current['input_hash']
        or _canonical_hash(state)!=checkpoint['state_hash'] or state.get('stepRunId')!=current['step_run_id']
        or state.get('status')!='succeeded' or state.get('inputHash')!=current['input_hash']
        or state.get('dependencySnapshotHash')!=_canonical_hash(dependency)
        or checkpoint['dependency_snapshot_hash']!=_canonical_hash(dependency)
        or _canonical_hash(checkpoint['dependency_snapshot'])!=_canonical_hash(dependency)):
        raise ValueError('stage completion checkpoint drifted')
    observe=current['observe_ref']
    if not isinstance(observe,dict) or not observe.get('evidenceId'):raise ValueError('stage observation missing')
    evidence=transaction.execute('''SELECT *,EXISTS(SELECT 1 FROM aip_evidence_revoke_event r
        WHERE r.org_id=e.org_id AND r.project_id=e.project_id AND r.evidence_id=e.evidence_id
        AND r.revision=1 AND r.content_hash=e.content_hash) AS revoked
        FROM aip_evidence e WHERE org_id=%s AND project_id=%s AND evidence_id=%s FOR SHARE''',(*scope.key,observe['evidenceId'])).fetchone()
    if (evidence is None or evidence['revoked'] or evidence['run_id']!=task_run_id or evidence['evidence_type']!='taor.observe'
        or _canonical_hash(evidence['payload'])!=evidence['content_hash']):raise ValueError('stage observation proof unavailable')
    body=evidence['payload']
    if (body.get('stepRunId')!=current['step_run_id'] or body.get('stepKey')!=stage
        or not isinstance(body.get('payload'),dict)
        or body['payload'].get(_OUTPUTS[stage][1])!=subject_ref.model_dump(mode='json',by_alias=True)):
        raise ValueError('stage observed a different subject')
    payload=dict(kind='validate_runtime',taskRunId=task_run_id,
        planRef=plan_ref.model_dump(mode='json',by_alias=True),stage=stage,
        stageAttemptRef=stage_attempt_ref.model_dump(mode='json',by_alias=True),
        subjectRef=subject_ref.model_dump(mode='json',by_alias=True),observationPayload=body)
    snapshot=dict(schemaVersion='aos.stage-review-runtime-snapshot/v1',taskId=task['task_id'],
        taskStatus=task['status'],runId=task_run_id,runStatus=run['status'],
        planRef=payload['planRef'],stageAttemptRef=payload['stageAttemptRef'],
        checkpointId=checkpoint['checkpoint_id'],checkpointStateHash=checkpoint['state_hash'],
        dependencySnapshotHash=checkpoint['dependency_snapshot_hash'],
        observationEvidenceId=evidence['evidence_id'],observationContentHash=evidence['content_hash'])
    return dict(plan=plan,snapshot=snapshot,payload=payload,
        expected={'subjectRef':payload['subjectRef']})


def require_stage_review_runtime(transaction,scope,**values):
    return read_stage_review_runtime_authority(transaction,scope,**values)['plan']


__all__=['read_stage_review_runtime_authority','require_stage_review_runtime']
