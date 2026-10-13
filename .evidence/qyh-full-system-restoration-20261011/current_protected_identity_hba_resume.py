"""Continue only the proved-unexecuted active HBA step; never resets passwords."""
from pathlib import Path
import importlib.util,json,hashlib,sys,os,stat
from datetime import datetime,timezone
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('c',P/'current_protected_identities.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
OUT=c.OUT;REVIEW=c.REVIEW;HBA='/etc/qyh_pg_hba.conf'

def main():
 assert c.mc.load_authority()['project_revision']=='AOS-002001'
 lease=next(x for x in c.mc.load_leases(c.mc.DEFAULT_PATHS)['leases'] if x['task_id']=='qyh-full-system-restoration-20261011')
 assert lease['owner']==c.r.OWNER and datetime.fromisoformat(lease['lease_expires_at'])>datetime.now(timezone.utc)
 source=json.loads(c.r.docker('inspect',c.r.SOURCE,text=True,capture_output=True).stdout)[0]
 assert source['Id']==c.r.CID and source['Image']==c.r.IMAGE and source['State']['Running']
 assert len(source['Mounts'])==1 and source['Mounts'][0]['Name']=='aos-qyh-history159-prepared-data-20261011'
 assert source['NetworkSettings']['Ports']['5432/tcp']==[{'HostIp':'127.0.0.1','HostPort':'18446'}]
 assert c.read('SHOW hba_file;').strip()==HBA and not(OUT/'hba-execute-intent.json').exists()
 con=json.loads((REVIEW/'resume-consumption-r4.json').read_text());assert con['status']=='CONSUMED_MATERIAL_REVIEW' and con['execution_authorized'] is False
 for path,digest in con['baseline']['files'].items():assert hashlib.sha256((c.ROOT/path).read_bytes()).hexdigest()==digest
 assert (REVIEW/'resume-material-1.txt').read_text()==Path(__file__).read_text()
 rec=json.loads((OUT/'credential-phase-readonly-reconciliation.json').read_text());assert rec['passwordTransactionCompleted'] and rec['hbaNeverModified']
 assert not c.CREDENTIAL.is_symlink() and stat.S_IMODE(c.CREDENTIAL.stat().st_mode)==0o600
 assert hashlib.sha256(c.CREDENTIAL.read_bytes()).hexdigest()==json.loads((OUT/'private/credential-intent.json').read_text())['credentialFileSHA256']
 prior=json.loads((OUT/'private/actual-hba-before.json').read_text());assert prior==json.loads((OUT/'private/actual-hba-before.second.json').read_text())
 old=c.r.docker('exec',c.r.SOURCE,'cat',HBA,text=True,capture_output=True).stdout
 owner=c.r.docker('exec',c.r.SOURCE,'stat','-c','%u:%g:%a',HBA,text=True,capture_output=True).stdout.strip()
 assert old==prior['text'] and owner==prior['ownershipMode'] and hashlib.sha256(old.encode()).hexdigest()==rec['actualHbaSHA256']
 native=json.loads(c.read("SELECT json_build_object('schema',(SELECT version_num FROM alembic_version),'cluster',(SELECT system_identifier::text FROM pg_control_system()),'enabled',(SELECT count(*) FROM extension_runtime_binding WHERE enabled),'otherSessions',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()),'credentialRoles',(SELECT count(*) FROM pg_authid WHERE rolname IN ('aos_a0v_directory_20260912','aos_a0v_runtime_20260912','aos_a0v_web_20260912') AND rolpassword IS NOT NULL));"));assert native=={'schema':'a0v_161','cluster':'7695302940039200809','enabled':0,'otherSessions':0,'credentialRoles':3}
 prepared=json.loads((OUT/'prepared.json').read_text());assert c.r.fingerprint(c.r.SOURCE,'aos_meta_head')==prepared['before'] and c.r.metadata(c.r.SOURCE,'aos_meta_head')==prepared['metadata']
 lines=old.splitlines(keepends=True);positions=[i for i,line in enumerate(lines) if line.split()==['host','all','all','0.0.0.0/0','reject']];assert len(positions)==1
 rule='host aos_meta_head '+','.join(c.ROLES.values())+' 0.0.0.0/0 scram-sha-256\n';new=''.join(lines[:positions[0]]+[rule]+lines[positions[0]:])
 c.record('hba-execute-intent.json',{'activePath':HBA,'beforeSHA256':rec['actualHbaSHA256'],'afterSHA256':hashlib.sha256(new.encode()).hexdigest(),'ownershipModePreserved':owner,'newRules':1,'existingRulesExactPreserved':True,'passwordTransactionNotRepeated':True})
 uid,gid,mode=owner.split(':');assert uid.isdigit() and gid.isdigit() and mode.isdigit()
 script='umask 077; set -C; cat > /etc/qyh_pg_hba.qyh-20261013-new; chown '+uid+':'+gid+' /etc/qyh_pg_hba.qyh-20261013-new; chmod '+mode+' /etc/qyh_pg_hba.qyh-20261013-new; mv /etc/qyh_pg_hba.qyh-20261013-new /etc/qyh_pg_hba.conf'
 c.r.docker('exec','--user','0:0','-i',c.r.SOURCE,'sh','-ec',script,input=new,text=True,capture_output=True)
 assert c.r.sql(c.r.SOURCE,'aos_meta_head','SELECT pg_reload_conf();').strip()=='t'
 assert c.r.docker('exec',c.r.SOURCE,'cat',HBA,text=True,capture_output=True).stdout==new
 rules=json.loads(c.read("SELECT json_agg(row_to_json(x)) FROM (SELECT type,database,user_name,address,auth_method,error FROM pg_hba_file_rules WHERE type LIKE 'host%')x;"));assert all(x['error'] is None for x in rules)
 c.record('hba-verified.json',{'rules':rules,'existingRulesPreserved':True,'noProcessRestart':True})
 dsns,generation=c._runtime_file_dsns(c.CREDENTIAL,with_generation=True);credentials=json.loads(c.CREDENTIAL.read_text());ids={}
 for plane,dsn in dsns.items():
  try:
   with c.psycopg.connect(dsn,row_factory=c.dict_row,connect_timeout=5) as conn:conn.read_only=True;ids[plane]=c.probe_runtime_database_identity(conn,protected_relations=c._PROTECTED_RELATIONS)
  except Exception:raise RuntimeError('CURRENT_SCRAM_PROBE_FAILED_RECONCILE_ONLY') from None
 c.require_isolated_runtime_identities(**ids);assert all(x.authority[2]=='aos_meta_head' for x in ids.values())
 for plane,x in credentials.items():
  bad=c.make_conninfo(host='127.0.0.1',port='18446',dbname='aos_meta_head',user=x['role'],password='KnownWrongNegativeCredential',application_name='qyh-negative-'+plane)
  try:
   with c.psycopg.connect(bad,connect_timeout=5):pass
  except c.psycopg.OperationalError:pass
  else:raise AssertionError('wrong password unexpectedly authenticated')
 assert c.r.fingerprint(c.r.SOURCE,'aos_meta_head')==prepared['before'] and c.r.metadata(c.r.SOURCE,'aos_meta_head')==prepared['metadata']
 assert c.read('SELECT count(*) FROM extension_runtime_binding WHERE enabled;').strip()=='0'
 after_source=json.loads(c.r.docker('inspect',c.r.SOURCE,text=True,capture_output=True).stdout)[0];assert after_source['State']['StartedAt']==source['State']['StartedAt']
 c.record('verification.json',{'outcome':'CURRENT_THREE_PLANE_NATIVE_SCRAM_ORIGINAL_IDENTITY_GATES_GREEN','nativeIdentities':{p:{'sessionUser':v.session_user,'roleOid':v.role_oid,'authority':list(v.authority),'directoryMember':v.directory_member,'runtimeMember':v.runtime_member,'privileged':v.privileged,'ownsProtectedRelation':v.owns_protected_relation} for p,v in ids.items()},'credentialReference':str(c.CREDENTIAL),'credentialFileGeneration':generation,'correctSCRAMLogins':3,'wrongPasswordsRejected':3,'source650TablesUnchanged':True,'schemaRoleFlagsMembershipSequencesUnchanged':True,'onlyExistingThreeRoleCredentialsChanged':True,'sourceVolumeAndProcessUnchanged':True,'hostActivated':False,'eightWorkbenchesAccepted':False,'secretsPrinted':False,'passwordTransactionReplayed':False})
 print('CURRENT_THREE_PLANE_NATIVE_SCRAM_ORIGINAL_IDENTITY_GATES_GREEN')
if __name__=='__main__':
 try:main()
 except Exception as e:print('CURRENT_HBA_CONTINUATION_FAILED_RECONCILE_ONLY:'+type(e).__name__);sys.exit(1)
