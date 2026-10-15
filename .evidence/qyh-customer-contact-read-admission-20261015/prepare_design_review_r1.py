from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
parts=['PRE-IMPLEMENTATION CONTACT READER DESIGN. Prerequisite private signing material is committed90a601 and code-quality PASS, NOT deployed. Contact reader/router do not exist yet. Review plan implementability/coherence before RED, not existence of future implementation/tests. Full231Goal ACTIVE, original runtime API80b39 remains. Synthetic saved observations are not current Consent/ActionReceipt/Contact authority.']
relative='services/aos-api/aos_api/ecommerce_workshop_customer_contact.py';raw=(R/relative).read_bytes()
assert subprocess.check_output(['git','show','HEAD:'+relative],cwd=R)==raw
parts.append('\nFULL FILE '+relative+' SHA '+hashlib.sha256(raw).hexdigest()+'\n'+raw.decode())
selected={
 'services/aos-api/aos_api/ecommerce_workshop_customer_contact_store.py':{'__init__','latest_start_for_tenant_or_none','authority_counts','list_dispatch_observations','require_start_authorities','require_action_receipt','latest_withdrawal_or_none'},
 'services/aos-api/aos_api/ecommerce_customer_lifecycle_readonly.py':{'_decode','_validate_batch','_matches','_strict','_privacy'}}
for relative,names in selected.items():
 raw=(R/relative).read_bytes();assert subprocess.check_output(['git','show','HEAD:'+relative],cwd=R)==raw
 lines=raw.decode().splitlines();tree=ast.parse(raw.decode())
 parts.append('\nSELECTED COMPLETE FUNCTIONS '+relative+' fullFileSHA '+hashlib.sha256(raw).hexdigest())
 for node in tree.body:
  candidates=node.body if isinstance(node,ast.ClassDef) else [node]
  for child in candidates:
   if isinstance(child,ast.FunctionDef) and child.name in names:
    start=min([child.lineno]+[d.lineno for d in child.decorator_list])-1
    parts.append('\n'+'\n'.join(lines[start:child.end_lineno]))
for path in [E/'implementation-plan-r2.md',E/'producer-probe-result-r2.json',E/'reader-scope-readback-r1.json',R/'.evidence/qyh-customer-start-signing-material-20261015/code-review-consumption-r2.json']:
 parts.append('\nEVIDENCE '+str(path.relative_to(R))+'\n'+path.read_text())
material=E/'design-review-material-r1.txt';relative=str(material.relative_to(R));materials={relative:'\n'.join(parts)}
size=len(json.dumps(materials).encode());assert size<=65536,size
request=dict(schema='aos-material-review/v1',request_id=E.name+'-design-r1',task_id=E.name,owner='codex-01a13484-f019-7d82-94ce-812396db9124',kind='route',
 baseline=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),authority_revision='AOS-002037',files={relative:hashlib.sha256(materials[relative].encode()).hexdigest()}),
 claims=['方案用完整两COUNT与同一核实只读RR截止面、有界selected Start/exact Batch/policies/reservation/withdrawal/observations读取，明确超界与错误稳定拒绝而不截断或补零/null，可实施且不把保存计数当当前Consent。',
 '方案先验证原未投影Start私有reason及原生产UTC签名、exact lineage/items/零效果与各保存观察签名，再复用原service投影并保留unknown held；不把投影当新签名Start，不调用原关闭resolver或Contact/Provider。',
 '额外两reader/test文件已非重叠登记，parent只canonical contact GET和HTTP测试接线，其他GET/POST/Web/原DB不扩权；未来RED/冻结/原DDL隔离PG/独立质量/真实SDK650和视觉门明确，当前只方案可行性审阅且完整Goal未缩小。'],materials=materials)
controller=(R/'.evidence/qyh-customer-contribution-read-admission-20261015/review_controller.py').read_text().replace('qyh-customer-contribution-read-admission-20261015',E.name)
with (E/'review_controller.py').open('x') as stream:stream.write(controller)
with material.open('x') as stream:stream.write(materials[relative])
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g;g.validate_request(R,request)
with (E/'design-review-request-r1.json').open('x') as stream:
 json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps(dict(materialBytes=size,readerCodeChanged=False,head=request['baseline']['head'])))
