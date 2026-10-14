from pathlib import Path
import ast,hashlib,json,subprocess
Q=Path(__file__).resolve().parent;R=Q.parents[1];p=R/'services/aos-api/aos_api/routers/ecommerce_workshop.py';s=p.read_text();old=subprocess.check_output(['git','show','HEAD:services/aos-api/aos_api/routers/ecommerce_workshop.py'],cwd=R,text=True)
def matrix(src):
 out=[]
 for n in ast.parse(src).body:
  if not isinstance(n,ast.FunctionDef):continue
  for d in n.decorator_list:
   if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and isinstance(d.func.value,ast.Name) and d.func.value.id=='router':out.append([d.func.attr.upper(),ast.literal_eval(d.args[0]),[ast.unparse(a.annotation) for a in n.args.args if a.annotation and 'CatalogDependency' in ast.unparse(a.annotation)]])
 return out
before,after=matrix(old),matrix(s);delta=[dict(before=a,after=b) for a,b in zip(before,after) if a!=b]
assert len(before)==len(after) and delta==[dict(before=['GET','/views/creator-growth/workflow/drafts',['CatalogDependency']],after=['GET','/views/creator-growth/workflow/drafts',['ReadCatalogDependency']])]
(Q/'route-matrix-current-r1.json').write_text(json.dumps(dict(before=before,after=after,changes=delta),separators=(',',':')))
parts=['ACTUAL routing quality candidate only. Current HEAD5a/Authority2030. CodeRootRED16fail41pass->129jointPASS. No original service switch, API25389f005/Web783466c; UI separateTask source269PASS+tsc, not browseraccepted. Standaloneboundedsource unchanged baae1ede/native/codePASS. Complete route matrix shows exactlyoneGET, allotherGETPOST unchanged.']
paths=[Q/'routing-implementation-plan.md',Q/'plan-review-consumption-r1.json',R/'services/aos-api/tests/test_ecommerce_workshop_read_http.py',Q/'green-r1.log',Q/'route-matrix-current-r1.json',R/'.evidence/qyh-creator-workflow-bounded-reader-20261014/code-review-consumption-r2.json',R/'.evidence/qyh-creator-workflow-bounded-reader-20261014/native-r1-result.json']
for p in paths:parts.append('FILE '+str(p.relative_to(R))+' SHA256 '+hashlib.sha256(p.read_bytes()).hexdigest()+'\n'+p.read_text())
for n in ast.parse(s).body:
 if isinstance(n,ast.FunctionDef) and n.name in ['list_creator_internal_workflows','get_creator_workflow_readonly','_require_creator_growth_installation','_map_creator_internal_workflow_error','_invoke','_reject_query_parameters']:
  parts.append('ACTUAL completeFUNC '+n.name+'\n'+ast.get_source_segment(s,n))
files=['services/aos-api/aos_api/routers/ecommerce_workshop.py','services/aos-api/tests/test_ecommerce_workshop_read_http.py','services/aos-api/aos_api/ecommerce_creator_internal_workflow_readonly.py','services/aos-api/tests/test_ecommerce_creator_internal_workflow_readonly.py'];hashes={f:hashlib.sha256((R/f).read_bytes()).hexdigest() for f in files};parts.append('CURRENT full source hashes '+json.dumps(hashes))
material='\n'.join(parts);p=Q/'code-review-package-r1.txt';p.write_text(material);rel=str(p.relative_to(R))
r={'schema':'aos-material-review/v1','request_id':Q.name+'-code-r1','task_id':Q.name,'owner':'codex-01a13484-f019-7d82-94ce-812396db9124','kind':'quality','baseline':{'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'authority_revision':'AOS-002030','files':{rel:hashlib.sha256(p.read_bytes()).hexdigest()}},'claims':['实际仅草稿listGET接线：原query/安装scope及权限在先，typed未知准入503，只读marker用有界reader，无marker保留旧list及错误映射。','完整HTTP矩阵仅一GET变化，其他GET和POST门未改；129项验证和同源有界reader独立证据支持代码候选，不宣称原客户或整Goal完成。'],'materials':{rel:material}}
(Q/'code-review-request-r1.json').write_text(json.dumps(r,ensure_ascii=False));print({'bytes':len(json.dumps(r['materials']).encode())})
