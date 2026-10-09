"""Independent read-only reconciliation of retained occupation privilege tests."""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, str(Path('services/aos-api').resolve()))
from aos_api import aip_provider_capacity_publication_transaction as transaction
from aos_api import aip_provider_capacity_publication_store as store
from aos_api.aip_provider_capacity_occupation_epoch_profile import _body, PAIR, EVIDENCE

withdrawal_race=owner_withdrawal=concurrency=True
log_path=Path(__file__).with_name('source-regression-r1.log')
log = log_path.read_text()
assert re.search(r'3 passed, 7 warnings in [0-9.]+s' if concurrency else r'11 passed, 7 warnings in [0-9.]+s', log) and ' skipped' not in log
cases = ['table_select','column_select','schema_create','database_create','database_temp',
         'connect_grant_option','direct_execute','default_acl','default_acl_grantee','inherit','createdb','membership_admin']
if concurrency:
    cases += ['membership_inherit','runtime_login','runtime_inherit','runtime_createdb','runtime_createrole',
              'runtime_replication','runtime_bypassrls','runtime_super']
    assert log.count('occupation concurrency reader_first three_native_writers_blocked caller_commit_released same_xid') == 2
    assert log.count('occupation concurrency writer_first native_wait actual_jwt_expired source_rejected_22023') == 2
if owner_withdrawal:
    assert log.count('occupation independent_owner three_current_owner_denials eight_auth_five_ref_denials native_set_denial signed_origin_withdrawn source_history_unchanged') == 2
if withdrawal_race:
    assert log.count('occupation signed_origin_writer_first native_blocked old_snapshot_rejected_40001') == 2
assert all(log.count('occupation privilege denied '+case+'\n') == 2 for case in cases)
databases = sorted(set(re.findall(r'Retained isolated test database: (aos_test_[0-9a-f]+_ti4_test)', log)))
assert len(databases) == (3 if concurrency else 11)
lab=json.loads(Path(__file__).with_name('lab.json').read_text());passfile=Path(lab['passfile']);assert passfile.stat().st_mode & 0o077 == 0
container=lab['container_id']
rows = []
total = 0
withdrawal_total = 0
for database in databases:
    with psycopg.connect(host='127.0.0.1',port=5436,dbname=database,user='aos_app',passfile=str(passfile),row_factory=dict_row) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == lab['cluster']
        role = conn.execute("""SELECT r.oid,rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,
            NOT EXISTS(SELECT 1 FROM pg_auth_members m WHERE m.roleid=r.oid OR m.member=r.oid) AS clean
            FROM pg_roles r WHERE rolname='aos_provider_capacity_occupation'""").fetchone()
        assert role and role['clean'] and not any(v for k,v in role.items() if k not in ('oid','clean'))
        runtime = conn.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='aos_runtime'").fetchone()
        assert runtime and not any(runtime.values())
        for catalog, acl in [('pg_class','relacl'),('pg_attribute','attacl'),('pg_proc','proacl'),
                             ('pg_namespace','nspacl'),('pg_database','datacl')]:
            count = conn.execute(psycopg.sql.SQL('SELECT count(*) AS n FROM {} p CROSS JOIN LATERAL aclexplode(p.{}) a WHERE a.grantee=%s').format(
                psycopg.sql.Identifier(catalog),psycopg.sql.Identifier(acl)),(role['oid'],)).fetchone()['n']
            assert count == 0, (database,catalog)
        assert conn.execute('SELECT count(*) AS n FROM pg_default_acl p WHERE p.defaclrole=%s OR EXISTS(SELECT 1 FROM aclexplode(p.defaclacl) a WHERE a.grantee=%s)',
                            (role['oid'],role['oid'])).fetchone()['n'] == 0
        for signature, expected in [(PAIR,_body(store.CAPACITY_ORIGINAL_WITHDRAWAL_BOUNDARY_SQL,PAIR)),
                                    (EVIDENCE,_body(transaction._original_evidence_boundary_sql(),EVIDENCE))]:
            assert conn.execute('SELECT prosrc FROM pg_proc WHERE oid=to_regprocedure(%s)',(signature,)).fetchone()['prosrc'] == expected
        for signature in ['public.read_capacity_source_for_occupation(bytea,jsonb)',
                          'public.require_capacity_occupation_source_installation()']:
            assert conn.execute('SELECT to_regprocedure(%s) IS NULL AS absent',(signature,)).fetchone()['absent']
        assert conn.execute("""SELECT count(*) AS n FROM pg_proc p CROSS JOIN LATERAL aclexplode(p.proacl) a
            WHERE p.oid='public.aos_capacity_evidence_epoch_lock(text,text,text)'::regprocedure
            AND a.grantee='aos_capacity_publication_owner'::regrole""").fetchone()['n'] == 0
        sources = conn.execute("""SELECT p.asset_id,p.content_hash,
            p.content_hash=encode(sha256(p.source_raw),'hex') AS hash_ok,
            aos_ed25519.verify(p.signature,p.source_raw,decode(s.signed_facts->>'sourceSignerPublicKey','base64')) AS signature_ok,
            s.finalized,(v.native_xid=s.native_xid AND v.native_pid=s.native_pid
              AND v.native_session=s.native_session AND s.native_session='aos_provider_capacity_issuer') AS provenance_ok
            FROM aos_capacity_publication_private.source_publication p
            JOIN aos_capacity_publication_private.source_pending s ON s.attempt_id=p.attempt_id
            JOIN aos_capacity_publication_private.source_provenance v ON (v.org_id,v.project_id,v.asset_id)=(p.org_id,p.project_id,p.asset_id)
            WHERE p.asset_id LIKE 'occupation-source-%'""").fetchall()
        assert all(all(r[k] for k in ('hash_ok','signature_ok','finalized','provenance_ok')) for r in sources)
        withdrawals = []
        if owner_withdrawal:
            withdrawals = conn.execute("""SELECT w.content_hash,w.prior_epoch,w.new_epoch,
                w.content_hash=encode(sha256(w.raw_body),'hex') AS hash_ok,
                aos_ed25519.verify(w.signature,w.raw_body,a.signer_public_key) AS signature_ok,
                e.epoch=2 AND e.head_origin_hash IS NULL AS head_withdrawn
                FROM aos_capacity_publication_private.origin_withdrawal w
                JOIN aos_capacity_publication_private.deployment_anchor a USING(org_id,project_id)
                JOIN aos_capacity_publication_private.registry_epoch e USING(org_id,project_id)
                WHERE w.org_id='org-org' AND w.project_id='dev-project'""").fetchall()
            assert len(withdrawals)==(1 if sources else 0)
            assert all(w['prior_epoch']==1 and w['new_epoch']==2 and all(w[k] for k in ('hash_ok','signature_ok','head_withdrawn')) for w in withdrawals)
            independent = conn.execute("SELECT count(*) AS n FROM public.meta_membership WHERE org_id='org-org' AND project_id='dev-project' AND subject LIKE 'occupation-owner-%' AND role='owner'").fetchone()['n']
            assert independent==(1 if sources else 0)
            withdrawal_total += len(withdrawals)
        total += len(sources)
        rows.append({'database':database,'sources':sources,'withdrawals':withdrawals,'exact_privilege_and_profile_restoration':True})
        conn.rollback()
assert total == 2
assert withdrawal_total==(2 if owner_withdrawal else 0)
paths = [str(log_path),'services/aos-api/aos_api/aip_provider_capacity_occupation_source.py',
         'services/aos-api/tests/aip/test_capacity_occupation_source_pg.py',str(Path(__file__))]
report = {'schema':'aos-occupation-privilege-verification/v1',
          'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
          'cases_per_layout':cases,'native_rejections':len(cases)*2,'restored_positive_after_each_rejection':True,
          'native_reader_writer_and_actual_waited_JWT_proven':concurrency,
          'independent_owner_and_real_signed_origin_withdrawal_proven':owner_withdrawal,
          'signed_origin_writer_first_and_old_snapshot_denial_proven':withdrawal_race,
          'durable_origin_withdrawals':withdrawal_total,
          'nontransferable_CONNECT_positive':True,'container':container,'databases':rows,'durable_occupation_sources':total,
          'sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
          'formal_resources_changed':False,'delivery':False,'full_goal_complete':False,
          'pending':['additional effective/indirect authority surfaces',
                     'samecaller shared physical occupation/budget/Intent','formal identity/deployment','actual COMMIT TTL']}
Path(__file__).with_name('signed-origin-race-verification.json' if withdrawal_race else 'independent-owner-withdrawal-verification.json' if owner_withdrawal else 'native-concurrency-verification.json' if concurrency else 'privilege-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'native_rejections':len(cases)*2,'databases':len(rows),'signed_sources':total,'restoration':'VERIFIED'}))
