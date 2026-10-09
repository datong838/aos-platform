from pathlib import Path
import sys,json,copy,hashlib,ast,subprocess
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'services/aos-api'))
import psycopg
def deny(*a,**k):raise AssertionError('database connections forbidden in pure provenance audit')
psycopg.connect=deny
from aos_api.aip_model_eval_execution_contracts import ModelEvalTargetJudgeSharedRiskManifest as V3,ModelEvalExecutionManifest as V1,ModelEvalTargetJudgeExecutionManifest as V2
from aos_api.aip_model_runtime_store import canonical_hash
p=json.loads((B/'shared-parent-risk-binding-native-1670-r2/native-risk-binding-proof.json').read_text()); original=V3.model_validate(p['manifest']).model_dump(mode='json',by_alias=True)
def projection(m):
 return {'sourceRefs':[[c[k]['sourceRef'] for k in ('target','judge')] for c in m['cases']], 'target':m['judgeRequest']['targetApplication']['request'],'judge':m['judgeRequest'],'targetParent':m['targetParentBudget'],'judgeParent':m['judgeParentBudget']}
base=projection(original);changes=[]
for field in ('identityId','intentRef','jointReceiptRef'):
 q=copy.deepcopy(original)
 if field=='identityId':q['cases'][0]['target'][field]='different-descriptive-identity'
 else:q['cases'][0]['target'][field]['resourceId']+='-different-description'
 parsed=V3.model_validate(q).model_dump(mode='json',by_alias=True)
 assert canonical_hash(parsed)!=canonical_hash(original) and projection(parsed)==base
 changes.append({'field':field,'v3_description_valid':True,'whole_manifest_hash_changed':True,'native_original_risk_inputs_unchanged':True,'native_modified_plan_executed':False})
for parser in (V1,V2):
 try:parser.model_validate(original)
 except ValueError:pass
 else:raise AssertionError('old manifest parser accepted v3')
path=R/'services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py';source=path.read_text();tree=ast.parse(source);node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='occupation_plan_risk_statements');sql_source=ast.get_source_segment(source,node)
assert 'manifestHash' not in sql_source and 'identityId' not in sql_source and 'jointReceiptRef' not in sql_source and 'intentRef' not in sql_source
out={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'authority_revision':'AOS-001671','original_full_manifest_hash':canonical_hash(original),'source_proof_sha256':hashlib.sha256((B/'shared-parent-risk-binding-native-1670-r2/native-risk-binding-proof.json').read_bytes()).hexdigest(),'risk_sql_sha256':hashlib.sha256(sql_source.encode()).hexdigest(),'pure_changes':changes,'old_parsers_reject_v3':True,'database_connections_forbidden':True,'finding':'RED_FULL_V3_PERSISTENT_PROVENANCE_NOT_BOUND','native_modified_plan_executed':False,'execution_allowed':False,'full_task_delivered':False}
(B/'shared-risk-persistent-provenance-audit-1671.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
