"""Read-only actual writer AST candidates; never infer a runtime lock order."""
import hashlib
import json
import os
import subprocess
import tempfile
from collections import deque
from pathlib import Path

import psycopg
import pglast
from psycopg.rows import dict_row
from source_lock_closure_probe import describe

BASE = Path(__file__).resolve().parent
# Independent grammar control reproduces the same serializer defect without
# any database, NEW row material, business payload or trigger execution.
parser_controls = {}
for returns, body in [('void', 'BEGIN RETURN; END'), ('trigger', 'BEGIN RETURN NEW; END')]:
    try:
        pglast.parse_plpgsql('CREATE FUNCTION public.control() RETURNS '+returns+
            ' LANGUAGE plpgsql AS $$'+body+'$$')
        parser_controls[returns] = 'PARSED'
    except json.JSONDecodeError:
        parser_controls[returns] = 'JSON_SERIALIZATION_FAILED'
assert pglast.__version__ in ('v8.4', 'v7.18')
expected_trigger = 'JSON_SERIALIZATION_FAILED' if pglast.__version__ == 'v8.4' else 'PARSED'
assert parser_controls == {'void': 'PARSED', 'trigger': expected_trigger}
reader = json.loads((BASE / 'source-lock-closure.json').read_text())
inventory = json.loads((BASE / 'catalog-lock-inventory.json').read_text())
prior = inventory['databases']['aos_test_fc2688b199ad_ti4_test']
names = {f['identity'].split('(')[0] for f in prior['functions']}
passfile = Path(tempfile.gettempdir()) / 'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode & 0o077 == 0
for key in ('PGPASSWORD', 'PGPASSFILE', 'PGOPTIONS', 'PGSERVICE', 'PGSERVICEFILE'):
    os.environ.pop(key, None)
with psycopg.connect(host='127.0.0.1', port=5434, user='aos_app',
        dbname=reader['identity']['database'], passfile=str(passfile), row_factory=dict_row) as conn:
    conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    identity = conn.execute("SELECT current_database() AS database,"
        "current_setting('transaction_read_only') AS readonly,"
        "system_identifier::text AS cluster FROM pg_control_system()").fetchone()
    assert identity == reader['identity']
    rows = conn.execute("""SELECT n.nspname||'.'||p.proname AS name,
        n.nspname||'.'||p.proname||'('||pg_get_function_identity_arguments(p.oid)||')' AS identity,
        p.prosrc AS body,pg_get_functiondef(p.oid) AS definition,l.lanname AS language
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        JOIN pg_language l ON l.oid=p.prolang
        WHERE p.prokind='f' AND (n.nspname='public' OR n.nspname='aos_ed25519'
            OR n.nspname LIKE 'aos_capacity_%private')""").fetchall()
    triggers = conn.execute("""SELECT ns.nspname||'.'||c.relname AS relation,
        t.tgname AS trigger,t.tgisinternal AS internal,t.tgtype AS timing_bits,
        t.tgenabled AS enabled,t.tgdeferrable AS deferrable,
        pn.nspname||'.'||p.proname AS function
        FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace ns ON ns.oid=c.relnamespace
        JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace pn ON pn.oid=p.pronamespace
        WHERE ns.nspname||'.'||c.relname=ANY(%s)
        ORDER BY ns.nspname,c.relname,t.tgname""", (prior['static_relation_closure'],)).fetchall()
    counts = {table: conn.execute('SELECT count(*) AS n FROM '+table).fetchone()['n']
        for table in ('aip_agent_run', 'aip_model_capacity_reservation',
            'aip_budget_reservation', 'aip_model_eval_budget_reservation')}
    assert not any(counts.values())
by_name = {}
for row in rows:
    by_name.setdefault(row['name'], []).append(row)
functions = []; pending = deque(sorted(names)); seen = set(); unresolved = set(); builtins = set(); overloads = {}
while pending:
    name = pending.popleft()
    if name in seen:
        continue
    seen.add(name)
    if name.startswith('pg_catalog.'):
        builtins.add(name)
        continue
    matches = by_name.get(name, [])
    if not matches:
        unresolved.add(name)
        continue
    if len(matches) > 1:
        overloads[name] = len(matches)
    for function in matches:
        try:
            described = describe(function)
        except json.JSONDecodeError:
            # Preserve serializer failure as missing coverage, never empty PASS.
            described = dict(identity=function['identity'], language=function['language'],
                body_sha256=hashlib.sha256(function['body'].encode()).hexdigest(),
                expressions=[], dynamic_statements=[], parse_failures=[dict(
                    stage='pglast_PLpgSQL_JSON', error_type='JSONDecodeError')])
        functions.append(described)
        for expression in described['expressions']:
            pending.extend(expression['calls'])
        for dynamic in described['dynamic_statements']:
            for summary in dynamic['template_summaries']:
                pending.extend(summary['calls'])
read_relations = {r for f in reader['functions'] for e in f['expressions'] for r in e['relations']}
candidates = []
for f in functions:
    name = f['identity'].split('(')[0]
    dml = [e for e in f['expressions'] if set(e['operations']) &
        {'InsertStmt', 'UpdateStmt', 'DeleteStmt', 'MergeStmt'}]
    attached = [t for t in triggers if t['function'] == name and t['relation'] in read_relations]
    shared = sorted({r for e in dml for r in e['relations']} & read_relations)
    if shared or attached:
        candidates.append(dict(identity=f['identity'], dml_relation_candidates=shared,
            source_relation_triggers=attached, dml_control_flow_paths=[e['control_flow_path'] for e in dml]))
result = dict(status='ACTUAL_WRITER_AST_CANDIDATES_NOT_RUNTIME_ORDER', identity=identity,
    parser_version=pglast.__version__,
    original_catalog_root_names=sorted(names), unresolved_explicit_calls=sorted(unresolved),
    native_builtin_calls=sorted(builtins), conservative_overloads=overloads,
    head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    functions=functions, triggers=triggers, candidates=candidates, product_counts=counts,
    parse_failures=sum(len(f['parse_failures']) for f in functions),
    dynamic_statements=sum(len(f['dynamic_statements']) for f in functions),
    dynamic_coverage_unknown_functions=sum(bool(f['parse_failures']) for f in functions),
    synthetic_parser_controls=parser_controls,
    probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    limitations=['DML relation candidates include joined read relations, not exact write targets',
        'Catalog and AST are possible paths, not an executed total lock order',
        'Trigger serializer failures leave their dynamic SQL and helper closure unknown',
        'Opaque helpers, implicit FK/unique locks and original opposite-writer concurrency remain pending'])
(BASE / 'writer-lock-candidates.json').write_text(json.dumps(result, indent=2)+'\n')
print('Writer AST:', len(functions), 'functions;', len(candidates), 'candidate intersections;',
    result['parse_failures'], 'parse failures;', result['dynamic_statements'], 'dynamic statements; product counts0')
