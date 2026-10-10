"""Exact registered launchd maintenance stop; no bootstrap, PID kill or business permit."""
import hashlib,importlib.util,json,os,re,sys
from pathlib import Path
API='com.aos.a0v-api-daily0900';WEB='com.aos.a0v-web-8434'
PORTS={API:8080,WEB:8434}
ROOT=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('registered_original142',ROOT/'scripts/a0v_current_142_maintenance.py');original=importlib.util.module_from_spec(s);sys.modules[s.name]=original;s.loader.exec_module(original)
class RegisteredLaunchRejected(RuntimeError):pass

def require(value,reason):
 if not value:raise RegisteredLaunchRejected(reason)

def require_candidate(expected,observed):
 require(type(expected) is dict and type(observed) is dict,'EXACT_CANDIDATE_REQUIRED')
 label=expected.get('label');require(label in PORTS,'FIXED_LABEL_REQUIRED')
 require(type(expected.get('port')) is int and expected['port']==PORTS[label],'FIXED_PORT_REQUIRED')
 for key in ('label','port','plist_sha256','registered','pid','last_exit_status','listener_pids','argv_sha256','cwd'):
  require(key in expected and key in observed and expected[key]==observed[key],'SERVICE_CHANGED:'+key)
 require(expected['registered'] is True,'REGISTERED_JOB_REQUIRED')
 for key in ('plist_sha256','argv_sha256'):require(type(expected[key]) is str and re.fullmatch(r'[0-9a-f]{64}',expected[key]) is not None,'EXACT_SERVICE_HASH_REQUIRED')
 require(type(expected['cwd']) is str and expected['cwd'].startswith('/'),'EXACT_CWD_REQUIRED')
 require(type(expected['last_exit_status']) is int and type(expected['listener_pids']) is list,'EXACT_LAUNCH_STATE_REQUIRED')
 if label==API:
  require(expected['pid'] is None and expected['listener_pids']==[] and 'fingerprint' not in expected and 'fingerprint' not in observed,'API_ORIGINAL_ABSENCE_REQUIRED')
 else:
  require(type(expected['pid']) is int and expected['pid']>1 and expected['listener_pids']==[str(expected['pid'])],'WEB_UNIQUE_PID_REQUIRED')
  require(type(expected.get('fingerprint')) is dict and type(observed.get('fingerprint')) is dict,'NATIVE_PROCESS_FINGERPRINT_REQUIRED')
  require(expected['fingerprint'].get('uid')==os.getuid() and expected['fingerprint'].get('pid')==expected['pid'],'PROCESS_OWNER_REQUIRED')
  require(expected['fingerprint'].get('argv_sha256')==expected['argv_sha256'] and expected['fingerprint'].get('cwd')==expected['cwd'],'PROCESS_ARGUMENTS_REQUIRED')
  try:original.require_process(expected['fingerprint'],observed['fingerprint'],executor_pid=os.getpid())
  except (original.MaintenanceBlocked,KeyError,TypeError) as exc:raise RegisteredLaunchRejected('PROCESS_IDENTITY_DRIFT') from exc
 return ['launchctl','bootout','gui/'+str(os.getuid())+'/'+label]

def write_record(journal,name,value):
 path=journal/name
 with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600),'w') as f:
  json.dump(value,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 fd=os.open(journal,os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)

def stop_registered(expected,observed,*,journal,runner,observe_after):
 """Called only by the bound maintenance executor after fresh Task/source guards.

 One persisted attempt per label/subjournal. Unknown/nonzero/postcondition failure
 is terminal for this invocation and reconcile-only; never bootstrap or resend.
 Injected runner/observer support isolated verification, not caller business authority.
 """
 command=require_candidate(expected,observed);journal=Path(journal)
 require(journal.is_dir() and not journal.is_symlink() and journal.stat().st_uid==os.getuid() and journal.stat().st_mode&0o077==0,'PRIVATE_JOURNAL_REQUIRED')
 try:original.record_attempt(journal,'stop_clients',{'step':'stop_clients','label':expected['label'],'command':command,'candidate_sha256':hashlib.sha256(json.dumps(expected,sort_keys=True).encode()).hexdigest(),'candidate':expected})
 except original.MaintenanceBlocked as exc:raise RegisteredLaunchRejected('EXISTING_ATTEMPT_RECONCILE_ONLY') from exc
 try:terminal=runner(command)
 except Exception as exc:
  write_record(journal,'stop_clients-terminal.json',{'status':'UNKNOWN_EXTERNAL','error_type':type(exc).__name__,'reconcile_only':True})
  raise RegisteredLaunchRejected('UNKNOWN_EXTERNAL_RECONCILE_ONLY') from exc
 if type(terminal) is not dict or type(terminal.get('returncode')) is not int:
  write_record(journal,'stop_clients-terminal.json',{'status':'UNKNOWN_EXTERNAL','error_type':'MalformedTerminal','reconcile_only':True})
  raise RegisteredLaunchRejected('COMMAND_TERMINAL_UNKNOWN_RECONCILE_ONLY')
 write_record(journal,'stop_clients-terminal.json',{'returncode':terminal['returncode'],'reconcile_only':terminal['returncode']!=0})
 require(terminal['returncode']==0,'BOOTOUT_FAILED_RECONCILE_ONLY')
 try:after=observe_after()
 except Exception as exc:raise RegisteredLaunchRejected('POST_OBSERVATION_UNKNOWN_RECONCILE_ONLY') from exc
 require(type(after) is dict and after.get('label')==expected['label'] and after.get('registered') is False and after.get('listener_pids')==[] and after.get('old_processes_gone') is True,'STOP_POSTCONDITION_UNVERIFIED')
 result={'label':expected['label'],'verified_stopped':True,'process_kill_used':False,'bootstrap_used':False,'business_execution_authorized':False}
 write_record(journal,'stop_clients-done.json',result);return result
