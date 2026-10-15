from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
impl=R/'.evidence/qyh-price-closure-bounded-reader-20261015'
parts=['ROUTE CODE QUALITY, not deployed. Shared-reader code r2 PASS legally consumed and current frozen335 PASS. Historical http-red-r1 was PRE-IMPLEMENTATION and is not current candidate evidence; no source changes after frozen335. Four product/test files only. No creator/customer/POST admission expansion beyond explicit price GET branch.\n']
selected={
 'services/aos-api/aos_api/routers/ecommerce_workshop.py':{
    '_reject_query_parameters','_invoke','get_ecommerce_workshop_read_catalog','get_ecommerce_workshop_catalog',
    'get_creator_closure_readonly','get_price_closure_readonly','get_ecommerce_workshop_three_module_closure',
    '_require_creator_growth_installation','_require_three_module_installation','get_three_module_closure_contribution_view'},
 'services/aos-api/tests/test_ecommerce_workshop_read_http.py':{
    'RejectingCatalog','ReadReached','client_with_catalogs','price_admission','lifecycle_admission','closure_probes','price_closure_probes',
    'test_read_dependency_only_reaches_explicit_audited_get_routes','test_creator_closure_selects_only_the_admitted_reader',
    'test_other_closure_modules_keep_legacy_catalog','test_creator_closure_query_cannot_change_scope_or_reader',
    'test_price_closure_selects_only_admitted_reader','test_price_closure_denied_before_both_readers',
    'test_price_closure_unknown_admission_is_unavailable','test_price_closure_failure_does_not_become_null_success',
    'test_price_closure_query_cannot_change_scope','test_price_closure_complete_http_dto'}}
for relative,names in selected.items():
    text=(R/relative).read_text();lines=text.splitlines();tree=ast.parse(text)
    parts.append('\nFULL SELECTED AST FUNCTIONS '+relative+' fullfileSHA '+hashlib.sha256(text.encode()).hexdigest())
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names:
            start=min([node.lineno]+[d.lineno for d in node.decorator_list])-1
            parts.append('\n'+'\n'.join(lines[start:node.end_lineno]))
        elif isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name) and node.target.id in {
                'ReadCatalogDependency','CatalogDependency','ThreeModuleClosureDependency',
                'CreatorClosureReadonlyDependency','PriceClosureReadonlyDependency'}:
            parts.append('\n'+'\n'.join(lines[node.lineno-1:node.end_lineno]))
    parts.append('\nEXACT FULL FILE DIFF\n'+subprocess.check_output(['git','diff','--',relative],text=True))
reader=R/'services/aos-api/aos_api/ecommerce_three_module_closure_readonly.py'
parts.append('\nFULL SHARED READER\n'+reader.read_text())
for name in ['source-verification-r1.json','native-r1-result.json','code-review-result-r2.json','code-review-consumption-r2.json']:
    parts.append('\nEVIDENCE '+name+'\n'+(impl/name).read_text())
log=impl/'green-frozen-cumulative-r1.log'
parts.append('\nCURRENT FROZEN FULL RAW LOG SHA '+hashlib.sha256(log.read_bytes()).hexdigest()+' FINAL EXCERPT\n'+'\n'.join(log.read_text().splitlines()[-3:]))
proof=json.loads((impl/'source-verification-r1.json').read_text())
assert proof['returncode']==0 and proof['sourceAfter']=={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in proof['sourceAfter']}
material=E/'route-quality-material-r1.txt';relative=str(material.relative_to(R));materials={relative:'\n'.join(parts)}
assert len(json.dumps(materials).encode())<=65536,len(json.dumps(materials).encode())
request={'schema':'aos-material-review/v1','request_id':E.name+'-route-quality-r1','task_id':E.name,
 'owner':'codex-01a13484-f019-7d82-94ce-812396db9124','kind':'quality',
 'baseline':{'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'authority_revision':'AOS-002035',
             'files':{relative:hashlib.sha256(materials[relative].encode()).hexdigest()}},
 'claims':['仅canonical price closure GET新增受支持typed ReadCatalog及固定Price reader分流，creator原入口、customer legacy及全部POST保持原门。',
           'principal租户和query拒绝、unknown准入及reader失败503、完整空/非空HTTP DTO与空命令/零外部效果语义已在冻结335中核对，不将读取失败补null成功。',
           '共享reader独立质量已合法消费，候选四文件与隔离原W6-009/creator回归证据支持本接线切片；未部署、未授生产source/预算/运营准入或宣称完整Goal完成。'],
 'materials':materials}
with material.open('x') as stream:stream.write(materials[relative])
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
g.validate_request(R,request)
with (E/'route-quality-request-r1.json').open('x') as stream:
    json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps({'materialBytes':len(json.dumps(materials).encode()),'sourceUnchangedSince335':True}))
