"""One exact reviewed Web switch; original API/PG/Chrome never signaled."""
from pathlib import Path
import argparse
import datetime
import hashlib
import io
import json
import os
import signal
import subprocess
import sys
import tarfile
import time

E = Path(__file__).resolve().parent
R = E.parents[1]
HEAD = '8dbb4c7c3f48ee161f4d6bf231b35c865a77caf5'
OWNER = 'codex-01a13484-f019-7d82-94ce-812396db9124'
OLD = 89803
API = 54057
NODE = '/Users/ddt/.workbuddy/binaries/node/versions/22.22.2-2/bin/node'
OLD_E = R / '.evidence/qyh-restoration-readonly-continuation-r6-20261015'
CSS = 'apps/web/src/styles/45-ecommerce-workshop.css'
sys.path.insert(0, str(R / 'scripts/long-task-watchdog'))
import aos_review as gate
sys.path.insert(0, str(R / 'scripts'))
import a0v_qyh_restored_http as guard


def read(p): return json.loads(p.read_text())
def cmd(*args): return subprocess.check_output(args, cwd=R, text=True, timeout=30).strip()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def save(name, value):
    with (E / name).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def listeners(port): return sorted({int(x) for x in cmd('lsof', '-t', '-nP', f'-iTCP:{port}', '-sTCP:LISTEN').split()})
def cwd(pid): return next(x[1:] for x in cmd('lsof', '-a', '-p', str(pid), '-d', 'cwd', '-Fn').splitlines() if x.startswith('n'))


def legal(folder, prefix, version):
    q = read(folder / f'{prefix}-request-{version}.json')
    v = read(folder / f'{prefix}-result-{version}.json')
    t = read(folder / f'{prefix}-result-{version}.transport.json')
    assert v['result']['verdict'] == 'PASS'
    assert gate.consumption_record(q, v, t, v['runner_sha256']) == read(folder / f'{prefix}-consumption-{version}.json')


def disk_manifest(source):
    return {str(p.relative_to(source)): sha(p) for p in source.rglob('*') if p.is_file()}


def base():
    assert cmd('git', 'rev-parse', 'HEAD') == HEAD and cmd('git', 'branch', '--show-current') == 'm1'
    memory = R.parent / 'docs/palantier/AOS项目开发上下文/memory'
    lease = read(memory / 'receipts/tasks' / (E.name + '.json'))
    assert lease in read(memory / 'leases.json')['leases'] and lease['owner'] == OWNER
    assert lease['base_revision'] == read(memory / 'authority.json')['project_revision'] == 'AOS-002039'
    assert datetime.datetime.fromisoformat(lease['lease_expires_at']) > datetime.datetime.now(datetime.timezone.utc)
    assert listeners(18080) == [API]
    api_source = guard.require_api_source_candidate(R / '.evidence/qyh-full-system-restoration-20261011/customer-closure-api-20261015.json')
    assert cwd(API) == str(api_source)
    assert not cmd('git', 'diff', '0b0c88882ce6e9cdab168baf485ef50fa5baefb7', 'HEAD', '--', 'services/aos-api', 'scripts', 'bundles')
    assert listeners(18434) == [OLD] and cwd(OLD) == str(R)
    assert cmd('ps', '-p', str(OLD), '-o', 'command=') == NODE + ' ' + str(OLD_E / 'price-visual-web-server.mjs')
    old = read(OLD_E / 'price-visual-web-source.json')
    assert old['head'] == 'f036e46c643308651b415179e6e991870dbc26ab'
    assert disk_manifest(Path(old['source'])) == old['manifest']
    pg = json.loads(cmd('docker', '--context', 'colima-aos-extension', 'inspect', 'qyh-restored-pg-20261011'))[0]
    assert pg['Id'] == '84989681fb7d3fc0f42d750672547ca0208fbba08dfef0d93837d8e64245dc3c'
    assert pg['State']['Running'] and pg['State']['StartedAt'] == '2026-10-14T20:36:36.408087963Z'
    assert len(pg['Mounts']) == 1 and pg['Mounts'][0]['Name'] == 'aos-qyh-history159-prepared-data-20261011'
    product = R / '.evidence/qyh-customer-visual-pointer-20261015'
    legal(product, 'code-review', 'r1')
    proof = read(product / 'source-verification-r1.json')
    assert all(x['returncode'] == 0 for x in proof['results'].values())
    web = read(E / 'customer-pointer-web-source.json')
    source = Path(web['source'])
    assert web['head'] == HEAD and web['port'] == 18434 and web['apiTarget'] == 'http://127.0.0.1:18080'
    assert disk_manifest(source) == web['manifest'] and sha(source / CSS) == proof['cssAfter']
    git_manifest = {}
    raw = subprocess.check_output(['git', 'archive', HEAD, 'apps/web', 'packages/ontology-sdk', 'packages/ui-kit'], cwd=R)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for item in archive.getmembers():
            if item.isfile() and not any(x.startswith('.env') for x in Path(item.name).parts):
                git_manifest[item.name] = hashlib.sha256(archive.extractfile(item).read()).hexdigest()
    assert git_manifest == web['manifest']
    assert sha(E / 'customer-pointer-web-server.mjs') == web['entrySha256']
    return web, pg


def quality():
    request = read(E / 'web-controller-review-request-r2.json')
    assert request['task_id'] == E.name and request['owner'] == OWNER
    gate.validate_request(R, request)
    legal(E, 'web-controller-review', 'r2')
    assert 'CONTROLLER_SHA ' + sha(Path(__file__)) in (E / 'web-controller-review-package-r2.txt').read_text()


parser = argparse.ArgumentParser()
parser.add_argument('--phase', choices=['preflight', 'web'], required=True)
args = parser.parse_args()
web, pg = base()
if args.phase == 'preflight':
    before = read(R / '.evidence/qyh-restoration-successor-latest-restart-20261013/customer-pointer-web-before-20261015.json')
    assert before['containerId'] == pg['Id'] and before['pgStartedAt'] == pg['State']['StartedAt']
    assert before['native']['schema'] == 'a0v_161' and before['native']['enabledBindings'] == 0 and len(before['fingerprints']) == 650
    native = guard.preflight(R / '.evidence/qyh-full-system-restoration-20261011/private/restored-identity.json', management_readonly=True)
    save('web-preflight-r1.json', dict(head=HEAD, oldWebPid=OLD, apiPid=API, nativeManagementReadonly=native, manifestVerifiedAgainstGit=True, oldSourceManifestVerified=True, sourceHashesVerified=True, otherServicesTouched=False))
    sys.exit(0)
quality()
assert not (E / 'pointer-web-switch-intent-r1.json').exists() and not (E / 'pointer-web-started-r1.json').exists(), 'known intent: reconcile, no replay'
assert read(E / 'web-preflight-r1.json')['head'] == HEAD
save('pointer-web-switch-intent-r1.json', dict(head=HEAD, oldPid=OLD, oldEntry=str(OLD_E / 'price-visual-web-server.mjs'), source=web['source'], pgApiChromeTouched=False))
os.kill(OLD, signal.SIGTERM)
for _ in range(100):
    result = subprocess.run(['lsof', '-t', '-nP', '-iTCP:18434', '-sTCP:LISTEN'], capture_output=True, text=True)
    if not result.stdout.strip(): break
    time.sleep(.2)
else: raise RuntimeError('old Web stop unresolved: reconcile only')
save('pointer-web-old-stop-r1.json', dict(oldPid=OLD, portFree=True))
env = {k: v for k, v in os.environ.items() if not k.startswith(('AOS_', 'PG', 'VITE_'))}
with (E / 'customer-pointer-live-web-r1.log').open('x') as stream:
    process = subprocess.Popen([NODE, str(E / 'customer-pointer-web-server.mjs')], cwd=R, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
save('pointer-web-started-r1.json', dict(head=HEAD, pid=process.pid, source=web['source'], spawnedOnly=True))
print(dict(webPid=process.pid, spawnedOnly=True))
