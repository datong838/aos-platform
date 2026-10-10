"""Actual owned Source and original whole plan necessary binding, no dispatch."""
import json
import pytest
from aos_api.aip_model_eval_execution_owner import ModelEvalExecutionOwner
from aos_api.aip_model_eval_budget_reservation import AipModelEvalBudgetReservationStore
from aos_api.aip_model_eval_execution_contracts import ModelEvalExecutionManifest
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
from tests.aip.test_model_eval_execution_contracts import _plan_body

def verify_source_whole_plan(c,scope,command,source,target,judge_app,judge_approval,base,label):
    def dump(v):return v.model_dump(mode='json',by_alias=True)
    c.execute('SAVEPOINT original_source_whole_plan')
    caller=c.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
    AipModelEvalBudgetReservationStore().hold(c,scope,judge_app['request_id'],judge_approval)
    judge=ModelEvalExecutionOwner().prepare_model_application(c,scope,judge_app['request_id'],judge_approval)
    body=_plan_body();body.update(executionId='source-plan-'+target.request_id,requestId=target.request_id,requestHash=target.request_hash,request=dump(target.request),parentBudgetLimits=[dump(v.parent_limit) for v in (target,judge)])
    for purpose,app in zip(('target','judge'),(target,judge)):
        leg=body['cases'][0][purpose];request=app.request
        for field in ('provider_ref','price_ref','quota_policy_ref','budget_policy_ref'):
            leg[type(request).model_fields[field].alias]=dump(getattr(request,field))
        leg.update(modelRef=dump(request.source_ref),approvalRef=dump(app.parent_limit.approval_ref),budgetHoldRef=dump(app.parent_limit.parent_hold_ref),sourceRef=dump(command.source_ref),physicalAccountRef=dump(source.account_candidate_ref))
    ref=target.request.suite_ref
    row=c.execute('SELECT * FROM aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s',(*scope.key,ref.asset_id,ref.revision)).fetchone()
    suite=AipEvalPackRegistry._suite_from_row(row);first=body['cases'][0];body['cases']=[]
    for index,case in enumerate(suite.cases):
        v=json.loads(json.dumps(first));v.update(caseId=case.case_id,inputHash=case.input_artifact.content_hash,expectedHash=case.expected_artifact.content_hash if case.expected_artifact else None)
        for purpose in ('target','judge'):
            for field in ('intentRef','budgetAllocationRef'):v[purpose][field]['resourceId']+='-source-'+str(index)
        body['cases'].append(v)
    body['caseSetHash']=canonical_hash([{k:v[k] for k in ('caseId','inputHash','expectedHash')} for v in body['cases']])
    plan=ModelEvalExecutionManifest.model_validate(body)
    (base/(label+'-whole-source-plan-input.json')).write_text(json.dumps(dict(plan=dump(plan),source=dump(source),source_ref=dump(command.source_ref),caller=caller,execution_allowed=False,limitations='Source/Provider/physical candidate and original two applications/Suite only; allocation/Intent/joint/executor refs descriptive'),indent=2)+'\n')
    from aos_api import aip_physical_capacity_occupation as api
    assert hasattr(api,'validate_original_source_model_plan'),'original signed Source whole-plan validator missing after original two application holds'
    assert api.validate_original_source_model_plan(c,scope,plan,source_commands=(command,)) is None
    for field in ('sourceRef','physicalAccountRef','providerRef'):
        for purpose in ('target','judge'):
            bad=json.loads(json.dumps(body));bad['cases'][-1][purpose][field]['assetId']+='-wrong-original'
            # Target provider is also tied by the typed original request; a
            # typed rejection is a valid pre-SQL failure for that combination.
            with pytest.raises(ValueError):api.validate_original_source_model_plan(c,scope,bad,source_commands=(command,))
    for commands in ((),(command,command)):
        with pytest.raises(ValueError):api.validate_original_source_model_plan(c,scope,plan,source_commands=commands)
    bad_command=command.model_copy(update={'source_ref':command.source_ref.model_copy(update={'asset_id':command.source_ref.asset_id+'-unused'})})
    with pytest.raises(ValueError):api.validate_original_source_model_plan(c,scope,plan,source_commands=(command,bad_command))
    from aos_api.tenant_scope import TenantScope
    with pytest.raises(ValueError):api.validate_original_source_model_plan(c,TenantScope('dev-org','dev-project'),plan,source_commands=(command,))
    after=c.execute('SELECT clock_timestamp() AS now,pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
    assert (after['xid'],after['pid'])==(caller['xid'],caller['pid'])
    (base/(label+'-whole-source-plan-verification.json')).write_text(json.dumps(dict(caller=caller,checked_at=after['now'].isoformat(),cases=len(plan.cases),legs=len(plan.cases)*2,distinct_sources=1,same_original_source=True,original_suite_model_judge_verified=True,original_judge_ref=dump(suite.judge),wrong_source_physical_provider_rejected=True,empty_duplicate_extra_commands_rejected=True,canary_rejected=True,execution_allowed=False),indent=2)+'\n')
    c.execute('ROLLBACK TO SAVEPOINT original_source_whole_plan')
    assert c.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation WHERE request_id=%s',(judge_app['request_id'],)).fetchone()['n']==0
