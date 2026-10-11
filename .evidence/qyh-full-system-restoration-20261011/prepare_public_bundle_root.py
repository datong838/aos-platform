"""Freeze four selected signed releases into one configured public root."""
import hashlib
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
import release_transition as T
from aos_api.asset_registry import control_wiring

OUTPUT = T.R / 'selected-public-bundles'

def fingerprints(root):
    result = {}
    for p in sorted(root.rglob('*')):
        assert not p.is_symlink(), 'Symlink not permitted in frozen public tree'
        if p.is_file():
            result[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result

if __name__ == '__main__':
    assert not OUTPUT.exists() and not (T.R / 'selected-public-root-intent.json').exists(), \
        'Prior preparation: reconcile without replacing output'
    trust = T.FileTrustRootProvider(T.TRUST).snapshot()
    source_loader = T.ManifestLoader({'a0v-canonical': T.LEGACY_ROOT,
        'a0v-qyh-current': T.CURRENT / 'signed-bundles'}, trust_roots=trust)
    sources = []
    for alias, bundle_id, version, retained in T.CASES:
        loaded = source_loader.load(f'bundle://{alias}/{bundle_id}/{version}')
        T.ReleasePolicy(trust_roots=trust).evaluate(
            T.OLD._load_builder()._release_record(loaded), checked_at=datetime.now(UTC))
        source = (T.LEGACY_ROOT if retained else T.CURRENT / 'signed-bundles') / bundle_id / version
        sources.append((alias, loaded, source, fingerprints(source)))
    T.record('selected-public-root-intent.json', {
        'task': 'qyh-full-system-restoration-20261011',
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=T.ROOT, text=True).strip(),
        'versions': [{'id': b.manifest.metadata.id, 'version': b.manifest.metadata.version,
                      'contentHash': b.content_hash} for _, b, _, _ in sources],
        'databaseWrites': 0, 'privateKeysCopied': False, 'globalConfigurationWrites': 0})
    OUTPUT.mkdir(mode=0o700)
    for _, b, source, before in sources:
        target = OUTPUT / b.manifest.metadata.id / b.manifest.metadata.version
        shutil.copytree(source, target)
        assert fingerprints(target) == fingerprints(source) == before
    os.environ['AOS_BUNDLE_ROOT'] = str(OUTPUT)
    roots = control_wiring._allowlist_roots(repository_root=T.ROOT)
    assert roots['a0v-qyh-current'] == roots['a0v-canonical'] == OUTPUT
    loader = T.ManifestLoader(roots, trust_roots=trust)
    rows = []
    for alias, b, source, before in sources:
        loaded = loader.load(f'bundle://{alias}/{b.manifest.metadata.id}/{b.manifest.metadata.version}')
        assert loaded.content_hash == b.content_hash
        assert loaded.signature == b.signature
        T.ReleasePolicy(trust_roots=trust).evaluate(
            T.OLD._load_builder()._release_record(loaded), checked_at=datetime.now(UTC))
        assert fingerprints(source) == before
        rows.append({'id': b.manifest.metadata.id, 'version': b.manifest.metadata.version,
            'contentHash': b.content_hash, 'modules': len(loaded.workshop_modules),
            'files': len(before), 'filesHash': hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()})
    assert sum(r['modules'] for r in rows) == 8
    T.record('selected-public-root-terminal.json', {'outcome': 'FOUR_SELECTED_PUBLIC_RELEASES_EXACT_ROOT_GREEN',
        'versions': rows, 'sourceFilesUnchanged': True, 'privateKeysCopied': False,
        'databaseWrites': 0, 'apiStarted': False, 'mixedImageQualification': False,
        'eightPagesAccepted': False, 'runtimeAuthority': False})
    print('FOUR_SELECTED_PUBLIC_RELEASES_EXACT_ROOT_GREEN')
