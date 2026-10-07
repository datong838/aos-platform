"""Exact baseline AST comparison and independent retained-DB readback."""
import ast
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

base=Path(__file__).resolve().parent
repo=base.parents[1]
baseline='e5bc1999b4074f484efb9a0d70a931bf1a3856df'
filename='services/aos-api/aos_api/aip_agent_run_service.py'
old=subprocess.check_output(['git','show',baseline+':'+filename],text=True)
new=(repo/filename).read_text()
def methods(source):
    return {node.name:ast.dump(node,include_attributes=False) for node in ast.walk(ast.parse(source)) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
before=methods(old);after=methods(new)
assert before.keys()==after.keys()
assert [name for name in before if before[name]!=after[name]]==['transition']
old_test='to_status is not AgentRunStatus.RUNNING'
new_test='to_status not in {AgentRunStatus.RUNNING, AgentRunStatus.UNKNOWN}'
normalized=new.replace(new_test,old_test)
assert methods(normalized)==before, 'Unexpected executable AST change'
passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode&0o077==0
for key in ('PGPASSWORD','PGOPTIONS','PGSERVICE','PGSERVICEFILE'):
    os.environ.pop(key,None)
os.environ['PGPASSFILE']=str(passfile)
logs={}
databases={}
for name,summary in [('red-r1.log','1 failed, 13 passed'),('green-r1.log','65 passed')]:
    raw=(base/name).read_text()
    assert summary in raw and ' skipped' not in raw
    roots=re.findall(r'Retained isolated test database: (aos_test_[a-z0-9_]+)',raw)
    assert len(roots)==1
    database=roots[0]
    with psycopg.connect(f'postgresql://aos_app@127.0.0.1:5434/{database}',row_factory=dict_row) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert str(conn.execute('SELECT system_identifier FROM pg_control_system()').fetchone()['system_identifier'])=='7693564235776004128'
        heads=conn.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall()
        agent_runs=conn.execute('SELECT count(*) AS n FROM aip_agent_run').fetchone()['n']
        capacity=conn.execute('SELECT count(*) AS n FROM aip_model_capacity_reservation').fetchone()['n']
        assert agent_runs==0 and capacity==0
        databases[database]=dict(heads=heads,agent_runs=agent_runs,capacity=capacity)
    logs[name]=dict(sha256=hashlib.sha256(raw.encode()).hexdigest(),summary=summary)
result=dict(baseline=baseline,status='SCOPED_UNIT_FIX_VERIFIED',logs=logs,retained_databases=databases,
    production_sha256=hashlib.sha256(new.encode()).hexdigest(),
    executable_change='Only transition release branch excludes UNKNOWN',
    limitations=['Tests exercise actual service with fake connection/gate; no lawful AgentRun PG proof',
        'PG readback only confirms retained bootstrap databases untouched by these unit tests',
        'Legacy TTL and start COMMIT-unknown release remain pending; no joint physical ledger proof'])
(base/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],'65PASS; original methods identical except exact release condition; retained DB zero AgentRun/capacity')
