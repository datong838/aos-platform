"""Native SHARE-to-UPDATE contention, test-only composition counterexample."""
import hashlib
import json
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

base=Path(__file__).resolve().parent
repo=base.parents[1]
prior=json.loads((base/'snapshot-lock-verification.json').read_text())
database=prior['database']
assert database=='aos_test_snapshot_lock_9314bde51c58'
assert subprocess.check_output(['docker','--context','colima-aos-a0v-test-only','inspect',
    'aos-capacity-publication-scram-20261006','--format','{{.Id}}'],text=True).strip()=='4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode&0o077==0
for key in ('PGPASSWORD','PGPASSFILE','PGOPTIONS','PGSERVICE','PGSERVICEFILE'):
    os.environ.pop(key,None)
def connect(**kwargs):
    return psycopg.connect(host='127.0.0.1',port=5434,dbname=database,user='aos_app',
        passfile=str(passfile),row_factory=dict_row,**kwargs)
case='share_to_update'
with connect() as c:
    assert str(c.execute('SELECT system_identifier FROM pg_control_system()').fetchone()['system_identifier'])==prior['cluster']
    c.execute("INSERT INTO gt_snapshot_probe.guard VALUES('org-org','dev-project',%s,0)",(case,))
def begin(c):
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ WRITE')
    c.execute('SET LOCAL ROLE aos_runtime')
    c.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
    c.execute("SET LOCAL lock_timeout='6s'")
    c.execute("SET LOCAL statement_timeout='8s'")
    c.execute('SELECT epoch FROM gt_snapshot_probe.guard WHERE case_id=%s FOR SHARE',(case,)).fetchone()
    return c.execute('SELECT pg_backend_pid() AS pid,pg_current_xact_id()::text AS xid').fetchone()
def upgrade(c):
    try:
        c.execute('UPDATE gt_snapshot_probe.guard SET epoch=epoch+1 WHERE case_id=%s',(case,))
        c.commit()
        return dict(status='committed')
    except psycopg.Error as e:
        c.rollback()
        return dict(status='rejected',sqlstate=e.sqlstate)
with connect() as first,connect() as second,connect(autocommit=True) as observer:
    first_id=begin(first);second_id=begin(second)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future=executor.submit(upgrade,first)
        deadline=time.monotonic()+3
        blockers=[]
        while second_id['pid'] not in blockers:
            blockers=observer.execute('SELECT pg_blocking_pids(%s) AS pids',(first_id['pid'],)).fetchone()['pids']
            assert not future.done() and time.monotonic()<deadline
            time.sleep(.01)
        second_result=upgrade(second)
        first_result=future.result(timeout=10)
    outcomes=[first_result,second_result]
    assert sum(x.get('sqlstate')=='40P01' for x in outcomes)==1
    assert sum(x['status']=='committed' for x in outcomes)==1
    final=observer.execute('SELECT epoch FROM gt_snapshot_probe.guard WHERE case_id=%s',(case,)).fetchone()['epoch']
    assert final==1
result=dict(status='NATIVE_SHARE_UPDATE_UPGRADE_CYCLE_CONFIRMED',database=database,
    first_caller=first_id,second_caller=second_id,first_blocked_by=blockers,
    first_result=first_result,second_result=second_result,final_epoch=final,
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    original_cost_runtime_sha256=hashlib.sha256((repo/'services/aos-api/aos_api/aip_budget_cost_runtime.py').read_bytes()).hexdigest(),
    limitations=['Native test-only row lock composition; not original complete budget execution',
        'No Source replay, Task, AgentRun, budget hold, Intent or Provider execution'])
(base/'upgrade-lock-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],outcomes,'final_epoch=',final)
