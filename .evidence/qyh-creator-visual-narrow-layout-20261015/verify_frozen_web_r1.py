"""Commit archive plus one CSS overlay; isolated existing tests, type and build."""
from pathlib import Path, PurePosixPath
import datetime
import hashlib
import io
import json
import os
import subprocess
import tarfile

E = Path(__file__).resolve().parent
R = E.parents[1]
HEAD = '40100ba60a3d08375e59d8e3ddfec38c8fc5e51c'
CSS = 'apps/web/src/styles/45-ecommerce-workshop.css'
NODE = '/Users/ddt/.workbuddy/binaries/node/versions/22.22.2-2/bin/node'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=R, text=True).strip() == HEAD
before = hashlib.sha256((R / CSS).read_bytes()).hexdigest()
source = E / 'private/candidate-source-r1'
assert not source.exists() and not (E / 'candidate-freeze-intent-r1.json').exists()
raw = subprocess.check_output(['git', 'archive', HEAD, 'apps/web', 'packages/ontology-sdk', 'packages/ui-kit'], cwd=R)
members = {}
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
    for item in archive.getmembers():
        path = PurePosixPath(item.name)
        assert not path.is_absolute() and '..' not in path.parts and (item.isfile() or item.isdir())
        if item.isfile() and not any(x.startswith('.env') for x in path.parts):
            members[item.name] = archive.extractfile(item).read()
members[CSS] = (R / CSS).read_bytes()
with (E / 'candidate-freeze-intent-r1.json').open('x') as stream:
    json.dump(dict(head=HEAD, source=str(source), overlay={CSS: before}, onlyOneOwnedCSSOverlay=True, userDirtyCopied=False, originalServicesTouched=False), stream, indent=2)
    stream.flush()
    os.fsync(stream.fileno())
source.mkdir(parents=True, mode=0o700)
for name, body in members.items():
    path = source / name
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(body)
    path.chmod(0o600)
manifest = {name: hashlib.sha256(body).hexdigest() for name, body in members.items()}
assert {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()} == manifest
(source / 'apps/web/node_modules').symlink_to(R / 'apps/web/node_modules', target_is_directory=True)
config = E / 'private/frozen-verification-config-r1.ts'
with config.open('x') as stream:
    stream.write('import base from ' + json.dumps(str(source / 'apps/web/vite.config.ts')) + ';\nexport default {...base,cacheDir:' + json.dumps(str(E / 'private/verification-cache-r1')) + ',envDir:' + json.dumps(str(E / 'private/no-env')) + ',test:{...base.test,cache:false}};\n')
commands = {
    'workshop-cumulative-r1': [NODE, 'node_modules/vitest/vitest.mjs', 'run', 'src/components/workshop', 'src/api/ecommerceWorkshop', '--config', str(config), '--no-cache'],
    'web-typecheck-r1': [NODE, 'node_modules/typescript/bin/tsc', '--noEmit'],
    'web-production-build-r1': [NODE, 'node_modules/vite/bin/vite.js', 'build', '--config', str(config)],
}
env = {k: v for k, v in os.environ.items() if not k.startswith(('AOS_', 'PG', 'VITE_', 'OPENAI_'))}
env.update(CI='1', NO_COLOR='1')
results = {}
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
for name, command in commands.items():
    with (E / (name + '.log')).open('x') as stream:
        process = subprocess.run(command, cwd=source / 'apps/web', env=env, stdout=stream, stderr=subprocess.STDOUT)
    results[name] = dict(returncode=process.returncode, command=command, logSha=hashlib.sha256((E / (name + '.log')).read_bytes()).hexdigest())
after = hashlib.sha256((R / CSS).read_bytes()).hexdigest()
assert before == after
assert all(hashlib.sha256((source / n).read_bytes()).hexdigest() == h for n, h in manifest.items())
with (E / 'source-verification-r1.json').open('x') as stream:
    json.dump(dict(baseHead=HEAD, cssBefore=before, cssAfter=after, source=str(source), manifest=manifest, onlyOneOwnedCSSOverlay=True, originalComponentUnchanged=True, noUserDirtyCopied=True, privateBuildAndCache=True, results=results, startedAt=started, finishedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(), originalServicesTouched=False, geometryAcceptance='pending actual browser after guarded Web update; no JSDOM geometry claim'), stream, indent=2)
print(json.dumps({k: v['returncode'] for k, v in results.items()}))
assert all(v['returncode'] == 0 for v in results.values())
