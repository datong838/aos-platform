from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
parts=['PRE-EFFECT CONTROLLER QUALITY: actual preflight has succeeded, but no API signal/spawn. Do not require post-effect proof to permit pre-effect control review. Whole Goal remains active; only this exact readonly API switch is considered.\n']
controller=E/'price_disposition_api_switch_r2.py'
parts.append('CONTROLLER_SHA '+hashlib.sha256(controller.read_bytes()).hexdigest())
parts.append('R1 NEED_EVIDENCE legally consumed, not a PASS. This new review is PRE-EFFECT: its own PASS/consumption cannot exist before it returns. The controller API phase requires this new independent PASS AND legal consumption before any signal. No self-certification. Fresh preflight r2 now actually calls original guard.preflight management_readonly=True and supplies limited-login/native identity/inventory proof. Readonly full650 before is independently retained.')
for name in ['api-controller-review-result-r1.json','api-controller-review-consumption-r1.json']:
    parts.append('\nPREVIOUS REVIEW '+name+'\n'+(E/name).read_text())

for name in ['price-disposition-api-plan.md','price_disposition_api_switch_r2.py','api-preflight-r2.json']:
    parts.append('\nFILE '+name+'\n'+(E/name).read_text())
path=R/'scripts/a0v_qyh_restored_http.py';text=path.read_text();lines=text.splitlines();tree=ast.parse(text)
parts.append('\nUNCHANGED WRAPPER FULL SOURCE SHA '+hashlib.sha256(path.read_bytes()).hexdigest())
names={'require_api_source_candidate','installed_readonly_environment','serve_management_readonly','management_command','management_app'}
for node in tree.body:
    if isinstance(node,ast.FunctionDef) and node.name in names:parts.append('\n'+'\n'.join(lines[node.lineno-1:node.end_lineno]))
before=R/'.evidence/qyh-restoration-successor-latest-restart-20261013/price-disposition-before-20261015.json'
proof=json.loads(before.read_text());assert len(proof['fingerprints'])==650
parts.append('\nFRESH FULL650 BEFORE SUMMARY (full table file retained, not omitted from authority)\n'+json.dumps({k:v for k,v in proof.items() if k!='fingerprints'})+'\nfull650FileSha '+hashlib.sha256(before.read_bytes()).hexdigest())
for folder,name in [
 (R/'.evidence/qyh-price-disposition-bounded-reader-20261015','source-verification-r1.json'),
 (R/'.evidence/qyh-price-disposition-bounded-reader-20261015','code-review-consumption-r2.json'),
 (R/'.evidence/qyh-price-disposition-read-admission-r2-20261015','route-quality-consumption-r2.json')]:
    parts.append('\nEVIDENCE '+str((folder/name).relative_to(R))+'\n'+(folder/name).read_text())
report=json.loads((R/'.evidence/qyh-full-system-restoration-20261011/price-disposition-api-20261015.json').read_text())
parts.append('\nACTUAL SOURCE FREEZE REPORT\n'+json.dumps(report))
material=E/'api-controller-review-package-r2.txt'
with material.open('x') as stream:stream.write('\n'.join(parts))
relative=str(material.relative_to(R));materials={relative:material.read_text()}
assert len(json.dumps(materials).encode())<=65536
request={'schema':'aos-material-review/v1','request_id':E.name+'-api-controller-r2','task_id':E.name,
 'owner':'codex-01a13484-f019-7d82-94ce-812396db9124','kind':'quality',
 'baseline':{'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'authority_revision':'AOS-002034',
     'files':{relative:hashlib.sha256(material.read_bytes()).hexdigest()}},
 'claims':['新控制器与实际预检核对精确m1/Authority/Lease、原API/Web身份、原PG卷和源manifest及已消费代码门；只允许一次准确API更新。',
           '新意图、原只读wrapper及异常只读对账边界保留；不重启PG/Web/Chrome、不替代每日完整重启，不把spawn或代码PASS当实际业务或视觉完成。'],
 'materials':materials}
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
g.validate_request(R,request)
with (E/'api-controller-review-request-r2.json').open('x') as stream:
    json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps({'materialBytes':len(json.dumps(materials).encode()),'controllerPreflightOnly':True}))
