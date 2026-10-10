from pathlib import Path
import os,json,sys,subprocess,hashlib
B=Path(__file__).resolve().parent;R=B.parents[2]
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
item=json.loads(subprocess.check_output(['docker','--context',lab['context'],'inspect',lab['name']],text=True))[0]
assert item['Id']==lab['container_id'] and item['Image']==lab['image'] and item['State']['Running']
for key in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(key,None)
os.environ.update(AOS_DATABASE_URL='postgresql://aos_app@127.0.0.1:5441/aos_meta',AOS_DOTENV_DISABLED='1',AOS_EXTENSION_PG_TEST='1',AOS_EXTENSION_PG_HOST='127.0.0.1',AOS_EXTENSION_PG_PORT='5441',AOS_EXTENSION_PG_USER='aos_app',AOS_EXTENSION_PG_DATABASE='aos_meta',AOS_TEST_RETAIN_DATABASE='1',AOS_TEST_USE_SHARED_DATABASE='0',AOS_CATALOG_SIGNED_EVIDENCE=str(B))
sys.path.insert(0,str(R/'services/aos-api'))
import psycopg
from psycopg.conninfo import conninfo_to_dict
original=psycopg.connect
# Supply the existing lab passfile only to the native isolated admin; never
# inspect or serialize its contents, or alter actual issuer credentials.
def connect(*args,**kwargs):
 p=conninfo_to_dict(args[0] if args else kwargs.get('conninfo',''))
 for key in ('host','port','user','dbname'):
  if key in kwargs:p[key]=kwargs[key]
 if p.get('user')=='aos_app':
  assert p.get('host')=='127.0.0.1' and str(p.get('port'))=='5441'
  assert p.get('dbname')=='aos_meta' or p.get('dbname','').startswith('aos_test_')
  kwargs['passfile']=lab['passfile']
 return original(*args,**kwargs)
psycopg.connect=connect
with original(host='127.0.0.1',port=5441,user='aos_app',dbname='aos_meta',passfile=lab['passfile']) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster'];c.rollback()
files=['services/aos-api/aos_api/'+n+'.py' for n in ('aip_provider_capacity_catalog_audit_profile','aip_provider_capacity_occupation_epoch_profile','aip_provider_capacity_publication_transaction','aip_provider_capacity_occupation_source')]+['services/aos-api/tests/aip/test_provider_capacity_catalog_audit_profile_pg.py']
(B/'attempt.json').open('x').write(json.dumps(dict(authority='AOS-001764',head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),task='gt-capacity-source-catalog-profile-20261011',cluster=lab['cluster'],file_hashes={f:hashlib.sha256((R/f).read_bytes()).hexdigest() for f in files},execution_allowed=False),indent=2)+'\n')
import pytest
class Record:
 def __init__(self):self.databases=[];self.reports=[]
 def pytest_runtest_call(self,item):
  from aos_api.db import get_dsn
  self.databases.append(conninfo_to_dict(get_dsn())['dbname'])
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.reports.append(dict(node=report.nodeid,phase=report.when,outcome=report.outcome))
r=Record();code=pytest.main([str(R/'services/aos-api/tests/aip/test_provider_capacity_catalog_audit_profile_pg.py')+'::test_catalog_profile_real_signed_source_commit_and_fresh_consumer','-q','-s','-p','no:cacheprovider'],plugins=[r]);(B/'result.json').open('x').write(json.dumps(dict(pytest_exit=int(code),databases=r.databases,reports=r.reports,execution_allowed=False),indent=2)+'\n');raise SystemExit(code)
