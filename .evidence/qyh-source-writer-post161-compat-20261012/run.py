import json,subprocess,hashlib,importlib.util,os
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.cwd();R=ROOT/'.evidence/qyh-source-writer-post161-compat-20261012';C='colima-aos-extension';LAB='qyh-source-writer-lab-20261011-recovered-20261012'
s=importlib.util.spec_from_file_location('ro',ROOT/'.evidence/qyh-current159-fresh-backup-restore-20261012/backup_restore.py');ro=importlib.util.module_from_spec(s);s.loader.exec_module(ro)
def emit(n,d):
 with (R/n).open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2);f.write('\n')
def lab_sql(q):return subprocess.check_output(['docker','--context',C,'exec',LAB,'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','postgres','-d','postgres','-c',q],text=True).strip()
assert not (R/'intent.json').exists(),'Existing attempt: reconcile only'
item=json.loads(subprocess.check_output(['docker','--context',C,'inspect',LAB],text=True))[0]
assert item['Id']=='73d28f492ab3c03ac0eb25f4fac5ba1db2a67941acfb1a860210ed57a657c9e7' and item['State']['Running'] and not item['Mounts']
assert item['NetworkSettings']['Ports']['5432/tcp']==[{'HostIp':'127.0.0.1','HostPort':'18432'}]
assert item['Config']['Labels']['aos.task']=='qyh-full-system-restoration-20261011'
assert lab_sql('SELECT system_identifier FROM pg_control_system();')=='7695402775127154735'
role_sql="SELECT count(*) FROM pg_roles WHERE rolname IN ('aos_bi_plan_issuer','aos_content_source_issuer','aos_contract_source_issuer');"
assert lab_sql(role_sql)=='0'
assert lab_sql("SELECT count(*) FROM pg_stat_activity WHERE datname<>'postgres' AND backend_type='client backend';")=='0'
assert ro.current_sql('SELECT version_num FROM alembic_version;').strip()=='a0v_161'
source=ro.source_fingerprint();assert len(source)==650
private=R/'private';private.mkdir(mode=0o700)
p=private/'before-source.json'
with os.fdopen(os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as f:json.dump(source,f,sort_keys=True)
files=['aos_api/aip_bi_plan_issuer_connection.py','aos_api/aip_source_issuer_connection.py','tests/aip/test_aip_source_issuer_connection_pg.py','tests/extension_runtime/test_plan_receipt_writer_protocol_pg.py','tests/conftest.py']
hashes={f:hashlib.sha256((ROOT/'services/aos-api'/f).read_bytes()).hexdigest() for f in files}
argv=[str(ROOT/'services/aos-api/.venv/bin/python'),'-m','pytest','tests/aip/test_aip_source_issuer_connection_pg.py','tests/extension_runtime/test_plan_receipt_writer_protocol_pg.py','-ra','--junitxml='+str(R/'native-junit.xml')]
env=dict(os.environ);env.update(AOS_DOTENV_DISABLED='1',AOS_SOURCE_ISSUER_PG_TEST='1',AOS_EXTENSION_PG_TEST='1',AOS_DATABASE_URL='postgresql://postgres@127.0.0.1:18432/postgres',PYTHONDONTWRITEBYTECODE='1',AOS_EXTENSION_RUNTIME_HOST_ENABLED='0',AOS_QYH_CRON_ENABLED='false')
env.pop('AOS_TEST_USE_SHARED_DATABASE',None)
emit('intent.json',{'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'authority':'AOS-001977','labContainerId':item['Id'],'labCluster':'7695402775127154735','sourceVersion':'a0v_161','sourceTables':650,'sourceManifestSha256':hashlib.sha256(p.read_bytes()).hexdigest(),'currentFiles':hashes,'argv':argv,'testOnly':True,'sourceMutationsAuthorized':False})
with (R/'original-native.log').open('x') as f:proc=subprocess.run(argv,cwd=ROOT/'services/aos-api',env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180)
after=ro.source_fingerprint();assert source==after,'Authoritative source changed'
assert lab_sql(role_sql)=='0','Temporary issuer role leak'
assert all(hashlib.sha256((ROOT/'services/aos-api'/f).read_bytes()).hexdigest()==h for f,h in hashes.items())
emit('result.json',{'returnCode':proc.returncode,'all650SourceTablesUnchanged':True,'temporaryIssuerRoles':0,'testSourceFilesUnchanged':True,'sourcePrivilegesChanged':False,'wholeProductionSourceReady':False,'eightPagesAccepted':False,'naturalFirstChainAccepted':False,'observedAt':datetime.now(timezone.utc).isoformat()})
print('Native return code',proc.returncode,'Source650 unchanged; issuer roles0; examine junit for scope and failures')
