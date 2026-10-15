"""Supported exact slice deliveries and full remaining Goal same-owner handoff."""
from pathlib import Path
import datetime
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
sys.path.insert(0,str(R/'scripts/memory'));import memoryctl as m
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
OWNER='codex-01a13484-f019-7d82-94ce-812396db9124';HEAD='43b60dfed6df62f5ef69200dea9d183d9ff42a5e';CODE='80b39a1a8d5f7b76e942c7005e8d4086980d215f'
def read(p):return json.loads(p.read_text())
def command(*args):return subprocess.check_output(args,cwd=R,text=True).strip()
def save(name,value):
 m.scan_secrets(value)
 with (E/name).open('x') as stream:
  json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
def legal(folder,prefix,version):
 req=read(folder/f'{prefix}-request-{version}.json');env=read(folder/f'{prefix}-result-{version}.json')
 transport=read(folder/f'{prefix}-result-{version}.transport.json');record=read(folder/f'{prefix}-consumption-{version}.json')
 assert env['result']['verdict']=='PASS' and g.consumption_record(req,env,transport,env['runner_sha256'])==record
assert command('git','rev-parse','HEAD')==HEAD and command('git','branch','--show-current')=='m1'
assert not command('git','diff','--cached','--name-only') and not command('git','diff',CODE,'HEAD','--','apps/web','services/aos-api','scripts','bundles')
legal(R/'.evidence/qyh-customer-contribution-read-admission-20261015','route-quality','r1')
legal(R/'.evidence/qyh-customer-lifecycle-bounded-reader-20261015','code-review','r1')
legal(E,'api-controller-review','r1');legal(E,'customer-live-review','r2')
proof=read(E/'customer-runtime-proof-r1.json');assert proof['all650BeforeAfterEqual'] and proof['actualCustomerSdk200'] and not proof['wholeGoalComplete']
assert command('lsof','-t','-nP','-iTCP:18080','-sTCP:LISTEN')=='15265' and proof['apiSource'] in command('lsof','-a','-p','15265','-d','cwd','-Fn')
assert command('lsof','-t','-nP','-iTCP:18434','-sTCP:LISTEN')=='89803'
pg=json.loads(command('docker','--context','colima-aos-extension','inspect','qyh-restored-pg-20261011'))[0]
assert pg['Id']==proof['originalContainerId'] and pg['State']['StartedAt']==proof['pgStartedAt'] and pg['Mounts'][0]['Name']==proof['originalVolume']
p=m.DEFAULT_PATHS;a=m.load_authority(p);assert a['project_revision']=='AOS-002036'
ids=['qyh-customer-contribution-read-admission-20261015','qyh-customer-lifecycle-bounded-reader-20261015',E.name]
leases=m.load_leases(p)['leases'];rows={}
for tid in ids:
 found=[x for x in leases if x['task_id']==tid];assert len(found)==1;row=rows[tid]=found[0]
 assert row['owner']==OWNER and row['base_revision']=='AOS-002036' and datetime.datetime.fromisoformat(row['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
 for other in leases:
  if other['task_id']!=tid:assert not m.scopes_overlap(row['scope'],other['scope'])
others=[x for x in leases if x['task_id'] not in ids];assert len(others)==38
dwave=next(x for x in rows[ids[0]]['scope'] if x.startswith('docs/'))
changed=['aos-platform/'+x for x in command('git','diff','--name-only','7385617635ab7331483ad6e891e8bf5e089839e5','HEAD').splitlines()]+[dwave]
save('customer-handoff-intent-r1.json',dict(head=HEAD,code=CODE,before='AOS-002036',expected='AOS-002037',tasks=ids,otherLeasesPreserved=38,wholeGoalComplete=False))
results=[
 'ONLY canonical customer contributions GET saved-evidence readonly slice delivered: genuine SDK200/four saved revision counts0/latestBatch null/two actual authorization gaps/commands[]/fourfalse; 400/401/contact and closure404/650 unchanged. Not current Consent/Contact or fullGoal completion.',
 'ONLY dedicated customer saved snapshot reader/tests delivered: complete saved revision COUNT semantics, bounded exact Batch/ancestor/policies, original typed hashes/ledger/lineage/unknown/privacy/errors; synthetic producer/native PG not production authority.',
 'SAME_OWNER_HANDOFF of ALL original remaining restoration/full231Goal/user authorization/daily and every aos latest original-volume fullPG/API/Web. Only this customer saved-read slice verified; current API15265/source80b39, Web89803/f036, originalPGStarted20:36:36/schema161/650/bindings0. FullC/user final budget/deployment/natural business/install/eightvisual/observe release remain.']
risks=['FullC sole genuine human final budget/original deployment/natural sourced business chain/install lifecycle/eight real scenarios/all visual/continuous release remain incomplete.',
 'Original DB readonly/HostworkerProviderOFF; unknownold12/disabledSchedule/source/noPush boundaries retained; original production external policy resolver remains unavailable.',
 'Original saved customer counts empty; synthetic nonempty fixture is not actual consent. Current six readiness cards/plan sidebar differ from reference task/log/artifacts, navigation density and empty-state footer wording pending; no fullvisual/a11y acceptance.']
for tid,result in zip(ids,results):
 files=[x for x in changed if any(x==s or x.startswith(s.rstrip('/')+'/') for s in rows[tid]['scope'])];assert files
 receipt=m.complete_task(p,task_id=tid,expected_revision='AOS-002036',result=result,changed_files=files,commits=[CODE,HEAD],verification=[
  'Design r1/reader code r1/route r1/controller r1/live r2 PASS and exact legal consumption; live oversize package rejected before request/attempt, preserved.',
  'Frozen387 only four owned overlays; original producer exact refs/typed ledger hash/prepare freeze inheritance/unknown; original W6-07 and adjacent price/closure/catalog regression.',
  'Owned tmpfs original w6_007 native saved revision snapshot1->2/old exact rev1/RLS/25006/SQLCASE/privacy/invalid metadata/timestamps/future refusal; accurateCID stopped, original volume untouched.',
  'Original genuine me and customer SDK200/four saved counts0/latest null/commands[]/fourfalse/query400/anonymous401/contact and closure404/businessNonGet[]; original650 full before-after equal.',
  'Three viewport four tabs/four filters/32px/no horizontal overflow, six actual/reference CSS-sized screenshots inspected; visual differences and nonempty/a11y/wholeGoal gaps explicit.'],risks=risks,blockers=[])
 save(tid+'-delivery-copy-r1.json',receipt)
incomplete=[x.replace('Customer contribution/contact/closure auxiliary GET remain unreviewed legacy;','Customer contact/closure auxiliary GET remain unreviewed legacy;').replace('Price dispositions and closure/customer contribution/contact/closure private helpers remain individually pending.','Saved price dispositions/closure and customer contributions delivered; customer contact/closure private helpers remain individually pending.') for x in a['incomplete']]
new=m.update_authority(p,expected_revision='AOS-002036',current_phase='Customer saved contributions readonly slice delivered; genuine SDK200 and original650 unchanged; full231Goal ACTIVE',delivery_status='ONLY customer root/reader saved-read slices plus ALL remaining maintenance handoff; full business/install/eightvisual/release incomplete',
 last_green_gate='Code80b39 four files/frozen387/nativeW6_007/code-controller-live PASS legal; API15265/source80b39, Web89803/f036 and original650 unchanged; actual SDK/read/deny/three viewport geometry only',
 next_gate='Customer contact-contributions auxiliary GET original producer/Store/DTO/privacy/consent/frequency/bounded cutoff audit before plan/admission; no ProtectedContact or dispatch; full original Goal retained',
 completed=[*a['completed'],'Only canonical customer saved contributions GET and bounded reader delivered: original genuine org-org/dev-project SDK200/four saved counts0/latest null/commands[]/fourfalse/400/401/contact and closure404/650 unchanged. Supersedes customer contribution legacy404 only, no current consent or contact authority.'],
 incomplete=[*incomplete,'Customer contact/closure helpers still legacy; customer full nonempty task/log/artifacts and footer wording, Page fake0/creator1280 crop/other fullvisual, all original fullC/userbudget/deployment/naturalbusiness/install/observe release remain.'],
 next_steps=[*a['next_steps'],'Continue registered customer contact saved contribution read audit, one helper at a time, plus full visual gaps. Daily/every actual aos latest original-volume fullPGAPIWeb and aos2 noRestart retained.'],
 source_commits={**a['source_commits'],'qyh-customer-contribution-code':CODE,'qyh-customer-contribution-live':HEAD},hard_boundaries=a['hard_boundaries'],evidence=[*a['evidence'],
 {'path':'aos-platform/.evidence/qyh-restoration-readonly-continuation-r9-20261015/customer-live-review-consumption-r2.json','summary':'Exact customer saved read/identity/source650/geometry slice PASS legally consumed, no business/current Consent/Contact/fullGoal authorization.'},
 {'path':'aos-platform/.evidence/qyh-restoration-readonly-continuation-r9-20261015/customer-live-report-r1.md','summary':'Genuine customer SDK200, original650 equality, six CSS-sized screenshots inspected and full remaining business/install/visual objectives.'}])
assert new['project_revision']=='AOS-002037';save('customer-authority-update-r1.json',dict(before='AOS-002036',after='AOS-002037',wholeGoalComplete=False))
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
save('customer-strong-memory-status-r1.json',status)
old=rows[E.name];expiry='2026-10-15T08:00:00+00:00'
maintenance=m.start_task(p,task_id='qyh-restoration-readonly-continuation-r10-20261015',owner=OWNER,expected_revision='AOS-002037',scope=[*old['scope'],'aos-platform/.evidence/qyh-restoration-readonly-continuation-r10-20261015'],excluded_scope=old['excluded_scope'],expected_outputs=[*old['expected_outputs'],'ALL remaining original231Goal/user authorization retained. Current runtime supersedes all older identities: API15265/source80b39,Web89803/f036,originalPGStarted20:36:36/schema161/650/bindings0. Only saved customer contributions delivered; fullC/user final budget/deployment/naturalbusiness/install/eightvisual/observe release continue; daily/every actual aos original-volume latest fullPGAPIWeb and aos2 noRestart.'],lease_expires_at=expiry)
next_task=m.start_task(p,task_id='qyh-customer-contact-read-admission-20261015',owner=OWNER,expected_revision='AOS-002037',scope=['aos-platform/services/aos-api/aos_api/routers/ecommerce_workshop.py','aos-platform/services/aos-api/tests/test_ecommerce_workshop_read_http.py',dwave,'aos-platform/.evidence/qyh-customer-contact-read-admission-20261015'],excluded_scope=rows[ids[0]]['excluded_scope'],expected_outputs=['Full231Goal/original authorization retained. Audit canonical customer/contact-contributions original producer/Store/DTO/privacy/consent/frequency/current authority/bounded same cutoff before design Prime/admission; never resolve ProtectedContact or dispatch/send.', 'Any extra reader/test/Web/shared files separately register before code. Frozen/native/genuine SDK/650/original visuals/independent reviews and accurate Delivery mandatory; no copied whitelist or reuse installation as unrelated budget authority.'],lease_expires_at=expiry)
after=m.load_leases(p)['leases'];assert [x for x in after if x['task_id'] not in [maintenance['task_id'],next_task['task_id']]]==others
for row in [maintenance,next_task]:
 assert row in after and row['owner']==OWNER
 for other in after:
  if other['task_id']!=row['task_id']:assert not m.scopes_overlap(row['scope'],other['scope'])
save('customer-next-wave-readback-r1.json',dict(authority='AOS-002037',maintenance=maintenance,nextTask=next_task,owner=OWNER,otherLeasesPreserved=38,nonOverlapping=True,strongCurrent=7,personalMemoryWrites=False,wholeGoalComplete=False))
print(json.dumps(dict(authority='AOS-002037',slicesDelivered=2,maintenanceAllRemainingHandoff=True,otherLeasesPreserved=38,strongCurrent=7,nextTask=next_task['task_id'],goal='ACTIVE')))
