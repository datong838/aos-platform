"""Catalog-declared indirect edges, not proof of execution or closure."""
import hashlib
import json
import subprocess
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

B = Path(__file__).resolve().parent
R = B.parents[2]
prior = json.loads((B.parent / 'planner-source-1797/independent-readback.json').read_text())
lab = json.loads((R / '.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
c = json.loads(subprocess.check_output(['docker', '--context', lab['context'], 'inspect', lab['name']], text=True))[0]
assert c['Id'] == lab['container_id'] and c['Image'] == lab['image'] and c['State']['Running']
fields = ('aggtransfn', 'aggfinalfn', 'aggcombinefn', 'aggserialfn', 'aggdeserialfn',
          'aggmtransfn', 'aggminvtransfn', 'aggmfinalfn')
seeds = {r['oid']: r for r in prior['observed_functions']}
queue = list(seeds)
seen, functions, edges = set(), [], []
with psycopg.connect(host='127.0.0.1', port=lab['port'], user='aos_app',
                     dbname=prior['database'], passfile=lab['passfile'], row_factory=dict_row) as conn:
    conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
    assert conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == lab['cluster']
    while queue:
        oid = queue.pop(0)
        if oid in seen:
            continue
        seen.add(oid)
        assert len(seen) <= 1000
        row = conn.execute('''SELECT p.oid,p.oid::regprocedure::text AS signature,
            p.prosupport::oid AS support,p.prosrc,p.probin,l.lanname AS language,
            p.provolatile,p.proowner::regrole::text AS owner,p.prosecdef,p.proconfig
            FROM pg_proc p JOIN pg_language l ON l.oid=p.prolang WHERE p.oid=%s''', (oid,)).fetchone()
        assert row is not None
        row['source_sha256'] = hashlib.sha256(row.pop('prosrc').encode()).hexdigest()
        if oid in seeds:
            assert row['signature'] == seeds[oid]['signature']
            assert row['source_sha256'] == seeds[oid]['source_sha256']
        functions.append(row)
        outgoing = {'prosupport': row['support']}
        aggregate = conn.execute('SELECT * FROM pg_aggregate WHERE aggfnoid=%s', (oid,)).fetchone()
        if aggregate:
            # regproc output is a name; cast through regprocedure to obtain exact OID.
            for field in fields:
                target = conn.execute('SELECT ' + field + '::oid AS target FROM pg_aggregate WHERE aggfnoid=%s', (oid,)).fetchone()['target']
                outgoing[field] = target
            sort_oid = int(aggregate['aggsortop'])
            if sort_oid:
                outgoing['aggsortop.oprcode'] = conn.execute('SELECT oprcode::oid AS target FROM pg_operator WHERE oid=%s', (sort_oid,)).fetchone()['target']
        for kind, target in outgoing.items():
            if target:
                edges.append(dict(source=oid, target=target, kind=kind, execution_observed=False))
                queue.append(target)
    conn.rollback()
result = dict(cluster=lab['cluster'], database=prior['database'], original_seed_count=len(seeds),
              function_count=len(functions), added_count=len(seen - seeds.keys()),
              functions=functions, edges=edges, catalog_snapshot_only=True,
              full_runtime_closure=False, execution_allowed=False)
(B / 'result.json').open('x').write(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k not in ('functions', 'edges')}))
