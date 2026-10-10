from pathlib import Path
import os,json,hashlib,subprocess
import psycopg
from psycopg.rows import dict_row
R=Path.cwd();N=Path(__file__).resolve().parent
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
c=json.loads(subprocess.check_output(['docker','--context',lab['context'],'inspect',lab['name']],text=True))[0];assert c['Id']==lab['container_id'] and c['State']['Running']
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname='aos_test_05f1a1dcd51f_ti4_test',passfile=lab['passfile'],row_factory=dict_row) as conn:
 conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 cluster=conn.execute('SELECT system_identifier::text AS v FROM pg_control_system()').fetchone()['v'];assert cluster==lab['cluster']
 rows=conn.execute("SELECT n.nspname,c.relname,t.tgname,t.tgdeferrable,t.tginitdeferred,p.prosrc,pg_get_userbyid(p.proowner) AS owner FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid WHERE n.nspname='aos_physical_capacity_occupation_private' AND p.proname='reject_unfinalized_parent_debit' ORDER BY c.relname,t.tgname").fetchall()
 assert len(rows)==7 and all(r['tgdeferrable'] and r['tginitdeferred'] for r in rows)
 assert all(r['prosrc'].strip()=="BEGIN RAISE EXCEPTION 'CAPACITY_PARENT_FINALIZE_REQUIRED' USING ERRCODE='23514'; END" for r in rows)
 guards=[dict(table=r['relname'],trigger=r['tgname'],owner=r['owner'],body_sha256=hashlib.sha256(r['prosrc'].encode()).hexdigest(),unconditional_reject=True) for r in rows]
 signature='public.finalize_capacity_shared_parent_admission(bytea,jsonb,uuid,text)'
 installed=conn.execute('SELECT to_regprocedure(%s)::text AS v',(signature,)).fetchone()['v'];assert installed is None
 conn.rollback()
(N/'native-finalizer-gap-1698.json').open('x').write(json.dumps(dict(cluster=cluster,readonly=True,guards=guards,candidate_signature=signature,candidate_installed=False,native_gap='RED: complete new-version admission finalizer not installed; old prepared lane unconditionally rejects',existing_guards_unchanged=True,product_files_created=False,execution_allowed=False,full_joint_pass=False),indent=2)+'\n')
print('native RED confirmed: candidate absent, original seven gates intact')
