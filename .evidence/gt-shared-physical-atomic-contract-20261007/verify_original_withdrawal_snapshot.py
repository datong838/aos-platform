"""Independent retained writer-first result and original Source prefix definitions."""
import ast
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
sys.path.insert(0, str(REPO / 'services/aos-api'))
from aos_api.aip_provider_capacity_publication_transaction import CAPACITY_ORIGINAL_SOURCE_FACTS_SQL
from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySourceV2, parse_signed_capacity_body

record = json.loads((BASE / 'original-withdrawal-snapshot-verification.json').read_text())
attempt = json.loads((BASE / 'original-withdrawal-snapshot-attempt.json').read_text())
assert all(record[k] == v for k, v in attempt.items())
assert record['verdict'] == 'ORIGINAL_API_WRITER_FIRST_STALE_40001_FRESH_SOURCE_PREFIX_REJECTED'
assert record['reader_blockers'] == [record['api_pid']]
assert record['old_snapshot_sqlstate'] == '40001' and record['fresh_snapshot_sqlstate'] == 'P0002'
assert record['reader']['session'] == 'aos_provider_capacity_issuer' and record['reader']['isolation'] == 'serializable'
assert record['identity']['database'] == 'aos_test_bf39f06c471f_ti4_test'
assert record['probe_sha256'] == hashlib.sha256((BASE / 'original_withdrawal_snapshot_probe.py').read_bytes()).hexdigest()
migration = REPO / 'services/aos-api/alembic/versions/a0v_151_capacity_withdrawal_epoch.py'
tree = ast.parse(migration.read_text())
bump = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
    and any(isinstance(t, ast.Name) and t.id == 'BUMP_BODY' for t in n.targets))
prefix = re.findall(r'CREATE FUNCTION aos_capacity_publication_private.read_original_source_facts\([^)]*\).*?'
    r'AS \$body\$(.*?)\$body\$;', CAPACITY_ORIGINAL_SOURCE_FACTS_SQL, re.S)
assert len(prefix) == 1
passfile = Path(tempfile.gettempdir()) / 'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode & 0o077 == 0
for key in ('PGPASSWORD', 'PGPASSFILE', 'PGOPTIONS', 'PGSERVICE', 'PGSERVICEFILE'):
    os.environ.pop(key, None)
with psycopg.connect(host='127.0.0.1', port=5434, user='aos_app',
        dbname=record['identity']['database'], passfile=str(passfile), row_factory=dict_row) as conn:
    conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    identity = conn.execute("SELECT current_database() AS database,"
        "current_setting('transaction_read_only') AS readonly,"
        "system_identifier::text AS cluster FROM pg_control_system()").fetchone()
    assert identity == dict(**record['identity'], readonly='on')
    rows = conn.execute("SELECT p.proposal_id,p.status,p.version,p.created_by,e.epoch FROM aip_action_proposal p "
        "JOIN aip_capacity_withdrawal_epoch e USING(org_id,project_id,proposal_id) WHERE p.proposal_id=ANY(%s)",
        ([record['proposal_id'], record['original_proposal_id']],)).fetchall()
    by_id = {r['proposal_id']: r for r in rows}; assert len(by_id) == 2
    changed = by_id[record['proposal_id']]; original = by_id[record['original_proposal_id']]
    assert {k: changed[k] for k in ('status', 'version', 'epoch')} == record['committed_state']
    assert (original['status'], original['version'], original['epoch']) == ('approved', 2, 0)
    assert changed['created_by'] == original['created_by']
    events = conn.execute('SELECT proposal_id,proposal_version,actor_id FROM aip_action_withdrawal_event '
        'WHERE idempotency_key=%s', (record['idempotency_key'],)).fetchall()
    assert events == [dict(proposal_id=record['proposal_id'], proposal_version=3, actor_id=changed['created_by'])]
    assert conn.execute("SELECT count(*) AS n FROM aip_action_event WHERE proposal_id=%s "
        "AND event_type='withdrawn'", (record['proposal_id'],)).fetchone()['n'] == 1
    for signature, expected, definer in [
            ('public.aos_capacity_withdrawal_epoch_bump()', bump, True),
            ('aos_capacity_publication_private.read_original_source_facts(text,jsonb,jsonb)', prefix[0], False)]:
        fn = conn.execute('SELECT prosrc,prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure',
            (signature,)).fetchone()
        assert fn['prosrc'] == expected and fn['prosecdef'] == definer and fn['proconfig'] == ['search_path=pg_catalog']
    assert conn.execute("SELECT count(*) AS n FROM pg_proc WHERE proname LIKE 'publication_facts_harness_%' "
        "OR proname LIKE 'publication_signed_harness_%'").fetchone()['n'] == 0
    signed = conn.execute("""SELECT s.source_raw,s.content_hash,aos_ed25519.verify(s.signature,s.source_raw,
        decode(p.original_signed_facts->>'sourceSignerPublicKey','base64')) AS valid
        FROM aos_capacity_publication_private.source_publication s
        JOIN aos_capacity_publication_private.source_provenance p USING(org_id,project_id,asset_id)""").fetchall()
    assert len(signed) == 1 and signed[0]['valid']
    raw = bytes(signed[0]['source_raw']); assert hashlib.sha256(raw).hexdigest() == signed[0]['content_hash']
    source = parse_signed_capacity_body(raw, PublishedProviderCapacitySourceV2)
    assert source.source_proposal_ref.asset_id == record['original_proposal_id'] and not source.execution_allowed
    assert conn.execute('SELECT epoch,head_origin_hash FROM aos_capacity_publication_private.registry_epoch').fetchall() == [dict(epoch=2, head_origin_hash=None)]
    flags = conn.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
        "FROM pg_roles WHERE rolname='aos_provider_capacity_occupation'").fetchone()
    assert flags and not any(flags.values())
    assert conn.execute("SELECT count(*) AS n FROM pg_auth_members WHERE member='aos_provider_capacity_occupation'::regrole "
        "OR roleid='aos_provider_capacity_occupation'::regrole").fetchone()['n'] == 0
    counts = {t: conn.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in record['product_counts']}
    assert counts == record['product_counts'] and not any(counts.values())
    assert conn.execute("SELECT count(*) AS n FROM aip_action_withdrawal_event WHERE org_id='dev-org' "
        "AND idempotency_key=%s", (record['idempotency_key'],)).fetchone()['n'] == 0
result = dict(status='WRITER_FIRST_COMMIT_TRUSTED_SOURCE_PREFIX_AND_RETAINED_STATE_VERIFIED',
    identity=identity, original_source_proposal_unchanged=True, withdrawal_events=1,
    product_counts=counts, canary=0, original_harnesses_removed=True,
    trusted_prefix_sha256=hashlib.sha256(prefix[0].encode()).hexdigest(),
    trusted_bump_sha256=hashlib.sha256(bump.encode()).hexdigest(),
    file_sha256={n: hashlib.sha256((BASE / n).read_bytes()).hexdigest() for n in
        ('original_withdrawal_snapshot_probe.py', 'run_original_withdrawal_snapshot_probe.py',
            'original-withdrawal-snapshot-attempt.json', 'original-withdrawal-snapshot-verification.json',
            'original-withdrawal-snapshot-r1.log', 'verify_original_withdrawal_snapshot.py')},
    limitations=['Retained state verifies commit; past wait and SQLSTATE require the original executed probe',
        'Original fact prefix and separate proposal, not a complete signed Source or joint business proof'])
(BASE / 'original-withdrawal-snapshot-independent-verification.json').write_text(json.dumps(result, indent=2)+'\n')
print(result['status'], 'Source prefix unchanged; old Source proposal intact; withdrawal1; canary0')
