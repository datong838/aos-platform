"""Same native caller Judge hold, never an execution or transport permit."""
import json
from uuid import uuid4

from aos_api.aip_budget_reservation_contracts import BudgetExactRef, _derive_bucket_authorities
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore, BudgetReservationBlocked, canonical_hash
from aos_api.aip_model_eval_judge_action import ModelJudgeCallActionGuard
from aos_api.aip_model_governance_policy_contracts import BudgetPolicyRevision
from aos_api.aip_agent_registry_contracts import VersionedAssetRef


class ModelJudgeBudgetStore:
    def __init__(self, *, release_policy, artifact_bytes):
        self._action = ModelJudgeCallActionGuard(release_policy=release_policy, artifact_bytes=artifact_bytes)
        self._ordinary = AipBudgetReservationStore()

    @staticmethod
    def _ref(payload, kind):
        ref = VersionedAssetRef.model_validate(payload)
        if ref.asset_type != kind:
            raise BudgetReservationBlocked('JUDGE_EXACT_BUDGET_SOURCE_REQUIRED')
        return BudgetExactRef(resourceType=kind, resourceId=ref.asset_id,
                              revision=ref.revision, contentHash='sha256:' + ref.content_hash)

    def _sources(self, conn, scope, facts):
        ref = VersionedAssetRef.model_validate(facts['budgetPolicyRef'])
        row = conn.execute("""SELECT r.* FROM aip_model_governance_policy_head h
            JOIN aip_model_governance_policy_revision r USING (org_id,project_id,policy_kind,policy_id)
            WHERE h.org_id=%s AND h.project_id=%s AND h.policy_kind='budget'
              AND h.policy_id=%s AND r.revision=h.current_revision FOR SHARE OF h""",
            (*scope.key, ref.asset_id)).fetchone()
        now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        if (row is None or row['revision'] != ref.revision or row['content_hash'] != ref.content_hash
                or row['lifecycle'] != 'active' or not row['effective_from'] <= now < row['effective_until']):
            raise BudgetReservationBlocked('JUDGE_CURRENT_BUDGET_POLICY_REQUIRED')
        policy = BudgetPolicyRevision.model_validate(row['payload'])
        if (policy.content_hash != ref.content_hash or (policy.tenant.org_id, policy.tenant.project_id) != scope.key
                or policy.currency != facts['currency']):
            raise BudgetReservationBlocked('JUDGE_BUDGET_POLICY_DRIFTED')
        budget_ref = self._ref(policy.budget_revision_ref.model_dump(mode='json', by_alias=True), 'BudgetRevision')
        price_ref = self._ref(facts['priceRef'], 'ModelPriceSnapshotRevision')
        provider_ref = self._ref(facts['providerRef'], 'ProviderInstanceRevision')
        head = conn.execute('SELECT current_revision FROM aip_budget_head WHERE org_id=%s AND project_id=%s AND budget_id=%s FOR SHARE',
                            (*scope.key, budget_ref.resource_id)).fetchone()
        if head is None or int(head['current_revision']) != budget_ref.revision:
            raise BudgetReservationBlocked('JUDGE_CURRENT_BUDGET_HEAD_REQUIRED')
        budget = self._ordinary._budget_authority(conn, scope, budget_ref, now)
        self._ordinary._price_authority(conn, scope, price_ref, now)
        return budget_ref, price_ref, provider_ref, budget, now

    @staticmethod
    def _immutable(row):
        keys = ('reservation_id', 'purpose', 'request_id', 'request_hash', 'proposal_id',
                'proposal_hash', 'approval_event_id', 'approval_ref', 'budget_policy_ref',
                'budget_revision_ref', 'price_ref', 'currency', 'upper_bound_minor', 'state')
        return {key: str(row[key]) if key == 'reservation_id' else row[key] for key in keys}

    @staticmethod
    def _expected_hold(reservation_id, request_id, request_hash, approval_event_id, current, budget_ref, price_ref, amount):
        return dict(reservation_id=str(reservation_id),
            purpose='model-judge-call', request_id=request_id, request_hash=request_hash,
            proposal_id=current['proposalId'], proposal_hash=current['proposalHash'],
            approval_event_id=approval_event_id, approval_ref=current['approvalRef'],
            budget_policy_ref=current['budgetPolicyRef'], budget_revision_ref=budget_ref.model_dump(mode='json', by_alias=True),
            price_ref=price_ref.model_dump(mode='json', by_alias=True), currency=current['currency'],
            upper_bound_minor=amount, state='held')

    def _require_existing_hold(self, conn, scope, existing, immutable, buckets, amount):
        digest = canonical_hash(immutable, prefixed=True)
        if self._immutable(existing) != immutable or existing['content_hash'] != digest:
            raise BudgetReservationBlocked('JUDGE_BUDGET_REPLAY_DRIFTED')
        backing = conn.execute('SELECT * FROM aip_model_judge_budget_reservation_bucket WHERE org_id=%s AND project_id=%s AND reservation_id=%s',
                               (*scope.key, existing['reservation_id'])).fetchall()
        expected = {(b.kind, b.account_id, b.period_start, b.currency, amount) for b in buckets}
        actual = {(b['bucket_kind'], b['account_id'], b['period_start'], b['currency'], b['reserved_minor']) for b in backing}
        if len(backing) != 3 or actual != expected:
            raise BudgetReservationBlocked('JUDGE_BUDGET_BACKING_DRIFTED')
        for bucket in buckets:
            row = self._ordinary._bucket_row(conn, scope, bucket)
            if (row is None or row['period_end'] != bucket.period_end or int(row['limit_minor']) != bucket.limit_minor
                    or int(row['held_minor']) < amount):
                raise BudgetReservationBlocked('JUDGE_BUDGET_BACKING_DRIFTED')

    def require_current_parent(self, conn, scope, parent_limit):
        """Necessary native new-purpose backing; never create a hold or Intent.

        The original fee fence is writable transaction protection. All original
        Source/approval locks and bucket locks stay on the caller transaction.
        """
        from aos_api.aip_model_eval_execution_contracts import ModelJudgeParentBudgetLimit
        parent = ModelJudgeParentBudgetLimit.model_validate(parent_limit)
        if (parent.tenant.org_id, parent.tenant.project_id) != scope.key:
            raise BudgetReservationBlocked('JUDGE_PARENT_TENANT_REQUIRED')
        facts = self._action.require_current_approval(conn, scope, parent.request_id,
            parent.request_hash, parent.approval_ref.resource_id)
        existing = conn.execute('SELECT * FROM aip_model_judge_budget_reservation WHERE org_id=%s AND project_id=%s AND reservation_id=%s',
            (*scope.key, parent.parent_hold_ref.resource_id)).fetchone()
        if existing is None or existing['content_hash'] != parent.parent_hold_ref.content_hash:
            raise BudgetReservationBlocked('JUDGE_EXACT_PARENT_HOLD_REQUIRED')
        budget_ref, price_ref, provider_ref, budget, now = self._sources(conn, scope, facts)
        amount = facts['upperBoundMinor']
        self._ordinary._cost_risk_authority(conn, scope, budget_ref, price_ref, amount,
            provider_ref=provider_ref, new_hold=False)
        buckets = _derive_bucket_authorities(task_account_id='model-judge/' + parent.request_id,
            budget_account_id=budget_ref.resource_id, upper_bound_minor=amount, checked_at=now,
            budget_effective_from=budget['effective_from'], budget_effective_until=budget['effective_until'],
            daily_limit_minor=int(budget['daily_limit_minor']), pilot_limit_minor=int(budget['monthly_limit_minor']),
            timezone_name='Asia/Shanghai')
        # Existing rows only: no INSERT/repair on the parent-reading path.
        for bucket in sorted(buckets, key=lambda item: (item.kind, item.account_id, item.period_start)):
            if self._ordinary._bucket_row(conn, scope, bucket, lock=True) is None:
                raise BudgetReservationBlocked('JUDGE_BUDGET_BACKING_DRIFTED')
        current = self._action.require_current_approval(conn, scope, parent.request_id,
            parent.request_hash, parent.approval_ref.resource_id)
        if self._sources(conn, scope, current)[:3] != (budget_ref, price_ref, provider_ref):
            raise BudgetReservationBlocked('JUDGE_BUDGET_SOURCE_DRIFTED_AFTER_WAIT')
        if (parent.approval_ref.model_dump(mode='json', by_alias=True) != current['approvalRef']
                or parent.budget_policy_ref.model_dump(mode='json', by_alias=True) != current['budgetPolicyRef']
                or parent.price_ref.model_dump(mode='json', by_alias=True) != current['priceRef']
                or parent.currency != current['currency'] or parent.upper_bound_minor != amount):
            raise BudgetReservationBlocked('JUDGE_PARENT_DECLARATION_DRIFTED')
        self._ordinary._cost_risk_authority(conn, scope, budget_ref, price_ref, amount,
            provider_ref=provider_ref, new_hold=False)
        immutable = self._expected_hold(existing['reservation_id'], parent.request_id, parent.request_hash,
            parent.approval_ref.resource_id, current, budget_ref, price_ref, amount)
        self._require_existing_hold(conn, scope, existing, immutable, buckets, amount)
        # The fee-fence check can itself wait. Recheck native database time and
        # original approval/Rule/source windows after every final lock.
        self._action.require_current_approval(conn, scope, parent.request_id,
            parent.request_hash, parent.approval_ref.resource_id)
        self._sources(conn, scope, current)

    def hold(self, conn, scope, request_id, request_hash, approval_event_id):
        # Strict native identity/transaction and all original source locks are
        # established by the exact internal guard, never by caller facts.
        facts = self._action.require_current_approval(conn, scope, request_id, request_hash, approval_event_id)
        if conn.execute("SELECT to_regclass('public.aip_model_judge_budget_reservation') AS relation").fetchone()['relation'] is None:
            raise BudgetReservationBlocked('JUDGE_BUDGET_INSTALLATION_REQUIRED')
        budget_ref, price_ref, provider_ref, budget, now = self._sources(conn, scope, facts)
        amount = facts['upperBoundMinor']
        existing = conn.execute('SELECT * FROM aip_model_judge_budget_reservation WHERE org_id=%s AND project_id=%s AND request_id=%s',
                                (*scope.key, request_id)).fetchone()
        # Writable original fee fence precedes shared bucket locking. The
        # eventual joint caller must preacquire it before physical allocation.
        self._ordinary._cost_risk_authority(conn, scope, budget_ref, price_ref, amount,
                                           provider_ref=provider_ref, new_hold=existing is None)
        buckets = _derive_bucket_authorities(task_account_id='model-judge/' + request_id,
            budget_account_id=budget_ref.resource_id, upper_bound_minor=amount, checked_at=now,
            budget_effective_from=budget['effective_from'], budget_effective_until=budget['effective_until'],
            daily_limit_minor=int(budget['daily_limit_minor']), pilot_limit_minor=int(budget['monthly_limit_minor']),
            timezone_name='Asia/Shanghai')
        self._ordinary._prepare_and_lock_buckets(conn, scope, buckets)
        current = self._action.require_current_approval(conn, scope, request_id, request_hash, approval_event_id)
        current_refs = self._sources(conn, scope, current)
        if current_refs[:3] != (budget_ref, price_ref, provider_ref):
            raise BudgetReservationBlocked('JUDGE_BUDGET_SOURCE_DRIFTED_AFTER_WAIT')
        self._ordinary._cost_risk_authority(conn, scope, budget_ref, price_ref, amount,
                                           provider_ref=provider_ref, new_hold=existing is None)
        immutable = self._expected_hold(existing['reservation_id'] if existing else uuid4(),
            request_id, request_hash, approval_event_id, current, budget_ref, price_ref, amount)
        digest = canonical_hash(immutable, prefixed=True)
        if existing is not None:
            self._require_existing_hold(conn, scope, existing, immutable, buckets, amount)
            return dict(existing)
        self._ordinary._require_bucket_room(conn, scope, buckets, amount)
        fields = tuple(immutable)
        values = [json.dumps(immutable[k]) if k.endswith('_ref') else immutable[k] for k in fields]
        placeholders = ','.join('%s::jsonb' if k.endswith('_ref') else '%s' for k in fields)
        conn.execute(f"INSERT INTO aip_model_judge_budget_reservation(org_id,project_id,{','.join(fields)},content_hash) VALUES(%s,%s,{placeholders},%s)",
                     (*scope.key, *values, digest))
        for bucket in buckets:
            updated = conn.execute('UPDATE aip_budget_bucket SET held_minor=held_minor+%s,version=version+1,updated_at=clock_timestamp() WHERE org_id=%s AND project_id=%s AND bucket_kind=%s AND account_id=%s AND period_start=%s AND currency=%s',
                (amount, *scope.key, bucket.kind, bucket.account_id, bucket.period_start, bucket.currency))
            if updated.rowcount != 1:
                raise BudgetReservationBlocked('JUDGE_SHARED_BUCKET_DRIFTED')
            conn.execute('INSERT INTO aip_model_judge_budget_reservation_bucket(org_id,project_id,reservation_id,bucket_kind,account_id,period_start,currency,reserved_minor) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                (*scope.key, immutable['reservation_id'], bucket.kind, bucket.account_id, bucket.period_start, bucket.currency, amount))
        return {**immutable, 'content_hash': digest}
