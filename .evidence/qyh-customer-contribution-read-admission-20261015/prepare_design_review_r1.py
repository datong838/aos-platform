from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
parts=['PRE-IMPLEMENTATION DESIGN REVIEW ONLY. No product code or admission yet. Full231Goal remains ACTIVE. Synthetic original producer probe is not real consent, contact, budget or operating authority. COUNT means all stored revisions, not active consent or distinct customers. Review whether the plan is safe and implementable before RED/code.']
for rel in ['services/aos-api/aos_api/ecommerce_workshop_customer_lifecycle.py','services/aos-api/aos_api/ecommerce_workshop_customer_lifecycle_store.py','services/aos-api/alembic/versions/w6_007_customer_lifecycle.py']:
 raw=(R/rel).read_bytes();assert subprocess.check_output(['git','show','HEAD:'+rel],cwd=R)==raw
 parts.append('\nFULL FILE '+rel+' SHA '+hashlib.sha256(raw).hexdigest()+'\n'+raw.decode())
rel='services/aos-api/aos_api/routers/ecommerce_workshop.py'
raw=(R/rel).read_bytes();assert subprocess.check_output(['git','show','HEAD:'+rel],cwd=R)==raw
text=raw.decode();lines=text.splitlines();tree=ast.parse(text)
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='get_customer_lifecycle_contribution_view')
parts.append('\nCURRENT ROUTE '+rel+' fullFileSHA '+hashlib.sha256(raw).hexdigest()+'\n'+'\n'.join(lines[min(d.lineno for d in node.decorator_list)-1:node.end_lineno]))
for name in ['implementation-plan-r1.md','producer-probe-result-r1.json','reader-scope-readback-r1.json']:
 parts.append('\nEVIDENCE '+name+'\n'+(E/name).read_text())
relative=str((E/'design-review-material-r1.txt').relative_to(R));materials={relative:'\n'.join(parts)}
size=len(json.dumps(materials).encode());assert size<=65536,size
request=dict(schema='aos-material-review/v1',request_id=E.name+'-design-r1',task_id=E.name,
 owner='codex-01a13484-f019-7d82-94ce-812396db9124',kind='route',
 baseline=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),authority_revision='AOS-002036',files={relative:hashlib.sha256(materials[relative].encode()).hexdigest()}),
 claims=['方案保留原四表完整保存修订COUNT语义，用同一只读一致快照和有界SQL读取选中Batch与exact祖先及四policy；失败稳定拒绝而非补零或null成功。',
 '方案按原producer typed refs与typed ledger签名、prepare/freeze继承及policy lineage验证保存事实，严格tenant/time/隐私/尺寸和零效果；不把历史granted或fixture当当前Consent或Contact准入。',
 '额外reader与test已非重叠登记，router仅canonical installed readonly GET分流；原writer/Store/DDL/Web及POST不改，RED/原DDL隔离PG/冻结相邻/独立质量/真实SDK650与视觉门明确，完整Goal未缩小。'],materials=materials)
controller=(R/'.evidence/qyh-price-closure-read-admission-20261015/review_controller.py').read_text().replace('qyh-price-closure-read-admission-20261015',E.name)
for path,value in [(E/'review_controller.py',controller),(R/relative,materials[relative])]:
 with path.open('x') as stream:stream.write(value)
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
g.validate_request(R,request)
with (E/'design-review-request-r1.json').open('x') as stream:
 json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps(dict(materialBytes=size,productChanges=False,request=request['request_id'])))
