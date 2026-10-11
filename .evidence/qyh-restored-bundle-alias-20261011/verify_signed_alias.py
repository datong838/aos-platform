"""Read actual signed candidates through production-controlled alias wiring."""
import hashlib
import importlib.util
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

R = Path(__file__).resolve().parent
ROOT = R.parents[1]
FULL = ROOT / '.evidence/qyh-full-system-restoration-20261011'
sys.path.insert(0, str(FULL))
import release_transition as T
from aos_api.asset_registry import control_wiring

def tree(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}

if __name__ == '__main__':
    output = R / 'actual-signed-alias-readback.json'
    assert not output.exists(), 'Existing proof: reconcile rather than overwrite'
    source = T.CURRENT / 'signed-bundles'
    before = tree(source)
    os.environ['AOS_BUNDLE_ROOT'] = str(source)
    roots = control_wiring._allowlist_roots(repository_root=ROOT)
    assert roots['a0v-qyh-current'] == roots['server'] == source
    trust = T.FileTrustRootProvider(T.TRUST).snapshot()
    loader = T.ManifestLoader(roots, trust_roots=trust)
    rows = []
    for bundle_id, version in [('domain.ecommerce.core', '1.4.3'),
                               ('solution.ecommerce.growth', '1.13.0')]:
        bundle = loader.load(f'bundle://a0v-qyh-current/{bundle_id}/{version}')
        T.ReleasePolicy(trust_roots=trust).evaluate(
            T.OLD._load_builder()._release_record(bundle), checked_at=datetime.now(UTC))
        rows.append({'id': bundle_id, 'version': version,
                     'contentHash': bundle.content_hash,
                     'modules': len(bundle.workshop_modules),
                     'sourceRef': bundle.source_ref})
    assert tree(source) == before
    output.write_text(json.dumps({'outcome': 'PRODUCTION_ALIAS_ACTUAL_SIGNATURE_GREEN',
        'versions': rows, 'signedTreeUnchanged': True, 'databaseWrites': 0,
        'apiStarted': False, 'eightPagesAccepted': False,
        'runtimeAuthority': False}, ensure_ascii=False, indent=2) + '\n')
    print('PRODUCTION_ALIAS_ACTUAL_SIGNATURE_GREEN')
