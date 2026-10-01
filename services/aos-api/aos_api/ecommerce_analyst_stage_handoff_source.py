"""Read accepted-draft/approved-successor lineage, never grant Handoff permission."""
from dataclasses import dataclass

from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef, GrowthPlanRevision
from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore, canonical_hash
from aos_api.ecommerce_analyst_stage_decision import AnalystStageDecisionRevision, require_stage_decision_applicable
from aos_api.ecommerce_analyst_stage_decision_store import AnalystStageDecisionStore
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import ReviewAdvanceHostService, TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope

_APPROVAL_METADATA = {'revision', 'version', 'prior_ref', 'lifecycle', 'approved_at',
                      'created_by', 'created_at', 'content_hash'}


@dataclass(frozen=True)
class ApprovedStageHandoffSource:
    """Owner-verified sources only; runtime/Eval/permission checks remain required."""
    approved: GrowthPlanRevision
    draft: GrowthPlanRevision
    decision: AnalystStageDecisionRevision


def read_approved_stage_handoff_source(transaction, scope, *, approved_ref,
        decision_ref, task_run_id, plan_ref, stage_attempt_ref):
    if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
        raise TypeError('stage Handoff source requires HostTransaction and TenantScope')
    approved_ref = AnalystExactRef.model_validate(approved_ref.model_dump())
    decision_ref = AnalystExactRef.model_validate(decision_ref.model_dump())
    command_ref = approved_ref.model_dump(mode='json', by_alias=True)
    command_ref['contentHash'] = 'sha256:' + approved_ref.content_hash
    approved = ReviewAdvanceHostService._revalidate_growth_plan(
        transaction=transaction, scope=scope, command={'growthPlanRef': command_ref})
    decision = AnalystStageDecisionStore(transaction, scope).read_current(decision_ref)
    if approved.prior_ref is None or approved.prior_ref != decision.subject_ref:
        raise ValueError('approved successor differs from accepted draft')
    owner = EcommerceAnalystAuthorityStore(TransactionBoundConnectFactory(transaction, scope))
    draft = owner.get_plan_exact(scope, approved.prior_ref)
    if (draft.lifecycle.value != 'draft' or approved.revision != draft.revision + 1
            or approved.version != draft.version + 1 or draft.generation_artifact_ref is None
            or canonical_hash(approved.model_dump(mode='json', by_alias=True, exclude=_APPROVAL_METADATA))
            != canonical_hash(draft.model_dump(mode='json', by_alias=True, exclude=_APPROVAL_METADATA))):
        raise ValueError('approved business content differs from accepted draft')
    now = transaction.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    if (not draft.created_at <= approved.created_at <= now
            or approved.approved_at != approved.created_at
            or draft.created_at > decision.created_at):
        raise ValueError('stage Handoff source chronology drifted')
    require_stage_decision_applicable(scope=scope, decision=decision,
        task_run_id=task_run_id, plan_ref=plan_ref, stage='solution-design',
        stage_attempt_ref=stage_attempt_ref, subject_ref=approved.prior_ref,
        artifact_ref=draft.generation_artifact_ref, eval_report_ref=decision.eval_report_ref,
        responsibility_plan_ref=decision.responsibility_plan_ref, now=now)
    return ApprovedStageHandoffSource(approved=approved, draft=draft, decision=decision)
