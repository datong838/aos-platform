"""Deliver only customer pointer slice, retain entire original Goal and remaining work."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys

E = Path(__file__).resolve().parent
R = E.parents[1]
OWNER = 'codex-01a13484-f019-7d82-94ce-812396db9124'
CODE = '8dbb4c7c3f48ee161f4d6bf231b35c865a77caf5'
HEAD = '50f9dfb91cdbbace10a34e9581c6182e611e414e'
sys.path.insert(0, str(R / 'scripts/memory'))
import memoryctl as m
sys.path.insert(0, str(R / 'scripts/long-task-watchdog'))
import aos_review as gate


def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def cmd(*args): return subprocess.check_output(args, cwd=R, text=True).strip()


def save(name, value):
    m.scan_secrets(value)
    with (E / name).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def legal(folder, prefix, version, runner='review_controller.py'):
    request = read(folder / f'{prefix}-request-{version}.json')
    result = read(folder / f'{prefix}-result-{version}.json')
    raw = read(folder / f'{prefix}-result-{version}.transport.json')
    assert result['result']['verdict'] == 'PASS'
    assert result['runner_sha256'] == sha(folder / runner)
    assert result['validator_sha256'] == sha(Path(gate.__file__))
    assert gate.consumption_record(request, result, raw, result['runner_sha256']) == read(folder / f'{prefix}-consumption-{version}.json')


assert cmd('git', 'rev-parse', 'HEAD') == HEAD and cmd('git', 'branch', '--show-current') == 'm1'
assert not cmd('git', 'diff', '--cached', '--name-only')
assert not cmd('git', 'diff', CODE, 'HEAD', '--', 'apps/web', 'packages', 'services/aos-api', 'scripts', 'bundles')
product = R / '.evidence/qyh-customer-visual-pointer-20261015'
legal(product, 'design-review', 'r3')
legal(product, 'code-review', 'r1')
legal(E, 'web-controller-review', 'r4', 'review_controller_r4.py')
legal(E, 'pointer-live-review', 'r2')
proof = read(E / 'pointer-runtime-proof-r2.json')
assert proof['all650BeforeAfterEqual'] and proof['threeViewportsNativePointerAndKeyboardPassed']
assert not proof['wholeVisualComplete'] and not proof['wholeGoalComplete']
assert cmd('lsof', '-t', '-nP', '-iTCP:18080', '-sTCP:LISTEN') == '54057'
assert cmd('lsof', '-t', '-nP', '-iTCP:18434', '-sTCP:LISTEN') == '61045'
assert proof['apiSource'] in cmd('lsof', '-a', '-p', '54057', '-d', 'cwd', '-Fn')
pg = json.loads(cmd('docker', '--context', 'colima-aos-extension', 'inspect', 'qyh-restored-pg-20261011'))[0]
assert pg['Id'] == proof['originalContainerId'] and pg['State']['StartedAt'] == proof['pgStartedAt']
assert pg['Mounts'][0]['Name'] == proof['originalVolume']
p = m.DEFAULT_PATHS
a = m.load_authority(p)
assert a['project_revision'] == 'AOS-002039'
leases = m.load_leases(p)['leases']
ids = [product.name, E.name]
rows = {}
for tid in ids:
    found = [x for x in leases if x['task_id'] == tid]
    assert len(found) == 1
    row = rows[tid] = found[0]
    assert row['owner'] == OWNER and row['base_revision'] == 'AOS-002039'
    assert datetime.datetime.fromisoformat(row['lease_expires_at']) > datetime.datetime.now(datetime.timezone.utc)
    assert all(not m.scopes_overlap(row['scope'], x['scope']) for x in leases if x['task_id'] != tid)
others = [x for x in leases if x['task_id'] not in ids]
assert len(others) == 38
dwave = next(x for x in rows[product.name]['scope'] if x.startswith('docs/'))
changed = ['aos-platform/' + x for x in cmd('git', 'diff', '--name-only', 'bb7a742849f9109ad4fc2f9ed9e9cfd55ffbac3a', 'HEAD').splitlines()] + [dwave]
save('pointer-handoff-intent-r2.json', dict(head=HEAD, code=CODE, before='AOS-002039', expected='AOS-002040', tasks=ids, otherLeasesPreserved=38, wholeGoalComplete=False))
results = [
    'ONLY customer ordinary pointer/keyboard slice delivered: two scoped CSS declarations, unchanged components/layout/data/authority. Three actual widths fourtabs/tabpanel/fourfilters/arrowHomeEnd/TabEnter/focus visible/32px/no horizontal overflow with trusted native input and hit checks, no force/DOMclick. Frozen407/type/build/independent design-code-controller-live PASS legal; not fullvisual/business/install/Goal completion.',
    'SAME_OWNER_HANDOFF of ALL original remaining restoration/full231Goal/user original authorization/daily every actual aos latest committed m1 original-volume fullPGAPIWeb/aos2 noRestart. Latest runtime supersedes older identities: Web61045/source8dbb764, API54057/source0b0c888 backend equal latest, originalPGStarted20:36:36/schema161/650/bindings0. Only customer input slice delivered; all fullvisual/business/install/fullC genuine final budget/deployment/observe release remain.'
]
verification = ['Independent exact design r3, code r1, current controller r4 and live r2 PASS legally consumed. Prior NEED/old failed input/JWT read preserved, no auto-PASS or model JSON repair; original validator unchanged.',
    'Latest oneCSS-overlay frozen62files407tests/type/build/currentSHA unchanged; fresh committed Web764 manifest equals Git archive and disk; old source manifest and exactPID preflight, missing-review negative before intent/signal.',
    'Original genuine three-width native pointer: four filters unique pressed/four tabs matchingpanel; ordinary explicitbuttons1/0 with isTrusted witness and center hit checks; normal keyboard Arrow/Home/End/TabEnter and visible focus, filters32/no horizontal overflow; six CSS-sized current actual/reference images individually inspected.',
    'Actual me/customer/contact SDK/commands empty/fivefalse/query400/anonymous401/businessNonGET empty; known expired readonly JWT recovered by normal original form without token export; final650 dictionaries and originalPG/API unchanged.']
risks = ['Only input hit area repaired; customer real task/plan/progress/log/artifacts/360, navigation/banner/footer wording and nonempty/all failure states/a11y remain; creator1280 crop/Pagefake0/other fullvisual remain.',
    'Full original natural sourced business chain, install/configure/deny/recover/uninstall/reinstall, eight real scenarios, fullC sole genuine user final budget/original deployment and continuous release remain. Original DB readonly/HostworkerProviderOFF/oldunknown12noReplay/disabledScheduleOFF/sourceNoRead/noPush retained.']
for tid, result in zip(ids, results):
    files = [x for x in changed if any(x == s or x.startswith(s.rstrip('/') + '/') for s in rows[tid]['scope'])]
    assert files
    receipt = m.complete_task(p, task_id=tid, expected_revision='AOS-002039', result=result, changed_files=files, commits=[CODE, HEAD], verification=verification, risks=risks, blockers=[])
    save(tid + '-delivery-copy-r2.json', receipt)
incomplete = []
for value in a['incomplete']:
    if value.startswith('Customer ordinary filter pointer blocked by transparent customer-tabs'):
        value = 'Customer pointer/fourtab/keyboard slice now delivered at8dbb with genuine three-width proof, superseding historical blocked-pointer/tab-unverified clause. All remaining original fullC genuine budget/deployment/natural first chain/install/eight scenarios/fullvisual/continuous release remain.'
    incomplete.append(value)
new = m.update_authority(p, expected_revision='AOS-002039',
    current_phase='Customer native pointer and keyboard slice delivered; original650 unchanged; creator1280 crop next; full231Goal ACTIVE',
    delivery_status='ONLY customer pointer slice plus ALL remaining maintenance handoff, not fullvisual/business/install/release completion',
    last_green_gate='Product8dbb twoCSS/frozen407/type/build/design-code-controller4-live2 PASS legal; Web61045/source8dbb764, API54057 unchanged, original650 equal; real3width native input passes',
    next_gate='Creator1280 right-column clipping fresh original/actual same-width evidence, approved product review/file plan/nonoverlap Lease/independent plan before minimal CSS change; all original business/budget/install gates continue',
    completed=[*a['completed'], 'Only customer transparent-tablist hit area repaired with two scoped CSS declarations at8dbb. Original three widths fourtabs/fourfilters/panel/ordinary native input/keyboard/focus/32px/no horizontal overflow verified, source764/originalAPI/650 unchanged; no fullvisual/business/install completion.'],
    incomplete=[*incomplete, 'Creator1280 right-column P1 cropping remains next visual task; customer task/plan/log/artifact/360/footer semantics and other visual gaps preserved. Full231Goal/sole-user final true budget and original deployment/natural first chain/install lifecycle/eight real scenarios/continuous release not complete.'],
    next_steps=[*a['next_steps'], 'Latest next step supersedes completed customer pointer repair instruction: start newly registered creator1280 narrow-layout comparison/audit, then exact file plan/independent design/RED before minimal repair. Preserve all other original fullGoal/daily every actual aos latest original-volume fullPGAPIWeb/aos2 noRestart.'],
    source_commits={**a['source_commits'], 'qyh-customer-pointer-code': CODE, 'qyh-customer-pointer-live': HEAD}, hard_boundaries=a['hard_boundaries'],
    evidence=[*a['evidence'], {'path': 'aos-platform/.evidence/qyh-restoration-readonly-continuation-r12-20261015/pointer-live-review-consumption-r2.json', 'summary': 'Exact current pointer/keyboard/input-source-data preservation slice PASS legal, no whole visual or operating authority.'},
        {'path': 'aos-platform/.evidence/qyh-restoration-readonly-continuation-r12-20261015/eight-workbench-visual-tracker-r2.md', 'summary': 'Current customer3width real interaction plus original comparison and other7 historical gaps distinguished, full eight visual/business remaining.'}])
assert new['project_revision'] == 'AOS-002040'
save('pointer-authority-update-r2.json', dict(before='AOS-002039', after='AOS-002040', wholeGoalComplete=False))
with m.memory_lock(p, exclusive=True):
    projection = m.canonical_projection(m.load_authority(p))
    prime = []
    for item in m.load_manifest(p)['projections']:
        if item.get('consistency') != 'strong': continue
        if item['adapter'] == 'prime_harness': prime.append(item); continue
        path = m.expand_path(item['path'], p)
        if item['adapter'] == 'authority_frontmatter': desired = m.render_frontmatter(path.read_text() if path.exists() else '', projection)
        elif item['adapter'] == 'json_file': desired = json.dumps(m.projection_document(projection), ensure_ascii=False, indent=2, sort_keys=True) + '\n'
        else: raise AssertionError('Unexpected strong adapter')
        m.scan_secrets(desired)
        m.atomic_write_text(path, desired)
    m.sync_prime(p, projection, prime)
status = m.memory_status(p)
assert all(x['status'] == 'CURRENT' for x in status['projections'] if x['consistency'] == 'strong')
save('pointer-strong-memory-status-r2.json', status)
old = rows[E.name]
expiry = '2026-10-15T16:00:00+00:00'
maintenance = m.start_task(p, task_id='qyh-restoration-readonly-continuation-r13-20261015', owner=OWNER, expected_revision='AOS-002040', scope=[*old['scope'], 'aos-platform/.evidence/qyh-restoration-readonly-continuation-r13-20261015'], excluded_scope=old['excluded_scope'], expected_outputs=[*old['expected_outputs'], 'ALL original remaining231Goal/user authorization/daily every actual aos latest original-volume fullPGAPIWeb/aos2 noRestart retained. Latest runtime supersedes all older identities: Web61045/source8dbb764, API54057/source0b0c888 backend equal latest, originalPGStarted20:36:36/schema161/650/bindings0. Only customer native input slice verified; fullvisual/business/install/fullC final genuine budget/deployment/continuous release remain.'], lease_expires_at=expiry)
visual = m.start_task(p, task_id='qyh-creator-visual-narrow-layout-20261015', owner=OWNER, expected_revision='AOS-002040', scope=[
    'aos-platform/apps/web/src/styles/45-ecommerce-workshop.css', 'aos-platform/apps/web/src/components/workshop/CreatorGrowthPage.tsx', 'aos-platform/apps/web/src/components/workshop/CreatorGrowthPage.test.tsx',
    'aos-platform/.evidence/qyh-creator-visual-narrow-layout-20261015', dwave],
    excluded_scope=['aos-platform/services/aos-api', 'aos-platform/maintenance/qiyuehui-restored-data-volume', 'aos-platform/pnpm-lock.yaml'],
    expected_outputs=['Keep full231Goal and prior customer pointer fix. Fresh actual/reference1280/1440/1920 audit creator right-column crop P1 with current original identity/readonly state, read approved creator product five stages and draft-only/receipt/contract/PII boundaries; file-level plan and independent design before code.',
        'Minimal customer-preserving creator-only responsive layout fix after true RED; do not hide content/blockers or fill demos/unlock execution. Register extra files before edits; frozen tests/type/build, true normal native pointer explicitbuttons1/0 and keyboard/clip/scroll/same-size original acceptance, independent code/controller/live gates and accurate Delivery. Preserve original data/API/PG/source/unknown/daily/aos2 boundaries and all remaining business/install/visual goals.'], lease_expires_at=expiry)
after = m.load_leases(p)['leases']
assert [x for x in after if x['task_id'] not in [maintenance['task_id'], visual['task_id']]] == others
for row in [maintenance, visual]:
    assert row in after and all(not m.scopes_overlap(row['scope'], x['scope']) for x in after if x['task_id'] != row['task_id'])
save('pointer-next-wave-readback-r2.json', dict(authority='AOS-002040', maintenance=maintenance, nextTask=visual, owner=OWNER, otherLeasesPreserved=38, nonOverlapping=True, strongCurrent=7, personalMemoryWrites=False, wholeGoalComplete=False))
print(json.dumps(dict(authority='AOS-002040', inputSliceDelivered=True, allRemainingMaintenanceHandoff=True, nextTask=visual['task_id'], otherLeasesPreserved=38, strongCurrent=7, goal='ACTIVE')))
