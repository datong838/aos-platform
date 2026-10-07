"""Read actual retained catalog lock surfaces; lexical inventory is not execution."""
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
DATABASES = ('aos_test_fc2688b199ad_ti4_test', 'aos_test_f2ef54f0da1d_ti4_test')
CLUSTER = '7693564235776004128'
PASSFILE = Path(tempfile.gettempdir()) / 'aos-capacity-publication-scram-20261006.pgpass'
assert PASSFILE.stat().st_mode & 0o077 == 0
assert subprocess.check_output(['docker', '--context', 'colima-aos-a0v-test-only', 'inspect',
    'aos-capacity-publication-scram-20261006', '--format', '{{.Id}}'], text=True).strip() == \
    '4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
for key in ('PGPASSWORD', 'PGPASSFILE', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS'):
    os.environ.pop(key, None)

# This deliberately bounded starting set does not claim every AOS writer.
PREFIXES = ('aip_budget_', 'aip_model_', 'aip_provider_', 'aip_action_', 'aip_capacity_')
SPECIAL = {'meta_membership', 'aip_capability_invocation', 'aip_registered_model_head',
    'aip_registered_model_revision'}
RELATION = re.compile(r'\b(?:FROM|JOIN|UPDATE|INTO)\s+(?:ONLY\s+)?'
    r'((?:[a-zA-Z_][a-zA-Z0-9_]*\.)?[a-zA-Z_][a-zA-Z0-9_]*)', re.I)
LOCK = re.compile(r'\bFOR\s+(?:NO\s+KEY\s+UPDATE|KEY\s+SHARE|UPDATE|SHARE)\b'
    r'|\b(?:pg_advisory_[a-z_]*|UPDATE|INSERT\s+INTO|DELETE\s+FROM|EXECUTE)\b', re.I)


def lexical_events(source):
    # Strip comments so comments do not manufacture dependency/lock claims.
    source = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
    source = re.sub(r'--[^\n]*', '', source)
    events = []
    for statement_no, statement in enumerate(source.split(';'), 1):
        matches = [m.group(0).upper() for m in LOCK.finditer(statement)]
        if not matches:
            continue
        relations = sorted(set(m.group(1) for m in RELATION.finditer(statement)))
        events.append(dict(lexical_statement=statement_no, operations=matches,
            relation_candidates=relations,
            dynamic_sql=bool(re.search(r'\bEXECUTE\b', statement, re.I))))
    return events


results = {}
for database in DATABASES:
    with psycopg.connect(host='127.0.0.1', port=5434, user='aos_app', dbname=database,
            passfile=str(PASSFILE), row_factory=dict_row) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        identity = conn.execute("SELECT current_database() AS database,"
            "current_setting('transaction_read_only') AS readonly,"
            "system_identifier::text AS cluster FROM pg_control_system()").fetchone()
        assert identity == dict(database=database, readonly='on', cluster=CLUSTER)
        heads = conn.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall()
        assert heads == [dict(version_num='a0v_157')]
        relations = conn.execute("""SELECT c.oid,n.nspname AS schema,c.relname AS name
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE c.relkind IN ('r','p') AND
            (n.nspname='public' OR n.nspname LIKE 'aos_capacity_%private')""").fetchall()
        by_name = {r['schema'] + '.' + r['name']: r for r in relations}
        roots = {name for name, r in by_name.items() if r['schema'] != 'public'
            or r['name'].startswith(PREFIXES) or r['name'] in SPECIAL}
        functions = conn.execute("""SELECT p.oid,n.nspname AS schema,p.proname AS name,
            pg_get_function_identity_arguments(p.oid) AS arguments,l.lanname AS language,
            p.prosrc AS source,p.prosecdef AS definer,p.proconfig AS config,
            p.proowner::regrole::text AS owner
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            JOIN pg_language l ON l.oid=p.prolang
            WHERE n.nspname='public' OR n.nspname LIKE 'aos_capacity_%private'""").fetchall()
        by_oid = {f['oid']: f for f in functions}
        triggers = conn.execute("""SELECT t.tgrelid,t.tgfoid,t.tgname,t.tgenabled,t.tgtype,
            t.tgdeferrable,t.tginitdeferred,t.tgisinternal,
            pg_get_triggerdef(t.oid,true) AS definition
            FROM pg_trigger t WHERE t.tgrelid=ANY(%s::oid[])""",
            ([r['oid'] for r in relations],)).fetchall()
        selected = set(roots)
        reached_functions = set()
        # Static SQL relation traversal only. A helper-function call is separately unresolved.
        while True:
            old = (len(selected), len(reached_functions))
            ids = {by_name[name]['oid'] for name in selected}
            for trigger in triggers:
                if trigger['tgrelid'] not in ids:
                    continue
                if trigger['tgfoid'] not in by_oid:
                    continue  # pg_catalog RI triggers are reported as external functions below.
                reached_functions.add(trigger['tgfoid'])
                for match in RELATION.finditer(by_oid[trigger['tgfoid']]['source']):
                    name = match.group(1)
                    name = name if '.' in name else 'public.' + name
                    if name in by_name:
                        selected.add(name)
            if old == (len(selected), len(reached_functions)):
                break
        # Include actual private entry/helper bodies; public reader may have been cleaned by fixture.
        reached_functions.update(f['oid'] for f in functions if f['schema'] != 'public')
        entries = []
        for oid in sorted(reached_functions):
            f = by_oid[oid]
            entries.append(dict(identity=f['schema']+'.'+f['name']+'('+f['arguments']+')',
                source_sha256=hashlib.sha256(f['source'].encode()).hexdigest(),
                language=f['language'], definer=f['definer'], owner=f['owner'], config=f['config'],
                lexical_lock_events=lexical_events(f['source']),
                dynamic_sql=bool(re.search(r'\bEXECUTE\b', f['source'], re.I))))
        selected_ids = {by_name[name]['oid'] for name in selected}
        selected_triggers = []
        oid_to_name = {r['oid']: name for name, r in by_name.items()}
        for t in triggers:
            if t['tgrelid'] not in selected_ids:
                continue
            f = by_oid.get(t['tgfoid'])
            selected_triggers.append(dict(table=oid_to_name[t['tgrelid']], name=t['tgname'],
                enabled=t['tgenabled'], before=bool(t['tgtype'] & 2), row=bool(t['tgtype'] & 1),
                insert=bool(t['tgtype'] & 4), delete=bool(t['tgtype'] & 8), update=bool(t['tgtype'] & 16),
                deferrable=t['tgdeferrable'], initially_deferred=t['tginitdeferred'],
                internal=t['tgisinternal'], function=f['schema']+'.'+f['name'] if f else 'outside_bounded_function_catalog',
                definition_sha256=hashlib.sha256(t['definition'].encode()).hexdigest()))
        product_counts = {table: conn.execute('SELECT count(*) AS n FROM '+table).fetchone()['n']
            for table in ('aip_agent_run','aip_model_capacity_reservation','aip_budget_reservation',
                'aip_model_eval_budget_reservation')}
        assert all(count == 0 for count in product_counts.values())
        results[database] = dict(identity=identity, migration_heads=heads, roots=sorted(roots),
            static_relation_closure=sorted(selected), triggers=selected_triggers, functions=entries,
            original_occupation_reader_present=any(f['name']=='read_capacity_source_for_occupation' for f in functions),
            product_counts=product_counts)

paths = ['services/aos-api/aos_api/aip_budget_reservation_store.py',
    'services/aos-api/aos_api/aip_model_eval_budget_reservation.py',
    'services/aos-api/aos_api/aip_budget_cost_runtime.py',
    'services/aos-api/aos_api/aip_budget_cost_issuer.py',
    'services/aos-api/aos_api/aip_budget_cost_consumer.sql',
    'services/aos-api/aos_api/aip_provider_capacity_occupation_source.py']
result = dict(status='BOUNDED_NATIVE_TRIGGER_LOCK_SURFACE_INVENTORIED', databases=results,
    head=subprocess.check_output(['git','rev-parse','HEAD'], cwd=REPO, text=True).strip(),
    source_sha256={p: hashlib.sha256((REPO/p).read_bytes()).hexdigest() for p in paths},
    probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    limitations=['Lexical statement order is not path or runtime lock order',
        'Static relation closure omits dynamic SQL and helper-function call closure',
        'Actual catalog hashes are observations, not trusted expected definitions or authorization',
        'Not complete writer graph, joint budget/physical/Intent implementation, or business first chain'])
(BASE/'catalog-lock-inventory.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'], {db:dict(tables=len(v['static_relation_closure']),triggers=len(v['triggers']),
    functions=len(v['functions'])) for db,v in results.items()})
