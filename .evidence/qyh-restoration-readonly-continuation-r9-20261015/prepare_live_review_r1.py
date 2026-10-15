from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
parent=R/'.evidence/qyh-customer-contribution-read-admission-20261015';impl=R/'.evidence/qyh-customer-lifecycle-bounded-reader-20261015'
parts=['POST-EFFECT LIVE QUALITY: only customer saved contribution readonly slice. Original full231Goal active, not complete. Images were individually inspected by current implementer; raw geometry, six PNG hashes/dimensions and candid visual gaps supplied. Do not claim model independently saw PNG pixels or full visual/nonempty/a11y/business completion.']
for name in ['customer-live-report-r1.md','customer-runtime-proof-r1.json','customer-full650-comparison-r1.json','customer-native-identity-sdk-r1.json','customer-native-geometry-deny-r1.json','customer-live-shas-r1.json','api-preflight-r1.json','pre-effect-gate-deny-result-r1.json','api-switch-intent-r1.json','api-started-r1.json','api-controller-review-result-r1.json','api-controller-review-consumption-r1.json']:
 parts.append('\nEVIDENCE '+name+'\n'+(E/name).read_text())
for folder,name in [(parent,'route-quality-result-r1.json'),(parent,'route-quality-consumption-r1.json'),(impl,'code-review-result-r1.json'),(impl,'code-review-consumption-r1.json'),(impl,'source-verification-r1.json'),(impl,'native-r1-result.json'),(impl,'native-r1-stopped.json')]:
 parts.append('\nEVIDENCE '+str((folder/name).relative_to(R))+'\n'+(folder/name).read_text())
proof=json.loads((E/'customer-runtime-proof-r1.json').read_text());assert proof['all650BeforeAfterEqual'] and proof['actualCustomerSdk200'] and not proof['wholeGoalComplete']
material=E/'customer-live-review-material-r1.txt';relative=str(material.relative_to(R));materials={relative:'\n'.join(parts)}
size=len(json.dumps(materials).encode());assert size<=65536,size
request=dict(schema='aos-material-review/v1',request_id=E.name+'-customer-live-r1',task_id=E.name,owner='codex-01a13484-f019-7d82-94ce-812396db9124',kind='quality',
 baseline=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),authority_revision='AOS-002036',files={relative:hashlib.sha256(materials[relative].encode()).hexdigest()}),
 claims=['独立前效controller PASS合法消费和真实缺审拒绝物证之后，仅一次fresh API更新；实际15265/cwd80b39源、Web89803/f036、原PG同CID卷StartedAt及650完整前后指纹一致支持本次保存读取现场。',
 '原唯一真人同租户正式customer SDK200保留四可信保存计数0/latest null/commands[]/四false与实际缺口，query400/匿名401/contact和closure404/业务nonGET[]，不将历史或合成事实当当前Consent/Contact或运营准入。',
 '实际三视口页签筛选/几何与六图尺寸hash、明确逐图检查及视觉差距登记只支持本真实空态读取slice；未声称像素/非空/a11y/八台或完整Goal完成，daily每次aos原卷full重启及全部剩余长期目标保持。'],materials=materials)
with material.open('x') as stream:stream.write(materials[relative])
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
g.validate_request(R,request)
with (E/'customer-live-review-request-r1.json').open('x') as stream:
 json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps(dict(materialBytes=size,wholeGoalComplete=False)))
