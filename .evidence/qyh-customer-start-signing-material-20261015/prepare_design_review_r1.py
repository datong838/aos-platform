from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1];P=R/'.evidence/qyh-customer-contact-read-admission-20261015'
parts=['PRE-IMPLEMENTATION DESIGN. Prerequisite only: preserve original customer Start signing reason privately. Full contact reader/real SDK/650/visual/full231Goal remain; no admission or product code changed yet. Original production resolvers remain blocked.']
for relative in ['services/aos-api/aos_api/ecommerce_workshop_customer_contact.py','services/aos-api/aos_api/ecommerce_workshop_customer_contact_store.py']:
 raw=(R/relative).read_bytes();assert subprocess.check_output(['git','show','HEAD:'+relative],cwd=R)==raw
 parts.append('\nFULL FILE '+relative+' SHA '+hashlib.sha256(raw).hexdigest()+'\n'+raw.decode())
for path in [E/'implementation-plan-r1.md',P/'producer-probe-result-r1.json',P/'signing-task-readback-r1.json']:
 parts.append('\nEVIDENCE '+str(path.relative_to(R))+'\n'+path.read_text())
raw=(R/'apps/web/src/api/ecommerceWorkshop/parser.ts').read_text();start=raw.index('function parseCustomerContactStart(');end=raw.index('export function parseCustomerContactContributionView',start)
parts.append('\nUNCHANGED PUBLIC START PARSER\n'+raw[start:end])
material=E/'design-review-material-r1.txt';relative=str(material.relative_to(R));materials={relative:'\n'.join(parts)}
size=len(json.dumps(materials).encode());assert size<=65536,size
request=dict(schema='aos-material-review/v1',request_id=E.name+'-design-r1',task_id=E.name,owner='codex-01a13484-f019-7d82-94ce-812396db9124',kind='route',
 baseline=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),authority_revision='AOS-002037',files={relative:hashlib.sha256(materials[relative].encode()).hexdigest()}),
 claims=['原Start签名含request.reason但保存模型遗漏的缺口由原producer探针证明；方案仅对新Start私有保存必要材料、原hash/idempotency不变，旧row缺材料不猜不补写，后续完整reader不降级弱校验。',
 '可选exclude/repr false字段与仅Start专用serializer设计保持公开wire/原frontend exact keys及旧payload decode；敏感理由在reservation之前拒绝且不echo，原生产resolver和零效果边界保留。',
 '三个产品测试文件已非重叠登记，RED/冻结原W6-08及相邻/原DDL隔离PG持久化往返/公开schema与独立质量门明确；此前置不冒充GET、当前Consent/Contact或完整Goal完成。'],materials=materials)
controller=(R/'.evidence/qyh-customer-contribution-read-admission-20261015/review_controller.py').read_text().replace('qyh-customer-contribution-read-admission-20261015',E.name)
with (E/'review_controller.py').open('x') as stream:stream.write(controller)
with material.open('x') as stream:stream.write(materials[relative])
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
g.validate_request(R,request)
with (E/'design-review-request-r1.json').open('x') as stream:
 json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps(dict(materialBytes=size,productCodeChanged=False)))
