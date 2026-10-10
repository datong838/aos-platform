from pathlib import Path
import ast,os,sys,json,hashlib,subprocess
import psycopg
from psycopg.rows import dict_row
R=Path.cwd();B=R/'.evidence/gt-shared-parent-native-certificate-prepare-20261010';N=B/'native-r22'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths=['services/aos-api/aos_api/aip_physical_capacity_occupation.py','services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py','services/aos-api/aos_api/aip_shared_parent_certificate_prepare.py','services/aos-api/aos_api/aip_shared_parent_executor_set_reader.py','services/aos-api/aos_api/aip_model_eval_execution_owner.py','services/aos-api/aos_api/aip_model_eval_judge_budget.py','services/aos-api/aos_api/aip_model_eval_budget_reservation.py','services/aos-api/aos_api/aip_budget_reservation_store.py']
plan=R/'.evidence/gt-shared-physical-atomic-contract-20261007/joint-implementation-plan.md';assert '所有实际相关legacy deferred' in plan.read_text()
proof=json.loads((N/'result-r22.json').read_text());assert proof['pytest_exit']==0
for p,h in proof['file_hashes'].items():assert sha(R/p)==h
calls={}
for p in paths:
 tree=ast.parse((R/p).read_text());functions=[]
 for node in ast.walk(tree):
  if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
  if not any(x in node.name for x in ('prepare','hold','reserve','revalidate','validate_original')):continue
  seq=[]
  for x in sorted((x for x in ast.walk(node) if isinstance(x,ast.Call)),key=lambda x:(x.lineno,x.col_offset)):
   name=ast.unparse(x.func)
   if name.endswith('.execute') and x.args and isinstance(x.args[0],ast.Constant) and isinstance(x.args[0].value,str):
    sql=' '.join(x.args[0].value.split());seq.append(dict(line=x.lineno,call=name,sql=sql))
   elif any(k in name for k in ('consume_capacity','require_cost','hold','prepare_model','read_shared','transaction','commit','rollback','prepare_shared')):seq.append(dict(line=x.lineno,call=name))
  if seq:functions.append(dict(function=node.name,line=node.lineno,end_line=node.end_lineno,calls=seq))
 calls[p]=functions
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=proof['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY')
 identity=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone();assert identity['cluster']==lab['cluster'] and identity['readonly']=='on'
 triggers=c.execute("""SELECT n.nspname AS schema,r.relname AS relation,t.tgname AS name,t.tgisinternal AS internal,t.tgdeferrable AS deferrable,t.tginitdeferred AS initially_deferred,t.tgenabled AS enabled,pg_get_triggerdef(t.oid) AS definition,p.oid::regprocedure::text AS function,pg_get_userbyid(p.proowner) AS owner,encode(sha256(convert_to(p.prosrc,'UTF8')),'hex') AS function_body_hash FROM pg_trigger t JOIN pg_class r ON r.oid=t.tgrelid JOIN pg_namespace n ON n.oid=r.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid WHERE t.tgdeferrable AND (n.nspname='public' OR n.nspname LIKE 'aos_%') ORDER BY 1,2,3""").fetchall()
 deny=c.execute("SELECT prosrc,pg_get_userbyid(proowner) AS owner FROM pg_proc WHERE oid='aos_physical_capacity_occupation_private.reject_unfinalized_parent_debit()'::regprocedure").fetchone();assert "BEGIN RAISE EXCEPTION 'CAPACITY_PARENT_FINALIZE_REQUIRED' USING ERRCODE='23514'; END" in deny['prosrc']
 relevant=[x for x in triggers if x['schema']=='aos_physical_capacity_occupation_private' and x['relation'] in ['prepared_parent_debit','prepared_execution_intent','prepared_plan_risk','prepared_shared_risk_description']]
 assert {x['relation'] for x in relevant}=={'prepared_parent_debit','prepared_plan_risk','prepared_shared_risk_description'}
 assert all(x['enabled']=='O' and 'reject_unfinalized_parent_debit' in x['function'] for x in relevant if not x['internal'])
 all_risk_triggers=c.execute("SELECT r.relname AS relation,t.tgname AS name,t.tgdeferrable AS deferrable,t.tginitdeferred AS initially_deferred,t.tgisinternal AS internal,pg_get_triggerdef(t.oid) AS definition FROM pg_trigger t JOIN pg_class r ON r.oid=t.tgrelid JOIN pg_namespace n ON n.oid=r.relnamespace WHERE n.nspname='aos_physical_capacity_occupation_private' ORDER BY 1,2").fetchall()
 constraints=c.execute("""SELECT n.nspname AS schema,r.relname AS relation,k.conname AS name,k.contype AS kind,k.condeferrable AS deferrable,k.condeferred AS initially_deferred,pg_get_constraintdef(k.oid) AS definition FROM pg_constraint k JOIN pg_class r ON r.oid=k.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace WHERE (n.nspname IN ('aos_physical_capacity_occupation_private','aos_model_eval_execution_private','aos_model_eval_issuer_private') OR (n.nspname='public' AND r.relname LIKE 'aip_model_eval_%')) ORDER BY 1,2,3""").fetchall()
 intent_fk=[x for x in constraints if x['relation']=='prepared_execution_intent' and x['kind']=='f'];assert any('prepared_parent_debit' in x['definition'] for x in intent_fk)
 out=dict(all_installed_risk_triggers=all_risk_triggers,intent_foreign_keys=intent_fk,intent_has_own_deferred_guard=False,intent_indirect_parent_guard_requires_exact_same_transaction_proof=True,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),authority='AOS-001683',identity=identity,input_hashes={p:sha(R/p) for p in paths},joint_plan_hash=sha(plan),static_call_inventory=calls,catalog_deferred_triggers=triggers,constraints=constraints,current_preparation_guards=relevant,unconditional_reject_owner=deny['owner'],unconditional_reject_body_hash=hashlib.sha256(deny['prosrc'].encode()).hexdigest(),application_catalog_count=sum(not x['internal'] for x in triggers),internal_catalog_count=sum(x['internal'] for x in triggers),actual_event_queue_proven=False,formal_root_provenance_verified=False,finalizer_implemented=False,execution_allowed=False,full_task_delivered=False)
 (B/'joint-finalizer-current-audit-1683.json').open('x').write(json.dumps(out,indent=2)+'\n')
 print(json.dumps(dict(database=identity['database'],readonly=True,application_catalog=out['application_catalog_count'],internal_catalog=out['internal_catalog_count'],preparation_guard_relations=sorted({x['relation'] for x in relevant}),actual_event_queue_proven=False,finalizer_implemented=False)))
