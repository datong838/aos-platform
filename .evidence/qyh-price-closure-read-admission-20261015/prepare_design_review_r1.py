from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
parts=['PRE-IMPLEMENTATION DESIGN REVIEW. No product candidate/route admission/deployment yet. Original complete231Goal retained. Review shared codec fixed PRICE entry plus preserved CREATOR behavior, not operating/source/gate authority. Source resolver excerpts explain producer only, GET never invokes them.\n']
for relative in ['services/aos-api/aos_api/ecommerce_workshop_three_module_closure.py',
                 'services/aos-api/aos_api/ecommerce_three_module_closure_readonly.py',
                 'services/aos-api/alembic/versions/w6_009_three_module_closure.py']:
    raw=(R/relative).read_bytes();assert subprocess.check_output(['git','show','HEAD:'+relative])==raw
    parts.append('\nFULL FILE '+relative+' SHA '+hashlib.sha256(raw).hexdigest()+'\n'+raw.decode())
relative='services/aos-api/aos_api/ecommerce_workshop_three_module_closure_store.py'
text=(R/relative).read_text();assert subprocess.check_output(['git','show','HEAD:'+relative])==text.encode()
tree=ast.parse(text);lines=text.splitlines()
parts.append('\nSTORE SELECTED COMPLETE METHODS '+relative+' fullFileSHA '+hashlib.sha256(text.encode()).hexdigest())
names={'__init__','_append','append_closure','_source_row','resolve_domain_items','latest_bindings'}
for node in tree.body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_STATUS' for t in node.targets):
        parts.append('\n'+'\n'.join(lines[node.lineno-1:node.end_lineno]))
    if isinstance(node,ast.ClassDef):
        for child in node.body:
            if isinstance(child,ast.FunctionDef) and child.name in names:
                start=min([child.lineno]+[d.lineno for d in child.decorator_list])-1
                parts.append('\n'+'\n'.join(lines[start:child.end_lineno]))
relative='services/aos-api/aos_api/routers/ecommerce_workshop.py'
text=(R/relative).read_text();lines=text.splitlines();tree=ast.parse(text)
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='get_three_module_closure_contribution_view')
parts.append('\nCURRENT ROUTE '+relative+' fullFileSHA '+hashlib.sha256(text.encode()).hexdigest()+'\n'+'\n'.join(lines[min(d.lineno for d in node.decorator_list)-1:node.end_lineno]))
for name in ['implementation-plan-r1.md','producer-probe-result-r1.json','reader-scope-readback-r1.json']:
    parts.append('\nEVIDENCE '+name+'\n'+(E/name).read_text())
relative=str((E/'design-review-material-r1.txt').relative_to(R));materials={relative:'\n'.join(parts)}
assert len(json.dumps(materials).encode())<=65536,len(json.dumps(materials).encode())
request={'schema':'aos-material-review/v1','request_id':E.name+'-design-r1','task_id':E.name,
 'owner':'codex-01a13484-f019-7d82-94ce-812396db9124','kind':'route',
 'baseline':{'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'authority_revision':'AOS-002035',
             'files':{relative:hashlib.sha256(materials[relative].encode()).hexdigest()}},
 'claims':['方案复用原closure与三binding的typed签名/派生ID/ledger及原五轴合同，新增固定price入口不复制权威引擎；creator正常行为和customer/POST原门保留。',
           '价格专用只读snapshot、SQL尺寸门、strict raw及tenant/module/exact/time/privacy、稳定失败与空命令设计可实施，不把已保存bridge当当前源或预算审批。',
           '额外两个文件已非重叠登记；RED/原producer/creator邻接/原DDL隔离PG/冻结/独立质量/真实SDK650及原稿现场验收明确，未声称代码或经营Goal完成。'],
 'materials':materials}
controller=(R/'.evidence/qyh-price-disposition-read-admission-r2-20261015/review_controller.py').read_text().replace('qyh-price-disposition-read-admission-r2-20261015',E.name)
with (E/'review_controller.py').open('x') as stream:stream.write(controller)
with (R/relative).open('x') as stream:stream.write(materials[relative])
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
g.validate_request(R,request)
with (E/'design-review-request-r1.json').open('x') as stream:
    json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps({'materialBytes':len(json.dumps(materials).encode()),'productChanges':False}))
