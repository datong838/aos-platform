"""Native legacy-pool expiry counterexample, never business admission evidence."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
PASSFILE = Path(tempfile.gettempdir()) / 'aos-capacity-publication-scram-20261006.pgpass'
assert PASSFILE.stat().st_mode & 0o077 == 0
assert subprocess.check_output([
    'docker', '--context', 'colima-aos-a0v-test-only', 'inspect',
    'aos-capacity-publication-scram-20261006', '--format', '{{.Id}}'
], text=True).strip() == '4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
for name in ('PGPASSWORD', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS'):
    os.environ.pop(name, None)
os.environ['PGPASSFILE'] = str(PASSFILE)
os.environ['AOS_DOTENV_DISABLED'] = '1'
sys.path.insert(0, str(REPO / 'services/aos-api'))

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from aos_api.db import connect, connect_read_only
from aos_api.aip_model_capacity_reservation import AipModelCapacityReservationGate
from aos_api.aip_agent_registry_store import AipAgentRegistryTransitionBlocked
from aos_api.tenant_scope import TenantScope
from tests.aip.test_model_eval_shared_capacity_pg import _ref, SCOPE, HASH
from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_runtime_contracts import ModelRouteResolution, ModelRuntimeReadiness
from psycopg.types.json import Jsonb
from datetime import UTC, datetime

def seed_one_second_pool(suffix):
    route = _ref('ModelRouteRevision', 'test:ttl:route:' + suffix)
    model = _ref('RegisteredModelRevision', 'test:ttl:model:' + suffix)
    provider = _ref('ProviderInstanceRevision', 'test:ttl:provider')
    with psycopg.connect(os.environ['AOS_DATABASE_URL']) as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES ('org-org','test') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES ('org-org','dev-project','test') ON CONFLICT DO NOTHING")
    with connect(SCOPE) as conn:
        conn.execute('INSERT INTO aip_model_capacity_pool_head(org_id,project_id,pool_id,current_revision,version) VALUES (%s,%s,%s,1,1)', (*SCOPE.key, 'test:ttl:pool:' + suffix))
        conn.execute('''INSERT INTO aip_model_capacity_pool_revision
            (org_id,project_id,pool_id,revision,content_hash,route_ref,model_ref,provider_ref,
             route_id,route_revision,route_hash,model_id,model_revision,model_hash,
             provider_id,provider_revision,provider_hash,max_concurrency,max_token_units,
             token_unit_per_reservation,lease_seconds,lifecycle,created_by)
            VALUES (%s,%s,%s,1,%s,%s,%s,%s,%s,1,%s,%s,1,%s,%s,1,%s,1,100,10,1,'active','pytest')''',
            (*SCOPE.key, 'test:ttl:pool:' + suffix, HASH,
             Jsonb(route.model_dump(mode='json', by_alias=True)),
             Jsonb(model.model_dump(mode='json', by_alias=True)),
             Jsonb(provider.model_dump(mode='json', by_alias=True)),
             route.asset_id, route.content_hash, model.asset_id, model.content_hash,
             provider.asset_id, provider.content_hash))
        conn.commit()
    return ModelRouteResolution(tenant=TenantContext(orgId=SCOPE.org_id,projectId=SCOPE.project_id),
        route=route,policy=_ref('RuntimePolicyRevision','test:ttl:policy'),
        readiness=ModelRuntimeReadiness.READY, selectedModel=model,selectedProvider=provider,
        selectedPriceSnapshot=_ref('ModelPriceSnapshotRevision','test:ttl:price'),
        blockerCodes=[],resolvedAt=datetime.now(UTC))

templates = re.findall(r'Retained isolated test database: (aos_test_[a-z0-9_]+)',
    (REPO / '.evidence/gt-budget-caller-transaction-20261007/green-r1.log').read_text())
assert len(templates) == 1
template = templates[0]
root_dsn = 'postgresql://aos_app@127.0.0.1:5434/aos_meta'
template_dsn = f'postgresql://aos_app@127.0.0.1:5434/{template}'
with psycopg.connect(template_dsn, row_factory=dict_row) as conn:
    conn.execute('SET TRANSACTION READ ONLY')
    assert str(conn.execute('SELECT system_identifier FROM pg_control_system()').fetchone()['system_identifier']) == '7693564235776004128'
    template_heads = conn.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall()
    for table in ('aip_model_capacity_reservation', 'aip_model_capacity_event', 'aip_agent_run'):
        assert conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(table))).fetchone()['n'] == 0
database = 'aos_test_legacy_ttl_' + uuid.uuid4().hex[:12]
with psycopg.connect(root_dsn, autocommit=True) as conn:
    conn.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(sql.Identifier(database), sql.Identifier(template)))
print('Retained owned counterexample database:', database, flush=True)
os.environ['AOS_DATABASE_URL'] = f'postgresql://aos_app@127.0.0.1:5434/{database}'
gate = AipModelCapacityReservationGate()
observations = []
for initial in ('reserved', 'consumed'):
    resolution = seed_one_second_pool(initial)
    first = gate.reserve(SCOPE, resolution, 'test:ttl:first:' + initial)
    if initial == 'consumed':
        gate.consume(SCOPE, first)
    try:
        gate.reserve(SCOPE, resolution, 'test:ttl:second:' + initial)
    except AipAgentRegistryTransitionBlocked as exc:
        assert str(exc) == 'capacity_concurrency_exhausted'
    else:
        raise AssertionError('Second reservation was not fenced before natural expiry')
    deadline = time.monotonic() + 5
    while True:
        with connect_read_only(SCOPE) as conn:
            before = conn.execute('SELECT status,expires_at,clock_timestamp() AS observed_at,expires_at<=clock_timestamp() AS expired FROM aip_model_capacity_reservation WHERE org_id=%s AND project_id=%s AND reservation_id=%s',
                (*SCOPE.key, first)).fetchone()
        if before['expired']:
            break
        assert time.monotonic() < deadline, 'Native clock expiry timed out'
        time.sleep(0.02)
    assert before['status'] == initial
    second = gate.reserve(SCOPE, resolution, 'test:ttl:second:' + initial)
    with connect_read_only(SCOPE) as conn:
        rows = conn.execute('SELECT reservation_id,status,expires_at FROM aip_model_capacity_reservation WHERE org_id=%s AND project_id=%s AND reservation_id IN (%s,%s) ORDER BY reservation_id',
            (*SCOPE.key, first, second)).fetchall()
        events = conn.execute('SELECT reservation_id,event_type,occurred_at FROM aip_model_capacity_event WHERE org_id=%s AND project_id=%s AND reservation_id IN (%s,%s) ORDER BY occurred_at,event_id',
            (*SCOPE.key, first, second)).fetchall()
    statuses = {r['reservation_id']: r['status'] for r in rows}
    assert statuses == {first: 'expired', second: 'reserved'}
    observations.append(dict(initial=initial, before=before, rows=rows, events=events,
        expected_unknown_preservation='NOT_IMPLEMENTED_BY_LEGACY_POOL', actual_second_admitted=True))
with connect_read_only(TenantScope('dev-org', 'dev-project')) as conn:
    canary = conn.execute('SELECT count(*) AS n FROM aip_model_capacity_reservation').fetchone()['n']
assert canary == 0
sources = {}
for name in ('aip_model_capacity_reservation.py', 'aip_agent_run_service.py'):
    sources[name] = hashlib.sha256((REPO / 'services/aos-api/aos_api' / name).read_bytes()).hexdigest()
result = dict(database=database, template=template, template_heads=template_heads,
    cluster='7693564235776004128', head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    observations=observations, canary=canary, source_hashes=sources,
    classification='LEGACY_NATIVE_EXPIRY_COUNTEREXAMPLE_CONFIRMED',
    limitations=['Synthetic legacy pool only; no signed Source or legitimate AgentRun authority',
        'Unknown AgentRun auto-release is source-confirmed, not a native AgentRun PG reproduction',
        'No physical joint-ledger, business execution, or formal database changes'])
(BASE / 'legacy-ttl-r2.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + '\n')
print(result['classification'], 'cases=', len(observations), 'canary=', canary, flush=True)
