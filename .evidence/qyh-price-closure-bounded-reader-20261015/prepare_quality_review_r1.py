from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
parent=R/'.evidence/qyh-price-closure-read-admission-20261015'
parts=['CANDIDATE SHARED READER QUALITY, not yet deployed. Plan r2 PASS legally consumed. Full Goal ACTIVE; no writer/operational authority. Current frozen335 tests PASS, first RED/failed implementation logs retained separately and are NOT current results. Preserve existing CREATOR default and reject unsupported modules; PRICE is a fixed subclass, not caller query selection.\n']
for relative in ['services/aos-api/aos_api/ecommerce_three_module_closure_readonly.py',
                 'services/aos-api/tests/test_ecommerce_three_module_closure_readonly.py',
                 'services/aos-api/aos_api/ecommerce_workshop_three_module_closure.py']:
    raw=(R/relative).read_bytes()
    parts.append('\nFULL FILE '+relative+' SHA '+hashlib.sha256(raw).hexdigest()+'\n'+raw.decode())
parts.append('\nEXACT SHARED READER DIFF AGAINST COMMITTED CREATOR BASELINE\n'+subprocess.check_output(['git','diff','--','services/aos-api/aos_api/ecommerce_three_module_closure_readonly.py'],text=True))
for folder,name in [(parent,'resource-ref-contract-note-r1.md'),(E,'source-verification-r1.json'),
                    (E,'native-r1-result.json'),(E,'native-r1-stopped.json')]:
    parts.append('\nEVIDENCE '+name+'\n'+(folder/name).read_text())
proof=json.loads((E/'source-verification-r1.json').read_text());assert proof['returncode']==0
assert proof['sourceAfter']=={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in proof['sourceAfter']}
log=E/'green-frozen-cumulative-r1.log'
parts.append('\nCURRENT FROZEN FULL RAW LOG SHA '+hashlib.sha256(log.read_bytes()).hexdigest()+' FINAL RESULT EXCERPT\n'+'\n'.join(log.read_text().splitlines()[-3:]))
material=E/'code-review-material-r1.txt';relative=str(material.relative_to(R));materials={relative:'\n'.join(parts)}
assert len(json.dumps(materials).encode())<=65536,len(json.dumps(materials).encode())
request={'schema':'aos-material-review/v1','request_id':E.name+'-code-r1','task_id':E.name,
 'owner':'codex-01a13484-f019-7d82-94ce-812396db9124','kind':'quality',
 'baseline':{'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'authority_revision':'AOS-002035',
             'files':{relative:hashlib.sha256(materials[relative].encode()).hexdigest()}},
 'claims':['候选复用原closure及binding的typed签名/派生ID/ledger/原public refs，固定price子类贯穿SQL/module/source/DTO，creator默认入口正常行为和旧错误码保留。',
           'price只在已核实只读一致snapshot内有界SELECT，strict raw/time/tenant/module/exact/privacy及稳定price错误门有效，空命令且不compile/bind/resolve/consume或授当前权限。',
           '冻结仅四owned overlay累计335项及原W6-009隔离PG证明候选与creator兼容、snapshot/RLS/25006/SQLCASE及五轴，不将synthetic mixed价格合同探针当原resolver实际经营能力；未部署或完成全Goal。'],
 'materials':materials}
controller=(parent/'review_controller.py').read_text().replace(parent.name,E.name)
with (E/'review_controller.py').open('x') as stream:stream.write(controller)
with material.open('x') as stream:stream.write(materials[relative])
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
g.validate_request(R,request)
with (E/'code-review-request-r1.json').open('x') as stream:
    json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps({'materialBytes':len(json.dumps(materials).encode()),'allOwnedHashesEqualFrozen335':True}))
