"""One-shot isolated restored identity probe; never source database control."""
import importlib.util
import json
import hashlib
import os
from pathlib import Path
import secrets
import subprocess

ROOT=Path('/Users/ddt/work/projects/ai_agent/aos-platform')
s=importlib.util.spec_from_file_location('restore',ROOT/'scripts/a0v_current_150_restore_gate.py')
r=importlib.util.module_from_spec(s);s.loader.exec_module(r)
c='current150-same-77f8f834ea15'
issuer='aos_provider_capacity_issuer'
base=ROOT.parent/'aos-recovery/current150-w5cb4-current150-restore-gate-20261005-154201'
phase=base/'native-scram-phase-20261006-0715-r2'
hba='/var/lib/postgresql/data/pg_hba.conf'
passfile='/tmp/current150-native-scram-20261006-0715-r2'

def command(args,data=None):
    return subprocess.run(['docker','--context',r.DEST_CONTEXT,'exec',*(['-i'] if data is not None else []),c,*args],input=data,capture_output=True,timeout=30)

def checked(args,data=None):
    value=command(args,data)
    if value.returncode:raise RuntimeError('isolated command failed; secret output withheld')
    return value.stdout

def admin(sql):
    return checked(['psql','-U','aos_app','-d',r.SOURCE,'-Atq','-v','ON_ERROR_STOP=1','-f','-'],sql.encode())

def write_file(path,data):
    checked(['sh','-c','umask 077; cat > "$1"','probe',path],data)

def native(sql):
    return command(['env','PGPASSFILE='+passfile,'psql','-w','-h','127.0.0.1','-U',issuer,'-d',r.SOURCE,'-Atq','-v','ON_ERROR_STOP=1','-f','-'],sql.encode())

revision=r.read_task()
item=json.loads(subprocess.check_output(['docker','--context',r.DEST_CONTEXT,'inspect',c]))[0]
intent=json.loads((base/'same-image-phase/intent.json').read_text())
r.require_target(item,container=c,image=intent['image'])
r.require_private_parent(base)
r.require(admin("SELECT rolcanlogin::text||'|'||(rolpassword IS NULL)::text FROM pg_authid WHERE rolname='"+issuer+"'").strip()==b'false|true','ORIGINAL_ROLE_DRIFT')
r.require(admin("SELECT has_database_privilege('aos_provider_capacity_issuer',current_database(),'CONNECT')").strip()==b'f','CONNECT_BASELINE_DRIFT')
original=checked(['cat',hba])
mode=checked(['stat','-c','%a',hba]).strip().decode()
r.require(mode in {'600','640','644'},'HBA_MODE_DRIFT')
r.require(command(['test','-e',passfile]).returncode==1,'PASSFILE_ALREADY_EXISTS')
phase.mkdir(mode=0o700) # Existing phase forbids replay.
g=r.load('g',ROOT/'scripts/a0v_current_142_restore_gate.py')
g.save(phase/'intent.json',{'authority':revision,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'container':c,'hba_sha256':hashlib.sha256(original).hexdigest(),'original_mode':mode})
fd=os.open(phase/'original-hba',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'wb') as f:f.write(original)
result={'outcome':'FAILED','authority':revision,'container':c}
try:
    write_file(hba,('host '+r.SOURCE+' '+issuer+' 127.0.0.1/32 scram-sha-256\n').encode()+original)
    checked(['chmod',mode,hba])
    r.require(admin('SELECT pg_reload_conf()').strip()==b't','HBA_RELOAD_FAILED')
    r.require(admin("SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL").strip()==b'0','HBA_PARSE_ERROR')
    admin('GRANT CONNECT ON DATABASE '+r.SOURCE+' TO '+issuer+';')
    password=secrets.token_hex(32)
    admin("SET password_encryption='scram-sha-256'; ALTER ROLE "+issuer+" LOGIN PASSWORD '"+password+"';")
    write_file(passfile,('127.0.0.1:5432:'+r.SOURCE+':'+issuer+':wrong-'+secrets.token_hex(8)+'\n').encode())
    bad=native('SELECT session_user;')
    r.require(bad.returncode!=0 and b'password authentication failed' in bad.stderr,'WRONG_PASSWORD_NOT_REJECTED')
    result['wrong_password_rejected']=True
    write_file(passfile,('127.0.0.1:5432:'+r.SOURCE+':'+issuer+':'+password+'\n').encode())
    sql="BEGIN READ ONLY; SET LOCAL aos.org_id='org-org'; SET LOCAL aos.project_id='dev-project'; SELECT json_build_object('session_user',session_user,'current_user',current_user,'database',current_database(),'positive_memberships',(SELECT count(*) FROM public.meta_membership)); SET LOCAL aos.org_id='dev-org'; SELECT json_build_object('canary_memberships',(SELECT count(*) FROM public.meta_membership)); COMMIT;"
    good=native(sql)
    if good.returncode: g.save(phase/'native-read-error.json',{'returncode':good.returncode,'stderr':good.stderr.decode()})
    r.require(good.returncode==0,'NATIVE_READ_FAILED')
    records=[json.loads(line) for line in good.stdout.decode().splitlines() if line.startswith('{')]
    r.require(len(records)==2 and records[0]['session_user']==issuer and records[0]['current_user']==issuer and records[0]['database']==r.SOURCE,'NATIVE_IDENTITY_DRIFT')
    r.require(records[0]['positive_memberships']>0 and records[1]['canary_memberships']==0,'NATIVE_RLS_FAILED_OR_EMPTY')
    result.update(outcome='NATIVE_SCRAM_READ_GREEN_CLEANUP_PENDING',wrong_password_rejected=True,observations=records)
finally:
    admin('ALTER ROLE '+issuer+' NOLOGIN PASSWORD NULL; REVOKE CONNECT ON DATABASE '+r.SOURCE+' FROM '+issuer+';')
    write_file(hba,original)
    checked(['chmod',mode,hba])
    r.require(admin('SELECT pg_reload_conf()').strip()==b't','RESTORE_RELOAD_FAILED')
    checked(['rm','-f',passfile])
    r.require(checked(['cat',hba])==original,'ORIGINAL_HBA_NOT_RESTORED')
    r.require(admin("SELECT rolcanlogin::text||'|'||(rolpassword IS NULL)::text FROM pg_authid WHERE rolname='"+issuer+"'").strip()==b'false|true','ORIGINAL_ROLE_NOT_RESTORED')
    result['cleanup']='original HBA bytes and role restored; private passfile removed'
    g.save(phase/'terminal.json',result)

def query(statement):
    return json.loads(admin("BEGIN READ ONLY; SET LOCAL timezone='UTC'; SET LOCAL search_path=pg_catalog,public; "+statement+'; COMMIT;'))
old=json.loads((base/'rehearsal-a150/after.json').read_text())
r.require_exact_restore(old,r.full_snapshot(g,query,old['role_names']))
result.update(outcome='NATIVE_SCRAM_READ_AND_RESTORE_GREEN',full_snapshot_unchanged=True,complete_formal_issuance='pending',source_migration_restart='pending')
g.save(phase/'verification.json',result)
(ROOT/'.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/current150-heartbeat-20261005-154201/native-scram-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
