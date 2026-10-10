from pathlib import Path
from uuid import uuid4,UUID
import json,hashlib
import psycopg,pytest
from psycopg.types.json import Jsonb
S='aos_physical_capacity_occupation_private'

def install_combined(admin,B):
 from aos_api.aip_physical_capacity_occupation_authority import OWNER,occupation_judge_intent_statements,occupation_prepared_call_statements,occupation_target_call_statements,occupation_target_ledger_statements
 for builder in (occupation_judge_intent_statements,occupation_prepared_call_statements,occupation_target_call_statements,occupation_target_ledger_statements):
  for statement in builder():admin.execute(statement)
 sql=f'''CREATE FUNCTION public.test_combined_preparation_readback(p_call uuid,p_judge uuid) RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $read$
 SELECT jsonb_build_object('root',(SELECT to_jsonb(r) FROM {S}.call_occupation r WHERE call_id=p_call),
 'event',(SELECT to_jsonb(e) FROM {S}.call_occupation_event e WHERE call_id=p_call AND event_seq=1),
 'judge',(SELECT to_jsonb(j) FROM {S}.prepared_judge_intent j WHERE intent_id=p_judge),
 'inflight',(SELECT count(*) FROM {S}.call_occupation WHERE counts_as_inflight),
 'prepared_requests',(SELECT count(*) FROM {S}.prepared_parent_debit),
 'prepared_tokens',(SELECT coalesce(sum(token_units),0) FROM {S}.prepared_parent_debit)) $read$'''
 admin.execute(sql);admin.execute('ALTER FUNCTION public.test_combined_preparation_readback(uuid,uuid) OWNER TO '+OWNER);admin.execute('REVOKE ALL ON FUNCTION public.test_combined_preparation_readback(uuid,uuid) FROM PUBLIC');admin.execute('GRANT EXECUTE ON FUNCTION public.test_combined_preparation_readback(uuid,uuid) TO aos_runtime')
 gate_sql=f"CREATE FUNCTION public.test_combined_early_constraint_group() RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $gate$ BEGIN SET CONSTRAINTS {S}.require_joint_finalization IMMEDIATE; END $gate$"
 admin.execute(gate_sql);admin.execute('ALTER FUNCTION public.test_combined_early_constraint_group() OWNER TO '+OWNER);admin.execute('REVOKE ALL ON FUNCTION public.test_combined_early_constraint_group() FROM PUBLIC');admin.execute('GRANT EXECUTE ON FUNCTION public.test_combined_early_constraint_group() TO aos_runtime')
 rows=admin.execute("""SELECT n.nspname||'.'||r.relname AS relation,pg_get_userbyid(r.relowner) AS owner,r.relrowsecurity,r.relforcerowsecurity,has_table_privilege('aos_runtime',r.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE') AS runtime_dml FROM pg_class r JOIN pg_namespace n ON n.oid=r.relnamespace WHERE n.nspname=%s AND r.relname=ANY(%s) ORDER BY r.relname""",(S,['prepared_judge_intent','prepared_call_occupation','call_occupation','call_occupation_event'])).fetchall();assert len(rows)==4 and all(x['owner']==OWNER and x['relrowsecurity'] and x['relforcerowsecurity'] and not x['runtime_dml'] for x in rows)
 guards=admin.execute("""SELECT n.nspname||'.'||r.relname AS relation,t.tgname,t.tgdeferrable,t.tginitdeferred,k.conname,encode(sha256(convert_to(p.prosrc,'UTF8')),'hex') AS body_hash FROM pg_trigger t JOIN pg_class r ON r.oid=t.tgrelid JOIN pg_namespace n ON n.oid=r.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_constraint k ON k.oid=t.tgconstraint WHERE n.nspname=%s AND p.proname='reject_unfinalized_parent_debit' ORDER BY relation,t.tgname""",(S,)).fetchall();assert len(guards)==7 and all(x['tgdeferrable'] and x['tginitdeferred'] for x in guards);assert sum(x['conname']=='require_joint_finalization' for x in guards)==2
 (B/'combined-installation.json').open('x').write(json.dumps(dict(tables=rows,guards=guards,readback_sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),test_only_readback=True,execution_allowed=False),indent=2)+'\n')

def verify_combined(conn,command,exact,target,judge,B,original_plan_id):
 from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
 from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
 from aos_api.ecommerce_content_pre_review_pack import build_content_pre_review_eval_packs
 from aos_api.ecommerce_content_pre_review_eval import GRAPH_ID,build_content_pre_review_graph
 from aos_api.aip_eval_contracts import AssetRevisionRef,AssetType
 from aos_api.aip_logic_graph_models import compute_logic_graph_hash
 raw=_consumption_packet(command);ref=Jsonb(exact.model_dump(mode='json',by_alias=True));tp=UUID(target.parent_limit.parent_hold_ref.resource_id);jp=UUID(judge.parent_limit.parent_hold_ref.resource_id);plan_id=UUID(str(original_plan_id))
 plan=conn.execute('SELECT public.prepare_capacity_plan_risk(%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s) AS fact',(raw,ref,tp,target.request_id,target.request_hash,jp,judge.request_id,judge.request_hash,plan_id)).fetchone()['fact'];assert not plan['executionAllowed'] and plan['planId']==str(original_plan_id)
 sr=plan['immutable']['originalFacts']['target']['application']['suiteRef'];row=conn.execute('SELECT * FROM public.aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s',('org-org','dev-project',sr['assetId'],int(sr['revision']))).fetchone();suite=AipEvalPackRegistry._suite_from_row(row);suite_raw=json.dumps(suite.model_dump(mode='json',by_alias=True,exclude={'content_hash'}),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
 original_target=AssetRevisionRef(assetType=AssetType.LOGIC_GRAPH,assetId=GRAPH_ID,revision='1',contentHash=compute_logic_graph_hash(build_content_pre_review_graph()));_,pack=build_content_pre_review_eval_packs(original_target);case=suite.cases[0];input_ref=case.input_artifact;input_raw=json.dumps(pack.artifacts[(input_ref.artifact_id,input_ref.revision)],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
 td,ti,call_id,ji,jd=[uuid4() for _ in range(5)]
 ta=(raw,ref,tp,target.request_id,target.request_hash,td,1,suite_raw,case.case_id,input_raw,ti)
 def intent():return conn.execute('SELECT public.prepare_capacity_execution_intent(%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s) AS fact',ta).fetchone()['fact']
 target_intent=intent();assert intent()==target_intent and target_intent['immutable']['inputHash']==input_ref.content_hash
 ca=(raw,ref,plan_id,ti,call_id)
 def occupation():return conn.execute('SELECT public.prepare_capacity_target_occupation(%s,%s::jsonb,%s,%s,%s) AS fact',ca).fetchone()['fact']
 ledger=occupation();assert occupation()==ledger and ledger['countsAsInflight'] is False and ledger['executionAllowed'] is False
 ja=(raw,ref,jp,judge.request_id,judge.request_hash,jd,1,case.case_id,ti,ji)
 def judge_intent():return conn.execute('SELECT public.prepare_capacity_judge_execution_intent(%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s) AS fact',ja).fetchone()['fact']
 pending=judge_intent();assert judge_intent()==pending and pending['state']=='awaiting_target_result' and pending['executionAllowed'] is False
 assert pending['immutable']['targetIntentHash']==target_intent['contentHash'];assert pending['immutable']['inputDependency']['state']=='awaiting_target_result'
 for value in (target_intent['immutable'],pending['immutable'],ledger['immutable']):assert (value['callerXid'],value['callerPid'])==(plan['immutable']['callerXid'],plan['immutable']['callerPid'])
 def read():return conn.execute('SELECT public.test_combined_preparation_readback(%s,%s) AS fact',(call_id,ji)).fetchone()['fact']
 stored=read();assert stored['root']['immutable']==ledger['immutable'] and stored['event']['immutable']==ledger['initialEvent'] and stored['judge']['immutable']==pending['immutable'];assert stored['inflight']==0 and stored['prepared_requests']==2
 denies=[]
 for table in ('prepared_judge_intent','prepared_call_occupation','call_occupation','call_occupation_event'):
  relation=S+'.'+table
  for op,sql in [('SELECT','SELECT * FROM '+relation),('INSERT','INSERT INTO '+relation+' DEFAULT VALUES'),('UPDATE',"UPDATE "+relation+" SET immutable='{}'::jsonb"),('DELETE','DELETE FROM '+relation),('TRUNCATE','TRUNCATE '+relation)]:
   with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc:
    with conn.transaction():conn.execute(sql)
   denies.append(dict(table=table,operation=op,sqlstate=exc.value.sqlstate))
 assert read()==stored
 # Direct runtime schema access stays denied; fixed trusted test helper exercises native name grouping.
 with pytest.raises(psycopg.errors.InsufficientPrivilege) as direct_exc:
  with conn.transaction():conn.execute('SET CONSTRAINTS '+S+'.require_joint_finalization IMMEDIATE')
 assert read()==stored
 with pytest.raises(psycopg.errors.CheckViolation,match='CAPACITY_PARENT_FINALIZE_REQUIRED') as exc:
  with conn.transaction():conn.execute('SELECT public.test_combined_early_constraint_group()')
 assert read()==stored
 out=dict(plan=plan,target_intent=target_intent,occupation=ledger,judge_intent=pending,stored=stored,dml_denials=denies,runtime_schema_constraint_denied=direct_exc.value.sqlstate,exact_name_group_rejected=exc.value.sqlstate,same_native_caller=True,all_four_successor_tables_installed=True,whole_case_manifest_still_required=True,actual_target_result_present=False,judge_input_materialized=False,actual_model_execution=False,execution_allowed=False)
 (B/'combined-preparation.json').open('x').write(json.dumps(out,indent=2)+'\n');return dict(caller_xid=plan['immutable']['callerXid'],caller_pid=plan['immutable']['callerPid'],case_id=case.case_id,prepared_requests=stored['prepared_requests'],prepared_tokens=stored['prepared_tokens'],successor_tables=4,dml_denials=len(denies),execution_allowed=False)
