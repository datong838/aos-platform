"""Exact saved-read delivery, all remaining Goal carried; never replay this intent."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys

E = Path(__file__).resolve().parent
R = E.parents[1]
sys.path.insert(0, str(R / 'scripts/memory'))
import memoryctl as m
sys.path.insert(0, str(R / 'scripts/long-task-watchdog'))
import aos_review as gate

OWNER = 'codex-01a13484-f019-7d82-94ce-812396db9124'
CODE = '0b0c88882ce6e9cdab168baf485ef50fa5baefb7'
HEAD = '04687f7fc7900a64fa964a3f5d92840987dec944'


def read(p): return json.loads(p.read_text())
def cmd(*args): return subprocess.check_output(args, cwd=R, text=True).strip()


def save(name, value):
    m.scan_secrets(value)
    with (E / name).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def legal(folder, prefix, version):
    request = read(folder / f'{prefix}-request-{version}.json')
    result = read(folder / f'{prefix}-result-{version}.json')
    raw = read(folder / f'{prefix}-result-{version}.transport.json')
    assert result['result']['verdict'] == 'PASS'
    assert gate.consumption_record(request, result, raw, result['runner_sha256']) == read(folder / f'{prefix}-consumption-{version}.json')


assert cmd('git', 'rev-parse', 'HEAD') == HEAD and cmd('git', 'branch', '--show-current') == 'm1'
assert not cmd('git', 'diff', '--cached', '--name-only')
assert not cmd('git', 'diff', CODE, 'HEAD', '--', 'services/aos-api', 'apps/web', 'scripts', 'bundles')
reader = R / '.evidence/qyh-customer-closure-bounded-reader-20261015'
parent = R / '.evidence/qyh-customer-closure-read-admission-20261015'
legal(reader, 'code-review', 'r1')
legal(parent, 'route-quality', 'r1')
legal(E, 'api-controller-review', 'r1')
legal(E, 'closure-live-review', 'r2')
proof = read(E / 'closure-runtime-proof-r1.json')
assert proof['all650BeforeAfterEqual'] and proof['actualCustomerClosureSdk200']
assert proof['filterPointerFailureAllWidths'] and not proof['tabsSwitchVerified']
assert not proof['wholeVisualComplete'] and not proof['wholeGoalComplete']
assert cmd('lsof', '-t', '-nP', '-iTCP:18080', '-sTCP:LISTEN') == '54057'
assert proof['apiSource'] in cmd('lsof', '-a', '-p', '54057', '-d', 'cwd', '-Fn')
assert cmd('lsof', '-t', '-nP', '-iTCP:18434', '-sTCP:LISTEN') == '89803'
pg = json.loads(cmd('docker', '--context', 'colima-aos-extension', 'inspect', 'qyh-restored-pg-20261011'))[0]
assert pg['Id'] == proof['originalContainerId'] and pg['State']['StartedAt'] == proof['pgStartedAt']
assert pg['Mounts'][0]['Name'] == proof['originalVolume']
p = m.DEFAULT_PATHS
a = m.load_authority(p)
assert a['project_revision'] == 'AOS-002038'
ids = [reader.name, parent.name, E.name]
leases = m.load_leases(p)['leases']
rows = {}
for tid in ids:
    found = [x for x in leases if x['task_id'] == tid]
    assert len(found) == 1
    row = rows[tid] = found[0]
    assert row['owner'] == OWNER and row['base_revision'] == 'AOS-002038'
    assert datetime.datetime.fromisoformat(row['lease_expires_at']) > datetime.datetime.now(datetime.timezone.utc)
    assert all(not m.scopes_overlap(row['scope'], x['scope']) for x in leases if x['task_id'] != tid)
others = [x for x in leases if x['task_id'] not in ids]
assert len(others) == 38
dwave = next(x for x in rows[parent.name]['scope'] if x.startswith('docs/'))
changed = ['aos-platform/' + x for x in cmd('git', 'diff', '--name-only', 'f3dd116e9c753e94af91667bf13da4f544938945', 'HEAD').splitlines()] + [dwave]
save('closure-handoff-intent-r1.json', dict(head=HEAD, code=CODE, before='AOS-002038', expected='AOS-002039', tasks=ids, otherLeasesPreserved=38, wholeGoalComplete=False))
results = [
    'ONLY bounded saved customer closure reader/tests delivered: original typed codec/hash/ID/ledger/exact refs, readonly RR/cutoff/SQL CASE/privacy/error/unknown/null/immature/request_more; no current Start/Consent/Receipt authority. Frozen558/native original W6-009/quality PASS legally consumed.',
    'ONLY canonical customer saved closure GET admission delivered: original genuine SDK200/four absent saved records/four blockers/commands empty/threefalse/query400/anonymous401/businessNonGET empty/650 unchanged. Visual FAILED/UNVERIFIED explicitly retained, not full business/install/Goal completion.',
    'SAME_OWNER_HANDOFF of ALL original remaining restoration/full231Goal/user original authorization/daily every actual aos latest m1 original-volume fullPGAPIWeb/aos2 noRestart. Current API54057/source0b0c888, Web89803/f036, originalPGStarted20:36:36/schema161/650/bindings0 supersede older identities. Customer filter pointer FAILED all widths and tab switching UNVERIFIED; all visual/business/install/fullC final genuine budget/deployment/observe release remain.'
]
verification = ['Exact current design/code/route-native/controller/live PASS legally consumed; NEED/RED/failed assertions/oversized pre-request drafts preserved.',
    'Frozen r3 only4owned overlays/558 tests/currentSHA unchanged; owned tmpfs originalW6-009 true empty/fiveaxes/snapshot/creator/RLS/25006/SQLCASE/privacy, exact CID stopped.',
    'Original actual me/customer SDK200/four nulls/four real blockers/emptycommands/threefalse/400/401/no businessNonGET and exact650 dictionaries unchanged.',
    'Six current CSS-sized screenshots individually inspected; no horizontal overflow/32px filters ONLY. Normal pointer FAILED tablist interception all three widths; tabs UNVERIFIED. No forced/DOM click rescue or full visual acceptance.']
risks = ['Full original business/install/eightvisual/continuousrelease remain; current saved references are not current Start/Consent/Receipt/operating authority.',
    'Customer transparent tablist blocks filters at1280/1440/1920; tabs ordinary click did not change selected state, cause not determined. Navigation/banner/task plan/log/artifacts/360/footer wording plus creator1280/Pagefake0 remain.',
    'OriginalDBreadonly/HostworkerProviderOFF/oldunknown12noReplay/disabledScheduleOFF/sourceNoRead/noPush. FullC sole genuine user final budget and original deployment remain separate.']
for tid, result in zip(ids, results):
    files = [x for x in changed if any(x == s or x.startswith(s.rstrip('/') + '/') for s in rows[tid]['scope'])]
    assert files
    receipt = m.complete_task(p, task_id=tid, expected_revision='AOS-002038', result=result, changed_files=files, commits=[CODE, HEAD], verification=verification, risks=risks, blockers=[])
    save(tid + '-delivery-copy-r1.json', receipt)
incomplete = list(a['incomplete'])
for i, value in enumerate(incomplete):
    if i >= 410 and ('customer' in value.lower() or 'creator workflowdrafts/closure404' in value):
        incomplete[i] = 'Historical read-route clauses below are superseded by current saved creator/price/customer GET Deliveries through AOS-002039; all listed business/install/visual/budget/release gaps remain: ' + value
new = m.update_authority(p, expected_revision='AOS-002038',
    current_phase='Customer saved closure GET delivered SDK200/650 unchanged; customer visual pointer FAILED registered next; full231Goal ACTIVE',
    delivery_status='ONLY saved closure reader+GET slice and ALL remaining maintenance same-owner handoff; no fullvisual/business/install/release completion',
    last_green_gate='Code0b0c888/frozen558/nativeW6-009/current code-route-controller-live PASS legal; API54057/Web89803/original650 unchanged; ordinary filter pointer FAILED retained',
    next_gate='Prioritize separate customer filter transparent-tablist pointer repair and tab state diagnosis with plan/Lease/RED/true browser; continue full original business/install/budget/other read audits',
    completed=[*a['completed'], 'Only customer saved closure GET/reader delivered: genuine SDK200/four missing saved records/four blockers/commands empty/threefalse/400/401/businessNonGET empty/650 unchanged. Six current screenshots reveal filter pointer failure all widths and tabs unverified; no full visual/current authority completion.'],
    incomplete=[*incomplete, 'Customer ordinary filter pointer blocked by transparent customer-tabs at all three widths; tab switching UNVERIFIED, cause pending. FullC final genuine budget/original deployment/natural first chain/install lifecycle/eight scenarios/fullvisual/continuous release remain.'],
    next_steps=[*a['next_steps'], 'Latest next step supersedes historical already-delivered read-audit instructions: customer saved contact/closure delivered. Prioritize newly registered customer visual pointer repair and tab diagnosis, preserving all full original goals/daily original-volume fullPGAPIWeb/aos2 noRestart.'],
    source_commits={**a['source_commits'], 'qyh-customer-closure-code': CODE, 'qyh-customer-closure-live': HEAD},
    hard_boundaries=a['hard_boundaries'], evidence=[*a['evidence'],
        {'path': 'aos-platform/.evidence/qyh-restoration-readonly-continuation-r11-20261015/closure-live-review-consumption-r2.json', 'summary': 'Saved read/identity/current runtime/recorded650/explicit visual failures PASS legal; no pixel/current operating authority claim.'},
        {'path': 'aos-platform/.evidence/qyh-restoration-readonly-continuation-r11-20261015/closure-live-report-r1.md', 'summary': 'Fresh customer closure SDK200 and original650 unchanged; six images and pointer interception/tab unverified candidly retained.'}])
assert new['project_revision'] == 'AOS-002039'
save('closure-authority-update-r1.json', dict(before='AOS-002038', after='AOS-002039', wholeGoalComplete=False))
with m.memory_lock(p, exclusive=True):
    projection = m.canonical_projection(m.load_authority(p))
    prime = []
    for item in m.load_manifest(p)['projections']:
        if item.get('consistency') != 'strong': continue
        if item['adapter'] == 'prime_harness':
            prime.append(item)
            continue
        path = m.expand_path(item['path'], p)
        if item['adapter'] == 'authority_frontmatter': desired = m.render_frontmatter(path.read_text() if path.exists() else '', projection)
        elif item['adapter'] == 'json_file': desired = json.dumps(m.projection_document(projection), ensure_ascii=False, indent=2, sort_keys=True) + '\n'
        else: raise AssertionError('Unexpected strong adapter')
        m.scan_secrets(desired)
        m.atomic_write_text(path, desired)
    m.sync_prime(p, projection, prime)
status = m.memory_status(p)
assert all(x['status'] == 'CURRENT' for x in status['projections'] if x['consistency'] == 'strong')
save('closure-strong-memory-status-r1.json', status)
old = rows[E.name]
expiry = '2026-10-15T16:00:00+00:00'
maintenance = m.start_task(p, task_id='qyh-restoration-readonly-continuation-r12-20261015', owner=OWNER, expected_revision='AOS-002039', scope=[*old['scope'], 'aos-platform/.evidence/qyh-restoration-readonly-continuation-r12-20261015'], excluded_scope=old['excluded_scope'], expected_outputs=[*old['expected_outputs'], 'ALL original remaining231Goal/user authorization retained. Latest runtime supersedes all older identities: API54057/source0b0c888, Web89803/f036, originalPGStarted20:36:36/schema161/650/bindings0. Saved closure read only delivered; customer pointer failure and tabs unverified/fullvisual/business/install/fullC final genuine budget/deployment/release remain. Daily every actual aos original-volume latest fullPGAPIWeb; aos2 noRestart.'], lease_expires_at=expiry)
visual = m.start_task(p, task_id='qyh-customer-visual-pointer-20261015', owner=OWNER, expected_revision='AOS-002039', scope=[
    'aos-platform/apps/web/src/styles/45-ecommerce-workshop.css',
    'aos-platform/apps/web/src/components/workshop/CustomerPage.tsx',
    'aos-platform/apps/web/src/components/workshop/CustomerPage.test.tsx',
    'aos-platform/.evidence/qyh-customer-visual-pointer-20261015', dwave],
    excluded_scope=['aos-platform/services/aos-api', 'aos-platform/maintenance/qiyuehui-restored-data-volume', 'aos-platform/pnpm-lock.yaml'],
    expected_outputs=['Full231Goal retained. Start from recorded genuine customer filter pointer interception by transparent tablist at1280/1440/1920; tab switch unverified, diagnose input/event/render cause before claiming product fix. Read approved customer product/visual plan, file plan and independent design before code.',
        'Minimal scoped pointer/layout repair without current authority/data/POST changes, appropriate RED and true browser pointer/keyboard/selected-state checks, exact CSS-size original comparison, frozen independent quality/live reviews and accurate Delivery. Do not force-click or DOMclick rescue, invent business data, claim fullvisual/business/Goal completion, or overwrite prior failure evidence. Register any further test or shared files first.'], lease_expires_at=expiry)
after = m.load_leases(p)['leases']
assert [x for x in after if x['task_id'] not in [maintenance['task_id'], visual['task_id']]] == others
for row in [maintenance, visual]:
    assert row in after and all(not m.scopes_overlap(row['scope'], x['scope']) for x in after if x['task_id'] != row['task_id'])
save('closure-next-wave-readback-r1.json', dict(authority='AOS-002039', maintenance=maintenance, nextTask=visual, owner=OWNER, otherLeasesPreserved=38, nonOverlapping=True, strongCurrent=7, personalMemoryWrites=False, wholeGoalComplete=False))
print(json.dumps(dict(authority='AOS-002039', savedReadSlicesDelivered=2, allRemainingMaintenanceHandoff=True, nextTask=visual['task_id'], otherLeasesPreserved=38, strongCurrent=7, goal='ACTIVE')))
