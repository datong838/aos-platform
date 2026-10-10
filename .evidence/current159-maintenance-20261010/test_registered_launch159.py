import copy,importlib.util,os,json
from pathlib import Path
import pytest
p=Path(__file__).with_name('registered_launch159.py');s=importlib.util.spec_from_file_location('registered_launch159_test',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

@pytest.fixture(autouse=True)
def private_journal(tmp_path):tmp_path.chmod(0o700)

def service(label=m.API):
 web=label==m.WEB;pid=700 if web else None
 d=dict(label=label,port=8434 if web else 8080,plist_sha256='a'*64,registered=True,pid=pid,last_exit_status=0 if web else 512,listener_pids=[str(pid)] if web else [],argv_sha256='b'*64,cwd='/repo/apps/web' if web else '/repo')
 if web:d['fingerprint']=dict(pid=pid,ppid=1,uid=os.getuid(),started='fixed-start',argv_sha256='b'*64,cwd=d['cwd'],children=[],listener_ports=[8434])
 return d

def stopped(d):return dict(label=d['label'],registered=False,listener_pids=[],old_processes_gone=True)

@pytest.mark.parametrize('variant',['pid','plist','argv','cwd','exit','registered','listener','child','started','foreign-uid'])
def test_drift_never_reaches_bootout(tmp_path,variant):
 d=service(m.WEB);o=copy.deepcopy(d);calls=[]
 if variant=='pid':o['pid']=701
 if variant=='plist':o['plist_sha256']='c'*64
 if variant=='argv':o['argv_sha256']='c'*64
 if variant=='cwd':o['cwd']='/other'
 if variant=='exit':o['last_exit_status']=1
 if variant=='registered':o['registered']=False
 if variant=='listener':o['listener_pids']=['700','701']
 if variant=='child':o['fingerprint']['children']=[dict(pid=701)]
 if variant=='started':o['fingerprint']['started']='reused-pid'
 if variant=='foreign-uid':d['fingerprint']['uid']=0;o['fingerprint']['uid']=0
 with pytest.raises(m.RegisteredLaunchRejected):m.stop_registered(d,o,journal=tmp_path,runner=lambda command:calls.append(command),observe_after=lambda:stopped(d))
 assert not calls and not list(tmp_path.iterdir())

def test_one_exact_command_and_durable_terminal_no_replay(tmp_path):
 d=service();calls=[]
 def run(command):
  assert (tmp_path/'stop_clients-attempt.json').is_file();calls.append(command);return dict(returncode=0)
 result=m.stop_registered(d,copy.deepcopy(d),journal=tmp_path,runner=run,observe_after=lambda:stopped(d))
 assert calls==[['launchctl','bootout','gui/'+str(os.getuid())+'/'+m.API]] and result['verified_stopped']
 assert (tmp_path/'stop_clients-terminal.json').is_file() and (tmp_path/'stop_clients-done.json').is_file()
 with pytest.raises(m.RegisteredLaunchRejected):m.stop_registered(d,d,journal=tmp_path,runner=run,observe_after=lambda:stopped(d))
 assert len(calls)==1

@pytest.mark.parametrize('variant',['nonzero','timeout','post-registered','post-listener','old-process-live'])
def test_failure_is_reconcile_only(tmp_path,variant):
 d=service();calls=[]
 def run(command):
  calls.append(command)
  if variant=='timeout':raise TimeoutError('unknown')
  return dict(returncode=1 if variant=='nonzero' else 0)
 post=stopped(d)
 if variant=='post-registered':post['registered']=True
 if variant=='post-listener':post['listener_pids']=['700']
 if variant=='old-process-live':post['old_processes_gone']=False
 with pytest.raises(m.RegisteredLaunchRejected):m.stop_registered(d,d,journal=tmp_path,runner=run,observe_after=lambda:post)
 assert len(calls)==1 and not (tmp_path/'stop_clients-done.json').exists()
 with pytest.raises(m.RegisteredLaunchRejected):m.stop_registered(d,d,journal=tmp_path,runner=run,observe_after=lambda:stopped(d))
 assert len(calls)==1

@pytest.mark.parametrize('label',['com.aos.other','com.aos.a0v-w5c3-runtime-host','../other'])
def test_only_two_labels_allowed(tmp_path,label):
 d=service();d['label']=label;calls=[]
 with pytest.raises(m.RegisteredLaunchRejected):m.stop_registered(d,d,journal=tmp_path,runner=lambda command:calls.append(command),observe_after=lambda:stopped(d))
 assert not calls

@pytest.mark.parametrize('terminal',[None,{},dict(returncode=True),dict(returncode='0')])
def test_malformed_terminal_has_unknown_receipt_and_no_replay(tmp_path,terminal):
 d=service();calls=[]
 def run(command):calls.append(command);return terminal
 with pytest.raises(m.RegisteredLaunchRejected):m.stop_registered(d,d,journal=tmp_path,runner=run,observe_after=lambda:stopped(d))
 receipt=json.loads((tmp_path/'stop_clients-terminal.json').read_text())
 assert receipt['status']=='UNKNOWN_EXTERNAL' and receipt['reconcile_only'] is True
 with pytest.raises(m.RegisteredLaunchRejected):m.stop_registered(d,d,journal=tmp_path,runner=run,observe_after=lambda:stopped(d))
 assert len(calls)==1 and not (tmp_path/'stop_clients-done.json').exists()

def test_observer_exception_cannot_replay_known_command(tmp_path):
 d=service();calls=[]
 def run(command):calls.append(command);return dict(returncode=0)
 def observe():raise TimeoutError('readback unavailable')
 with pytest.raises(m.RegisteredLaunchRejected):m.stop_registered(d,d,journal=tmp_path,runner=run,observe_after=observe)
 assert json.loads((tmp_path/'stop_clients-terminal.json').read_text())['returncode']==0
 with pytest.raises(m.RegisteredLaunchRejected):m.stop_registered(d,d,journal=tmp_path,runner=run,observe_after=lambda:stopped(d))
 assert len(calls)==1 and not (tmp_path/'stop_clients-done.json').exists()

@pytest.mark.parametrize('kind',['non-private','symlink'])
def test_unsafe_journal_rejected_before_command(tmp_path,kind):
 target=tmp_path/'private';target.mkdir(mode=0o700);journal=target
 if kind=='non-private':target.chmod(0o755)
 else:journal=tmp_path/'link';journal.symlink_to(target,target_is_directory=True)
 d=service();calls=[]
 with pytest.raises(m.RegisteredLaunchRejected):m.stop_registered(d,d,journal=journal,runner=lambda command:calls.append(command),observe_after=lambda:stopped(d))
 assert not calls and not list(target.iterdir())
