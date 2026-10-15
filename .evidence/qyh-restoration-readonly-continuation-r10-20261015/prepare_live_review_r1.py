from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
parts=['POST-EFFECT LIVE QUALITY ONLY: original genuine customer contact saved-read slice. Full231Goal ACTIVE, not operating authority. Implementer inspected6 new PNGs pairwise; geometry/dimensions/SHA supplied. Do not claim this text-only reviewer saw PNG pixels or fullvisual/nonempty/a11y/business completion.']
for name in ['contact-live-report-r1.md','verify_contact_runtime_r1.py','contact-runtime-proof-r1.json','contact-native-identity-sdk-r1.json','contact-live-shas-r1.json','api-preflight-r1.json','preflight-terminal-cid-mismatch-r0.json','pre-effect-gate-deny-result-r1.json','api-switch-intent-r1.json','api-started-r1.json']:
 parts.append('\nEVIDENCE '+name+'\n'+(E/name).read_text())
for name in ['contact-full650-comparison-r1.json','contact-native-geometry-deny-r1.json']:
 path=E/name;value=json.loads(path.read_text())
 if name.startswith('contact-full650'):
  assert len(value['tableEquality'])==650 and all(value['tableEquality'].values());value={k:v for k,v in value.items() if k!='tableEquality'};value['all650EntriesVerifiedTrue']=True
 else:
  value={'metrics':[dict(width=x['width'],height=x['height'],geometry=x['geometry'],tabSelectedCounts=[len(y) for y in x['tabs']],tabUniqueCount=len({y[0] for y in x['tabs']}),filters=x['filters']) for x in value['metrics']], 'trace':value['trace'],'businessNonGet':value['businessNonGet'],'temporaryViewportCleared':value['temporaryViewportCleared'],'normalAuthPosts':value['normalAuthPosts']}
 parts.append('\nBOUNDED EVIDENCE '+name+' fullRawSHA '+hashlib.sha256(path.read_bytes()).hexdigest()+'\n'+json.dumps(value,ensure_ascii=False))
for folder,stem,version in [(R/'.evidence/qyh-customer-start-signing-material-20261015','code-review','r2'),(R/'.evidence/qyh-customer-contact-bounded-reader-20261015','code-review','r2'),(R/'.evidence/qyh-customer-contact-read-admission-20261015','route-quality','r1'),(E,'api-controller-review','r1')]:
 request=folder/f'{stem}-request-{version}.json';result=folder/f'{stem}-result-{version}.json';transport=result.with_suffix('.transport.json');consumption=folder/f'{stem}-consumption-{version}.json'
 req=json.loads(request.read_text());env=json.loads(result.read_text());raw=json.loads(transport.read_text());record=json.loads(consumption.read_text())
 assert env['result']['verdict']=='PASS' and g.consumption_record(req,env,raw,env['runner_sha256'])==record
 parts.append('\nACTUAL CODE/CONTROLLER GATE, exact consumption independently recomputed\n'+json.dumps(dict(task=req['task_id'],kind=req['kind'],verdict=env['result']['verdict'],resultFile=str(result.relative_to(R)),resultSha=hashlib.sha256(result.read_bytes()).hexdigest(),transportSha=hashlib.sha256(transport.read_bytes()).hexdigest(),consumption=record)))
for name in ['source-verification-r2.json','native-r2-stopped.json']:
 parts.append('\nREADER EVIDENCE '+name+'\n'+(R/'.evidence/qyh-customer-contact-bounded-reader-20261015'/name).read_text())
proof=json.loads((E/'contact-runtime-proof-r1.json').read_text());assert proof['all650BeforeAfterEqual'] and proof['actualContactSdk200'] and not proof['wholeGoalComplete']
material=E/'contact-live-review-material-r1.txt';relative=str(material.relative_to(R));materials={relative:'\n'.join(parts)};size=len(json.dumps(materials).encode());assert size<=65536,size
request=dict(schema='aos-material-review/v1',request_id=E.name+'-contact-live-r1',task_id=E.name,owner='codex-01a13484-f019-7d82-94ce-812396db9124',kind='quality',
 baseline=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),authority_revision='AOS-002037',files={relative:hashlib.sha256(materials[relative].encode()).hexdigest()}),
 claims=['修正前CID误替换预检安全拒绝且无效果、修正后真实预检与缺审负向/独立controller PASS合法消费后仅一次新意图API更新；实际44093/cwd17164、Web89803/f036与原PG同CID卷StartedAt及650完整前后全等支持本保存读取现场。',
 '原唯一真人同租户正式contact SDK200保留两可信保存计数0/latest null/ledger0/真实blocker/commands[]/五false，query400/匿名401/customer closure404/业务nonGET[]；不将隔离持久化、保存typed Receipt或空视图当当前Consent/Contact或经营准入。',
 '实际三视口页签筛选几何与六图尺寸hash、实施者逐图检视和明确视觉差距只支持当前空态读取slice，未声称非空/a11y/八台或完整Goal完成；daily每次aos原卷full重启、唯一真人最终预算/部署/自然经营/安装与全部remaining保持。'],materials=materials)
with material.open('x') as stream:stream.write(materials[relative])
g.validate_request(R,request)
with (E/'contact-live-review-request-r1.json').open('x') as stream:json.dump(request,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps(dict(materialBytes=size,wholeGoalComplete=False)))
