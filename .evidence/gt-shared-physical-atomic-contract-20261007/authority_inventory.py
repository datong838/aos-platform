"""Read-only owned signed-Source history and exact writer source inventory."""
import ast
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

base = Path(__file__).resolve().parent
repo = base.parents[1]
passfile = Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode & 0o077 == 0
for key in ('PGPASSWORD','PGOPTIONS','PGSERVICE','PGSERVICEFILE'):
    os.environ.pop(key,None)
os.environ['PGPASSFILE'] = str(passfile)
log = repo/'.evidence/gt-capacity-source-publication-20261006/occupation-independent-owner-withdrawal-r4.log'
databases = re.findall(r'Retained isolated test database: (aos_test_[a-z0-9_]+)', log.read_text())
assert len(databases) == 3 and len(set(databases)) == 3
observations = {}
for database in databases:
    with psycopg.connect(f'postgresql://aos_app@127.0.0.1:5434/{database}',row_factory=dict_row) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        identity = conn.execute("SELECT current_database() AS database, current_setting('transaction_read_only') AS readonly,system_identifier::text AS cluster FROM pg_control_system()").fetchone()
        assert identity == dict(database=database,readonly='on',cluster='7693564235776004128')
        counts = {}
        for schema,table in [('public','aip_agent_run'),('public','aip_task'),
            ('public','aip_agent_registry_receipt'),('public','aip_model_capacity_reservation'),
            ('aos_capacity_publication_private','global_account'),
            ('aos_capacity_publication_private','global_provider'),
            ('aos_capacity_publication_private','source_publication')]:
            relation = schema+'.'+table
            exists = conn.execute('SELECT to_regclass(%s) AS relation',(relation,)).fetchone()['relation']
            counts[relation] = None if exists is None else conn.execute(sql.SQL('SELECT count(*) AS n FROM {}.{}').format(sql.Identifier(schema),sql.Identifier(table))).fetchone()['n']
        mapping = []
        if counts['aos_capacity_publication_private.global_account']:
            mapping = conn.execute('''SELECT a.account_id,a.org_id,a.project_id,count(p.provider_id) AS providers
                FROM aos_capacity_publication_private.global_account a
                LEFT JOIN aos_capacity_publication_private.global_provider p USING(account_id)
                GROUP BY a.account_id,a.org_id,a.project_id ORDER BY a.account_id''').fetchall()
        statuses = conn.execute('SELECT status,count(*) AS n FROM public.aip_agent_run GROUP BY status ORDER BY status').fetchall()
        observations[database] = dict(identity=identity,counts=counts,physical_mapping=mapping,agent_statuses=statuses,
            migration_heads=conn.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall())

writers = {}
for filename in ('aip_agent_run_service.py','aip_model_capacity_reservation.py',
    'aip_budget_reservation_store.py','aip_model_eval_budget_reservation.py',
    'ecommerce_content_agentrun_owner.py','ecommerce_content_capacity_owner.py',
    'ecommerce_content_budget_command_owner.py'):
    path = repo/'services/aos-api/aos_api'/filename
    source = path.read_text()
    items = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
            if node.func.attr in ('commit','reserve','release','release_for_run','reserve_in_transaction','hold_for_eval_in_transaction'):
                items.append(dict(line=node.lineno,call=ast.unparse(node.func)))
            elif node.func.attr == 'execute' and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str):
                query=node.args[0].value
                if any(token in query for token in ('FOR UPDATE','FOR SHARE','pg_advisory_xact_lock')):
                    items.append(dict(line=node.lineno,sql=' '.join(query.split())))
    writers[filename] = dict(sha256=hashlib.sha256(source.encode()).hexdigest(),calls=sorted(items,key=lambda x:x['line']))
result = dict(status='READ_ONLY_HISTORY_AND_SOURCE_INVENTORY',databases=observations,writers=writers,
    source_log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
    limitations=['No attempt replay; no Source/profile mutation',
        'Source existence alone does not prove current admission or complete account authority',
        'AST calls omit dynamic SQL/transitive calls; lock-order freeze still requires manual and native checks'])
(base/'authority-inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
for name,record in observations.items():
    print(name,'AgentRun=',record['counts']['public.aip_agent_run'],
        'Source=',record['counts']['aos_capacity_publication_private.source_publication'],
        'physical providers=',[row['providers'] for row in record['physical_mapping']])
