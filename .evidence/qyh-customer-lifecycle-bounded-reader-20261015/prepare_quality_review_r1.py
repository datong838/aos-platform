from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
parent=R/'.evidence/qyh-customer-contribution-read-admission-20261015'
parts=['READER CODE QUALITY ONLY, NOT DEPLOYED. Full231Goal ACTIVE. Original domain writer/Store/DDL unchanged. Independent design PASS legally consumed. Synthetic native PG uses only disposable tmpfs, not original business DB or real Consent authority.']
for relative in ['services/aos-api/aos_api/ecommerce_customer_lifecycle_readonly.py','services/aos-api/tests/test_ecommerce_customer_lifecycle_readonly.py','services/aos-api/aos_api/ecommerce_workshop_customer_lifecycle.py']:
 raw=(R/relative).read_bytes()
 parts.append('\nFULL FILE '+relative+' SHA '+hashlib.sha256(raw).hexdigest()+'\n'+raw.decode())
for path in [parent/'implementation-plan-r1.md',parent/'design-review-consumption-r1.json',E/'source-verification-r1.json',E/'native-r1-result.json',E/'native-r1-stopped.json']:
 parts.append('\nEVIDENCE '+str(path.relative_to(R))+'\n'+path.read_text())
log=E/'green-frozen-cumulative-r1.log'
parts.append('\nFULL RAW LOG SHA '+hashlib.sha256(log.read_bytes()).hexdigest()+'\n'+'\n'.join(log.read_text().splitlines()[-3:]))
proof=json.loads((E/'source-verification-r1.json').read_text())
assert proof['returncode']==0 and proof['sourceAfter']=={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in proof['sourceAfter']}
material=E/'code-review-material-r1.txt';relative=str(material.relative_to(R));materials={relative:'\n'.join(parts)}
size=len(json.dumps(materials).encode());assert size<=65536,size
request=dict(schema='aos-material-review/v1',request_id=E.name+'-code-r1',task_id=E.name,
 owner='codex-01a13484-f019-7d82-94ce-812396db9124',kind='quality',
 baseline=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),authority_revision='AOS-002036',files={relative:hashlib.sha256(materials[relative].encode()).hexdigest()}),
 claims=['客户reader在同一核实只读RR快照中读取四完整保存修订COUNT及有界latest Batch/exact ancestor/policies，SQL尺寸与时间门、outer metadata与稳定错误防止失败伪装空成功。',
 '选中保存事实按原policy请求签名、typed refs/typed ledger与item hashes、prepare/freeze完整继承及lineage核验；strict raw/tenant/time/隐私和零效果保留unknown，不产生Contact或当前Consent准入。',
 '冻结仅四owned overlay的387专项及相邻测试、原w6_007临时PG真快照/RLS/25006/SQLCASE/metadata拒绝物证与已停止CID支持此候选；未部署、不宣称真实经营或完整Goal完成。'],materials=materials)
controller=(parent/'review_controller.py').read_text().replace(parent.name,E.name)
with (E/'review_controller.py').open('x') as stream:stream.write(controller)
with material.open('x') as stream:stream.write(materials[relative])
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
g.validate_request(R,request)
with (E/'code-review-request-r1.json').open('x') as stream:
 json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps(dict(materialBytes=size,sourceUnchangedSinceFrozen387=True)))
