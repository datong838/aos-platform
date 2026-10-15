from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
impl=R/'.evidence/qyh-customer-lifecycle-bounded-reader-20261015'
parts=['ROUTE CODE QUALITY ONLY, not deployed. Reader code r1 PASS legally consumed; frozen387 PASS. RED logs are pre-implementation, not current failures. Full231Goal ACTIVE. Canonical customer contributions GET only; contact/closure/POST remain legacy. Original DB untouched.']
selected={
 'services/aos-api/aos_api/routers/ecommerce_workshop.py':{'_reject_query_parameters','_invoke','get_ecommerce_workshop_read_catalog','get_ecommerce_workshop_catalog','get_ecommerce_workshop_customer_lifecycle','get_customer_lifecycle_readonly','_require_customer_installation','get_customer_lifecycle_contribution_view','get_customer_contact_contribution_view'},
 'services/aos-api/tests/test_ecommerce_workshop_read_http.py':{'RejectingCatalog','ReadReached','client_with_catalogs','price_admission','customer_lifecycle_probes','test_read_dependency_only_reaches_explicit_audited_get_routes','test_unreviewed_get_still_uses_legacy_admission','test_customer_lifecycle_selects_only_admitted_reader','test_customer_lifecycle_denied_before_business_read','test_customer_lifecycle_unknown_admission_fails_closed','test_customer_lifecycle_failure_does_not_become_empty_success','test_customer_lifecycle_query_cannot_change_scope','test_customer_lifecycle_full_http_serialization'}}
for relative,names in selected.items():
 text=(R/relative).read_text();lines=text.splitlines();tree=ast.parse(text)
 parts.append('\nSELECTED COMPLETE AST '+relative+' fullFileSHA '+hashlib.sha256(text.encode()).hexdigest())
 for node in tree.body:
  if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names:
   start=min([node.lineno]+[d.lineno for d in node.decorator_list])-1
   parts.append('\n'+'\n'.join(lines[start:node.end_lineno]))
  elif isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name) and node.target.id in {'ReadCatalogDependency','CatalogDependency','CustomerLifecycleDependency','CustomerLifecycleReadonlyDependency','CustomerContactDependency'}:
   parts.append('\n'+'\n'.join(lines[node.lineno-1:node.end_lineno]))
 parts.append('\nEXACT FULL FILE DIFF\n'+subprocess.check_output(['git','diff','--',relative],cwd=R,text=True))
parts.append('\nFULL READER\n'+(R/'services/aos-api/aos_api/ecommerce_customer_lifecycle_readonly.py').read_text())
for name in ['source-verification-r1.json','native-r1-result.json','native-r1-stopped.json','code-review-result-r1.json','code-review-consumption-r1.json']:
 parts.append('\nEVIDENCE '+name+'\n'+(impl/name).read_text())
proof=json.loads((impl/'source-verification-r1.json').read_text())
assert proof['returncode']==0 and proof['sourceAfter']=={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in proof['sourceAfter']}
log=impl/'green-frozen-cumulative-r1.log'
parts.append('\nRAW FROZEN LOG SHA '+hashlib.sha256(log.read_bytes()).hexdigest()+'\n'+'\n'.join(log.read_text().splitlines()[-3:]))
material=E/'route-quality-material-r1.txt';relative=str(material.relative_to(R));materials={relative:'\n'.join(parts)}
size=len(json.dumps(materials).encode());assert size<=65536,size
request=dict(schema='aos-material-review/v1',request_id=E.name+'-route-quality-r1',task_id=E.name,owner='codex-01a13484-f019-7d82-94ce-812396db9124',kind='quality',
 baseline=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),authority_revision='AOS-002036',files={relative:hashlib.sha256(materials[relative].encode()).hexdigest()}),
 claims=['仅canonical customer contributions GET切换typed ReadCatalog并按installed readonly blocker分流专用reader；正常legacy成功、contact/closure和全部POST保持原门。',
 'principal租户/query拒绝/unknown准入及读取失败503、真实空和非空完整HTTP序列化/原写命令正常路径与只读空命令及四false均在冻结387中验证，不把异常补零/null成功。',
 'reader独立质量已合法消费，四文件冻结及原w6_007临时PG完整修订计数/快照/RLS/25006/SQLCASE/隐私证据支持此接线候选；原卷未触碰、未部署，不授Contact/Consent/预算/经营权限或宣称完整Goal完成。'],materials=materials)
with material.open('x') as stream:stream.write(materials[relative])
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
g.validate_request(R,request)
with (E/'route-quality-request-r1.json').open('x') as stream:
 json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps(dict(materialBytes=size,sourceUnchangedSinceFrozen387=True)))
