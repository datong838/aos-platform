from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
parts=['POST-EFFECT READONLY LIVE QUALITY. Actual API95375/source4e switch completed once after controller quality r4 PASS legal. Full business/install/visual Goal NOT complete; no production/gate permission sought. Geometry and six local PNG hash/dimension evidence are supplied, NOT a claim this tools-disabled reviewer has viewed image pixels or all eight workbenches.\n']
for name in ['disposition-live-report-r1.md','verify_disposition_runtime_r1.py',
             'disposition-runtime-proof-r1.json','disposition-native-identity-sdk-r1.json','disposition-live-shas-r1.json',
             'api-switch-intent-r1.json','api-old-stop-r1.json','api-started-r1.json','api-controller-review-consumption-r4.json']:
    path=E/name;parts.append('\nFILE '+name+' SHA '+hashlib.sha256(path.read_bytes()).hexdigest()+'\n'+path.read_text())
comparison=E/'disposition-full650-comparison-r1.json'
parts.append('\nALL650 FULL TABLE EQUALITY MAP (compact JSON; every table retained) FILESHA '+hashlib.sha256(comparison.read_bytes()).hexdigest()+'\n'+json.dumps(json.loads(comparison.read_text()),separators=(',',':')))
browser=json.loads((E/'disposition-native-geometry-deny-r1.json').read_text())
browser['trace']=[x for x in browser['trace'] if '/ecommerce-workshop/' in x['path'] or x['path'] in ['/api/v1/auth/token','/api/v1/me']]
parts.append('\nBROWSER ACTUAL METRICS/DENY AND RELEVANT NETWORK TRACE (only periodic health and general module polls omitted) full original fileSHA '+hashlib.sha256((E/'disposition-native-geometry-deny-r1.json').read_bytes()).hexdigest()+'\n'+json.dumps(browser,separators=(',',':')))
for folder,prefix,version in [
 (R/'.evidence/qyh-price-disposition-read-admission-r2-20261015','route-quality','r2'),
 (R/'.evidence/qyh-price-disposition-bounded-reader-20261015','code-review','r2'),
 (E,'api-controller-review','r4')]:
    result=folder/f'{prefix}-result-{version}.json';consumption=folder/f'{prefix}-consumption-{version}.json'
    raw=json.loads(result.read_text());assert raw['result']['verdict']=='PASS'
    consumed=json.loads(consumption.read_text());assert consumed['status']=='CONSUMED_MATERIAL_REVIEW'
    parts.append('\nEXACT PRIOR GATE '+str(result.relative_to(R))+' SHA '+hashlib.sha256(result.read_bytes()).hexdigest()+'\n'+json.dumps(consumed))
path=R/'.evidence/qyh-host-oid-durable-full-restore-20261013/rehearse.py'
text=path.read_text();lines=text.splitlines();tree=ast.parse(text)
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='fingerprint')
parts.append('\nORIGINAL FULL FINGERPRINT FUNCTION full source SHA '+hashlib.sha256(path.read_bytes()).hexdigest()+'\n'+'\n'.join(lines[node.lineno-1:node.end_lineno]))
material=E/'disposition-live-review-material-r1.txt'
with material.open('x') as stream:stream.write('\n'.join(parts))
relative=str(material.relative_to(R));materials={relative:material.read_text()}
assert len(json.dumps(materials).encode())<=65536,len(json.dumps(materials).encode())
request={'schema':'aos-material-review/v1','request_id':E.name+'-disposition-live-r1','task_id':E.name,
 'owner':'codex-01a13484-f019-7d82-94ce-812396db9124','kind':'quality',
 'baseline':{'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'authority_revision':'AOS-002034',
     'files':{relative:hashlib.sha256(material.read_bytes()).hexdigest()}},
 'claims':['真实API监听及cwd对应最新已提交4e冻源，原Web和原PG卷/StartedAt保持；fresh原650表完整指纹逐表相等，证据不宣称全恢复或经营完成。',
           '原真人org-org/dev-project正式处置SDK由404变200可信空及空命令/外部false，query400与新匿名401、实际canonical价格closure404保留，业务nonGet为空且没有未知登录重放。',
           '三个实际视口的DOM四筛选32px和切换状态已核，最终六份原稿/实际PNG尺寸及SHA已记录并区分无效采集；不宣称全页或八台视觉和真实业务完成。'],
 'materials':materials}
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
g.validate_request(R,request)
with (E/'disposition-live-review-request-r1.json').open('x') as stream:
    json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps({'materialBytes':len(json.dumps(materials).encode()),'all650TablesIncluded':True}))
