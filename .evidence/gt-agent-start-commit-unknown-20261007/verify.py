"""Exact AST normalization and retained native read-only database checks."""
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
baseline='60480bcc0813a9dadf2c7064b657aa8d4b0c44df'
filename='services/aos-api/aos_api/aip_agent_run_service.py'
old=subprocess.check_output(['git','show',baseline+':'+filename],text=True)
new=(repo/filename).read_text()
class NormalizeCommitWarning(ast.NodeTransformer):
    changed=0
    def visit_Call(self,node):
        self.generic_visit(node)
        if (ast.unparse(node.func)=='log.warning' and node.args
            and isinstance(node.args[0],ast.Constant)
            and node.args[0].value=='capacity_start_commit_outcome_unknown agent_run_id=%s reservation_id=%s'):
            assert [ast.unparse(arg) for arg in node.args[1:]]==['agent_run_id','reservation_id'] and not node.keywords
            self.changed+=1
            return ast.parse('self._capacity_gate.release(scope, reservation_id)').body[0].value
        return node
normalizer=NormalizeCommitWarning()
normalized=normalizer.visit(ast.parse(new))
assert normalizer.changed==1
assert ast.dump(normalized,include_attributes=False)==ast.dump(ast.parse(old),include_attributes=False)
passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode&0o077==0
for key in ('PGPASSWORD','PGOPTIONS','PGSERVICE','PGSERVICEFILE'):
    os.environ.pop(key,None)
os.environ['PGPASSFILE']=str(passfile)
logs={};databases={}
for name,summary in [('red-r1.log','2 failed, 13 passed'),('green-r1.log','66 passed')]:
    raw=(base/name).read_text()
    assert summary in raw and ' skipped' not in raw
    roots=re.findall(r'Retained isolated test database: (aos_test_[a-z0-9_]+)',raw)
    assert len(roots)==1
    database=roots[0]
    with psycopg.connect(f'postgresql://aos_app@127.0.0.1:5434/{database}',row_factory=dict_row) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert str(conn.execute('SELECT system_identifier FROM pg_control_system()').fetchone()['system_identifier'])=='7693564235776004128'
        counts={table:conn.execute('SELECT count(*) AS n FROM '+table).fetchone()['n']
            for table in ('aip_agent_run','aip_model_capacity_reservation')}
        assert set(counts.values())=={0}
        databases[database]=dict(counts=counts,heads=conn.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall())
    logs[name]=dict(sha256=hashlib.sha256(raw.encode()).hexdigest(),summary=summary)
result=dict(status='START_COMMIT_ERROR_PRESERVATION_UNIT_VERIFIED',baseline=baseline,
    production_sha256=hashlib.sha256(new.encode()).hexdigest(),logs=logs,retained_databases=databases,
    exact_change='Only commit-exception eager release replaced with static structured warning',
    limitations=['Fake connection/gate simulations, including post-commit response loss; no native PG fault injection',
        'Retained bootstrap PG only; lawful AgentRun creation chain not proven',
        'Legacy pool TTL can still expire reservations; physical joint ledger remains pending'])
(base/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],'66PASS; exact AST change only; retained PG zero AgentRun/capacity')
