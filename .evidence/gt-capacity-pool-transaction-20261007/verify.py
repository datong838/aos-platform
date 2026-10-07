"""Compare extracted algorithm and retained caller-owned PG transactions."""
import ast
import copy
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

BASE = 'd032a63996beab59b29bb0e125ef5d2696f57282'
MODULE = 'services/aos-api/aos_api/aip_model_capacity_reservation.py'
TEST = 'services/aos-api/tests/aip/test_capacity_pool_transaction_pg.py'
old = ast.parse(subprocess.check_output(['git', 'show', BASE + ':' + MODULE], text=True))
new = ast.parse(Path(MODULE).read_text())
def methods(tree):
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    return {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
before, after = methods(old), methods(new)
for name in before.keys() - {'reserve'}:
    assert ast.dump(before[name]) == ast.dump(after[name]), name
assert [ast.dump(n) for n in before['reserve'].body[:2]] == [ast.dump(n) for n in after['reserve'].body[:2]]
body = copy.deepcopy(before['reserve'].body[-1].body)
assert isinstance(body[-2], ast.Expr) and body[-2].value.func.attr == 'commit'
body.pop(-2)
class OriginalCore(ast.NodeTransformer):
    def visit_Return(self, node):
        assert isinstance(node.value, ast.Subscript)
        assert node.value.value.id in ('replay', 'row')
        node.value = ast.Tuple(elts=[node.value, ast.Constant(node.value.value.id == 'row')], ctx=ast.Load())
        return node
class NormalizeSQL(ast.NodeTransformer):
    def visit_Constant(self, node):
        if isinstance(node.value, str) and '\n' in node.value:
            node.value = ' '.join(node.value.split())
        return node
expected = ast.Module(body=body, type_ignores=[])
expected = NormalizeSQL().visit(OriginalCore().visit(expected))
actual = NormalizeSQL().visit(ast.Module(body=copy.deepcopy(after['_reserve_pool'].body), type_ignores=[]))
assert ast.dump(expected) == ast.dump(actual), 'original pool algorithm changed beyond transaction ownership'
for name in ('_reserve_pool', 'reserve_pool_in_transaction'):
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr in ('commit', 'rollback', 'close') for n in ast.walk(after[name]))

logdir = Path('.evidence/gt-capacity-source-publication-20261006')
logs = {}
for name, result in (
    ('pool-caller-transaction-red-r1.log', '10 failed'),
    ('pool-caller-transaction-green-r1.log', '24 passed, 2 xfailed'),
    ('pool-caller-transaction-adjacent-r1.log', '65 passed, 2 xfailed'),
):
    path = logdir / name
    raw = path.read_text()
    assert result in raw and ' skipped' not in raw
    databases = set(re.findall(r'Retained isolated test database: (aos_test_[0-9a-f]+_ti4_test)', raw))
    assert len(databases) == 1
    assert not re.search(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', raw)
    logs[name] = {'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'result':result, 'database':databases.pop()}
passfile = Path(tempfile.gettempdir()) / 'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode & 0o077 == 0
password = passfile.read_text().strip().split(':')[-1]
assert all(password not in (logdir / name).read_text() for name in logs)
assert subprocess.check_output(['docker','--context','colima-aos-a0v-test-only','inspect',
    'aos-capacity-publication-scram-20261006','--format','{{.Id}}'],text=True).strip() == '4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
native = []
for name, log in logs.items():
    with psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',password=password,
                         dbname=log['database'],row_factory=dict_row) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        identity = conn.execute("SELECT current_database() AS database,(SELECT system_identifier::text FROM pg_control_system()) AS cluster").fetchone()
        assert identity == {'database':log['database'],'cluster':'7693564235776004128'}
        rows = conn.execute("""SELECT pool_id,agent_run_id,status FROM aip_model_capacity_reservation
            WHERE pool_id LIKE 'pool-txn:%' ORDER BY pool_id""").fetchall()
        count = conn.execute("""SELECT count(*) AS n FROM aip_model_capacity_event e
            JOIN aip_model_capacity_reservation r USING(org_id,project_id,reservation_id)
            WHERE r.pool_id LIKE 'pool-txn:%'""").fetchone()['n']
        expected_count = 0 if 'red' in name else 2 if 'adjacent' in name else 1
        assert len(rows) == count == expected_count, (name, rows, count)
        assert all(r['status'] == 'reserved' for r in rows)
        canary = conn.execute("""SELECT
            (SELECT count(*) FROM aip_model_capacity_reservation WHERE org_id='dev-org') AS reservations,
            (SELECT count(*) FROM aip_model_capacity_event WHERE org_id='dev-org') AS events""").fetchone()
        assert canary == {'reservations':0,'events':0}
        source_count = conn.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.source_publication').fetchone()['n']
        assert source_count == 0
        native.append({'log':name,'identity':identity,'pool_reservations':rows,'pool_events':count,
                       'canary':canary,'signed_sources':source_count})
        conn.rollback()
report = {'schema':'aos-capacity-pool-transaction-verification/v1','base_head':BASE,
    'file_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (MODULE,TEST)},
    'original_pool_algorithm_preserved':True,'other_original_methods_ast_unchanged':True,
    'new_entry_ends_no_transaction':True,'logs':logs,'native_readonly':native,
    'actual_tests':'caller rollback/commit/exception, same native xid, uncommitted observer invisibility, lock timeout/release, replay before and after callerCOMMIT,10 connection negatives',
    'limits':['Pool transaction kernel only; no Source/physical capacity/Intent authority.',
        'Fixture READY/pools are negative/transaction fixtures, not legitimate business positives.',
        'Source role profile/sharedoccupation/budget+Intent/cutover/unknown and COMMITTTL still pending.'],
    'formal_resources_touched':False,'full_goal_complete':False}
Path('.evidence/gt-capacity-pool-transaction-20261007/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'original_algorithm_preserved':True,'retained_databases':len(native),
                  'durable_new_pool_reservations':sum(len(r['pool_reservations']) for r in native)}))
