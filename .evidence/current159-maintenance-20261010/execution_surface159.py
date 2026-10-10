"""Current local preview execution inventory; no global fleet or business permit."""
import hashlib, importlib.util, json, os, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

SOURCE='9cc6091c304b55f637987f1fb7ffff57d64cc5020e65f2912a18969df99e9cde'
CLUSTER='7683855731447750695'; DB='aos_current_preview_20260927'
COUNTS=('runtime_bindings','host_assignments','enabled_host_identities','enabled_meta_schedules','host_leases')
THREAD='01a107a2-e9e4-7670-bc44-1144fa9b27e2'; TASK='current159-maintenance-20261010'
ENDPOINTS={'default':'unix:///var/run/docker.sock','desktop-linux':'unix:///Users/ddt/.docker/run/docker.sock',
 'colima-aos-a0v-test-only':'unix:///Users/ddt/.colima/aos-a0v-test-only/docker.sock',
 'colima-aos-extension':'unix:///Users/ddt/.colima/aos-extension/docker.sock'}
IMAGES={'sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd',
 'sha256:bcdf34e61bae2345234063d6fa3dd31dbd89b9dd97d9a669b59edc0f1212d883'}
COMMANDS=(['postgres'],['postgres','-c','shared_buffers=16MB','-c','max_connections=30'])

def require(v,reason):
 if not v:raise ValueError(reason)

class SurfaceRejected(ValueError):
 def __init__(self,reason,observations):
  super().__init__(reason);self.observations=observations

def require_current_surface(v,*,now):
 require(type(v) is dict and v.get('scope')=='CURRENT_PREVIEW_LOCAL_EXECUTION_SURFACE_ONLY','CURRENT_LOCAL_SCOPE_REQUIRED')
 require((v.get('source_id'),v.get('cluster'),v.get('database'))==(SOURCE,CLUSTER,DB),'CURRENT_DATABASE_IDENTITY_DRIFT')
 binding=v.get('binding');require(type(binding) is dict and set(binding)=={'thread','owner','task_id','authority_revision','head'}
  and binding['thread']==THREAD and binding['owner']=='codex-'+THREAD and binding['task_id']==TASK
  and type(binding['head']) is str and re.fullmatch('[0-9a-f]{40}',binding['head']) is not None
  and type(binding['authority_revision']) is str and re.fullmatch('AOS-[0-9]{6}',binding['authority_revision']) is not None,'NATIVE_TASK_HEAD_BINDING_REQUIRED')
 require(type(now) is datetime and now.tzinfo is not None,'AWARE_CURRENT_TIME_REQUIRED')
 try:at=datetime.fromisoformat(v['at']);age=(now-at).total_seconds()
 except (KeyError,TypeError,ValueError):raise ValueError('NATIVE_OBSERVATION_TIME_REQUIRED') from None
 require(0<=age<=30,'STALE_EXECUTION_SURFACE')
 counts=v.get('counts');require(type(counts) is dict and set(counts)==set(COUNTS)
  and all(type(counts[k]) is int and counts[k]==0 for k in COUNTS),'CURRENT_EXECUTION_CONFIGURATION_NOT_EMPTY')
 require(v.get('process_inventory_utf8_strict') is True and type(v.get('process_inventory_sha256')) is str
  and re.fullmatch('[0-9a-f]{64}',v['process_inventory_sha256']) is not None
  and v.get('forbidden_runtime_pids')==[],'CURRENT_RUNTIME_PROCESS_UNRESOLVED')
 require(v.get('legacy_api_label_absent') is True and v.get('host_label_absent') is True,'UNCONTROLLED_REGISTERED_RUNTIME')
 require(v.get('global_fleet_off_proven') is False and v.get('business_runtime_authorized') is False,'SCOPE_OR_PERMISSION_EXPANSION')
 contexts=v.get('contexts');require(type(contexts) is dict and set(contexts)==set(ENDPOINTS),'DOCKER_CONTEXT_INVENTORY_INCOMPLETE')
 ids=[];source_count=0
 for name,endpoint in ENDPOINTS.items():
  row=contexts[name];require(type(row) is dict and row.get('endpoint')==endpoint,'DOCKER_ENDPOINT_DRIFT')
  if name=='default':require(row.get('state')=='SOCKET_ABSENT' and row.get('socket_exists') is False,'DEFAULT_ENGINE_UNRESOLVED');continue
  if name=='colima-aos-a0v-test-only':
   require(row.get('state')=='STOPPED_COLIMA' and row.get('socket_exists') is False and row.get('colima_status')=='Stopped','STOPPED_ENGINE_NOT_PROVEN');continue
  require(row.get('state')=='RUNNING' and type(row.get('containers')) is list,'LIVE_ENGINE_INVENTORY_REQUIRED')
  for item in row['containers']:
   require(type(item) is dict and type(item.get('id')) is str and re.fullmatch('[0-9a-f]{64}',item['id']) is not None,'EXACT_CONTAINER_ID_REQUIRED')
   ids.append(item['id'])
   require(item.get('image') in IMAGES and item.get('cmd') in COMMANDS and item.get('entrypoint')==['docker-entrypoint.sh'],'RUNNING_NON_POSTGRES_OR_UNKNOWN_COMMAND')
   if item['id']==SOURCE:
    source_count+=1;require(name=='colima-aos-extension' and item['cmd']==['postgres'],'CURRENT_SOURCE_ENGINE_DRIFT')
 require(len(ids)==len(set(ids)) and source_count==1,'CURRENT_SOURCE_MISSING_OR_DUPLICATE')

def collect():
 """Native read-only collector; caller must separately guard live Task/HEAD/authority."""
 root=Path(__file__).resolve().parents[2]
 def run(args):return subprocess.run(args,capture_output=True,timeout=20)
 def checked(args):
  r=run(args);require(r.returncode==0,'READONLY_COMMAND_FAILED:'+args[0]);return r.stdout.decode('utf8',errors='strict')
 authority_path=root.parent/'docs/palantier/AOS项目开发上下文/memory/authority.json'
 binding={'thread':THREAD,'owner':'codex-'+THREAD,'task_id':TASK,
  'authority_revision':json.loads(authority_path.read_text())['project_revision'],'head':checked(['git','-C',str(root),'rev-parse','HEAD']).strip()}
 contexts=json.loads(checked(['docker','context','inspect',*ENDPOINTS]))
 require({r['Name']:r['Endpoints']['docker']['Host'] for r in contexts}==ENDPOINTS,'EXACT_CONTEXT_ENDPOINTS_REQUIRED')
 require(set(checked(['docker','context','ls','--format','{{.Name}}']).splitlines())==set(ENDPOINTS),'NEW_CONTEXT_REQUIRES_REVIEW')
 colima=[json.loads(x) for x in checked(['colima','list','--json']).splitlines()]
 statuses={x['name']:x['status'] for x in colima}
 require(statuses.get('aos-a0v-test-only')=='Stopped' and statuses.get('aos-extension')=='Running','COLIMA_CURRENT_TOPOLOGY_DRIFT')
 engines={}
 for name,endpoint in ENDPOINTS.items():
  exists=os.path.lexists(endpoint.removeprefix('unix://'))
  if name=='default':engines[name]={'endpoint':endpoint,'state':'SOCKET_ABSENT','socket_exists':exists};continue
  if name=='colima-aos-a0v-test-only':engines[name]={'endpoint':endpoint,'state':'STOPPED_COLIMA','socket_exists':exists,'colima_status':statuses['aos-a0v-test-only']};continue
  ids=checked(['docker','--context',name,'ps','-q','--no-trunc']).splitlines()
  items=[]
  for ident in ids:
   fmt='{"id":{{json .Id}},"image":{{json .Image}},"cmd":{{json .Config.Cmd}},"entrypoint":{{json .Config.Entrypoint}}}'
   items.append(json.loads(checked(['docker','--context',name,'inspect','--format',fmt,ident])))
  engines[name]={'endpoint':endpoint,'state':'RUNNING','containers':items}
 raw=run(['ps','-axo','pid=,ppid=,args=']);require(raw.returncode==0,'FULL_PROCESS_INVENTORY_FAILED');text=raw.stdout.decode('utf8',errors='strict')
 allowed={os.getpid(),os.getppid()};forbidden=[]
 targets=('aos_api','a0v_ecommerce_runtime_host.py','a0v_current_preview_http.py','services/aos-api','aos-recovery/api159-source-')
 for line in text.splitlines():
  fields=line.strip().split(None,2);require(len(fields)==3 and fields[0].isdigit() and fields[1].isdigit(),'MALFORMED_PROCESS_INVENTORY')
  if int(fields[0]) not in allowed and any(x in fields[2] for x in targets):forbidden.append(int(fields[0]))
 absent={}
 for label in ('com.aos.a0v-api-8080','com.aos.a0v-w5c3-runtime-host'):
  r=run(['launchctl','list',label]);absent[label]=(r.returncode==113 and r.stderr.decode('utf8',errors='strict')==f'Could not find service "{label}" in domain for port\n')
 spec=importlib.util.spec_from_file_location('surface_boot159',root/'scripts/a0v_current_preview_bootstrap.py');boot=importlib.util.module_from_spec(spec);spec.loader.exec_module(boot)
 import psycopg
 with psycopg.connect(**boot._connection_parameters()) as conn:
  conn.read_only=True;conn.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ
  require(conn.info.dbname==DB,'CURRENT_DATABASE_TARGET_REQUIRED')
  cluster=conn.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]
  result=conn.execute('''SELECT (SELECT count(*) FROM extension_runtime_binding),
   (SELECT count(*) FROM extension_runtime_host_assignment),
   (SELECT count(*) FROM extension_runtime_host_identity WHERE enabled),
   (SELECT count(*) FROM meta_schedule WHERE enabled),
   (SELECT count(*) FROM extension_runtime_host_lease_a0v_093)''').fetchone();conn.rollback()
 value={'scope':'CURRENT_PREVIEW_LOCAL_EXECUTION_SURFACE_ONLY','source_id':SOURCE,'cluster':cluster,'database':DB,'at':datetime.now(timezone.utc).isoformat(),
  'binding':binding,
  'counts':dict(zip(COUNTS,result)),'process_inventory_utf8_strict':True,'process_inventory_sha256':hashlib.sha256(raw.stdout).hexdigest(),'forbidden_runtime_pids':forbidden,
  'legacy_api_label_absent':absent['com.aos.a0v-api-8080'],'host_label_absent':absent['com.aos.a0v-w5c3-runtime-host'],
  'global_fleet_off_proven':False,'business_runtime_authorized':False,'contexts':engines}
 require(binding['head']==checked(['git','-C',str(root),'rev-parse','HEAD']).strip() and binding['authority_revision']==json.loads(authority_path.read_text())['project_revision'],'OBSERVATION_HEAD_AUTHORITY_CHANGED')
 try:require_current_surface(value,now=datetime.now(timezone.utc))
 except ValueError as exc:raise SurfaceRejected(str(exc),value) from exc
 return value
