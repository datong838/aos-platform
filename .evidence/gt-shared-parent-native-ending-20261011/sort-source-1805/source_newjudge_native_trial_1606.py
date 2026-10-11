"""Fresh original Source + complete dual-parent native risk bridge trial."""
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
import copy
import json
import os
import psycopg
import pytest
from psycopg.rows import dict_row
from aos_api.tenant_scope import apply_transaction_scope, TenantScope
from tests.aip._runtime_guard_history_fixture import isolated_owner

POLICY = None

def run_source_newjudge_trial(params, command, exact, source, provider, caller,
        issuer_factory, https_signer, guard_issuer_factory, guard_consumer_factory, tmp_path, base):
    from aos_api.aip_physical_capacity_occupation_authority import (
        occupation_judge_fact_statements, occupation_judge_parent_debit_statements,
        occupation_plan_risk_statements, occupation_shared_risk_description_statements)
    from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
    from psycopg.types.json import Jsonb
    from aos_api.aip_physical_capacity_occupation import prepare_shared_parent_risk_plan, prepare_shared_parent_risk_description
    from aos_api.aip_model_eval_execution_owner import ModelEvalOwnerRejected
    from tests.aip.test_model_eval_judge_authority_pg import test_exact_signed_rule_new_original_suite
    # Reuse the current original test unchanged: its fresh approval window is
    # 150 seconds. Never extend an existing approval or replay r1 effects.
    import inspect,hashlib
    original_text=inspect.getsource(test_exact_signed_rule_new_original_suite)
    assert original_text.count('expires=datetime.now(UTC)+timedelta(seconds=150)')==1
    Path(__file__).with_name('approval-window-origin.json').write_text(json.dumps({
        'original_function_sha256':hashlib.sha256(original_text.encode()).hexdigest(),
        'original_test_used_unchanged':True,'current_fresh_approval_seconds':150,
        'clock_mocked':False,'previous_expired_approval_extended':False},indent=2)+'\n')
    proofs = []
    root_state = {}
    def install_before_snapshot():
        from aos_api import aip_shared_parent_atomic_admission as admission
        from aos_api.aip_physical_capacity_occupation_authority import OWNER
        with isolated_owner() as admin:
            from aos_api.aip_provider_capacity_catalog_audit_profile import catalog_installation_statements, catalog_profile_is_installed
            for statement in catalog_installation_statements(include_consumer=True):admin.execute(statement)
            assert catalog_profile_is_installed(admin)
            for statement in (*occupation_judge_fact_statements(),
                              *occupation_judge_parent_debit_statements(),
                              *occupation_plan_risk_statements(),
                              *occupation_shared_risk_description_statements()):
                admin.execute(statement)
        with isolated_owner() as admin:
            for statement in (*admission.shared_parent_original_fact_statements(), *admission.shared_parent_admission_origin_statements()):
                admin.execute(statement)
            from aos_api import aip_shared_parent_certificate_prepare as cert
            from aos_api import aip_model_eval_execution_authority as auth
            from shared_identity_certificate_fixture import prime_root
            from datetime import datetime,timezone
            root=prime_root(datetime.now(timezone.utc));root_state['root']=root
            for statement in cert.shared_parent_certificate_prepare_statements():
                if (statement.startswith('CREATE FUNCTION '+cert.VERIFY.split('(')[0]+'(')
                    or statement.startswith('ALTER FUNCTION '+cert.VERIFY+' ')
                    or statement.startswith('REVOKE ALL ON FUNCTION '+cert.VERIFY+' ')
                    or statement.startswith('GRANT EXECUTE ON FUNCTION '+cert.VERIFY+' ')):
                    admin.execute(statement)
            for statement in admission.shared_parent_admission_certificate_set_statements():admin.execute(statement)
            for statement in (*admission.shared_parent_admission_storage_statements(),*admission.shared_parent_pending_origin_lookup_statements(),*admission.shared_parent_physical_obligation_statements(),*admission.shared_parent_initial_intent_statements(),*admission.shared_parent_end_authority_statements(),*admission.shared_parent_initial_call_authority_statements(),*admission.shared_parent_initial_window_obligation_statements(),*admission.shared_parent_live_physical_fact_statements(),*admission.shared_parent_complete_parent_risk_statements(),*admission.shared_parent_final_intent_validation_statements(),*admission.shared_parent_final_call_validation_statements()):admin.execute(statement)
            for statement in (*admission.shared_parent_exact_receipt_statements(), *admission.shared_parent_final_physical_comparison_statements()):admin.execute(statement)
            for statement in admission.shared_parent_complete_end_fact_statements():admin.execute(statement)
            admin.execute("CREATE FUNCTION public.test_fixed_native_collector(uuid,text,xid8,integer) RETURNS jsonb LANGUAGE C VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS '/tmp/aos_fixed_collector_b2ba3349a459440fa396a2d190846733.so','probe_fixed_collector'")
            admin.execute('REVOKE ALL ON FUNCTION public.test_fixed_native_collector(uuid,text,xid8,integer) FROM PUBLIC,aos_runtime')
            admin.execute('GRANT EXECUTE ON FUNCTION public.test_fixed_native_collector(uuid,text,xid8,integer) TO '+admission.OWNER)
            for name,target in [('test_owned_receipt_v2','public.stage_shared_parent_complete_receipt_v2'),('test_owned_final_physical','public.verify_shared_parent_final_physical'),('test_owned_complete_end_facts','public.test_fixed_native_collector')]:
                admin.execute('CREATE FUNCTION public.'+name+'(p_plan uuid,p_hash text,p_xid xid8,p_pid integer) RETURNS jsonb LANGUAGE SQL VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS '+"'SELECT "+target+"(p_plan,p_hash,p_xid,p_pid)'")
                signature='public.'+name+'(uuid,text,xid8,integer)'
                admin.execute('ALTER FUNCTION '+signature+' OWNER TO '+admission.OWNER)
                admin.execute('REVOKE ALL ON FUNCTION '+signature+' FROM PUBLIC')
                admin.execute('GRANT EXECUTE ON FUNCTION '+signature+' TO aos_runtime')
            raw=json.dumps(root,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
            rh=hashlib.sha256(raw).hexdigest()
            admin.execute('SET LOCAL ROLE '+auth.ISSUER_OWNER)
            admin.execute("SET LOCAL aos.org_id='org-org'");admin.execute("SET LOCAL aos.project_id='dev-project'")
            admin.execute('INSERT INTO aos_model_eval_issuer_private.issuer_root(org_id,project_id,issuer_id,key_id,bootstrap_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s)',('org-org','dev-project',root['issuerId'],root['issuerKeyId'],'a'*64,rh,raw))
            admin.execute('INSERT INTO aos_model_eval_issuer_private.issuer_epoch(org_id,project_id,issuer_id,key_id,epoch,root_hash) VALUES (%s,%s,%s,%s,1,%s)',('org-org','dev-project',root['issuerId'],root['issuerKeyId'],rh))
            root_state['xid']=admin.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
            admin.execute('RESET ROLE')
            admin.execute("CREATE FUNCTION public.test_owned_admission_certificates(p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,p_judge uuid,p_jr text,p_jh text,p_plan uuid,p_manifest jsonb,p_manifest_hash text,p_certificates bytea) RETURNS jsonb LANGUAGE SQL VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS 'SELECT public.validate_shared_parent_admission_certificate_set(p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_manifest_hash,p_certificates)'")
            signature='public.test_owned_admission_certificates(bytea,jsonb,uuid,text,text,uuid,text,text,uuid,jsonb,text,bytea)'
            admin.execute('ALTER FUNCTION '+signature+' OWNER TO '+auth.ISSUER_OWNER)
            admin.execute('REVOKE ALL ON FUNCTION '+signature+' FROM PUBLIC')
            admin.execute('GRANT EXECUTE ON FUNCTION '+signature+' TO aos_runtime')
            admin.execute("CREATE FUNCTION public.test_owned_pending_origin(p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,p_judge uuid,p_jr text,p_jh text,p_plan uuid,p_manifest jsonb,p_manifest_hash text,p_certificates bytea) RETURNS jsonb LANGUAGE SQL VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS 'SELECT public.persist_shared_parent_admission_origin(p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_manifest_hash,p_certificates)'")
            signature=admission.PERSIST.replace('public.persist_shared_parent_admission_origin(', 'public.test_owned_pending_origin(')
            admin.execute('ALTER FUNCTION '+signature+' OWNER TO '+auth.ISSUER_OWNER);admin.execute('REVOKE ALL ON FUNCTION '+signature+' FROM PUBLIC');admin.execute('GRANT EXECUTE ON FUNCTION '+signature+' TO aos_runtime')
            admin.execute("""CREATE FUNCTION public.test_owned_pending_mutation(p_plan uuid,p_kind text) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $m$ BEGIN
             IF p_kind='UPDATE' THEN UPDATE aos_shared_parent_admission_private.pending_origin SET caller_pid=caller_pid WHERE plan_id=p_plan;
             ELSIF p_kind='DELETE' THEN DELETE FROM aos_shared_parent_admission_private.pending_origin WHERE plan_id=p_plan;
             ELSIF p_kind='TRUNCATE' THEN TRUNCATE aos_shared_parent_admission_private.pending_origin;
             ELSE RAISE EXCEPTION 'TEST_KIND'; END IF; END $m$""")
            admin.execute("CREATE FUNCTION public.test_owned_end_authority(p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,p_judge uuid,p_jr text,p_jh text,p_plan uuid,p_manifest jsonb,p_mh text,p_certificates bytea,p_pending_hash text) RETURNS jsonb LANGUAGE SQL VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS 'SELECT public.stage_shared_parent_end_authority(p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_mh,p_certificates,p_pending_hash)'")
            sig=admission.STAGE_AUTHORITY.replace('stage_shared_parent_end_authority','test_owned_end_authority')
            admin.execute('ALTER FUNCTION '+sig+' OWNER TO '+auth.ISSUER_OWNER)
            admin.execute('REVOKE ALL ON FUNCTION '+sig+' FROM PUBLIC')
            admin.execute('GRANT EXECUTE ON FUNCTION '+sig+' TO aos_runtime')
            admin.execute("CREATE FUNCTION public.test_owned_retained_origin(p_plan uuid,p_hash text,p_xid xid8,p_pid integer) RETURNS jsonb LANGUAGE SQL VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS 'SELECT public.read_shared_parent_retained_origin(p_plan,p_hash,p_xid,p_pid)'")
            sig=admission.READ_RETAINED.replace('read_shared_parent_retained_origin','test_owned_retained_origin')
            admin.execute('ALTER FUNCTION '+sig+' OWNER TO '+admission.OWNER)
            admin.execute('REVOKE ALL ON FUNCTION '+sig+' FROM PUBLIC')
            admin.execute('GRANT EXECUTE ON FUNCTION '+sig+' TO aos_runtime')
            admin.execute("CREATE FUNCTION public.test_owned_authority_mutation(p_plan uuid,p_kind text) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $m$ BEGIN IF p_kind='UPDATE' THEN UPDATE aos_shared_parent_admission_private.end_authority SET caller_pid=caller_pid WHERE plan_id=p_plan; ELSIF p_kind='DELETE' THEN DELETE FROM aos_shared_parent_admission_private.end_authority WHERE plan_id=p_plan; ELSE RAISE EXCEPTION 'TEST_KIND'; END IF; END $m$")
            sig='public.test_owned_authority_mutation(uuid,text)'
            admin.execute('ALTER FUNCTION '+sig+' OWNER TO '+auth.ISSUER_OWNER)
            admin.execute('REVOKE ALL ON FUNCTION '+sig+' FROM PUBLIC')
            admin.execute('GRANT EXECUTE ON FUNCTION '+sig+' TO aos_runtime')
            admin.execute('CREATE FUNCTION public.test_owned_initial_obligation(p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,p_judge uuid,p_jr text,p_jh text,p_plan uuid,p_manifest jsonb,p_mh text,p_certificates bytea,p_pending_hash text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $p$ BEGIN RETURN public.prepare_shared_parent_initial_target_obligation(p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_mh,p_certificates,p_pending_hash); END $p$')
            initial_signature=admission.INITIAL_OBLIGATION.replace('prepare_shared_parent_initial_target_obligation','test_owned_initial_obligation')
            admin.execute('ALTER FUNCTION '+initial_signature+' OWNER TO '+admission.OWNER)
            admin.execute('REVOKE ALL ON FUNCTION '+initial_signature+' FROM PUBLIC')
            admin.execute('GRANT EXECUTE ON FUNCTION '+initial_signature+' TO aos_runtime')
            admin.execute("CREATE FUNCTION public.test_owned_initial_intents(p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,p_judge uuid,p_jr text,p_jh text,p_plan uuid,p_manifest jsonb,p_mh text,p_certificates bytea,p_pending_hash text,p_obligation_hash text,p_suite_raw bytea,p_input_raw bytea,p_target_intent uuid,p_judge_intent uuid) RETURNS jsonb LANGUAGE SQL VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS 'SELECT public.prepare_shared_parent_initial_intents(p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_mh,p_certificates,p_pending_hash,p_obligation_hash,p_suite_raw,p_input_raw,p_target_intent,p_judge_intent)'")
            sig=admission.INITIAL_INTENT.replace('prepare_shared_parent_initial_intents','test_owned_initial_intents')
            admin.execute("CREATE FUNCTION public.test_owned_initial_call_authority(p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,p_judge uuid,p_jr text,p_jh text,p_plan uuid,p_manifest jsonb,p_mh text,p_certificates bytea,p_pending_hash text,p_obligation_hash text,p_suite_raw bytea,p_input_raw bytea,p_target_intent uuid,p_judge_intent uuid) RETURNS jsonb LANGUAGE SQL VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS 'SELECT public.stage_shared_parent_initial_call_authority(p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_mh,p_certificates,p_pending_hash,p_obligation_hash,p_suite_raw,p_input_raw,p_target_intent,p_judge_intent)' ")
            call_sig=admission.STAGE_INITIAL_CALL.replace('stage_shared_parent_initial_call_authority','test_owned_initial_call_authority')
            admin.execute('ALTER FUNCTION '+call_sig+' OWNER TO '+admission.OWNER);admin.execute('REVOKE ALL ON FUNCTION '+call_sig+' FROM PUBLIC');admin.execute('GRANT EXECUTE ON FUNCTION '+call_sig+' TO aos_runtime')
            admin.execute("CREATE FUNCTION public.test_owned_read_initial_call(p_plan uuid,p_hash text,p_xid xid8,p_pid integer) RETURNS jsonb LANGUAGE SQL VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS 'SELECT public.read_shared_parent_initial_call_authority(p_plan,p_hash,p_xid,p_pid)'")
            call_sig=admission.READ_INITIAL_CALL.replace('read_shared_parent_initial_call_authority','test_owned_read_initial_call')
            admin.execute('ALTER FUNCTION '+call_sig+' OWNER TO '+admission.OWNER);admin.execute('REVOKE ALL ON FUNCTION '+call_sig+' FROM PUBLIC');admin.execute('GRANT EXECUTE ON FUNCTION '+call_sig+' TO aos_runtime')
            admin.execute("CREATE FUNCTION public.test_owned_final_call(p_plan uuid,p_hash text,p_xid xid8,p_pid integer) RETURNS jsonb LANGUAGE SQL VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS 'SELECT public.verify_shared_parent_final_call_authority(p_plan,p_hash,p_xid,p_pid)'")
            final_sig='public.test_owned_final_call(uuid,text,xid8,integer)'
            admin.execute('ALTER FUNCTION '+final_sig+' OWNER TO '+admission.OWNER)
            admin.execute('REVOKE ALL ON FUNCTION '+final_sig+' FROM PUBLIC')
            admin.execute('GRANT EXECUTE ON FUNCTION '+final_sig+' TO aos_runtime')
            admin.execute("CREATE FUNCTION public.test_owned_initial_window(p_plan uuid,p_hash text,p_xid xid8,p_pid integer) RETURNS jsonb LANGUAGE SQL VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS 'SELECT public.stage_shared_parent_initial_window_obligation(p_plan,p_hash,p_xid,p_pid)'")
            win_sig=admission.STAGE_INITIAL_WINDOW.replace('stage_shared_parent_initial_window_obligation','test_owned_initial_window')
            admin.execute("CREATE FUNCTION public.test_owned_live_physical(p_plan uuid,p_hash text,p_xid xid8,p_pid integer) RETURNS jsonb LANGUAGE SQL VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS 'SELECT public.read_shared_parent_live_physical_facts(p_plan,p_hash,p_xid,p_pid)'")
            admin.execute('ALTER FUNCTION public.test_owned_live_physical(uuid,text,xid8,integer) OWNER TO '+admission.OWNER)
            admin.execute('REVOKE ALL ON FUNCTION public.test_owned_live_physical(uuid,text,xid8,integer) FROM PUBLIC')
            admin.execute('GRANT EXECUTE ON FUNCTION public.test_owned_live_physical(uuid,text,xid8,integer) TO aos_runtime')

            admin.execute("CREATE FUNCTION public.test_owned_complete_risk(p_plan uuid,p_hash text,p_xid xid8,p_pid integer) RETURNS jsonb LANGUAGE SQL VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS 'SELECT public.stage_shared_parent_complete_risk(p_plan,p_hash,p_xid,p_pid)'")
            sig='public.test_owned_complete_risk(uuid,text,xid8,integer)'
            admin.execute('ALTER FUNCTION '+sig+' OWNER TO '+admission.OWNER)
            admin.execute('REVOKE ALL ON FUNCTION '+sig+' FROM PUBLIC')
            admin.execute('GRANT EXECUTE ON FUNCTION '+sig+' TO aos_runtime')
            admin.execute("CREATE FUNCTION public.test_owned_risk_mutation(p_plan uuid,p_op text) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $m$ BEGIN IF p_op='UPDATE' THEN UPDATE aos_shared_parent_physical_private.complete_parent_risk SET caller_pid=caller_pid WHERE plan_id=p_plan; ELSIF p_op='DELETE' THEN DELETE FROM aos_shared_parent_physical_private.complete_parent_risk WHERE plan_id=p_plan; ELSE RAISE EXCEPTION 'TEST_KIND'; END IF; END $m$")
            sig='public.test_owned_risk_mutation(uuid,text)'
            admin.execute('ALTER FUNCTION '+sig+' OWNER TO '+admission.OWNER)
            admin.execute('REVOKE ALL ON FUNCTION '+sig+' FROM PUBLIC')
            admin.execute('GRANT EXECUTE ON FUNCTION '+sig+' TO aos_runtime')
            admin.execute("CREATE FUNCTION public.test_owned_live_union(p_plan uuid) RETURNS jsonb LANGUAGE SQL SECURITY DEFINER SET search_path=pg_catalog AS $probe$ SELECT jsonb_build_object('requests',count(*),'tokens',coalesce(sum(token_units),0)) FROM (SELECT d.token_units FROM aos_physical_capacity_occupation_private.prepared_parent_debit d JOIN aos_shared_parent_physical_private.initial_target_obligation o ON d.physical_account_id=o.physical_account_id WHERE o.plan_id=p_plan UNION ALL SELECT d.token_upper_bound FROM aos_shared_parent_physical_private.initial_target_obligation d JOIN aos_shared_parent_physical_private.initial_target_obligation o ON d.physical_account_id=o.physical_account_id WHERE o.plan_id=p_plan) native_union $probe$")
            admin.execute('ALTER FUNCTION public.test_owned_live_union(uuid) OWNER TO '+admission.OWNER)
            admin.execute('REVOKE ALL ON FUNCTION public.test_owned_live_union(uuid) FROM PUBLIC')
            admin.execute('GRANT EXECUTE ON FUNCTION public.test_owned_live_union(uuid) TO aos_runtime')

            admin.execute('ALTER FUNCTION '+win_sig+' OWNER TO '+admission.OWNER);admin.execute('REVOKE ALL ON FUNCTION '+win_sig+' FROM PUBLIC');admin.execute('GRANT EXECUTE ON FUNCTION '+win_sig+' TO aos_runtime')
            sig=admission.INITIAL_INTENT.replace('prepare_shared_parent_initial_intents','test_owned_initial_intents')
            admin.execute('ALTER FUNCTION '+sig+' OWNER TO '+admission.OWNER)
            admin.execute('REVOKE ALL ON FUNCTION '+sig+' FROM PUBLIC')
            admin.execute('GRANT EXECUTE ON FUNCTION '+sig+' TO aos_runtime')
            admin.execute('CREATE FUNCTION public.test_owned_pending_lookup(p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,p_judge uuid,p_jr text,p_jh text,p_plan uuid,p_manifest jsonb,p_mh text,p_certificates bytea,p_pending_hash text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $p$ BEGIN RETURN public.read_shared_parent_pending_origin(p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_mh,p_certificates,p_pending_hash); END $p$')
            lookup_signature=admission.READ_PENDING.replace('read_shared_parent_pending_origin','test_owned_pending_lookup')
            admin.execute('ALTER FUNCTION '+lookup_signature+' OWNER TO '+admission.OWNER)
            admin.execute('REVOKE ALL ON FUNCTION '+lookup_signature+' FROM PUBLIC')
            admin.execute('GRANT EXECUTE ON FUNCTION '+lookup_signature+' TO aos_runtime')
            signature='public.test_owned_pending_mutation(uuid,text)';admin.execute('ALTER FUNCTION '+signature+' OWNER TO '+auth.ISSUER_OWNER);admin.execute('REVOKE ALL ON FUNCTION '+signature+' FROM PUBLIC');admin.execute('GRANT EXECUTE ON FUNCTION '+signature+' TO aos_runtime')
            # Explicit test-only forwarding proxy. No original production
            # function is replaced and no formal/retained old DB is used.
            admin.execute("""CREATE FUNCTION public.test_owned_versioned_origin(
              p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,
              p_judge uuid,p_jr text,p_jh text,p_plan uuid,p_manifest jsonb,p_hash text)
              RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $proxy$
              DECLARE before_counts jsonb; after_counts jsonb; result jsonb;
              BEGIN
                before_counts:=jsonb_build_array(
                  (SELECT count(*) FROM aos_physical_capacity_occupation_private.prepared_plan_risk),
                  (SELECT count(*) FROM aos_physical_capacity_occupation_private.prepared_shared_risk_description));
                result:=public.build_shared_parent_admission_origin(p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_hash);
                after_counts:=jsonb_build_array(
                  (SELECT count(*) FROM aos_physical_capacity_occupation_private.prepared_plan_risk),
                  (SELECT count(*) FROM aos_physical_capacity_occupation_private.prepared_shared_risk_description));
                IF before_counts IS DISTINCT FROM after_counts THEN RAISE EXCEPTION 'LEGACY_PREPARATION_MUTATED'; END IF;
                RETURN result||jsonb_build_object('legacyBefore',before_counts,'legacyAfter',after_counts);
              END $proxy$""")
            signature='public.test_owned_versioned_origin(bytea,jsonb,uuid,text,text,uuid,text,text,uuid,jsonb,text)'
            admin.execute('ALTER FUNCTION '+signature+' OWNER TO '+OWNER)
            admin.execute('REVOKE ALL ON FUNCTION '+signature+' FROM PUBLIC')
            admin.execute('GRANT EXECUTE ON FUNCTION '+signature+' TO aos_runtime')
    @contextmanager
    def native_factory(scope):
        install_before_snapshot()
        with psycopg.connect(**params, row_factory=dict_row) as conn:
            conn.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
            conn.execute("SET LOCAL TimeZone='UTC'")
            apply_transaction_scope(conn, scope)
            yield conn
    def prefix(conn):
        conn.execute('SELECT public.prepare_capacity_occupation_account_guard(%s,%s::jsonb)',
            (_consumption_packet(command), Jsonb(exact.model_dump(mode='json', by_alias=True))))
    def probe(conn, body, target, judge):
        nonlocal command
        # Independent current consumption identity is acquired once at ingress.
        # The existing command must still authenticate; no mid-call refresh.
        from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityConsumptionCommand
        from datetime import datetime, timezone
        import hashlib
        prior_packet = json.loads(_consumption_packet(command))
        auth_before = prior_packet['authentication']
        ingress_now = datetime.now(timezone.utc)
        fresh = ProviderCapacityConsumptionCommand(schema_version=command.schema_version,
            tenant=command.tenant, source_ref=command.source_ref,
            bearer_token=https_signer[0](auth_before['consumerSubject']))
        current_packet = json.loads(_consumption_packet(fresh))
        assert {k:v for k,v in current_packet.items() if k != 'authentication'} == {k:v for k,v in prior_packet.items() if k != 'authentication'}
        assert {k:v for k,v in current_packet['authentication'].items() if k != 'authenticationExpiresAt'} == {k:v for k,v in auth_before.items() if k != 'authenticationExpiresAt'}
        deadline = datetime.fromisoformat(current_packet['authentication']['authenticationExpiresAt'].replace('Z','+00:00'))
        assert 115 < (deadline-ingress_now).total_seconds() <= 120
        command = fresh
        Path(__file__).with_name('fresh-ingress-authentication.json').open('x').write(json.dumps({
            'same_verified_identity':True,'original_token_authenticated_before_new_ingress':True,
            'original_auth_deadline':auth_before['authenticationExpiresAt'],
            'new_ingress_at':ingress_now.isoformat(),'fresh_120_second_auth_deadline':deadline.isoformat(),
            'old_packet_sha256':hashlib.sha256(json.dumps(prior_packet,sort_keys=True).encode()).hexdigest(),
            'fresh_packet_sha256':hashlib.sha256(_consumption_packet(command)).hexdigest(),
            'source_and_approval_unchanged':True,'mid_call_authentication_refresh':False,
            'execution_allowed':False},indent=2)+'\n')
        from aos_api import aip_shared_parent_atomic_admission as admission
        from aos_api.aip_physical_capacity_occupation_authority import OWNER
        from aos_api.aip_model_runtime_store import canonical_hash
        from uuid import UUID
        shared=copy.deepcopy(body)
        shared['schemaVersion']='aos.model-eval-target-judge-shared-risk-manifest/v3'
        shared['executionId']=str(uuid4())
        for case in shared['cases']:
            for purpose in ('target','judge'):
                case[purpose]['sourceRef']=exact.model_dump(mode='json',by_alias=True)
                case[purpose]['physicalAccountRef']=source.account_candidate_ref.model_dump(mode='json',by_alias=True)
                del case[purpose]['allocationUpperBoundMinor'];del case[purpose]['budgetAllocationRef']
        from shared_identity_certificate_fixture import keys_for_manifest
        keys=keys_for_manifest(shared)
        params_origin=(_consumption_packet(command),Jsonb(exact.model_dump(mode='json',by_alias=True)),
            UUID(target.parent_limit.parent_hold_ref.resource_id),target.request_id,target.request_hash,
            UUID(judge.parent_limit.parent_hold_ref.resource_id),judge.request_id,judge.request_hash,
            UUID(shared['executionId']))
        def build(value=shared, hash_override=None):
            return conn.execute('SELECT public.test_owned_versioned_origin(%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s) AS doc',
                (*params_origin,Jsonb(value),canonical_hash(value) if hash_override is None else hash_override)).fetchone()['doc']
        caller_origin=conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        doc=build()
        assert doc['immutable']['callerXid']==caller_origin['xid'] and doc['immutable']['callerPid']==caller_origin['pid']
        assert doc['contentHash']=='sha256:'+canonical_hash(doc['immutable'])
        assert doc['immutable']['originalRiskHash']=='sha256:'+canonical_hash(doc['immutable']['originalRisk'])
        assert doc['immutable']['manifest']==shared and doc['immutable']['state']=='awaiting_full_admission'
        assert doc['executionAllowed'] is False and doc['legacyBefore']==doc['legacyAfter']
        import base64
        from datetime import datetime,timezone,timedelta
        from shared_identity_certificate_fixture import ROOT_KEY,public
        root=root_state['root'];now=datetime.now(timezone.utc)
        end=min(datetime.fromisoformat(shared['judgeRequest']['expiresAt']),datetime.fromisoformat(root['validUntil'].replace('Z','+00:00')))
        certificates=[]
        encode=lambda x:json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        for case in shared['cases']:
            for purpose in ('target','judge'):
                app=shared['judgeRequest']['targetApplication' if purpose=='target' else 'judgeGovernanceApplication']
                claim=dict(schemaVersion='aos.model-eval-shared-parent-certificate-signing-input/v3',tenant=shared['tenant'],executionId=shared['executionId'],manifestHash=doc['immutable']['manifestHash'],requestHash=app['requestHash'] if purpose=='target' else shared['judgeRequestHash'],caseId=case['caseId'],purpose=purpose,candidateRef=app['request']['targetRef'],leg=case[purpose],issuerId=root['issuerId'],issuerKeyId=root['issuerKeyId'],publicKeyBase64=base64.b64encode(public(keys[purpose])).decode(),validFrom=(now-timedelta(seconds=1)).isoformat(),validUntil=end.isoformat(),descriptionHash=doc['contentHash'],originalRiskHash=doc['immutable']['originalRiskHash'],callerXid=caller_origin['xid'],callerPid=caller_origin['pid'])
                message=b'AOS-MODEL-EVAL-SHARED-PARENT-CERTIFICATE-SIGNING-INPUT-v3\n'+encode(claim)
                certificates.append(dict(schemaVersion='aos.model-eval-shared-parent-signed-certificate-envelope/v3',certificate=claim,signatureBase64=base64.b64encode(ROOT_KEY.sign(message)).decode()))
        call_started=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'];assert call_started<end
        pending=conn.execute('SELECT public.test_owned_pending_origin(%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s) AS result',(*params_origin,Jsonb(shared),canonical_hash(shared),encode(certificates))).fetchone()['result']
        assert pending['persisted'] is True and pending['executionAllowed'] is False
        assert pending['immutable']['origin']=={k:v for k,v in doc.items() if k not in ('legacyBefore','legacyAfter')}
        assert pending['contentHash']=='sha256:'+canonical_hash(pending['immutable'])
        assert pending['immutable']['certificateSetHash']=='sha256:'+__import__('hashlib').sha256(encode(certificates)).hexdigest()
        lookup_params=(*params_origin,Jsonb(shared),canonical_hash(shared),encode(certificates),pending['contentHash'])
        stage_sql='SELECT public.test_owned_end_authority('+','.join(['%s']*13)+') AS result'
        material=conn.execute(stage_sql,lookup_params).fetchone()['result']
        assert material['contentHash']=='sha256:'+canonical_hash(material['immutable'])
        assert material['immutable']['sourcePacketHash']=='sha256:'+__import__('hashlib').sha256(params_origin[0]).hexdigest()
        assert material['immutable']['pendingOriginHash']==pending['contentHash']
        assert material['executionAllowed'] is False
        risk_args=(params_origin[-1],pending['contentHash'],caller_origin['xid'],caller_origin['pid'])
        risk_sql='SELECT public.test_owned_complete_risk(%s,%s,%s::xid8,%s) AS result'
        risk_ledger=conn.execute(risk_sql,risk_args).fetchone()['result']
        assert risk_ledger['contentHash']=='sha256:'+canonical_hash(risk_ledger['immutable'])
        assert risk_ledger['immutable']['originalRisk']==doc['immutable']['originalRisk']
        assert risk_ledger['immutable']['originalRiskHash']==doc['immutable']['originalRiskHash']
        assert risk_ledger['immutable']['authorityMaterialHash']==material['contentHash']
        assert len(risk_ledger['immutable']['originalRisk']['legs'])==4
        assert len(risk_ledger['immutable']['originalRisk']['parentRisks'])==2
        risk_negatives=[] # Independently accepted in risk1739r2 and phase1741r1; not repeated in this whole traversal.
        Path(__file__).with_name('parent-risk-stage-proof.json').open('x').write(json.dumps({'risk':risk_ledger,'original_origin':doc,'pending':pending,'retained_authority':material,'root':root,'certificates':certificates,'caller':caller_origin,'negative_cases':risk_negatives,'negative_cases_separately_verified':['parent-risk-native-1739-r2/independent-readback.json','certificate-phase-native-1741-r1/independent-readback.json'],'formal_root_provenance':False,'full_admission':False},ensure_ascii=False,indent=2)+'\n')
        retained=None # Dedicated retained read already accepted; full internal original reads unchanged.
        faults=[] # Existing retention negatives already accepted independently at1730; do not stack duplicate native work.
        legacy_id=uuid4()
        legacy=conn.execute('SELECT public.prepare_capacity_parent_debit(%s,%s::jsonb,%s,%s,%s,%s,%s) AS result',(*params_origin[:5],legacy_id,1)).fetchone()['result']
        assert legacy['executionAllowed'] is False
        initial=conn.execute('SELECT public.test_owned_initial_obligation(%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s) AS result',lookup_params).fetchone()['result']
        assert initial['executionAllowed'] is False
        assert initial['immutable']['pendingOriginHash']==pending['contentHash']
        assert initial['immutable']['caseId']==shared['cases'][0]['caseId']
        assert initial['contentHash']=='sha256:'+canonical_hash(initial['immutable'])
        from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
        from aos_api.ecommerce_content_pre_review_pack import build_content_pre_review_eval_packs
        from aos_api.ecommerce_content_pre_review_eval import GRAPH_ID,build_content_pre_review_graph
        from aos_api.aip_eval_contracts import AssetRevisionRef,AssetType
        from aos_api.aip_logic_graph_models import compute_logic_graph_hash
        ref=target.request.suite_ref
        suite_row=conn.execute('SELECT * FROM aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s',('org-org','dev-project',ref.asset_id,ref.revision)).fetchone()
        suite=AipEvalPackRegistry._suite_from_row(suite_row)
        suite_raw=encode(suite.model_dump(mode='json',by_alias=True,exclude={'content_hash'}))
        graph=AssetRevisionRef(assetType=AssetType.LOGIC_GRAPH,assetId=GRAPH_ID,revision='1',contentHash=compute_logic_graph_hash(build_content_pre_review_graph()))
        _,pack=build_content_pre_review_eval_packs(graph)
        input_ref=suite.cases[0].input_artifact
        input_raw=encode(pack.artifacts[(input_ref.artifact_id,input_ref.revision)])
        intent_args=(*lookup_params,initial['contentHash'],suite_raw,input_raw,uuid4(),uuid4())
        sql='SELECT public.test_owned_initial_call_authority('+','.join(['%s']*18)+') AS result'
        call_material=conn.execute(sql,intent_args).fetchone()['result']
        call_read_args=(params_origin[-1],call_material['contentHash'],caller_origin['xid'],caller_origin['pid'])
        def intent_write_counts():
            return conn.execute("SELECT relname,n_tup_ins,n_tup_upd,n_tup_del FROM pg_stat_xact_user_tables WHERE schemaname='aos_shared_parent_physical_private' AND relname IN ('target_intent','judge_dependency') ORDER BY relname").fetchall()
        # The complete Receipt binder itself invokes unchanged FINAL_CALL. No
        # separate duplicate demonstration is stacked into the Source window.
        call_read_sql='SELECT public.test_owned_initial_window(%s,%s,%s::xid8,%s) AS result'
        window_obligation=conn.execute(call_read_sql,call_read_args).fetchone()['result']
        intents=window_obligation['initialCall']
        assert window_obligation['contentHash']=='sha256:'+canonical_hash(window_obligation['immutable'])
        assert window_obligation['immutable']['unresolvedRequests']==2
        assert window_obligation['immutable']['unresolvedTokenUpperBound']==initial['immutable']['tokenUpperBound']+legacy['physicalTokens']
        assert window_obligation['immutable']['sourceTokenLimit']['mode']=='inflight_upper_bound'
        assert window_obligation['immutable']['windowExpiryReleasesRisk'] is False
        assert intents['executionAllowed'] is False
        assert intents['targetIntentHash']=='sha256:'+canonical_hash(intents['targetIntent'])
        assert intents['judgeDependencyHash']=='sha256:'+canonical_hash(intents['judgeDependency'])
        assert intents['targetIntent']['inputValue']==json.loads(input_raw)
        assert intents['judgeDependency']['targetIntentHash']==intents['targetIntentHash']
        assert intents['judgeDependency']['inputDependency']['state']=='awaiting_target_result'
        assert intents['targetIntent']['obligationHash']==initial['contentHash']
        live_args=(params_origin[-1],window_obligation['contentHash'],caller_origin['xid'],caller_origin['pid'])
        live_sql='SELECT public.test_owned_live_physical(%s,%s,%s::xid8,%s) AS result'
        receipt=conn.execute('SELECT public.test_owned_receipt_v2(%s,%s,%s::xid8,%s) AS result',call_read_args).fetchone()['result']
        assert receipt['executionAllowed'] is False and receipt['persisted'] is True
        sealed=receipt['immutable'];assert len(sealed['nodes'])==8
        assert sealed['schemaVersion']=='aos.shared-parent-complete-receipt-preparation/v2'
        assert receipt['contentHash']=='sha256:'+canonical_hash(sealed)
        live={'facts':sealed['physicalFacts'],'contentHash':sealed['physicalFactsHash']}
        assert live['facts']['unresolvedRequests']==2 and live['facts']['unresolvedTokenUpperBound']==20000
        assert len(live['facts']['unresolvedMembers'])==2
        physical_args=(params_origin[-1],receipt['contentHash'],caller_origin['xid'],caller_origin['pid'])
        counts_before=intent_write_counts()
        physical=conn.execute('SELECT public.test_owned_final_physical(%s,%s,%s::xid8,%s) AS result',physical_args).fetchone()['result']
        assert physical['physicalComparisonMatched'] is True and physical['executionAllowed'] is False
        assert intent_write_counts()==counts_before
        # Exercise PG_CATCH after hook installation, preserving the original caller.
        import psycopg as cleanup_pg
        try:
            with conn.transaction():
                conn.execute('SELECT public.test_owned_complete_end_facts(%s,%s,%s::xid8,%s)',(physical_args[0],'sha256:'+'0'*64,*physical_args[2:]))
        except cleanup_pg.Error as cleanup_error:
            assert cleanup_error.sqlstate=='23514'
            assert 'SHARED_ADMISSION_COMPLETE_END_RECEIPT_REQUIRED' in str(cleanup_error)
        else:
            raise AssertionError('incorrect receipt hash admitted')
        conn.execute("SET LOCAL TimeZone='UTC'")
        restored=conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        assert restored==caller_origin
        Path(__file__).with_name('cleanup-proof.json').open('x').write(json.dumps(dict(internal_error='SHARED_ADMISSION_COMPLETE_END_RECEIPT_REQUIRED',utility_after_error=True,same_caller=True,caller=restored,full_native_ending=False),indent=2)+'\n')
        end_facts=conn.execute('SELECT public.test_owned_complete_end_facts(%s,%s,%s::xid8,%s) AS result',physical_args).fetchone()['result']
        assert end_facts['nodes']==sealed['nodes'] and len(end_facts['nodes'])==8
        assert end_facts['receiptHash']==receipt['contentHash']
        assert end_facts['sourcePacketHash']==sealed['sourcePacketHash']
        assert end_facts['originalRiskHash']==sealed['originalRiskHash']
        assert end_facts['physicalComparison']==physical
        assert end_facts['executionAllowed'] is False and end_facts['nativeEndRequired'] is True
        assert end_facts['durableDeadlineEstablished'] is False
        import __main__ as observation_state
        import hashlib as catalog_hash
        observed = sorted(observation_state.observed_oids)
        frozen = conn.execute("""SELECT p.oid,p.oid::regprocedure::text AS signature,
            p.xmin::text AS creation_xid,p.proowner::regrole::text AS owner,
            p.prosecdef,p.proconfig,p.proacl::text AS acl,l.lanname AS language,
            p.provolatile,p.probin,p.prosrc FROM pg_proc p
            JOIN pg_language l ON l.oid=p.prolang WHERE p.oid=ANY(%s::oid[]) ORDER BY p.oid""",(observed,)).fetchall()
        assert len(frozen)==len(observed)
        for function in frozen:
            function['source_sha256']=catalog_hash.sha256(function.pop('prosrc').encode()).hexdigest()
        Path(__file__).with_name('in-transaction-functions.json').open('x').write(json.dumps(dict(caller=caller_origin,functions=frozen,observed=observed),indent=2)+'\n')

        assert intent_write_counts()==counts_before
        Path(__file__).with_name('complete-end-facts-positive-proof.json').open('x').write(json.dumps(dict(end_facts=end_facts,receipt=receipt,caller=caller_origin,original_signed_source=True,independent_parents=2,real_certificate_legs=4,formal_root_provenance=False,nodes=8,no_intent_writes=True,full_admission=False,execution_allowed=False),indent=2,default=str)+'\n')
        Path(__file__).with_name('receipt-v2-positive-proof.json').open('x').write(json.dumps(dict(receipt=receipt,physical=physical,caller=caller_origin,original_signed_source=True,independent_parents=2,real_certificate_legs=4,formal_root_provenance=False,nodes=8,full_admission=False,execution_allowed=False),indent=2,default=str)+'\n')
        late_legacy=conn.execute('SELECT public.prepare_capacity_parent_debit(%s,%s::jsonb,%s,%s,%s,%s,%s) AS result',(*params_origin[:5],uuid4(),1)).fetchone()['result']
        totals=conn.execute('SELECT public.test_owned_live_union(%s) AS result',(params_origin[-1],)).fetchone()['result']
        assert late_legacy['physicalRequests']==2 and late_legacy['physicalTokens']==20000
        assert totals=={'requests':3,'tokens':30000}
        assert totals['requests']>2 and totals['tokens']>window_obligation['immutable']['sourceTokenLimit']['maxTokens']
        with pytest.raises(psycopg.errors.CheckViolation,match='SHARED_ADMISSION_FINAL_PHYSICAL_CHANGED'):
            with conn.transaction():conn.execute('SELECT public.test_owned_final_physical(%s,%s,%s::xid8,%s) AS result',physical_args).fetchone()
        Path(__file__).with_name('receipt-v2-late-writer-proof.json').open('x').write(json.dumps(dict(receiptHash=receipt['contentHash'],late_legacy=late_legacy,actual_union=totals,final_physical_changed_rejected=True,execution_allowed=False),indent=2,default=str)+'\n')
        live_overload_rejected=True
        call_faults=[]
        bad=list(intent_args);bad[15]=input_raw+b' '
        with pytest.raises(psycopg.errors.CheckViolation):
            with conn.transaction():conn.execute(sql,bad)
        call_faults.append('raw_input_tamper_rejected')
        with pytest.raises(psycopg.errors.CheckViolation,match='SHARED_ADMISSION_WINDOW_NATIVE_MATERIAL_REQUIRED'):
            with conn.transaction():conn.execute(call_read_sql,(call_read_args[0],'sha256:'+'0'*64,*call_read_args[2:]))
        call_faults.append('wrong_material_hash_rejected')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():conn.execute('SELECT * FROM aos_shared_parent_physical_private.initial_call_authority')
        call_faults.append('runtime_table_read_rejected')
        root_state['proof']={'result':pending,'root':root,'certificates':certificates,'negative_cases':faults,'real_signatures':True,'formal_root_provenance':False,'call_started':call_started.isoformat(),'certificate_end':end.isoformat(),'postwait_native_revalidation':True,'retained_authority':material,'retained_readback':retained,'initial_call_material':call_material,'initial_call_readback':intents,'initial_call_negatives':call_faults,'initial_obligation':initial,'initial_window_obligation':window_obligation,'legacy_prepared_debit':legacy,'late_legacy_debit':late_legacy,'actual_union_after_late_writer':totals,'window_snapshot_not_current':True,'live_physical_facts':live,'live_overload_rejected':live_overload_rejected}
        failures=[] # Previous original-fact negatives accepted at1720; no duplicate rerun.
        proofs.append(dict(certificate_proof=root_state['proof'],origin=doc,caller=caller_origin,negative_cases=failures,
            original_signed_source_and_independent_parents=True,legacy_preparation_unchanged=True,
            execution_allowed=False,full_admission_pass=False))
        return proofs[-1]
    def finish(conn):
        xid=conn.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
        with pytest.raises(psycopg.errors.CheckViolation,match='SHARED_ADMISSION_COMPLETE_END_CHANNEL_REQUIRED'):
            conn.commit()
        assert conn.info.transaction_status==psycopg.pq.TransactionStatus.IDLE
        proofs[0]['rollback_xid']=xid;proofs[0]['actual_commit_rejected']=True
        with Path(__file__).with_name('component-native-proof.json').open('x') as stream:
            json.dump(proofs[0],stream,ensure_ascii=False,indent=2)
        return dict(xid=xid,actual_commit_rejected=True,execution_allowed=False)
    trial_path = tmp_path / 'shared-parent-native-source'
    trial_path.mkdir()
    test_exact_signed_rule_new_original_suite(caller, issuer_factory, https_signer,
        guard_issuer_factory, guard_consumer_factory, trial_path, source_provider=provider,
        whole_caller_factory=native_factory, source_prefix=prefix, source_probe=probe,
        source_finish=finish, source_native_only=True)
    assert len(proofs) == 1
    with Path(__file__).with_name('native-origin-proof.json').open('x') as stream:
        json.dump(proofs[0], stream, ensure_ascii=False, indent=2)
