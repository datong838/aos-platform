"""Exact stopped Web restoration helper; internal maintenance only, never API start."""
import hashlib,importlib.util,json,os,sys
from pathlib import Path
s=importlib.util.spec_from_file_location('restore_registered159',Path(__file__).with_name('registered_launch159.py'));m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)

def require(v,why):m.require(v,why)

def restore_web(expected,*,plist_path,stop_proof,before,journal,runner,observe_after):
 """Caller must freshly bind Task/HEAD/authority/source; no authority from these DTOs."""
 require(expected.get('label')==m.WEB,'WEB_ONLY')
 m.require_candidate(expected,expected)
 canonical=hashlib.sha256(json.dumps(expected,sort_keys=True).encode()).hexdigest()
 require(type(stop_proof) is dict and stop_proof.get('candidate_sha256')==canonical and stop_proof.get('returncode')==0 and type(stop_proof.get('returncode')) is int and stop_proof.get('verified_stopped') is True and stop_proof.get('label')==m.WEB,'ORIGINAL_VERIFIED_STOP_REQUIRED')
 require(type(before) is dict and before.get('label')==m.WEB and before.get('registered') is False and before.get('listener_pids')==[] and before.get('old_processes_gone') is True,'CURRENT_STOPPED_STATE_REQUIRED')
 path=Path(plist_path);fixed=Path.home()/'Library/LaunchAgents'/ (m.WEB+'.plist')
 require(path==fixed and path.is_file() and not path.is_symlink() and path.stat().st_uid==os.getuid(),'ORIGINAL_PLIST_PATH_REQUIRED')
 require(hashlib.sha256(path.read_bytes()).hexdigest()==expected['plist_sha256'],'ORIGINAL_PLIST_HASH_REQUIRED')
 journal=Path(journal);require(journal.is_dir() and not journal.is_symlink() and journal.stat().st_uid==os.getuid() and journal.stat().st_mode&0o077==0,'PRIVATE_JOURNAL_REQUIRED')
 command=['launchctl','bootstrap','gui/'+str(os.getuid()),str(path)]
 try:m.original.record_attempt(journal,'restart_clients',{'step':'restart_clients','label':m.WEB,'command':command,'candidate_sha256':canonical})
 except m.original.MaintenanceBlocked as exc:raise m.RegisteredLaunchRejected('EXISTING_ATTEMPT_RECONCILE_ONLY') from exc
 try:terminal=runner(command)
 except Exception as exc:
  m.write_record(journal,'restart_clients-terminal.json',{'status':'UNKNOWN_EXTERNAL','error_type':type(exc).__name__,'reconcile_only':True});raise m.RegisteredLaunchRejected('UNKNOWN_EXTERNAL_RECONCILE_ONLY') from exc
 if type(terminal) is not dict or type(terminal.get('returncode')) is not int:
  m.write_record(journal,'restart_clients-terminal.json',{'status':'UNKNOWN_EXTERNAL','error_type':'MalformedTerminal','reconcile_only':True});raise m.RegisteredLaunchRejected('TERMINAL_UNKNOWN_RECONCILE_ONLY')
 m.write_record(journal,'restart_clients-terminal.json',{'returncode':terminal['returncode'],'reconcile_only':terminal['returncode']!=0})
 require(terminal['returncode']==0,'BOOTSTRAP_FAILED_RECONCILE_ONLY')
 try:after=observe_after()
 except Exception as exc:raise m.RegisteredLaunchRejected('READBACK_UNKNOWN_RECONCILE_ONLY') from exc
 require(type(after) is dict and type(after.get('pid')) is int and after['pid'] not in (expected['pid'],os.getpid()),'NEW_PROCESS_ID_REQUIRED')
 updated=dict(expected,pid=after['pid'],last_exit_status=after.get('last_exit_status'),listener_pids=[str(after['pid'])],fingerprint=after.get('fingerprint'))
 m.require_candidate(updated,after)
 fp=after['fingerprint'];old=expected['fingerprint']
 require(fp.get('ppid')==old['ppid'] and fp.get('listener_ports')==[8434] and type(fp.get('started')) is str and fp['started'] and fp['started']!=old['started'],'NEW_PROCESS_START_REQUIRED')
 children=fp.get('children');old_children=old['children']
 require(type(children) is list and len(children)==len(old_children)==1,'EXACT_HELPER_REQUIRED')
 c=children[0];oc=old_children[0]
 require(type(c) is dict and type(oc) is dict and set(c)==set(oc)=={'pid','ppid','uid','started','argv_sha256'},'EXACT_HELPER_FINGERPRINT_SCHEMA_REQUIRED')
 require(type(c) is dict and type(c.get('pid')) is int and c['pid']>1 and c['pid'] not in (oc['pid'],after['pid'],os.getpid()) and c.get('ppid')==after['pid'] and c.get('uid')==os.getuid() and c.get('argv_sha256')==oc['argv_sha256'] and type(c.get('started')) is str and c['started'] and c['started']!=oc['started'],'NEW_EXACT_HELPER_REQUIRED')
 result={'label':m.WEB,'verified_restored':True,'new_pid':after['pid'],'business_execution_authorized':False,'api_bootstrap_used':False}
 m.write_record(journal,'restart_clients-done.json',result);return result
