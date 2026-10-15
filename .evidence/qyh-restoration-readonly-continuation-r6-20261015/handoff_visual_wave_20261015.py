from pathlib import Path
import datetime, hashlib, json, os, subprocess, sys
R=Path.cwd();E=R/'.evidence/qyh-restoration-readonly-continuation-r6-20261015'
sys.path.insert(0,str(R/'scripts/memory'));import memoryctl as m
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
OWNER='codex-01a13484-f019-7d82-94ce-812396db9124'
HEAD='7038adb5b8b791bafd43b7206b9bf28be86da4bf'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==HEAD
assert subprocess.check_output(['git','branch','--show-current'],text=True).strip()=='m1'
assert not subprocess.check_output(['git','diff','--cached','--name-only'],text=True).strip()
assert not subprocess.check_output(['git','diff','f036e46c643308651b415179e6e991870dbc26ab','HEAD','--','apps/web','services/aos-api','scripts','bundles'],text=True)
p=m.DEFAULT_PATHS;a=m.load_authority(p);assert a['project_revision']=='AOS-002033'
def read(path):return json.loads(path.read_text())
def save(name,obj):
 m.scan_secrets(obj)
 with (E/name).open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
def legal(folder,prefix,version):
 q=read(folder/f'{prefix}-request-{version}.json');v=read(folder/f'{prefix}-result-{version}.json');t=read(folder/f'{prefix}-result-{version}.transport.json');c=read(folder/f'{prefix}-consumption-{version}.json')
 assert g.consumption_record(q,v,t,v['runner_sha256'])==c and c['status']=='CONSUMED_MATERIAL_REVIEW' and v['result']['verdict']=='PASS'
legal(R/'.evidence/qyh-price-visual-filter-sizing-20261015','code-review','r3');legal(E,'web-controller-review','r3');legal(E,'visual-live-review','r3')
proof=read(E/'visual-runtime-proof-r1.json');assert proof['tables650AllBeforeAfterEqual'] and proof['actualThreeViewportFilters32px'] and not proof['wholeGoalComplete']
for pid,port in [(89803,18434),(80779,18080)]:
 assert subprocess.check_output(['lsof','-t',f'-iTCP:{port}','-sTCP:LISTEN'],text=True).strip()==str(pid)
pg=json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','inspect','qyh-restored-pg-20261011'],text=True))[0]
assert pg['Id']==proof['originalContainerId'] and pg['State']['StartedAt']==proof['pgStartedAt'] and pg['Mounts'][0]['Name']==proof['originalVolume']
ids=['qyh-price-visual-filter-sizing-20261015','qyh-price-disposition-read-admission-20261015','qyh-restoration-readonly-continuation-r6-20261015']
active=m.load_leases(p)['leases'];rows={}
for tid in ids:
 found=[x for x in active if x['task_id']==tid];assert len(found)==1;row=rows[tid]=found[0]
 assert row['owner']==OWNER and row['base_revision']=='AOS-002033' and datetime.datetime.fromisoformat(row['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
 for other in active:
  if other['task_id']!=tid:assert not m.scopes_overlap(row['scope'],other['scope'])
others=[x for x in active if x['task_id'] not in ids]
dwave=next(s for s in rows[ids[1]]['scope'] if s.startswith('docs/'))
changed=['aos-platform/'+f for f in subprocess.check_output(['git','diff','--name-only','c1860a9a1455a68b99c9579101c1f05e51a649e7','HEAD'],text=True).splitlines()]+[dwave]
save('visual-handoff-intent-r1.json',dict(head=HEAD,before='AOS-002033',expected='AOS-002034',tasks=ids,otherLeasesPreserved=len(others),wholeGoalComplete=False,personalMemoryWrites=False))
results=[
 'ONLY single price-primary CSS filter sizing delivered: align-content:start, actual genuine original price page three widths all32px and safe filters; other visual/business goals incomplete.',
 'AUDIT_ONLY delivered: price dispositions default producer/Store/DTO/tenant/privacy/hash/count risks audited, ten committed sources. NO implementation or GET admission. ALL remaining implementation, plan/Prime/RED/native/SDK/Delivery scope carries intact into same-owner r2 successor at new authority.',
 'SAME_OWNER_HANDOFF of ALL remaining original restoration/full231Goal/user authorization/daily and every aos latest original-volume fullPG/API/Web. Verified only Webf036 sizing and original650 unchanged; Web-only refresh not daily replacement. Not whole restoration/install/business/visual/release completion.'
]
risks=['Original schema161/650 READONLY, HostworkerProviderOFF, budget162 not deployed; unknownold12/disabledSchedule/source/noPush boundaries retained.','FullC unique genuine human final budget/original deployment/natural business/install lifecycle/eight real scenarios/other visual/observation release remain incomplete.','Current real price data empty; isolated nonempty tests are not customer data or approval. Page helper failure fake0, creator1280 crop and other fullvisual remain.']
for tid,result in zip(ids,results):
 files=[f for f in changed if any(f==s or f.startswith(s.rstrip('/')+'/') for s in rows[tid]['scope'])];assert files
 commits=['7a429875f58c6594323ca1e5cc475ea2b622b375','f036e46c643308651b415179e6e991870dbc26ab',HEAD]
 receipt=m.complete_task(p,task_id=tid,expected_revision='AOS-002033',result=result,changed_files=files,commits=commits,verification=['Exact CSS quality r3/Webcontroller r3/livequality r3 PASS legally consumed; malformed and NEED/raw drafts preserved.','407 frozen tests/tsc/build; original component fixture RED89/255/345 to32 and filter/nonprimary sameviewport verification; exact fixture processes stopped.','Original genuine OIDC SDK commands[] and real three widths32px/filter/400/401, aux404 unchanged, six current reference/actual screenshots inspected.','Full650 before/freshbefore/after equal; API80779/source246 unchanged; Web89803/sourcef036 and764manifest; no business writes.'],risks=risks,blockers=[])
 save(tid+'-delivery-copy-r1.json',receipt)
new=m.update_authority(p,expected_revision='AOS-002033',current_phase='Single price filter sizing P1 delivered in real readonly UI; price disposition audit carried to implementation successor; full231Goal ACTIVE',delivery_status='ONLY one CSS visual slice plus audit-only handoff and ALL remaining maintenance; full install/business/eightvisual/release incomplete',last_green_gate='f036 one CSS declaration,407/typecheck/build/isolated original-component and genuine threeviewport32px; quality/control/live PASS consumed;650 full equality and API binding preserved',next_gate='Price disposition full readonly implementation plan/producer typedhash/complete bounded counts under carried registered scope; extra reader/sharedpure rules separately register before code; all fullC/business/install/other visual goals retained',completed=[*a['completed'],'Only price primary filter track sizing P1 now fixed in actual genuine original page at1280/1440/1920 all32px; supersedes earlier height89/255/345 pending only for this issue, not other visual/business acceptance.','Price disposition initial readonly audit delivered ONLY; all implementation/admission/native/SDK/quality requirements remain in successor. Actual Web89803/sourcef036, API80779/source246 backend trees equal evidence7038; original650 unchanged, Web-only not daily substitute.'],incomplete=[*a['incomplete'],'Price dispositions GET remains404/unimplemented read admission; audit does not finish it. Page helper failure fake0/creator1280 crop/remaining eightvisual/fullC truehuman budget/deployment/natural business/install lifecycle/observe release remain.'],next_steps=[*a['next_steps'],'Immediately continue carried price disposition full readonly implementation scheme: original producer hashes/typed binding/complete bounded revision counts/consistent snapshot/refs/privacy, separately register extra files before planPrime/RED.'],source_commits={**a['source_commits'],'qyh-price-filter-sizing-code':'f036e46c643308651b415179e6e991870dbc26ab','qyh-price-filter-sizing-live':HEAD},hard_boundaries=a['hard_boundaries'],evidence=[*a['evidence'],{'path':'aos-platform/.evidence/qyh-restoration-readonly-continuation-r6-20261015/visual-live-review-consumption-r3.json','summary':'Exact original genuine price sizing/read/data slice PASS legal; no operating or fullGoal approval.'},{'path':'aos-platform/.evidence/qyh-restoration-readonly-continuation-r6-20261015/visual-live-report-r1.md','summary':'Actual three widths32px/650 equality/same API and six reference/actual screenshots; remaining goals retained.'}])
assert new['project_revision']=='AOS-002034';save('visual-authority-update-r1.json',dict(before='AOS-002033',after='AOS-002034',historyPreserved=True,wholeGoalComplete=False))
with m.memory_lock(p,exclusive=True):
 projection=m.canonical_projection(m.load_authority(p));prime=[]
 for item in m.load_manifest(p)['projections']:
  if item.get('consistency')!='strong':continue
  if item['adapter']=='prime_harness':prime.append(item);continue
  path=m.expand_path(item['path'],p)
  if item['adapter']=='authority_frontmatter':desired=m.render_frontmatter(path.read_text() if path.exists() else '',projection)
  elif item['adapter']=='json_file':desired=json.dumps(m.projection_document(projection),ensure_ascii=False,indent=2,sort_keys=True)+'\n'
  else:raise AssertionError('unexpected strong adapter')
  m.scan_secrets(desired);m.atomic_write_text(path,desired)
 m.sync_prime(p,projection,prime)
status=m.memory_status(p);assert all(x['status']=='CURRENT' for x in status['projections'] if x['consistency']=='strong');save('visual-strong-memory-status-r1.json',status)
old=rows[ids[-1]];expiry='2026-10-15T04:00:00+00:00'
maintenance=m.start_task(p,task_id='qyh-restoration-readonly-continuation-r7-20261015',owner=OWNER,expected_revision='AOS-002034',scope=[*old['scope'],'aos-platform/.evidence/qyh-restoration-readonly-continuation-r7-20261015'],excluded_scope=old['excluded_scope'],expected_outputs=[*old['expected_outputs'],'ALL original remaining requirements/user authorization/full231Goal retained. Current runtime statement SUPERSEDES every older historical PID/head assertion: Web89803/sourcef036, API80779/source246 backend-equal current, originalPGStarted20:36:36/schema161/650/bindings0. Latest daily/every aos same-volume fullPGAPIWeb and aos2 noRestart remain; only single price sizing P1 delivered.'],lease_expires_at=expiry)
audit=rows[ids[1]]
successor=m.start_task(p,task_id='qyh-price-disposition-read-admission-r2-20261015',owner=OWNER,expected_revision='AOS-002034',scope=[*audit['scope'],'aos-platform/.evidence/qyh-price-disposition-read-admission-r2-20261015'],excluded_scope=audit['excluded_scope'],expected_outputs=[*audit['expected_outputs'],'Carry ALL remaining disposition GET read implementation from audit predecessor. Audit-only Delivery is NOT admission/completion. Use original models/producer typed bindinghash/frozen fullJSON/observations and complete bounded revision counts; same snapshot/tenant/privacy/SQLbytes/stable unavailable, no default fake0 or commands. Register reader/sharedpure rule files before code, planPrime/RED/frozen regression/nativePG/genuine SDK/650/visual/live/precise Delivery required. FullGoal unchanged.'],lease_expires_at=expiry)
after=m.load_leases(p)['leases'];assert maintenance in after and successor in after
assert [x for x in after if x['task_id'] not in [maintenance['task_id'],successor['task_id']]]==others
for row in [maintenance,successor]:
 assert row['owner']==OWNER
 for other in after:
  if row['task_id']!=other['task_id']:assert not m.scopes_overlap(row['scope'],other['scope'])
save('visual-next-wave-readback-r1.json',dict(authority='AOS-002034',maintenance=maintenance,successor=successor,owner=OWNER,otherLeasesPreserved=len(others),nonOverlapping=True,personalMemoryWrites=False,wholeGoalComplete=False))
print(json.dumps(dict(authority='AOS-002034',visualSliceDelivered=1,auditOnlyDelivered=1,maintenanceAllRemainingHandoff=True,strongCurrent=7,nextTask=successor['task_id'],otherLeasesPreserved=len(others),goal='ACTIVE')))
