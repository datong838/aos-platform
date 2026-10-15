from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
R=Path(__file__).resolve().parents[2]
E=Path(__file__).resolve().parent
task=E.name
old=R/'.evidence/qyh-price-contribution-read-admission-20261015/review_controller.py'
controller=E/'review_controller.py'
with controller.open('x') as stream:
    stream.write(old.read_text().replace('qyh-price-contribution-read-admission-20261015',task))
parts=['Stage: PRE-IMPLEMENTATION design gate. No candidate code, native PG, live deployment or completion claim yet. Review whether this complete plan is safe and compatible enough to implement; future tests are exit criteria, not claimed evidence.\n']
files=['services/aos-api/aos_api/ecommerce_workshop_price_disposition.py',
       'services/aos-api/aos_api/ecommerce_workshop_price_disposition_store.py',
       'services/aos-api/alembic/versions/w6_006_price_disposition.py']
for relative in files:
    raw=(R/relative).read_bytes()
    assert subprocess.check_output(['git','show','HEAD:'+relative])==raw
    parts.append('\nFILE '+relative+' SHA256 '+hashlib.sha256(raw).hexdigest()+'\n'+raw.decode())
db=R/'services/aos-api/aos_api/db.py'
parts.append('\nDB connection implementation excerpt (full file hash '+hashlib.sha256(db.read_bytes()).hexdigest()+')\n'+'\n'.join(db.read_text().splitlines()[:118]))
for name in ['bounded-read-design-r1.md','producer-probe-result-r1.json','implementation-scope-readback-r1.json']:
    parts.append('\nEVIDENCE '+name+'\n'+(E/name).read_text())
package=E/'design-review-material-r1.txt'
with package.open('x') as stream:stream.write('\n'.join(parts))
relative=str(package.relative_to(R))
materials={relative:package.read_text()}
assert len(json.dumps(materials).encode())<=65536, len(json.dumps(materials).encode())
request={'schema':'aos-material-review/v1','request_id':task+'-design-r1','task_id':task,
 'owner':'codex-01a13484-f019-7d82-94ce-812396db9124','kind':'route',
 'baseline':{'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'authority_revision':'AOS-002034',
             'files':{relative:hashlib.sha256(package.read_bytes()).hexdigest()}},
 'claims':[
  '该方案保持原四类处置producer签名、完整修订计数及观察exact关联，不将保存引用当当前运行授权；共享纯规则提取不改变writer行为。',
  '该方案在单一只读snapshot内先元数据限额再SQL有界payload，全部失败关闭，能够在实施阶段消除跨截止面及错误补零风险。',
  '文件归属、独立门禁与后续原生产兼容测试和真实只读验收明确；这是实施前方案审查，不宣称候选代码、现场或完整Goal完成。'],
 'materials':materials}
sys.path.insert(0,str(R/'scripts/long-task-watchdog'))
import aos_review as g
g.validate_request(R,request)
target=E/'design-review-request-r1.json'
with target.open('x') as stream:
    json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps({'materialBytes':len(json.dumps(materials).encode()),'request':str(target.relative_to(R))}))
