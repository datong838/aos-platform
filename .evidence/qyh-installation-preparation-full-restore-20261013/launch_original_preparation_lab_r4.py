"""Protected frozen-source launcher; no passwords in environment or arguments."""
from pathlib import Path
import runpy,json,os,sys,subprocess
from psycopg.conninfo import conninfo_to_dict,make_conninfo
P=Path(__file__).resolve().parent;ROOT=P.parents[1];NAME=P.name+'-transport'
sys.path.insert(0,str(ROOT/'scripts'));import a0v_qyh_restored_http as entry
source=entry.require_api_source_candidate(P.parent/'qyh-full-system-restoration-20261011/selected-installation-preparation-api-20261013.json')
state=json.loads((P/'lab-transport-verification.json').read_text());assert state['outcome']=='REAL_ISOLATED_THREE_PLANE_LAB_TRANSPORT_GREEN'
clone=json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','inspect',NAME],text=True))[0];assert clone['Id']==state['container'] and clone['Mounts'][0]['Name']==P.name
creds=json.loads((P/'private/lab-identities.json').read_text());runtime=conninfo_to_dict(creds['runtime']['dsn']);assert runtime['host']=='127.0.0.1' and runtime['port']=='18549' and runtime['dbname']=='aos_meta_head';runtime.pop('password')
passfile=P/'private/lab-runtime.pgpass'
assert passfile.stat().st_mode & 0o777==0o600
assert passfile.read_text()=='127.0.0.1:18549:aos_meta_head:'+creds['runtime']['role']+':'+creds['runtime']['password']+'\n'
assert (P/'original-lab-apply-receipt-r3.json').exists() and not (P/'original-lab-continue-accepted-operation-r4.json').exists()
parent=P.parent/'qyh-full-system-restoration-20261011'
env={k:v for k,v in os.environ.items() if not k.startswith(('AOS_','PG')) and k not in ('PYTHONPATH','PYTHONHOME')}
env.update({'AOS_DOTENV_DISABLED':'1','PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(source/'services/aos-api'),'AOS_DATABASE_URL':make_conninfo(**runtime),'PGPASSFILE':str(passfile.resolve()),'AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE':str((P/'private/lab-identities.json').resolve()),'AOS_BUNDLE_ROOT':str((parent/'selected-public-bundles').resolve()),'AOS_BUNDLE_TRUST_ROOTS_FILE':str((parent/'restoration-public-trust-roots.json').resolve()),'AOS_EXTENSION_RUNTIME_HOST_ENABLED':'0','QYH_ISOLATED_EVIDENCE_DIRECTORY':str(P.resolve())})
r=subprocess.run([sys.executable,str((P/'original_preparation_lab_r4.py').resolve())],cwd=source,env=env,timeout=180)
raise SystemExit(r.returncode)
