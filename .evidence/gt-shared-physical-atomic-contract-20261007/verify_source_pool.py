"""Independent, read-only durable verification of the retained counterexample."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

base = Path(__file__).resolve().parent
repo = base.parents[1]
sys.path.insert(0, str(repo / 'services/aos-api'))
from aos_api.aip_provider_capacity_publication_contracts import (
    PublishedProviderCapacitySourceV2, parse_signed_capacity_body,
)

record = json.loads((base / 'source-pool-counterexample.json').read_text())
assert record['database'] == 'aos_test_b6bde5fde605_ti4_test'
assert subprocess.check_output([
    'docker', '--context', 'colima-aos-a0v-test-only', 'inspect',
    'aos-capacity-publication-scram-20261006', '--format', '{{.Id}}',
], text=True).strip() == '4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
passfile = Path(tempfile.gettempdir()) / 'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode & 0o077 == 0
for key in ('PGPASSWORD', 'PGPASSFILE', 'PGOPTIONS', 'PGSERVICE', 'PGSERVICEFILE'):
    os.environ.pop(key, None)

with psycopg.connect(
    host='127.0.0.1', port=5434, dbname=record['database'], user='aos_app',
    passfile=str(passfile), row_factory=dict_row,
) as conn:
    conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    identity = conn.execute("""SELECT current_database() AS database,
        current_setting('transaction_read_only') AS readonly,
        system_identifier::text AS cluster FROM pg_control_system()""").fetchone()
    assert identity == dict(database=record['database'], readonly='on', cluster=record['cluster'])
    sources = conn.execute("""SELECT s.source_raw,s.content_hash,s.account_id,
        aos_ed25519.verify(s.signature,s.source_raw,
            decode(p.original_signed_facts->>'sourceSignerPublicKey','base64')) AS signature_valid
        FROM aos_capacity_publication_private.source_publication s
        JOIN aos_capacity_publication_private.source_provenance p USING(org_id,project_id,asset_id)
        WHERE s.content_hash=%s""", (record['source_hash'],)).fetchall()
    assert len(sources) == 1
    signed = sources[0]
    raw = bytes(signed['source_raw'])
    assert signed['signature_valid'] is True
    assert hashlib.sha256(raw).hexdigest() == record['source_hash']
    source = parse_signed_capacity_body(raw, PublishedProviderCapacitySourceV2)
    assert str(source.physical_account_id) == str(signed['account_id']) == record['physical_account_id']
    assert source.max_concurrency == record['signed_concurrency_limit'] == 2
    assert source.execution_allowed is False and source.token_limit.mode == 'inflight_upper_bound'
    provider_ids = [p.asset_id for p in source.provider_refs]
    mapping = conn.execute("""SELECT provider_id,account_id FROM aos_capacity_publication_private.global_provider
        WHERE provider_id=ANY(%s) ORDER BY provider_id""", (provider_ids,)).fetchall()
    assert len(mapping) == len(provider_ids) == 3
    assert all(str(p['account_id']) == record['physical_account_id'] for p in mapping)
    ids = [r['reservation_id'] for r in record['rows']]
    rows = conn.execute("""SELECT reservation_id,pool_id,request_units,token_units,status
        FROM aip_model_capacity_reservation WHERE reservation_id=ANY(%s)
        ORDER BY reservation_id""", (ids,)).fetchall()
    assert rows == record['rows']
    assert len(rows) == 3 and sum(r['request_units'] for r in rows) == 3
    pools = conn.execute("""SELECT provider_id,max_concurrency FROM aip_model_capacity_pool_revision
        WHERE pool_id=ANY(%s) ORDER BY pool_id""", (list({r['pool_id'] for r in rows}),)).fetchall()
    assert len(pools) == 2 and len({p['provider_id'] for p in pools}) == 2
    assert all(p['provider_id'] in provider_ids and p['max_concurrency'] == 2 for p in pools)
    events = conn.execute('SELECT count(*) AS n FROM aip_model_capacity_event WHERE reservation_id=ANY(%s)', (ids,)).fetchone()['n']
    assert events == record['events'] == 3
    canary = conn.execute("SELECT count(*) AS n FROM aip_model_capacity_reservation WHERE org_id='dev-org'").fetchone()['n']
    runs = conn.execute('SELECT count(*) AS n FROM aip_agent_run').fetchone()['n']
    assert canary == runs == 0
    epoch = conn.execute('SELECT epoch,head_origin_hash FROM aos_capacity_publication_private.registry_epoch').fetchall()
    assert epoch == [dict(epoch=2, head_origin_hash=None)]
    role = conn.execute("""SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls
        FROM pg_roles WHERE rolname='aos_provider_capacity_occupation'""").fetchone()
    assert role is not None and not any(role.values())
    memberships = conn.execute("""SELECT count(*) AS n FROM pg_auth_members
        WHERE roleid='aos_provider_capacity_occupation'::regrole
        OR member='aos_provider_capacity_occupation'::regrole""").fetchone()['n']
    assert memberships == 0
    heads = conn.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall()

files = ['source_pool_probe.py', 'run_source_pool_probe.py', 'verify_source_pool.py',
         'source-pool-counterexample.json', 'source-pool-r3.log']
result = dict(
    status='DURABLE_COUNTEREXAMPLE_INDEPENDENTLY_VERIFIED', identity=identity,
    signature_valid=True, source_hash_valid=True, signed_limit=2, committed_request_units=3,
    provider_count=3, pool_count=2, events=events, canary=canary, agent_runs=runs,
    origin_withdrawn=True, occupation_role_restored=True, migration_heads=heads,
    head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    file_sha256={name:hashlib.sha256((base/name).read_bytes()).hexdigest() for name in files},
    limitations=record['limitations'] + [
        'Source is now withdrawn; signature history does not authorize admission or replay',
        'Precommit invisibility and caller xid/pid are original probe evidence, not independently reconstructed',
        'Only retained isolated database read; no formal database, service or business execution',
    ],
)
(base/'source-pool-independent-verification.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
print(result['status'], 'signature_valid limit=2 committed=3 canary=0 AgentRun=0 role_restored origin_withdrawn')
