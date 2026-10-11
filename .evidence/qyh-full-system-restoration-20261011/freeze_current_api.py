"""Freeze exact committed API sources privately; never start or switch a service."""
import ast
import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

R = Path(__file__).resolve().parent
ROOT = R.parents[1]

def digest(value):
    return hashlib.sha256(value).hexdigest()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt-stem', default='frozen-current-api-candidate')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,100}', args.receipt_stem):
        parser.error('receipt stem must be a bounded lowercase filename')
    assert subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT,
        text=True).strip() == 'm1'
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    result_path = R / (args.receipt_stem + '.json')
    intent_path = R / (args.receipt_stem + '-intent.json')
    destination = R / 'private' / ('api-source-' + head)
    assert not result_path.exists() and not intent_path.exists() and not destination.exists(), 'Existing candidate: reconcile only'
    archive = subprocess.check_output(['git', 'archive', '--format=tar', head,
        'services/aos-api', 'scripts'], cwd=ROOT, timeout=60)
    members = []
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as tar:
        for member in tar.getmembers():
            relative = PurePosixPath(member.name)
            assert not relative.is_absolute() and '..' not in relative.parts
            assert member.isfile() or member.isdir(), 'Regular Git sources only'
            assert relative.parts[0] in {'services', 'scripts'}
            assert '.env' not in relative.parts, 'Environment credentials forbidden'
            if member.isfile():
                stream = tar.extractfile(member)
                assert stream is not None
                members.append((member.name, stream.read()))
    manifest = {name: digest(data) for name, data in members}
    assert len(manifest) == len(members) and len(manifest) > 1000
    source = dict(members)
    main = ast.parse(source['services/aos-api/aos_api/main.py'])
    enabled_names = {n.value for n in ast.walk(main) if isinstance(n, ast.Constant)
        and isinstance(n.value, str) and n.value.startswith('AOS_') and n.value.endswith('_ENABLED')}
    previous = ast.parse(source['scripts/a0v_current_preview_http.py'])
    assignments = [n for n in previous.body if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'FLAGS' for t in n.targets)]
    assert len(assignments) == 1
    flags = ast.literal_eval(assignments[0].value)
    assert enabled_names <= set(flags), 'Current startup worker switch missing original OFF flag'
    assert all(flags[k] in {'false', '0'} for k in enabled_names)
    assert flags['AOS_EXTENSION_RUNTIME_HOST_ENABLED'] == '0'
    assert flags['AOS_DB_MIGRATION_MODE'] == 'disabled'
    flags.update({'AOS_AUTH_ALLOW_DEV': '0', 'AOS_AUTH_EXTERNAL_ONLY': '1',
        'AOS_REST_CONNECTOR_MOCK': '0'})
    # All checks precede filesystem creation. Intent is durable before copying.
    with intent_path.open('x') as stream:
        json.dump({'head': head, 'destination': str(destination), 'fileCount': len(members),
            'serviceStart': False, 'originalPreviewTouched': False}, stream, indent=2)
        stream.write('\n')
    destination.mkdir(mode=0o700)
    for name, data in members:
        target = destination / name
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        for parent in target.parents:
            if parent == destination.parent:
                break
            parent.chmod(0o700)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
    observed = {str(p.relative_to(destination)): digest(p.read_bytes())
        for p in destination.rglob('*') if p.is_file()}
    assert observed == manifest
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode()
    fd = os.open(destination.parent / ('api-manifest-' + head + '.json'),
        os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(manifest_bytes)
    report = {'outcome': 'CURRENT_M1_API_SOURCE_CANDIDATE_FROZEN_NO_START',
        'head': head, 'source': str(destination), 'fileCount': len(manifest),
        'manifestSha256': digest(manifest_bytes),
        'mainSha256': manifest['services/aos-api/aos_api/main.py'],
        'originalPreviewEntrySha256': manifest['scripts/a0v_current_preview_http.py'],
        'explicitStartupEnabledSwitches': sorted(enabled_names), 'startupFlags': flags,
        'exactGitArchiveFilesVerified': True, 'sourcePrivate0700Files0600': True,
        'uncommittedWorktreeChangesCopied': False, 'credentialsCopied': False,
        'apiStarted': False, 'runtimeAuthorized': False, 'eightPagesAccepted': False,
        'remaining': ['real independent publisher', 'current four-package installation',
            'formal OIDC settings and current Owner', 'current configuration approval',
            'guarded PG/API/Web restart and actual eight-page browser acceptance']}
    with result_path.open('x') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'outcome': report['outcome'], 'head': head, 'fileCount': len(manifest),
        'manifestSha256': report['manifestSha256'], 'apiStarted': False}))
