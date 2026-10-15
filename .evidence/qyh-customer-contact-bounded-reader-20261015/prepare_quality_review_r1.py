from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1];P=R/'.evidence/qyh-customer-contact-read-admission-20261015'
parts=['CURRENT READER CODE QUALITY, not deployed. Full231Goal ACTIVE. Canonical saved contact view only, never current Consent/ActionReceipt/Contact or send admission. A typed saved receipt ref does not assert current production resolver enabled. Original signed Start is validated BEFORE its original contribution projection; projected items keep original hash and are not claimed a new signed Start.']
for rel in ['services/aos-api/aos_api/ecommerce_customer_contact_readonly.py','services/aos-api/tests/test_ecommerce_customer_contact_readonly.py']:
 raw=(R/rel).read_bytes();parts.append('\nFULL FILE '+rel+' SHA '+hashlib.sha256(raw).hexdigest()+'\n'+raw.decode())
rel='services/aos-api/aos_api/ecommerce_workshop_customer_contact.py';raw=(R/rel).read_bytes();assert subprocess.check_output(['git','show','HEAD:'+rel],cwd=R)==raw
parts.append('\nORIGINAL PRODUCER COMPLETE SELECTED FUNCTIONS '+rel+' fullFileSHA '+hashlib.sha256(raw).hexdigest())
tree=ast.parse(raw.decode());lines=raw.decode().splitlines()
names={'start_batch','record_dispatch_observation','contribution_view','_ledger','customer_start_signing_hash','customer_start_authority_data'}
for node in tree.body:
 nodes=node.body if isinstance(node,ast.ClassDef) else [node]
 for child in nodes:
  if isinstance(child,ast.FunctionDef) and child.name in names:
   begin=min([child.lineno]+[d.lineno for d in child.decorator_list])-1
   parts.append('\n'+'\n'.join(lines[begin:child.end_lineno]))
plan=P/'implementation-plan-r2.md'
parts.append('\nPLAN BOUNDED CONTRACT, fullPlanSHA '+hashlib.sha256(plan.read_bytes()).hexdigest()+'''\nOne verified readonly RR snapshot/cutoff; complete saved frequency revisions and withdrawal observations COUNT, not active/unique customers. Invalid/future aggregates reject, not filter. Original exact frozen Batch+prepared and4 policies via existing pure lifecycle validation. Original typed Start/private reason/UTC hash/derived ID/eligible coverage/ref lineage, saved reservation and skip witness, typed permit/attempt/outbox/zero effects. Dispatch observation original request hash/exact original start+observable item/date/state/manual resolution before original service projection. No current authority resolvers invoked. Metadata phase proves bounds BEFORE payload queries: 1MiB each/8MiB total/1280 rows/1000 items/256 observations (257 reject), statement3s/lock0.5s/monotonic10s between queries AND decode loops. Strict raw/no coercion, tenant/time/privacy, stable503 not fake0/null, commands[]/fivefalse. Original legacy/POST untouched, full reader route/runtimeSDK650/visual/live gates still required.\n''')
for path in [P/'design-review-consumption-r1.json',E/'source-verification-r1.json',E/'native-r1-stopped.json']:
 parts.append('\nEVIDENCE '+str(path.relative_to(R))+'\n'+path.read_text())
native=E/'native-r1-result.json';value=json.loads(native.read_text());facts=value.pop('connectionFacts')
value['connectionFactCount']=len(facts);value['uniqueConnectionFacts']=list({json.dumps(x,sort_keys=True):x for x in facts}.values())
parts.append('\nNATIVE ACTUAL RESULT fullRawSHA '+hashlib.sha256(native.read_bytes()).hexdigest()+'\n'+json.dumps(value))
for name in ['red-r1.log','green-r2.log','green-frozen-cumulative-r1.log']:
 path=E/name;parts.append('\nRAW LOG '+name+' SHA '+hashlib.sha256(path.read_bytes()).hexdigest()+'\n'+'\n'.join(path.read_text().splitlines()[-3:]))
proof=json.loads((E/'source-verification-r1.json').read_text());assert proof['returncode']==0
assert proof['sourceAfter']=={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in proof['sourceAfter']}
material=E/'code-review-material-r1.txt';relative=str(material.relative_to(R));materials={relative:'\n'.join(parts)}
size=len(json.dumps(materials).encode());assert size<=65536,size
request=dict(schema='aos-material-review/v1',request_id=E.name+'-code-r1',task_id=E.name,owner='codex-01a13484-f019-7d82-94ce-812396db9124',kind='quality',
 baseline=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),authority_revision='AOS-002037',files={relative:hashlib.sha256(materials[relative].encode()).hexdigest()}),
 claims=['读取器在核实同一只读RR截止面保留两完整COUNT，metadata阶段先证明行数/单行/总字节再查询payload，固定参数化SQL/超界/时间/稳定失败门符合方案，不把异常补零/null或截断冒充完整。',
 '原Start/private reason/UTC typed hash及exact Batch/policy/eligible coverage/各binding、保存reservation/withdrawal/observation按原producer核验，再复用原贡献投影保留unknown held/原hash/原对象；strict raw/隐私/零效果/空命令和五false，不授当前Contact/Consent/Receipt权限。',
 '原producer组合非空与重新hash伪造负向55项、四owned overlay冻结481及原W6-007/008临时PG真快照/计数/RLS/25006/SQLCASE/metadata前置总量门且准确CID已停支持该候选，尚未部署、不宣称经营/八台视觉或完整Goal完成。'],materials=materials)
controller=(P/'review_controller.py').read_text().replace(P.name,E.name)
with (E/'review_controller.py').open('x') as stream:stream.write(controller)
with material.open('x') as stream:stream.write(materials[relative])
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g;g.validate_request(R,request)
with (E/'code-review-request-r1.json').open('x') as stream:
 json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps(dict(materialBytes=size,sourceUnchangedSinceFrozen481=True)))
