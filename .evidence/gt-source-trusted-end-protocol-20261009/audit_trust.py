import hashlib,json,subprocess
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
F=R/'.evidence/gt-source-desktop-shm-lab-20261009';lab=json.loads((F/'lab.json').read_text())
p=json.loads((F/'independent-whole-final-verification.json').read_text());db=next(x['database'] for x in p['databases'] if x['sources'])
with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=db,passfile=lab['passfile'],row_factory=dict_row) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    assert c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']=='on'
    assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
    functions=c.execute("""SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid) AS arguments,p.prosrc,p.probin,p.prosecdef,p.proconfig,p.proowner::regrole::text AS owner,p.proacl::text
       FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='aos_ed25519' ORDER BY p.proname,p.oid""").fetchall()
    assert any(x['proname']=='verify' for x in functions)
    roles=c.execute("SELECT rolname,rolsuper,rolcanlogin,rolinherit,rolcreaterole,rolcreatedb,rolreplication,rolbypassrls FROM pg_roles WHERE rolname IN ('aos_runtime','aos_capacity_publication_owner','aos_provider_capacity_issuer','aos_provider_capacity_policy_publisher') ORDER BY rolname").fetchall()
    assert len(roles)==4 and all(not x['rolsuper'] and not x['rolbypassrls'] for x in roles)
    memberships=c.execute("SELECT member::regrole::text AS member,roleid::regrole::text AS role,admin_option FROM pg_auth_members WHERE member IN (SELECT oid FROM pg_roles WHERE rolname IN ('aos_runtime','aos_provider_capacity_issuer','aos_provider_capacity_policy_publisher')) ORDER BY member,role").fetchall()
    parameters=c.execute("SELECT name,setting,context,source FROM pg_settings WHERE name IN ('shared_preload_libraries','session_preload_libraries','local_preload_libraries','max_prepared_transactions') ORDER BY name").fetchall()
    privileges=[]
    for role in ('aos_runtime','aos_provider_capacity_issuer','aos_provider_capacity_policy_publisher'):
        row=c.execute("SELECT has_schema_privilege(%s,'aos_capacity_publication_private','CREATE') AS schema_create,has_table_privilege(%s,'aos_capacity_publication_private.source_pending','INSERT,UPDATE,DELETE') AS mutate_pending,has_function_privilege(%s,'aos_capacity_publication_private.require_pending_source_finalized()','EXECUTE') AS execute_pending_guard",(role,role,role)).fetchone()
        assert not row['schema_create'] and not row['mutate_pending'] and not row['execute_pending_guard'];privileges.append(dict(role=role,**row))
result=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),authority_revision='AOS-001650',database=db,cluster=lab['cluster'],read_only=True,verifier_functions=functions,roles=roles,memberships=memberships,preload_parameters=parameters,caller_privileges=privileges,callback_registration_not_inferred=True,strict_completion_deadline='RED_UNPROVEN',formal_execution=False)
(B/'trust-audit.json').write_text(json.dumps(result,indent=2))
print('Native READ ONLY verifier/caller/installation trust audit complete; no callback LOAD or configuration writes')
