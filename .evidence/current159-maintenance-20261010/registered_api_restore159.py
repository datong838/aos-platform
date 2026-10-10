"""Exact registered API source replacement/start; internal whole-maintenance use only."""
import hashlib,importlib.util,json,math,os,plistlib,secrets,sys,time
from pathlib import Path
E=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('api_restore_registered159',E/'registered_launch159.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
API=m.API;ROOT='/Users/ddt/work/projects/ai_agent/aos-platform'
SOURCE_STATE='/Users/ddt/work/projects/ai_agent/aos-recovery/api159-source-132b92e20d26'
ENTRY_PATH=Path(SOURCE_STATE)/'api159-registered-entry.py'
INTERPRETER=ROOT+'/services/aos-api/.venv/bin/python'
SIGNED='/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json'
OLD_SHA='0ed893602c8fc5626672c87414788919a489df9e49ebfc083e22132a40535861'
SOURCE='9cc6091c304b55f637987f1fb7ffff57d64cc5020e65f2912a18969df99e9cde'
CLUSTER='7683855731447750695';DB='aos_current_preview_20260927';VOLUME='aos-a0v-recovery-pg-data'
ORIGINAL_CANDIDATE_SHA=hashlib.sha256(json.dumps(json.loads((E/'current-window159-service-candidates.json').read_text())[API],sort_keys=True).encode()).hexdigest()

def require(v,reason):
 if not v:raise ValueError(reason)
def sha(raw):return hashlib.sha256(raw).hexdigest()

def make_plan(original,source,runtime):
 require(type(original) is bytes and sha(original)==OLD_SHA,'ORIGINAL_PLIST_BYTES_REQUIRED')
 require(type(source) is dict and source.get('state')==SOURCE_STATE and source.get('status')=='COMMITTED_STARTUP_SOURCE_MATERIALIZED'
  and source.get('files')==5604 and source.get('migration_files')==2487,'EXACT_SOURCE_RESOURCE_REQUIRED')
 require(type(runtime) is dict and runtime.get('status')=='COMMITTED_API_REAL_APPLICATION_IMPORT_GREEN'
  and runtime.get('all_api_modules_from_export') is True and runtime.get('server_started') is False
  and runtime.get('lifespan_executed') is False and runtime.get('source_manifest_sha256')==source['manifest_sha256']
  and runtime.get('signed_crypto_exact') is True and runtime.get('source_exact_after_import') is True
  and runtime.get('formal157_full_snapshot_equal_before_after_and_original_protocol') is True
  and runtime.get('signed_root')==str(Path(SIGNED).parent/'signing-state/signed-bundles'),'REAL_EXPORTED_IMPORT_REQUIRED')
 require(runtime.get('interpreter')==INTERPRETER and runtime.get('interpreter_realpath')==str(Path(INTERPRETER).resolve())
  and runtime.get('interpreter_sha256')==sha(Path(INTERPRETER).read_bytes()),'ORIGINAL_INTERPRETER_DRIFT')
 cfg=plistlib.loads(original)
 require(cfg['Label']==API and cfg['ProgramArguments']==[INTERPRETER,ROOT+'/scripts/a0v_current_preview_http.py','--signed-receipt',SIGNED,'--serve']
  and cfg['WorkingDirectory']==ROOT and cfg['RunAtLoad'] is True and cfg['KeepAlive'] is True,'ORIGINAL_API_PROFILE_DRIFT')
 cfg['WorkingDirectory']=SOURCE_STATE+'/source';cfg['ProgramArguments'][1]=SOURCE_STATE+'/api159-registered-entry.py'
 cfg['EnvironmentVariables']={**cfg['EnvironmentVariables'],'PYTHONDONTWRITEBYTECODE':'1'}
 cfg['KeepAlive']=False
 raw=plistlib.dumps(cfg,fmt=plistlib.FMT_XML,sort_keys=True)
 return {'schema':'aos-current-api159-restoration-plan/v1','label':API,'port':8080,'original_plist_sha256':OLD_SHA,
  'source_state':SOURCE_STATE,'source_manifest_sha256':source['manifest_sha256'],'interpreter_sha256':runtime['interpreter_sha256'],
  'startup_guard_sha256':sha((E/'api159_registered_entrypoint.py').read_bytes()),
  'argv_sha256':sha(json.dumps(cfg['ProgramArguments'],separators=(',',':')).encode()),'cwd':cfg['WorkingDirectory'],
  'plist_sha256':sha(raw),'plist_hex':raw.hex(),'business_runtime_authorized':False,'startup_attempted':False}

def require_entry(plan):
 path=ENTRY_PATH
 require(path.is_file() and not path.is_symlink() and path.resolve()==path and path.stat().st_uid==os.getuid() and path.stat().st_mode&0o077==0,'PRIVATE_FROZEN_ENTRY_REQUIRED')
 require(sha(path.read_bytes())==plan['startup_guard_sha256'],'FROZEN_STARTUP_ENTRY_DRIFT')

def require_window(window):
 require(type(window) is dict and all(window.get(k)==v for k,v in {'source_id':SOURCE,'cluster':CLUSTER,'database':DB,'version':'a0v_159','volume':VOLUME}.items()),'CURRENT_NATIVE159_REQUIRED')
 require(all(window.get(k) is True for k in ('original_configuration_source_restored','complete_migrated_catalogues_equal','source_original158159_commit_verified'))
  and window.get('unknown_external') is False,'VERIFIED_CURRENT_MAINTENANCE_REQUIRED')

def require_after(plan,after,*,not_before):
 require(type(after) is dict and after.get('label')==API and after.get('registered') is True and type(after.get('pid')) is int
  and after['pid']>1 and after['pid']!=os.getpid() and after.get('listener_pids')==[str(after['pid'])]
  and after.get('plist_sha256')==plan['plist_sha256'],'NEW_EXACT_API_PROCESS_REQUIRED')
 fp=after.get('fingerprint')
 require(type(fp) is dict and set(fp)=={'pid','ppid','uid','started','argv_sha256','cwd','children','listener_ports'},'EXACT_API_FINGERPRINT_REQUIRED')
 require(fp['pid']==after['pid'] and type(fp['ppid']) is int and fp['ppid']==1 and type(fp['uid']) is int and fp['uid']==os.getuid()
  and type(fp['started']) is str and bool(fp['started']) and fp['argv_sha256']==plan['argv_sha256'] and fp['cwd']==plan['cwd']
  and fp['children']==[] and fp['listener_ports']==[8080],'API_PROCESS_IDENTITY_DRIFT')
 try:started=time.mktime(time.strptime(fp['started'],'%a %b %d %H:%M:%S %Y'))
 except (ValueError,OverflowError):raise ValueError('NATIVE_PROCESS_START_REQUIRED') from None
 require(math.floor(not_before)<=started<=time.time(),'API_NOT_STARTED_BY_THIS_ATTEMPT')

def restore_api(plan,*,stop_proof,before,window,journal,guard,runner,observe_after):
 """Caller guard validates fresh native Task/HEAD/source/DB; DTOs confer no authority.

 Caller separately verifies signed health, denial, tenant and browser acceptance.
 Both effects are durable exclusive attempts; no replay or compensating restart.
 """
 require_window(window)
 require(type(stop_proof) is dict and stop_proof.get('label')==API and stop_proof.get('candidate_sha256')==ORIGINAL_CANDIDATE_SHA
  and type(stop_proof.get('returncode')) is int and stop_proof['returncode']==0 and stop_proof.get('verified_stopped') is True,'ORIGINAL_API_STOP_REQUIRED')
 require(type(before) is dict and before.get('label')==API and before.get('registered') is False
  and before.get('listener_pids')==[] and before.get('old_processes_gone') is True,'API_STILL_RUNNING_OR_UNKNOWN')
 journal=Path(journal);require(journal.is_dir() and not journal.is_symlink() and journal.stat().st_uid==os.getuid() and journal.stat().st_mode&0o077==0,'PRIVATE_JOURNAL_REQUIRED')
 path=Path.home()/'Library/LaunchAgents'/(API+'.plist')
 require(path.is_file() and not path.is_symlink() and path.resolve()==path and path.stat().st_uid==os.getuid(),'ORIGINAL_REGISTERED_PLIST_PATH_REQUIRED')
 original=path.read_bytes();require(sha(original)==OLD_SHA,'ORIGINAL_PLIST_CHANGED')
 source=json.loads((E/'prepared-api159-source.json').read_text());runtime=json.loads((E/'prepared-api159-real-app-import.json').read_text())
 require(plan==make_plan(original,source,runtime),'RESTORATION_PLAN_CHANGED')
 guard();require_entry(plan)
 m.write_record(journal,'plist-replace-intent.json',{'path':str(path),'old_sha256':OLD_SHA,'new_sha256':plan['plist_sha256']})
 try:
  with os.fdopen(os.open(journal/'original-api.plist',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(original);f.flush();os.fsync(f.fileno())
  fd=os.open(journal,os.O_RDONLY)
  try:os.fsync(fd)
  finally:os.close(fd)
  raw=bytes.fromhex(plan['plist_hex']);tmp=path.with_name('.'+API+'.tmp-'+secrets.token_hex(6))
  with os.fdopen(os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  require(not path.is_symlink() and sha(path.read_bytes())==OLD_SHA,'PLIST_CAS_DRIFT')
  os.replace(tmp,path)
  fd=os.open(path.parent,os.O_RDONLY)
  try:os.fsync(fd)
  finally:os.close(fd)
  require(sha(path.read_bytes())==plan['plist_sha256'],'REPLACEMENT_READBACK_FAILED')
 except Exception as exc:
  m.write_record(journal,'plist-replace-terminal.json',{'status':'UNKNOWN_EXTERNAL','error_type':type(exc).__name__,'reconcile_only':True});raise
 m.write_record(journal,'plist-replace-terminal.json',{'status':'REPLACED_EXACT','old_backup_sha256':sha((journal/'original-api.plist').read_bytes()),'new_sha256':sha(path.read_bytes())})
 guard();require_entry(plan)
 require(not path.is_symlink() and sha(path.read_bytes())==plan['plist_sha256'],'PLIST_CHANGED_BEFORE_BOOTSTRAP')
 command=['launchctl','bootstrap','gui/'+str(os.getuid()),str(path)]
 attempt_at=time.time()
 m.write_record(journal,'api-bootstrap-intent.json',{'command':command,'plan_sha256':sha(json.dumps(plan,sort_keys=True).encode()),'attempt_at':attempt_at})
 try:terminal=runner(command)
 except Exception as exc:
  m.write_record(journal,'api-bootstrap-terminal.json',{'status':'UNKNOWN_EXTERNAL','error_type':type(exc).__name__,'reconcile_only':True});raise ValueError('UNKNOWN_BOOTSTRAP_RECONCILE_ONLY') from exc
 if type(terminal) is not dict or type(terminal.get('returncode')) is not int:
  m.write_record(journal,'api-bootstrap-terminal.json',{'status':'UNKNOWN_EXTERNAL','reconcile_only':True});raise ValueError('MALFORMED_TERMINAL_RECONCILE_ONLY')
 m.write_record(journal,'api-bootstrap-terminal.json',{'returncode':terminal['returncode'],'reconcile_only':terminal['returncode']!=0})
 require(terminal['returncode']==0,'BOOTSTRAP_FAILED_RECONCILE_ONLY')
 try:after=observe_after();require_after(plan,after,not_before=attempt_at)
 except Exception as exc:
  m.write_record(journal,'api-bootstrap-post-terminal.json',{'status':'UNVERIFIED','error_type':type(exc).__name__,'reconcile_only':True});raise
 m.write_record(journal,'api-bootstrap-post-terminal.json',{'status':'VERIFIED','pid':after['pid'],'started':after['fingerprint']['started']})
 result={'label':API,'verified_restored':True,'new_pid':after['pid'],'current159_preview_only':True,'business_runtime_authorized':False,'browser_acceptance_pending':True}
 m.write_record(journal,'api-bootstrap-done.json',result);return result
