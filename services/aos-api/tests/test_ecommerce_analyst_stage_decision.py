from datetime import datetime,timedelta,timezone
import pytest
from aos_api.ecommerce_analyst_stage_decision import AnalystStageDecisionRevision,require_stage_decision_applicable
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.tenant_scope import TenantScope
SCOPE=TenantScope('org-org','dev-project')
NOW=datetime(2026,9,11,12,tzinfo=timezone.utc)


def ref(kind,key):return AnalystExactRef(resourceType=kind,resourceId=key,revision=1,contentHash='a'*64)


def decision(**changes):
    body=dict(tenant=dict(orgId=SCOPE.org_id,projectId=SCOPE.project_id),decision_id='review',revision=1,version=1,
        content_hash='0'*64,created_by='human:reviewer',created_at=NOW,task_run_id='run',plan_ref=ref('PlanRevision','plan'),stage='portrait',
        stage_attempt_ref=dict(resourceType='StepRunAttempt',runId='run',stepKey='portrait',stepRunId='step',attempt=1,inputHash='b'*64),
        subject_ref=ref('InsightRevision','portrait'),artifact_ref=ref('Artifact','original-text'),eval_report_ref=ref('EvalReportRevision','eval'),
        responsibility_plan_ref=ref('ResponsibilityPlanRevision','responsibility'),reviewer=dict(kind='human_principal',resourceId='human:reviewer',version=1),
        decision='accept',reason='核对来源后接受此版本',expires_at=NOW+timedelta(hours=1))
    body.update(changes)
    item=AnalystStageDecisionRevision(**body)
    return item.model_copy(update={'content_hash':canonical_hash(item.model_dump(mode='json',by_alias=True,exclude={'content_hash'}))})


def args(item):
    return dict(scope=SCOPE,decision=item,now=NOW,**{k:getattr(item,k) for k in ('task_run_id','plan_ref','stage','stage_attempt_ref','subject_ref','artifact_ref','eval_report_ref','responsibility_plan_ref')})


def test_exact_accept_and_expiry_boundary():
    item=decision();values=args(item)
    assert require_stage_decision_applicable(**values) is None
    values['now']=item.expires_at
    with pytest.raises(ValueError):require_stage_decision_applicable(**values)


@pytest.mark.parametrize('key',['task_run_id','plan_ref','stage','stage_attempt_ref','subject_ref','artifact_ref','eval_report_ref','responsibility_plan_ref','scope','now','hash'])
def test_every_exact_binding_and_clock_required(key):
    item=decision();values=args(item)
    if key in ('task_run_id','stage'):values[key]='other'
    elif key=='stage_attempt_ref':values[key]=values[key].model_copy(update={'attempt':2})
    elif key=='scope':values[key]=TenantScope('dev-org','dev-project')
    elif key=='now':values[key]=NOW-timedelta(seconds=1)
    elif key=='hash':values['decision']=item.model_copy(update={'reason':'changed'})
    else:values[key]=values[key].model_copy(update={'content_hash':'d'*64})
    with pytest.raises(ValueError):require_stage_decision_applicable(**values)


@pytest.mark.parametrize('kind',['return','reject','revoke'])
def test_non_accept_never_advances(kind):
    item=decision(decision=kind,expires_at=None)
    with pytest.raises(ValueError):require_stage_decision_applicable(**args(item))


@pytest.mark.parametrize('changes',[
    dict(reviewer=dict(kind='agent_instance',resourceId='human:reviewer',version=1)),
    dict(created_by='someone-else'),dict(reason=' '),dict(revision=True),dict(expires_at=None),
    dict(expires_at=NOW+timedelta(days=8)),dict(expires_at=NOW),dict(stage='diagnosis'),
    dict(artifact_ref=ref('Task','other')),dict(revision=2,version=2),
    dict(prior_ref=ref('AnalystStageDecisionRevision','other')),
])
def test_invalid_decision_contract_rejected(changes):
    with pytest.raises(ValueError):decision(**changes)


@pytest.mark.parametrize('field',['plan_ref','subject_ref','stage_attempt_ref','reviewer'])
def test_nested_boolean_version_rejected(field):
    item=decision();raw=getattr(item,field).model_dump(mode='json',by_alias=True)
    raw['attempt' if field=='stage_attempt_ref' else 'version' if field=='reviewer' else 'revision']=True
    with pytest.raises(ValueError):decision(**{field:raw})
