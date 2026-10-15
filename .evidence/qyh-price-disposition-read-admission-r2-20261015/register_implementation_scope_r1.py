"""Register the exact additional implementation scope using supported memoryctl."""
from pathlib import Path
import datetime
import json
import os
import sys
R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R/'scripts/memory'))
import memoryctl as m
p = m.DEFAULT_PATHS
owner = 'codex-01a13484-f019-7d82-94ce-812396db9124'
parent = 'qyh-price-disposition-read-admission-r2-20261015'
task = 'qyh-price-disposition-bounded-reader-20261015'
assert m.load_authority(p)['project_revision'] == 'AOS-002034'
leases = m.load_leases(p)['leases']
current = [r for r in leases if r['task_id'] == parent]
assert len(current) == 1 and current[0]['owner'] == owner
assert datetime.datetime.fromisoformat(current[0]['lease_expires_at']) > datetime.datetime.now(datetime.timezone.utc)
assert not any(r['task_id'] == task for r in leases)
scope = ['aos-platform/'+s for s in [
    'services/aos-api/aos_api/ecommerce_price_disposition_readonly.py',
    'services/aos-api/tests/aip/test_ecommerce_price_disposition_readonly.py',
    'services/aos-api/aos_api/ecommerce_workshop_price_disposition.py',
    'services/aos-api/tests/aip/test_w6_06_price_disposition.py',
    '.evidence/'+task]]
for row in leases:
    assert not m.scopes_overlap(scope, row['scope'])
result = m.start_task(p, task_id=task, owner=owner, expected_revision='AOS-002034',
    scope=scope, excluded_scope=['aos-platform/apps/web', 'aos-platform/maintenance/qiyuehui-restored-data-volume'],
    expected_outputs=[
        'Exact additional files for carried disposition GET read; full231Goal/user authorization/daily original-volume fullPGAPIWeb preserved, no operating authorization.',
        'Plan Prime before product code; single snapshot complete bounded counts, original producer typed binding/full frozen hash/observation ancestry and privacy/tenant/time/SQL payload guard.',
        'Pure rules extracted only from original service with unchanged writer behavior; RED/native isolated original DDL PG/frozen regression and independent quality; no original business writes/source/Provider/unknown replay.',
        'Carry precise implementation quality evidence back to parent route/live scope; accurate Delivery only, not whole business or visual completion.'],
    lease_expires_at=current[0]['lease_expires_at'])
after = m.load_leases(p)['leases']
assert result in after and [r for r in after if r['task_id'] != task] == leases
target = Path(__file__).with_name('implementation-scope-readback-r1.json')
with target.open('x') as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2); stream.flush(); os.fsync(stream.fileno())
print(json.dumps({'task': task, 'scopeFiles': 4, 'priorLeasesPreserved': len(leases), 'productChanges': False}))
