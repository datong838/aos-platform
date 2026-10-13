"""One bounded READ ONLY 650-table snapshot; never backup/restore or restart."""
from pathlib import Path
import importlib.util,sys,json,hashlib,subprocess,argparse,re,time
R=Path(__file__).resolve().parents[2];P=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);a=parser.parse_args();assert re.fullmatch('[a-z][a-z0-9-]{0,60}',a.label)
output=P/(a.label+'.json');intent=P/(a.label+'-intent.json');assert not output.exists() and not intent.exists(),'existing snapshot: readonly reconcile, no replay'
spec=importlib.util.spec_from_file_location('original_readonly_fingerprint',R/'.evidence/qyh-host-oid-durable-full-restore-20261013/rehearse.py');fp=importlib.util.module_from_spec(spec);spec.loader.exec_module(fp)
container=json.loads(fp.docker('inspect',fp.SOURCE,capture_output=True,text=True).stdout)[0]
assert container['Id']==fp.CID and container['State']['Running'] and len(container['Mounts'])==1 and container['Mounts'][0]['Name']=='aos-qyh-history159-prepared-data-20261011'
assert container['NetworkSettings']['Ports']['5432/tcp']==[{'HostIp':'127.0.0.1','HostPort':'18446'}]
native=json.loads(fp.sql(fp.SOURCE,'aos_meta_head',"BEGIN READ ONLY;SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'schema',(SELECT version_num FROM alembic_version),'enabledBindings',(SELECT count(*) FROM extension_runtime_binding WHERE enabled),'otherActiveClients',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND backend_type='client backend' AND state='active'));ROLLBACK;"))
assert native['cluster']=='7695302940039200809' and native['schema']=='a0v_161' and native['enabledBindings']==0
intent.write_text(json.dumps({'label':a.label,'containerId':container['Id'],'volume':container['Mounts'][0]['Name'],'readonly':True,'serialQueries':650,'unknownOutcomeNoResend':True},indent=2)+'\n')
t=time.monotonic();fingerprints=fp.fingerprint(fp.SOURCE,'aos_meta_head');assert len(fingerprints)==650
report={'label':a.label,'native':native,'containerId':container['Id'],'volume':container['Mounts'][0]['Name'],'pgStartedAt':container['State']['StartedAt'],'fingerprints':fingerprints,'elapsedSeconds':round(time.monotonic()-t,3),'dbWrites':False,'scriptSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'originalFingerprintFunctionSourceSha256':hashlib.sha256((R/'.evidence/qyh-host-oid-durable-full-restore-20261013/rehearse.py').read_bytes()).hexdigest()}
output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['label','native','volume','pgStartedAt','elapsedSeconds','dbWrites']}))
