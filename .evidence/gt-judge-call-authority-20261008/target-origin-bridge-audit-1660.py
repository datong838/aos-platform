"""Current original v2 Judge versus legacy signed Target source, read only."""
from pathlib import Path
import json,hashlib,sys,subprocess
import psycopg
from psycopg.rows import dict_row
from pydantic import ValidationError
B=Path(__file__).resolve().parent;R=B.parents[1]
sys.path.insert(0,str(R/'services/aos-api'))
from aos_api.aip_model_eval_execution_contracts import ModelEvalExecutionManifest,ModelEvalTargetJudgeExecutionManifest
name='judge-expected-bytes-green-1659-r1'
proof=json.loads((B/name/(name+'-whole-plan-proof.json')).read_text())
result=json.loads((B/(name+'-result.json')).read_text());assert result['pytest_exit']==0
body=proof['manifest'];new=ModelEvalTargetJudgeExecutionManifest.model_validate(body)
try:
 ModelEvalExecutionManifest.model_validate(body)
 raise AssertionError('legacy unexpectedly accepts original new-purpose body')
except ValidationError as e:
 errors=[{'location':list(x['loc']),'type':x['type']} for x in e.errors()]
assert any(x['location']==['schemaVersion'] and x['type']=='value_error' for x in errors)
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=result['database'],passfile=lab['passfile'],options='-c default_transaction_read_only=on',row_factory=dict_row) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 counts={}
 for table in ('aos_model_eval_execution_private.manifest','aos_model_eval_execution_private.case_result','aos_model_eval_issuer_private.executor_certificate','aos_model_eval_issuer_private.target_result_origin'):
  exists=c.execute('SELECT to_regclass(%s)::text AS name',(table,)).fetchone()['name']
  counts[table]=None if exists is None else c.execute('SELECT count(*) AS n FROM '+table).fetchone()['n']
 assert counts['aos_model_eval_execution_private.case_result']==0
 function=c.execute("SELECT to_regprocedure('public.read_model_target_result_facts(text,text,text)')::text AS name").fetchone()['name']
 assert c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']=='on';c.rollback()
paths=['services/aos-api/aos_api/'+x+'.py' for x in ('aip_model_eval_execution_owner','aip_model_eval_execution_reader','aip_model_eval_execution_authority','aip_model_eval_execution_contracts')]
out={'authority_revision':'AOS-001660','head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'database':result['database'],'current_original_whole_schema':new.schema_version,'original_cases':len(new.cases),'legacy_exact_rejection':errors,'read_only_inventory':counts,'runtime_target_fact_function':function,'file_hashes':{p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in paths},'result':'ORIGINAL_V2_JUDGE_NOT_WIRED_TO_LEGACY_TARGET_PROOF','execution_allowed':False,'full_task_delivered':False,'limitations':'Legacy signed COMMITTED Target reader exists in code but uses legacy Manifest/ModelEvalBudgetReservation for both legs. Current approved v2 uses independent ModelJudgeBudgetReservation and original Judge request/rule; no Target row in this owned DB. No proof/input coercion, installation or fabricated Target output performed.'}
with (B/'target-origin-bridge-result-1660.json').open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps({'result':out['result'],'legacy_error_count':len(errors),'inventory':counts,'runtime_target_fact_function':function,'execution_allowed':False}))
