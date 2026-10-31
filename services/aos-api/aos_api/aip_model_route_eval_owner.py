"""Caller-retained governed Eval Source prefix, not an execution Owner grant.

The original authenticated native Source consumer remains the authority for
these reads. Output is a nonexecuting description, never a permission token.
Approval/budget, physical admission, dispatch and atomic report proof are not
implemented by this prefix. No credential or authentication packet is returned.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re

import psycopg
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from aos_api.aip_model_route_eval_manifest import (
    RouteEvalBudgetBinding,_alias_input,_aware,_canonical,
    route_eval_call_key,validate_route_eval_application,
)
from aos_api.aip_model_route_eval_signatures import (
    GovernedEvalIssuerInput,
    GovernedEvalSignedCase,
    GovernedEvalSignedCertificate,
    _manifest,
    validate_governed_case_signature,
)
from aos_api.aip_provider_capacity_occupation_source import (
    SESSION,consume_capacity_source_for_occupation,
)
from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityConsumptionCommand
from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySourceV2
from aos_api.asset_registry.canonical_json import canonical_json

SOURCE_PREFIX_DOMAIN=b'AOS-GOVERNED-EVAL-SOURCE-PREFIX-v1\n'
PREAPPROVAL_SOURCE_DOMAIN=b'AOS-ROUTE-EVAL-PREAPPROVAL-SOURCE-PREFIX-v1\n'
PRESENTED_CASE_BUNDLE_DOMAIN=b'AOS-ROUTE-EVAL-PRESENTED-CASE-BUNDLE-v1\n'
CURRENT_ADMISSION_BUNDLE_DOMAIN=b'AOS-ROUTE-EVAL-CURRENT-ADMISSION-BUNDLE-v1\n'


class GovernedEvalOwnerRejected(ValueError):
    """Safe category: never embeds Source commands, credentials or raw packets."""


@dataclass(frozen=True)
class PresentedRouteEvalCase:
    """One exact presented signed case; never native or durable authority."""

    envelope: GovernedEvalSignedCase
    certificate_envelope: GovernedEvalSignedCertificate
    issuer_input: GovernedEvalIssuerInput
    input_bytes: bytes
    output_bytes: bytes
    artifact_input_bytes: bytes
    expected_output: bytes | None = None


def _presented_hash(value) -> str:
    return hashlib.sha256(
        _canonical(value.model_dump(mode='json',by_alias=True))
    ).hexdigest()


def prepare_route_eval_presented_case_bundle(manifest_bytes: bytes, *,
        checked_at: datetime, revoked_identity_ids: frozenset[str],
        cases: tuple[PresentedRouteEvalCase,...]) -> bytes:
    """Verify complete presented Route Target/Judge bytes without granting execution.

    Native Source, approval, budget, dispatch, usage, cost, commit and durable
    proof remain separate Owner gates. Raw artifacts and signatures are not
    returned, so this prefix cannot become a transport or replay payload.
    """
    try:
        body=_manifest(manifest_bytes)
        if 'routeApplication' not in body or type(cases) is not tuple:
            raise ValueError('complete Route tuple required')
        expected=[(call['caseId'],call['purpose']) for call in body['routeApplication']['calls']]
        indexed={}
        for item in cases:
            if type(item) is not PresentedRouteEvalCase:
                raise ValueError('exact presented Route case required')
            claim=item.envelope.claim;key=(claim.case_id,claim.purpose)
            if key in indexed:
                raise ValueError('unique presented Route case required')
            indexed[key]=item
        if len(indexed)!=len(cases) or set(indexed)!=set(expected) or len(expected)!=len(set(expected)):
            raise ValueError('all and only Route manifest cases required')
        at=_aware(checked_at)
        if type(revoked_identity_ids) is not frozenset:
            raise ValueError('immutable revocation snapshot required')
        result=[];seen=set()
        for case_id,purpose in expected:
            if case_id in seen or purpose!='target':
                continue
            target=indexed[(case_id,'target')];judge=indexed[(case_id,'judge')]
            common=dict(checked_at=at,revoked_identity_ids=revoked_identity_ids,
                artifact_input_bytes=target.artifact_input_bytes,
                expected_output=target.expected_output)
            validate_governed_case_signature(manifest_bytes,target.envelope,
                certificate_envelope=target.certificate_envelope,
                issuer_input=target.issuer_input,input_bytes=target.input_bytes,
                output_bytes=target.output_bytes,**common)
            validate_governed_case_signature(manifest_bytes,judge.envelope,
                certificate_envelope=judge.certificate_envelope,
                issuer_input=judge.issuer_input,input_bytes=judge.input_bytes,
                output_bytes=judge.output_bytes,
                artifact_input_bytes=judge.artifact_input_bytes,
                expected_output=judge.expected_output,
                checked_at=at,revoked_identity_ids=revoked_identity_ids,
                target_envelope=target.envelope,
                target_certificate_envelope=target.certificate_envelope,
                target_issuer_input=target.issuer_input,
                target_input_bytes=target.input_bytes,
                target_output_bytes=target.output_bytes)
            result.append({'caseId':case_id,
                'targetEnvelopeHash':_presented_hash(target.envelope),
                'targetOutputHash':target.envelope.claim.output_hash,
                'judgeEnvelopeHash':_presented_hash(judge.envelope),
                'judgeOutputHash':judge.envelope.claim.output_hash,
                'passed':judge.envelope.claim.passed,
                'detailCode':judge.envelope.claim.detail_code})
            seen.add(case_id)
        if len(result)*2!=len(expected):
            raise ValueError('paired Target and Judge cases required')
        payload={'schemaVersion':'aos.route-eval-presented-case-bundle/v1',
            'manifestHash':hashlib.sha256(manifest_bytes).hexdigest(),
            'executionId':body['executionId'],
            'contextBindingHash':body['contextBindingHash'],
            'checkedAt':at.isoformat(),'cases':result,'executionAllowed':False}
        return PRESENTED_CASE_BUNDLE_DOMAIN+_canonical(payload)
    except (ValueError,TypeError,KeyError,AttributeError):
        raise GovernedEvalOwnerRejected(
            'ROUTE_EVAL_COMPLETE_PRESENTED_CASE_BUNDLE_REQUIRED'
        ) from None


def prepare_route_eval_current_admission_bundle(conn, *, expected_database: str,
        scope, manifest_bytes: bytes, guard,
        revoked_identity_ids: frozenset[str],
        cases: tuple[PresentedRouteEvalCase,...]) -> bytes:
    """Prove current approvals and existing HELD budget facts without writing.

    This deliberately cannot create a missing reservation. It only rechecks
    exact manifest requests against their original Action authority, locks and
    reads already-held Store facts, then revalidates the complete presented
    Target/Judge signatures at the final database clock.
    """
    try:
        from aos_api.aip_budget_reservation_contracts import BudgetReservationState
        from aos_api.aip_budget_reservation_store import AipBudgetReservationStore
        from aos_api.aip_model_route_eval_action import RouteEvalActionGuard
        from aos_api.tenant_scope import TenantScope
        if (type(scope) is not TenantScope or scope.key!=('org-org','dev-project')
            or type(guard) is not RouteEvalActionGuard
            or type(revoked_identity_ids) is not frozenset
            or type(cases) is not tuple):
            raise ValueError('exact current Route admission inputs required')
        start=_context(conn,expected_database)
        body=_manifest(manifest_bytes)
        if 'routeApplication' not in body or 'routeBudgetBindings' not in body:
            raise ValueError('Route manifest required')
        raw_bindings=body['routeBudgetBindings']
        if type(raw_bindings) is not list:
            raise ValueError('complete Route budget bindings required')
        bindings=[RouteEvalBudgetBinding.model_validate(_alias_input(value))
            for value in raw_bindings]
        calls=body['routeApplication']['calls']
        if len(bindings)!=len(calls):
            raise ValueError('all and only Route budget bindings required')
        indexed={item.call_key:item for item in bindings}
        if len(indexed)!=len(bindings):
            raise ValueError('unique Route budget bindings required')
        store=AipBudgetReservationStore();admissions=[]
        for call in calls:
            call_key=route_eval_call_key(body['executionId'],
                body['contextBindingHash'],call['caseId'],call['purpose'])
            binding=indexed.get(call_key)
            if binding is None:
                raise ValueError('manifest call budget binding required')
            request,unused_actor=guard._current_call_budget_request(
                conn,scope,binding.request.approval_ref.resource_id)
            if request!=binding.request:
                raise ValueError('current Route budget request drifted')
            store._lock_invocation(conn,scope,request.operation_id,
                request.invocation_key)
            row=store._reservation_by_key(conn,scope,request.operation_id,
                request.invocation_key,lock=True)
            if row is None:
                raise ValueError('existing HELD Route reservation required')
            current=store._view(conn,scope,row,replayed=False)
            manifest_reservation=binding.reservation
            exact_fields=('tenant','invocation_ref','reservation_ref','operation_id',
                'invocation_key','task_ref','policy_ref','pricing_ref','approval_ref',
                'state','currency','upper_bound_minor','actual_minor',
                'provider_request_receipt_ref','provider_receipt_ref',
                'usage_receipt_refs','reconciliation_evidence_ref','request_hash',
                'created_at')
            if (current.state is not BudgetReservationState.HELD
                or manifest_reservation.state is not BudgetReservationState.HELD
                or any(getattr(current,name)!=getattr(manifest_reservation,name)
                    for name in exact_fields)):
                raise ValueError('current HELD Route reservation drifted')
            checked=conn.execute('SELECT clock_timestamp() AS now').fetchone()
            checked_at=checked.get('now') if type(checked) is dict else None
            checked_at=_aware(checked_at)
            budget=store._budget_authority(conn,scope,request.policy_ref,checked_at)
            store._task_authority(conn,scope,request.task_ref,
                operation_id=request.operation_id)
            store._price_authority(conn,scope,request.pricing_ref,checked_at)
            store._approval_authority(conn,scope,request.approval_ref,checked_at,
                task_ref=request.task_ref,operation_id=request.operation_id,
                upper_bound_minor=request.upper_bound_minor,
                policy_ref=request.policy_ref,pricing_ref=request.pricing_ref,
                invocation_key=request.invocation_key)
            store._cost_risk_authority(conn,scope,request.policy_ref,
                request.pricing_ref,request.upper_bound_minor)
            links=conn.execute("""SELECT rb.bucket_kind,rb.account_id,
                rb.period_start,rb.currency,rb.reserved_minor,b.period_end,
                b.limit_minor,b.held_minor
                FROM public.aip_budget_reservation_bucket rb
                JOIN public.aip_budget_bucket b ON b.org_id=rb.org_id
                 AND b.project_id=rb.project_id AND b.bucket_kind=rb.bucket_kind
                 AND b.account_id=rb.account_id AND b.period_start=rb.period_start
                 AND b.currency=rb.currency
                WHERE rb.org_id=%s AND rb.project_id=%s AND rb.reservation_id=%s
                ORDER BY CASE rb.bucket_kind WHEN 'task' THEN 1 WHEN 'daily' THEN 2 ELSE 3 END
                FOR SHARE OF b""",(*scope.key,row['reservation_id'])).fetchall()
            if type(links) is not list or len(links)!=3:
                raise ValueError('three current Route bucket links required')
            expected_buckets={(item.kind,item.account_id,item.period_start,
                item.currency):item for item in manifest_reservation.buckets}
            current_buckets={(item.kind,item.account_id,item.period_start,
                item.currency):item for item in current.buckets}
            if (len(expected_buckets)!=3 or len(current_buckets)!=3
                or set(expected_buckets)!=set(current_buckets)):
                raise ValueError('current Route bucket identity drifted')
            seen=set()
            for link in links:
                key=(link['bucket_kind'],link['account_id'],link['period_start'],
                    link['currency'])
                expected=expected_buckets.get(key);now_bucket=current_buckets.get(key)
                if (key in seen or expected is None or now_bucket is None
                    or link['period_end']!=expected.period_end
                    or int(link['limit_minor'])!=expected.limit_minor
                    or now_bucket.period_end!=expected.period_end
                    or now_bucket.limit_minor!=expected.limit_minor
                    or int(link['reserved_minor'])!=request.upper_bound_minor
                    or int(link['held_minor'])<int(link['reserved_minor'])):
                    raise ValueError('current Route bucket backing drifted')
                seen.add(key)
            if set(seen)!=set(expected_buckets):
                raise ValueError('complete current Route bucket backing required')
            admissions.append({'callKey':call_key,
                'operationId':request.operation_id,
                'requestHash':request.request_hash(),
                'invocationRef':current.invocation_ref.model_dump(
                    mode='json',by_alias=True),
                'reservationRef':current.reservation_ref.model_dump(
                    mode='json',by_alias=True),
                'budgetRevision':int(budget['revision'])})
        if set(indexed)!={route_eval_call_key(body['executionId'],
                body['contextBindingHash'],call['caseId'],call['purpose'])
                for call in calls}:
            raise ValueError('all and only Route admission calls required')
        final=_context(conn,expected_database)
        stable=('database','database_oid','login','role','org_id','project_id',
            'isolation','readonly','xid','pid')
        if (any(final[name]!=start[name] for name in stable)
            or final['now']<start['now']):
            raise ValueError('current Route caller drifted')
        presented=prepare_route_eval_presented_case_bundle(manifest_bytes,
            checked_at=final['now'],revoked_identity_ids=revoked_identity_ids,
            cases=cases)
        payload={'schemaVersion':'aos.route-eval-current-admission-bundle/v1',
            'manifestHash':hashlib.sha256(manifest_bytes).hexdigest(),
            'executionId':body['executionId'],
            'contextBindingHash':body['contextBindingHash'],
            'callerXid':final['xid'],'callerPid':final['pid'],
            'checkedAt':final['now'].isoformat(),'calls':admissions,
            'presentedBundleHash':hashlib.sha256(presented).hexdigest(),
            'executionAllowed':False}
        return CURRENT_ADMISSION_BUNDLE_DOMAIN+_canonical(payload)
    except (ValueError,TypeError,KeyError,AttributeError,RuntimeError,psycopg.Error):
        raise GovernedEvalOwnerRejected(
            'ROUTE_EVAL_CURRENT_ADMISSION_REQUIRED'
        ) from None


def _require_native_connection(conn):
    if (type(conn) is not psycopg.Connection or conn.closed or conn.autocommit
        or conn.read_only is True or conn.row_factory is not dict_row
        or conn.info.transaction_status!=TransactionStatus.INTRANS
        or not conn.pgconn.used_password
        or conn.info.get_parameters().get('require_auth')!='scram-sha-256'):
        raise GovernedEvalOwnerRejected('GOVERNED_EVAL_NATIVE_SOURCE_CALLER_REQUIRED')


def _context(conn,expected_database):
    _require_native_connection(conn)
    row=conn.execute("""SELECT current_database() AS database,
        (SELECT oid FROM pg_catalog.pg_database WHERE datname=current_database()) AS database_oid,
        session_user AS login,current_user AS role,
        current_setting('aos.org_id',true) AS org_id,current_setting('aos.project_id',true) AS project_id,
        current_setting('transaction_isolation') AS isolation,
        current_setting('transaction_read_only') AS readonly,
        pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid,clock_timestamp() AS now""").fetchone()
    if (type(row) is not dict or row.get('database')!=expected_database
        or type(row.get('database_oid')) is not int or row['database_oid']<1
        or (row.get('login'),row.get('role'),row.get('org_id'),row.get('project_id'),row.get('isolation'),row.get('readonly'))
           !=(SESSION,'aos_runtime','org-org','dev-project','serializable','off')
        or type(row.get('xid')) is not str or re.fullmatch(r'[1-9][0-9]*',row['xid']) is None
        or type(row.get('pid')) is not int or row['pid']<1
        or type(row.get('now')) is not datetime or row['now'].utcoffset() is None):
        raise GovernedEvalOwnerRejected('GOVERNED_EVAL_SOURCE_CONTEXT_REQUIRED')
    return row


def _ref_key(ref):
    return tuple(ref[n] for n in ('assetType','assetId','revision','contentHash'))


def _required_sources(body):
    if 'modelPlan' in body:
        calls=[(c['caseId'],p,c[p]) for c in body['modelPlan']['cases'] for p in ('target','judge')]
    else:calls=[(c['caseId'],c['purpose'],c) for c in body['routeApplication']['calls']]
    sources={};identities={}
    for case,purpose,leg in calls:
        ref=leg['sourceRef'];key=_ref_key(ref);identity=key[:3]
        if identity in identities and identities[identity]!=key:
            raise ValueError('conflicting Source hash for same exact identity')
        identities[identity]=key
        sources.setdefault(key,[]).append((case,purpose,leg))
    return sources


def _commands(commands,required):
    if type(commands) is not tuple or len(commands)!=len(required):
        raise ValueError('complete immutable native Source command set required')
    indexed={}
    for value in commands:
        if type(value) is not ProviderCapacityConsumptionCommand:
            raise ValueError('original typed Source command required')
        # SecretStr remains an opaque object. Never dump commands as JSON or
        # include their validation exceptions in logs or returned errors.
        command=ProviderCapacityConsumptionCommand.model_validate(_alias_input(value)).model_copy(deep=True)
        ref=command.source_ref.model_dump(mode='json',by_alias=True);key=_ref_key(ref)
        if key not in required or key in indexed:raise ValueError('exact unique Source command required')
        indexed[key]=command
    if set(indexed)!=set(required):raise ValueError('all and only Manifest Source refs required')
    return indexed


def _source(value,ref,legs,context):
    if type(value) is not PublishedProviderCapacitySourceV2:
        raise ValueError('complete original published Source V2 required')
    source=PublishedProviderCapacitySourceV2.model_validate(_alias_input(value))
    raw=canonical_json(source.model_dump(mode='json',by_alias=True))
    if (hashlib.sha256(raw).hexdigest()!=ref.content_hash
        or (source.asset_id,source.revision)!=(ref.asset_id,ref.revision)
        or (source.tenant.org_id,source.tenant.project_id)!=('org-org','dev-project')
        or source.execution_allowed is not False
        or source.deployment_target.database!=context['database']
        or source.deployment_target.database_oid!=context['database_oid']):
        raise ValueError('complete current Source identity/hash/deployment required')
    providers=[item.model_dump(mode='json',by_alias=True) for item in source.provider_refs]
    account=source.account_candidate_ref.model_dump(mode='json',by_alias=True)
    if any(leg['providerRef'] not in providers or leg['physicalAccountRef']!=account for _,_,leg in legs):
        raise ValueError('Source must exactly cover every Provider and physical account')
    return source


def _authentication_deadline(command,*,actor_id=None):
    # Original OIDC/JWT verification is repeated after all Source lock waits.
    # The packet exists only within this function and is never returned/logged.
    try:
        raw=_consumption_packet(command)
    except Exception:
        # Original auth adapters can raise ApiError/RuntimeError containing
        # upstream details. Keep opaque authentication failures out of callers.
        raise GovernedEvalOwnerRejected('GOVERNED_EVAL_AUTH_RECHECK_REQUIRED') from None
    if type(raw) is not bytes:raise ValueError('original authentication packet required')
    packet=json.loads(raw)
    if (packet.get('protocol')!='aos-provider-capacity-source-consumption/v1'
        or packet.get('tenant')!={'orgId':'org-org','projectId':'dev-project'}
        or packet.get('sourceRef')!=command.source_ref.model_dump(mode='json',by_alias=True)):
        raise ValueError('same current authenticated consumption command required')
    if actor_id is not None and packet['authentication']['consumerSubject']!=actor_id:
        raise ValueError('verified current consumer must be the original actor')
    return _aware(packet['authentication']['authenticationExpiresAt'])


def _source_entries(required,indexed,observed):
    entries=[]
    for key in sorted(required):
        legs=required[key];source=observed[key]
        providers={_ref_key(leg['providerRef']):leg['providerRef'] for _,_,leg in legs}
        entries.append({'sourceRef':indexed[key].source_ref.model_dump(mode='json',by_alias=True),
            'providerRefs':[providers[k] for k in sorted(providers)],'physicalAccountRef':legs[0][2]['physicalAccountRef'],
            'calls':[{'caseId':case,'purpose':purpose} for case,purpose,_ in legs],
            'validUntil':source.valid_until.isoformat()})
    return entries


def prepare_governed_eval_sources(conn,*,expected_database: str,manifest_bytes: bytes,
                                  commands: tuple[ProviderCapacityConsumptionCommand,...]) -> bytes:
    """Read all original Sources on one native caller, without execution rights.

    Returned bytes are neither current after transaction end nor a substitute
    for the Source/approval/budget rechecks at actual joint admission. All roles,
    transactions, connections and effect decisions stay with the original caller.
    """
    return _prepare_governed_eval_sources(conn,expected_database=expected_database,
        manifest_bytes=manifest_bytes,commands=commands,native=False)


def prepare_governed_eval_native_sources(conn,*,expected_database: str,manifest_bytes: bytes,
        commands: tuple[ProviderCapacityConsumptionCommand,...]) -> bytes:
    """Both Model/Route Manifest Source facts on the new fixed native caller.

    This requires the same complete original Manifest and grants no execution
    or approval authority. The Route preapproval path has a separate entry.
    """
    return _prepare_governed_eval_sources(conn,expected_database=expected_database,
        manifest_bytes=manifest_bytes,commands=commands,native=True)


def _consume_eval_source(conn,command,native):
    if native:
        from aos_api.aip_model_route_eval_source_bridge import consume_route_eval_capacity_source
        return consume_route_eval_capacity_source(conn,command)
    return consume_capacity_source_for_occupation(conn,command)


def _prepare_governed_eval_sources(conn,*,expected_database,manifest_bytes,commands,native):
    try:
        if type(expected_database) is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,62}',expected_database) is None:
            raise ValueError('fixed exact database required')
        body=_manifest(manifest_bytes);required=_required_sources(body);indexed=_commands(commands,required)
        before=_route_source_context(conn,expected_database,native);observed={}
        for key in sorted(required):
            command=indexed[key]
            value=_consume_eval_source(conn,command,native)
            observed[key]=_source(value,command.source_ref,required[key],before)
        deadlines=[_authentication_deadline(indexed[key]) for key in sorted(indexed)]
        after=_route_source_context(conn,expected_database,native);at=after['now']
        if (any(after[k]!=v for k,v in before.items() if k!='now') or at<before['now']
            or _aware(body['compiledAt'])>at or any(deadline<=at for deadline in deadlines)):
            raise ValueError('same caller and current authentication after waits required')
        expiry=(body['modelPlan']['judgeRequest']['expiresAt'] if 'modelPlan' in body else body['routeApplication']['expiresAt'])
        if at>=_aware(expiry) or any(not s.valid_from<=at<s.valid_until or s.issued_at>at for s in observed.values()):
            raise ValueError('current Source and original application windows after waits required')
        result={'schemaVersion':'aos.governed-eval-source-prefix/v1','manifestHash':hashlib.sha256(manifest_bytes).hexdigest(),
            'database':after['database'],'databaseOid':after['database_oid'],'callerXid':after['xid'],'callerPid':after['pid'],
            'checkedAt':at.isoformat(),'sources':_source_entries(required,indexed,observed),'executionAllowed':False}
        domain=b'AOS-GOVERNED-EVAL-NATIVE-SOURCE-PREFIX-v1\n' if native else SOURCE_PREFIX_DOMAIN
        return domain+_canonical(result)
    except (ValueError,TypeError,KeyError,AttributeError,psycopg.Error):
        raise GovernedEvalOwnerRejected('GOVERNED_EVAL_CURRENT_SOURCE_PREFIX_REQUIRED') from None


def prepare_route_eval_preapproval_sources(conn,*,expected_database: str,context_bytes: bytes,
        application,actor_id: str,commands: tuple[ProviderCapacityConsumptionCommand,...]) -> bytes:
    """Necessary native Source/actor checks before approval, never permission.

    No approval or HELD budget is an input. Full locked Run/Rule/current context
    and original human Action authority remain necessary before any decision.
    The caller retains every Source/membership lock and its transaction.
    """
    return _prepare_route_eval_sources(conn,expected_database=expected_database,
        context_bytes=context_bytes,application=application,actor_id=actor_id,commands=commands,native=False)


def prepare_route_eval_native_sources(conn,*,expected_database: str,context_bytes: bytes,
        application,actor_id: str,commands: tuple[ProviderCapacityConsumptionCommand,...]) -> bytes:
    """Necessary original Source facts using the NEW fixed Model/Route caller.

    The dedicated bridge must be independently installed and qualified first.
    This is not the full Rule/material/approval/budget/dispatch Guard. It cannot
    approve, create an execution grant or survive the caller transaction as proof.
    """
    return _prepare_route_eval_sources(conn,expected_database=expected_database,
        context_bytes=context_bytes,application=application,actor_id=actor_id,commands=commands,native=True)


def _route_source_context(conn,expected_database,native):
    if not native:
        return _context(conn,expected_database)
    from aos_api.aip_model_route_eval_source_bridge import _context as native_context
    row=native_context(conn)
    if row['database']!=expected_database:
        raise ValueError('same expected native Source database required')
    return row


def _prepare_route_eval_sources(conn,*,expected_database,context_bytes,application,actor_id,commands,native):
    from aos_api.aip_model_eval_action import ModelEvalActionGuard
    from aos_api.tenant_scope import TenantScope
    try:
        if (type(expected_database) is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,62}',expected_database) is None
            or type(actor_id) is not str or not 1<=len(actor_id)<=200
            or actor_id!=actor_id.strip() or actor_id=='unknown'):
            raise ValueError('exact database and current actor required')
        before=_route_source_context(conn,expected_database,native)
        app=validate_route_eval_application(context_bytes,application=application,checked_at=before['now'])
        body={'routeApplication':app.model_dump(mode='json',by_alias=True)}
        required=_required_sources(body);indexed=_commands(commands,required);observed={}
        for key in sorted(required):
            command=indexed[key]
            if _authentication_deadline(command,actor_id=actor_id)<=before['now']:
                raise ValueError('current actor authentication required')
            value=_consume_eval_source(conn,command,native)
            observed[key]=_source(value,command.source_ref,required[key],before)
        ModelEvalActionGuard._role(conn,TenantScope('org-org','dev-project'),actor_id)
        deadlines=[_authentication_deadline(indexed[key],actor_id=actor_id) for key in sorted(indexed)]
        after=_route_source_context(conn,expected_database,native);at=after['now']
        if (any(after[k]!=v for k,v in before.items() if k!='now') or at<before['now']
            or at>=app.expires_at or any(deadline<=at for deadline in deadlines)
            or any(not s.valid_from<=at<s.valid_until or s.issued_at>at for s in observed.values())):
            raise ValueError('same caller and current Source, actor and application after waits required')
        result={'schemaVersion':'aos.route-eval-preapproval-source-prefix/v1',
            'applicationHash':hashlib.sha256(_canonical(body['routeApplication'])).hexdigest(),
            'contextBindingHash':app.context_binding_hash,'database':after['database'],'databaseOid':after['database_oid'],
            'callerXid':after['xid'],'callerPid':after['pid'],'checkedAt':at.isoformat(),
            'sources':_source_entries(required,indexed,observed),'executionAllowed':False}
        domain=b'AOS-ROUTE-EVAL-NATIVE-SOURCE-PREFIX-v1\n' if native else PREAPPROVAL_SOURCE_DOMAIN
        return domain+_canonical(result)
    except (ValueError,TypeError,KeyError,AttributeError,RuntimeError,psycopg.Error):
        raise GovernedEvalOwnerRejected('ROUTE_EVAL_PREAPPROVAL_SOURCE_REQUIRED') from None
