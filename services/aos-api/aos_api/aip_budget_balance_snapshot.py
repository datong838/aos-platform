"""Same-snapshot budget observations, without reservation or execution authority."""
from __future__ import annotations
from dataclasses import asdict,dataclass
from datetime import datetime
from typing import Any
import psycopg
from psycopg.pq import TransactionStatus
from aos_api.aip_budget_contracts import BudgetLifecycle,BudgetRevisionCreate
from aos_api.aip_budget_reservation_contracts import BudgetBucketAuthority,ReserveBudgetRequest,derive_bucket_authorities
from aos_api.aip_budget_store import AipBudgetAuthorityStore,BudgetStoreError,canonical_hash
from aos_api.db import connect_read_only
from aos_api.tenant_scope import TenantScope

class BudgetBalanceSnapshotUnavailable(RuntimeError):
    """Unavailable or drifted source must never be treated as zero usage."""

@dataclass(frozen=True)
class BudgetBucketObservation:
    kind:str
    account_id:str
    period_start:datetime
    period_end:datetime
    currency:str
    limit_minor:int
    exposure_minor:int|None
    remaining_minor:int|None
    blocker_codes:tuple[str,...]

@dataclass(frozen=True)
class BudgetBalanceSnapshot:
    org_id:str
    project_id:str
    budget_id:str
    budget_revision:int
    budget_hash:str
    head_version:int
    proposed_request_hash:str
    checked_at:datetime
    snapshot_started_at:datetime
    buckets:tuple[BudgetBucketObservation,...]
    snapshot_hash:str

    @property
    def execution_authorized(self)->bool:
        return False

    @property
    def cost_upper_bound_authorized(self)->bool:
        return False


def observe_bucket(target:BudgetBucketAuthority,row:Any,proposed_upper_bound_minor:int)->BudgetBucketObservation:
    """Observe original four-state exposure; missing rows are not initialized here."""
    if type(proposed_upper_bound_minor) is not int or not 0<proposed_upper_bound_minor<=100_000_000:
        raise ValueError('positive integer proposed upper bound required')
    blockers=();exposure=None;remaining=None
    if row is None:
        blockers=('BUDGET_BUCKET_UNAVAILABLE',)
    elif (row['period_end']!=target.period_end or row['currency']!=target.currency
          or type(row['limit_minor']) is not int or row['limit_minor']!=target.limit_minor):
        blockers=('BUDGET_BUCKET_AUTHORITY_DRIFTED',)
    else:
        values=[row[k] for k in ('held_minor','submitted_minor','settled_minor','unknown_minor')]
        if any(type(v) is not int or v<0 for v in values):
            blockers=('BUDGET_BUCKET_EXPOSURE_INVALID',)
        else:
            exposure=sum(values);remaining=target.limit_minor-exposure
            if row['unknown_minor']>0:
                blockers+=('BUDGET_USAGE_UNKNOWN',)
            if exposure+proposed_upper_bound_minor>target.limit_minor:
                blockers+=('BUDGET_LIMIT_EXCEEDED',)
    return BudgetBucketObservation(target.kind,target.account_id,target.period_start,target.period_end,
                                   target.currency,target.limit_minor,exposure,remaining,blockers)

class BudgetBalanceSnapshotReader:
    def __init__(self,connect_factory=None)->None:
        self._connect=connect_factory or connect_read_only

    def read(self,scope:TenantScope,request:ReserveBudgetRequest)->BudgetBalanceSnapshot:
        # Proposed request addresses the original buckets; it proves no approved cost.
        if type(scope) is not TenantScope or type(request) is not ReserveBudgetRequest:
            raise BudgetBalanceSnapshotUnavailable('exact tenant and original proposed request required')
        request=ReserveBudgetRequest.model_validate(request.model_dump(mode='python',by_alias=True),strict=True)
        with self._connect(scope) as conn:
            if (type(conn) is not psycopg.Connection or conn.closed or conn.autocommit
                or not conn.read_only or conn.info.transaction_status!=TransactionStatus.INTRANS):
                raise BudgetBalanceSnapshotUnavailable('native read-only scoped snapshot required')
            identity=conn.execute("""SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,
                current_setting('aos.project_id',true) AS project_id,
                current_setting('transaction_isolation') AS isolation,
                current_setting('transaction_read_only') AS read_only,clock_timestamp() AS checked_at,
                transaction_timestamp() AS snapshot_started_at""").fetchone()
            if any(identity[k]!=v for k,v in {'role':'aos_runtime','org_id':scope.org_id,
                    'project_id':scope.project_id,'isolation':'repeatable read','read_only':'on'}.items()):
                raise BudgetBalanceSnapshotUnavailable('native read-only scoped snapshot required')
            now=identity['checked_at']
            try:
                budget=AipBudgetAuthorityStore().get(scope,request.policy_ref.resource_id,conn=conn)
            except BudgetStoreError as exc:
                raise BudgetBalanceSnapshotUnavailable('current budget source unavailable') from exc
            raw=conn.execute("""SELECT h.current_revision,h.version AS head_version,r.*
                FROM aip_budget_head h JOIN aip_budget_revision r
                  ON r.org_id=h.org_id AND r.project_id=h.project_id AND r.budget_id=h.budget_id
                 AND r.revision=h.current_revision
                WHERE h.org_id=%s AND h.project_id=%s AND h.budget_id=%s""",
                (*scope.key,request.policy_ref.resource_id)).fetchone()
            content=BudgetRevisionCreate.model_validate(budget.model_dump(include=set(BudgetRevisionCreate.model_fields)))
            expected={'org_id':scope.org_id,'project_id':scope.project_id,'budget_id':budget.budget_id,
                'revision':budget.revision,'content_hash':budget.content_hash,'lifecycle':budget.lifecycle.value,
                'currency':budget.currency,'daily_limit_minor':budget.daily_limit_minor,
                'monthly_limit_minor':budget.monthly_limit_minor,'environment':budget.environment,
                'alert_threshold_pct':budget.alert_threshold_pct,'owner':budget.owner,
                'over_budget_approver':budget.over_budget_approver,'hard_stop':budget.hard_stop,
                'unknown_usage_behavior':budget.unknown_usage_behavior,
                'effective_from':budget.effective_from,'effective_until':budget.effective_until}
            if (raw is None or any(raw[k]!=v for k,v in expected.items())
                or raw['current_revision']!=request.policy_ref.revision or type(raw['head_version']) is not int
                or raw['head_version']<1 or budget.tenant.org_id!=scope.org_id
                or budget.tenant.project_id!=scope.project_id
                or budget.content_hash!=request.policy_ref.content_hash.removeprefix('sha256:')
                or budget.content_hash!=canonical_hash(content.model_dump(mode='json',by_alias=True))
                or budget.lifecycle is not BudgetLifecycle.ACTIVE
                or not budget.effective_from<=now<budget.effective_until
                or not budget.hard_stop or budget.unknown_usage_behavior!='block'):
                raise BudgetBalanceSnapshotUnavailable('current exact active budget source required')
            targets=derive_bucket_authorities(request,checked_at=now,budget_effective_from=budget.effective_from,
                budget_effective_until=budget.effective_until,daily_limit_minor=budget.daily_limit_minor,
                pilot_limit_minor=budget.monthly_limit_minor)
            observations=[]
            for t in targets:
                row=conn.execute("""SELECT period_end,currency,limit_minor,held_minor,submitted_minor,
                    settled_minor,unknown_minor FROM aip_budget_bucket
                    WHERE org_id=%s AND project_id=%s AND bucket_kind=%s AND account_id=%s
                      AND period_start=%s AND currency=%s""",
                    (*scope.key,t.kind,t.account_id,t.period_start,t.currency)).fetchone()
                observations.append(observe_bucket(t,row,request.upper_bound_minor))
            payload={'scope':scope.key,'budget':request.policy_ref.model_dump(mode='json',by_alias=True),
                     'headVersion':raw['head_version'],'proposedRequestHash':request.request_hash(),
                     'checkedAt':now,'snapshotStartedAt':identity['snapshot_started_at'],'buckets':[asdict(x) for x in observations]}
            return BudgetBalanceSnapshot(*scope.key,budget.budget_id,budget.revision,budget.content_hash,
                raw['head_version'],request.request_hash(),now,identity['snapshot_started_at'],tuple(observations),canonical_hash(payload))
