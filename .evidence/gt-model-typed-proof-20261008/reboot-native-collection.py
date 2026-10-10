"""All original native nodes, fresh retained isolated DB per node, sequential."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
E=Path(__file__).resolve().parent;R=E.parents[1];label=sys.argv[1]
assert label in ('reboot-native-r3','reboot-native-r4','reboot-native-r5','reboot-native-r6')
J=E/label;J.mkdir(mode=0o700)
nodes=json.loads((E/'reboot-native-r1/terminal.json').read_text())['collected'];assert len(nodes)==len(set(nodes))==34
source=json.loads((E/'reboot-native-r1/attempt.json').read_text())['source_hashes']
paths=[R/f for f in source]+[Path(__file__),E/'reboot-native-review.py'];frozen={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
def save(name,value):
 with os.fdopen(os.open(J/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as out:json.dump(value,out,indent=2);out.flush();os.fsync(out.fileno())
save('attempt.json',{'at':datetime.now(timezone.utc).isoformat(),'nodes':nodes,'source_hashes':frozen,'unknown_replay_allowed':False,'formal_database_writes':0})
results=[]
if label=='reboot-native-r4':
 for i,node in enumerate(nodes[:21],1):
  child='reboot-native-r3-n'+str(i).zfill(2)
  attempt=json.loads((E/child/'attempt.json').read_text())
  terminal=json.loads((E/child/'terminal.json').read_text())
  assert all(attempt['source_hashes'][f]==frozen[f] for f in source)
  assert terminal['exit']==0 and terminal['results']==[{'nodeid':node,'phase':'call','outcome':'passed'}]
  results.append({'node':node,'child':child,'process_exit':0,'terminal':terminal,'consumed_known_result':True})
 save('prior-known-results.json',results)
for i,node in enumerate(nodes,1):
 if label=='reboot-native-r4' and i<=21:continue
 if label in ('reboot-native-r4','reboot-native-r6'):
  lab=json.loads((E/'reboot-lab.json').read_text())
  available=int(subprocess.check_output(['docker','--context',lab['context'],'exec',lab['name'],'df','-k','/dev/shm'],text=True).splitlines()[-1].split()[3])*1024
  assert available>33554432, 'shared memory launch floor'
 assert all(hashlib.sha256((R/f).read_bytes()).hexdigest()==h for f,h in frozen.items())
 child=label+'-n'+str(i).zfill(2)
 with os.fdopen(os.open(J/(child+'.local.log'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as out:
  proc=subprocess.Popen([sys.executable,str(E/'reboot-native-review.py'),child,node],cwd=R,stdout=out,stderr=subprocess.STDOUT)
  save(child+'-handle.json',{'pid':proc.pid,'node':node,'argv':[str(E/'reboot-native-review.py'),child,node]})
  code=proc.wait()
 terminal=E/child/'terminal.json';r=json.loads(terminal.read_text()) if terminal.exists() else None
 result={'node':node,'child':child,'process_exit':code,'terminal':r};results.append(result);save(child+'-observed.json',result)
 print(json.dumps({'completed':i,'total':len(nodes),'process_exit':code,'passed':r is not None and r['exit']==0 and r['results']==[{'nodeid':node,'phase':'call','outcome':'passed'}]}),flush=True)
 if code!=0 or r is None or r['exit']!=0:break
passed=len(results)==34 and all(r['process_exit']==0 and r['terminal']['results']==[{'nodeid':r['node'],'phase':'call','outcome':'passed'}] for r in results)
save('terminal.json',{'at':datetime.now(timezone.utc).isoformat(),'all_34_passed':passed,'results':results,'source_hashes':frozen,'formal_database_writes':0,'root_trust_proven':False,'execution_allowed':False,'full_task_delivery':False});raise SystemExit(0 if passed else 1)
