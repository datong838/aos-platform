from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
implementation=R/'.evidence/qyh-price-disposition-bounded-reader-20261015'
parts=['ROUTE CODE QUALITY ONLY. Candidate not deployed; reader separate independent quality r2 PASS consumed. Full Goal still ACTIVE, no operating/budget/source approval. Native synthetic fixture is not customer evidence. Historical unchanged migration test failure retained (w6_009 expected/current a0v_162); frozen selected cumulative267 passes, no all-suite claim.\n']
selected={
 'services/aos-api/aos_api/routers/ecommerce_workshop.py':{
    '_reject_query_parameters','_invoke','_require_price_governance_installation',
    'get_ecommerce_workshop_read_catalog','get_ecommerce_workshop_catalog',
    'get_ecommerce_workshop_price_disposition','get_price_disposition_readonly',
    'get_price_disposition_contribution_view'},
 'services/aos-api/tests/test_ecommerce_workshop_read_http.py':{
    'client_with_catalogs','RejectingCatalog','ReadReached','price_admission','disposition_probes',
    'test_read_dependency_only_reaches_explicit_audited_get_routes',
    'test_price_disposition_selects_only_admitted_reader','test_price_disposition_denied_before_business_read',
    'test_price_disposition_unknown_admission_fails_closed','test_price_disposition_failure_does_not_become_empty_success',
    'test_price_disposition_query_cannot_change_scope','test_price_disposition_full_http_serialization'}}
for relative,names in selected.items():
    text=(R/relative).read_text();lines=text.splitlines();tree=ast.parse(text)
    parts.append('\nFILE AST full selected functions with decorators '+relative+' fullfileSHA '+hashlib.sha256(text.encode()).hexdigest())
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names:
            start=min([node.lineno]+[d.lineno for d in node.decorator_list])-1
            parts.append('\n'+'\n'.join(lines[start:node.end_lineno]))
        elif isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name) and node.target.id in {
                'ReadCatalogDependency','CatalogDependency','PriceDispositionDependency','PriceDispositionReadonlyDependency'}:
            parts.append('\n'+'\n'.join(lines[node.lineno-1:node.end_lineno]))
    parts.append('\nEXACT FULL DIFF\n'+subprocess.check_output(['git','diff','--',relative],text=True))
reader=R/'services/aos-api/aos_api/ecommerce_price_disposition_readonly.py'
parts.append('\nFULL CANDIDATE READER SHA '+hashlib.sha256(reader.read_bytes()).hexdigest()+'\n'+reader.read_text())
for name in ['source-verification-r1.json','native-r1-result.json','code-review-result-r2.json','code-review-consumption-r2.json']:
    parts.append('\nEVIDENCE '+name+'\n'+(implementation/name).read_text())
for folder,name in [(implementation,'green-frozen-cumulative-r1.log'),(E,'http-serialization-r1.log'),(E,'http-red-r1.log')]:
    log=folder/name
    parts.append('\nRAW LOG '+name+' SHA '+hashlib.sha256(log.read_bytes()).hexdigest()+' FINAL EXCERPT\n'+'\n'.join(log.read_text().splitlines()[-3:]))
material=E/'route-quality-material-r1.txt'
with material.open('x') as stream:stream.write('\n'.join(parts))
relative=str(material.relative_to(R));materials={relative:material.read_text()}
assert len(json.dumps(materials).encode())<=65536,len(json.dumps(materials).encode())
request={'schema':'aos-material-review/v1','request_id':E.name+'-route-quality-r1','task_id':E.name,
 'owner':'codex-01a13484-f019-7d82-94ce-812396db9124','kind':'quality',
 'baseline':{'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'authority_revision':'AOS-002034',
     'files':{relative:hashlib.sha256(material.read_bytes()).hexdigest()}},
 'claims':[
    '路由仅为该已审计GET使用受支持ReadCatalog，并按typed installed readonly标记选择专用reader；原legacy成功分支和全部POST仍保持原门。',
    '认证tenant来自principal，query覆盖在准入前拒绝，unknown admission与reader失败稳定503且不补零或泄露底层错误；完整HTTP DTO保留真实空值及空命令。',
    '本波候选六文件和冻结267项、原生产兼容及独立临时PG证据可支持接线代码质量；独立reader质量已合法消费，尚未部署或完成整体业务与视觉目标。'],
 'materials':materials}
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
g.validate_request(R,request)
with (E/'route-quality-request-r1.json').open('x') as stream:
    json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps({'materialBytes':len(json.dumps(materials).encode()),'task':E.name}))
