"""Original candidate reader, real current readonly role, counts only."""
from pathlib import Path
import os,sys,subprocess,json
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
sys.path.insert(0,str(ROOT/'scripts'));import a0v_qyh_restored_http as entry
source=entry.require_api_source_candidate(P/'selected-installation-preparation-api-20261013.json')
env={k:v for k,v in os.environ.items() if not k.startswith(('AOS_','PG')) and k not in ('PYTHONPATH','PYTHONHOME')}
env.update({'AOS_DOTENV_DISABLED':'1','PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(source/'services/aos-api'),'AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE':str((P/'private/current-runtime-host-identities-20261013.json').resolve())})
code='''import json
from contextlib import contextmanager
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
from aos_api.extension_runtime.runtime_configuration_candidates import RuntimeConfigurationCandidateReader
from aos_api.tenant_scope import TenantScope
@contextmanager
def readonly():
 with runtime_worker_connection() as conn:
  conn.read_only=True
  yield conn
value=RuntimeConfigurationCandidateReader(connect_factory=readonly).read(TenantScope('org-org','dev-project'))
print(json.dumps({'counts':value.counts,'missing':list(value.missing),'allPresent':value.all_present,'configurationBoundToCurrentInstallation':False,'humanSpendingAuthorityVerified':False,'currentDatabaseWrites':False}))
'''
if __name__=='__main__':
 r=subprocess.run([sys.executable,'-c',code],cwd=source,env=env,capture_output=True,text=True,timeout=45)
 output=json.loads(r.stdout.splitlines()[-1]) if r.stdout.strip() and r.stdout.splitlines()[-1].startswith('{') else {}
 with (P/'current-eight-configuration-readiness-20261013.json').open('x') as f:json.dump({'exitCode':r.returncode,'native':output,'stderr':r.stderr,'sourceHead':json.loads((P/'selected-installation-preparation-api-20261013.json').read_text())['head'],'currentDatabaseWrites':False},f,indent=2)
 print(json.dumps(output));assert r.returncode==0
