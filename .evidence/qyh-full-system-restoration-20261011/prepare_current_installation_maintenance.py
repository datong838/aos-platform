"""Readonly exact source reconciliation and protected candidate preparation; no execute."""
from pathlib import Path
import runpy,json,os,sys,hashlib,subprocess,importlib.util
from datetime import datetime,timezone
from psycopg.conninfo import conninfo_to_dict,make_conninfo
P=Path(__file__).resolve().parent;ROOT=P.parents[1];OUT=P/'current-original-installation-maintenance-20261013'
s=importlib.util.spec_from_file_location('mc',ROOT/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
sys.path.insert(0,str(ROOT/'scripts'));import a0v_qyh_restored_http as entry
if __name__=='__main__':
 assert m.load_authority()['project_revision']=='AOS-002004'
 lease=next(x for x in m.load_leases(m.DEFAULT_PATHS)['leases'] if x['task_id']==P.name)
 assert lease['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and datetime.fromisoformat(lease['lease_expires_at'])>datetime.now(timezone.utc)
 source=entry.require_api_source_candidate(P/'selected-installation-preparation-api-20261013.json')
 lab=P.parent/'qyh-installation-preparation-full-restore-20261013';b=runpy.run_path(str(lab/'restore.py'),run_name='current_readonly_preparation')['b'];before=json.loads((lab/'source-before.json').read_text())
 assert json.loads((lab/'consumption-r8.json').read_text())['status']=='CONSUMED_MATERIAL_REVIEW'
 fingerprints=b.fingerprint(b.SOURCE,'aos_meta_head');metadata=b.metadata(b.SOURCE,'aos_meta_head');assert fingerprints==before['fingerprints'] and metadata==before['metadata']
 native=entry.select_current_installation(identity_file=(P/'private/restored-identity.json').resolve(),installation_id='ab2fd72f-d81c-400d-bbbc-e1589a159d6b',bundle_root=(P/'selected-public-bundles').resolve(),trust_roots_file=(P/'restoration-public-trust-roots.json').resolve())
 current=json.loads(runpy.run_path(str(P/'current_installation_operation_audit.py'),run_name='current_native')['c'].read(runpy.run_path(str(P/'current_installation_operation_audit.py'),run_name='current_query')['QUERY']))
 assert current['installation']['state']=='approved' and current['installation']['etag_version']==3 and current['operations']==[] and current['currentHumanMembership']==[{'role':'admin'}]
 assert len(current['decisions'])==1 and current['decisions'][0]['actor']=='human:conversation-owner:01a107a2-e9e4-7670-bc44-1144fa9b27e2'
 creds_path=(P/'private/current-runtime-host-identities-20261013.json').resolve();creds=json.loads(creds_path.read_text());params=conninfo_to_dict(creds['runtime']['dsn']);assert params['dbname']=='aos_meta_head' and params['host']=='127.0.0.1' and params['port']=='18446';params.pop('password',None)
 assert not OUT.exists(),'existing maintenance evidence: reconcile only'
 OUT.mkdir();private=OUT/'private';private.mkdir(mode=0o700)
 with (OUT/'source-before.json').open('x') as f:json.dump({'fingerprints':fingerprints,'metadata':metadata,'nativeInstallation':current,'originalSignedPreflight':native},f,indent=2)
 passfile=private/'runtime.pgpass'
 with os.fdopen(os.open(passfile,os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600),'w') as f:f.write('127.0.0.1:18446:aos_meta_head:'+creds['runtime']['role']+':'+creds['runtime']['password']+'\n')
 env={k:v for k,v in os.environ.items() if not k.startswith(('AOS_','PG')) and k not in ('PYTHONPATH','PYTHONHOME')}
 env.update({'AOS_DOTENV_DISABLED':'1','PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(source/'services/aos-api'),'AOS_DATABASE_URL':make_conninfo(**params),'PGPASSFILE':str(passfile.resolve()),'AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE':str(creds_path),'AOS_CURRENT_RESTORED_API_IDENTITY_FILE':str((P/'private/restored-identity.json').resolve()),'AOS_CURRENT_RESTORED_INSTALLATION_ID':'ab2fd72f-d81c-400d-bbbc-e1589a159d6b','AOS_BUNDLE_ROOT':str((P/'selected-public-bundles').resolve()),'AOS_BUNDLE_TRUST_ROOTS_FILE':str((P/'restoration-public-trust-roots.json').resolve()),'AOS_EXTENSION_RUNTIME_HOST_ENABLED':'1','AOS_EXTENSION_RUNTIME_PREPARATION_ONLY':'1','AOS_EXTENSION_RUNTIME_CONFIGURATION_STAGE_ENABLED':'0','AOS_EXTENSION_RUNTIME_UI_READ_ENABLED':'0','AOS_EXTENSION_OCI_CONTEXT':'colima-aos-extension','AOS_EXTENSION_RUNTIME_PLATFORM':'linux/arm64','QYH_CURRENT_EVIDENCE_DIRECTORY':str(OUT.resolve())})
 # Only paths and password-free DSN. Keep all launch state private for exact reuse.
 with os.fdopen(os.open(private/'launch.json',os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600),'w') as f:json.dump({'env':env,'source':str(source),'candidateScript':str((P/'current_original_installation_preparation.py').resolve()),'candidateSHA256':hashlib.sha256((P/'current_original_installation_preparation.py').read_bytes()).hexdigest()},f,indent=2)
 with (OUT/'prepared.json').open('x') as f:json.dump({'sourceHead':'b514011bd244305c85d48ac4b92860f5b0303b50','authority':'AOS-002004','source650AndMetadataMatchFreshCompleteBackupBaseline':True,'originalIndependentRestoreAndReviewsAccepted':True,'currentInstallationApproved3':True,'currentNoOperations':True,'currentHumanMembershipAdmin':True,'originalHumanChatApprovalRecorded':True,'fullHostEnabled':False,'providerEnabled':False,'businessWorkersEnabled':False,'sourceDBWrites':False,'budgetChanged':False,'mutationExecuted':False,'scriptSHA256':hashlib.sha256((P/'current_original_installation_preparation.py').read_bytes()).hexdigest()},f,indent=2)
 print('CURRENT_INSTALLATION_MAINTENANCE_READONLY_PREPARED_NO_EXECUTION')
