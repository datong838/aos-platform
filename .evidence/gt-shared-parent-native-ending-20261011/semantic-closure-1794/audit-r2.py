"""Read-only syntactic dependency candidates, never a runtime allowlist."""
import hashlib
import json
import subprocess
from pathlib import Path

import pglast
import psycopg
from pglast import parser
from psycopg.rows import dict_row

B = Path(__file__).resolve().parent
R = B.parents[2]
lab = json.loads((R / '.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
container = json.loads(subprocess.check_output(
    ['docker', '--context', lab['context'], 'inspect', lab['name']], text=True))[0]
assert container['Id'] == lab['container_id'] and container['Image'] == lab['image']
assert container['State']['Running']


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def names(items):
    return '.'.join(item['String']['sval'] for item in items)


with psycopg.connect(host='127.0.0.1', port=lab['port'], user='aos_app',
                     dbname='aos_test_2687abc41131_ti4_test', passfile=lab['passfile'],
                     row_factory=dict_row) as conn:
    conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
    assert conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == lab['cluster']
    server = conn.execute('SHOW server_version_num').fetchone()['server_version_num']
    rows = conn.execute("""SELECT p.oid, n.nspname AS schema, p.proname AS name,
        p.oid::regprocedure::text AS signature, l.lanname AS language,
        p.proowner::regrole::text AS owner, p.prosecdef, p.proconfig,
        p.proacl::text AS acl, p.provolatile, p.prosrc, p.probin,
        CASE WHEN l.lanname IN ('sql','plpgsql') THEN pg_get_functiondef(p.oid) END AS definition
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        JOIN pg_language l ON l.oid=p.prolang WHERE p.prokind='f'""").fetchall()
    conn.rollback()

by_name = {}
for row in rows:
    by_name.setdefault(row['name'], []).append(row)
queue = [r for r in rows if r['schema'] == 'public' and r['name'] == 'read_shared_parent_complete_end_facts']
assert len(queue) == 1
visited, output = set(), []
while queue:
    row = queue.pop(0)
    if row['oid'] in visited:
        continue
    visited.add(row['oid'])
    assert len(visited) < 1000
    record = {k: row[k] for k in ('oid', 'signature', 'language', 'owner', 'prosecdef', 'proconfig', 'acl', 'provolatile', 'probin')}
    record['body_sha256'] = hashlib.sha256((row['definition'] or row['prosrc']).encode()).hexdigest()
    queries, errors, dynamics = [], [], []
    if row['language'] == 'plpgsql':
        try:
            tree = pglast.parse_plpgsql(row['definition'])
            for node in walk(tree):
                if 'PLpgSQL_expr' in node:
                    expr = node['PLpgSQL_expr']
                    queries.append((expr['query'], expr.get('parseMode', 0)))
                dynamics.extend(k for k in node if k.startswith('PLpgSQL_stmt_dyn'))
        except Exception as error:
            errors.append({'phase': 'plpgsql', 'error': str(error)})
    elif row['language'] == 'sql':
        queries.append((row['prosrc'], 0))
    functions, operators, casts = set(), set(), set()
    for query, mode in queries:
        try:
            # PL/pgSQL mode 2 is a SQL expression. Other modes remain explicit gaps.
            if mode == 3:
                tokens = pglast.scan(query)
                if len(tokens) < 3 or tokens[0].name != 'IDENT' or tokens[1].name not in ('COLON_EQUALS', 'ASCII_61'):
                    raise ValueError('unsupported assignment target')
                query = query[tokens[1].end + 1:]
                mode = 2
            if mode not in (0, 2):
                raise ValueError('unsupported PL/pgSQL parse mode ' + str(mode))
            tree = json.loads(parser.parse_sql_json(('SELECT ' if mode == 2 else '') + query))
            for node in walk(tree):
                if 'FuncCall' in node:
                    functions.add(names(node['FuncCall']['funcname']))
                if 'A_Expr' in node:
                    operators.add(names(node['A_Expr'].get('name', [])))
                if 'TypeCast' in node:
                    casts.add(names(node['TypeCast']['typeName'].get('names', [])))
        except Exception as error:
            errors.append({'phase': 'sql', 'mode': mode, 'query_sha256': hashlib.sha256(query.encode()).hexdigest(), 'error': str(error)})
    edges = []
    for name in sorted(functions):
        parts = name.split('.')
        candidates = by_name.get(parts[-1], [])
        if len(parts) == 2:
            candidates = [r for r in candidates if r['schema'] == parts[0]]
        # Unqualified names deliberately retain all schemas; no search_path inference.
        edges.append({'call': name, 'candidates': [r['signature'] for r in candidates], 'overload_resolved': False})
        queue.extend(candidates)
    record.update(explicit_calls=edges, operators=sorted(operators), casts=sorted(casts),
                  parse_errors=errors, dynamic_statements=sorted(set(dynamics)),
                  native_body_uninspected=row['language'] not in ('sql', 'plpgsql'))
    output.append(record)

result = dict(server_version_num=server, parser_version=pglast.__version__,
              parser_pg_version=json.loads(parser.parse_sql_json('SELECT 1'))['version'],
              cluster=lab['cluster'], functions=output, function_count=len(output),
              parse_error_count=sum(len(r['parse_errors']) for r in output),
              dynamic_statement_count=sum(len(r['dynamic_statements']) for r in output),
              semantic_closure_proved=False, runtime_allowlist=False, execution_allowed=False,
              limitations=['PG parser major differs from server', 'All overloads are candidates only',
                           'Implicit casts/operator resolution/planner/native internals unproved',
                           'Catalog snapshot does not prove immutable lifecycle'])
(B / 'result-r2.json').open('x').write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k != 'functions'}))
