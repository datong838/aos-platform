from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
parts=['CODE QUALITY OF PREREQUISITE ONLY. Not deployed; contact GET still legacy404. Full231Goal ACTIVE. Original production default UTC typed signature is preserved. Old records lacking reason or unsupported historical timezone provenance are not guessed or rewritten. This fixes future saved signing material, not Contact/Consent/receipt authorization.']
for rel in ['services/aos-api/aos_api/ecommerce_workshop_customer_contact.py','services/aos-api/aos_api/ecommerce_workshop_customer_contact_store.py','services/aos-api/tests/test_customer_start_signing_material.py']:
 raw=(R/rel).read_bytes();parts.append('\nFULL FILE '+rel+' SHA '+hashlib.sha256(raw).hexdigest()+'\n'+raw.decode())
for name in ['implementation-plan-r2.md','design-review-consumption-r2.json','source-verification-r1.json','native-r1-result.json','native-r1-stopped.json','model-contract-probe-result-r2.json']:
 parts.append('\nEVIDENCE '+name+'\n'+(E/name).read_text())
for name in ['red-r1.log','green-r1.log','green-frozen-cumulative-r1.log']:
 path=E/name;parts.append('\nRAW LOG '+name+' SHA '+hashlib.sha256(path.read_bytes()).hexdigest()+'\n'+'\n'.join(path.read_text().splitlines()[-3:]))
proof=json.loads((E/'source-verification-r1.json').read_text());assert proof['returncode']==0 and len(proof['sourceAfter'])==3
assert all(hashlib.sha256((R/p).read_bytes()).hexdigest()==sha for p,sha in proof['sourceAfter'].items())
material=E/'code-review-material-r1.txt';rel=str(material.relative_to(R));materials={rel:'\n'.join(parts)}
size=len(json.dumps(materials).encode());assert size<=65536,size
request=dict(schema='aos-material-review/v1',request_id=E.name+'-code-r1',task_id=E.name,owner='codex-01a13484-f019-7d82-94ce-812396db9124',kind='quality',
 baseline=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),authority_revision='AOS-002037',files={rel:hashlib.sha256(materials[rel].encode()).hexdigest()}),
 claims=['仅三个登记文件最小补新Start原reason的私有保存与原生产UTC typed签名纯重建；原producer签名配方不改，旧row缺材料兼容decode但不猜不回填，原Start/receipt resolver与零效果保持。',
 '公开model_dump/API序列化schema/原frontend字段与repr不包含私有reason，Store新记录回读后能复原原hash；敏感reason在任何Store或reservation访问前稳定拒绝且不echo，unknown贡献投影仍保持held且不篡改原Start。',
 'RED8失败1通过后专项及原W6-08共20通过，三owned overlay冻结407与原w6_008临时PG真实Store往返/幂等/旧row不补写/RLS/25006并停止CID物证支持此前置代码候选；未部署或放行GET，不宣称实际Contact/Consent或完整Goal完成。'],materials=materials)
with material.open('x') as stream:stream.write(materials[rel])
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g;g.validate_request(R,request)
with (E/'code-review-request-r1.json').open('x') as stream:
 json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps(dict(materialBytes=size,threeOwnedOverlays=True,productDeployed=False)))
