"""Register exact extra reader scope using supported memory API, with readback."""
from pathlib import Path
import datetime
import json
import os
import subprocess
import sys
E=Path(__file__).resolve().parent;R=E.parents[1]
sys.path.insert(0,str(R/'scripts/memory'));import memoryctl as m
OWNER='codex-01a13484-f019-7d82-94ce-812396db9124'
TID='qyh-customer-lifecycle-bounded-reader-20261015'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()=='7385617635ab7331483ad6e891e8bf5e089839e5'
p=m.DEFAULT_PATHS;a=m.load_authority(p);assert a['project_revision']=='AOS-002036'
before=m.load_leases(p)['leases']
parent=next(x for x in before if x['task_id']==E.name)
assert parent['owner']==OWNER and datetime.datetime.fromisoformat(parent['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
assert not any(x['task_id']==TID for x in before),'Reconcile existing registration; never repeat.'
scope=['aos-platform/services/aos-api/aos_api/ecommerce_customer_lifecycle_readonly.py','aos-platform/services/aos-api/tests/test_ecommerce_customer_lifecycle_readonly.py','aos-platform/.evidence/'+TID]
for x in before:assert not m.scopes_overlap(scope,x['scope'])
row=m.start_task(p,task_id=TID,owner=OWNER,expected_revision='AOS-002036',scope=scope,excluded_scope=parent['excluded_scope'],
 expected_outputs=['Only saved customer contribution readonly snapshot reader and exact tests. Original typed producer hashes, complete saved-revision counts, strict tenant/time/privacy/bounds/failures and commands[]; no ProtectedContact/current consent authorization or effects.','Full231Goal, independent design/code Prime and frozen/native/genuine SDK/650/visual gates retained; no domain writer/Store/DDL/Web/AIP changes.'],lease_expires_at=parent['lease_expires_at'])
after=m.load_leases(p)['leases'];assert [x for x in after if x['task_id']!=TID]==before and row in after
for x in after:
 if x['task_id']!=TID:assert not m.scopes_overlap(row['scope'],x['scope'])
(R/'.evidence'/TID).mkdir(mode=0o700)
with (E/'reader-scope-readback-r1.json').open('x') as stream:
 json.dump(dict(authority='AOS-002036',reader=row,otherLeasesPreserved=len(before),nonOverlapping=True,wholeGoalComplete=False),stream,indent=2);stream.flush();os.fsync(stream.fileno())
print(json.dumps(dict(reader=TID,nonOverlapping=True,otherLeasesPreserved=len(before),productChanges=False)))
