from pathlib import Path
import datetime
import json
import os
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
sys.path.insert(0,str(R/'scripts/memory'));import memoryctl as m
p=m.DEFAULT_PATHS;owner='codex-01a13484-f019-7d82-94ce-812396db9124'
assert m.load_authority(p)['project_revision']=='AOS-002035'
before=m.load_leases(p)['leases'];parent=next(r for r in before if r['task_id']==E.name)
assert parent['owner']==owner and datetime.datetime.fromisoformat(parent['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
task='qyh-price-closure-bounded-reader-20261015'
assert not any(r['task_id']==task for r in before)
scope=['aos-platform/services/aos-api/aos_api/ecommerce_three_module_closure_readonly.py',
       'aos-platform/services/aos-api/tests/test_ecommerce_three_module_closure_readonly.py',
       'aos-platform/.evidence/'+task]
for row in before:assert not m.scopes_overlap(scope,row['scope'])
receipt=m.start_task(p,task_id=task,owner=owner,expected_revision='AOS-002035',scope=scope,
    excluded_scope=['aos-platform/apps/web','aos-platform/maintenance/qiyuehui-restored-data-volume'],
    expected_outputs=['Full231Goal and original authorization retained; only price closure saved view, no compiler/bind/consume/source/provider effects.',
        'Share original creator closure codec with fixed price entry and error prefix; preserve creator normal/default and customer legacy. Independent plan before RED/code, strict price raw/tenant/hash/ledger/exact bindings/privacy/time/SQL bounds.',
        'Original producer price nonempty five axes, creator regression, frozen cumulative/native originalDDL/realSDK and650/live independent gates; accurate slice Delivery only, whole Goal remains ACTIVE.'],
    lease_expires_at=parent['lease_expires_at'])
after=m.load_leases(p)['leases'];assert receipt in after and [r for r in after if r['task_id']!=task]==before
with (E/'reader-scope-readback-r1.json').open('x') as stream:
    json.dump(receipt,stream,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps(dict(task=task,scopeFiles=2,otherLeasesPreserved=len(before),productChanges=False)))
