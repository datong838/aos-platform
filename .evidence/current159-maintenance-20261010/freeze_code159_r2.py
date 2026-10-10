"""Freeze exact committed migration code into one new isolated code volume."""
import sys,json,subprocess,hashlib,tarfile,io,os,secrets
from pathlib import Path
from datetime import datetime,timezone
import importlib.util
E=Path(__file__).resolve().parent;R=E.parents[1];CTX='colima-aos-extension';HEAD='c95ad824bd6640f41edb6d5fd762b76f33d16b63';TOOL='sha256:982fd540f5eb90d3b936bea1aa084b70a72470b5d2bd024964455c3cf45e3e25'
s=importlib.util.spec_from_file_location('mfreeze159',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==HEAD and m.load_authority()['project_revision']=='AOS-001705'
t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks/current159-maintenance-20261010.json').read_text());assert t['status']=='ACTIVE' and t['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc) and [z for z in m.load_leases(m.DEFAULT_PATHS)['leases'] if z['task_id']==t['task_id']]==[t]
archive=subprocess.check_output(['git','archive',HEAD,'services/aos-api/aos_api','services/aos-api/alembic','services/aos-api/alembic.ini'],cwd=R)
manifest={}
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
 for member in tar.getmembers():
  assert not member.name.startswith('/') and '..' not in Path(member.name).parts and (member.isfile() or member.isdir())
  if member.isfile():
   content=tar.extractfile(member).read();blob=subprocess.check_output(['git','show',HEAD+':'+member.name],cwd=R);assert content==blob;manifest[member.name]=hashlib.sha256(content).hexdigest()
volume='current159-code-'+secrets.token_hex(6);J=R.parent/'aos-recovery'/volume;J.mkdir(mode=0o700)
def save(n,v):
 with os.fdopen(os.open(J/n,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as out:json.dump(v,out,indent=2,sort_keys=True);out.flush();os.fsync(out.fileno())
save('intent.json',{'head':HEAD,'volume':volume,'tool':TOOL,'archive_sha256':hashlib.sha256(archive).hexdigest(),'manifest':manifest,'task':t['task_id'],'uncommitted_code_excluded':True})
args=['docker','--context',CTX,'run','-i','--pull','never','--name',volume+'-init','--network','none','--cap-drop','ALL','--security-opt','no-new-privileges','--mount','type=volume,source='+volume+',target=/code','--entrypoint','tar',TOOL,'-xf','-','-C','/code']
p=subprocess.run(args,input=archive,capture_output=True,timeout=60);save('init-terminal.json',{'exit':p.returncode,'stderr':p.stderr.decode(errors='replace')});assert p.returncode==0
program="import pathlib,json,hashlib; p=pathlib.Path('/code'); print(json.dumps({str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob('*') if f.is_file()},sort_keys=True))"
args=['docker','--context',CTX,'run','--pull','never','--name',volume+'-verify','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--mount','type=volume,source='+volume+',target=/code,readonly',TOOL,'python','-c',program]
p=subprocess.run(args,capture_output=True,timeout=30);save('verify-terminal.json',{'exit':p.returncode,'stderr':p.stderr.decode(errors='replace')});assert p.returncode==0 and json.loads(p.stdout)==manifest
report={'status':'EXACT_COMMITTED_CODE_VOLUME_VERIFIED','head':HEAD,'volume':volume,'files':len(manifest),'archive_sha256':hashlib.sha256(archive).hexdigest(),'manifest_sha256':hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),'tool':TOOL,'state':str(J),'uncommitted_code_excluded':True}
save('result.json',report);(E/'committed-code159-r2.json').open('x').write(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
