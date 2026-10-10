import copy,importlib.util,json,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest
E=Path(__file__).parent
def module():
 s=importlib.util.spec_from_file_location('currentfulltest',E/'current159_native_maintenance.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m

def owner_fixture(m):
 now=datetime.now(timezone.utc);t={'task_id':m.TASK,'owner':m.OWNER,'status':'ACTIVE','lease_expires_at':(now+timedelta(hours=1)).isoformat(),'scope':['aos-platform/maintenance/current-preview-'+x for x in ('database','api','web')]};return t,[t],now
@pytest.mark.parametrize('variant',['owner','expired','status','missing','duplicate','overlap','delivered','authority','head','scope'])
def test_owner_and_all_overlap_before_effect(variant):
 m=module();t,ls,now=owner_fixture(m);delivered=False;a='AOS-001714';h='h'
 if variant=='owner':t['owner']='other'
 if variant=='expired':t['lease_expires_at']=(now-timedelta(seconds=1)).isoformat()
 if variant=='status':t['status']='COMPLETE'
 if variant=='missing':ls=[]
 if variant=='duplicate':ls=[t,t]
 if variant=='overlap':ls.append({'task_id':'other','scope':[t['scope'][0]],'lease_expires_at':(now-timedelta(days=1)).isoformat()})
 if variant=='delivered':delivered=True
 if variant=='authority':a='AOS-001715'
 if variant=='head':h='changed'
 if variant=='scope':t['scope'].pop()
 with pytest.raises(ValueError):m.require_owner(t,ls,'AOS-001714','h',a,h,delivered,now)
def test_original_live_owner():
 m=module();t,ls,now=owner_fixture(m);m.require_owner(t,ls,'AOS-001714','h','AOS-001714','h',False,now)

@pytest.mark.parametrize('variant',['no-backup','no-fullrestore','one-step','unknown','sourcecluster','clonecluster','currentversion','cloneversion','otherstep'])
def test_current_migration_requires_complete_independent_rehearsal(variant):
 m=module();p={'complete_original157_restore':True,'clone_original_steps':[158,159],'second_window_backup':True,'unknown_external':False};c={'cluster':m.CLUSTER,'base':{'version':'a0v_157'}};clone={'cluster':'other','base':{'version':'a0v_159'}};step=158
 if variant=='no-backup':p['second_window_backup']=False
 if variant=='no-fullrestore':p['complete_original157_restore']=False
 if variant=='one-step':p['clone_original_steps']=[158]
 if variant=='unknown':p['unknown_external']=True
 if variant=='sourcecluster':c['cluster']='other'
 if variant=='clonecluster':clone['cluster']=m.CLUSTER
 if variant=='currentversion':c['base']['version']='a0v_159'
 if variant=='cloneversion':clone['base']['version']='a0v_158'
 if variant=='otherstep':step=160
 with pytest.raises(ValueError):m.require_current_migration(p,c,clone,step)

@pytest.mark.parametrize('args',[['restart','foreign'],['rm','-f','anything'],['exec','foreign','pg_dump'],['exec','source','psql','-c','DROP DATABASE aos_current_preview_20260927'],['exec','source','pg_restore','-d','postgres'],['run','--name','clone','--network','bridge','image'],['run','--name','clone','--network','none','--rm','image'],['run','--name','unknown','--network','none','image'],['exec','-e','PGOPTIONS=-c session_replication_role=replica','clone','pg_restore']])
def test_command_boundary_no_fallback_no_destructive(args):
 m=module();args=[m.SOURCE if x=='source' else x for x in args]
 with pytest.raises(ValueError):m.require_effect(args,target='clone',tools={'tool'},image='image',tool_image='toolimage')
def test_exact_current_backup_and_fence_commands():
 m=module()
 for args in [['restart',m.SOURCE],['exec',m.SOURCE,'psql','-X','-U','aos_app','-d',m.DB,'-qAt','-v','ON_ERROR_STOP=1','-c',"ALTER SYSTEM SET listen_addresses=''"],['exec',m.SOURCE,'pg_dump','-U','aos_app','-d',m.DB,'-Fc'],['exec','-i',m.SOURCE,'pg_restore','--list']]:m.require_effect(args,target='clone',tools=set(),image='image',tool_image='toolimage')

@pytest.mark.parametrize('command',[['pg_dump','-U','aos_app','-d','other_database','-Fc'],['pg_dumpall','-U','aos_app'],['psql','-U','other','-c',"ALTER SYSTEM SET listen_addresses=''"],['pg_dump','-U','aos_app','-d','aos_current_preview_20260927','--clean']])
def test_current_effects_require_complete_exact_original_arguments(command):
 m=module()
 with pytest.raises(ValueError):m.require_effect(['exec',m.SOURCE,*command],target='clone',tools=set(),image='image',tool_image='toolimage')

@pytest.mark.parametrize('variant',['unknown','failure','boolean','foreign-intent','live','port','oldpid'])
def test_no_stop_replay_or_unknown_prefix(variant):
 m=module();c={'label':'original','pid':1};i={'label':'original','candidate':c,'candidate_sha256':m.sha(json.dumps(c,sort_keys=True).encode())};t={'returncode':0,'reconcile_only':False};after={'label':'original','registered':False,'listener_pids':[],'old_processes_gone':True}
 if variant=='unknown':t['reconcile_only']=True
 if variant=='failure':t['returncode']=1
 if variant=='boolean':t['returncode']=False
 if variant=='foreign-intent':i['candidate_sha256']='foreign'
 if variant=='live':after['registered']=True
 if variant=='port':after['listener_pids']=['11']
 if variant=='oldpid':after['old_processes_gone']=False
 with pytest.raises(ValueError):m.require_known_stop(c,i,t,after)
def test_known_zero_terminal_and_independent_stopped_prefix():
 m=module();c={'label':'original','pid':1};i={'label':'original','candidate':c,'candidate_sha256':m.sha(json.dumps(c,sort_keys=True).encode())};t={'returncode':0,'reconcile_only':False};a={'label':'original','registered':False,'listener_pids':[],'old_processes_gone':True}
 assert m.require_known_stop(c,i,t,a)['verified_stopped'] is True
