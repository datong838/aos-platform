from pathlib import Path
import datetime, json, os, subprocess, sys

R = Path.cwd()
E = R / '.evidence/qyh-restoration-readonly-continuation-r4-20261015'
sys.path.insert(0, str(R / 'scripts/memory'))
import memoryctl as m
sys.path.insert(0, str(R / 'scripts/long-task-watchdog'))
import aos_review as g

owner = 'codex-01a13484-f019-7d82-94ce-812396db9124'
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
assert head == 'f1a1f51f06e0931ad8026a13b6260d4029edc48a'
assert subprocess.check_output(['git', 'branch', '--show-current'], text=True).strip() == 'm1'
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only'], text=True).strip()
assert not subprocess.check_output(['git', 'diff', '1627a39050cc5e8c88f223c56eb870f085091dd9', 'HEAD', '--', 'services/aos-api', 'scripts', 'bundles', 'apps/web'], text=True)
p = m.DEFAULT_PATHS
a = m.load_authority(p)
assert a['project_revision'] == 'AOS-002031'

def read(path):
    return json.loads(path.read_text())

def save(name, value):
    m.scan_secrets(value)
    with (E / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())

def legal(folder, prefix, version):
    request = read(folder / f'{prefix}-request-{version}.json')
    result_path = folder / f'{prefix}-result-{version}.json'
    result = read(result_path)
    transport = read(result_path.with_suffix('.transport.json'))
    consumption = read(folder / f'{prefix}-consumption-{version}.json')
    assert g.consumption_record(request, result, transport, result['runner_sha256']) == consumption
    assert consumption['status'] == 'CONSUMED_MATERIAL_REVIEW'
    assert result['result']['verdict'] == 'PASS'

for name, version in [('qyh-creator-closure-read-admission-20261015', 'r1'), ('qyh-creator-closure-bounded-reader-20261015', 'r1'), ('qyh-creator-closure-readonly-client-20261015', 'r3'), ('qyh-creator-closure-readonly-contract-20261015', 'r1')]:
    legal(R / '.evidence' / name, 'code-review', version)
for prefix, version in [('api-controller-review', 'r1'), ('web-controller-review', 'r2'), ('closure-live-review', 'r1')]:
    legal(E, prefix, version)
proof = read(E / 'creator-closure-final-runtime-proof-r2.json')
assert proof['tables650Equal'] and proof['commandsRemainEmptyInActualSDK'] and proof['webManifestVerified']
assert not proof['wholeGoalComplete'] and not proof['businessWrites']
for pid, port in [(72678, 18080), (76677, 18434)]:
    os.kill(pid, 0)
    listener = subprocess.check_output(['lsof', '-nP', '-a', '-p', str(pid), f'-iTCP:{port}', '-sTCP:LISTEN'], text=True)
    assert str(pid) in listener
pg = json.loads(subprocess.check_output(['docker', '--context', 'colima-aos-extension', 'inspect', 'qyh-restored-pg-20261011'], text=True))[0]
assert pg['State']['Running'] and pg['State']['StartedAt'] == proof['pgSameStartedAt']
assert any(x.get('Name') == proof['originalVolume'] for x in pg['Mounts'])

ids = ['qyh-creator-closure-read-admission-20261015', 'qyh-creator-closure-bounded-reader-20261015', 'qyh-creator-closure-readonly-client-20261015', 'qyh-creator-closure-readonly-contract-20261015', 'qyh-restoration-readonly-continuation-r4-20261015']
leases = m.load_leases(p)['leases']
rows = {}
for tid in ids:
    matches = [x for x in leases if x['task_id'] == tid]
    assert len(matches) == 1
    rows[tid] = matches[0]
    assert matches[0]['owner'] == owner and matches[0]['base_revision'] == 'AOS-002031'
    assert datetime.datetime.fromisoformat(matches[0]['lease_expires_at']) > datetime.datetime.now(datetime.timezone.utc)
others = [x for x in leases if x['task_id'] not in ids]
for tid, row in rows.items():
    for other in leases:
        if other['task_id'] != tid:
            assert not m.scopes_overlap(row['scope'], other['scope'])
changed = ['aos-platform/' + x for x in subprocess.check_output(['git', 'diff', '--name-only', '2f9362bb8fcf71eb167d8d18630a7d82cdeef824', 'HEAD'], text=True).splitlines()]
dwave = 'docs/palantier/20_tech/电商平台接入/微商城电商接入方案/D-waves/2026-10-13-QYH-八台只读入口恢复与经营链接续清单.md'
changed.append(dwave)
save('closure-wave-handoff-intent-r1.json', {'authorityBefore': 'AOS-002031', 'authorityExpected': 'AOS-002032', 'head': head, 'tasks': ids, 'otherLeasesPreserved': len(others), 'wholeGoalComplete': False, 'personalMemoryWrites': False})
results = [
    'ONLY creator closure GET installed readonly admission delivered; genuine OIDC GET and SDK200, query400/anonymous401; price/customer closure remain404; POST and operating authority unchanged.',
    'ONLY dedicated saved creator closure four-table bounded REPEATABLE_READ readonly reader delivered; original typed hash/ledger/NULLmodule/refs/tenant/privacy/time checks; exact frozen244PASS and isolated native snapshot/RLS/write25006/byteguard. No producer or business completion.',
    'ONLY original SDK parser exact empty or original ordered four commands delivered; drift rejected, actual normal OIDC SDK retains empty commands; frozen407PASS/typecheck0; no commands invented or component/CSS changes.',
    'ONLY public contribution response command type original fixed tuple or empty tuple delivered; no casts/othercontract changes, same frozen407PASS/typecheck0 and actual SDK evidence.',
    'SAME_OWNER_HANDOFF of ALL remaining original restoration/231Goal/user authorization/daily aos latest original-volume fullPG/API/Web requirements. Verified ONLY current read slice API53/Web1627 and original650 unchanged; API/Web refresh is not a daily replacement, whole restoration/business/visual/release incomplete.'
]
risks = ['Original650/schema161 DB READONLY, Host/worker/Provider OFF; budget162 not deployed; source/old12/unknownRun/disabledSchedule/noPush boundaries retained.', 'FullC unique genuine user final budget/original deployment, natural business first chain, install/config/deny/recover/uninstallreinstall, eight real scenarios, visualP1, observation and release remain incomplete.', 'Current real saved contribution axes null; isolated fixture does not prove business records or genuine approval.']
for tid, result in zip(ids, results):
    files = [f for f in changed if any(f == s or f.startswith(s.rstrip('/') + '/') for s in rows[tid]['scope'])]
    assert files
    delivery = m.complete_task(p, task_id=tid, expected_revision='AOS-002031', result=result, changed_files=files, commits=['53d572ba3265d77835a49ee92441c7ce26ea7faa', '1627a39050cc5e8c88f223c56eb870f085091dd9', head], verification=['Exact frozen code and runtime Prime PASS legally consumed; original raw evidence retained.', 'Backend244PASS/Web407PASS/typecheck0; real original OIDC native and actual SDK commands empty,650 before/after unchanged; original writes absent.', 'Source/API72678/Web76677 and original PG/volume verified; three viewports retain creator1280 crop P1; no full visual/business acceptance.'], risks=risks, blockers=[])
    save(tid + '-delivery-copy-r1.json', delivery)

new = m.update_authority(p, expected_revision='AOS-002031', current_phase='Creator saved closure readonly API and SDK slice delivered; full longGoal ACTIVE; next price contribution readonly audit', delivery_status='ONLY four exact creator readonly slices and ALL remaining maintenance handoff; full restoration/business/visual/release incomplete', last_green_gate='53 backend244/1627 Web407+typecheck0; exact code/control/live Prime PASS legally consumed; real OIDC native and SDK readonly200/401400; original650 unchanged', next_gate='Price contribution auxiliary GET default producer/store/DTO/tenant/privacy/cutoff/bounds audit then exact plan before RED/admission; all fullC/business/install/visual/observe goals retained', completed=[*a['completed'], 'Creator saved closure GET bounded four-table reader and SDK empty-command contract delivered only; supersedes closure404 pending only for creator readonly slice, not price/customer/operating authority.', 'Actual API72678/source53 and Web76677/source1627 code trees equal evidence HEAD f1a1f51; original650 unchanged. API/Web reading refresh not daily substitute; original daily full6bf evidence retained.'], incomplete=[*a['incomplete'], 'Remaining price contributions/dispositions/closure and customer contribution/contact/closure private auxiliary reads individually pending; fullC genuine-user final budget/original deployment/natural business/install lifecycle/eight real scenarios/visualP1/continuous observation release remain.'], next_steps=[*a['next_steps'], 'Immediately audit registered price contribution GET readonly producer/transitiveStore/nestedDTO/tenant/privacy/consistency/bounds/authorization; separately register extra files before coding.'], source_commits={**a['source_commits'], 'qyh-creator-closure-backend': '53d572ba3265d77835a49ee92441c7ce26ea7faa', 'qyh-creator-closure-client': '1627a39050cc5e8c88f223c56eb870f085091dd9', 'qyh-creator-closure-live': head}, hard_boundaries=a['hard_boundaries'], evidence=[*a['evidence'], {'path': 'aos-platform/.evidence/qyh-restoration-readonly-continuation-r4-20261015/closure-live-review-consumption-r1.json', 'summary': 'Exact readonly live slice PASS legally consumed; not whole Goal completion.'}, {'path': 'aos-platform/.evidence/qyh-restoration-readonly-continuation-r4-20261015/creator-closure-live-report-r1.md', 'summary': 'Genuine OIDC native+actual SDK readonly facts/source/data/remaining P1 and full scope.'}])
assert new['project_revision'] == 'AOS-002032'
save('closure-authority-update-r1.json', {'old': 'AOS-002031', 'new': 'AOS-002032', 'wholeGoalComplete': False})
with m.memory_lock(p, exclusive=True):
    projection = m.canonical_projection(m.load_authority(p))
    prime = []
    for item in m.load_manifest(p)['projections']:
        if item.get('consistency') != 'strong':
            continue
        if item['adapter'] == 'prime_harness':
            prime.append(item)
            continue
        path = m.expand_path(item['path'], p)
        if item['adapter'] == 'authority_frontmatter':
            desired = m.render_frontmatter(path.read_text() if path.exists() else '', projection)
        elif item['adapter'] == 'json_file':
            desired = json.dumps(m.projection_document(projection), ensure_ascii=False, indent=2, sort_keys=True) + '\n'
        else:
            raise AssertionError('unexpected strong adapter')
        m.scan_secrets(desired)
        m.atomic_write_text(path, desired)
    m.sync_prime(p, projection, prime)
status = m.memory_status(p)
save('closure-strong-memory-status-r1.json', status)
assert all(x['status'] == 'CURRENT' for x in status['projections'] if x['consistency'] == 'strong')

expiry = '2026-10-15T02:00:00+00:00'
old = rows[ids[-1]]
maintenance = m.start_task(p, task_id='qyh-restoration-readonly-continuation-r5-20261015', owner=owner, expected_revision='AOS-002032', scope=[*old['scope'], 'aos-platform/.evidence/qyh-restoration-readonly-continuation-r5-20261015'], excluded_scope=old['excluded_scope'], expected_outputs=[*old['expected_outputs'], 'Carry ALL original remaining restoration/user authorization/full231Goal. Current API72678/source53 and Web76677/source1627 trees equal f1a1f51, original PG started20:36:36/schema161/650/bindings0. Future daily/every aos latest committed m1 original-volume fullPG/API/Web preserved; aos2 no restart. Read wave handoff is not full completion.'], lease_expires_at=expiry)
next_task = m.start_task(p, task_id='qyh-price-contribution-read-admission-20261015', owner=owner, expected_revision='AOS-002032', scope=['aos-platform/services/aos-api/aos_api/routers/ecommerce_workshop.py', 'aos-platform/services/aos-api/tests/test_ecommerce_workshop_read_http.py', 'aos-platform/.evidence/qyh-price-contribution-read-admission-20261015', dwave], excluded_scope=['aos-platform/apps/web', 'aos-platform/maintenance/qiyuehui-restored-data-volume', 'aos-platform/services/aos-api/aos_api/aip_action_execution.py', 'aos-platform/services/aos-api/aos_api/aip_action_store.py'], expected_outputs=['Full231Goal and eight step Loop preserved; initial readonly audit price contributions GET defaultproducer/transitiveStore/tenant/nestedDTO/privacy/consistentcutoff/bounds/error/authorization before exact plan and Prime/RED.', 'Register extra product files separately before code; no source/businesswrite/budgetapproval/Provider/oldunknown replay or implicit priceclosure/customer admission. Same viewport original visual comparison remains required for applicable UI waves.'], lease_expires_at=expiry)
active = m.load_leases(p)['leases']
assert maintenance in active and next_task in active
assert [x for x in active if x['task_id'] not in [maintenance['task_id'], next_task['task_id']]] == others
for row in [maintenance, next_task]:
    assert row['owner'] == owner
    for other in active:
        if row['task_id'] != other['task_id']:
            assert not m.scopes_overlap(row['scope'], other['scope'])
save('closure-next-wave-readback-r1.json', {'authority': 'AOS-002032', 'maintenance': maintenance, 'nextTask': next_task, 'owner': owner, 'nonOverlapping': True, 'otherLeasesPreserved': len(others), 'wholeGoalComplete': False, 'personalMemoryWrites': False})
print(json.dumps({'authority': 'AOS-002032', 'sliceDeliveries': 4, 'maintenanceAllRemainingHandoff': True, 'nextTask': next_task['task_id'], 'strongCurrent': sum(x['consistency'] == 'strong' and x['status'] == 'CURRENT' for x in status['projections']), 'otherLeasesPreserved': len(others), 'goal': 'ACTIVE'}))
