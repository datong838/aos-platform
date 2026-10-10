import copy,hashlib,importlib.util,json,os
from pathlib import Path
import pytest
s=importlib.util.spec_from_file_location('web_restore_test',Path(__file__).with_name('registered_web_restore159.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

@pytest.fixture
def resources(tmp_path,monkeypatch):
 monkeypatch.setattr(Path,'home',classmethod(lambda cls:tmp_path));p=tmp_path/'Library/LaunchAgents'/ (m.m.WEB+'.plist');p.parent.mkdir(parents=True);p.write_bytes(b'original-frozen-web-plist')
 journal=tmp_path/'journal';journal.mkdir(mode=0o700)
 child=dict(pid=701,ppid=700,uid=os.getuid(),started='old-helper',argv_sha256='c'*64)
 d=dict(label=m.m.WEB,port=8434,plist_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),registered=True,pid=700,last_exit_status=0,listener_pids=['700'],argv_sha256='b'*64,cwd='/repo/apps/web',fingerprint=dict(pid=700,ppid=1,uid=os.getuid(),started='old-start',argv_sha256='b'*64,cwd='/repo/apps/web',children=[child],listener_ports=[8434]))
 proof=dict(label=m.m.WEB,candidate_sha256=hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest(),returncode=0,verified_stopped=True)
 before=dict(label=m.m.WEB,registered=False,listener_pids=[],old_processes_gone=True)
 after=copy.deepcopy(d);after.update(pid=702,listener_pids=['702']);after['fingerprint'].update(pid=702,started='new-start');after['fingerprint']['children'][0].update(pid=703,ppid=702,started='new-helper')
 return d,p,proof,before,journal,after

def invoke(r,calls,terminal=None):
 d,p,proof,before,journal,after=r
 def run(command):
  assert (journal/'restart_clients-attempt.json').is_file();calls.append(command)
  if isinstance(terminal,Exception):raise terminal
  return {'returncode':0} if terminal is None else terminal
 return m.restore_web(d,plist_path=p,stop_proof=proof,before=before,journal=journal,runner=run,observe_after=lambda:after)

def test_exact_web_restoration_and_no_second_bootstrap(resources):
 calls=[];result=invoke(resources,calls)
 assert result['verified_restored'] and calls==[['launchctl','bootstrap','gui/'+str(os.getuid()),str(resources[1])]]
 with pytest.raises(m.m.RegisteredLaunchRejected):invoke(resources,calls)
 assert len(calls)==1

@pytest.mark.parametrize('drift',['api','stop-hash','stop-nonzero','stop-unverified','registered','listener','process-alive','plist','symlink'])
def test_precondition_drift_has_no_command(resources,drift):
 d,p,proof,before,journal,after=resources
 if drift=='api':d['label']=m.m.API
 if drift=='stop-hash':proof['candidate_sha256']='d'*64
 if drift=='stop-nonzero':proof['returncode']=1
 if drift=='stop-unverified':proof['verified_stopped']=False
 if drift=='registered':before['registered']=True
 if drift=='listener':before['listener_pids']=['700']
 if drift=='process-alive':before['old_processes_gone']=False
 if drift=='plist':p.write_bytes(b'changed')
 if drift=='symlink':old=p.with_suffix('.saved');p.rename(old);p.symlink_to(old)
 calls=[]
 with pytest.raises(m.m.RegisteredLaunchRejected):invoke(resources,calls)
 assert not calls and not list(journal.iterdir())

@pytest.mark.parametrize('drift',['old-pid','executor-pid','start','uid','argv','port','registered','helper-pid','helper-ppid','helper-argv','helper-start','extra-child','helper-descendant'])
def test_bad_native_readback_never_done_or_retry(resources,drift):
 after=resources[-1];fp=after['fingerprint'];child=fp['children'][0]
 if drift=='old-pid':after['pid']=700
 if drift=='executor-pid':after['pid']=os.getpid()
 if drift=='start':fp['started']='old-start'
 if drift=='uid':fp['uid']=-1
 if drift=='argv':after['argv_sha256']=fp['argv_sha256']='d'*64
 if drift=='port':fp['listener_ports']=[8080]
 if drift=='registered':after['registered']=False
 if drift=='helper-pid':child['pid']=701
 if drift=='helper-ppid':child['ppid']=700
 if drift=='helper-argv':child['argv_sha256']='d'*64
 if drift=='helper-start':child['started']='old-helper'
 if drift=='extra-child':fp['children'].append(copy.deepcopy(child))
 if drift=='helper-descendant':child['children']=[{'pid':704}]
 calls=[]
 with pytest.raises(m.m.RegisteredLaunchRejected):invoke(resources,calls)
 assert len(calls)==1 and not (resources[4]/'restart_clients-done.json').exists()
 with pytest.raises(m.m.RegisteredLaunchRejected):invoke(resources,calls)
 assert len(calls)==1

@pytest.mark.parametrize('terminal',[{'returncode':1},{'returncode':True},{},TimeoutError('unknown')])
def test_failed_unknown_terminal_never_done_or_retry(resources,terminal):
 calls=[]
 with pytest.raises(m.m.RegisteredLaunchRejected):invoke(resources,calls,terminal)
 assert len(calls)==1 and (resources[4]/'restart_clients-terminal.json').exists() and not (resources[4]/'restart_clients-done.json').exists()
 with pytest.raises(m.m.RegisteredLaunchRejected):invoke(resources,calls)
 assert len(calls)==1
