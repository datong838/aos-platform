"""Carry consumed development risk limits into new holds and submissions.

Historical reconciliation never calls this gate. A revocation increments the
fence row, so a SERIALIZABLE transaction with an older snapshot must abort.
"""
from aos_api.aip_budget_cost_basis import BudgetCostBasisProposal, DevelopmentRiskProposal
from aos_api.aip_budget_cost_issuer import _provider
from aos_api.aip_budget_cost_proposal_store import _view
from aos_api.aip_budget_activation_store import _member
from aos_api.aip_budget_store import canonical_hash
from aos_api.aip_model_runtime_contracts import ModelPriceSnapshotRevision


class BudgetCostRuntimeBlocked(ValueError):
    pass


def shared_risk_totals(conn, scope, budget_id: str) -> tuple[int, int]:
    """Count ordinary and Model Eval exposure under one BudgetRevision."""
    row=conn.execute("""SELECT sum(n) AS n,sum(risk) AS risk FROM (
        SELECT count(*) AS n,coalesce(sum(upper_bound_minor),0) AS risk
          FROM public.aip_budget_reservation
         WHERE org_id=%s AND project_id=%s
           AND policy_ref->>'resourceType'='BudgetRevision'
           AND policy_ref->>'resourceId'=%s
        UNION ALL
        SELECT count(*) AS n,coalesce(sum(upper_bound_minor),0) AS risk
          FROM public.aip_model_eval_budget_reservation
         WHERE org_id=%s AND project_id=%s
           AND budget_revision_ref->>'resourceType'='BudgetRevision'
           AND budget_revision_ref->>'resourceId'=%s
    ) shared_exposure""",(*scope.key,budget_id,*scope.key,budget_id)).fetchone()
    return int(row['n']), int(row['risk'])


def require_cost_risk(conn, scope, policy_ref, pricing_ref, upper_bound_minor, *, provider_ref=None, new_hold=True) -> ModelPriceSnapshotRevision | None:
    """Return the verified cost price, or None for the legacy non-cost path.

    Use only in the scoped admission transaction. This does not create a hold.
    """
    try:
        receipts=conn.execute("SELECT * FROM public.aip_budget_receipt WHERE org_id=%s AND project_id=%s "
            "AND operation='budget_revision.activate_cost' AND result_ref->>'resourceId'=%s",
            (*scope.key,policy_ref.resource_id)).fetchall()
        if not receipts:
            return  # Existing non-cost budgets keep their established authority path.
        if len(receipts)!=1:raise ValueError('ambiguous activation')
        receipt=receipts[0];result=receipt['result_ref']
        if (result.get('resourceType')!='BudgetRevision' or result.get('revision')!=policy_ref.revision
                or result.get('contentHash')!=policy_ref.content_hash.removeprefix('sha256:')):
            raise ValueError('activation target drift')
        fence=conn.execute('SELECT * FROM public.aip_budget_cost_runtime_fence WHERE org_id=%s AND project_id=%s '
            'AND budget_id=%s AND revision=%s FOR UPDATE',(*scope.key,policy_ref.resource_id,policy_ref.revision)).fetchone()
        if fence is None or fence['decision_id']!=result.get('decisionId'):raise ValueError('fence missing')
        # A real row write serializes concurrent holds and closes stale-snapshot races.
        conn.execute('UPDATE public.aip_budget_cost_runtime_fence SET version=version+1 WHERE org_id=%s AND project_id=%s '
            'AND budget_id=%s AND revision=%s',(*scope.key,policy_ref.resource_id,policy_ref.revision))
        return _verify_cost_risk_contents(conn, scope, policy_ref, pricing_ref,
            upper_bound_minor, receipt=receipt, fence=fence,
            provider_ref=provider_ref, new_hold=new_hold)
    except Exception as exc:
        # Includes serialization failures: caller must reconcile, never transparently resend.
        raise BudgetCostRuntimeBlocked('BUDGET_COST_CURRENT_RISK_AUTHORITY_REQUIRED') from exc


def _verify_cost_risk_contents(conn, scope, policy_ref, pricing_ref, upper_bound_minor,
    *, receipt, fence, provider_ref=None, new_hold=True) -> ModelPriceSnapshotRevision:
    """Internal original-content verifier, without changing the admission fence.

    The admitting caller must lock the original fence before calling this helper.
    It supplies no independent permission, receipt, reservation or retry behavior.
    Exceptions propagate to that caller, including native serialization failures.
    """
    result=receipt['result_ref']
    row=conn.execute('SELECT * FROM public.aip_budget_cost_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
        (*scope.key,result.get('proposalId'))).fetchone()
    if row is None:raise ValueError('proposal missing')
    view=_view(row,scope);p=BudgetCostBasisProposal.from_canonical_payload(view['proposal'])
    digest=canonical_hash(dict(domain='aos.budget-cost-consume/v1',tenant=p.tenant.model_dump(by_alias=True),
        proposalId=row['proposal_id'],proposalHash=p.proposal_hash,decisionId=fence['decision_id']))
    expected=dict(resourceType='BudgetRevision',resourceId=p.target.budget_id,revision=p.target.revision,
        contentHash=canonical_hash(view['proposal']['target']),proposalId=row['proposal_id'],proposalHash=p.proposal_hash,
        decisionId=fence['decision_id'],receiptId='budget-cost-consume-'+digest)
    if result!=expected or receipt['request_hash']!=digest or receipt['idempotency_key']!=row['proposal_id'] or receipt['receipt_id']!=expected['receiptId']:
        raise ValueError('receipt drift')
    head=conn.execute('SELECT current_revision,version FROM public.aip_budget_head WHERE org_id=%s AND project_id=%s '
        'AND budget_id=%s FOR SHARE',(*scope.key,p.target.budget_id)).fetchone()
    if head is None or head['current_revision']!=p.target.revision or head['version']!=p.expected_head_version+1:
        raise ValueError('current budget head drift')
    decision=conn.execute('SELECT * FROM public.aip_budget_cost_decision WHERE org_id=%s AND project_id=%s AND decision_id=%s',
        (*scope.key,fence['decision_id'])).fetchone()
    if (decision is None or decision['proposal_id']!=row['proposal_id'] or decision['proposal_hash']!=p.proposal_hash
            or decision['decision']!='approved' or decision['actor_subject']!=p.checker_subject
            or not isinstance(p.basis,DevelopmentRiskProposal)
            or decision['source_ref']!=p.basis.provider.model_dump(by_alias=True)
            or conn.execute('SELECT 1 FROM public.aip_budget_cost_revocation WHERE org_id=%s AND project_id=%s AND decision_id=%s',
                (*scope.key,fence['decision_id'])).fetchone()):raise ValueError('approval revoked or drifted')
    _member(conn,scope,p.maker_subject,label='MAKER');_member(conn,scope,p.checker_subject,label='CHECKER')
    _provider(conn,scope,p)
    # Hold the current price head through new hold/submission admission.
    # A concurrent withdrawal must serialize; an old SERIALIZABLE snapshot aborts.
    price_head=conn.execute('SELECT current_revision FROM public.aip_model_price_snapshot_head '
        'WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s FOR SHARE',
        (*scope.key,pricing_ref.resource_id)).fetchone()
    if price_head is None or price_head['current_revision']!=pricing_ref.revision:
        raise ValueError('current development price head drift')
    price_row=conn.execute('SELECT payload,content_hash,lifecycle FROM public.aip_model_price_snapshot_revision '
        'WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s AND revision=%s',
        (*scope.key,pricing_ref.resource_id,pricing_ref.revision)).fetchone()
    price=ModelPriceSnapshotRevision.model_validate(price_row['payload'] if price_row else None)
    body=price.model_dump(mode='json',by_alias=True)
    now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    if (price.content_hash!=pricing_ref.content_hash.removeprefix('sha256:') or price.content_hash!=price_row['content_hash']
        or price.content_hash!=canonical_hash({k:v for k,v in body.items() if k not in {'tenant','revision','contentHash','createdBy','createdAt'}})
        or price_row['lifecycle']!='active' or price.lifecycle.value!='active' or price.tenant!=p.tenant
        or price.price_snapshot_id!=pricing_ref.resource_id or price.revision!=pricing_ref.revision
        or not p.target.effective_from<=now<p.target.effective_until or not price.effective_from<=now
        or price.effective_until is None or now>=price.effective_until or price.development_cost_authorization is None):
        raise ValueError('exact bounded development price required')
    auth=price.development_cost_authorization
    auth.require_scope(scope=scope,provider=p.basis.provider,provider_model_id=p.basis.provider_model_id,
        approval_ref=fence['decision_id'],now=now)
    if auth.effective_from<p.target.effective_from or auth.effective_until>p.target.effective_until:
        raise ValueError('authorization window drift')
    if provider_ref is not None and (provider_ref.resource_type,provider_ref.resource_id,provider_ref.revision,
        provider_ref.content_hash.removeprefix('sha256:'))!=(p.basis.provider.asset_type,p.basis.provider.asset_id,
        p.basis.provider.revision,p.basis.provider.content_hash):raise ValueError('submission provider drift')
    if type(upper_bound_minor) is not int or upper_bound_minor!=p.basis.per_request_risk_minor:
        raise ValueError('exact per-request risk hold required')
    # Both callers spend the same activated BudgetRevision.  Keep this
    # query after the writable fence lock so concurrent ordinary and Eval
    # holds cannot each observe the other's old total.
    used_count, used_risk = shared_risk_totals(conn,scope,p.target.budget_id)
    extra=1 if new_hold else 0
    if used_count+extra>p.basis.max_requests or used_risk+upper_bound_minor*extra>p.basis.total_risk_minor:
        raise ValueError('risk allowance exhausted')
    return price
