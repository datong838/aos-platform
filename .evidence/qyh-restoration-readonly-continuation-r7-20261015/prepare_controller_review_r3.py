from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
parts=['PRE-EFFECT CONTROLLER QUALITY: actual preflight has succeeded, but no API signal/spawn. Do not require post-effect proof to permit pre-effect control review. Whole Goal remains active; only this exact readonly API switch is considered.\n']
controller=E/'price_disposition_api_switch_r3.py'
parts.append('CONTROLLER_SHA '+hashlib.sha256(controller.read_bytes()).hexdigest())
parts.append('STAGE: this invocation IS the independent PRE-EFFECT controller quality review. Its own result/consumption cannot exist before completion. The API phase verifies this future review result PASS and exact legal consumption BEFORE any signal. Previous controller NEED_EVIDENCE verdicts retained separately; they are NOT the two code-gate verdicts. Actual two code results and consumptions follow; verify exact task IDs/statuses, do not conflate controller reviews with reader/route code reviews. No runtime admission sought; apiStartAuthorized=false and HostOFF are expected.')
for folder,prefix in [(R/'.evidence/qyh-price-disposition-read-admission-r2-20261015','route-quality'),(R/'.evidence/qyh-price-disposition-bounded-reader-20261015','code-review')]:
    for suffix in ['result','consumption']:
        file=folder/(prefix+'-'+suffix+'-r2.json')
        item=json.loads(file.read_text())
        assert (item['result']['verdict']=='PASS') if suffix=='result' else (item['status']=='CONSUMED_MATERIAL_REVIEW')
        parts.append('\nACTUAL INDEPENDENT CODE GATE '+str(file.relative_to(R))+'\n'+file.read_text())

for name in ['price-disposition-api-plan.md','price_disposition_api_switch_r3.py','api-preflight-r3.json']:
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
material=E/'api-controller-review-package-r3.txt'
with material.open('x') as stream:stream.write('\n'.join(parts))
relative=str(material.relative_to(R));materials={relative:material.read_text()}
assert len(json.dumps(materials).encode())<=65536
request={'schema':'aos-material-review/v1','request_id':E.name+'-api-controller-r3','task_id':E.name,
 'owner':'codex-01a13484-f019-7d82-94ce-812396db9124','kind':'quality',
 'baseline':{'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'authority_revision':'AOS-002034',
     'files':{relative:hashlib.sha256(material.read_bytes()).hexdigest()}},
 'claims':['当前预检与两个独立代码PASS及合法消费可核；控制器必须在本次维护审查PASS合法消费之后才生成新意图并仅更新准确旧API，未提前执行。',
           '前效控制器与原readonly wrapper保留一次意图和未知对账边界，不向PG/Web/Chrome发信号，不授运行准入或代替每日完整重启；现场核验仍是后效门。'],
 'materials':materials}
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
g.validate_request(R,request)
with (E/'api-controller-review-request-r3.json').open('x') as stream:
    json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps({'materialBytes':len(json.dumps(materials).encode()),'controllerPreflightOnly':True}))
