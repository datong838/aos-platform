"""Independent retained-catalog and cross-parser evidence verification."""
import hashlib
import json
import os
import tempfile
from pathlib import Path

import pglast
import psycopg
from psycopg.rows import dict_row

BASE = Path(__file__).resolve().parent
assert pglast.__version__ == 'v7.18'
assert BASE / '.parser-v7' in Path(pglast.__file__).resolve().parents
record = json.loads((BASE / 'writer-lock-candidates.json').read_text())
old = json.loads((BASE / 'writer-lock-candidates-r1.json').read_text())
source = json.loads((BASE / 'source-lock-closure.json').read_text())
assert old['parse_failures'] == 39 and old['dynamic_coverage_unknown_functions'] == 39
assert record['parser_version'] == 'v7.18' and len(record['functions']) == 101
assert record['parse_failures'] == 0 and record['unresolved_explicit_calls'] == []
assert record['dynamic_statements'] == record['dynamic_coverage_unknown_functions'] == 0
assert record['conservative_overloads'] == {'public.digest': 2}
assert record['synthetic_parser_controls'] == {'void': 'PARSED', 'trigger': 'PARSED'}
by_id = {f['identity']: f for f in record['functions']}
assert len(by_id) == 101
pairs = [(f, by_id[f['identity']]) for f in source['functions']
    if f['identity'] in by_id and f['body_sha256'] == by_id[f['identity']]['body_sha256']]
assert len(pairs) == 54
def operations(function):
    return [{k: v for k, v in e.items() if k != 'control_flow_path'}
        for e in function['expressions']]
assert all(operations(a) == operations(b) for a, b in pairs)
path_differences = sum(a['expressions'] != b['expressions'] for a, b in pairs)
assert path_differences == 16
assert record['probe_sha256'] == hashlib.sha256((BASE / 'writer_lock_candidates.py').read_bytes()).hexdigest()
passfile = Path(tempfile.gettempdir()) / 'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode & 0o077 == 0
for key in ('PGPASSWORD', 'PGPASSFILE', 'PGOPTIONS', 'PGSERVICE', 'PGSERVICEFILE'):
    os.environ.pop(key, None)
with psycopg.connect(host='127.0.0.1', port=5434, user='aos_app',
        dbname=source['identity']['database'], passfile=str(passfile), row_factory=dict_row) as conn:
    conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    identity = conn.execute("SELECT current_database() AS database,"
        "current_setting('transaction_read_only') AS readonly,"
        "system_identifier::text AS cluster FROM pg_control_system()").fetchone()
    assert identity == source['identity'] == record['identity'] == old['identity']
    rows = conn.execute("""SELECT n.nspname||'.'||p.proname||'('
        ||pg_get_function_identity_arguments(p.oid)||')' AS identity,p.prosrc AS body
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE p.prokind='f' AND (n.nspname='public' OR n.nspname='aos_ed25519'
            OR n.nspname LIKE 'aos_capacity_%private')""").fetchall()
    live = {f['identity']: hashlib.sha256(f['body'].encode()).hexdigest() for f in rows}
    assert all(live.get(f['identity']) == f['body_sha256'] for f in record['functions'])
    relations = sorted({t['relation'] for t in record['triggers']})
    triggers = conn.execute("""SELECT ns.nspname||'.'||c.relname AS relation,
        t.tgname AS trigger,t.tgisinternal AS internal,t.tgtype AS timing_bits,
        t.tgenabled AS enabled,t.tgdeferrable AS deferrable,
        pn.nspname||'.'||p.proname AS function
        FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace ns ON ns.oid=c.relnamespace
        JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace pn ON pn.oid=p.pronamespace
        WHERE ns.nspname||'.'||c.relname=ANY(%s)
        ORDER BY ns.nspname,c.relname,t.tgname""", (relations,)).fetchall()
    assert triggers == record['triggers']
    counts = {t: conn.execute('SELECT count(*) AS n FROM '+t).fetchone()['n']
        for t in record['product_counts']}
    assert counts == record['product_counts'] and not any(counts.values())
result = dict(status='WRITER_AST_CATALOG_AND_CROSS_PARSER_VERIFIED_RUNTIME_ORDER_PENDING',
    identity=identity, actual_function_bodies=101, actual_triggers=len(triggers),
    source_unchanged_operation_sequences=54, parser_control_flow_path_differences=path_differences,
    parser_version=pglast.__version__, parser_binary_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in Path(pglast.__file__).parent.glob('*.so')}, product_counts=counts,
    file_sha256={n: hashlib.sha256((BASE / n).read_bytes()).hexdigest() for n in
        ('writer_lock_candidates.py', 'writer-lock-candidates.json', 'writer-lock-candidates-r1.json',
            'verify_writer_lock_candidates.py')},
    limitations=['Identical operation sequences omit version-specific control-flow wrapper paths',
        'Opaque C functions and conservative overloads remain separate',
        'AST and trigger attachments do not prove a total runtime lock order or joint ledger authority'])
(BASE / 'writer-lock-independent-verification.json').write_text(json.dumps(result, indent=2)+'\n')
print(result['status'], '101 actual bodies; 54 unchanged operation sequences; product counts0')
