import hashlib,importlib.util,json,plistlib,re,shlex,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('registered_readback',E/'registered_launch159.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def run(args):return subprocess.run(args,capture_output=True,text=True,timeout=15)
def digest(args):return hashlib.sha256(json.dumps(args,separators=(',',':')).encode()).hexdigest()
expected=json.loads((E/'current-window159-service-candidates.json').read_text());results={}
for label in (m.API,m.WEB):
 old=expected[label];p=Path.home()/'Library/LaunchAgents'/ (label+'.plist');raw=p.read_bytes();plist=plistlib.loads(raw)
 assert plist['Label']==label
 launch=run(['launchctl','list',label]);assert launch.returncode==0
 pids=re.findall(r'^\s*"PID" = ([0-9]+);$',launch.stdout,re.M)
 exits=re.findall(r'^\s*"LastExitStatus" = (-?[0-9]+);$',launch.stdout,re.M)
 assert len(pids)<=1 and len(exits)==1
 pid=int(pids[0]) if pids else None
 listeners=run(['lsof','-nP','-iTCP:'+str(old['port']),'-sTCP:LISTEN','-t'])
 assert listeners.returncode in (0,1)
 observed=dict(label=label,port=old['port'],plist_sha256=hashlib.sha256(raw).hexdigest(),registered=True,pid=pid,last_exit_status=int(exits[0]),listener_pids=sorted(set(listeners.stdout.split())),argv_sha256=digest(plist['ProgramArguments']),cwd=plist['WorkingDirectory'])
 if label==m.WEB:
  children=old['fingerprint']['children'];assert len(children)==1
  child=run(['ps','-p',str(children[0]['pid']),'-o','args=']);assert child.returncode==0
  child_args=shlex.split(child.stdout);assert digest(child_args)==children[0]['argv_sha256']
  observed['fingerprint']=m.original.read_service_candidate(pid=pid,expected_argv=plist['ProgramArguments'],expected_cwd=plist['WorkingDirectory'],expected_port=old['port'],expected_child_argv=child_args)
 m.require_candidate(old,observed)
 results[label]=observed
print(json.dumps({'status':'EXACT_NATIVE_CANDIDATES_VERIFIED','services':results,'launchctl_mutations':0,'database_mutations':0,'zero_window_established':False,'business_execution_authorized':False},indent=2))
