from pathlib import Path
import datetime, hashlib, json, os, subprocess, sys

R = Path.cwd()
E = R / '.evidence/qyh-restoration-readonly-continuation-r5-20261015'
sys.path.insert(0, str(R/'scripts/memory'))
import memoryctl as m
sys.path.insert(0, str(R/'scripts/long-task-watchdog'))
import aos_review as g
owner = 'codex-01a13484-f019-7d82-94ce-812396db9124'
head = subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip()
assert head == 'c1860a9a1455a68b99c9579101c1f05e51a649e7'
assert subprocess.check_output(['git','branch','--show-current'], text=True).strip() == 'm1'
assert not subprocess.check_output(['git','diff','--cached','--name-only'], text=True).strip()
assert not subprocess.check_output(['git','diff','246d8305332c143bd281cc6aedb013649b81f7d6','HEAD','--','services/aos-api','scripts','bundles','apps/web'], text=True)
p = m.DEFAULT_PATHS
a = m.load_authority(p)
assert a['project_revision'] == 'AOS-002032'

def read(path): return json.loads(path.read_text())
def save(name, value):
    m.scan_secrets(value)
    with (E/name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush(); os.fsync(f.fileno())
def legal(folder, prefix, version):
    req = read(folder/f'{prefix}-request-{version}.json')
    result = read(folder/f'{prefix}-result-{version}.json')
    transport = read(folder/f'{prefix}-result-{version}.transport.json')
    con = read(folder/f'{prefix}-consumption-{version}.json')
    assert g.consumption_record(req,result,transport,result['runner_sha256']) == con
    assert con['status'] == 'CONSUMED_MATERIAL_REVIEW' and result['result']['verdict'] == 'PASS'

legal(R/'.evidence/qyh-price-contribution-read-admission-20261015','code-review','r2')
legal(R/'.evidence/qyh-price-contribution-bounded-reader-20261015','code-review','r1')
legal(E,'api-controller-review','r1')
legal(E,'price-live-review','r1')
proof = read(E/'price-runtime-proof-r1.json')
assert proof['tables650BeforeAfterFinalEqual'] and proof['commandsRemainEmptyInActualSDK']
assert not proof['wholeGoalComplete'] and not proof['businessWrites']
for pid,port in [(80779,18080),(76677,18434)]:
    os.kill(pid,0)
    assert str(pid) in subprocess.check_output(['lsof','-nP','-a','-p',str(pid),f'-iTCP:{port}','-sTCP:LISTEN'],text=True)
pg = json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','inspect','qyh-restored-pg-20261011'],text=True))[0]
assert pg['Id'] == proof['originalContainerId'] and pg['State']['Running']
assert pg['State']['StartedAt'] == proof['pgStartedAt']
assert any(x.get('Name') == proof['originalVolume'] for x in pg['Mounts'])
verification = read(R/'.evidence/qyh-price-contribution-bounded-reader-20261015/source-verification-r2.json')
for name,sha in verification['sourceAfter'].items():
    assert hashlib.sha256((R/name).read_bytes()).hexdigest() == sha

ids = ['qyh-price-contribution-read-admission-20261015','qyh-price-contribution-bounded-reader-20261015','qyh-restoration-readonly-continuation-r5-20261015']
leases = m.load_leases(p)['leases']
rows = {}
for tid in ids:
    matches = [x for x in leases if x['task_id'] == tid]
    assert len(matches) == 1
    row = rows[tid] = matches[0]
    assert row['owner'] == owner and row['base_revision'] == 'AOS-002032'
    assert datetime.datetime.fromisoformat(row['lease_expires_at']) > datetime.datetime.now(datetime.timezone.utc)
    for other in leases:
        if other['task_id'] != tid: assert not m.scopes_overlap(row['scope'],other['scope'])
others = [x for x in leases if x['task_id'] not in ids]
dwave = 'docs/palantier/20_tech/电商平台接入/微商城电商接入方案/D-waves/2026-10-13-QYH-八台只读入口恢复与经营链接续清单.md'
changed = ['aos-platform/'+x for x in subprocess.check_output(['git','diff','--name-only','8374113ae12b615980198f98416611a5e10fc377','HEAD'],text=True).splitlines()] + [dwave]
save('price-wave-handoff-intent-r1.json',dict(before='AOS-002032',expected='AOS-002033',head=head,tasks=ids,otherLeasesPreserved=len(others),wholeGoalComplete=False,personalMemoryWrites=False))
results = [
    'ONLY price contributions GET installed readonly admission delivered; actual genuine OIDC SDK200/null batch/blocker/empty commands, query400/anonymous401; normal legacy and all POST unchanged; dispositions/priceclosure/customer remain unadmitted.',
    'ONLY bounded same-snapshot saved price research reader delivered; original prepared hash and frozen exact ancestor/inheritance, tenant/refs/ledger/time/privacy/SQLCASE checked; frozen224PASS and isolated originalDDL nonempty producer/RLS25006/snapshot/bytes/privacy. Not real budget approval or business completion.',
    'SAME_OWNER_HANDOFF of ALL remaining original restoration/full231Goal/user authorization/daily and every aos latest original-volume fullPG/API/Web requirements. Verified only API246/Web1627 readonly price slice and original650 unchanged; API-only refresh not daily replacement; full restoration/install/business/visual/release incomplete.'
]
risks = ['Original schema161/650 DB READONLY and Host/worker/Provider OFF; budget162 not deployed; original unknown12Run/disabledSchedule/source/noPush boundaries retained.', 'FullC genuine-user final budget/original deployment/natural business/install lifecycle/eight real scenarios/visualP1/observation release remain incomplete.', 'Current saved batch absent; isolated producer fixture not genuine customer batch or approval; price filter heights89/255/345 and helper failure fake0 remain known UI defects.']
for tid,result in zip(ids,results):
    files = [f for f in changed if any(f == s or f.startswith(s.rstrip('/')+'/') for s in rows[tid]['scope'])]
    assert files
    delivery = m.complete_task(p,task_id=tid,expected_revision='AOS-002032',result=result,changed_files=files,commits=['246d8305332c143bd281cc6aedb013649b81f7d6',head],verification=['Exact plan/code/controller/live Prime PASS legally consumed; earlier rejected/NEED results preserved.', 'Frozen224PASS; original w6_005 isolated PG producer snapshot/RLS/write25006/SQLCASE/privacy; exact CID stopped.', 'Original genuine OIDC actual SDK/null batch/empty commands; query400/anonymous401; actual API80779/source246 and Web76677/source1627; original650 before/after/final equal.', 'Fresh original and actual price screenshots at1280/1440/1920 inspected; visualP1 remains; no business acceptance.'],risks=risks,blockers=[])
    save(tid+'-delivery-copy-r1.json',delivery)
new = m.update_authority(p,expected_revision='AOS-002032',current_phase='Price saved batch contribution readonly API and SDK slice delivered; full231Goal ACTIVE; next price disposition readonly audit',delivery_status='ONLY two exact price reading slices and ALL remaining maintenance handoff; full restoration/business/visual/release incomplete',last_green_gate='246 frozen224 and exact code/controller/live Prime legally consumed; original OIDC actual SDK200/401400/emptycommands,650 before-after-final unchanged',next_gate='Registered price disposition auxiliary GET producer/Store/DTO/tenant/privacy/cutoff/bounds audit before exact plan/RED; separately register any reader/UI files; preserve fullC/business/install/visual/observe goals',completed=[*a['completed'],'Price contributions GET and bounded saved batch reader delivered only; supersedes old price-contributions404 pending for this read slice only, not price dispositions/closure or operating authority.', 'Actual API80779/source246d830 and Web76677/source1627 code trees equal evidence c1860a9; original650 unchanged; API-only refresh not daily substitute.'],incomplete=[*a['incomplete'],'Price dispositions and closure/customer contribution/contact/closure private helpers remain individually pending. FullC final genuine budget/deployment/natural business/install lifecycle/eight real scenarios/visualP1 and continuous release incomplete.'],next_steps=[*a['next_steps'],'Immediately audit price dispositions GET producer/transitiveStore/nestedDTO/tenant/privacy/consistentcutoff/bounds/error/authorization; separately register reader or UI failures/visual fixes before code.'],source_commits={**a['source_commits'],'qyh-price-contribution-readonly-code':'246d8305332c143bd281cc6aedb013649b81f7d6','qyh-price-contribution-readonly-live':head},hard_boundaries=a['hard_boundaries'],evidence=[*a['evidence'],{'path':'aos-platform/.evidence/qyh-restoration-readonly-continuation-r5-20261015/price-live-review-consumption-r1.json','summary':'Exact live readonly price slice legally consumed, not operating permission or wholeGoal.'},{'path':'aos-platform/.evidence/qyh-restoration-readonly-continuation-r5-20261015/price-live-report-r1.md','summary':'Genuine normal SDK/nullbatch/empty commands/source/650 and six visual screenshots/remainingP1; fullGoal retained.'}])
assert new['project_revision'] == 'AOS-002033'
save('price-authority-update-r1.json',dict(before='AOS-002032',after='AOS-002033',historyPreserved=True,wholeGoalComplete=False))
with m.memory_lock(p,exclusive=True):
    projection = m.canonical_projection(m.load_authority(p))
    prime = []
    for item in m.load_manifest(p)['projections']:
        if item.get('consistency') != 'strong': continue
        if item['adapter'] == 'prime_harness': prime.append(item); continue
        path = m.expand_path(item['path'],p)
        if item['adapter'] == 'authority_frontmatter': desired = m.render_frontmatter(path.read_text() if path.exists() else '',projection)
        elif item['adapter'] == 'json_file': desired = json.dumps(m.projection_document(projection),ensure_ascii=False,indent=2,sort_keys=True)+'\n'
        else: raise AssertionError('unexpected strong adapter')
        m.scan_secrets(desired); m.atomic_write_text(path,desired)
    m.sync_prime(p,projection,prime)
status = m.memory_status(p)
assert all(x['status'] == 'CURRENT' for x in status['projections'] if x['consistency'] == 'strong')
save('price-strong-memory-status-r1.json',status)
old = rows[ids[-1]]
expiry = '2026-10-15T02:00:00+00:00'
maintenance = m.start_task(p,task_id='qyh-restoration-readonly-continuation-r6-20261015',owner=owner,expected_revision='AOS-002033',scope=[*old['scope'],'aos-platform/.evidence/qyh-restoration-readonly-continuation-r6-20261015'],excluded_scope=old['excluded_scope'],expected_outputs=[*old['expected_outputs'],'Carry ALL original remaining restoration/user authorization/full231Goal/daily and every aos latest m1 original-volume fullPG/API/Web; aos2 no restart. Actual API80779/source246d830, Web76677/source1627 code equal c1860a9, originalPGStarted20:36:36/schema161/650/bindings0. Only saved price read slice verified; all business/install/visual/observe goals remain.'],lease_expires_at=expiry)
next_task = m.start_task(p,task_id='qyh-price-disposition-read-admission-20261015',owner=owner,expected_revision='AOS-002033',scope=['aos-platform/services/aos-api/aos_api/routers/ecommerce_workshop.py','aos-platform/services/aos-api/tests/test_ecommerce_workshop_read_http.py','aos-platform/.evidence/qyh-price-disposition-read-admission-20261015',dwave],excluded_scope=['aos-platform/apps/web','aos-platform/maintenance/qiyuehui-restored-data-volume','aos-platform/services/aos-api/aos_api/aip_action_execution.py','aos-platform/services/aos-api/aos_api/aip_action_store.py'],expected_outputs=['Full231Goal and eight-step Loop preserved; readonly audit price dispositions GET defaultproducer/transitiveStore/DTO/tenant/privacy/cutoff/bounds/error/admission before exact plan/Prime/RED.', 'Extra reader or Web/CSS failures/visual scope must separately register before code; no priceclosure/customer admission, original business writes/source/budgetapproval/Provider/oldunknown replay. Applicable original visual comparison retained.'],lease_expires_at=expiry)
active = m.load_leases(p)['leases']
assert maintenance in active and next_task in active
assert [x for x in active if x['task_id'] not in [maintenance['task_id'],next_task['task_id']]] == others
for row in [maintenance,next_task]:
    assert row['owner'] == owner
    for other in active:
        if row['task_id'] != other['task_id']: assert not m.scopes_overlap(row['scope'],other['scope'])
save('price-next-wave-readback-r1.json',dict(authority='AOS-002033',maintenance=maintenance,nextTask=next_task,owner=owner,nonOverlapping=True,otherLeasesPreserved=len(others),wholeGoalComplete=False,personalMemoryWrites=False))
print(json.dumps(dict(authority='AOS-002033',sliceDeliveries=2,maintenanceAllRemainingHandoff=True,strongCurrent=7,nextTask=next_task['task_id'],otherLeasesPreserved=len(others),goal='ACTIVE')))
