from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
parts=['PRE-EFFECT CONTROLLER QUALITY: actual preflight has succeeded, but no API signal/spawn. Do not require post-effect proof to permit pre-effect control review. Whole Goal remains active; only this exact readonly API switch is considered.\n']
controller=E/'customer_contact_api_switch_r1.py'
parts.append('CONTROLLER_SHA '+hashlib.sha256(controller.read_bytes()).hexdigest())
for name in ['pre-effect-gate-deny-result-r1.json','pre-effect-gate-deny-raw-r1.log']:
    parts.append('\nCURRENT ACTUAL MISSING-REVIEW NEGATIVE GATE '+name+'\n'+(E/name).read_text())
parts.append('This current controller negative API-phase experiment ran before any current review request existed. It failed inside quality() reading the required review file, before intent/signal/spawn; old API15265/Web89803/PG exact states were unchanged. This invocation is the first independent current pre-effect controller review, not a post-deployment review. Its result/consumption are FUTURE prerequisites checked in API phase, never a pre-existing claim. User original maintenance authorization is preserved separately; no operating/runtime authorization sought.')

parts.append('STAGE: this invocation IS the independent PRE-EFFECT controller quality review. Its own result/consumption cannot exist before completion. The API phase verifies this future review result PASS and exact legal consumption BEFORE any signal. Prior-wave controller NEED_EVIDENCE verdicts are not current code-gate verdicts; they are NOT the three code-gate verdicts. Actual three code results and consumptions follow; verify exact task IDs/statuses, do not conflate controller reviews with reader/route code reviews. No runtime admission sought; apiStartAuthorized=false and HostOFF are expected.')
for folder,prefix,version in [(R/'.evidence/qyh-customer-contact-read-admission-20261015','route-quality','r1'),(R/'.evidence/qyh-customer-contact-bounded-reader-20261015','code-review','r1')]:
    for suffix in ['result','consumption']:
        file=folder/(prefix+'-'+suffix+'-'+version+'.json')
        item=json.loads(file.read_text())
        assert (item['result']['verdict']=='PASS') if suffix=='result' else (item['status']=='CONSUMED_MATERIAL_REVIEW')
        parts.append('\nACTUAL INDEPENDENT CODE GATE '+str(file.relative_to(R))+'\n'+file.read_text())

for name in ['customer-contact-api-plan.md','customer_contact_api_switch_r1.py','api-preflight-r1.json']:
    parts.append('\nFILE '+name+'\n'+(E/name).read_text())
path=R/'scripts/a0v_qyh_restored_http.py';text=path.read_text();lines=text.splitlines();tree=ast.parse(text)
parts.append('\nUNCHANGED WRAPPER FULL SOURCE SHA '+hashlib.sha256(path.read_bytes()).hexdigest())
names={'require_api_source_candidate','installed_readonly_environment','serve_management_readonly','management_command','management_app'}
for node in tree.body:
    if isinstance(node,ast.FunctionDef) and node.name in names:parts.append('\n'+'\n'.join(lines[node.lineno-1:node.end_lineno]))
before=R/'.evidence/qyh-restoration-successor-latest-restart-20261013/customer-contact-before-20261015.json'
proof=json.loads(before.read_text());assert len(proof['fingerprints'])==650
parts.append('\nFRESH FULL650 BEFORE SUMMARY (full table file retained, not omitted from authority)\n'+json.dumps({k:v for k,v in proof.items() if k!='fingerprints'})+'\nfull650FileSha '+hashlib.sha256(before.read_bytes()).hexdigest())
for folder,name in [
 (R/'.evidence/qyh-customer-contact-bounded-reader-20261015','source-verification-r2.json'),
 (R/'.evidence/qyh-customer-contact-bounded-reader-20261015','code-review-consumption-r2.json'),
 (R/'.evidence/qyh-customer-contact-read-admission-20261015','route-quality-consumption-r1.json')]:
    parts.append('\nEVIDENCE '+str((folder/name).relative_to(R))+'\n'+(folder/name).read_text())
report=json.loads((R/'.evidence/qyh-full-system-restoration-20261011/customer-contact-api-20261015.json').read_text())
parts.append('\nACTUAL SOURCE FREEZE REPORT\n'+json.dumps(report))
material=E/'api-controller-review-package-r1.txt'
with material.open('x') as stream:stream.write('\n'.join(parts))
relative=str(material.relative_to(R));materials={relative:material.read_text()}
assert len(json.dumps(materials).encode())<=65536
request={'schema':'aos-material-review/v1','request_id':E.name+'-api-controller-r1','task_id':E.name,
 'owner':'codex-01a13484-f019-7d82-94ce-812396db9124','kind':'quality',
 'baseline':{'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'authority_revision':'AOS-002037',
     'files':{relative:hashlib.sha256(material.read_bytes()).hexdigest()}},
 'claims':['控制器源码将本次独立复审PASS合法消费置于新意图和信号之前；本机缺少必需审查文件的负向实验已在quality处拒绝，旧API/Web/PG及意图缺失状态前后一致。',
           '当前真实只读预检、三个独立代码PASS及其消费、原只读wrapper与准确API15265身份可核；所供前效代码仅更新指定API，不向PG/Web/Chrome发信号，不替代daily或后效SDK/650/视觉验收。'],
 'materials':materials}
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
g.validate_request(R,request)
with (E/'api-controller-review-request-r1.json').open('x') as stream:
    json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps({'materialBytes':len(json.dumps(materials).encode()),'controllerPreflightOnly':True}))
