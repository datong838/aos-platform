"""Supported metadata handoff only; geometry verified, actual input explicitly incomplete."""
from pathlib import Path
import json,hashlib,subprocess,datetime,os,sys
E=Path(__file__).resolve().parent;R=E.parents[1]
HEAD='306e999c575cf56abf679473abee89f692fc5142';CODE='d5c8598e50904041314c3ab66703f103a003a48b'
OWNER='codex-01a13484-f019-7d82-94ce-812396db9124'
C=R/'.evidence/qyh-creator-visual-narrow-layout-20261015';D=E/'daily-20261016'
sys.path.insert(0,str(R/'scripts/memory'));import memoryctl as m
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as gate
sys.path.insert(0,str(R/'scripts'));import a0v_qyh_restored_http as guard
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def cmd(*a):return subprocess.check_output(a,cwd=R,text=True).strip()
def save(n,v):
 m.scan_secrets(v)
 with (E/n).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
def legal(folder,prefix,version,runner):
 q=read(folder/(prefix+'-request'+('-'+version if version else '')+'.json'))
 v=read(folder/(prefix+'-result'+('-'+version if version else '')+'.json'));t=read(folder/(prefix+'-result'+('-'+version if version else '')+'.transport.json'));c=read(folder/(prefix+'-consumption'+('-'+version if version else '')+'.json'))
 assert v['result']['verdict']=='PASS' and v['validator_sha256']==sha(Path(gate.__file__)) and v['runner_sha256']==sha(folder/runner)
 assert gate.consumption_record(q,v,t,sha(folder/runner))==c
assert cmd('git','rev-parse','HEAD')==HEAD and cmd('git','branch','--show-current')=='m1' and not cmd('git','diff','--cached','--name-only')
assert not cmd('git','diff',CODE,'HEAD','--','apps/web','packages','services/aos-api','scripts','bundles')
for pre,ver in [('design-review','r2'),('code-review','r1'),('diagnostic-review','r2')]:legal(C,pre,ver,'review_controller.py')
legal(D,'controller-review','','review_controller_r1.py');legal(D,'live-review','r1','review_live_r1.py');legal(E,'web-controller-review','r2','review_controller_r2.py')
api=guard.require_api_source_candidate(R/'.evidence/qyh-full-system-restoration-20261011/daily-current-api-20261016.json')
assert cmd('lsof','-t','-nP','-iTCP:18080','-sTCP:LISTEN')=='72057' and str(api) in cmd('lsof','-a','-p','72057','-d','cwd','-Fn')
assert cmd('lsof','-t','-nP','-iTCP:18434','-sTCP:LISTEN')=='75206' and cmd('ps','-p','75206','-o','command=')=='/Users/ddt/.workbuddy/binaries/node/versions/22.22.2-2/bin/node '+str(E/'creator-narrow-web-server.mjs')
w=read(E/'creator-narrow-web-source.json');source=Path(w['source']);assert w['head']==CODE and {str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}==w['manifest']
pg=json.loads(cmd('docker','--context','colima-aos-extension','inspect','qyh-restored-pg-20261011'))[0];assert pg['Id']=='84989681fb7d3fc0f42d750672547ca0208fbba08dfef0d93837d8e64245dc3c' and pg['State']['StartedAt']=='2026-10-15T16:28:04.112157693Z' and pg['Mounts'][0]['Name']=='aos-qyh-history159-prepared-data-20261011'
F=R/'.evidence/qyh-restoration-successor-latest-restart-20261013';before=read(F/'creator-narrow-web-before-20261016.json');after=read(F/'creator-narrow-web-after-20261016.json');assert before['fingerprints']==after['fingerprints'] and len(after['fingerprints'])==650
proof=read(C/'current-runtime-geometry-checkpoint-r1.json');fixture=read(C/'isolated-layout-verification-r1.json');assert proof['fourWidthsRightCropRemoved'] and not proof['inputAcceptancePassed'] and not proof['deliveryComplete'] and not proof['wholeGoalComplete'];assert fixture['fixtureCommandCalls']==0 and fixture['fixtureServerStopped'] and not fixture['actualChromeInputPassed']
p=m.DEFAULT_PATHS;a=m.load_authority(p);assert a['project_revision']=='AOS-002040'
leases=m.load_leases(p)['leases'];ids=[C.name,E.name];rows={}
for tid in ids:
 xs=[x for x in leases if x['task_id']==tid];assert len(xs)==1;row=rows[tid]=xs[0];assert row['owner']==OWNER and row['base_revision']=='AOS-002040' and datetime.datetime.fromisoformat(row['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
 assert all(not m.scopes_overlap(row['scope'],x['scope']) for x in leases if x['task_id']!=tid)
others=[x for x in leases if x['task_id'] not in ids];assert len(others)==38
dwave=next(x for x in rows[C.name]['scope'] if x.startswith('docs/'))
changed=['aos-platform/'+x for x in cmd('git','diff','--name-only','40100ba60a3d08375e59d8e3ddfec38c8fc5e51c','HEAD').splitlines()]+[dwave]
newM='qyh-restoration-readonly-continuation-r14-20261016';newC='qyh-creator-native-input-and-scroll-20261016';expiry='2026-10-16T08:00:00+00:00'
save('geometry-daily-handoff-intent-r2.json',dict(before='AOS-002040',expected='AOS-002041',head=HEAD,code=CODE,oldTasks=ids,newTasks=[newC,newM],otherLeasesPreserved=38,actualInputPassed=False,wholeGoalComplete=False))
verification=['Creator design-r2/code-r1 PASS legally consumed; frozen407/type/build; only two CSS min widths changed. Diagnostic-r2 PASS legally consumed for facts/boundaries, not genuine input/business acceptance.','Daily original-volume PGAPIWeb controller/live PASS legally consumed; Web-only controller-r1 NEED_DECISION unchanged/consumed, scoped stage-r2 PASS legally consumed before one Web switch. API72057/40100 backend-equal latest, Web75206/d5 source764, originalPG new epoch/schema161/650/bindings0.','Actual1280 board972 vs original1100 and1180 board872 vs original970; all four widths no right-column crop, eight actual/reference images inspected. Current full650 before/after dictionaries equal, normal original OIDC reads/businessNonGET empty.','Synthetic fixture only: original frozen component/CSS, dev-org/fixture-project,24 long resourceRefs/four long titles; four widths five normal view switches/TabEnter focus/vertical end and narrow table horizontal last columns verified,commands0/no originalAPI proxy,temporaryserver andtab closed. Not genuine original browser input proof.']
risks=['GEOMETRY_ONLY_INPUT_INCOMPLETE_HANDOFF: actual originalChrome pointer/keyboard/scroll still unverified; protocol returns no captured events. No proven component/interceptor cause; do not force/DOMclick or replace with fixture. Full original creator fileplan acceptance and final live review still pending.','ALL original remaining231Goal/user authorization/fullC genuine final budget and original deployment/natural sourced first chain/install-config-deny-recover-uninstall-reinstall/eight real scenarios/fullvisual/continuous observe-release retained. DBreadonly/HostworkerProviderOFF/unknown old12noReplay/disabledScheduleOFF/mallsourceNoRead/noPush.','Old writer remains archived; readonly question could not be delivered and no unarchive/resume performed. Personal Codex memory and privateGoal/reminder stores untouched.']
results={C.name:'GEOMETRY_ONLY_INPUT_INCOMPLETE_HANDOFF: deliver reviewed twoCSS candidate and actual four-width geometry plus isolated nonempty risk evidence ONLY. ActualChrome input/end-scroll/remaining original acceptance explicitly NOT complete; same-owner successor carries ALL old outputs/scopes and pending gates unchanged.',E.name:'DAILY_AND_WEB_MAINTENANCE_SLICE_ONLY + SAME_OWNER_HANDOFF of ALL original remaining restoration/user authorization/full231Goal/daily-every-actual-aos latest original-volume fullPGAPIWeb/aos2 noRestart. Actual runtime supersedes old PIDs: API72057/40100 backend-current,Web75206/d5,PGStarted16:28:04/schema161/650/bindings0. No whole restoration/business/visual/input completion.'}
for tid in ids:
 files=[x for x in changed if any(x==s or x.startswith(s.rstrip('/')+'/') for s in rows[tid]['scope'])];assert files
 delivery=m.complete_task(p,task_id=tid,expected_revision='AOS-002040',result=results[tid],changed_files=files,commits=[CODE,HEAD],verification=verification,risks=risks,blockers=['OriginalChrome input witness/actual UI response absent; preserve pending and continue authorized safe steps, not whole Goal blocked.'])
 save(tid+'-boundary-delivery-r2.json',delivery)
new=m.update_authority(p,expected_revision='AOS-002040',current_phase='Creator right-crop geometry and isolated longtext risk verified; genuine Chrome input pending; daily original-volume latest restart verified; full231Goal ACTIVE',delivery_status='ONLY verified geometry/fixture and maintenance slices; ALL remaining original tasks handed to same owner; no fullvisual/business/install/input completion',last_green_gate='Code d5c8598 twoCSS/407/type/build/design-code-diagnostic PASS legal; actual4width geometry; isolated5views/scroll/keyboard only; Web75206 API72057 original650 equal; daily originalvolume PGAPIWeb reviewed',next_gate='Recover genuine original Chrome input and verify real four-width stages/filters/keyboard/end-scroll; never substitute fixture. Continue registered safe natural-business/budget/current-installation source preparation with full original boundaries.',completed=[*a['completed'],'2026-10-16 verified daily same-original-volume PGAPIWeb at40100 plus Creator d5 twoCSS reviewed Web-only update; actual four-width right-crop geometry removed and isolated longtext/fiveview/scroll risk evidence verified. Genuine originalChrome input remains explicitly unverified; no whole completion.'],incomplete=[*a['incomplete'],'Latest superseding creator status: d5 fixes1280/1180 right-crop geometry, actualWeb75206 current, isolated fixture four widths/fiveviews/scroll/keyboard passed and stopped. Actual originalChrome normal input/scroll/filters/final full live acceptance remain; ALL original budget/business/install/eightvisual/release goals pending.'],next_steps=[*a['next_steps'],'Latest: same-owner creator-native-input-and-scroll-20261016 carries ALL incomplete original creator fileplan; originalChrome protocol no events is NOT component-root-cause proof. Maintain fullGoal and daily/every-aos originalvolume latest fullPGAPIWeb, aos2 noRestart; continue registered safe business preparation.'],source_commits={**a['source_commits'],'qyh-creator-narrow-code':CODE,'qyh-creator-geometry-fixture-evidence':HEAD},hard_boundaries=a['hard_boundaries'],evidence=[*a['evidence'],{'path':'aos-platform/'+str((C/'diagnostic-review-consumption-r2.json').relative_to(R)),'summary':'Legal PASS for actual geometry and isolated fixture facts, explicitly not genuine input or whole operating completion.'},{'path':'aos-platform/'+str((D/'live-review-consumption-r1.json').relative_to(R)),'summary':'Daily original-volume latest PGAPIWeb actual8roots/identity/deny/core input/source/650 reviewed; maintenance slice only.'}],evidence_cutoff=datetime.datetime.now(datetime.timezone.utc).isoformat())
assert new['project_revision']=='AOS-002041'
with m.memory_lock(p,exclusive=True):
 projection=m.canonical_projection(m.load_authority(p));prime=[]
 for item in m.load_manifest(p)['projections']:
  if item.get('consistency')!='strong':continue
  if item['adapter']=='prime_harness':prime.append(item);continue
  path=m.expand_path(item['path'],p)
  if item['adapter']=='authority_frontmatter':desired=m.render_frontmatter(path.read_text() if path.exists() else '',projection)
  elif item['adapter']=='json_file':desired=json.dumps(m.projection_document(projection),ensure_ascii=False,indent=2,sort_keys=True)+'\n'
  else:raise AssertionError('Unknown strong adapter')
  m.scan_secrets(desired);m.atomic_write_text(path,desired)
 m.sync_prime(p,projection,prime)
status=m.memory_status(p);assert all(x['status']=='CURRENT' for x in status['projections'] if x['consistency']=='strong');save('geometry-strong-memory-status-r2.json',status)
old=rows[E.name];maintenance=m.start_task(p,task_id=newM,owner=OWNER,expected_revision='AOS-002041',scope=[*old['scope'],'aos-platform/.evidence/'+newM],excluded_scope=old['excluded_scope'],expected_outputs=[*old['expected_outputs'],'ALL remaining original231Goal/restoration/user authority/daily every actual aos latest originalvolume fullPGAPIWeb/aos2 noRestart retained. Latest runtime supersedes all old PID/source assertions: API72057/40100 backend-current,Web75206/d5,originalPGStarted16:28:04/schema161/650/bindings0. Geometry-only creator handoff and actual-input pending do NOT close fullGoal/visual/business/install/budget/release.'],lease_expires_at=expiry)
old=rows[C.name];creator=m.start_task(p,task_id=newC,owner=OWNER,expected_revision='AOS-002041',scope=[*old['scope'],'aos-platform/.evidence/'+newC],excluded_scope=old['excluded_scope'],expected_outputs=[*old['expected_outputs'],'ALL incomplete original creator fileplan/genuine native originalChrome input/end-scroll/filters/keyboard/1180+3width/final independent live and business/visual goals retained. Existing d5 design-r2/code-r1/407 and geometry/isolated fixture diagnostic-r2 delivered only as evidence; do not repeat delivered tests without new changes or use fixture as genuine input proof. No proven Playwright listener root cause; old writer stays archived.'],lease_expires_at=expiry)
afterLeases=m.load_leases(p)['leases'];assert [x for x in afterLeases if x['task_id'] not in [newM,newC]]==others
for row in [maintenance,creator]:assert row in afterLeases and all(not m.scopes_overlap(row['scope'],x['scope']) for x in afterLeases if x['task_id']!=row['task_id'])
save('geometry-next-task-readback-r2.json',dict(authority='AOS-002041',maintenance=maintenance,creator=creator,otherLeasesPreserved=38,nonOverlapping=True,strongCurrent=7,actualOriginalInputPassed=False,wholeGoalComplete=False,personalMemoryWrites=False))
print(json.dumps({'authority':'AOS-002041','sameOwnerAllRemainingHandoff':True,'otherLeasesPreserved':38,'strongCurrent':7,'actualInputPassed':False,'goal':'ACTIVE'}))
