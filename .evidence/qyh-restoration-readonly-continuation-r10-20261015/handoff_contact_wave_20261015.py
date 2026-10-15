"""Exact four-scope delivery; all remaining original Goal handed to same owner."""
from pathlib import Path
import datetime
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
sys.path.insert(0,str(R/'scripts/memory'));import memoryctl as m
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
OWNER='codex-01a13484-f019-7d82-94ce-812396db9124';HEAD='0c76d03d2e552b8977e9d647e94cc5a32daf647a';CODE='17164dc7b71bdb897db501d03657741f42c8122b';SIGN='90a601fd1ad2a57c128bf05416dbf97239412865'
def read(p):return json.loads(p.read_text())
def command(*args):return subprocess.check_output(args,cwd=R,text=True).strip()
def save(name,value):
 m.scan_secrets(value)
 with (E/name).open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
def legal(folder,stem,version):
 req=read(folder/f'{stem}-request-{version}.json');env=read(folder/f'{stem}-result-{version}.json');raw=read(folder/f'{stem}-result-{version}.transport.json');record=read(folder/f'{stem}-consumption-{version}.json')
 assert env['result']['verdict']=='PASS' and g.consumption_record(req,env,raw,env['runner_sha256'])==record
assert command('git','rev-parse','HEAD')==HEAD and command('git','branch','--show-current')=='m1'
assert not command('git','diff','--cached','--name-only') and not command('git','diff',CODE,'HEAD','--','services/aos-api','apps/web','scripts','bundles')
legal(R/'.evidence/qyh-customer-start-signing-material-20261015','code-review','r2')
legal(R/'.evidence/qyh-customer-contact-bounded-reader-20261015','code-review','r2')
legal(R/'.evidence/qyh-customer-contact-read-admission-20261015','route-quality','r1')
legal(E,'api-controller-review','r1');legal(E,'contact-live-review','r1')
proof=read(E/'contact-runtime-proof-r1.json');assert proof['all650BeforeAfterEqual'] and proof['actualContactSdk200'] and not proof['wholeGoalComplete']
assert command('lsof','-t','-nP','-iTCP:18080','-sTCP:LISTEN')=='44093' and proof['apiSource'] in command('lsof','-a','-p','44093','-d','cwd','-Fn')
assert command('lsof','-t','-nP','-iTCP:18434','-sTCP:LISTEN')=='89803'
pg=json.loads(command('docker','--context','colima-aos-extension','inspect','qyh-restored-pg-20261011'))[0]
assert pg['Id']==proof['originalContainerId'] and pg['State']['StartedAt']==proof['pgStartedAt'] and pg['Mounts'][0]['Name']==proof['originalVolume']
p=m.DEFAULT_PATHS;a=m.load_authority(p);assert a['project_revision']=='AOS-002037'
ids=['qyh-customer-start-signing-material-20261015','qyh-customer-contact-bounded-reader-20261015','qyh-customer-contact-read-admission-20261015',E.name]
leases=m.load_leases(p)['leases'];rows={}
for tid in ids:
 found=[x for x in leases if x['task_id']==tid];assert len(found)==1;row=rows[tid]=found[0]
 assert row['owner']==OWNER and row['base_revision']=='AOS-002037' and datetime.datetime.fromisoformat(row['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
 for other in leases:
  if other['task_id']!=tid:assert not m.scopes_overlap(row['scope'],other['scope'])
others=[x for x in leases if x['task_id'] not in ids];assert len(others)==38
dwave=next(x for x in rows[ids[2]]['scope'] if x.startswith('docs/'))
changed=['aos-platform/'+x for x in command('git','diff','--name-only','b91134970d94fb1eab83556d3b98c7324711596f','HEAD').splitlines()]+[dwave]
save('contact-handoff-intent-r1.json',dict(head=HEAD,code=CODE,signingCode=SIGN,before='AOS-002037',expected='AOS-002038',tasks=ids,otherLeasesPreserved=38,wholeGoalComplete=False))
results=[
 'ONLY prerequisite Start private-signing-material code contract delivered: new original reason privately persists, public schema/wire/repr unchanged, production UTC typed hash reconstructible, sensitive reason before Store refuses, legacy row not backfilled. Original-volume new Start persistence NOT performed or claimed.',
 'ONLY saved contact readonly reader/tests delivered: verified RR full counts, exact original Start/batch ancestry/policies/reservation/withdrawal/observation, original projection/unknown held, strict metadata-before-bulk/JSON depth/bounds/privacy/error/commands[]/fivefalse. Not current Consent/Receipt/Contact authority.',
 'ONLY canonical customer contact-contributions GET saved-read slice delivered: original genuine SDK200/two saved counts0/latestStart null/ledger0/actual blocker/commands[]/fivefalse,400/401/customer closure404/businessNonGET[]/650 unchanged. Not business/install/fullvisual/fullGoal completion.',
 'SAME_OWNER_HANDOFF of ALL original remaining restoration/full231Goal/sole original human authorization/daily and every actual aos latest original-volume fullPG/API/Web; aos2 noRestart. Only this contact saved-read slice plus signing code contract verified. Current API44093/source17164, Web89803/f036, originalPGStarted20:36:36/schema161/650/bindings0 supersede older identities. FullC/user final budget/deployment/naturalbusiness/install/eightvisual/observe release remain.']
risks=['All original full231Goal business/install/eight real scenarios/fullvisual/observe release remain; FullC sole genuine user final budget/original deployment still separate.',
 'Original DB readonly/HostworkerProviderOFF; unknownold12/disabledSchedule/source/noPush retained. Original production Start and ActionReceipt resolvers remain unavailable; saved typed references never operating approval.',
 'Actual original contact rows empty; private reason persistence/nonempty/unknown/manual fixtures only in isolated PG. Legacy Start missing reason fails closed, never guessed/backfilled/replayed. Customer task/log/artifacts/footer wording, creator1280 crop, Page fake0 and other fullvisual remain.']
verification=[
 'Design/source/fresh reader r2/route r1/controller r1/live r1 PASS exact legal consumption. Historical NEED, expired pre-request draft, r1 old source PASS and corrected CID preflight failure preserved, not relabeled or replayed.',
 'Prerequisite RED8fail1pass/20 targeted/frozen407/native W6-008 actual Store/private roundtrip/public FastAPI output; current reader55 plus deep JSON RED fix/frozen482 only4 owned overlays, no user dirty copied.',
 'Original W6-007/008 owned tmpfs native empty SUM NULL/snapshot saved revision1->2/old exact policy/RLS/25006/SQLCASE/metadata budget before bulk/real1100 JSON decoder refused; accurateCID stopped, original volume untouched.',
 'Original unique genuine me/customer contact SDK200/two counts0/latest null/ledger0/commands[]/fivefalse/query400/anonymous401/customer closure404/businessNonGET[]; full650 before-after dictionaries identical.',
 'Current 3 viewports four tabs/four filters32/no horizontal overflow; 6 actual/reference CSS-sized PNGs individually inspected; candid visual gaps preserved, no nonempty/a11y/fullvisual/Goal completion claim.']
for tid,result in zip(ids,results):
 files=[x for x in changed if any(x==s or x.startswith(s.rstrip('/')+'/') for s in rows[tid]['scope'])];assert files
 receipt=m.complete_task(p,task_id=tid,expected_revision='AOS-002037',result=result,changed_files=files,commits=[SIGN,CODE,HEAD],verification=verification,risks=risks,blockers=[])
 save(tid+'-delivery-copy-r1.json',receipt)
incomplete=[x.replace('Customer contact/closure auxiliary GET remain unreviewed legacy;','Customer closure auxiliary GET remains unreviewed legacy;').replace('customer contact/closure private helpers remain individually pending.','customer closure private helper remains individually pending.').replace('Customer contact/closure helpers still legacy;','Customer closure helper still legacy;') for x in a['incomplete']]
new=m.update_authority(p,expected_revision='AOS-002037',current_phase='Customer saved contact read slice and private signing code contract delivered; genuine SDK200/original650 unchanged; full231Goal ACTIVE',delivery_status='ONLY signing code contract/contact reader+GET saved-read slices plus ALL remaining maintenance handoff; full business/install/eightvisual/release incomplete',
 last_green_gate='Signing90a601/code17164/frozen482/nativeW6-007008/code-controller-live PASS legal; API44093/source17164, Web89803/f036 and original650 unchanged; saved SDK/read/deny/3viewport geometry only',next_gate='Customer closure auxiliary GET original compiler/Store/source/private reason/typed signatures/snapshot/bounds audit before independent plan/admission; all original budget/naturalbusiness/install/visual goals retained',
 completed=[*a['completed'],'Only customer contact saved canonical GET and bounded reader plus private signing material code contract delivered. Original genuine org-org/dev-project SDK200/two counts0/latest null/ledger0/commands[]/fivefalse/400/401/customer closure404/650 unchanged. No actual original-volume Start write, current Consent/Contact/Receipt or full Goal completion.'],
 incomplete=[*incomplete,'Customer closure helper still legacy. Original fullC sole user final budget/original deployment/natural sourced business/install lifecycle/eight real scenarios/all visual/continuous release remain; current customer task/log/artifacts/footer wording, Page fake0/creator1280 crop/other gaps explicit.'],next_steps=[*a['next_steps'],'Continue newly registered customer closure saved contribution audit individually; do not bulk whitelist helpers. Preserve daily/every actual aos latest m1 original-volume fullPGAPIWeb, aos2 noRestart and full original Goal.'],
 source_commits={**a['source_commits'],'qyh-customer-start-signing-code':SIGN,'qyh-customer-contact-code':CODE,'qyh-customer-contact-live':HEAD},hard_boundaries=a['hard_boundaries'],evidence=[*a['evidence'],
 {'path':'aos-platform/.evidence/qyh-restoration-readonly-continuation-r10-20261015/contact-live-review-consumption-r1.json','summary':'Exact saved contact read/current identity/source650/geometry slice PASS legally consumed, no current Consent/Contact/Receipt or fullGoal authorization.'},
 {'path':'aos-platform/.evidence/qyh-restoration-readonly-continuation-r10-20261015/contact-live-report-r1.md','summary':'Actual original contact SDK200 and empty facts, zero effects, unchanged650, six current CSS-sized screenshot comparison and all remaining visual/business goals.'}])
assert new['project_revision']=='AOS-002038';save('contact-authority-update-r1.json',dict(before='AOS-002037',after='AOS-002038',wholeGoalComplete=False))
with m.memory_lock(p,exclusive=True):
 projection=m.canonical_projection(m.load_authority(p));prime=[]
 for item in m.load_manifest(p)['projections']:
  if item.get('consistency')!='strong':continue
  if item['adapter']=='prime_harness':prime.append(item);continue
  path=m.expand_path(item['path'],p)
  if item['adapter']=='authority_frontmatter':desired=m.render_frontmatter(path.read_text() if path.exists() else '',projection)
  elif item['adapter']=='json_file':desired=json.dumps(m.projection_document(projection),ensure_ascii=False,indent=2,sort_keys=True)+'\n'
  else:raise AssertionError('Unexpected strong adapter')
  m.scan_secrets(desired);m.atomic_write_text(path,desired)
 m.sync_prime(p,projection,prime)
status=m.memory_status(p);assert all(x['status']=='CURRENT' for x in status['projections'] if x['consistency']=='strong')
save('contact-strong-memory-status-r1.json',status)
old=rows[E.name];expiry='2026-10-15T16:00:00+00:00'
maintenance=m.start_task(p,task_id='qyh-restoration-readonly-continuation-r11-20261015',owner=OWNER,expected_revision='AOS-002038',scope=[*old['scope'],'aos-platform/.evidence/qyh-restoration-readonly-continuation-r11-20261015'],excluded_scope=old['excluded_scope'],expected_outputs=[*old['expected_outputs'],'ALL original remaining231Goal/sole human authorization retained. Current runtime supersedes all older identities: API44093/source17164,Web89803/f036,originalPGStarted20:36:36/schema161/650/bindings0. Only contact saved-read and signing code contract delivered; fullC/user final budget/deployment/naturalbusiness/install/eightvisual/observe release remain; daily/every actual aos latest original-volume fullPGAPIWeb and aos2 noRestart.'],lease_expires_at=expiry)
next_task=m.start_task(p,task_id='qyh-customer-closure-read-admission-20261015',owner=OWNER,expected_revision='AOS-002038',scope=['aos-platform/services/aos-api/aos_api/routers/ecommerce_workshop.py','aos-platform/services/aos-api/tests/test_ecommerce_workshop_read_http.py',dwave,'aos-platform/.evidence/qyh-customer-closure-read-admission-20261015'],excluded_scope=rows[ids[2]]['excluded_scope'],expected_outputs=['Full231Goal/sole original human authorization retained. Audit canonical customer closure saved contribution GET original compiler/Store/customer source/private signing data/DTO/tenant/privacy/same cutoff/limits before independent design; no compile/bind/consume/current Contact/Consent/Receipt authority.', 'Register any additional shared reader/test/Web files before coding. Frozen/native/genuine SDK/650/original visual/live independent reviews and accurate Delivery, no copied whitelist/source/oldRun or operating approval expansion.'],lease_expires_at=expiry)
after=m.load_leases(p)['leases'];assert [x for x in after if x['task_id'] not in [maintenance['task_id'],next_task['task_id']]]==others
for row in [maintenance,next_task]:
 assert row in after and row['owner']==OWNER
 for other in after:
  if other['task_id']!=row['task_id']:assert not m.scopes_overlap(row['scope'],other['scope'])
save('contact-next-wave-readback-r1.json',dict(authority='AOS-002038',maintenance=maintenance,nextTask=next_task,owner=OWNER,otherLeasesPreserved=38,nonOverlapping=True,strongCurrent=7,personalMemoryWrites=False,wholeGoalComplete=False))
print(json.dumps(dict(authority='AOS-002038',slicesDelivered=3,maintenanceAllRemainingHandoff=True,otherLeasesPreserved=38,strongCurrent=7,nextTask=next_task['task_id'],goal='ACTIVE')))
