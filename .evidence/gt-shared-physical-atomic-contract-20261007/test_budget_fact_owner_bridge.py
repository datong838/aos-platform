"""Test-owned original-runtime fact bridge; not formal Source or execution."""
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
import json
import psycopg
import pytest
from psycopg.rows import dict_row
from aos_api.db import get_dsn
from aos_api.tenant_scope import TenantScope, apply_transaction_scope
from aos_api.aip_model_eval_budget_reservation import AipModelEvalBudgetReservationStore
from legal_eval_application_fixture_r4 import create_application
from tests.aip.test_budget_cost_consumer_pg import caller
from tests.aip.test_budget_cost_issuer_pg import issuer_factory

pytest_plugins = ('tests.conftest',)


def test_budget_fact_owner_bridge(caller, issuer_factory, https_signer,
                                 guard_issuer_factory, guard_consumer_factory, tmp_path):
    create_application(caller, issuer_factory, https_signer, guard_issuer_factory,
                       guard_consumer_factory, tmp_path)
    base = Path(__file__).parent
    application = json.loads((base / 'legal-eval-application-result-r4.json').read_text())
    scope = TenantScope('org-org', 'dev-project')
    suffix = uuid4().hex[:12]
    schema = 'gt_budget_fact_' + suffix
    owner = 'gt_ledger_probe_' + suffix
    signature = f'{schema}.verify_eval(uuid,text,text)'
    # All names below are generated lowercase ASCII identifiers, never user SQL.
    body = f"""CREATE FUNCTION {signature.split('(')[0]}(p_hold uuid,p_request text,p_hash text)
      RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE h public.aip_model_eval_budget_reservation%ROWTYPE; n bigint; exact_rows boolean;
    BEGIN
      IF current_user<>'aos_runtime' OR session_user<>'aos_app'
         OR current_setting('transaction_isolation')<>'serializable'
         OR current_setting('transaction_read_only')<>'off'
         OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
         OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project' THEN
        RAISE EXCEPTION 'TEST_BUDGET_FACT_SCOPE_IDENTITY' USING ERRCODE='42501';
      END IF;
      SELECT * INTO h FROM public.aip_model_eval_budget_reservation
        WHERE org_id='org-org' AND project_id='dev-project' AND reservation_id=p_hold
          AND request_id=p_request AND request_hash=p_hash AND state='held'
          AND xmin::text=pg_current_xact_id()::text;
      IF NOT FOUND THEN
        RAISE EXCEPTION 'TEST_BUDGET_FACT_EXACT_CURRENT_XID' USING ERRCODE='23514';
      END IF;
      SELECT count(*),bool_and(l.reserved_minor=h.upper_bound_minor
          AND b.held_minor>=l.reserved_minor AND l.xmin::text=pg_current_xact_id()::text
          AND b.xmin::text=pg_current_xact_id()::text) INTO n,exact_rows
        FROM public.aip_model_eval_budget_reservation_bucket l
        JOIN public.aip_budget_bucket b USING(org_id,project_id,bucket_kind,account_id,period_start,currency)
        WHERE l.org_id=h.org_id AND l.project_id=h.project_id AND l.reservation_id=h.reservation_id;
      IF n<>3 OR exact_rows IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'TEST_BUDGET_FACT_THREE_BUCKETS' USING ERRCODE='23514';
      END IF;
      RETURN jsonb_build_object('reservationId',h.reservation_id,'requestHash',h.request_hash,
        'contentHash',h.content_hash,'upperBoundMinor',h.upper_bound_minor,
        'xid',pg_current_xact_id()::text,'executionAllowed',false);
    END $$"""
    with psycopg.connect(get_dsn(), row_factory=dict_row) as admin:
        admin.execute(f'CREATE ROLE {owner} NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION')
        admin.execute(f'CREATE SCHEMA {schema}')
        admin.execute(f'GRANT USAGE,CREATE ON SCHEMA {schema} TO aos_runtime')
        admin.execute(body)
        admin.execute(f'ALTER FUNCTION {signature} OWNER TO aos_runtime')
        admin.execute(f'REVOKE ALL ON FUNCTION {signature} FROM PUBLIC')
        admin.execute(f'REVOKE CREATE ON SCHEMA {schema} FROM aos_runtime')
        admin.execute(f'GRANT USAGE ON SCHEMA {schema} TO {owner}')
        admin.execute(f'GRANT EXECUTE ON FUNCTION {signature} TO {owner}')
        admin.commit()
        approval = admin.execute('SELECT approval_event_id FROM aip_action_approval_event WHERE proposal_id=%s',
                                 (application['proposal_id'],)).fetchone()['approval_event_id']
    @contextmanager
    def transaction(tenant=scope):
        with psycopg.connect(get_dsn(), row_factory=dict_row) as conn:
            conn.execute('BEGIN ISOLATION LEVEL SERIALIZABLE READ WRITE')
            conn.execute('SET LOCAL ROLE aos_runtime')
            apply_transaction_scope(conn, tenant)
            try:
                yield conn
            finally:
                conn.rollback()
    result = {}
    try:
        with psycopg.connect(get_dsn(), row_factory=dict_row) as admin:
            flags = admin.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=%s', (owner,)).fetchone()
            assert all(value is False for value in flags.values())
            assert admin.execute('SELECT count(*) AS n FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole', (owner, owner)).fetchone()['n'] == 0
            assert admin.execute("SELECT has_table_privilege(%s,'public.aip_model_eval_budget_reservation','SELECT') AS allowed", (owner,)).fetchone()['allowed'] is False
            actual = admin.execute('SELECT pg_get_functiondef(%s::regprocedure) AS body', (signature,)).fetchone()['body']
        store = AipModelEvalBudgetReservationStore()
        with transaction() as conn:
            held = store.hold(conn, scope, application['request_id'], approval)
            native = conn.execute('SELECT txid_current()::text AS xid,pg_backend_pid() AS pid').fetchone()
            conn.execute(f'SET LOCAL ROLE {owner}')
            with conn.transaction():
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with conn.transaction():
                        conn.execute('SELECT request_hash FROM public.aip_model_eval_budget_reservation')
            proof = conn.execute(f'SELECT {schema}.verify_eval(%s,%s,%s) AS result',
                                 (held['reservation_id'], application['request_id'], application['request_hash'])).fetchone()['result']
            assert proof['xid'] == native['xid'] and proof['executionAllowed'] is False
            with pytest.raises(psycopg.errors.CheckViolation):
                with conn.transaction():
                    conn.execute(f'SELECT {schema}.verify_eval(%s,%s,%s)', (held['reservation_id'], application['request_id'], '0'*64))
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.transaction():
                    apply_transaction_scope(conn, TenantScope('dev-org', 'dev-project'))
                    conn.execute(f'SELECT {schema}.verify_eval(%s,%s,%s)', (held['reservation_id'], application['request_id'], application['request_hash']))
            # Known single commit: preserve the held obligation, never TTL-release.
            attempt = base / 'budget-fact-owner-bridge-commit.json'
            assert not attempt.exists()
            attempt.write_text(json.dumps({'status':'ATTEMPTED','database':application['database'],'reservation_id':str(held['reservation_id'])})+'\n')
            conn.commit()
            attempt.write_text(json.dumps({'status':'CONFIRMED','database':application['database'],'reservation_id':str(held['reservation_id']),'xid':native['xid']})+'\n')
        with transaction() as conn:
            conn.execute(f'SET LOCAL ROLE {owner}')
            with pytest.raises(psycopg.errors.CheckViolation):
                with conn.transaction():
                    conn.execute(f'SELECT {schema}.verify_eval(%s,%s,%s)', (held['reservation_id'], application['request_id'], application['request_hash']))
        result = {'status':'TEST_OWNED_ORIGINAL_RUNTIME_BUDGET_BRIDGE_VERIFIED','database':application['database'],
                  'owner':owner,'schema':schema,'actual_function_body':actual,'native_identity':native,'proof':proof,
                  'direct_table_read_denied':True,'hash_canary_old_xid_denied':True,
                  'limitations':['Owned admin SCRAM/session; not original occupation Source identity',
                                 'Eval-budget same-xid/ACL primitive only; no full joint/Intent/ordinary budget',
                                 'Formal bridge requires exact installer, original authority and complete hash/ref/deadline finalizer']}
    finally:
        with psycopg.connect(get_dsn(), row_factory=dict_row) as admin:
            admin.execute(f'DROP FUNCTION {signature}')
            admin.execute(f'REVOKE ALL ON SCHEMA {schema} FROM {owner},aos_runtime')
            admin.commit()
            assert admin.execute('SELECT to_regprocedure(%s) AS f', (signature,)).fetchone()['f'] is None
            assert admin.execute('SELECT count(*) AS n FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole', (owner,owner)).fetchone()['n'] == 0
            result['temporary_function_removed_and_role_inert'] = True
        (base/'budget-fact-owner-bridge-result.json').write_text(json.dumps(result,indent=2,default=str)+'\n')
