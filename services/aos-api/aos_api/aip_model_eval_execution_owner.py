"""Original Model application preparation, never joint admission or dispatch."""
from datetime import datetime
from typing import Literal

import psycopg
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row
from pydantic import Field, field_validator, model_validator

from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
from aos_api.aip_model_eval_execution_contracts import (
    _ModelExecutionContract, ModelEvalParentBudgetLimit,
    ModelEvalExecutionManifest, ModelJudgeParentBudgetLimit, ModelEvalCaseInputBinding,
)
from aos_api.aip_model_eval_execution_reader import validate_model_parent_hold
from aos_api.aip_model_eval_budget_reservation import AipModelEvalBudgetReservationStore
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.tenant_scope import TenantScope
from aos_api.aip_contracts import TenantContext


class ModelEvalOwnerRejected(ValueError):
    pass


class ModelEvalApplicationPreparation(_ModelExecutionContract):
    """Server-derived necessary facts. No Source/Intent or execution authority."""
    schema_version: Literal['aos.model-eval-application-preparation/v1']
    request_id: str = Field(min_length=1,max_length=200)
    request_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    request: ModelEvalRequestCreate
    parent_limit: ModelEvalParentBudgetLimit
    parent_row_xmin: str = Field(pattern=r'^[0-9]+$')
    caller_xid: str = Field(pattern=r'^[0-9]+$')
    caller_pid: int = Field(strict=True,gt=0)
    checked_at: datetime
    execution_allowed: Literal[False]

    @field_validator('execution_allowed',mode='before')
    @classmethod
    def _nonexecuting(cls,value):
        if type(value) is not bool or value is not False:
            raise ValueError('native nonexecuting preparation required')
        return value


class ModelJudgeApplicationPreparation(_ModelExecutionContract):
    """Server-derived new-purpose facts, never a joint admission certificate."""
    schema_version: Literal['aos.model-judge-application-preparation/v1']
    request_id: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    request: dict
    parent_limit: ModelJudgeParentBudgetLimit
    parent_row_xmin: str = Field(pattern=r'^[0-9]+$')
    caller_xid: str = Field(pattern=r'^[1-9][0-9]*$')
    caller_pid: int = Field(strict=True, gt=0)
    checked_at: datetime
    execution_allowed: Literal[False]

    @field_validator('execution_allowed', mode='before')
    @classmethod
    def _nonexecuting(cls, value):
        return ModelEvalApplicationPreparation._nonexecuting(value)

    @model_validator(mode='after')
    def _exact_request_and_parent(self):
        parent = self.parent_limit
        body = self.request
        governance = body.get('judgeGovernanceApplication')
        governance = governance.get('request') if isinstance(governance, dict) else None
        try:
            expiry = datetime.fromisoformat(body['expiresAt'])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('original Judge preparation expiry required') from exc
        if (not self.request_id.strip() or self.request_id != self.request_id.strip()
                or self.checked_at.utcoffset() is None
                or expiry.utcoffset() is None or self.checked_at >= expiry
                or body.get('schemaVersion') != 'aos.model-judge-call-request/v2'
                or body.get('purpose') != 'model-judge-call'
                or body.get('executionAllowed') is not False
                or canonical_hash(body) != self.request_hash
                or (parent.request_id, parent.request_hash) != (self.request_id, self.request_hash)
                or body.get('tenant') != parent.tenant.model_dump(mode='json', by_alias=True)
                or body.get('currency') != parent.currency
                or type(body.get('upperBoundMinor')) is not int
                or body['upperBoundMinor'] != parent.upper_bound_minor
                or not isinstance(governance, dict)
                or governance.get('budgetPolicyRef') != parent.budget_policy_ref.model_dump(mode='json', by_alias=True)
                or governance.get('priceRef') != parent.price_ref.model_dump(mode='json', by_alias=True)):
            raise ValueError('exact nonexecuting original Judge preparation required')
        return self


class ModelEvalExecutionOwner:
    """Prepare from original tables on caller connection; no execution methods."""

    def _prepare_dual_purpose_bucket_fences(self, conn, scope, request_id,
                                            approval_event_id, *, release_policy,
                                            artifact_bytes) -> None:
        """Internal budget prefix only; no hold, physical admission or Intent.

        The eventual joint caller must acquire its authenticated Source and
        physical account guard before invoking this bucket stage. This method
        neither establishes nor certifies those independent prerequisites.
        """
        from aos_api.aip_budget_reservation_contracts import (
            _derive_bucket_authorities, derive_model_eval_bucket_authorities,
        )
        from aos_api.aip_model_eval_judge_budget import ModelJudgeBudgetStore

        self.prepare_dual_purpose_fee_fences(conn, scope, request_id,
            approval_event_id, release_policy=release_policy, artifact_bytes=artifact_bytes)
        try:
            store = ModelJudgeBudgetStore(release_policy=release_policy, artifact_bytes=artifact_bytes)
            row = conn.execute('''SELECT request_hash FROM aip_model_eval_judge_request
                WHERE org_id=%s AND project_id=%s AND request_id=%s''',
                (*scope.key, request_id)).fetchone()
            if row is None:
                raise ModelEvalOwnerRejected('original two-purpose bucket request required')

            def derive():
                facts = store._action.require_current_approval(conn, scope, request_id,
                    row['request_hash'], approval_event_id)
                target = facts['request']['targetApplication']
                inputs = ((target['request'], target['requestId'], False),
                          (facts, request_id, True))
                originals = [(item, ident, judge, store._sources(conn, scope, item))
                             for item, ident, judge in inputs]
                now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                unique = {}
                refs = []
                for item, ident, judge, sources in originals:
                    budget_ref, price_ref, provider_ref, budget, _ = sources
                    refs.append((budget_ref, price_ref, provider_ref))
                    common = dict(upper_bound_minor=item['upperBoundMinor'], checked_at=now,
                        budget_effective_from=budget['effective_from'],
                        budget_effective_until=budget['effective_until'],
                        daily_limit_minor=int(budget['daily_limit_minor']),
                        pilot_limit_minor=int(budget['monthly_limit_minor']),
                        timezone_name='Asia/Shanghai')
                    if judge:
                        buckets = _derive_bucket_authorities(task_account_id='model-judge/' + ident,
                            budget_account_id=budget_ref.resource_id, **common)
                    else:
                        buckets = derive_model_eval_bucket_authorities(request_id=ident,
                            budget_revision_ref=budget_ref, **common)
                    for bucket in buckets:
                        key = (bucket.kind, bucket.account_id, bucket.period_start, bucket.currency)
                        if key in unique and unique[key] != bucket:
                            raise ModelEvalOwnerRejected('conflicting original shared bucket definitions')
                        unique[key] = bucket
                return facts, tuple(refs), tuple(unique[key] for key in sorted(unique)), now

            facts, refs, buckets, _ = derive()
            identity = conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
            # One original Store call locks the union in its established order.
            # No per-purpose hold can acquire the second set in reverse order.
            store._ordinary._prepare_and_lock_buckets(conn, scope, buckets)
            current, current_refs, current_buckets, _ = derive()
            def stable(value):
                return {k: v for k, v in value.items() if k not in ('checkedAt', 'sourceFactsHash')}
            if stable(current) != stable(facts) or current_refs != refs or current_buckets != buckets:
                raise ModelEvalOwnerRejected('original two-purpose buckets drifted after waits')
            for bucket in buckets:
                backing = store._ordinary._bucket_row(conn, scope, bucket)
                if (backing is None or backing['period_end'] != bucket.period_end
                        or int(backing['limit_minor']) != bucket.limit_minor):
                    raise ModelEvalOwnerRejected('original two-purpose bucket backing drifted')
            for item, refs_for_item in zip((current['request']['targetApplication']['request'], current), refs):
                budget_ref, price_ref, provider_ref = refs_for_item
                store._ordinary._cost_risk_authority(conn, scope, budget_ref, price_ref,
                    item['upperBoundMinor'], provider_ref=provider_ref, new_hold=False)
            # Final fee/source reads can wait too: derive once more, then check
            # actual database time for every original period on this caller.
            final, final_refs, final_buckets, _ = derive()
            after = conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid,clock_timestamp() AS now').fetchone()
            if (stable(final) != stable(facts) or final_refs != refs or final_buckets != buckets
                    or (after['xid'], after['pid']) != (identity['xid'], identity['pid'])
                    or after['now'] >= datetime.fromisoformat(final['approvalExpiresAt'])
                    or after['now'] >= datetime.fromisoformat(final['request']['expiresAt'])
                    or any(not b.period_start <= after['now'] < b.period_end for b in buckets)):
                raise ModelEvalOwnerRejected('current native two-purpose bucket prefix required')
        except (KeyError, TypeError, ValueError, RuntimeError, psycopg.Error) as exc:
            if isinstance(exc, ModelEvalOwnerRejected):
                raise
            raise ModelEvalOwnerRejected('original two-purpose bucket prefix unavailable') from exc

    def prepare_dual_purpose_fee_fences(self, conn: psycopg.Connection, scope: TenantScope,
                                        request_id: str, approval_event_id: str, *,
                                        release_policy, artifact_bytes) -> None:
        """Original two-purpose fee prefix, before any buckets on this entry.

        Current risk checks grant no new hold or physical execution permission.
        Source/physical locks and all-entry caller ordering remain separate.
        """
        from aos_api.aip_model_eval_judge_budget import ModelJudgeBudgetStore
        if (type(conn) is not psycopg.Connection or type(scope) is not TenantScope
                or scope.key != ('org-org', 'dev-project')
                or conn.info.transaction_status != TransactionStatus.INTRANS
                or conn.row_factory is not dict_row
                or any(type(v) is not str or not 1 <= len(v) <= 200 or v.strip() != v
                       for v in (request_id, approval_event_id))):
            raise ModelEvalOwnerRejected('exact native two-purpose fee caller required')
        try:
            identity = conn.execute('''SELECT current_user AS role,
                current_setting('aos.org_id',true) AS org,current_setting('aos.project_id',true) AS project,
                current_setting('transaction_isolation') AS isolation,
                pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid''').fetchone()
            if (identity['role'], identity['org'], identity['project'], identity['isolation']) != ('aos_runtime', *scope.key, 'serializable'):
                raise ModelEvalOwnerRejected('original runtime SERIAL fee prefix required')
            row = conn.execute('''SELECT request_json,request_hash FROM aip_model_eval_judge_request
                WHERE org_id=%s AND project_id=%s AND request_id=%s''', (*scope.key, request_id)).fetchone()
            if row is None or canonical_hash(row['request_json']) != row['request_hash']:
                raise ModelEvalOwnerRejected('original immutable Judge fee source required')
            store = ModelJudgeBudgetStore(release_policy=release_policy, artifact_bytes=artifact_bytes)
            facts = store._action.require_current_approval(conn, scope, request_id, row['request_hash'], approval_event_id)
            target = row['request_json']['targetApplication']['request']
            inputs = sorted((target, facts), key=lambda x: (x['budgetPolicyRef']['assetId'], x['budgetPolicyRef']['revision']))
            sources = [(item, store._sources(conn, scope, item)[:3]) for item in inputs]
            for item, refs in sorted(sources, key=lambda pair: (pair[1][0].resource_id, pair[1][0].revision,
                                                               pair[1][1].resource_id, pair[1][1].revision)):
                budget, price, provider = refs
                store._ordinary._cost_risk_authority(conn, scope, budget, price, item['upperBoundMinor'],
                                                     provider_ref=provider, new_hold=False)
            # Original approval/Rule and every policy/head/price are rechecked
            # after the fee waits. No prepare/hold reader acquires buckets here.
            current = store._action.require_current_approval(conn, scope, request_id, row['request_hash'], approval_event_id)
            def stable(value):
                return {k: v for k, v in value.items() if k not in ('checkedAt', 'sourceFactsHash')}
            if stable(current) != stable(facts) or any(store._sources(conn, scope, item)[:3] != refs for item, refs in sources):
                raise ModelEvalOwnerRejected('original two-purpose fee sources drifted after waits')
            after = conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid,clock_timestamp() AS now').fetchone()
            if ((after['xid'], after['pid']) != (identity['xid'], identity['pid'])
                    or after['now'] >= datetime.fromisoformat(current['approvalExpiresAt'])
                    or after['now'] >= datetime.fromisoformat(current['request']['expiresAt'])):
                raise ModelEvalOwnerRejected('same native two-purpose fee caller required')
        except (KeyError, TypeError, ValueError, RuntimeError, psycopg.Error) as exc:
            if isinstance(exc, ModelEvalOwnerRejected):
                raise
            raise ModelEvalOwnerRejected('current original two-purpose fee prefix unavailable') from exc

    def prepare_judge_application(self, conn: psycopg.Connection, scope: TenantScope,
                                  request_id: str, approval_event_id: str, *,
                                  release_policy, artifact_bytes) -> ModelJudgeApplicationPreparation:
        """Derive a new-purpose parent from original rows on this caller only.

        Caller declarations cannot substitute for the original internal guard.
        No reservation/Intent creation, transaction end or dispatch occurs.
        """
        from aos_api.aip_model_eval_execution_reader import validate_judge_parent_hold
        if (type(conn) is not psycopg.Connection or type(scope) is not TenantScope
                or scope.key != ('org-org', 'dev-project')
                or conn.info.transaction_status != TransactionStatus.INTRANS
                or conn.row_factory is not dict_row
                or any(type(v) is not str or not 1 <= len(v) <= 200 or v.strip() != v
                       for v in (request_id, approval_event_id))):
            raise ModelEvalOwnerRejected('exact native Judge preparation caller required')
        try:
            ctx = conn.execute("""SELECT current_user AS role,
                current_setting('aos.org_id',true) AS org,current_setting('aos.project_id',true) AS project,
                current_setting('transaction_isolation') AS isolation,
                pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid""").fetchone()
            if (ctx['role'], ctx['org'], ctx['project'], ctx['isolation']) != ('aos_runtime', *scope.key, 'serializable'):
                raise ModelEvalOwnerRejected('original runtime SERIAL Judge preparation required')
            hold = conn.execute('''SELECT *,xmin::text AS origin_xid FROM aip_model_judge_budget_reservation
                WHERE org_id=%s AND project_id=%s AND request_id=%s AND approval_event_id=%s''',
                (*scope.key, request_id, approval_event_id)).fetchone()
            row = conn.execute('''SELECT request_hash,request_json,expires_at FROM aip_model_eval_judge_request
                WHERE org_id=%s AND project_id=%s AND request_id=%s''', (*scope.key, request_id)).fetchone()
            if (hold is None or row is None or canonical_hash(row['request_json']) != row['request_hash']
                    or row['request_hash'] != hold['request_hash']):
                raise ModelEvalOwnerRejected('existing exact original Judge request and hold required')
            request = row['request_json']
            governance = request['judgeGovernanceApplication']['request']
            parent = ModelJudgeParentBudgetLimit.model_validate(dict(
                schemaVersion='aos.model-judge-parent-budget/v1', purpose='model-judge-call',
                tenant=TenantContext(orgId=scope.org_id, projectId=scope.project_id),
                parentHoldRef=dict(resourceType='ModelJudgeBudgetReservation', resourceId=str(hold['reservation_id']),
                                   revision=1, contentHash=hold['content_hash']),
                requestId=request_id, requestHash=row['request_hash'], approvalRef=hold['approval_ref'],
                budgetPolicyRef=governance['budgetPolicyRef'], priceRef=governance['priceRef'],
                currency=request['currency'], upperBoundMinor=request['upperBoundMinor'], executionAllowed=False))
            self.prepare_dual_purpose_fee_fences(conn, scope, request_id, approval_event_id,
                                                release_policy=release_policy, artifact_bytes=artifact_bytes)
            validate_judge_parent_hold(conn, expected_tenant=parent.tenant, parent_limit=parent,
                                      release_policy=release_policy, artifact_bytes=artifact_bytes)
            final = conn.execute('''SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid,
                clock_timestamp() AS now,a.expires_at AS approval_expiry
                FROM aip_action_approval_event a WHERE a.org_id=%s AND a.project_id=%s AND a.approval_event_id=%s''',
                (*scope.key, approval_event_id)).fetchone()
            if (final is None or (ctx['xid'], ctx['pid']) != (final['xid'], final['pid'])
                    or row['expires_at'] <= final['now'] or final['approval_expiry'] is None
                    or final['approval_expiry'] <= final['now']):
                raise ModelEvalOwnerRejected('same-caller current Judge preparation required after locks')
            return ModelJudgeApplicationPreparation(
                schemaVersion='aos.model-judge-application-preparation/v1', requestId=request_id,
                requestHash=row['request_hash'], request=request, parentLimit=parent,
                parentRowXmin=hold['origin_xid'], callerXid=final['xid'], callerPid=final['pid'],
                checkedAt=final['now'], executionAllowed=False)
        except (KeyError, TypeError, ValueError, psycopg.Error) as exc:
            if isinstance(exc, ModelEvalOwnerRejected):
                raise
            raise ModelEvalOwnerRejected('current original Judge preparation unavailable or drifted') from exc

    def validate_judge_application_case_set(self, conn: psycopg.Connection, scope: TenantScope,
                                           request_id: str, approval_event_id: str, *,
                                           target_request_id: str, target_request_hash: str,
                                           cases: tuple, case_set_hash: str,
                                           release_policy, artifact_bytes) -> None:
        """Bind the whole ordered input plan to current original Judge sources.

        Re-read through the original internal guard; no caller preparation is
        trusted. This neither reads expected bytes nor certifies Target output,
        joint capacity, unique Intent, commit, or execution permission.
        """
        import re
        if (type(cases) is not tuple or not 1 <= len(cases) <= 10000
                or type(target_request_id) is not str or not 1 <= len(target_request_id) <= 200
                or target_request_id.strip() != target_request_id
                or any(type(v) is not str or re.fullmatch(r'[0-9a-f]{64}', v) is None
                       for v in (target_request_hash, case_set_hash))):
            raise ModelEvalOwnerRejected('exact complete Judge case input declaration required')
        try:
            presented = [ModelEvalCaseInputBinding.model_validate(c).model_dump(mode='json', by_alias=True)
                         for c in cases]
        except (TypeError, ValueError) as exc:
            raise ModelEvalOwnerRejected('strict Judge case input binding required') from exc
        if (len({c['caseId'] for c in presented}) != len(presented)
                or canonical_hash(presented) != case_set_hash):
            raise ModelEvalOwnerRejected('unique exact Judge case input hash required')
        preparation = self.prepare_judge_application(conn, scope, request_id, approval_event_id,
                                                     release_policy=release_policy, artifact_bytes=artifact_bytes)
        body = preparation.request
        original = [dict(caseId=c['caseId'], inputHash=c['inputArtifact']['contentHash'],
                         expectedHash=c['expectedArtifact']['contentHash']
                         if c.get('expectedArtifact') is not None else None)
                    for c in body['cases']]
        target = body['targetApplication']
        if ((target['requestId'], target['requestHash']) != (target_request_id, target_request_hash)
                or presented != original):
            raise ModelEvalOwnerRejected('complete original Target and ordered Judge cases required')
        final = conn.execute('''SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid,
            clock_timestamp() AS now,expires_at FROM aip_action_approval_event
            WHERE org_id=%s AND project_id=%s AND approval_event_id=%s''',
            (*scope.key, approval_event_id)).fetchone()
        if (final is None or (final['xid'], final['pid']) != (preparation.caller_xid, preparation.caller_pid)
                or final['expires_at'] is None or final['now'] >= final['expires_at']
                or final['now'] >= datetime.fromisoformat(body['expiresAt'])):
            raise ModelEvalOwnerRejected('same-caller current Judge cases required after locks')

    def validate_original_model_plan_suite(self,conn: psycopg.Connection,
                                          scope: TenantScope,manifest) -> None:
        """Necessary approved Suite case/hash binding, never Model quality.

        Artifact bytes, input encoding, Judge qualification, formal identity,
        Source/joint admission and actual execution remain independent gates.
        """
        from aos_api.aip_eval_pack_registry import AipEvalPackRegistry,compute_eval_suite_hash
        from aos_api.aip_model_eval_request_store import AipModelEvalRequestStore,ModelEvalRequestBlocked
        plan=ModelEvalExecutionManifest.model_validate(manifest)
        self.validate_original_model_plan_requests(conn,scope,plan)
        try:
            # Reuse the original current frozen Contract/Suite target reader
            # on the same caller connection, with all original locks retained.
            AipModelEvalRequestStore._eval_sources(conn,scope,plan.request)
        except ModelEvalRequestBlocked as exc:
            raise ModelEvalOwnerRejected('current original Suite Contract required') from exc
        with conn.cursor(row_factory=dict_row) as cur:
            ref=plan.request.suite_ref
            row=cur.execute('''SELECT * FROM aip_eval_suite_revision WHERE org_id=%s
                AND project_id=%s AND suite_id=%s AND revision=%s''',
                (*scope.key,ref.asset_id,ref.revision)).fetchone()
            if row is None:
                raise ModelEvalOwnerRejected('complete original Suite required')
            suite=AipEvalPackRegistry._suite_from_row(row)
            if suite.content_hash!=ref.content_hash or compute_eval_suite_hash(suite)!=ref.content_hash:
                raise ModelEvalOwnerRejected('complete original Suite hash required')
            expected={case.case_id:(case.input_artifact.content_hash,
                case.expected_artifact.content_hash if case.expected_artifact is not None else None)
                for case in suite.cases}
            presented={case.case_id:(case.input_hash,case.expected_hash) for case in plan.cases}
            if expected!=presented:
                raise ModelEvalOwnerRejected('complete exact original Suite cases required')
        # Contract/readiness dependencies may have waited after the first
        # deadline check. Recheck every original parent after those waits.
        self.validate_original_model_plan_requests(conn,scope,plan)

    def validate_original_model_plan_input_bytes(self, conn: psycopg.Connection,
                                                 scope: TenantScope, manifest, *, inputs: tuple) -> None:
        """Consume exact original case bytes, never a prompt or token proof.

        Current original request/Suite authority is read on the same caller
        before and after parsing. No arbitrary artifact resolver is invoked;
        supplied bytes must match every approved case exactly once in order.
        Source/joint commit, Model formatting, tokenizer and execution remain
        independent prerequisites. This method creates no persisted fact.
        """
        import hashlib
        import json
        import math

        plan = ModelEvalExecutionManifest.model_validate(manifest)
        if (type(inputs) is not tuple or len(inputs) != len(plan.cases)
                or any(type(item) is not tuple or len(item) != 2
                       or type(item[0]) is not str or type(item[1]) is not bytes
                       or not 0 < len(item[1]) <= 1048576 for item in inputs)
                or tuple(item[0] for item in inputs) != tuple(case.case_id for case in plan.cases)):
            raise ModelEvalOwnerRejected('complete immutable original Model input byte set required')
        self.validate_original_model_plan_suite(conn, scope, plan)

        def unique_object(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError('duplicate JSON member')
                value[key] = item
            return value

        def finite_constant(_value):
            raise ValueError('nonfinite JSON constant')

        def finite_number(text):
            value = float(text)
            if not math.isfinite(value):
                raise ValueError('nonfinite JSON number')
            return value

        for case, (_, raw) in zip(plan.cases, inputs):
            try:
                json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object,
                           parse_constant=finite_constant, parse_float=finite_number)
            except (ValueError, RecursionError) as exc:
                raise ModelEvalOwnerRejected('strict original Model input UTF8 JSON required') from exc
            # Do not normalize/re-serialize: even valid trailing whitespace
            # changes the registered Artifact bytes and must be rejected.
            if hashlib.sha256(raw).hexdigest() != case.input_hash:
                raise ModelEvalOwnerRejected('exact original Model input byte hash required')
        self.validate_original_model_plan_suite(conn, scope, plan)

    def validate_original_model_judge_binding(self, conn: psycopg.Connection,
                                              scope: TenantScope, manifest) -> None:
        """Necessary original Suite Model Judge binding, never dispatch authority.

        Deterministic Judges and ModelRoute dispatch need their own contracts;
        this gate only accepts the approved RegisteredModel-backed branch.
        """
        from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
        from aos_api.aip_eval_contracts import AssetType
        plan = ModelEvalExecutionManifest.model_validate(manifest)
        self.validate_original_model_plan_suite(conn, scope, plan)
        ref = plan.request.suite_ref
        with conn.cursor(row_factory=dict_row) as cur:
            row = cur.execute("""SELECT * FROM aip_eval_suite_revision WHERE org_id=%s
                AND project_id=%s AND suite_id=%s AND revision=%s""",
                (*scope.key, ref.asset_id, ref.revision)).fetchone()
            if row is None:
                raise ModelEvalOwnerRejected('original Suite Model Judge unavailable')
            suite = AipEvalPackRegistry._suite_from_row(row)
        judge_model = suite.judge.model_route
        if judge_model is None or judge_model.asset_type is not AssetType.REGISTERED_MODEL:
            raise ModelEvalOwnerRejected('original Suite Model Judge exact RegisteredModel required')
        for case in plan.cases:
            model = case.judge.model_ref
            if (model.asset_type != 'RegisteredModelRevision'
                    or (model.asset_id, str(model.revision), model.content_hash) !=
                    (judge_model.asset_id, judge_model.revision, judge_model.content_hash)):
                raise ModelEvalOwnerRejected('original Suite Model Judge differs from approved Judge leg')
        self.validate_original_model_plan_requests(conn, scope, plan)

    def validate_original_model_plan_requests(self,conn: psycopg.Connection,
                                             scope: TenantScope,manifest) -> None:
        """Necessary original request/hold/approval bindings for all plan legs.

        Descriptive Source/Intent/joint refs, formal Subject admission,
        issuer provenance, executor identity and quality remain separate gates.
        No holds, transactions, permissions or execution facts are created.
        """
        if (type(conn) is not psycopg.Connection or type(scope) is not TenantScope
                or scope.key!=('org-org','dev-project')
                or conn.info.transaction_status!=TransactionStatus.INTRANS):
            raise ModelEvalOwnerRejected('exact original plan caller required')
        plan=ModelEvalExecutionManifest.model_validate(manifest)
        if (plan.tenant.org_id,plan.tenant.project_id)!=scope.key:
            raise ModelEvalOwnerRejected('original plan tenant required')
        with conn.cursor(row_factory=dict_row) as cur:
            ctx=cur.execute("""SELECT current_user AS role,current_setting('aos.org_id',true) AS org,
                current_setting('aos.project_id',true) AS project,
                current_setting('transaction_isolation') AS isolation""").fetchone()
            if (ctx['role'],ctx['org'],ctx['project'],ctx['isolation'])!=('aos_runtime',*scope.key,'serializable'):
                raise ModelEvalOwnerRejected('original runtime SERIAL plan caller required')
            originals={};hold_ids=[]
            for parent in plan.parent_budget_limits:
                row=cur.execute('''SELECT request_json,request_hash,expires_at FROM aip_model_eval_request
                    WHERE org_id=%s AND project_id=%s AND request_id=%s''',
                    (*scope.key,parent.request_id)).fetchone()
                if (row is None or row['request_hash']!=parent.request_hash
                        or canonical_hash(row['request_json'])!=parent.request_hash):
                    raise ModelEvalOwnerRejected('immutable original plan application required')
                request=ModelEvalRequestCreate.model_validate(row['request_json'])
                if (request.tenant.org_id,request.tenant.project_id)!=scope.key:
                    raise ModelEvalOwnerRejected('original application tenant required')
                originals[parent.parent_hold_ref.resource_id]=(parent,request,row['expires_at'])
                # Use server UUIDs; presented malformed hold identifiers must
                # be rejected without sending them through a SQL UUID cast.
                hold=cur.execute('''SELECT reservation_id FROM aip_model_eval_budget_reservation
                    WHERE org_id=%s AND project_id=%s AND reservation_id::text=%s''',
                    (*scope.key,parent.parent_hold_ref.resource_id)).fetchone()
                if hold is None:
                    raise ModelEvalOwnerRejected('existing original plan hold required')
                hold_ids.append(hold['reservation_id'])
            for case in plan.cases:
                for leg in (case.target,case.judge):
                    parent,request,_=originals[leg.budget_hold_ref.resource_id]
                    if any(left!=right for left,right in (
                        (leg.model_ref,request.source_ref),(leg.provider_ref,request.provider_ref),
                        (leg.price_ref,request.price_ref),(leg.quota_policy_ref,request.quota_policy_ref),
                        (leg.budget_policy_ref,request.budget_policy_ref))):
                        raise ModelEvalOwnerRejected('exact original leg governance required')
                    if leg.purpose=='target' and (parent.request_id!=plan.request_id
                            or parent.request_hash!=plan.request_hash or request!=plan.request):
                        raise ModelEvalOwnerRejected('complete original Target application required')
            heads={}
            for _,request,_ in originals.values():
                key=request.source_ref.asset_id;expected=(request.source_ref.revision,request.expected_head_version)
                if key in heads and heads[key]!=expected:
                    raise ModelEvalOwnerRejected('consistent original Model head required')
                heads[key]=expected
            for key,expected in sorted(heads.items()):
                head=cur.execute('''SELECT current_revision,version FROM aip_registered_model_head
                    WHERE org_id=%s AND project_id=%s AND registered_model_id=%s FOR SHARE''',
                    (*scope.key,key)).fetchone()
                if head is None or (head['current_revision'],head['version'])!=expected:
                    raise ModelEvalOwnerRejected('current original Model head required')
            # Replay the original checker guard from server approval/proposal
            # rows, before budget locks. This creates no holds or fee writes.
            from aos_api.aip_model_eval_action import ModelEvalActionGuard
            approvals=cur.execute('SELECT * FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND approval_event_id=ANY(%s) ORDER BY approval_event_id',
                (*scope.key,[p.approval_ref.resource_id for p in plan.parent_budget_limits])).fetchall()
            if len(approvals)!=len(plan.parent_budget_limits):
                raise ModelEvalOwnerRejected('complete original Model checker approval required')
            proposals=cur.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=ANY(%s) ORDER BY proposal_id FOR SHARE',
                (*scope.key,[a['proposal_id'] for a in approvals])).fetchall()
            by_proposal={p['proposal_id']:p for p in proposals}
            for approval in approvals:
                proposal=by_proposal.get(approval['proposal_id'])
                if (proposal is None or proposal['status']!='approved' or approval['decision']!='approved'
                        or approval['proposal_hash']!=proposal['proposal_hash']
                        or int(approval['proposal_version'])!=int(proposal['version'])-1
                        or approval['action_binding_hash']!=proposal['action_binding_hash']
                        or approval['approval_policy_hash']!=proposal['approval_policy_hash']):
                    raise ModelEvalOwnerRejected('current original Model checker proposal binding required')
                try:
                    ModelEvalActionGuard().check_proposal(conn,scope,approval['actor_id'],proposal,checker=True)
                except (TypeError,ValueError,RuntimeError) as exc:
                    # Preserve the original post-wait deadline rejection even
                    # when the reused guard encounters expiration first.
                    expired_at=cur.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                    if (any(expiry<=expired_at for _,_,expiry in originals.values())
                            or any(a['expires_at'] is None or a['expires_at']<=expired_at for a in approvals)
                            or any(p['expires_at']<=expired_at for p in proposals)):
                        raise ModelEvalOwnerRejected('all original applications and approvals must remain current after locks') from exc
                    raise ModelEvalOwnerRejected('original Model checker authority drifted') from exc
            # Every original bucket is locked once in the original kernel's
            # global key order before per-parent readers can reacquire them.
            cur.execute('''SELECT b.bucket_kind,b.account_id,b.period_start,b.currency
                FROM aip_budget_bucket b WHERE b.org_id=%s AND b.project_id=%s
                  AND EXISTS(SELECT 1 FROM aip_model_eval_budget_reservation_bucket l
                    WHERE (l.org_id,l.project_id,l.bucket_kind,l.account_id,l.period_start,l.currency)=
                          (b.org_id,b.project_id,b.bucket_kind,b.account_id,b.period_start,b.currency)
                      AND l.reservation_id=ANY(%s))
                ORDER BY b.bucket_kind,b.account_id,b.period_start,b.currency FOR SHARE OF b''',
                (*scope.key,hold_ids)).fetchall()
            tenant=TenantContext(orgId=scope.org_id,projectId=scope.project_id)
            for parent,_,_ in sorted(originals.values(),key=lambda item:item[0].request_id):
                validate_model_parent_hold(conn,expected_tenant=tenant,parent_limit=parent)
            approvals=cur.execute('''SELECT approval_event_id,expires_at FROM aip_action_approval_event
                WHERE org_id=%s AND project_id=%s AND approval_event_id=ANY(%s)''',
                (*scope.key,[p.approval_ref.resource_id for p in plan.parent_budget_limits])).fetchall()
            now=cur.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            if (len(approvals)!=len(plan.parent_budget_limits)
                    or any(p['expires_at']<=now for p in proposals)
                    or any(expiry<=now for _,_,expiry in originals.values())
                    or any(row['expires_at'] is None or row['expires_at']<=now for row in approvals)):
                raise ModelEvalOwnerRejected('all original applications and approvals must remain current after locks')

    def prepare_model_application(self,conn: psycopg.Connection,scope: TenantScope,
                                  request_id: str,approval_event_id: str) -> ModelEvalApplicationPreparation:
        if (type(conn) is not psycopg.Connection or type(scope) is not TenantScope or scope.key!=('org-org','dev-project')
            or any(type(v) is not str or not 1<=len(v)<=200 or v.strip()!=v
                   for v in (request_id,approval_event_id))
            or conn.info.transaction_status!=TransactionStatus.INTRANS):
            raise ModelEvalOwnerRejected('exact original caller application required')
        with conn.cursor(row_factory=dict_row) as cur:
            ctx=cur.execute("""SELECT current_user AS role,current_setting('aos.org_id',true) AS org,
                current_setting('aos.project_id',true) AS project,
                current_setting('transaction_isolation') AS isolation,
                pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid""").fetchone()
            if (ctx['role'],ctx['org'],ctx['project'],ctx['isolation'])!=('aos_runtime',*scope.key,'serializable'):
                raise ModelEvalOwnerRejected('original runtime SERIAL caller required')
            hold=cur.execute('''SELECT *,xmin::text AS origin_xid FROM aip_model_eval_budget_reservation
                WHERE org_id=%s AND project_id=%s AND request_id=%s AND approval_event_id=%s''',
                (*scope.key,request_id,approval_event_id)).fetchone()
            if hold is None:
                raise ModelEvalOwnerRejected('existing original budget hold required; preparation cannot create it')
            # Existing hold makes this a replay of the original algorithm, never
            # a new hold. Its current guard checks remain owned by that kernel.
            AipModelEvalBudgetReservationStore().hold(conn,scope,request_id,approval_event_id)
            row=cur.execute('''SELECT request_hash,request_json,expires_at FROM aip_model_eval_request
                WHERE org_id=%s AND project_id=%s AND request_id=%s''',(*scope.key,request_id)).fetchone()
            request=ModelEvalRequestCreate.model_validate(row['request_json'])
            if canonical_hash(row['request_json'])!=row['request_hash'] or row['request_hash']!=hold['request_hash']:
                raise ModelEvalOwnerRejected('immutable original application hash required')
            head=cur.execute('''SELECT current_revision,version FROM aip_registered_model_head
                WHERE org_id=%s AND project_id=%s AND registered_model_id=%s FOR SHARE''',
                (*scope.key,request.source_ref.asset_id)).fetchone()
            if head is None or (head['current_revision'],head['version'])!=(request.source_ref.revision,request.expected_head_version):
                raise ModelEvalOwnerRejected('current original Model head required')
            approval=cur.execute('''SELECT approval_event_id,proposal_id,proposal_version,proposal_hash,
                decision,actor_id,reason,expires_at,created_at,action_binding_hash
                FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND approval_event_id=%s''',
                (*scope.key,approval_event_id)).fetchone()
            parent=ModelEvalParentBudgetLimit.model_validate(dict(
                parentHoldRef=dict(resourceType='ModelEvalBudgetReservation',resourceId=str(hold['reservation_id']),
                                   revision=1,contentHash=hold['content_hash']),requestId=request_id,requestHash=row['request_hash'],
                approvalRef=dict(resourceType='ActionApprovalEvent',resourceId=approval_event_id,
                                 revision=approval['proposal_version'],contentHash=canonical_hash(dict(approval),prefixed=True)),
                budgetPolicyRef=request.budget_policy_ref,priceRef=request.price_ref,
                currency=request.currency,upperBoundMinor=request.upper_bound_minor))
            validate_model_parent_hold(conn,expected_tenant=TenantContext(orgId=scope.org_id,projectId=scope.project_id),parent_limit=parent)
            now=cur.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            if row['expires_at']<=now or approval['expires_at']<=now:
                raise ModelEvalOwnerRejected('application must remain current after all preparation locks')
            return ModelEvalApplicationPreparation(schemaVersion='aos.model-eval-application-preparation/v1',
                requestId=request_id,requestHash=row['request_hash'],request=request,parentLimit=parent,
                parentRowXmin=hold['origin_xid'],callerXid=ctx['xid'],callerPid=ctx['pid'],checkedAt=now,executionAllowed=False)

    def validate_original_target_judge_manifest(self, conn, scope, manifest, *,
                                               release_policy, artifact_bytes) -> None:
        """Read original fresh dual parents and whole request on this caller.

        Internal necessary reader only. Authenticated Source/account guard must
        precede the eventual joint caller; this method provides neither Source
        proof, held per-call allocations/Intents nor finalization or execution.
        """
        from aos_api.aip_model_eval_execution_contracts import ModelEvalTargetJudgeExecutionManifest
        try:
            plan = ModelEvalTargetJudgeExecutionManifest.model_validate(manifest)
            if (type(conn) is not psycopg.Connection or type(scope) is not TenantScope
                    or scope.key != ('org-org','dev-project')
                    or plan.tenant != TenantContext(orgId=scope.org_id,projectId=scope.project_id)
                    or conn.info.transaction_status != TransactionStatus.INTRANS
                    or conn.row_factory is not dict_row):
                raise ModelEvalOwnerRejected('exact native whole newJudge caller required')
            identity = conn.execute("""SELECT current_user AS role,
                current_setting('aos.org_id',true) AS org,current_setting('aos.project_id',true) AS project,
                current_setting('transaction_isolation') AS isolation,
                pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid""").fetchone()
            if (identity['role'],identity['org'],identity['project'],identity['isolation']) != (
                    'aos_runtime',*scope.key,'serializable'):
                raise ModelEvalOwnerRejected('original runtime SERIAL whole caller required')
            # Reject absent/stale/forged parents before the bucket preparer can
            # produce metadata. No row-lock upgrade precedes original Registry.
            for table, parent_limit in (
                    ('aip_model_eval_budget_reservation',plan.target_parent_budget),
                    ('aip_model_judge_budget_reservation',plan.judge_parent_budget)):
                original = conn.execute('SELECT content_hash,xmin::text AS origin_xid FROM '+table+
                    ' WHERE org_id=%s AND project_id=%s AND request_id=%s AND approval_event_id=%s AND reservation_id=%s',
                    (*scope.key,parent_limit.request_id,parent_limit.approval_ref.resource_id,
                     parent_limit.parent_hold_ref.resource_id)).fetchone()
                if (original is None or original['origin_xid'] != identity['xid']
                        or original['content_hash'] != parent_limit.parent_hold_ref.content_hash):
                    raise ModelEvalOwnerRejected('fresh dual parent rows on exact caller required')
            parent = plan.judge_parent_budget
            # Retain original global Registry -> fees -> union buckets ordering.
            self._prepare_dual_purpose_bucket_fences(conn,scope,plan.judge_request_id,
                parent.approval_ref.resource_id,release_policy=release_policy,artifact_bytes=artifact_bytes)
            target_parent = plan.target_parent_budget
            target = self.prepare_model_application(conn,scope,target_parent.request_id,
                target_parent.approval_ref.resource_id)
            # Target preparation can wait. Re-read new-purpose approval, Rule,
            # governance and fee guards afterward; never trust a caller cache.
            judge = self.prepare_judge_application(conn,scope,plan.judge_request_id,
                parent.approval_ref.resource_id,release_policy=release_policy,artifact_bytes=artifact_bytes)
            if (judge.request != plan.judge_request or judge.request_hash != plan.judge_request_hash
                    or judge.parent_limit != parent or target.parent_limit != target_parent
                    or target.request.model_dump(mode='json',by_alias=True) != plan.judge_request['targetApplication']['request']):
                raise ModelEvalOwnerRejected('exact database original whole Manifest facts required')
            if any((p.caller_xid,p.caller_pid,p.parent_row_xmin) != (
                    identity['xid'],identity['pid'],identity['xid']) for p in (target,judge)):
                raise ModelEvalOwnerRejected('fresh dual parent rows on exact caller required')
            final = conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid,clock_timestamp() AS now').fetchone()
            ids = [p.parent_limit.approval_ref.resource_id for p in (target,judge)]
            approvals = conn.execute('''SELECT approval_event_id,expires_at FROM aip_action_approval_event
                WHERE org_id=%s AND project_id=%s AND approval_event_id=ANY(%s)''',(*scope.key,ids)).fetchall()
            now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            deadlines = [target.request.expires_at,datetime.fromisoformat(judge.request['expiresAt'])]
            rule_end = judge.request['ruleFacts']['validUntil']
            if rule_end is not None:
                deadlines.append(datetime.fromisoformat(rule_end))
            if ((final['xid'],final['pid']) != (identity['xid'],identity['pid'])
                    or len(approvals) != 2 or any(a['expires_at'] is None or a['expires_at'] <= now for a in approvals)
                    or any(d <= now for d in deadlines)):
                raise ModelEvalOwnerRejected('current whole Manifest after all original waits required')
        except (KeyError,TypeError,ValueError,RuntimeError,psycopg.Error) as exc:
            if isinstance(exc,ModelEvalOwnerRejected):
                raise
            raise ModelEvalOwnerRejected('original whole newJudge Manifest unavailable or drifted') from exc
