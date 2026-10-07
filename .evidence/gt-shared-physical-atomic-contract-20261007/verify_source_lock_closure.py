"""Independent AST controls, retained helper hashes and exact fixture restoration."""
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

BASE=Path(__file__).resolve().parent
REPO=BASE.parents[1]
sys.path.insert(0,str(REPO/'services/aos-api'))
sys.path.insert(0,str(BASE))
from source_lock_closure_probe import describe
from aos_api.aip_provider_capacity_occupation_source import occupation_source_statements
from aos_api.aip_provider_capacity_occupation_epoch_profile import legacy_epoch_profile_restoration_statements, occupation_epoch_profile_statements

record=json.loads((BASE/'source-lock-closure.json').read_text())
assert record['identity']['database']=='aos_test_2807432bd393_ti4_test'
assert len(record['functions'])==59 and record['unresolved_explicit_calls']==[]
assert not any(f['parse_failures'] or f['dynamic_statements'] for f in record['functions'])
assert record['conservative_overload_candidates']=={'public.digest':2}
opaque=[f['identity'] for f in record['functions'] if f.get('opaque_non_SQL_language')]
assert len(opaque)==3

controls={}
for name,body in [
    ('literal',"BEGIN IF 'EXECUTE'='EXECUTE' THEN PERFORM 1; END IF; END"),
    ('dynamic',"BEGIN EXECUTE format('SELECT x FROM public.sample WHERE id=%s',1); END"),
    ('lock',"BEGIN PERFORM 1 FROM public.sample FOR UPDATE; END"),
    ('assignment','DECLARE v jsonb; BEGIN v:=aos_capacity_publication_private.control_helper(); END')]:
    definition='CREATE FUNCTION public.control_'+name+'() RETURNS void LANGUAGE plpgsql AS $$'+body+'$$'
    actual=describe(dict(identity=name,language='plpgsql',body=body,definition=definition))
    assert actual['parse_failures']==[]
    controls[name]=dict(dynamic=len(actual['dynamic_statements']),
        locks=sum(len(e['locks']) for e in actual['expressions']),
        calls=sorted({call for e in actual['expressions'] for call in e['calls']}))
assert controls['literal']==dict(dynamic=0,locks=0,calls=[])
assert controls['dynamic']['dynamic']==1
assert controls['lock']['locks']==1
assert controls['assignment']['calls']==['aos_capacity_publication_private.control_helper']

def expected_bodies(statements):
    result={}
    for statement in statements:
        for match in re.finditer(r'CREATE(?: OR REPLACE)? FUNCTION\s+([\w.]+)\([^)]*\).*?'
                r'AS\s+(\$\w*\$)(.*?)\2',statement,re.S):
            result[match.group(1)]=hashlib.sha256(match.group(3).encode()).hexdigest()
    return result

roots=expected_bodies(occupation_source_statements())
restored=expected_bodies(legacy_epoch_profile_restoration_statements())
assert len(roots)==2 and len(restored)==3
installation='aos_capacity_publication_private.require_current_source_installation'
active_profiles=expected_bodies(occupation_epoch_profile_statements())
fixture_path=REPO/'services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py'
fixture_tree=ast.parse(fixture_path.read_text())
fixture=next(n for n in fixture_tree.body if isinstance(n,ast.FunctionDef) and n.name=='exact_public_source_caller')
cleanup=next(n for n in fixture.body if isinstance(n,ast.Try) and n.finalbody).finalbody
assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='execute'
    and n.args and isinstance(n.args[0],ast.Constant)
    and n.args[0].value=='DROP FUNCTION '+installation+'()'
    for statement in cleanup for n in ast.walk(statement))
removed=set(roots)|{installation}
retained_restored=set(restored)-{installation}
assert len(retained_restored)==2
for f in record['functions']:
    name=f['identity'].split('(')[0]
    if name in roots:assert f['body_sha256']==roots[name]
    if name==installation:assert f['body_sha256']==active_profiles[name]

PASSFILE=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert PASSFILE.stat().st_mode&0o077==0
for key in ('PGPASSWORD','PGPASSFILE','PGOPTIONS','PGSERVICE','PGSERVICEFILE'):
    os.environ.pop(key,None)
with psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',dbname=record['identity']['database'],
        passfile=str(PASSFILE),row_factory=dict_row) as conn:
    conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    identity=conn.execute("SELECT current_database() AS database,current_setting('transaction_read_only') AS readonly,"
        "system_identifier::text AS cluster FROM pg_control_system()").fetchone()
    assert identity==record['identity']
    live=conn.execute("""SELECT n.nspname||'.'||p.proname||'('||pg_get_function_identity_arguments(p.oid)||')' AS identity,
        n.nspname||'.'||p.proname AS name,p.prosrc AS body
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE p.prokind='f' AND (n.nspname='public' OR n.nspname='aos_ed25519'
            OR n.nspname LIKE 'aos_capacity_%private')""").fetchall()
    by_id={f['identity']:f for f in live};matched=0
    for f in record['functions']:
        name=f['identity'].split('(')[0]
        if name in removed:
            assert f['identity'] not in by_id
        else:
            assert f['identity'] in by_id
            digest=hashlib.sha256(by_id[f['identity']]['body'].encode()).hexdigest()
            if name in retained_restored:assert digest==restored[name]
            else:
                assert digest==f['body_sha256']
                matched+=1
    assert matched==54
    source=conn.execute("""SELECT s.source_raw,aos_ed25519.verify(s.signature,s.source_raw,
        decode(p.original_signed_facts->>'sourceSignerPublicKey','base64')) AS signed
        FROM aos_capacity_publication_private.source_publication s
        JOIN aos_capacity_publication_private.source_provenance p USING(org_id,project_id,asset_id)
        WHERE s.content_hash=%s""",(record['source_hash'],)).fetchone()
    assert source['signed'] and hashlib.sha256(bytes(source['source_raw'])).hexdigest()==record['source_hash']
    assert conn.execute('SELECT epoch,head_origin_hash FROM aos_capacity_publication_private.registry_epoch').fetchall()==[dict(epoch=2,head_origin_hash=None)]
    flags=conn.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
        "FROM pg_roles WHERE rolname='aos_provider_capacity_occupation'").fetchone()
    assert flags and not any(flags.values())
    assert conn.execute("SELECT count(*) AS n FROM pg_auth_members WHERE member='aos_provider_capacity_occupation'::regrole "
        "OR roleid='aos_provider_capacity_occupation'::regrole").fetchone()['n']==0
    counts={table:conn.execute('SELECT count(*) AS n FROM '+table).fetchone()['n'] for table in
        ('aip_agent_run','aip_model_capacity_reservation','aip_budget_reservation','aip_model_eval_budget_reservation')}
    assert not any(counts.values())
    assert conn.execute("SELECT count(*) AS n FROM aip_model_capacity_reservation WHERE org_id='dev-org'").fetchone()['n']==0
result=dict(status='SOURCE_AST_CONTROLS_AND_RETAINED_RESTORATION_VERIFIED',identity=identity,
    synthetic_parser_controls=controls,unchanged_helper_bodies=matched,
    root_entries_removed=2,outer_fixture_installation_audit_removed=1,trusted_legacy_profiles_restored=2,
    fixture_cleanup_sha256=hashlib.sha256(fixture_path.read_bytes()).hexdigest(),signed_source_history_valid=True,
    origin_withdrawn=True,occupation_role_inert=True,product_counts=counts,canary=0,
    file_sha256={name:hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in
        ('source_lock_closure_probe.py','run_source_lock_closure_probe.py','source-lock-closure.json',
            'source-lock-closure-r1.json','source-lock-closure-r2.log','verify_source_lock_closure.py')},
    limitations=['Parser controls are synthetic grammar cases, not database business authority',
        'Original successful Source native test proves active installation window, not retained current admission',
        'Three non-SQL crypto functions, conservative overloads, implicit locks and opposite writers remain separately governed'])
(BASE/'source-lock-closure-independent-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],'59 AST functions; 54 unchanged; original profiles2 restored; roots2 plus outer installation audit removed; canary0')
