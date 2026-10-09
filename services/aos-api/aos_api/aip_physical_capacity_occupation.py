"""Same-caller Source/Model preparation; no physical admission or dispatch."""
from datetime import datetime
from typing import Literal

import psycopg
from psycopg.rows import dict_row
from pydantic import field_validator

from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
from aos_api.aip_model_eval_execution_contracts import _ModelExecutionContract
from aos_api.aip_model_eval_execution_owner import (
    ModelEvalApplicationPreparation, ModelEvalExecutionOwner, ModelEvalOwnerRejected,
)
from aos_api.aip_model_eval_budget_reservation import AipModelEvalBudgetReservationStore
from aos_api.aip_provider_capacity_occupation_source import consume_capacity_source_for_occupation
from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySourceV2
from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityConsumptionCommand
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.tenant_scope import TenantScope
from aos_api.aip_physical_capacity_occupation_contracts import PhysicalAccountGuardPreparation


class SourceModelPreparation(_ModelExecutionContract):
    """Necessary facts only. The parent hold remains in the caller transaction."""
    schema_version: Literal['aos.source-model-application-preparation/v1']
    source_ref: FormalExactRef
    source: PublishedProviderCapacitySourceV2
    application: ModelEvalApplicationPreparation
    checked_at: datetime
    execution_allowed: Literal[False]
    physical_guard: PhysicalAccountGuardPreparation | None = None

    @field_validator('execution_allowed', mode='before')
    @classmethod
    def _nonexecuting(cls, value):
        return ModelEvalApplicationPreparation._nonexecuting(value)


def prepare_source_model_application(
    conn: psycopg.Connection, scope: TenantScope,
    source_command: ProviderCapacityConsumptionCommand,
    request_id: str, approval_event_id: str,
) -> SourceModelPreparation:
    return _prepare_source_model_application(conn,scope,source_command,request_id,approval_event_id,guarded=False)


def prepare_guarded_source_model_application(conn,scope,source_command,request_id,approval_event_id) -> SourceModelPreparation:
    """Explicit isolated joint preparation; requires separately installed guard."""
    return _prepare_source_model_application(conn,scope,source_command,request_id,approval_event_id,guarded=True)


def _prepare_source_model_application(conn,scope,source_command,request_id,approval_event_id,*,guarded):
    if (type(scope) is not TenantScope or scope.key != ('org-org', 'dev-project')
        or any(type(value) is not str or not 1 <= len(value) <= 200 or value.strip() != value
               for value in (request_id, approval_event_id))):
        raise ModelEvalOwnerRejected('exact positive original application required')
    # This original reader authenticates the actual SCRAM session/tenant,
    # signature, current owner, installation and Source prefix on this conn.
    # Its locks precede all Model/budget locks and survive until caller ends.
    source = consume_capacity_source_for_occupation(conn, source_command)
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute('''SELECT request_json,request_hash FROM aip_model_eval_request
            WHERE org_id=%s AND project_id=%s AND request_id=%s''',
            (*scope.key, request_id)).fetchone()
        if row is None or canonical_hash(row['request_json']) != row['request_hash']:
            raise ModelEvalOwnerRejected('immutable original application required')
        request = ModelEvalRequestCreate.model_validate(row['request_json'])
        provider = request.provider_ref
        if not any((ref.asset_type, ref.asset_id, ref.revision, ref.content_hash)
                   == (provider.asset_type, provider.asset_id, provider.revision, provider.content_hash)
                   for ref in source.provider_refs):
            raise ModelEvalOwnerRejected('original application Provider must exactly belong to Source')
        physical_guard=None
        if guarded:
            from aos_api.aip_model_governance_policy_contracts import BudgetPolicyRevision
            from aos_api.aip_budget_reservation_contracts import BudgetExactRef
            from aos_api.aip_budget_cost_runtime import require_cost_risk
            from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
            from psycopg.types.json import Jsonb
            policy_row=cur.execute('''SELECT r.content_hash,r.payload FROM aip_model_governance_policy_head h
              JOIN aip_model_governance_policy_revision r USING(org_id,project_id,policy_kind,policy_id)
              WHERE h.org_id=%s AND h.project_id=%s AND h.policy_kind='budget'
                AND h.policy_id=%s AND r.revision=h.current_revision AND r.revision=%s FOR SHARE OF h''',
              (*scope.key,request.budget_policy_ref.asset_id,request.budget_policy_ref.revision)).fetchone()
            if policy_row is None or policy_row['content_hash']!=request.budget_policy_ref.content_hash:
                raise ModelEvalOwnerRejected('current original budget policy required before physical guard')
            policy=BudgetPolicyRevision.model_validate(policy_row['payload'])
            def budget_ref(ref):
                return BudgetExactRef(resourceType=ref.asset_type,resourceId=ref.asset_id,revision=ref.revision,contentHash='sha256:'+ref.content_hash)
            # Reuse original current-risk algorithm and its real UPDATE fence.
            # Complete all-entry writer isolation is still required to deploy.
            require_cost_risk(conn,scope,budget_ref(policy.budget_revision_ref),budget_ref(request.price_ref),
                              request.upper_bound_minor,provider_ref=budget_ref(request.provider_ref))
            guard_fact=cur.execute('SELECT public.prepare_capacity_occupation_account_guard(%s,%s::jsonb) AS fact',
                                  (_consumption_packet(source_command),Jsonb(source_command.source_ref.model_dump(mode='json',by_alias=True)))).fetchone()['fact']
            physical_guard=PhysicalAccountGuardPreparation.model_validate(guard_fact)
        AipModelEvalBudgetReservationStore().hold(conn, scope, request_id, approval_event_id)
        application = ModelEvalExecutionOwner().prepare_model_application(
            conn, scope, request_id, approval_event_id)
        # Recheck original authenticated authority after budget waits. This is
        # preparation currentness, never a caller COMMIT or dispatch guarantee.
        if consume_capacity_source_for_occupation(conn, source_command) != source:
            raise ModelEvalOwnerRejected('same current Source required')
        now = cur.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        identity = cur.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        if (not source.valid_from <= now < source.valid_until
            or (identity['xid'], identity['pid']) != (application.caller_xid, application.caller_pid)):
            raise ModelEvalOwnerRejected('current same-caller Source preparation required')
        if physical_guard is not None and (
            (physical_guard.xid,physical_guard.pid)!=(identity['xid'],identity['pid'])
            or physical_guard.physical_account_id!=source.physical_account_id
            or physical_guard.source_ref!=source_command.source_ref):
            raise ModelEvalOwnerRejected('same-caller physical guard required')
        return SourceModelPreparation(
            schemaVersion='aos.source-model-application-preparation/v1',
            sourceRef=source_command.source_ref, source=source, application=application,
            checkedAt=now, executionAllowed=False,physicalGuard=physical_guard)


def validate_original_source_model_plan(conn,scope,manifest,*,source_commands) -> None:
    """Necessary original Source/whole-plan binding; no joint admission."""
    from psycopg.pq import TransactionStatus
    from aos_api.aip_model_eval_execution_contracts import ModelEvalExecutionManifest
    if (type(conn) is not psycopg.Connection or type(scope) is not TenantScope
            or scope.key!=('org-org','dev-project')
            or conn.info.transaction_status!=TransactionStatus.INTRANS
            or type(source_commands) is not tuple or not 0<len(source_commands)<=20000):
        raise ModelEvalOwnerRejected('exact original Source plan caller and immutable commands required')
    plan=ModelEvalExecutionManifest.model_validate(manifest)
    if (plan.tenant.org_id,plan.tenant.project_id)!=scope.key:
        raise ModelEvalOwnerRejected('positive original Source plan tenant required')
    commands=[ProviderCapacityConsumptionCommand.model_validate(value) for value in source_commands]
    def key(ref):return (ref.asset_type,ref.asset_id,ref.revision,ref.content_hash)
    indexed={key(command.source_ref):command for command in commands}
    wanted={key(leg.source_ref) for case in plan.cases for leg in (case.target,case.judge)}
    if len(indexed)!=len(commands) or set(indexed)!=wanted:
        raise ModelEvalOwnerRejected('complete exact original Source command set required')
    with conn.cursor(row_factory=dict_row) as cur:
        caller=cur.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        # Original authenticated Source prefix precedes this entry's Model
        # locks. No client Source body, active flag or physical DTO is trusted.
        sources={k:consume_capacity_source_for_occupation(conn,indexed[k]) for k in sorted(indexed)}
        for case in plan.cases:
            for leg in (case.target,case.judge):
                source=sources[key(leg.source_ref)]
                if (not any(key(ref)==key(leg.provider_ref) for ref in source.provider_refs)
                        or key(source.account_candidate_ref)!=key(leg.physical_account_ref)):
                    raise ModelEvalOwnerRejected('exact original Source Provider and physical candidate required for every leg')
        ModelEvalExecutionOwner().validate_original_model_judge_binding(conn,scope,plan)
        for k in sorted(indexed):
            if consume_capacity_source_for_occupation(conn,indexed[k])!=sources[k]:
                raise ModelEvalOwnerRejected('same current original Source for whole plan required')
        # Original request/approval/proposal records were validated and their
        # mutable heads locked above. Recheck their windows after Source waits.
        deadlines=cur.execute('''SELECT r.expires_at AS request_expiry,
            a.expires_at AS approval_expiry,p.expires_at AS proposal_expiry
            FROM aip_model_eval_request r JOIN aip_model_eval_budget_reservation h
              USING(org_id,project_id,request_id)
            JOIN aip_action_approval_event a ON (h.org_id,h.project_id,h.approval_event_id)=
              (a.org_id,a.project_id,a.approval_event_id)
            JOIN aip_action_proposal p ON (a.org_id,a.project_id,a.proposal_id)=
              (p.org_id,p.project_id,p.proposal_id)
            WHERE r.org_id=%s AND r.project_id=%s AND r.request_id=ANY(%s)
              AND h.reservation_id::text=ANY(%s)''',
            (*scope.key,[p.request_id for p in plan.parent_budget_limits],
             [p.parent_hold_ref.resource_id for p in plan.parent_budget_limits])).fetchall()
        now=cur.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        after=cur.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        if (caller!=after or len(deadlines)!=len(plan.parent_budget_limits)
                or any(expiry is None or expiry<=now for row in deadlines for expiry in row.values())
                or any(not source.valid_from<=now<source.valid_until for source in sources.values())):
            raise ModelEvalOwnerRejected('all original Model and Source windows must remain current on same caller after waits')


def prepare_shared_parent_risk_plan(conn, scope, source_command, manifest, *,
                                    release_policy, artifact_bytes):
    """Bind all original v3 obligations to the native private risk producer.

    The result remains caller-owned prepared risk. This function neither
    commits nor signs, admits, dispatches or releases an actual call.
    """
    from uuid import UUID
    from psycopg.pq import TransactionStatus
    from psycopg.types.json import Jsonb
    from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
    from aos_api.aip_model_eval_execution_contracts import ModelEvalTargetJudgeSharedRiskManifest

    try:
        if (type(conn) is not psycopg.Connection or conn.closed or conn.autocommit
                or conn.read_only or conn.info.transaction_status != TransactionStatus.INTRANS
                or not conn.pgconn.used_password or conn.row_factory is not dict_row
                or conn.info.get_parameters().get('require_auth') != 'scram-sha-256'
                or type(scope) is not TenantScope or scope.key != ('org-org', 'dev-project')
                or type(source_command) is not ProviderCapacityConsumptionCommand):
            raise ValueError('native original shared-parent caller required')
        plan = ModelEvalTargetJudgeSharedRiskManifest.model_validate(manifest)
        plan_id = UUID(plan.execution_id)
        if str(plan_id) != plan.execution_id:
            raise ValueError('canonical native plan UUID required')
        command = ProviderCapacityConsumptionCommand.model_validate(source_command)

        def identity():
            return conn.execute("""SELECT session_user AS login,current_user AS role,
              current_setting('aos.org_id',true) AS org_id,current_setting('aos.project_id',true) AS project_id,
              current_setting('transaction_isolation') AS isolation,current_setting('transaction_read_only') AS readonly,
              current_setting('TimeZone') AS timezone,current_setting('session_replication_role') AS replication,
              pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid""").fetchone()

        before = identity()
        if tuple(before[k] for k in ('login', 'role', 'org_id', 'project_id',
                                     'isolation', 'readonly', 'timezone', 'replication')) != (
                'aos_provider_capacity_occupation', 'aos_runtime', *scope.key,
                'serializable', 'off', 'UTC', 'origin'):
            raise ValueError('exact native occupation session required')
        source = consume_capacity_source_for_occupation(conn, command)
        def key(ref):
            return (str(ref.asset_type), ref.asset_id, str(ref.revision), ref.content_hash)
        for case in plan.cases:
            for leg in (case.target, case.judge):
                if (key(leg.source_ref) != key(command.source_ref)
                        or key(leg.physical_account_ref) != key(source.account_candidate_ref)
                        or not any(key(leg.provider_ref) == key(ref) for ref in source.provider_refs)):
                    raise ValueError('complete original Source binding required for every leg')
        owner = ModelEvalExecutionOwner()
        owner.validate_original_target_judge_shared_risk_manifest(conn, scope, plan,
            release_policy=release_policy, artifact_bytes=artifact_bytes)
        target, judge = plan.target_parent_budget, plan.judge_parent_budget
        packet = _consumption_packet(command)
        row = conn.execute('''SELECT public.prepare_capacity_plan_risk(
          %s,%s::jsonb,%s::uuid,%s,%s,%s::uuid,%s,%s,%s::uuid) AS fact''',
            (packet, Jsonb(command.source_ref.model_dump(mode='json', by_alias=True)),
             UUID(target.parent_hold_ref.resource_id), target.request_id, target.request_hash,
             UUID(judge.parent_hold_ref.resource_id), judge.request_id, judge.request_hash, plan_id)).fetchone()
        if row is None:
            raise ValueError('native complete risk row required')
        result = row['fact']
        body = result['immutable']
        facts = body['originalFacts']
        expected_risks = []
        for purpose, parent, application in (
                ('target', target, plan.judge_request['targetApplication']['request']),
                ('judge', judge, plan.judge_request)):
            fact = facts[purpose]
            if (fact['application'] != application
                    or (fact['reservationId'], fact['contentHash'], fact['requestId'], fact['requestHash'],
                        fact['approvalEventId'], fact['upperBoundMinor'], fact['currency']) != (
                        parent.parent_hold_ref.resource_id, parent.parent_hold_ref.content_hash,
                        parent.request_id, parent.request_hash, parent.approval_ref.resource_id,
                        parent.upper_bound_minor, parent.currency)
                    or (fact['xid'], fact['pid'], fact['physicalAccountId']) != (
                        before['xid'], before['pid'], source.physical_account_id)
                    or fact['sourceRef'] != command.source_ref.model_dump(mode='json', by_alias=True)):
                raise ValueError('exact native parent risk and original application required')
            expected_risks.append(dict(purpose=purpose, parentHold=parent.parent_hold_ref.resource_id,
                parentHash=parent.parent_hold_ref.content_hash, upperBoundMinor=parent.upper_bound_minor,
                currency=parent.currency))
        expected_legs = [dict(case=case, purpose=purpose,
            parentHold=parent.parent_hold_ref.resource_id, state=state)
            for case in plan.judge_request['cases']
            for purpose, parent, state in (
                ('target', target, 'awaiting_input_binding'), ('judge', judge, 'awaiting_target_result'))]
        if (body['schemaVersion'] != 'aos.capacity-complete-plan-risk/v1'
                or body['riskMode'] != 'original_shared_parent_caps'
                or body['tenant'] != plan.tenant.model_dump(mode='json', by_alias=True)
                or body['state'] != 'prepared_risk_only'
                or body['executionAllowed'] is not False or result['executionAllowed'] is not False
                or result['planId'] != plan.execution_id or body['planId'] != plan.execution_id
                or (body['callerLogin'], body['callerXid'], body['callerPid']) != (
                    before['login'], before['xid'], before['pid'])
                or facts['cases'] != plan.judge_request['cases']
                or body['parentRisks'] != expected_risks or body['legs'] != expected_legs
                or result['contentHash'] != 'sha256:' + canonical_hash(body)):
            raise ValueError('whole native risk body must bind the complete v3 plan')
        if consume_capacity_source_for_occupation(conn, command) != source:
            raise ValueError('current original Source after native waits required')
        owner.validate_original_target_judge_shared_risk_manifest(conn, scope, plan,
            release_policy=release_policy, artifact_bytes=artifact_bytes)
        now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        if (not source.valid_from <= now < source.valid_until
                or identity() != before or _consumption_packet(command) != packet):
            raise ValueError('same caller and command after original waits required')
        return result
    except Exception:
        raise ModelEvalOwnerRejected('CAPACITY_SHARED_PARENT_NATIVE_PLAN_REQUIRED') from None


def prepare_target_occupation(conn, scope, source_command, plan_id, intent_id, call_id):
    """Prepare on the original caller connection; never commit or dispatch."""
    from uuid import UUID
    from psycopg.pq import TransactionStatus
    from psycopg.types.json import Jsonb
    from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
    from aos_api.aip_physical_capacity_occupation_contracts import PhysicalOccupationPreparation

    try:
        if (type(conn) is not psycopg.Connection or conn.closed or conn.autocommit
                or conn.read_only or conn.info.transaction_status != TransactionStatus.INTRANS
                or not conn.pgconn.used_password
                or conn.info.get_parameters().get('require_auth') != 'scram-sha-256'
                or conn.row_factory is not dict_row
                or type(scope) is not TenantScope or scope.key != ('org-org', 'dev-project')
                or type(source_command) is not ProviderCapacityConsumptionCommand
                or any(type(value) is not UUID for value in (plan_id, intent_id, call_id))):
            raise ValueError('native same-caller occupation preparation required')
        command = ProviderCapacityConsumptionCommand.model_validate(source_command)

        def identity():
            return conn.execute("""SELECT session_user AS login,current_user AS role,
              current_setting('aos.org_id',true) AS org_id,
              current_setting('aos.project_id',true) AS project_id,
              current_setting('transaction_isolation') AS isolation,
              current_setting('transaction_read_only') AS readonly,
              current_setting('TimeZone') AS timezone,
              current_setting('session_replication_role') AS replication,
              pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid""").fetchone()

        before = identity()
        if (tuple(before[k] for k in ('login', 'role', 'org_id', 'project_id',
                                    'isolation', 'readonly', 'timezone', 'replication')) !=
                ('aos_provider_capacity_occupation', 'aos_runtime', *scope.key,
                 'serializable', 'off', 'UTC', 'origin')):
            raise ValueError('exact original occupation caller required')
        source = consume_capacity_source_for_occupation(conn, command)
        packet = _consumption_packet(command)
        row = conn.execute('''SELECT public.prepare_capacity_target_occupation(
          %s,%s::jsonb,%s::uuid,%s::uuid,%s::uuid) AS fact''',
          (packet, Jsonb(command.source_ref.model_dump(mode='json', by_alias=True)),
           plan_id, intent_id, call_id)).fetchone()
        if row is None:
            raise ValueError('original occupation preparation response required')
        result = PhysicalOccupationPreparation.model_validate(row['fact'])
        root = result.immutable
        if (identity() != before or _consumption_packet(command) != packet
                or (root.tenant.org_id, root.tenant.project_id) != scope.key
                or (root.caller_login, root.caller_xid, root.caller_pid) !=
                   (before['login'], before['xid'], before['pid'])
                or (root.plan_id, root.intent_id, result.call_id) !=
                   (str(plan_id), str(intent_id), str(call_id))
                or root.physical_account_id != source.physical_account_id):
            raise ValueError('exact same-caller occupation response required')
        return result
    except Exception:
        # Preserve caller-owned transaction handling; suppress credential inputs.
        raise ModelEvalOwnerRejected('CAPACITY_TYPED_OCCUPATION_PREPARATION_REQUIRED') from None


def prepare_shared_parent_risk_description(conn, scope, source_command, manifest, *,
                                          release_policy, artifact_bytes):
    """Persist whole v3 description against original risk; never authenticate calls."""
    from uuid import UUID
    from psycopg.types.json import Jsonb
    from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
    from aos_api.aip_model_eval_execution_contracts import ModelEvalTargetJudgeSharedRiskManifest
    from aos_api.aip_physical_capacity_occupation_contracts import SharedParentRiskDescriptionPreparation
    try:
        packet = _consumption_packet(source_command)
        risk = prepare_shared_parent_risk_plan(conn, scope, source_command, manifest,
            release_policy=release_policy, artifact_bytes=artifact_bytes)
        plan = ModelEvalTargetJudgeSharedRiskManifest.model_validate(manifest)
        body = plan.model_dump(mode='json', by_alias=True)
        result = conn.execute('''SELECT public.prepare_capacity_shared_risk_description(
          %s,%s::jsonb,%s::uuid,%s::jsonb,%s) AS fact''',
            (_consumption_packet(source_command),
             Jsonb(source_command.source_ref.model_dump(mode='json', by_alias=True)),
             UUID(plan.execution_id), Jsonb(body), canonical_hash(body))).fetchone()
        if result is None:
            raise ValueError('original persisted description required')
        parsed = SharedParentRiskDescriptionPreparation.model_validate(result['fact'])
        if (parsed.immutable.manifest != plan
                or parsed.immutable.original_risk_hash != risk['contentHash']
                or (parsed.immutable.caller_xid, parsed.immutable.caller_pid) != (
                    risk['immutable']['callerXid'], risk['immutable']['callerPid'])
):
            raise ValueError('same current original risk and full manifest required')
        source = consume_capacity_source_for_occupation(conn, source_command)
        ModelEvalExecutionOwner().validate_original_target_judge_shared_risk_manifest(
            conn, scope, plan, release_policy=release_policy, artifact_bytes=artifact_bytes)
        current = conn.execute("""SELECT clock_timestamp() AS now,pg_current_xact_id()::text AS xid,
          pg_backend_pid() AS pid,session_user AS login,current_user AS role,
          current_setting('aos.org_id',true) AS org,current_setting('aos.project_id',true) AS project,
          current_setting('transaction_isolation') AS isolation,current_setting('transaction_read_only') AS readonly,
          current_setting('TimeZone') AS timezone,current_setting('session_replication_role') AS replication""").fetchone()
        if (_consumption_packet(source_command) != packet
                or not source.valid_from <= current['now'] < source.valid_until
                or (current['xid'],current['pid'],current['login'],current['role'],current['org'],
                    current['project'],current['isolation'],current['readonly'],current['timezone'],current['replication']) !=
                   (parsed.immutable.caller_xid,parsed.immutable.caller_pid,
                    'aos_provider_capacity_occupation','aos_runtime',*scope.key,'serializable','off','UTC','origin')):
            raise ValueError('same current caller after all description waits required')
        return parsed
    except Exception:
        raise ModelEvalOwnerRejected('CAPACITY_SHARED_DESCRIPTION_REQUIRED') from None
