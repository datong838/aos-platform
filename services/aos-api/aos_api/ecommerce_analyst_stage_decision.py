"""Exact human stage decision contracts; callers must verify current Owners."""
from datetime import datetime,timedelta
from typing import Literal
from pydantic import Field,StrictInt,field_validator,model_validator
from aos_api.aip_eval_contracts import EvalStageAttemptRef
from aos_api.aip_production_contracts import AssigneeRef
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef,_RevisionBase
from aos_api.ecommerce_analyst_authority_store import canonical_hash

_SUBJECTS={'portrait':'InsightRevision','diagnosis':'DecisionSummaryRevision','solution-design':'GrowthPlanRevision'}


class AnalystStageDecisionRevision(_RevisionBase):
    schema_version: Literal['aos.analyst-stage-decision/v1']='aos.analyst-stage-decision/v1'
    decision_id: str=Field(min_length=1,max_length=200)
    revision: StrictInt=Field(ge=1)
    version: StrictInt=Field(ge=1)
    task_run_id: str=Field(min_length=1,max_length=200)
    plan_ref: AnalystExactRef
    stage: Literal['portrait','diagnosis','solution-design']
    stage_attempt_ref: EvalStageAttemptRef
    subject_ref: AnalystExactRef
    artifact_ref: AnalystExactRef
    eval_report_ref: AnalystExactRef
    responsibility_plan_ref: AnalystExactRef
    reviewer: AssigneeRef
    decision: Literal['accept','return','reject','revoke']
    reason: str=Field(min_length=1,max_length=2000)
    expires_at: datetime|None=None

    @field_validator('plan_ref','subject_ref','artifact_ref','eval_report_ref','responsibility_plan_ref','prior_ref',mode='before')
    @classmethod
    def _strict_reference_revision(cls,value):
        if isinstance(value,dict) and type(value.get('revision')) is not int:
            raise ValueError('strict numeric exact revision required')
        return value

    @field_validator('stage_attempt_ref','reviewer',mode='before')
    @classmethod
    def _strict_attempt_version(cls,value):
        if isinstance(value,dict):
            key='attempt' if 'attempt' in value else 'version'
            if type(value.get(key)) is not int:
                raise ValueError('strict attempt or reviewer version required')
        return value

    @field_validator('decision_id','task_run_id','created_by','reason')
    @classmethod
    def _canonical(cls,value):
        if not value or value.strip()!=value:raise ValueError('canonical decision identity and reason required')
        return value

    @model_validator(mode='after')
    def _decision_integrity(self):
        self._validate_chain(self.decision_id,'AnalystStageDecisionRevision')
        for ref,kind in ((self.plan_ref,'PlanRevision'),(self.subject_ref,_SUBJECTS[self.stage]),
            (self.artifact_ref,'Artifact'),(self.eval_report_ref,'EvalReportRevision'),
            (self.responsibility_plan_ref,'ResponsibilityPlanRevision')):
            if ref.resource_type!=kind:raise ValueError('stage decision reference type drifted')
        if (self.reviewer.kind!='human_principal' or self.reviewer.resource_id!=self.created_by
            or self.stage_attempt_ref.run_id!=self.task_run_id
            or self.stage_attempt_ref.step_key not in ({'solution-design','solution_design'} if self.stage=='solution-design' else {self.stage})):
            raise ValueError('human reviewer or exact stage attempt required')
        if self.decision=='accept':
            if (self.expires_at is None or self.expires_at.utcoffset() is None
                or not self.created_at<self.expires_at<=self.created_at+timedelta(days=7)):
                raise ValueError('accepted stage requires bounded explicit expiry')
        elif self.expires_at is not None:
            raise ValueError('non-accept decision cannot carry execution lifetime')
        return self


def require_stage_decision_applicable(*,scope,decision,task_run_id,plan_ref,stage,stage_attempt_ref,
    subject_ref,artifact_ref,eval_report_ref,responsibility_plan_ref,now):
    """Compare an Owner-verified current decision, never authenticate a caller body."""
    item=AnalystStageDecisionRevision.model_validate(decision.model_dump())
    if (not isinstance(now,datetime) or now.utcoffset() is None or item.decision!='accept'
        or (item.tenant.org_id,item.tenant.project_id)!=scope.key
        or not item.created_at<=now<item.expires_at
        or canonical_hash(item.model_dump(mode='json',by_alias=True,exclude={'content_hash'}))!=item.content_hash):
        raise ValueError('accepted current stage decision unavailable')
    expected=dict(task_run_id=task_run_id,plan_ref=plan_ref,stage=stage,stage_attempt_ref=stage_attempt_ref,
        subject_ref=subject_ref,artifact_ref=artifact_ref,eval_report_ref=eval_report_ref,responsibility_plan_ref=responsibility_plan_ref)
    if any(getattr(item,key)!=value for key,value in expected.items()):
        raise ValueError('stage decision cannot authorize different inputs')
