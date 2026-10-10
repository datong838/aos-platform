"""Validate collected maintenance observations; never execute or grant business authority."""
import importlib.util,re,sys
from datetime import datetime,timezone
from pathlib import Path
THREAD='01a107a2-e9e4-7670-bc44-1144fa9b27e2'
OWNER='codex-'+THREAD
TASK='current159-maintenance-20261010'
SOURCE_ID='9cc6091c304b55f637987f1fb7ffff57d64cc5020e65f2912a18969df99e9cde'
VOLUME='aos-a0v-recovery-pg-data'
CLUSTER='7683855731447750695'
DATABASE='aos_current_preview_20260927'
SERVICES=('api','web','host','worker','provider')
BINDINGS=('thread','owner','task_id','authority_revision','head','source_id','volume','cluster','database','version','image','code_archive_sha256','first_rehearsal_sha256')
ROOT=Path(__file__).resolve().parents[2]

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
original=load('original142_zero_window159',ROOT/'scripts/a0v_current_142_maintenance.py')
memory=load('original_scope_overlap159',ROOT/'scripts/memory/memoryctl.py')

class Window159Rejected(RuntimeError):pass

def require(value,reason):
 if not value:raise Window159Rejected(reason)

def require_zero_window(expected,observed,*,task,leases,now,delivered):
 """Inputs must come from independently collected exact state, never caller permission DTOs.

 Successful predicate evaluation is not a backup, migration, runtime or execution permit.
 The executor separately freezes proof files, journals each side effect, and collects
 the actual database/process state before every operation.
 """
 require(type(expected) is dict and type(observed) is dict,'OBSERVATION_REQUIRED')
 for field in BINDINGS:
  require(type(expected.get(field)) is str and expected[field] and observed.get(field)==expected[field],'BINDING_DRIFT:'+field)
 for field,value in [('thread',THREAD),('owner',OWNER),('task_id',TASK),('source_id',SOURCE_ID),('volume',VOLUME),('cluster',CLUSTER),('database',DATABASE),('version','a0v_157')]:
  require(expected[field]==value,'FIXED_CURRENT_SCOPE_REQUIRED:'+field)
 require(re.fullmatch(r'AOS-[0-9]{6}',expected['authority_revision']) is not None,'AUTHORITY_REQUIRED')
 require(re.fullmatch(r'[0-9a-f]{40}',expected['head']) is not None,'COMMIT_REQUIRED')
 require(re.fullmatch(r'sha256:[0-9a-f]{64}',expected['image']) is not None,'IMAGE_REQUIRED')
 for field in ('code_archive_sha256','first_rehearsal_sha256'):
  require(re.fullmatch(r'[0-9a-f]{64}',expected[field]) is not None,'EXACT_PROOF_HASH_REQUIRED')
 require(type(task) is dict and type(leases) is list and delivered is False,'ORIGINAL_TASK_REQUIRED')
 require(task.get('task_id')==TASK and task.get('owner')==OWNER and task.get('status')=='ACTIVE','ORIGINAL_OWNER_REQUIRED')
 require(all(type(x) is dict and type(x.get('scope')) is list for x in leases),'LEASE_DOCUMENT_REQUIRED')
 require([x for x in leases if x.get('task_id')==TASK]==[task],'EXACT_UNIQUE_LEASE_REQUIRED')
 require(not any(memory.scopes_overlap(task.get('scope',[]),x['scope']) for x in leases if x.get('task_id')!=TASK),'UNRESOLVED_OVERLAPPING_LEASE')
 require(type(now) is datetime and now.tzinfo is not None and now.utcoffset() is not None,'AWARE_DATABASE_OBSERVATION_TIME_REQUIRED')
 try:expires=datetime.fromisoformat(task['lease_expires_at'])
 except (KeyError,ValueError,TypeError):raise Window159Rejected('LEASE_EXPIRY_REQUIRED') from None
 require(expires.tzinfo is not None and expires.utcoffset() is not None and expires>now,'LIVE_LEASE_REQUIRED')
 base=task.get('base_revision');require(type(base) is str and re.fullmatch(r'AOS-[0-9]{6}',base) is not None and base<=expected['authority_revision'],'ORIGINAL_BASE_REQUIRED')
 target='aos-platform/maintenance/current-preview-database'
 require(type(task.get('scope')) is list and target in task['scope'],'EXACT_MAINTENANCE_SCOPE_REQUIRED')
 require(type(task.get('excluded_scope')) is list and not memory.scopes_overlap([target],task['excluded_scope']),'EXCLUDED_SCOPE')
 require(observed.get('unknown_external') is False,'UNKNOWN_RECONCILE_ONLY')
 services=observed.get('services');require(type(services) is dict and set(services)==set(SERVICES) and all(services[k] is False for k in SERVICES),'EXECUTION_SERVICE_NOT_OFF')
 require(type(observed.get('listen_addresses')) is str,'LISTEN_OBSERVATION_REQUIRED')
 for field in ('tcp_exit','other_clients','prepared'):
  require(type(observed.get(field)) is int and observed[field]>=0,'NATIVE_INTEGER_REQUIRED:'+field)
 try:original.require_window(listen_addresses=observed['listen_addresses'],tcp_exit=observed['tcp_exit'],other_clients=observed['other_clients'],prepared=observed['prepared'])
 except original.MaintenanceBlocked as exc:raise Window159Rejected(str(exc)) from exc
