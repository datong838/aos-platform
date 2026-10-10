import copy,importlib.util,json,os,plistlib,time
from pathlib import Path
import pytest

E=Path(__file__).parent
def module():
 s=importlib.util.spec_from_file_location('api_restore159_test',E/'registered_api_restore159.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def inputs():
 old=(Path.home()/'Library/LaunchAgents/com.aos.a0v-api-daily0900.plist').read_bytes()
 source=json.loads((E/'prepared-api159-source.json').read_text());runtime=json.loads((E/'prepared-api159-real-app-import.json').read_text())
 return old,source,runtime

def test_only_exact_source_and_original_config():
 m=module();old,s,r=inputs();p=m.make_plan(old,s,r);cfg=plistlib.loads(bytes.fromhex(p['plist_hex']))
 original=plistlib.loads(old)
 assert cfg['Label']==original['Label'] and cfg['ProgramArguments'][0]==original['ProgramArguments'][0]
 assert cfg['ProgramArguments'][2:]==original['ProgramArguments'][2:]
 assert cfg['KeepAlive'] is False and cfg['RunAtLoad'] is True
 assert cfg['WorkingDirectory']==s['state']+'/source'
 assert cfg['EnvironmentVariables']=={**original['EnvironmentVariables'],'PYTHONDONTWRITEBYTECODE':'1'}
 assert p['business_runtime_authorized'] is False

@pytest.mark.parametrize('variant',['old-drift','source-state','source-status','runtime-interpreter','runtime-status','foreign-modules','runtime-server','wrong-signed-root','no-crypto','no-full-snapshot','changed-source'])
def test_bad_preparation(variant):
 m=module();old,s,r=inputs()
 if variant=='old-drift':old+=b'\n'
 if variant=='source-state':s['state']='/tmp/foreign'
 if variant=='source-status':s['status']='fake'
 if variant=='runtime-interpreter':r['interpreter']='/tmp/python'
 if variant=='runtime-status':r['status']='fake'
 if variant=='foreign-modules':r['all_api_modules_from_export']=False
 if variant=='runtime-server':r['server_started']=True
 if variant=='wrong-signed-root':r['signed_root']='/tmp'
 if variant=='no-crypto':r['signed_crypto_exact']=False
 if variant=='no-full-snapshot':r['formal157_full_snapshot_equal_before_after_and_original_protocol']=False
 if variant=='changed-source':r['source_exact_after_import']=False
 with pytest.raises(ValueError):m.make_plan(old,s,r)

def fixture(tmp_path,monkeypatch):
 m=module();old,s,r=inputs();plan=m.make_plan(old,s,r)
 home=tmp_path/'home';agents=home/'Library/LaunchAgents';agents.mkdir(parents=True);target=agents/(m.API+'.plist');target.write_bytes(old)
 monkeypatch.setattr(m.Path,'home',classmethod(lambda cls:home))
 entry=tmp_path/'entry.py';entry.write_bytes((E/'api159_registered_entrypoint.py').read_bytes());entry.chmod(0o600);monkeypatch.setattr(m,'ENTRY_PATH',entry)
 journal=tmp_path/'journal';journal.mkdir(mode=0o700)
 stop={'label':m.API,'candidate_sha256':m.ORIGINAL_CANDIDATE_SHA,'returncode':0,'verified_stopped':True}
 before={'registered':False,'listener_pids':[],'old_processes_gone':True,'label':m.API}
 window={'source_id':m.SOURCE,'cluster':m.CLUSTER,'database':m.DB,'version':'a0v_159','volume':m.VOLUME,'original_configuration_source_restored':True,'complete_migrated_catalogues_equal':True,'source_original158159_commit_verified':True,'unknown_external':False}
 fp={'pid':991,'ppid':1,'uid':os.getuid(),'started':time.strftime('%a %b %d %H:%M:%S %Y'),'argv_sha256':plan['argv_sha256'],'cwd':plan['cwd'],'children':[],'listener_ports':[8080]}
 after={'label':m.API,'registered':True,'pid':991,'listener_pids':['991'],'plist_sha256':plan['plist_sha256'],'fingerprint':fp}
 return m,plan,old,journal,stop,before,window,after,target

def test_one_replace_and_bootstrap_no_repeat(tmp_path,monkeypatch):
 m,p,old,j,stop,before,window,after,target=fixture(tmp_path,monkeypatch);calls=[];guards=[]
 def observed():
  after['fingerprint']['started']=time.strftime('%a %b %d %H:%M:%S %Y');return after
 result=m.restore_api(p,stop_proof=stop,before=before,window=window,journal=j,guard=lambda:guards.append(1),runner=lambda c:(calls.append(c) or {'returncode':0}),observe_after=observed)
 assert result['verified_restored'] is True and len(calls)==1 and len(guards)==2
 assert (j/'original-api.plist').read_bytes()==old and target.read_bytes()==bytes.fromhex(p['plist_hex'])
 with pytest.raises((ValueError,FileExistsError)):m.restore_api(p,stop_proof=stop,before=before,window=window,journal=j,guard=lambda:None,runner=lambda c:calls.append(c),observe_after=lambda:after)
 assert len(calls)==1

@pytest.mark.parametrize('variant',['schema157','foreign-source','unknown','live','wrong-stop','changed-plist'])
def test_before_effect_rejection(tmp_path,monkeypatch,variant):
 m,p,old,j,stop,before,window,after,target=fixture(tmp_path,monkeypatch);calls=[]
 if variant=='schema157':window['version']='a0v_157'
 if variant=='foreign-source':window['source_id']='foreign'
 if variant=='unknown':window['unknown_external']=True
 if variant=='live':before['registered']=True
 if variant=='wrong-stop':stop['candidate_sha256']='x'
 if variant=='changed-plist':target.write_bytes(b'changed')
 initial=target.read_bytes()
 with pytest.raises(ValueError):m.restore_api(p,stop_proof=stop,before=before,window=window,journal=j,guard=lambda:None,runner=lambda c:calls.append(c),observe_after=lambda:after)
 assert calls==[] and target.read_bytes()==initial

@pytest.mark.parametrize('terminal',[{'returncode':1},{'returncode':True},{},None])
def test_terminal_failure_no_repeat(tmp_path,monkeypatch,terminal):
 m,p,old,j,stop,before,window,after,target=fixture(tmp_path,monkeypatch);calls=[]
 with pytest.raises(ValueError):m.restore_api(p,stop_proof=stop,before=before,window=window,journal=j,guard=lambda:None,runner=lambda c:(calls.append(c) or terminal),observe_after=lambda:after)
 assert len(calls)==1 and (j/'api-bootstrap-terminal.json').exists() and not (j/'api-bootstrap-done.json').exists()

@pytest.mark.parametrize('variant',['foreign-uid','foreign-cwd','extra-child','wrong-port','wrong-start','wrong-parent','wrong-pid'])
def test_post_fingerprint_reject(tmp_path,monkeypatch,variant):
 m,p,old,j,stop,before,window,after,target=fixture(tmp_path,monkeypatch);fp=after['fingerprint']
 if variant=='foreign-uid':fp['uid']+=1
 if variant=='foreign-cwd':fp['cwd']='/tmp'
 if variant=='extra-child':fp['children']=[123]
 if variant=='wrong-port':fp['listener_ports']=[9999]
 if variant=='wrong-start':fp['started']=''
 if variant=='wrong-parent':fp['ppid']=123
 if variant=='wrong-pid':fp['pid']=990
 with pytest.raises(ValueError):m.restore_api(p,stop_proof=stop,before=before,window=window,journal=j,guard=lambda:None,runner=lambda c:{'returncode':0},observe_after=lambda:after)
 assert not (j/'api-bootstrap-done.json').exists()

@pytest.mark.parametrize('started',['bogus','Sat Oct 10 10:00:00 2026','Sat Oct 10 10:00:00 2036'])
def test_process_not_born_in_this_attempt(tmp_path,monkeypatch,started):
 m,p,old,j,stop,before,window,after,target=fixture(tmp_path,monkeypatch);after['fingerprint']['started']=started
 with pytest.raises(ValueError):m.restore_api(p,stop_proof=stop,before=before,window=window,journal=j,guard=lambda:None,runner=lambda c:{'returncode':0},observe_after=lambda:after)
 assert not (j/'api-bootstrap-done.json').exists()

@pytest.mark.parametrize('which_guard',[1,2])
def test_fresh_guard_failure_never_bootstraps(tmp_path,monkeypatch,which_guard):
 m,p,old,j,stop,before,window,after,target=fixture(tmp_path,monkeypatch);calls=[];guards=[]
 def guard():
  guards.append(1)
  if len(guards)==which_guard:raise ValueError('current source/task drift')
 with pytest.raises(ValueError):m.restore_api(p,stop_proof=stop,before=before,window=window,journal=j,guard=guard,runner=lambda c:calls.append(c),observe_after=lambda:after)
 assert calls==[]
 assert (target.read_bytes()==old)==(which_guard==1)

@pytest.mark.parametrize('variant',['missing','changed','public','symlink'])
def test_frozen_entry_drift_no_replace(tmp_path,monkeypatch,variant):
 m,p,old,j,stop,before,window,after,target=fixture(tmp_path,monkeypatch);entry=m.ENTRY_PATH;calls=[]
 if variant=='missing':entry.unlink()
 if variant=='changed':entry.write_bytes(b'wrong')
 if variant=='public':entry.chmod(0o644)
 if variant=='symlink':entry.unlink();entry.symlink_to(E.resolve()/'api159_registered_entrypoint.py')
 with pytest.raises(ValueError):m.restore_api(p,stop_proof=stop,before=before,window=window,journal=j,guard=lambda:None,runner=lambda c:calls.append(c),observe_after=lambda:after)
 assert calls==[] and target.read_bytes()==old and not (j/'plist-replace-intent.json').exists()

def test_entry_changed_between_effects_no_bootstrap(tmp_path,monkeypatch):
 m,p,old,j,stop,before,window,after,target=fixture(tmp_path,monkeypatch);calls=[];guards=[]
 def guard():
  guards.append(1)
  if len(guards)==2:m.ENTRY_PATH.write_bytes(b'changed after plist replacement')
 with pytest.raises(ValueError):m.restore_api(p,stop_proof=stop,before=before,window=window,journal=j,guard=guard,runner=lambda c:calls.append(c),observe_after=lambda:after)
 assert calls==[] and target.read_bytes()==bytes.fromhex(p['plist_hex']) and not (j/'api-bootstrap-intent.json').exists()
