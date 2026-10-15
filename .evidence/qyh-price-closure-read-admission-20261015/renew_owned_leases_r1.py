from pathlib import Path
import json
import os
import sys
R=Path(__file__).resolve().parents[2];E=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'scripts/memory'));import memoryctl as m
p=m.DEFAULT_PATHS;assert m.load_authority(p)['project_revision']=='AOS-002035'
owner='codex-01a13484-f019-7d82-94ce-812396db9124'
ids=['qyh-restoration-readonly-continuation-r8-20261015',E.name]
before=m.load_leases(p)['leases'];rows={tid:next(r for r in before if r['task_id']==tid) for tid in ids}
assert all(row['owner']==owner and row['base_revision']=='AOS-002035' for row in rows.values())
with (E/'renewal-intent-r1.json').open('x') as stream:
    json.dump(dict(tasks=ids,before=rows,expiry='2026-10-15T08:00:00+00:00',originalGoalRetained=True),stream,indent=2);stream.flush();os.fsync(stream.fileno())
renewed=[]
for tid in ids:
    renewed.append(m.renew_task(p,task_id=tid,owner=owner,expected_revision='AOS-002035',expected_task=rows[tid],
        lease_expires_at='2026-10-15T08:00:00+00:00',reconciliation='Same owner accurate Delivery2035 and current readonly audit continuation, no overlapping writer; extend before04UTC for complete plan/Prime/code/native/live Loop, keep every original remaining requirement.'))
after=m.load_leases(p)['leases']
assert all(row in after for row in renewed)
assert [r for r in before if r['task_id'] not in ids]==[r for r in after if r['task_id'] not in ids]
with (E/'renewal-readback-r1.json').open('x') as stream:
    json.dump(dict(authority='AOS-002035',renewed=renewed,otherLeasesPreserved=38,nonOverlapping=True),stream,indent=2)
print(json.dumps(dict(renewed=ids,expiry='2026-10-15T08:00:00+00:00',otherLeasesPreserved=38)))
