from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1];I=R/'.evidence/qyh-customer-contact-bounded-reader-20261015'
parts=['ROUTE CODE QUALITY, NOT DEPLOYED. Reader r2 PASS legally consumed, frozen482 current. Prerequisite private-signing code90a601 committed; original runtime still80b39. Only canonical customer contact-contributions GET expands installed readonly admission. Source/Consent/Contact/Receipt/Provider/send authority remains OFF. Full231Goal ACTIVE.']
selected={
 'services/aos-api/aos_api/routers/ecommerce_workshop.py':{'_reject_query_parameters','_invoke','get_ecommerce_workshop_read_catalog','get_ecommerce_workshop_catalog','get_ecommerce_workshop_customer_contact','get_customer_contact_readonly','get_customer_contact_contribution_view'},
 'services/aos-api/tests/test_ecommerce_workshop_read_http.py':{'RejectingCatalog','ReadReached','client_with_catalogs','contact_admission','contact_probes','test_read_dependency_only_reaches_explicit_audited_get_routes','test_unreviewed_get_still_uses_legacy_admission','test_customer_contact_selects_only_admitted_reader','test_customer_contact_denied_before_business_read','test_customer_contact_unknown_admission_fails_closed','test_customer_contact_read_failure_never_becomes_empty_success','test_customer_contact_query_cannot_change_scope','test_customer_contact_complete_public_http_dto'}}
for rel,names in selected.items():
 raw=(R/rel).read_bytes();lines=raw.decode().splitlines();tree=ast.parse(raw.decode())
 parts.append('\nCOMPLETE SELECTED AST '+rel+' fullFileSHA '+hashlib.sha256(raw).hexdigest())
 for node in tree.body:
  if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names:
   start=min([node.lineno]+[d.lineno for d in node.decorator_list])-1;parts.append('\n'+'\n'.join(lines[start:node.end_lineno]))
  elif isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name) and node.target.id in {'ReadCatalogDependency','CatalogDependency','CustomerContactDependency','CustomerContactReadonlyDependency'}:
   parts.append('\n'+'\n'.join(lines[node.lineno-1:node.end_lineno]))
 parts.append('\nEXACT FULL FILE DIFF\n'+subprocess.check_output(['git','diff','--',rel],cwd=R,text=True))
parts.append('\nFULL CURRENT READER\n'+(R/'services/aos-api/aos_api/ecommerce_customer_contact_readonly.py').read_text())
for name in ['source-verification-r2.json','native-r2-stopped.json','code-review-result-r2.json','code-review-consumption-r2.json']:
 parts.append('\nEVIDENCE '+name+'\n'+(I/name).read_text())
native=I/'native-r2-result.json';value=json.loads(native.read_text());facts=value.pop('connectionFacts');value['connectionFactCount']=len(facts);value['uniqueConnectionFacts']=list({json.dumps(x,sort_keys=True):x for x in facts}.values())
parts.append('\nNATIVE RESULT fullRawSHA '+hashlib.sha256(native.read_bytes()).hexdigest()+'\n'+json.dumps(value))
proof=json.loads((I/'source-verification-r2.json').read_text());assert proof['returncode']==0
assert proof['sourceAfter']=={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in proof['sourceAfter']}
for name in ['http-red-r1.log']:
 path=E/name;parts.append('\nPRE-IMPLEMENTATION RED '+name+' fullRawSHA '+hashlib.sha256(path.read_bytes()).hexdigest()+'\n'+'\n'.join(path.read_text().splitlines()[-2:]))
log=I/'green-frozen-cumulative-r2.log';parts.append('\nCURRENT FROZEN fullRawSHA '+hashlib.sha256(log.read_bytes()).hexdigest()+'\n'+'\n'.join(log.read_text().splitlines()[-2:]))
material=E/'route-quality-material-r1.txt';relative=str(material.relative_to(R));materials={relative:'\n'.join(parts)};size=len(json.dumps(materials).encode());assert size<=65536,size
request=dict(schema='aos-material-review/v1',request_id=E.name+'-route-quality-r1',task_id=E.name,owner='codex-01a13484-f019-7d82-94ce-812396db9124',kind='quality',
 baseline=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),authority_revision='AOS-002037',files={relative:hashlib.sha256(materials[relative].encode()).hexdigest()}),
 claims=['仅canonical customer contact-contributions GET使用typed ReadCatalog，并校验返回module/tenant与principal一致后按installed readonly blocker分流；正常legacy成功及其他GET/POST原门保持。',
 'query拒绝/准入未知及错module租户拒绝/reader各失败503不补null、空与非空完整HTTP DTO、空命令和五false均由冻结482验证；未扩大原安装/真人授权为Contact或发送权限。',
 'reader r2独立质量已合法消费，冻结四owned overlay及原W6-007/008临时PG当前版本物证（含深JSON decoder限制、metadata先于bulk）且CID停止，支持该接线候选；尚未部署、原卷未碰、经营/八台视觉/完整Goal不宣称完成。'],materials=materials)
with material.open('x') as stream:stream.write(materials[relative])
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g;g.validate_request(R,request)
with (E/'route-quality-request-r1.json').open('x') as stream:json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps(dict(materialBytes=size,sourceUnchangedSinceFrozen482=True)))
