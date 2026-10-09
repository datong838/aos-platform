"""Read-only retained lab verification; no Source execution or DB cleanup."""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import types
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, str(Path('services/aos-api').resolve()))
from aos_api import aip_provider_capacity_publication_transaction as transaction
from aos_api import aip_provider_capacity_publication_store as store
from aos_api.aip_provider_capacity_occupation_epoch_profile import _body, PAIR, EVIDENCE

head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
assert head == '04a9cd1c9ebf9528928c9024835d1323623f558e'
compatibility=existing_consumer=False; cumulative=True
log_path=Path(__file__).with_name('adjacent-r1.log');log=log_path.read_text();summary='8 passed, 7 warnings in 102.92s';assert summary in log and ' skipped' not in log
databases = set(re.findall(r'Retained isolated test database: (aos_test_[0-9a-f]+_ti4_test)', log))
assert len(databases) == (9 if cumulative else 3 if compatibility or existing_consumer else 5)
lab=json.loads(Path(__file__).with_name('lab.json').read_text());passfile=Path(lab['passfile']);assert passfile.stat().st_mode & 0o077==0;container=lab['container_id']
expected = {
    PAIR: _body(store.CAPACITY_ORIGINAL_WITHDRAWAL_BOUNDARY_SQL, PAIR),
    EVIDENCE: _body(transaction._original_evidence_boundary_sql(), EVIDENCE),
}
rows = []
total = 0
for database in sorted(databases):
    with psycopg.connect(host='127.0.0.1', port=5436, dbname=database, user='aos_app', passfile=str(passfile),
                         row_factory=dict_row) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == lab['cluster']
        sources = conn.execute("""SELECT p.asset_id,p.content_hash,
            p.content_hash=encode(sha256(p.source_raw),'hex') AS hash_ok,
            aos_ed25519.verify(p.signature,p.source_raw,decode(s.signed_facts->>'sourceSignerPublicKey','base64')) AS signature_ok,
            s.finalized,(v.native_xid=s.native_xid AND v.native_pid=s.native_pid
              AND v.native_session=s.native_session AND s.native_session='aos_provider_capacity_issuer') AS provenance_ok
            FROM aos_capacity_publication_private.source_publication p
            JOIN aos_capacity_publication_private.source_pending s ON s.attempt_id=p.attempt_id
            JOIN aos_capacity_publication_private.source_provenance v
              ON (v.org_id,v.project_id,v.asset_id)=(p.org_id,p.project_id,p.asset_id)
            WHERE p.asset_id LIKE %s""", ('occupation-%',)).fetchall()
        assert all(all(r[k] for k in ('hash_ok', 'signature_ok', 'finalized', 'provenance_ok')) for r in sources)
        for signature, body in expected.items():
            actual = conn.execute('SELECT prosrc FROM pg_proc WHERE oid=to_regprocedure(%s)', (signature,)).fetchone()
            assert actual and actual['prosrc'] == body
        assert conn.execute("""SELECT NOT EXISTS(SELECT 1 FROM pg_proc p,LATERAL aclexplode(p.proacl) a
            WHERE p.oid='public.aos_capacity_evidence_epoch_lock(text,text,text)'::regprocedure
            AND a.grantee='aos_capacity_publication_owner'::regrole) AS clean""").fetchone()['clean']
        signatures = ['public.prepare_capacity_source(bytea,text,text,jsonb)', 'public.commit_capacity_source(text,bytea,bytea)',
            'public.read_current_capacity_source(bytea,jsonb)', 'public.read_capacity_source_for_occupation(bytea,jsonb)',
            'public.require_capacity_occupation_source_installation()',
            'aos_capacity_publication_private.require_current_source_installation()']
        assert all(conn.execute('SELECT to_regprocedure(%s) IS NULL AS absent', (s,)).fetchone()['absent'] for s in signatures)
        role = conn.execute("""SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,
            NOT EXISTS(SELECT 1 FROM pg_auth_members m WHERE m.roleid=r.oid OR m.member=r.oid) AS clean
            FROM pg_roles r WHERE rolname='aos_provider_capacity_occupation'""").fetchone()
        assert role and role['clean'] and not any(v for k,v in role.items() if k != 'clean')
        total += len(sources)
        rows.append({'database': database, 'sources': sources, 'legacy_audit_bodies_restored': True,
            'neutral_extra_grant_restored': True, 'temporary_interfaces_restored': True, 'occupation_role_restored': True})
        conn.rollback()
assert total == 4
original_files = ['services/aos-api/aos_api/aip_provider_capacity_publication_store.py',
    'services/aos-api/alembic/versions/a0v_150_provider_capacity_issuance_boundary.py']
assert all(subprocess.check_output(['git','show','HEAD:'+p]) == Path(p).read_bytes() for p in original_files)
legacy = types.ModuleType('occupation_verification_legacy_transaction')
sys.modules[legacy.__name__] = legacy
source_path = 'services/aos-api/aos_api/aip_provider_capacity_publication_transaction.py'
exec(compile(subprocess.check_output(['git','show','HEAD:'+source_path]), 'HEAD:'+source_path, 'exec'), legacy.__dict__)
default_outputs = {
    'private_installation': (legacy.source_private_installation_audit_sql(), transaction.source_private_installation_audit_sql()),
    'private_transaction': (legacy._source_transaction_statements(), transaction._source_transaction_statements()),
    'public_without_consumer': (legacy.source_public_entry_statements(), transaction.source_public_entry_statements()),
    'public_with_consumer': (legacy.source_public_entry_statements(include_consumer=True), transaction.source_public_entry_statements(include_consumer=True)),
}
assert all(before == after for before,after in default_outputs.values())
default_hashes = {name: hashlib.sha256(json.dumps(after).encode()).hexdigest() for name,(before,after) in default_outputs.items()}
paths = [*original_files, 'services/aos-api/aos_api/aip_provider_capacity_occupation_epoch_profile.py',
    source_path, 'services/aos-api/aos_api/aip_provider_capacity_publication_lock_boundary.py',
    'services/aos-api/aos_api/aip_provider_capacity_evidence_fence.py',
    'services/aos-api/aos_api/aip_provider_capacity_occupation_source.py',
    'services/aos-api/tests/aip/test_capacity_occupation_epoch_profile_pg.py',
    'services/aos-api/tests/aip/test_capacity_occupation_source_pg.py', str(log_path)]
report = {'schema': 'aos-occupation-epoch-profile-verification/v1', 'head': head,
    'result': summary, 'scope': 'EXISTING_CONSUMER_THREE_ENTRY_PROFILE' if existing_consumer else 'CUMULATIVE_PROFILE_AND_LEGACY_EPOCH' if cumulative else 'ISSUER_NATIVE_SQL_COMPATIBILITY' if compatibility else 'NONEXECUTING_ISOLATED_PROFILE_ONLY', 'container_id': container, 'retained_databases': rows,
    'durable_occupation_sources': total, 'original_default_files_unchanged': original_files,
    'default_sql_outputs_equal_HEAD': default_hashes,
    'sha256': {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
    'pending': ['full new-purpose role/effective privileges negatives',
        'new profile writer/reader competition and waiting JWT expiry', 'samecaller Source/sharedoccupation/budget/Intent integration',
        'formal deployment/identity/authorization', 'actual final COMMIT TTL'],
    'task_delivered': False, 'full_goal_complete': False, 'formal_resources_changed': False}
report_name = 'verification-existing-consumer.json' if existing_consumer else 'verification-cumulative.json' if cumulative else 'verification-issuer-compatibility.json' if compatibility else 'verification.json'
Path(__file__).with_name('independent-adjacent-verification.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'retained_databases': len(rows), 'durable_sources': total, 'restoration': 'VERIFIED',
    'original_default_files': 'UNCHANGED', 'formal_resources_changed': False}))
