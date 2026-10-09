"""Actual signed Source and original Model application on one native caller.

No physical allocation, execution Intent, dispatch or formal authorization.
"""
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sys
from uuid import uuid4
import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityConsumptionCommand
from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySourceV2,parse_signed_capacity_body
from aos_api.db import get_dsn
from aos_api.tenant_scope import TenantScope,apply_transaction_scope
from tests.aip._runtime_guard_history_fixture import isolated_owner,https_signer,guard_issuer_factory,guard_consumer_factory
from tests.aip.test_budget_cost_consumer_pg import caller
from tests.aip.test_budget_cost_issuer_pg import issuer_factory
pytest_plugins=('tests.aip.test_capacity_source_publication_transaction_pg',)
SCOPE=TenantScope('org-org','dev-project')
ROLE='aos_provider_capacity_occupation'


def test_original_dual_parent_lifecycle_is_not_ordinary_settlement(
        caller, issuer_factory, https_signer, guard_issuer_factory,
        guard_consumer_factory, tmp_path):
    """A complete approved suite keeps both unknown-cost parent liabilities.

    Ordinary invocation receipts must never identify Eval/Judge parents. This
    is an original native isolation gate, not a new settlement authorization.
    """
    from aos_api.aip_budget_reservation_store import (
        AipBudgetReservationStore, BudgetReservationNotFound,
    )
    from tests.aip.test_model_eval_judge_authority_pg import test_exact_signed_rule_new_original_suite
    proofs = []

    def probe(conn, body, target, judge):
        assert len(body['cases']) == 2
        xid = conn.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
        parents = []
        ordinary = AipBudgetReservationStore()
        for purpose, table, parent in (
                ('target', 'aip_model_eval_budget_reservation', target.parent_limit),
                ('judge', 'aip_model_judge_budget_reservation', judge.parent_limit)):
            reservation = parent.parent_hold_ref.resource_id
            query = ('SELECT *,xmin::text AS origin_xid FROM ' + table +
                     ' WHERE org_id=%s AND project_id=%s AND reservation_id=%s')
            args = (*SCOPE.key, reservation)
            before = conn.execute(query, args).fetchone()
            assert before['state'] == 'held' and before['upper_bound_minor'] == 10
            assert before['origin_xid'] == xid
            assert before['content_hash'] == parent.parent_hold_ref.content_hash
            buckets = conn.execute('SELECT * FROM ' + table + '_bucket'
                ' WHERE org_id=%s AND project_id=%s AND reservation_id=%s', args).fetchall()
            assert len(buckets) == 3 and all(b['reserved_minor'] == 10 for b in buckets)
            # The original private reader must resolve its own invocation row,
            # never a same-tenant foreign-purpose parent UUID.
            with conn.transaction(force_rollback=True):
                with pytest.raises(BudgetReservationNotFound):
                    ordinary._reservation_by_id(conn, SCOPE, reservation, lock=True)
            with conn.transaction(force_rollback=True):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute('UPDATE ' + table + " SET state='cost_pending'"
                        ' WHERE org_id=%s AND project_id=%s AND reservation_id=%s', args)
            assert conn.execute(query, args).fetchone() == before
            assert conn.execute('SELECT * FROM ' + table + '_bucket'
                ' WHERE org_id=%s AND project_id=%s AND reservation_id=%s', args).fetchall() == buckets
            price = before['price_ref']
            payload = conn.execute('SELECT payload FROM aip_model_price_snapshot_revision'
                ' WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s AND revision=%s',
                (*SCOPE.key, price['resourceId'], price['revision'])).fetchone()['payload']
            assert all(payload.get(k) is None for k in
                       ('inputTokenPrice', 'outputTokenPrice', 'cachedTokenPrice'))
            parents.append({'purpose': purpose, 'reservation': reservation,
                'content_hash': before['content_hash'], 'upper_bound_minor': 10,
                'origin_xid': xid, 'bucket_count': 3, 'numeric_prices': False,
                'ordinary_reader_rejected': True, 'runtime_transition_rejected': True})
        proofs.append({'xid': xid, 'parents': parents,
            'complete_legs': [(c['caseId'], p) for c in body['cases'] for p in ('target', 'judge')],
            'execution_allowed': False})
        return proofs[-1]

    test_exact_signed_rule_new_original_suite(caller, issuer_factory, https_signer,
        guard_issuer_factory, guard_consumer_factory, tmp_path, source_probe=probe)
    assert len(proofs) == 1
    from aos_api.db import connect
    with connect(SCOPE) as independent:
        assert independent.execute('SELECT pg_xact_status(%s::xid8) AS status',
            (proofs[0]['xid'],)).fetchone()['status'] == 'aborted'
        for p in proofs[0]['parents']:
            table = 'aip_model_eval_budget_reservation' if p['purpose'] == 'target' else 'aip_model_judge_budget_reservation'
            assert independent.execute('SELECT count(*) AS n FROM ' + table +
                ' WHERE org_id=%s AND project_id=%s AND reservation_id=%s',
                (*SCOPE.key, p['reservation'])).fetchone()['n'] == 0
    root = os.environ.get('AOS_PARENT_LIFECYCLE_EVIDENCE')
    if root:
        with (Path(root) / 'native-proof.json').open('x') as stream:
            json.dump({'proof': proofs[0], 'independent_xact_status': 'aborted',
                'original_parent_rows_after_rollback': 0, 'provider_calls': 0}, stream, indent=2)

@pytest.mark.parametrize('native_original_fact_reader',['shared'],indirect=True)
def test_source_model_preparation_original_native_caller(exact_public_source_caller,https_signer,caller,issuer_factory,guard_issuer_factory,guard_consumer_factory,tmp_path):
    business_fixture_caller = caller
    sign, _ = https_signer
    issuer, packet, material, original = exact_public_source_caller
    issuance, _, _ = material['actual_command']()
    asset = 'occupation-source-' + uuid4().hex
    pending = issuer.execute('SELECT * FROM public.prepare_capacity_source(%s,%s,%s,%s::jsonb)',
        (packet, issuance.idempotency_key, asset, Jsonb(material['refs'][-1]))).fetchone()
    raw = bytes(pending['source_raw'])
    finalized = issuer.execute('SELECT * FROM public.commit_capacity_source(%s,%s,%s)',
        (issuance.idempotency_key, raw, material['source_key'].sign(raw))).fetchone()
    issuer.commit()
    source = parse_signed_capacity_body(raw, PublishedProviderCapacitySourceV2)
    exact = FormalExactRef(asset_type='ProviderCapacitySourceRevision', asset_id=asset,
        revision=1, content_hash=finalized['content_hash'])
    command = ProviderCapacityConsumptionCommand(schema_version=1, tenant=source.tenant, source_ref=exact,
        bearer_token=sign(original[0]['maker']))
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore
    ref=source.provider_refs[0]
    provider=AipModelRuntimeStore().get_provider(SCOPE,ref.asset_id,ref.revision)
    assert provider.content_hash==ref.content_hash
    base=Path(__file__).resolve().parents[4]/'.evidence/gt-atomic-model-admission-20261008'
    for name in ('legal_model_prefix_for_application_r4','legal_eval_application_fixture_r4'):
        spec=importlib.util.spec_from_file_location(name,base/(name+'.py'))
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    from aos_api.db import connect
    judge_path=tmp_path/'source-judge';judge_path.mkdir()
    sys.modules['legal_eval_application_fixture_r4'].create_application(
        caller,issuer_factory,https_signer,guard_issuer_factory,guard_consumer_factory,judge_path,source_provider=provider)
    judge_app=json.loads((base/'legal-eval-application-result-r4.json').read_text())
    with connect(SCOPE) as c:
        judge_approval=c.execute("SELECT approval_event_id FROM aip_action_approval_event WHERE proposal_id=%s AND decision='approved'",(judge_app['proposal_id'],)).fetchone()['approval_event_id']
    with connect(SCOPE) as c:
        judge_model_ref=c.execute('SELECT request_json FROM aip_model_eval_request WHERE request_id=%s',(judge_app['request_id'],)).fetchone()['request_json']['sourceRef']
    sys.modules['legal_eval_application_fixture_r4'].create_application(
        caller,issuer_factory,https_signer,guard_issuer_factory,guard_consumer_factory,tmp_path,source_provider=provider,suite_case_copies=2,judge_model_ref=judge_model_ref)
    app=json.loads((base/'legal-eval-application-result-r4.json').read_text())
    from aos_api.db import connect
    with connect(SCOPE) as c:
        approval=c.execute("SELECT approval_event_id FROM aip_action_approval_event WHERE proposal_id=%s AND decision='approved'",(app['proposal_id'],)).fetchone()['approval_event_id']
    # A second genuinely published, independently approved application uses a
    # different Provider. It must be rejected before creating a parent hold.
    other_path=tmp_path/'other-model';other_path.mkdir()
    sys.modules['legal_eval_application_fixture_r4'].create_application(
        caller,issuer_factory,https_signer,guard_issuer_factory,guard_consumer_factory,other_path)
    other=json.loads((base/'legal-eval-application-result-r4.json').read_text())
    with connect(SCOPE) as c:
        other_approval=c.execute("SELECT approval_event_id FROM aip_action_approval_event WHERE proposal_id=%s AND decision='approved'",(other['proposal_id'],)).fetchone()['approval_event_id']
    password = secrets.token_urlsafe(32)
    with isolated_owner() as admin:
        prior = admin.execute("""SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,
            rolreplication,rolbypassrls,shobj_description(oid,'pg_authid') AS description
            FROM pg_roles WHERE rolname=%s""", (ROLE,)).fetchone()
        label = 'Owned isolated GT capacity occupation Source fixture; never formal identity'
        if prior is None:
            admin.execute("CREATE ROLE aos_provider_capacity_occupation NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS")
            admin.execute(psycopg.sql.SQL('COMMENT ON ROLE aos_provider_capacity_occupation IS {}').format(psycopg.sql.Literal(label)))
        else:
            assert prior['description'] == label
            assert all(prior[k] is False for k in prior.keys() - {'description'})
            assert admin.execute("SELECT 1 FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole", (ROLE,ROLE)).fetchone() is None
        admin.execute("SET LOCAL password_encryption='scram-sha-256'")
        admin.execute(psycopg.sql.SQL('ALTER ROLE aos_provider_capacity_occupation LOGIN PASSWORD {}').format(psycopg.sql.Literal(password)))
        admin.execute('GRANT aos_runtime TO aos_provider_capacity_occupation')
        runtime = admin.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='aos_runtime'").fetchone()
        assert runtime and not any(runtime.values())
    try:
        from aos_api.aip_provider_capacity_occupation_source import occupation_source_statements
        from aos_api.aip_provider_capacity_occupation_epoch_profile import occupation_epoch_profile_statements
        with isolated_owner() as admin:
            from aos_api.aip_provider_capacity_publication_transaction import source_public_entry_statements
            admin.execute('DROP FUNCTION public.prepare_capacity_source(bytea,text,text,jsonb)')
            admin.execute('DROP FUNCTION public.commit_capacity_source(text,bytea,bytea)')
            admin.execute('DROP FUNCTION aos_capacity_publication_private.require_current_source_installation()')
            for statement in source_public_entry_statements(include_consumer=True):
                admin.execute(statement)
            for statement in occupation_epoch_profile_statements():
                admin.execute(statement)
            for statement in occupation_source_statements():
                admin.execute(statement)
            from aos_api.aip_physical_capacity_occupation_authority import OWNER,FACT,ENTRY,occupation_eval_fact_statements
            flags=admin.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,shobj_description(oid,'pg_authid') AS description FROM pg_roles WHERE rolname=%s",(OWNER,)).fetchone()
            label='Owned isolated joint fact bridge; no formal authority'
            if flags is None:
                admin.execute('CREATE ROLE '+OWNER+' NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS')
                admin.execute(psycopg.sql.SQL('COMMENT ON ROLE {} IS {}').format(psycopg.sql.Identifier(OWNER),psycopg.sql.Literal(label)))
            else:
                assert flags['description']==label and not any(v for k,v in flags.items() if k!='description')
            assert admin.execute('SELECT count(*) AS n FROM pg_auth_members WHERE member=%s::regrole OR roleid=%s::regrole',(OWNER,OWNER)).fetchone()['n']==0
            before=admin.execute("SELECT oid,prosrc,proacl::text FROM pg_proc WHERE oid='public.read_capacity_source_for_occupation(bytea,jsonb)'::regprocedure").fetchone()
            admin.execute('GRANT USAGE ON SCHEMA public TO '+OWNER)
            for statement in occupation_eval_fact_statements():admin.execute(statement)
            from aos_api.aip_physical_capacity_occupation_authority import occupation_account_guard_statements,SCHEMA,SOURCE_FACT,GUARD
            for statement in occupation_account_guard_statements():admin.execute(statement)
            from aos_api.aip_physical_capacity_occupation_authority import occupation_parent_debit_statements,DEBIT
            debit_statements=occupation_parent_debit_statements()
            for statement in debit_statements:admin.execute(statement)
            from aos_api.aip_physical_capacity_occupation_authority import occupation_case_binding_statements,CASE_FACT,CASE_DEBIT
            case_statements=occupation_case_binding_statements()
            for statement in case_statements:admin.execute(statement)
            from aos_api.aip_physical_capacity_occupation_authority import occupation_intent_statements,INTENT
            intent_statements=occupation_intent_statements()
            for statement in intent_statements:admin.execute(statement)
            # Test-only Owner probes reach the real caller's existing row.
            # They are never an installed product entry or execution authority.
            for operation in ('update','delete'):
                action=("UPDATE "+SCHEMA+".prepared_execution_intent SET state='prepared' WHERE intent_id=p_id"
                        if operation=='update' else "DELETE FROM "+SCHEMA+".prepared_execution_intent WHERE intent_id=p_id")
                admin.execute(f"""CREATE FUNCTION public.test_capacity_intent_{operation}_probe(p_id uuid)
                  RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $probe$
                  DECLARE old_hash text;
                  BEGIN
                    SELECT content_hash INTO STRICT old_hash FROM {SCHEMA}.prepared_execution_intent
                      WHERE intent_id=p_id AND org_id='org-org' AND project_id='dev-project';
                    {action};
                    RETURN old_hash;
                  END $probe$""")
                admin.execute(f'ALTER FUNCTION public.test_capacity_intent_{operation}_probe(uuid) OWNER TO '+OWNER)
                admin.execute(f'REVOKE ALL ON FUNCTION public.test_capacity_intent_{operation}_probe(uuid) FROM PUBLIC')
                admin.execute(f'GRANT EXECUTE ON FUNCTION public.test_capacity_intent_{operation}_probe(uuid) TO aos_runtime')
            import hashlib,re
            from aos_api.aip_physical_capacity_occupation_authority import occupation_input_binding_statements,INPUT_DEBIT
            input_statements=occupation_input_binding_statements()
            for statement in input_statements:admin.execute(statement)
            intent_install=admin.execute("SELECT prosrc,prosecdef,proconfig,pg_get_userbyid(proowner) AS owner FROM pg_proc WHERE oid=%s::regprocedure",(INTENT,)).fetchone()
            intent_body=intent_statements[11].split('$intent$')[1]
            assert intent_install['prosrc']==intent_body and intent_install['prosecdef'] and intent_install['owner']==OWNER and intent_install['proconfig']==['search_path=pg_catalog']
            assert admin.execute("SELECT has_table_privilege('aos_runtime',%s,'SELECT,INSERT,UPDATE,DELETE') AS allowed",(SCHEMA+'.prepared_execution_intent',)).fetchone()['allowed'] is False
            acl=admin.execute("SELECT a.grantee::regrole::text AS grantee,a.privilege_type,a.is_grantable FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE p.oid=%s::regprocedure",(INTENT,)).fetchall()
            assert {v['grantee'] for v in acl}=={OWNER,'aos_runtime'} and len(acl)==2 and all(v['privilege_type']=='EXECUTE' and not v['is_grantable'] for v in acl)
            (base/(os.environ.get('AOS_SOURCE_MODEL_EVIDENCE_LABEL','source-model-current')+'-intent-installation.json')).write_text(json.dumps(dict(body_hash=hashlib.sha256(intent_body.encode()).hexdigest(),owner=OWNER,acl=acl),indent=2)+'\n')
            installed=admin.execute("SELECT prosrc,prosecdef,proconfig,pg_get_userbyid(proowner) AS owner FROM pg_proc WHERE oid=%s::regprocedure",(INPUT_DEBIT,)).fetchone()
            expected=input_statements[0].split('$inputbind$')[1]
            assert installed['prosrc']==expected and installed['prosecdef'] is True and installed['owner']==OWNER
            assert installed['proconfig']==['search_path=pg_catalog']
            (base/(os.environ.get('AOS_SOURCE_MODEL_EVIDENCE_LABEL','source-model-current')+'-input-installation.json')).write_text(json.dumps(dict(body_hash=hashlib.sha256(expected.encode()).hexdigest(),owner=installed['owner'],fixed_path=True),indent=2)+'\n')
            assert admin.execute('SELECT has_table_privilege(%s,%s,\'SELECT,INSERT,UPDATE,DELETE\') AS allowed',
                ('aos_runtime',SCHEMA+'.prepared_parent_debit')).fetchone()['allowed'] is False
            assert admin.execute('SELECT has_table_privilege(%s,%s,\'SELECT,INSERT,UPDATE,DELETE\') AS allowed',('aos_runtime',SCHEMA+'.account_guard')).fetchone()['allowed'] is False
            assert admin.execute("SELECT has_table_privilege(%s,'public.aip_model_eval_budget_reservation','SELECT') AS allowed",(OWNER,)).fetchone()['allowed'] is False
            assert admin.execute("SELECT has_function_privilege(%s,'public.read_capacity_source_for_occupation(bytea,jsonb)','EXECUTE') AS allowed",(OWNER,)).fetchone()['allowed'] is False
            assert admin.execute("SELECT oid,prosrc,proacl::text FROM pg_proc WHERE oid='public.read_capacity_source_for_occupation(bytea,jsonb)'::regprocedure").fetchone()==before
            statements=occupation_eval_fact_statements()
            installed=[]
            guard_statements=occupation_account_guard_statements()
            for signature,statement,tag in [(FACT,statements[0],'fact'),(ENTRY,statements[4],'entry'),(SOURCE_FACT,guard_statements[7],'source'),(GUARD,guard_statements[11],'guard')]:
                row=admin.execute("SELECT prosrc,r.rolname AS owner,prosecdef,proconfig FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner WHERE p.oid=%s::regprocedure",(signature,)).fetchone()
                trusted=re.search(r'\$'+tag+r'\$(.*?)\$'+tag+r'\$',statement,re.S)[1]
                assert row['prosrc']==trusted and row['prosecdef'] is True and row['proconfig']==['search_path=pg_catalog']
                assert row['owner']==('aos_runtime' if signature in {FACT,SOURCE_FACT} else OWNER)
                acl=admin.execute("SELECT a.grantee::regrole::text AS grantee,a.privilege_type,a.is_grantable FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE p.oid=%s::regprocedure",(signature,)).fetchall()
                assert {a['grantee'] for a in acl}=={OWNER,'aos_runtime'} and len(acl)==2
                assert all(a['privilege_type']=='EXECUTE' and not a['is_grantable'] for a in acl)
                installed.append(dict(signature=signature,owner=row['owner'],body_sha256=hashlib.sha256(trusted.encode()).hexdigest(),acl=acl))
            installation_label=os.environ.get('AOS_SOURCE_MODEL_EVIDENCE_LABEL','source-model-current')
            (base/(installation_label+'-installation.json')).write_text(json.dumps(dict(functions=installed,source_original_unchanged=True,owner_memberships=0,old_table_read=False),indent=2)+'\n')
            debit_function=admin.execute("SELECT prosrc,r.rolname AS owner,prosecdef,proconfig FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner WHERE p.oid=%s::regprocedure",(DEBIT,)).fetchone()
            assert debit_function['prosrc']==re.search(r'\$debit\$(.*?)\$debit\$',debit_statements[-4],re.S)[1]
            assert debit_function['owner']==OWNER and debit_function['prosecdef'] and debit_function['proconfig']==['search_path=pg_catalog']
            (base/(installation_label+'-debit-installation.json')).write_text(json.dumps(dict(signature=DEBIT,owner=OWNER,
                body_sha256=hashlib.sha256(debit_function['prosrc'].encode()).hexdigest(),runtime_table_dml=False),indent=2)+'\n')
            case_installation=[]
            for signature,statement,tag,expected_owner in [(CASE_FACT,case_statements[6],'casefact','aos_runtime'),(CASE_DEBIT,case_statements[10],'casebind',OWNER)]:
                row=admin.execute('SELECT prosrc,r.rolname AS owner FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner WHERE p.oid=%s::regprocedure',(signature,)).fetchone()
                assert row['owner']==expected_owner and row['prosrc']==re.search(r'\$'+tag+r'\$(.*?)\$'+tag+r'\$',statement,re.S)[1]
                case_installation.append(dict(signature=signature,owner=row['owner'],body_sha256=hashlib.sha256(row['prosrc'].encode()).hexdigest()))
            (base/(installation_label+'-case-installation.json')).write_text(json.dumps(case_installation,indent=2)+'\n')
        params = conninfo_to_dict(get_dsn())
        params.update(user=ROLE, password=password, require_auth='scram-sha-256')
        if os.environ.get('AOS_SOURCE_NEW_JUDGE_NATIVE') == '1':
            # Explicit owned-lab integration; the default original node is unchanged.
            from source_newjudge_native_trial_1606 import run_source_newjudge_trial
            run_source_newjudge_trial(params, command, exact, source, provider,
                business_fixture_caller, issuer_factory, https_signer,
                guard_issuer_factory, guard_consumer_factory, tmp_path, base)
        with psycopg.connect(**params, row_factory=dict_row) as caller:
            caller.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
            caller.execute("SET LOCAL TimeZone='UTC'")
            apply_transaction_scope(caller, SCOPE)
            identity = caller.execute('SELECT session_user AS login,current_user AS role,pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
            assert caller.pgconn.used_password
            assert identity['login'] == ROLE and identity['role'] == 'aos_runtime'
            assert identity['xid'] != source.issuance_context.transaction_id
            assert identity['pid'] != source.issuance_context.backend_pid
            label=os.environ.get('AOS_SOURCE_MODEL_EVIDENCE_LABEL','source-model-current')
            (base/(label+'-input.json')).write_text(json.dumps(dict(source=source.model_dump(mode='json',by_alias=True),source_ref=exact.model_dump(mode='json',by_alias=True),application=app,approval_event_id=approval,caller=identity),indent=2)+'\n')
            from aos_api.aip_physical_capacity_occupation import prepare_source_model_application,prepare_guarded_source_model_application,SourceModelPreparation
            from aos_api.aip_model_eval_execution_owner import ModelEvalOwnerRejected
            with pytest.raises(ModelEvalOwnerRejected,match='Provider'):
                prepare_guarded_source_model_application(caller,SCOPE,command,other['request_id'],other_approval)
            assert caller.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation').fetchone()['n']==0
            with pytest.raises(ModelEvalOwnerRejected,match='positive'):
                prepare_source_model_application(caller,TenantScope('dev-org','dev-project'),command,app['request_id'],approval)
            preparation=prepare_guarded_source_model_application(caller,SCOPE,command,app['request_id'],approval)
            spec=importlib.util.spec_from_file_location('original_source_plan_fixture_r1',base/'original_source_plan_fixture_r1.py')
            whole_fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(whole_fixture)
            whole_fixture.verify_source_whole_plan(caller,SCOPE,command,source,preparation.application,judge_app,judge_approval,base,label)
            guard=preparation.physical_guard
            assert guard is not None and guard.version==1
            assert guard.physical_account_id==source.physical_account_id
            assert (guard.xid,guard.pid)==(identity['xid'],identity['pid'])
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with caller.transaction():caller.execute('SELECT * FROM aos_physical_capacity_occupation_private.account_guard')
            assert preparation.source==source
            assert preparation.application.request_hash==app['request_hash']
            assert preparation.application.caller_xid==identity['xid'] and preparation.application.caller_pid==identity['pid']
            assert preparation.execution_allowed is False
            from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
            parent=preparation.application.parent_limit.parent_hold_ref
            fact=caller.execute('SELECT public.read_capacity_occupation_eval_fact(%s,%s::jsonb,%s::uuid,%s,%s) AS fact',
                (_consumption_packet(command),Jsonb(exact.model_dump(mode='json',by_alias=True)),parent.resource_id,app['request_id'],app['request_hash'])).fetchone()['fact']
            assert fact['xid']==identity['xid'] and fact['pid']==identity['pid']
            assert fact['physicalAccountId']==source.physical_account_id
            assert fact['contentHash']==parent.content_hash and fact['executionAllowed'] is False
            assert fact['tokenUpperBound']==10000
            with pytest.raises(psycopg.errors.CheckViolation,match='CURRENT_HOLD'):
                with caller.transaction():
                    caller.execute('SELECT public.read_capacity_occupation_eval_fact(%s,%s::jsonb,%s::uuid,%s,%s)',
                        (_consumption_packet(command),Jsonb(exact.model_dump(mode='json',by_alias=True)),parent.resource_id,app['request_id'],'0'*64))
            assert caller.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']==identity['xid']
            (base/(label+'-budget-fact.json')).write_text(json.dumps(fact,indent=2)+'\n')
            for forbidden in (True,0,'false'):
                with pytest.raises(ValueError):
                    SourceModelPreparation.model_validate(preparation.model_copy(update={'execution_allowed':forbidden}))
            assert caller.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']==identity['xid']
            (base/(label+'-preparation.json')).write_text(json.dumps(preparation.model_dump(mode='json',by_alias=True),indent=2)+'\n')
            # The actual original preparation precedes this new artifact.
            # Prepared debits have no execution Intent/finalizer and must fail
            # even a real caller COMMIT, never become durable admission.
            first,second=uuid4(),uuid4()
            def debit(key,amount,request_hash=app['request_hash']):
                return caller.execute('SELECT public.prepare_capacity_parent_debit(%s,%s::jsonb,%s::uuid,%s,%s,%s::uuid,%s::bigint) AS fact',
                    (_consumption_packet(command),Jsonb(exact.model_dump(mode='json',by_alias=True)),parent.resource_id,
                     app['request_id'],request_hash,key,amount)).fetchone()['fact']
            # Budget still has room: this rejection must be physical capacity.
            class UndoProbe(Exception):pass
            with pytest.raises(UndoProbe):
                with caller.transaction():
                    debit(uuid4(),1);limited=debit(uuid4(),1)
                    assert limited['physicalRequests']==2 and limited['physicalTokens']==20000
                    with pytest.raises(psycopg.errors.CheckViolation,match='PHYSICAL_CAPACITY'):
                        with caller.transaction():debit(uuid4(),1)
                    raise UndoProbe()
            one=debit(first,6);two=debit(second,4)
            assert one['allocatedMinor']==6 and two['allocatedMinor']==10 and two['parentCapMinor']==10
            replay=debit(first,6);assert replay['allocatedMinor']==10
            assert one['physicalTokens']==10000 and two['physicalTokens']==replay['physicalTokens']==20000
            assert two['physicalRequests']==replay['physicalRequests']==2
            from aos_api.aip_physical_capacity_occupation_authority import occupation_case_binding_statements,CASE_DEBIT
            # RED is after the complete original Source/budget/debit prefix.
            # In GREEN the fixed artifact is installed before caller begins.
            from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
            suite_ref=preparation.application.request.suite_ref
            row=caller.execute('SELECT * FROM aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s',
                (*SCOPE.key,suite_ref.asset_id,suite_ref.revision)).fetchone()
            suite=AipEvalPackRegistry._suite_from_row(row)
            suite_raw=json.dumps(suite.model_dump(mode='json',by_alias=True,exclude={'content_hash'}),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
            def bind_case(key=first,amount=6,case_id=suite.cases[0].case_id,witness=suite_raw):
                return caller.execute('SELECT public.prepare_capacity_case_parent_debit(%s,%s::jsonb,%s::uuid,%s,%s,%s::uuid,%s::bigint,%s,%s) AS fact',
                    (_consumption_packet(command),Jsonb(exact.model_dump(mode='json',by_alias=True)),parent.resource_id,
                     app['request_id'],app['request_hash'],key,amount,witness,case_id)).fetchone()['fact']
            bound=bind_case();assert bound['inputHash']==suite.cases[0].input_artifact.content_hash
            assert bound['caseBinding']['judgeRef']==suite.judge.model_dump(mode='json',by_alias=True)
            original_expected=suite.cases[0].expected_artifact
            expected_ref=None if original_expected is None else original_expected.model_dump(mode='json',by_alias=True)
            assert bound['caseBinding']['expectedRef']==expected_ref
            assert bind_case()['caseBindingHash']==bound['caseBindingHash']
            with pytest.raises(psycopg.errors.CheckViolation,match='CASE'):
                with caller.transaction():bind_case(case_id='not-an-original-case')
            with pytest.raises(psycopg.errors.CheckViolation,match='SUITE'):
                with caller.transaction():bind_case(witness=suite_raw+b' ')
            with pytest.raises(psycopg.errors.CheckViolation,match='CASE_REPLAY'):
                with caller.transaction():bind_case(key=second,amount=4)
            (base/(label+'-case-binding.json')).write_text(json.dumps(dict(fact=bound,suite_raw=suite_raw.decode(),
                input_ref=suite.cases[0].input_artifact.model_dump(mode='json',by_alias=True),execution_allowed=False),indent=2)+'\n')
            from aos_api.aip_physical_capacity_occupation_authority import occupation_input_binding_statements
            from aos_api.ecommerce_content_pre_review_pack import build_content_pre_review_eval_packs
            from aos_api.ecommerce_content_pre_review_eval import GRAPH_ID,build_content_pre_review_graph
            from aos_api.aip_eval_contracts import AssetRevisionRef,AssetType
            from aos_api.aip_logic_graph_models import compute_logic_graph_hash
            original_target=AssetRevisionRef(assetType=AssetType.LOGIC_GRAPH,assetId=GRAPH_ID,revision='1',contentHash=compute_logic_graph_hash(build_content_pre_review_graph()))
            _,original_pack=build_content_pre_review_eval_packs(original_target)
            original_ref=suite.cases[0].input_artifact
            input_value=original_pack.artifacts[(original_ref.artifact_id,original_ref.revision)]
            input_raw=json.dumps(input_value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
            def bind_input(witness=input_raw):
                return caller.execute('SELECT public.prepare_capacity_input_parent_debit(%s,%s::jsonb,%s::uuid,%s,%s,%s::uuid,%s::bigint,%s,%s,%s) AS fact',(_consumption_packet(command),Jsonb(exact.model_dump(mode='json',by_alias=True)),parent.resource_id,app['request_id'],app['request_hash'],first,6,suite_raw,suite.cases[0].case_id,witness)).fetchone()['fact']
            input_bound=bind_input()
            assert input_bound['verifiedInputHash']==original_ref.content_hash
            assert input_bound['inputValue']==input_value and input_bound['executionAllowed'] is False
            for invalid in (input_raw+b' ',None):
                with pytest.raises(psycopg.errors.CheckViolation,match='INPUT_BYTES'):
                    with caller.transaction():bind_input(invalid)
            assert bind_input()['allocatedMinor']==10
            (base/(label+'-input-binding.json')).write_text(json.dumps(dict(fact=input_bound,input_raw=input_raw.decode(),input_ref=original_ref.model_dump(mode='json',by_alias=True),execution_allowed=False),indent=2)+'\n')
            from aos_api.aip_physical_capacity_occupation_authority import occupation_intent_statements
            intent_id=uuid4()
            def prepare_intent(key=intent_id,debit_key=first,witness=input_raw):
                return caller.execute('SELECT public.prepare_capacity_execution_intent(%s,%s::jsonb,%s::uuid,%s,%s,%s::uuid,%s::bigint,%s,%s,%s,%s::uuid) AS fact',(_consumption_packet(command),Jsonb(exact.model_dump(mode='json',by_alias=True)),parent.resource_id,app['request_id'],app['request_hash'],debit_key,6,suite_raw,suite.cases[0].case_id,witness,key)).fetchone()['fact']
            intent=prepare_intent()
            assert intent['state']=='prepared' and intent['executionAllowed'] is False
            assert intent['immutable']['inputHash']==original_ref.content_hash
            assert intent['immutable']['caseBinding']==bound['caseBinding']
            assert intent['immutable']['caseBinding']['expectedRef']==expected_ref
            assert intent['immutable']['application']==preparation.application.request.model_dump(mode='json',by_alias=True)
            assert intent['immutable']['requestMaker']!=intent['immutable']['approvalChecker']
            assert prepare_intent()['contentHash']==intent['contentHash']
            mutations=[]
            for operation in ('update','delete'):
                with pytest.raises(psycopg.errors.InsufficientPrivilege,match='CAPACITY_INTENT_IMMUTABLE') as denied:
                    with caller.transaction():
                        caller.execute(f'SELECT public.test_capacity_intent_{operation}_probe(%s::uuid)',(intent_id,))
                restored=prepare_intent()
                assert restored==intent
                mutations.append(dict(operation=operation,sqlstate=denied.value.sqlstate,
                    content_hash=restored['contentHash'],existing_row_verified=True))
            (base/(label+'-intent-existing-row-negative.json')).write_text(json.dumps(dict(
                intent_id=str(intent_id),caller_xid=identity['xid'],caller_pid=identity['pid'],
                probes=mutations,execution_allowed=False),indent=2)+'\n')
            for key,debit_key,witness,error in [(uuid4(),first,input_raw,'INTENT_REPLAY'),(None,first,input_raw,'INTENT_ID'),(intent_id,second,input_raw,'REPLAY'),(intent_id,first,input_raw+b' ','INPUT_BYTES')]:
                with pytest.raises(psycopg.errors.CheckViolation,match=error):
                    with caller.transaction():prepare_intent(key,debit_key,witness)
            (base/(label+'-intent.json')).write_text(json.dumps(intent,indent=2)+'\n')
            assert replay['executionAllowed'] is False and replay['xid']==identity['xid']
            for key,amount,error in [(uuid4(),1,'PARENT_CAP'),(uuid4(),9223372036854775807,'PARENT_CAP'),(first,5,'REPLAY'),(uuid4(),0,'INPUT'),(uuid4(),None,'INPUT'),(None,1,'INPUT')]:
                with pytest.raises(psycopg.errors.CheckViolation,match=error):
                    with caller.transaction():debit(key,amount)
            with pytest.raises(psycopg.errors.CheckViolation,match='CURRENT_HOLD'):
                with caller.transaction():debit(uuid4(),1,'0'*64)
            with pytest.raises(psycopg.errors.CheckViolation,match='FINALIZE_REQUIRED'):
                with caller.transaction():caller.execute('SET CONSTRAINTS ALL IMMEDIATE')
            with pytest.raises(psycopg.errors.CheckViolation,match='FINALIZE_REQUIRED'):
                caller.commit()
            with isolated_owner() as admin:
                assert admin.execute('SELECT pg_xact_status(%s::xid8) AS s',(identity['xid'],)).fetchone()['s']=='aborted'
                for table in ('parent_debit_guard','prepared_parent_debit'):
                    assert admin.execute('SELECT count(*) AS n FROM '+SCHEMA+'.'+table).fetchone()['n']==0
            (base/(label+'-parent-debit.json')).write_text(json.dumps(dict(first=one,second=two,replay=replay,
                commit_sqlstate='23514',caller_status='aborted',early_check_rejected=True,private_rows=0,execution_allowed=False),indent=2)+'\n')
        with connect(SCOPE) as c:
            assert c.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation WHERE request_id=%s',(app['request_id'],)).fetchone()['n']==0
            assert c.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation WHERE request_id=%s',(other['request_id'],)).fetchone()['n']==0
            assert c.execute('SELECT count(*) AS n FROM aip_agent_run').fetchone()['n']==0
        with isolated_owner() as admin:
            assert admin.execute('SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.account_guard').fetchone()['n']==0
        # Real Source caller race: the shared guard is metadata, not admission.
        # Keep its known commits in this retained isolated database for audit.
        from threading import Thread,Event
        import time
        def guard_read(c):
            c.execute("SET LOCAL TimeZone='UTC'")
            apply_transaction_scope(c,SCOPE)
            return c.execute('SELECT public.prepare_capacity_occupation_account_guard(%s,%s::jsonb) AS fact',
                (_consumption_packet(command),Jsonb(exact.model_dump(mode='json',by_alias=True)))).fetchone()['fact']
        with psycopg.connect(**params,row_factory=dict_row) as writer,psycopg.connect(**params,row_factory=dict_row) as stale:
            writer.isolation_level=stale.isolation_level=psycopg.IsolationLevel.SERIALIZABLE
            baseline=guard_read(writer);assert baseline['version']==1
            writer.commit()
            stale.execute("SET LOCAL TimeZone='UTC'");apply_transaction_scope(stale,SCOPE)
            stale_id=stale.execute('SELECT pg_current_snapshot()::text AS snapshot,pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
            current=guard_read(writer);assert current['version']==2
            entered=Event();done=Event();outcome={}
            def old_snapshot_read():
                try:
                    stale.execute("SET LOCAL statement_timeout='10s'")
                    entered.set();outcome['fact']=guard_read(stale)
                except BaseException as error:outcome['error']=error
                finally:done.set()
            thread=Thread(target=old_snapshot_read);thread.start()
            try:
                assert entered.wait(2)
                blocked=False
                with isolated_owner() as observer:
                    deadline=time.monotonic()+4
                    while time.monotonic()<deadline:
                        observer.execute('SELECT pg_stat_clear_snapshot()')
                        blocked=current['pid'] in observer.execute('SELECT pg_blocking_pids(%s) AS pids',(stale_id['pid'],)).fetchone()['pids']
                        if blocked:break
                        assert not done.is_set()
                        time.sleep(.02)
                assert blocked and not done.is_set()
                writer.commit()
                assert done.wait(4)
                assert isinstance(outcome.get('error'),psycopg.errors.SerializationFailure) and 'fact' not in outcome
                stale.rollback()
                (base/(label+'-guard-race.json')).write_text(json.dumps(dict(baseline=baseline,writer=current,stale=stale_id,blocked=True,sqlstate='40001',execution_allowed=False),indent=2)+'\n')
            finally:
                writer.rollback();thread.join(timeout=11);assert not thread.is_alive();stale.rollback()
    finally:
        with isolated_owner() as admin:
            from aos_api.aip_physical_capacity_occupation_authority import OWNER,FACT,ENTRY
            from aos_api.aip_physical_capacity_occupation_authority import SOURCE_FACT,GUARD,SCHEMA
            if os.environ.get('AOS_SOURCE_NEW_JUDGE_NATIVE') == '1':
                from aos_api.aip_physical_capacity_occupation_authority import JUDGE_DEBIT, JUDGE_ENTRY, JUDGE_FACT
                if os.environ.get('AOS_NEW_JUDGE_INTENT_NATIVE') == '1':
                    from aos_api.aip_physical_capacity_occupation_authority import JUDGE_INTENT
                    admin.execute('DROP FUNCTION IF EXISTS '+JUDGE_INTENT)
                for signature in (JUDGE_DEBIT, JUDGE_ENTRY, JUDGE_FACT):
                    admin.execute('DROP FUNCTION IF EXISTS '+signature)
            for operation in ('update','delete'):
                admin.execute(f'DROP FUNCTION IF EXISTS public.test_capacity_intent_{operation}_probe(uuid)')
            admin.execute('DROP FUNCTION IF EXISTS public.prepare_capacity_execution_intent(bytea,jsonb,uuid,text,text,uuid,bigint,bytea,text,bytea,uuid)')
            admin.execute('DROP FUNCTION IF EXISTS public.prepare_capacity_input_parent_debit(bytea,jsonb,uuid,text,text,uuid,bigint,bytea,text,bytea)')
            admin.execute('DROP FUNCTION IF EXISTS public.prepare_capacity_parent_debit(bytea,jsonb,uuid,text,text,uuid,bigint)')
            admin.execute('DROP FUNCTION IF EXISTS public.prepare_capacity_case_parent_debit(bytea,jsonb,uuid,text,text,uuid,bigint,bytea,text)')
            admin.execute('DROP FUNCTION IF EXISTS public.capacity_occupation_eval_case_fact(bytea,jsonb,uuid,text,text,bytea,text)')
            admin.execute('DROP FUNCTION IF EXISTS '+GUARD)
            admin.execute('DROP FUNCTION IF EXISTS '+SOURCE_FACT)
            # Retained isolated private guard metadata is evidence. Its closed
            # owner has no login/membership, and runtime never receives DML.
            admin.execute('DROP FUNCTION IF EXISTS '+ENTRY)
            admin.execute('DROP FUNCTION IF EXISTS '+FACT)
            if admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(OWNER,)).fetchone():
                admin.execute('REVOKE USAGE ON SCHEMA public FROM '+OWNER)
            admin.execute(psycopg.sql.SQL('REVOKE CONNECT ON DATABASE {} FROM '+ROLE).format(psycopg.sql.Identifier(admin.info.dbname)))
            admin.execute('DROP FUNCTION IF EXISTS public.read_current_capacity_source(bytea,jsonb)')
            admin.execute('DROP FUNCTION IF EXISTS public.read_capacity_source_for_occupation(bytea,jsonb)')
            admin.execute('DROP FUNCTION IF EXISTS public.require_capacity_occupation_source_installation()')
            from aos_api.aip_provider_capacity_occupation_epoch_profile import legacy_epoch_profile_restoration_statements
            for statement in legacy_epoch_profile_restoration_statements():
                admin.execute(statement)
            admin.execute('ALTER ROLE aos_provider_capacity_occupation NOLOGIN')
            admin.execute('REVOKE aos_runtime FROM aos_provider_capacity_occupation')
