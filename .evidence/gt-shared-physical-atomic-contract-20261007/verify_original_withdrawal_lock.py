"""Independent original API commit, epoch trigger and preserved Source readback."""
import ast
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
sys.path.insert(0, str(REPO / 'services/aos-api'))
from aos_api.aip_provider_capacity_publication_contracts import (
    PublishedProviderCapacitySourceV2, parse_signed_capacity_body)

record = json.loads((BASE / 'original-withdrawal-lock-verification.json').read_text())
assert record['identity']['database'] == 'aos_test_384992d717f4_ti4_test'
assert record['after_epoch'] == record['before_epoch']+1 == 1
assert record['after_proposal_version'] == record['before_proposal_version']+1 == 3
assert record['proposal_id'] != record['original_source_proposal_id']
assert record['probe_sha256'] == hashlib.sha256((BASE / 'original_withdrawal_lock_probe.py').read_bytes()).hexdigest()
migration = REPO / 'services/aos-api/alembic/versions/a0v_151_capacity_withdrawal_epoch.py'
tree = ast.parse(migration.read_text())
expected = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
    and any(isinstance(t, ast.Name) and t.id == 'BUMP_BODY' for t in n.targets))
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
    rows = conn.execute("""SELECT p.proposal_id,p.status,p.version,p.created_by,x.epoch
        FROM aip_action_proposal p JOIN aip_capacity_withdrawal_epoch x
        USING(org_id,project_id,proposal_id) WHERE p.proposal_id=ANY(%s)""",
        ([record['proposal_id'], record['original_source_proposal_id']],)).fetchall()
    by_id = {r['proposal_id']: r for r in rows}
    assert len(by_id) == 2
    changed = by_id[record['proposal_id']]; original = by_id[record['original_source_proposal_id']]
    assert (changed['status'], changed['version'], changed['epoch'], changed['created_by']) == (
        'withdrawn', 3, 1, record['maker'])
    assert (original['status'], original['version'], original['epoch']) == ('approved', 2, 0)
    withdrawal = conn.execute('SELECT proposal_id,proposal_version,actor_id FROM aip_action_withdrawal_event '
        'WHERE idempotency_key=%s', (record['idempotency_key'],)).fetchall()
    assert withdrawal == [dict(proposal_id=record['proposal_id'], proposal_version=3, actor_id=record['maker'])]
    assert conn.execute("SELECT count(*) AS n FROM aip_action_event WHERE proposal_id=%s "
        "AND event_type='withdrawn'", (record['proposal_id'],)).fetchone()['n'] == 1
    fn = conn.execute("SELECT p.prosrc,p.prosecdef,p.proconfig,r.rolname AS owner FROM pg_proc p "
        "JOIN pg_roles r ON r.oid=p.proowner WHERE p.oid='public.aos_capacity_withdrawal_epoch_bump()'::regprocedure").fetchone()
    assert fn['prosrc'] == expected and fn['prosecdef'] and fn['proconfig'] == ['search_path=pg_catalog']
    assert fn['owner'] == 'aos_capacity_withdrawal_epoch_owner'
    triggers = conn.execute("SELECT tgname,tgtype,tgisinternal,tgenabled,tgdeferrable,tginitdeferred "
        "FROM pg_trigger WHERE tgrelid='public.aip_action_withdrawal_event'::regclass "
        "AND (tgisinternal OR tgname='zz_capacity_withdrawal_epoch_bump_a0v151') ORDER BY tgname").fetchall()
    bump = [t for t in triggers if not t['tgisinternal']]
    assert len(bump) == 1 and bump[0]['tgtype'] == 5 and bump[0]['tgenabled'] == 'O'
    fks = [t for t in triggers if t['tgisinternal'] and t['tgtype'] & 4]
    assert fks and all(t['tgtype'] == 5 and t['tgenabled'] == 'O' and not t['tgdeferrable']
        and not t['tginitdeferred'] and t['tgname'] < bump[0]['tgname'] for t in fks)
    signed = conn.execute("""SELECT s.source_raw,s.content_hash,aos_ed25519.verify(s.signature,s.source_raw,
        decode(p.original_signed_facts->>'sourceSignerPublicKey','base64')) AS valid
        FROM aos_capacity_publication_private.source_publication s
        JOIN aos_capacity_publication_private.source_provenance p USING(org_id,project_id,asset_id)""").fetchall()
    assert len(signed) == 1 and signed[0]['valid']
    raw = bytes(signed[0]['source_raw'])
    assert hashlib.sha256(raw).hexdigest() == signed[0]['content_hash']
    source = parse_signed_capacity_body(raw, PublishedProviderCapacitySourceV2)
    assert source.source_proposal_ref.asset_id == record['original_source_proposal_id']
    assert source.execution_allowed is False
    assert conn.execute('SELECT epoch,head_origin_hash FROM aos_capacity_publication_private.registry_epoch').fetchall() == [dict(epoch=2, head_origin_hash=None)]
    assert conn.execute("SELECT to_regprocedure('public.read_capacity_source_for_occupation(bytea,jsonb)') AS f").fetchone()['f'] is None
    flags = conn.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
        "FROM pg_roles WHERE rolname='aos_provider_capacity_occupation'").fetchone()
    assert flags and not any(flags.values())
    assert conn.execute("SELECT count(*) AS n FROM pg_auth_members WHERE member='aos_provider_capacity_occupation'::regrole "
        "OR roleid='aos_provider_capacity_occupation'::regrole").fetchone()['n'] == 0
    counts = {t: conn.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in record['product_counts']}
    assert counts == record['product_counts'] and not any(counts.values())
    assert conn.execute("SELECT count(*) AS n FROM aip_action_withdrawal_event WHERE org_id='dev-org' "
        "AND idempotency_key=%s", (record['idempotency_key'],)).fetchone()['n'] == 0
result = dict(status='ORIGINAL_WITHDRAWAL_COMMIT_AND_TRUSTED_TRIGGER_INDEPENDENTLY_VERIFIED',
    identity=identity, withdrawal_events=1, action_events=1, new_proposal_version=3, new_epoch=1,
    original_source_proposal_unchanged=True, original_source_signature_valid=True, source_origin_withdrawn=True,
    trusted_bump_body_sha256=hashlib.sha256(expected.encode()).hexdigest(),
    original_fk_before_after_bump_verified=True, product_counts=counts, canary=0,
    file_sha256={n: hashlib.sha256((BASE / n).read_bytes()).hexdigest() for n in
        ('original_withdrawal_lock_probe.py', 'run_original_withdrawal_lock_probe.py',
            'original-withdrawal-lock-verification.json', 'original-withdrawal-r1-reconciliation.json',
            'verify_original_withdrawal_lock.py')},
    limitations=['Wait evidence belongs to the executed original probe; retained state alone cannot prove prior waiting',
        'Separate approved proposal and isolated row-lock primitives, not joint business admission'])
(BASE / 'original-withdrawal-lock-independent-verification.json').write_text(json.dumps(result, indent=2)+'\n')
print(result['status'], 'withdrawal1; epoch1; original Source proposal intact; canary0')
