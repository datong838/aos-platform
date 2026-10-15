"""Supported exact slice deliveries and same-owner continuation; never whole Goal completion."""
from pathlib import Path
import datetime
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
sys.path.insert(0,str(R/'scripts/memory'));import memoryctl as m
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as g
OWNER='codex-01a13484-f019-7d82-94ce-812396db9124'
HEAD='d73f83388be98029345d9b18e761e8e816ea2b74';CODE='4e038063368cc41fe17aec7b9f6148fa66bd7192'
def read(path):return json.loads(path.read_text())
def save(name,value):
    m.scan_secrets(value)
    with (E/name).open('x') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
def command(*args):return subprocess.check_output(args,cwd=R,text=True).strip()
def legal(folder,prefix,version):
    request=read(folder/f'{prefix}-request-{version}.json');result=read(folder/f'{prefix}-result-{version}.json')
    transport=read(folder/f'{prefix}-result-{version}.transport.json');consumed=read(folder/f'{prefix}-consumption-{version}.json')
    assert g.consumption_record(request,result,transport,result['runner_sha256'])==consumed
    assert result['result']['verdict']=='PASS' and consumed['status']=='CONSUMED_MATERIAL_REVIEW'
assert command('git','rev-parse','HEAD')==HEAD and command('git','branch','--show-current')=='m1'
assert not command('git','diff','--cached','--name-only')
assert not command('git','diff',CODE,'HEAD','--','apps/web','services/aos-api','scripts','bundles')
legal(R/'.evidence/qyh-price-disposition-read-admission-r2-20261015','route-quality','r2')
legal(R/'.evidence/qyh-price-disposition-bounded-reader-20261015','code-review','r2')
legal(E,'api-controller-review','r4');legal(E,'disposition-live-review','r1')
proof=read(E/'disposition-runtime-proof-r1.json')
assert proof['all650BeforeAfterEqual'] and proof['actualNativeDispositionSdk200'] and not proof['wholeGoalComplete']
assert command('lsof','-t','-nP','-iTCP:18080','-sTCP:LISTEN')=='95375'
assert proof['apiSource'] in command('lsof','-a','-p','95375','-d','cwd','-Fn')
assert command('lsof','-t','-nP','-iTCP:18434','-sTCP:LISTEN')=='89803'
pg=json.loads(command('docker','--context','colima-aos-extension','inspect','qyh-restored-pg-20261011'))[0]
assert pg['Id']==proof['originalContainerId'] and pg['State']['StartedAt']==proof['pgStartedAt'] and pg['Mounts'][0]['Name']==proof['originalVolume']
p=m.DEFAULT_PATHS;a=m.load_authority(p);assert a['project_revision']=='AOS-002034'
ids=['qyh-price-disposition-read-admission-r2-20261015','qyh-price-disposition-bounded-reader-20261015',E.name]
leases=m.load_leases(p)['leases'];rows={}
for tid in ids:
    found=[r for r in leases if r['task_id']==tid];assert len(found)==1;row=rows[tid]=found[0]
    assert row['owner']==OWNER and row['base_revision']=='AOS-002034'
    assert datetime.datetime.fromisoformat(row['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
    for other in leases:
        if other['task_id']!=tid:assert not m.scopes_overlap(row['scope'],other['scope'])
others=[r for r in leases if r['task_id'] not in ids];assert len(others)==38
dwave=next(s for s in rows[ids[0]]['scope'] if s.startswith('docs/'))
changed=['aos-platform/'+s for s in command('git','diff','--name-only','e58240059c950b7a3ebe9b31d760e55f5fb05c9b','HEAD').splitlines()]+[dwave]
save('disposition-handoff-intent-r1.json',dict(head=HEAD,code=CODE,before='AOS-002034',expected='AOS-002035',tasks=ids,otherLeasesPreserved=38,wholeGoalComplete=False))
results=[
 'ONLY admitted price dispositions GET saved-evidence read delivered: original genuine SDK200/credible saved empty/null/commands[]/externalfalse, query400/anonymous401, no business effects; no operating or fullGoal completion.',
 'ONLY bounded saved disposition reader and original pure-rule compatibility delivered: original typed binding/frozen fullpayload/observation exact links, complete saved revision counts and privacy/tenant/single readonly snapshot/metadata SQL limits; synthetic native fixture not production authority.',
 'SAME_OWNER_HANDOFF of ALL original remaining restoration/full231Goal/user authorization/daily and every aos latest original-volume fullPG/API/Web; only current price disposition readonly slice verified. API95375/source4e Web89803/f036 originalPG/schema161/650/bindings0; not whole maintenance/install/business/visual/release completion.']
risks=['FullC unique genuine human final budget/original deployment/natural business/install lifecycle/eight scenarios/fullvisual/observe release remain incomplete.',
       'Original DB readonly/HostworkerProviderOFF; unknownold12/disabledSchedule/source/noPush boundaries retained. Historical migration test expects old w6_009 while committed head a0v_162; raw failure preserved, no migration.',
       'Actual saved dispositions empty; isolated synthetic nonempty/receipt resolvers are not actual approval. Page helper failure fake0/creator1280 crop/other visual remain.']
for tid,result in zip(ids,results):
    files=[f for f in changed if any(f==s or f.startswith(s.rstrip('/')+'/') for s in rows[tid]['scope'])];assert files
    receipt=m.complete_task(p,task_id=tid,expected_revision='AOS-002034',result=result,changed_files=files,commits=[CODE,HEAD],
        verification=['Design PASS/code reader r2/route r2/controller r4/live r1 all exact legal consumed; NEED/REWORK and malformed/oversize drafts preserved.',
            'Frozen267 and targeted current route17/fullHTTP3; original producer four kinds/prepared/frozen/hash/complete8 count and old referenced frozen observation.',
            'Owned tmpfs exactW6_006 native snapshot Case1-to2/RLS/25006/prepayload oversize/SQLCASE/privacy passed; exactCID stopped, original volume untouched.',
            'Original genuine me/SDK200/commands[]/externalfalse/query400/anonymous401/canonical priceclosure404/businessNonGet[]; full650 before-after equal.',
            'Actual three widths filter32 and safe switching; six final actualr2/referencer3 correct CSS-sized PNGs inspected, invalid captures preserved separately.'],risks=risks,blockers=[])
    save(tid+'-delivery-copy-r1.json',receipt)
incomplete=[x.replace('Price dispositions GET remains404/unimplemented read admission; audit does not finish it. ','') for x in a['incomplete']]
new=m.update_authority(p,expected_revision='AOS-002034',current_phase='Price disposition saved-evidence readonly slice delivered; actual genuine SDK200 and original650 unchanged; full231Goal ACTIVE',
    delivery_status='ONLY price disposition root/reader slice plus ALL remaining maintenance handoff; full install/business/eightvisual/release incomplete',
    last_green_gate='Code4e six files/frozen267/nativeW6_006/code-controller-live PASS legal; API95375/source4e, Web89803/f036 and original650 unchanged; actual SDK/read/deny/32px only',
    next_gate='Price closure auxiliary GET original producer/Store/DTO/tenant/privacy/complete bounded snapshot audit before admission; remaining user budget/business/install/eightvisual goals retained',
    completed=[*a['completed'],'Only saved price dispositions GET/reader now delivered in actual original genuine org-org/dev-project: SDK200 credible empty/null/commands[]/externalfalse,400/401 and unchanged650. Supersedes prior disposition404/audit-only status only for this slice, not price closure or other goals.'],
    incomplete=[*incomplete,'Price closure canonical GET still404; customer auxiliary helpers, Page failure fake0/creator1280 crop/other fullvisual and entire original fullC/userbudget/deployment/naturalbusiness/install/observe release remain.'],
    next_steps=[*a['next_steps'],'Continue registered price closure read audit next; no automatic copied whitelist or operating authority. Daily/every actual aos latest original-volume fullPGAPIWeb remains; aos2 noRestart.'],
    source_commits={**a['source_commits'],'qyh-price-disposition-code':CODE,'qyh-price-disposition-live':HEAD},hard_boundaries=a['hard_boundaries'],
    evidence=[*a['evidence'],{'path':'aos-platform/.evidence/qyh-restoration-readonly-continuation-r7-20261015/disposition-live-review-consumption-r1.json','summary':'Exact original saved disposition read/identity/source650/geometry slice PASS legal; no business or fullGoal approval.'},
        {'path':'aos-platform/.evidence/qyh-restoration-readonly-continuation-r7-20261015/disposition-live-report-r1.md','summary':'Genuine SDK200/commands empty, original650 equality, actual final six CSS-sized screenshots and remaining goals.'}])
assert new['project_revision']=='AOS-002035';save('disposition-authority-update-r1.json',dict(before='AOS-002034',after='AOS-002035',wholeGoalComplete=False))
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
status=m.memory_status(p);assert all(x['status']=='CURRENT' for x in status['projections'] if x['consistency']=='strong')
save('disposition-strong-memory-status-r1.json',status)
old=rows[E.name];expiry='2026-10-15T04:00:00+00:00'
maintenance=m.start_task(p,task_id='qyh-restoration-readonly-continuation-r8-20261015',owner=OWNER,expected_revision='AOS-002035',
    scope=[*old['scope'],'aos-platform/.evidence/qyh-restoration-readonly-continuation-r8-20261015'],excluded_scope=old['excluded_scope'],
    expected_outputs=[*old['expected_outputs'],'ALL original remaining restoration/full231Goal/user authorization retained. Current runtime SUPERSEDES every older PID/head assertion: API95375/source4e,Web89803/f036,originalPGStarted20:36:36/schema161/650/bindings0. Only saved disposition readonly slice delivered; fullC/userbudget/natural business/install/eightvisual/release continue; daily/every aos latest original-volume fullPGAPIWeb and aos2 noRestart preserved.'],lease_expires_at=expiry)
next_task=m.start_task(p,task_id='qyh-price-closure-read-admission-20261015',owner=OWNER,expected_revision='AOS-002035',
    scope=['aos-platform/services/aos-api/aos_api/routers/ecommerce_workshop.py','aos-platform/services/aos-api/tests/test_ecommerce_workshop_read_http.py',dwave,'aos-platform/.evidence/qyh-price-closure-read-admission-20261015'],
    excluded_scope=rows[ids[0]]['excluded_scope'],
    expected_outputs=['Full231Goal and original authorization retained. Audit canonical GET views/price/closure-contributions defaultproducer/Store/DTO/tenant/privacy/consistent cutoff/bounds/error before planPrime/admission.',
        'Any extra reader/shared rules or Web files separately register before code; do not bulk switch Catalog. Original no-effects/source/budget/unknown boundaries; applicable visual comparison; frozen regression/native/genuine SDK/650/live/accurate Delivery.'],lease_expires_at=expiry)
after=m.load_leases(p)['leases']
assert [r for r in after if r['task_id'] not in [maintenance['task_id'],next_task['task_id']]]==others
for row in [maintenance,next_task]:
    assert row in after and row['owner']==OWNER
    for other in after:
        if other['task_id']!=row['task_id']:assert not m.scopes_overlap(row['scope'],other['scope'])
save('disposition-next-wave-readback-r1.json',dict(authority='AOS-002035',maintenance=maintenance,nextTask=next_task,
    owner=OWNER,otherLeasesPreserved=38,nonOverlapping=True,strongCurrent=7,personalMemoryWrites=False,wholeGoalComplete=False))
print(json.dumps(dict(authority='AOS-002035',slicesDelivered=2,maintenanceAllRemainingHandoff=True,otherLeasesPreserved=38,strongCurrent=7,nextTask=next_task['task_id'],goal='ACTIVE')))
