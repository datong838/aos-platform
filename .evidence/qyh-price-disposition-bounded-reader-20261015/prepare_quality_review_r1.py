from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
parent=R/'.evidence/qyh-price-disposition-read-admission-r2-20261015'
controller=E/'review_controller.py'
with controller.open('x') as stream:
    stream.write((parent/'review_controller.py').read_text().replace(parent.name,E.name))
parts=['CODE QUALITY GATE: current candidate, not deployed and no operating approval. Original daily/full Goal remains. Read all supplied source; plan PASS is not code proof. Historical migration-head test failed (w6_009 expected/a0v_162 actual), unchanged migration/test; raw failure retained, no migration or claim that it passed.\n']
for relative in ['services/aos-api/aos_api/ecommerce_price_disposition_readonly.py',
                 'services/aos-api/aos_api/ecommerce_workshop_price_disposition.py',
                 'services/aos-api/tests/aip/test_ecommerce_price_disposition_readonly.py']:
    raw=(R/relative).read_bytes()
    parts.append('\nFILE '+relative+' SHA256 '+hashlib.sha256(raw).hexdigest()+'\n'+raw.decode())
relative='services/aos-api/tests/aip/test_w6_06_price_disposition.py'
text=(R/relative).read_text();tree=ast.parse(text)
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='test_shared_saved_disposition_rules_preserve_original_producer')
lines=text.splitlines();start=min([node.lineno]+[d.lineno for d in node.decorator_list])-1
parts.append('\nNEW SHARED RULE TEST '+relative+' fullfileSHA '+hashlib.sha256(text.encode()).hexdigest()+'\n'+'\n'.join(lines[start:node.end_lineno]))
diff=subprocess.check_output(['git','diff','--','services/aos-api/aos_api/ecommerce_workshop_price_disposition.py'],text=True)
parts.append('\nEXACT SERVICE DIFF\n'+diff)
for path in [E/'native-r1-result.json',E/'native-r1-stopped.json',E/'source-verification-r1.json']:
    parts.append('\nEVIDENCE '+path.name+'\n'+path.read_text())
log=E/'green-frozen-cumulative-r1.log'
parts.append('\nFULL RAW FROZEN LOG SHA '+hashlib.sha256(log.read_bytes()).hexdigest()+'\n'+log.read_text())
parts.append('\nPLAN SHA '+hashlib.sha256((parent/'bounded-read-design-r1.md').read_bytes()).hexdigest()+'; route PASS legally consumed. Router has separate parent quality gate still pending; implementation PASS cannot deploy.\n')
material=E/'code-review-material-r1.txt'
with material.open('x') as stream:stream.write('\n'.join(parts))
relative=str(material.relative_to(R));materials={relative:material.read_text()}
assert len(json.dumps(materials).encode())<=65536,len(json.dumps(materials).encode())
request={'schema':'aos-material-review/v1','request_id':E.name+'-code-r1','task_id':E.name,
    'owner':'codex-01a13484-f019-7d82-94ce-812396db9124','kind':'quality',
    'baseline':{'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'authority_revision':'AOS-002034',
        'files':{relative:hashlib.sha256(material.read_bytes()).hexdigest()}},
    'claims':[
        '候选reader只在同一已核实READ ONLY REPEATABLE READ连接中按固定四表读取，元数据行数和总字节先门控，SQLCASE载荷及截止面保持完整有界计数，失败不补零。',
        '候选reader核对原typed绑定哈希、prepared与frozen完整继承、case和contract以及观察exact关系、严格字段和隐私；保存gate及receipt不构成当前授权。',
        '原service变更只提取原kind分类纯规则，未改写入准入、resolver、签名或幂等；原producer兼容测试及冻结267项和隔离原W6DDL物证支持候选质量，未声称现场或整体Goal完成。'],
    'materials':materials}
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
g.validate_request(R,request)
with (E/'code-review-request-r1.json').open('x') as stream:
    json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps({'materialBytes':len(json.dumps(materials).encode()),'task':E.name}))
