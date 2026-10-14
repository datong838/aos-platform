from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys
root=Path('.evidence/qyh-creator-lifecycle-read-admission-20261014')
files=['services/aos-api/aos_api/routers/ecommerce_workshop.py','services/aos-api/tests/test_ecommerce_workshop_read_http.py','services/aos-api/aos_api/ecommerce_workshop_creator_lifecycle_readonly.py','services/aos-api/tests/aip/test_creator_lifecycle_readonly.py']
def hashes():return {f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in files}
start=datetime.datetime.now(datetime.timezone.utc).isoformat();before=hashes()
tests=['tests/test_ecommerce_workshop_read_http.py','tests/test_ecommerce_workshop_read_catalog.py','tests/aip/test_creator_lifecycle_readonly.py','tests/aip/test_creator_lifecycle_read_tenant.py','tests/aip/test_w6_04_creator_lifecycle.py','tests/aip/test_w6_04_creator_lifecycle_migration.py','tests/asset_registry/test_ecommerce_installed_readonly_catalog.py','tests/asset_registry/test_ecommerce_workshop_catalog.py']
env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','AOS_TEST_USE_SHARED_DATABASE':'1','AOS_DATABASE_URL':'postgresql://placeholder@127.0.0.1:1/unused','AOS_DOTENV_DISABLED':'1'}
cmd=[str(Path('services/aos-api/.venv/bin/python').absolute()),'-m','pytest','-p','no:cacheprovider',*[str(Path('services/aos-api')/t) for t in tests]]
with (root/'cumulative-green-r3.log').open('x') as log:r=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
after=hashes();assert before==after
receipt={'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'startedAt':start,'finishedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sourceBefore':before,'sourceAfter':after,'returncode':r.returncode,'command':cmd,'logSha256':hashlib.sha256((root/'cumulative-green-r3.log').read_bytes()).hexdigest(),'uncommittedCandidate':True,'originalRuntimeTouched':False,'redLogHistoricalPreimplementation':True}
(root/'cumulative-source-receipt-r3.json').write_text(json.dumps(receipt,indent=2))
assert r.returncode==0
print({'returncode':r.returncode,'sourceEqual':before==after})
