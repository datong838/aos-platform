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
HEAD='0d0623496efc3f44c839a7172f39168a020008e0';CODE='04092c82f9dcaccf7b23ff6e61d536a9f650aa38'
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
legal(R/'.evidence/qyh-price-closure-read-admission-20261015','route-quality','r1')
legal(R/'.evidence/qyh-price-closure-bounded-reader-20261015','code-review','r2')
legal(E,'api-controller-review','r1');legal(E,'closure-live-review','r1')
proof=read(E/'closure-runtime-proof-r1.json')
assert proof['all650BeforeAfterEqual'] and proof['actualPriceSdk200'] and not proof['wholeGoalComplete']
assert command('lsof','-t','-nP','-iTCP:18080','-sTCP:LISTEN')=='8498'
assert proof['apiSource'] in command('lsof','-a','-p','8498','-d','cwd','-Fn')
assert command('lsof','-t','-nP','-iTCP:18434','-sTCP:LISTEN')=='89803'
pg=json.loads(command('docker','--context','colima-aos-extension','inspect','qyh-restored-pg-20261011'))[0]
assert pg['Id']==proof['originalContainerId'] and pg['State']['StartedAt']==proof['pgStartedAt'] and pg['Mounts'][0]['Name']==proof['originalVolume']
p=m.DEFAULT_PATHS;a=m.load_authority(p);assert a['project_revision']=='AOS-002035'
ids=['qyh-price-closure-read-admission-20261015','qyh-price-closure-bounded-reader-20261015',E.name]
leases=m.load_leases(p)['leases'];rows={}
for tid in ids:
    found=[r for r in leases if r['task_id']==tid];assert len(found)==1;row=rows[tid]=found[0]
    assert row['owner']==OWNER and row['base_revision']=='AOS-002035'
    assert datetime.datetime.fromisoformat(row['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
    for other in leases:
        if other['task_id']!=tid:assert not m.scopes_overlap(row['scope'],other['scope'])
others=[r for r in leases if r['task_id'] not in ids];assert len(others)==38
dwave=next(s for s in rows[ids[0]]['scope'] if s.startswith('docs/'))
changed=['aos-platform/'+s for s in command('git','diff','--name-only','804a0279aa3d426a693504cb3336fb5a8ca4d149','HEAD').splitlines()]+[dwave]
save('closure-handoff-intent-r1.json',dict(head=HEAD,code=CODE,before='AOS-002035',expected='AOS-002036',tasks=ids,otherLeasesPreserved=38,wholeGoalComplete=False))
results=[
 'ONLY canonical price closure saved contribution GET delivered: original genuine SDK200/fournull/four gaps/commands[]/threefalse; creator still creator,400/401 and customer closure404 retained. No operating or fullGoal completion.',
 'ONLY shared saved closure reader fixed PRICE entry delivered: original typed hash/IDs/ledger/exact bindings/public refs, strict price raw/privacy/SQLbounds and unchanged CREATOR normal behavior; synthetic fixture not real source/cohort authority.',
 'SAME_OWNER_HANDOFF of ALL original remaining restoration/full231Goal/user authorization/daily and every aos latest original-volume fullPG/API/Web; only current price closure readonly slice verified. API8498/source04092 Web89803/f036 originalPG/schema161/650/bindings0; not whole maintenance/install/business/visual/release completion.']
risks=['FullC unique genuine human final budget/original deployment/natural business/install lifecycle/eight scenarios/fullvisual/observe release remain incomplete.',
       'Original DB readonly/HostworkerProviderOFF; unknownold12/disabledSchedule/source/noPush boundaries retained. Historical migration test expects old w6_009 while committed head a0v_162; raw failure preserved, no migration.',
       'Actual saved price closures empty; isolated synthetic nonempty/receipt resolvers are not actual approval. Page helper failure fake0/creator1280 crop/other visual remain.']
for tid,result in zip(ids,results):
    files=[f for f in changed if any(f==s or f.startswith(s.rstrip('/')+'/') for s in rows[tid]['scope'])];assert files
    receipt=m.complete_task(p,task_id=tid,expected_revision='AOS-002035',result=result,changed_files=files,commits=[CODE,HEAD],
        verification=['Design r2/code reader r2/route r1/controller r1/live r1 all exact legal consumed; NEED/REWORK and malformed/oversize drafts preserved.',
            'Frozen335 and joint253/reader108/fullHTTP3; original compiler typed hashes, five independent axes and public string Task revision preserved; mixed-price fixture not actual resolver capability.',
            'Owned tmpfs exactW6_009 native price source snapshot/CREATOR preservation/RLS/25006/SQLCASE64KiB/privacy passed; exactCID stopped, original volume untouched.',
            'Original genuine me/price and creator SDK200/fournull/commands[]/threefalse/query400/anonymous401/customerclosure404/businessNonGet[]; full650 before-after equal.',
            'Actual three widths filter32 and safe switching; six actual/reference-r1 native correct CSS-sized PNGs inspected; no fullvisual acceptance.'],risks=risks,blockers=[])
    save(tid+'-delivery-copy-r1.json',receipt)
incomplete=[x.replace('Price closure canonical GET still404; ','') for x in a['incomplete']]
new=m.update_authority(p,expected_revision='AOS-002035',current_phase='Price closure saved-evidence readonly slice delivered; price and creator genuine SDK200/original650 unchanged; full231Goal ACTIVE',
    delivery_status='ONLY price closure root/shared-reader slice plus ALL remaining maintenance handoff; full install/business/eightvisual/release incomplete',
    last_green_gate='Code04092 four files/frozen335/nativeW6_009/code-controller-live PASS legal; API8498/source04092, Web89803/f036 and original650 unchanged; actual SDK/read/deny/32px only',
    next_gate='Customer contribution auxiliary GET original producer/Store/DTO/tenant/privacy/source-consent/bounded cutoff audit before admission; all original userbudget/business/install/eightvisual goals retained',
    completed=[*a['completed'],'Only saved price closure canonical GET/shared reader delivered in original genuine org-org/dev-project: price and creator SDK200/fournull/four gaps/commands[]/threefalse,400/401 and unchanged650. Supersedes prior price closure404 only; customer helpers and full business/install/visual goals remain.'],
    incomplete=[*incomplete,'Customer contribution/contact/closure auxiliary GET remain unreviewed legacy; Page failure fake0/creator1280 crop/other fullvisual and all original fullC/userbudget/deployment/naturalbusiness/install/observe release remain.'],
    next_steps=[*a['next_steps'],'Continue registered customer contribution read audit next; no automatic copied whitelist or operating authority. Daily/every actual aos latest original-volume fullPGAPIWeb remains; aos2 noRestart.'],
    source_commits={**a['source_commits'],'qyh-price-closure-code':CODE,'qyh-price-closure-live':HEAD},hard_boundaries=a['hard_boundaries'],
    evidence=[*a['evidence'],{'path':'aos-platform/.evidence/qyh-restoration-readonly-continuation-r8-20261015/closure-live-review-consumption-r1.json','summary':'Exact original saved price closure read/creator preservation/identity/source650/geometry slice PASS legal; no business or fullGoal approval.'},
        {'path':'aos-platform/.evidence/qyh-restoration-readonly-continuation-r8-20261015/closure-live-report-r1.md','summary':'Genuine price and creator SDK200/commands empty, original650 equality, actual final six CSS-sized screenshots and remaining goals.'}])
assert new['project_revision']=='AOS-002036';save('closure-authority-update-r1.json',dict(before='AOS-002035',after='AOS-002036',wholeGoalComplete=False))
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
save('closure-strong-memory-status-r1.json',status)
old=rows[E.name];expiry='2026-10-15T08:00:00+00:00'
maintenance=m.start_task(p,task_id='qyh-restoration-readonly-continuation-r9-20261015',owner=OWNER,expected_revision='AOS-002036',
    scope=[*old['scope'],'aos-platform/.evidence/qyh-restoration-readonly-continuation-r9-20261015'],excluded_scope=old['excluded_scope'],
    expected_outputs=[*old['expected_outputs'],'ALL original remaining restoration/full231Goal/user authorization retained. Current runtime SUPERSEDES every older PID/head assertion: API8498/source04092,Web89803/f036,originalPGStarted20:36:36/schema161/650/bindings0. Only saved price closure readonly slice delivered; fullC/userbudget/natural business/install/eightvisual/release continue; daily/every aos latest original-volume fullPGAPIWeb and aos2 noRestart preserved.'],lease_expires_at=expiry)
next_task=m.start_task(p,task_id='qyh-customer-contribution-read-admission-20261015',owner=OWNER,expected_revision='AOS-002036',
    scope=['aos-platform/services/aos-api/aos_api/routers/ecommerce_workshop.py','aos-platform/services/aos-api/tests/test_ecommerce_workshop_read_http.py',dwave,'aos-platform/.evidence/qyh-customer-contribution-read-admission-20261015'],
    excluded_scope=rows[ids[0]]['excluded_scope'],
    expected_outputs=['Full231Goal and original authorization retained. Audit canonical GET views/customer/contributions defaultproducer/Store/DTO/tenant/privacy/source-consent/consistent cutoff/bounds/error before planPrime/admission; no ProtectedContact or dispatch.',
        'Any extra reader/shared rules or Web files separately register before code; do not bulk switch Catalog. Original no-effects/source/budget/unknown boundaries; applicable visual comparison; frozen regression/native/genuine SDK/650/live/accurate Delivery.'],lease_expires_at=expiry)
after=m.load_leases(p)['leases']
assert [r for r in after if r['task_id'] not in [maintenance['task_id'],next_task['task_id']]]==others
for row in [maintenance,next_task]:
    assert row in after and row['owner']==OWNER
    for other in after:
        if other['task_id']!=row['task_id']:assert not m.scopes_overlap(row['scope'],other['scope'])
save('closure-next-wave-readback-r1.json',dict(authority='AOS-002036',maintenance=maintenance,nextTask=next_task,
    owner=OWNER,otherLeasesPreserved=38,nonOverlapping=True,strongCurrent=7,personalMemoryWrites=False,wholeGoalComplete=False))
print(json.dumps(dict(authority='AOS-002036',slicesDelivered=2,maintenanceAllRemainingHandoff=True,otherLeasesPreserved=38,strongCurrent=7,nextTask=next_task['task_id'],goal='ACTIVE')))
