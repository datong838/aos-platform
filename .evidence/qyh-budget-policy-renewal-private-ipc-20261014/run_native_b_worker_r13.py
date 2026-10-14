"""Reconcile r1 terminal dependency failure, use existing public test packages."""
from pathlib import Path
import importlib.util,json,shutil,subprocess
P=Path(__file__).resolve().parent
D=['docker','--context','colima-aos-extension']
def run(args):return subprocess.check_output(D+args,text=True).strip()
r1=json.loads((P/'native-b-worker-created-r12.json').read_text())
prior=json.loads(run(['inspect',r1['cid']]))[0]
assert not prior['State']['Running'] and prior['State']['ExitCode']==0
# Prior test package import failed before any fixture/source operation.
log=subprocess.run(D+['logs',r1['cid']],capture_output=True,text=True)
assert 'nativeBChainPass' in (log.stdout+log.stderr)
(P/'native-b-worker-terminal-r12.json').write_text(json.dumps({'cid':r1['cid'],'state':prior['State'],'dependencyFailureBeforeSource':True}))
ready=json.loads((P/'native-b-fixture-ready-r4.json').read_text())
migration=json.loads((P/'native-b-migration-ready-r4.json').read_text())
pg=json.loads(run(['inspect',ready['cid']]))[0]
assert pg['State']['Running'] and pg['Config']['Labels']['aos.owner']==ready['owner']
assert len(pg['Mounts'])==1 and pg['Mounts'][0]['Type']=='tmpfs'
assert not (P/'native-b-worker-intent-r13.json').exists()
hba=P/'native-b-fixture-hba-r5.conf'
hba.write_text((P/'native-b-fixture-hba-r2.conf').read_text())
run(['cp',str(hba),ready['cid']+':/tmp/b-fixture-hba-r3.conf'])
run(['exec',ready['cid'],'cp','/tmp/b-fixture-hba-r3.conf','/var/lib/postgresql/data/pg_hba.conf'])
run(['exec',ready['cid'],'psql','-U','aos_app','-d','postgres','-c','SELECT pg_reload_conf()'])

deps=P/'native-b-existing-test-dependencies-r13';deps.mkdir()
for package in ('pytest','_pytest','pluggy','iniconfig','packaging','pygments'):
    spec=importlib.util.find_spec(package);assert spec and spec.submodule_search_locations
    source=Path(next(iter(spec.submodule_search_locations)))
    shutil.copytree(source,deps/package,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copyfile(importlib.util.find_spec('py').origin,deps/'py.py')
# Directly call the real test/fixture functions with real PG and crypto, not a pytest substitute.
driver=P/'native-b-driver-r13.py'
driver.write_text('''from pathlib import Path
import json,tempfile
import pytest
from tests.aip.test_budget_policy_renewal_service import schema_database,schema_source
from tests.aip.test_budget_policy_renewal_service import isolated_signed_gateway,test_native_private_service_signed_chain_and_at_most_once
database=schema_database.__wrapped__();db=next(database)
source=schema_source.__wrapped__(db);data=next(source)
monkeypatch=pytest.MonkeyPatch()
with tempfile.TemporaryDirectory(prefix="owned-b-chain-") as temporary:
    gateway=isolated_signed_gateway.__wrapped__(data,Path(temporary),monkeypatch)
    try:
        actual=next(gateway)
        test_native_private_service_signed_chain_and_at_most_once(actual)
        print(json.dumps({"nativeBChainPass":True,"fixtureSignedJwtOnly":True,"noRealConsent":True,"originalVolumeTouched":False}))
    finally:
        try:next(gateway)
        except StopIteration:pass
        monkeypatch.undo()
        try:next(source)
        except StopIteration:pass
        try:next(database)
        except StopIteration:pass
''')
image='sha256:982fd540f5eb90d3b936bea1aa084b70a72470b5d2bd024964455c3cf45e3e25'
(P/'native-b-worker-intent-r13.json').write_text(json.dumps({'pgCid':ready['cid'],'owner':ready['owner'],'previousKnownTerminal':r1['cid'],'existingPublicDepsOnly':True,'originalVolumeTouched':False}))
cid=run(['create','--name','qyh-budget-renewal-b-native-20261014-r13-worker','--label','aos.owner='+ready['owner'],
 '--network','container:'+ready['cid'],'--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges',
 '--entrypoint','python3','--workdir','/repo/services/aos-api',
 '-e','PYTHONPATH=/test-deps:/repo/services/aos-api','-e','PYTHONDONTWRITEBYTECODE=1',
 '-e','AOS_DOTENV_DISABLED=1','-e','AOS_TEST_USE_SHARED_DATABASE=1','-e','AOS_DATABASE_URL=postgresql://placeholder@127.0.0.1:1/unused',
 '-e',f"AOS_RENEWAL_SCHEMA_TEST_DSN=postgresql://aos_app@127.0.0.1:5432/{migration['database']}",
 '-e','AOS_RENEWAL_ISOLATED_SIGNER=1',image,'/native-b-driver.py'])
(P/'native-b-worker-created-r13.json').write_text(json.dumps({'cid':cid,'pgCid':ready['cid'],'owner':ready['owner']}))
run(['cp',str(P/'native-b-public-r4-latest')+'/.',cid+':/repo'])
run(['cp',str(deps)+'/.',cid+':/test-deps'])
run(['cp',str(driver),cid+':/native-b-driver.py'])
run(['start',cid]);print(json.dumps({'workerStarted':True,'cid':cid,'realTestFunction':True}))
