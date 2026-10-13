"""Execute only exact reviewed current installation candidate; no unknown replay."""
from pathlib import Path
import argparse,runpy,json,hashlib,subprocess,sys,importlib.util
from datetime import datetime,timezone
P=Path(__file__).resolve().parent;ROOT=P.parents[1];OUT=P/'current-original-installation-maintenance-20261013'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--review-round',choices=['r1','r2'],required=True);args=parser.parse_args();assert args.execute,'explicit reviewed execute required'
 s=importlib.util.spec_from_file_location('mc',ROOT/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
 assert m.load_authority()['project_revision']=='AOS-002004'
 lease=next(x for x in m.load_leases(m.DEFAULT_PATHS)['leases'] if x['task_id']==P.name)
 assert lease['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and datetime.fromisoformat(lease['lease_expires_at'])>datetime.now(timezone.utc)
 review=P.parent/'qyh-current-original-installation-maintenance-review-20261013';cons=json.loads((review/('consumption-'+args.review_round+'.json')).read_text());assert cons['status']=='CONSUMED_MATERIAL_REVIEW'
 request=json.loads((review/('request-'+args.review_round+'.json')).read_text());assert cons['request_id']==request['request_id'] and cons['baseline']==request['baseline']
 assert digest(P/'current_original_installation_preparation.py')==request['baseline']['files'][str(review/'material-1.txt')]
 private=json.loads((OUT/'private/launch.json').read_text());prepared=json.loads((OUT/'prepared.json').read_text());assert digest(Path(private['candidateScript']))==private['candidateSHA256']==prepared['scriptSHA256']
 assert not any((OUT/x).exists() for x in ['execution-intent.json','current-apply-intent.json','current-apply-receipt.json','current-preparation-failure.json']), 'attempt or unknown result exists: readonly reconciliation only'
 lab=P.parent/'qyh-installation-preparation-full-restore-20261013';b=runpy.run_path(str(lab/'restore.py'),run_name='source_preexecution_readonly')['b'];before=json.loads((OUT/'source-before.json').read_text())
 assert b.fingerprint(b.SOURCE,'aos_meta_head')==before['fingerprints'] and b.metadata(b.SOURCE,'aos_meta_head')==before['metadata']
 actor=runpy.run_path(str(P/'current_installation_operation_audit.py'),run_name='fresh_native');native=json.loads(actor['c'].read(actor['QUERY']))
 assert native['installation']['state']=='approved' and native['installation']['etag_version']==3 and native['operations']==[] and native['currentHumanMembership']==[{'role':'admin'}]
 with (OUT/'execution-intent.json').open('x') as f:json.dump({'authority':'AOS-002004','task':P.name,'thread':'01a107a2-e9e4-7670-bc44-1144fa9b27e2','owner':lease['owner'],'candidateSHA256':private['candidateSHA256'],'sourceBeforeSHA256':digest(OUT/'source-before.json'),'reviewConsumptionSHA256':digest(review/('consumption-'+args.review_round+'.json')),'actorIsDelegatedCanonicalHuman':True,'fullHostAuthorized':False,'runtimeEnableAuthorized':False,'sourceOrProviderAuthorized':False,'unknownResultRetryAuthorized':False},f,indent=2)
 # Native pipeline has durable per-operation receipt/intent journals. No automatic subprocess retry.
 result=subprocess.run([sys.executable,private['candidateScript']],cwd=private['source'],env=private['env'],timeout=180)
 with (OUT/'execution-process-result.json').open('x') as f:json.dump({'exitCode':result.returncode,'automaticRetry':False,'currentInstallationMaintenance':True,'systemRestarted':False,'eightPagesAccepted':False},f,indent=2)
 raise SystemExit(result.returncode)
