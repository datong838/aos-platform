"""Read-only fixed two-lab closed-role verification after native protocol."""
import ast,hashlib,importlib.util,json,os,secrets,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
E=Path(__file__).resolve().parent;R=E.parents[1]
s=importlib.util.spec_from_file_location('window_independent_guard159',E/'window159_native_rehearsal.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
result=json.loads((E/'window159-native-rehearsal-r1.json').read_text());assert result['status']=='ISOLATED_FULL_NATIVE_WINDOW159_PROTOCOL_GREEN'
J=Path(result['state'])/'independent-readonly-r1';J.mkdir(mode=0o700)
def save(name,data):
 with os.fdopen(os.open(J/name,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600),'w') as out:json.dump(data,out,indent=2,sort_keys=True);out.flush();os.fsync(out.fileno())
 fd=os.open(J,os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)
mem=m.load('window_independent_memory159',R/'scripts/memory/memoryctl.py')
assert mem.load_authority()['project_revision']=='AOS-001709'
t=mem.read_json(mem.DEFAULT_PATHS.receipts_path/'tasks'/ (m.TASK+'.json'));assert t['owner']==m.OWNER and t['status']=='ACTIVE' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc) and [x for x in mem.load_leases(mem.DEFAULT_PATHS)['leases'] if x['task_id']==m.TASK]==[t]
old_tree=ast.parse((E/'first-native-rehearsal159-r2-independent.py').read_text());literal=next(n.value for n in old_tree.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='program' for x in n.targets));program=ast.literal_eval(literal)
ids=['0a78aab54c880c1b7a17d965f4c10f58d81779f0c732ec4ba3ffb56df0fcb2c4','0d43faad9ecb351b7584d27ad099b05f9bb198d2991401a22480a4cee5975fdd'];proofs=[]
for i,pg in enumerate((result['source_lab'],result['independent_restore'])):
 x=json.loads(subprocess.check_output(['docker','--context',m.CTX,'inspect',pg],timeout=20))[0];image=json.loads((Path(result['state'])/'manifest.json').read_text())['image'];m.require_lab(x,pg,image);assert x['Id']==ids[i]
 body=program.replace('7694901228328955942',result['lab_clusters'][i]);args=['docker','--context',m.CTX,'run','-i','--pull','never','--name','window159-closed-readonly-'+secrets.token_hex(6),'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--cpus','1','--mount','type=bind,source='+x['GraphDriver']['Data']['MergedDir']+'/var/run/postgresql,target=/pgsocket,readonly',json.loads((E/'committed-code159-r3.json').read_text())['tool'],'python','-']
 save(str(i)+'-intent.json',{'args':args,'program_sha256':hashlib.sha256(body.encode()).hexdigest(),'read_only':True,'cluster':result['lab_clusters'][i]})
 try:p=subprocess.run(args,input=body.encode(),capture_output=True,timeout=120)
 except Exception as exc:save(str(i)+'-terminal.json',{'status':'UNKNOWN_EXTERNAL','error_type':type(exc).__name__});raise
 save(str(i)+'-terminal.json',{'exit':p.returncode,'stderr':p.stderr.decode(errors='replace')});assert p.returncode==0
 proof=json.loads(p.stdout);assert proof['cluster']==result['lab_clusters'][i] and proof['read_only'] is True;proofs.append(proof);save(str(i)+'-proof.json',proof)
report={'status':'BOTH_NATIVE_LABS_CLOSED_ROLE_INDEPENDENT_READBACK_GREEN','labs':proofs,'native_protocol_sha256':hashlib.sha256((E/'window159-native-rehearsal-r1.json').read_bytes()).hexdigest(),'formal_database_writes':0,'current_second_zero_window_backup_pending':True,'business_execution_authorized':False,'goal_complete':False}
save('result.json',report);(E/'window159-native-independent-readback.json').open('x').write(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
