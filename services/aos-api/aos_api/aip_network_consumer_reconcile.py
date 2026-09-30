"""Exact read-only observations; absence never authorizes consumption resend."""
from aos_api.aip_network_consumer_connection import require_consumer_identity, CALLER, OWNER
from aos_api.tenant_scope import TenantScope

FUNCTION = 'public.aip_reconcile_network_receipt_a0v_121(text,text,text,text)'


class ConsumerReconcileBlocked(RuntimeError):
    pass


def reconcile_network_receipt(conn, scope: TenantScope, proposal: str, event: str,
                              expected_database: str) -> dict:
    if conn.read_only is not True:
        raise ConsumerReconcileBlocked('CONSUMER_RECONCILE_READ_ONLY_REQUIRED')
    if any(type(value) is not str or not value or value != value.strip() or len(value) > 200
           for value in (proposal, event)):
        raise ConsumerReconcileBlocked('CONSUMER_RECONCILE_EXACT_INQUIRY_REQUIRED')
    require_consumer_identity(conn, scope, expected_database)
    try:
        row = conn.execute("""SELECT p.prosecdef,p.provolatile,p.proconfig,p.proowner::regrole::text AS owner,
            has_function_privilege(session_user,p.oid,'EXECUTE') AS executable,
            EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
                WHERE a.privilege_type='EXECUTE' AND a.grantee NOT IN (%s::regrole,%s::regrole)) AS extra
            FROM pg_catalog.pg_proc p WHERE p.oid=to_regprocedure(%s)""", (CALLER, OWNER, FUNCTION)).fetchone()
        if (row is None or row['prosecdef'] is not True or row['provolatile'] != 's'
                or row['proconfig'] != ['search_path=pg_catalog'] or row['owner'] != OWNER
                or row['executable'] is not True or row['extra'] is not False):
            raise ConsumerReconcileBlocked('CONSUMER_RECONCILE_FUNCTION_DRIFT')
        result = conn.execute('SELECT public.aip_reconcile_network_receipt_a0v_121(%s,%s,%s,%s) AS result',
                              (*scope.key, proposal, event)).fetchone()['result']
        if type(result) is not dict or result.get('status') not in {'unresolved', 'observed', 'conflict'}:
            raise ConsumerReconcileBlocked('CONSUMER_RECONCILE_INVALID_RESULT')
        if result['status'] == 'observed':
            if (set(result) != {'status', 'receipt'} or type(result['receipt']) is not dict
                    or result['receipt'].get('proposalId') != proposal
                    or result['receipt'].get('approvalEventId') != event):
                raise ConsumerReconcileBlocked('CONSUMER_RECONCILE_INVALID_RESULT')
        elif set(result) != {'status'}:
            raise ConsumerReconcileBlocked('CONSUMER_RECONCILE_INVALID_RESULT')
        return result
    except ConsumerReconcileBlocked:
        raise
    except Exception:
        raise ConsumerReconcileBlocked('CONSUMER_RECONCILE_QUERY_FAILED') from None
