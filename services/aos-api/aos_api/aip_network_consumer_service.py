"""Private consumer composition; no HTTP entrypoint or credential fallback."""
from pathlib import Path
from aos_api.tenant_scope import TenantScope
from aos_api.aip_network_consumer_auth import authenticate_consumer_request
from aos_api.aip_network_consumer_attempt import reserve_consumer_attempt
from aos_api.aip_network_consumer_contracts import NetworkConsumerCommand, NetworkConsumerInquiry
from aos_api.aip_network_consumer_connection import (
    ConsumerDatabaseConfig, connect_consumer, CALLER, OWNER,
)
from aos_api.aip_network_issuer_attempt import AttemptAlreadyRecorded, AttemptUnknown


class ConsumerServiceBlocked(RuntimeError):
    pass


def _function_gate(conn, signature, volatility):
    row = conn.execute("""SELECT p.prosecdef,p.provolatile,p.proconfig,
        p.proowner::regrole::text AS owner,
        has_function_privilege(session_user,p.oid,'EXECUTE') AS executable,
        EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
          WHERE a.privilege_type='EXECUTE' AND a.grantee NOT IN (%s::regrole,%s::regrole)) AS extra
        FROM pg_catalog.pg_proc p WHERE p.oid=to_regprocedure(%s)""",
        (CALLER, OWNER, signature)).fetchone()
    if (row is None or row['prosecdef'] is not True or row['provolatile'] != volatility
            or row['proconfig'] != ['search_path=pg_catalog'] or row['owner'] != OWNER
            or row['executable'] is not True or row['extra'] is not False):
        raise ConsumerServiceBlocked('CONSUMER_SERVICE_FUNCTION_DRIFT')


def _actor_call(conn, request, subject, *, read_only):
    name = 'reconcile' if read_only else 'consume'
    function = f'public.aip_{name}_network_as_actor_a0v_122'
    _function_gate(conn, function + '(text,text,text,text,text,text,text,text)', 's' if read_only else 'v')
    if read_only:
        _function_gate(conn, 'public.aip_reconcile_network_receipt_a0v_121(text,text,text,text)', 's')
    return conn.execute(f'SELECT {function}(%s,%s,%s,%s,%s,%s,%s,%s) AS result', (
        request.org_id, request.project_id, request.proposal_id, request.approval_event_id,
        subject, request.proposal_hash, request.target_content_hash, request.binding_hash,
    )).fetchone()['result']


def _observe(request, config, subject):
    scope = TenantScope(request.org_id, request.project_id)
    with connect_consumer(config, scope, read_only=True) as conn:
        result = _actor_call(conn, request, subject, read_only=True)
        if type(result) is not dict or result.get('status') not in {'unresolved', 'observed', 'conflict'}:
            raise ConsumerServiceBlocked('CONSUMER_SERVICE_INVALID_OBSERVATION')
        if result['status'] == 'observed':
            receipt = result.get('receipt')
            if (set(result) != {'status', 'receipt'} or type(receipt) is not dict
                    or receipt.get('proposalId') != request.proposal_id
                    or receipt.get('approvalEventId') != request.approval_event_id
                    or receipt.get('contentHash') != request.target_content_hash
                    or receipt.get('resourceType') != 'NetworkPolicyRevision'):
                raise ConsumerServiceBlocked('CONSUMER_SERVICE_INVALID_OBSERVATION')
        elif set(result) != {'status'}:
            raise ConsumerServiceBlocked('CONSUMER_SERVICE_INVALID_OBSERVATION')
        return result


def inquire_network(request: NetworkConsumerInquiry, config: ConsumerDatabaseConfig) -> dict:
    if type(request) is not NetworkConsumerInquiry or type(config) is not ConsumerDatabaseConfig:
        raise ConsumerServiceBlocked('CONSUMER_SERVICE_EXACT_INPUT_REQUIRED')
    principal = authenticate_consumer_request(request)
    return _observe(request, config, principal.subject)


def consume_network_once(command: NetworkConsumerCommand, config: ConsumerDatabaseConfig,
                         attempt_directory: str | Path) -> dict:
    if type(command) is not NetworkConsumerCommand or type(config) is not ConsumerDatabaseConfig:
        raise ConsumerServiceBlocked('CONSUMER_SERVICE_EXACT_INPUT_REQUIRED')
    principal = authenticate_consumer_request(command)
    prior = _observe(command.inquiry(), config, principal.subject)
    if prior['status'] != 'unresolved':
        return prior
    try:
        reserve_consumer_attempt(attempt_directory, command, principal)
    except (AttemptAlreadyRecorded, AttemptUnknown):
        # Unknown or previously reserved attempts never authorize another write.
        pass
    else:
        try:
            with connect_consumer(config, TenantScope(command.org_id, command.project_id)) as conn:
                _actor_call(conn, command, principal.subject, read_only=False)
        except Exception:
            # Includes commit-response loss. Observe independently; never resend.
            pass
    try:
        return _observe(command.inquiry(), config, principal.subject)
    except Exception:
        return {'status': 'unresolved'}
