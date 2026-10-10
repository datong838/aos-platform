import copy, importlib.util
from datetime import datetime,timezone,timedelta
from pathlib import Path
import pytest

def module():
    s=importlib.util.spec_from_file_location('surface159',Path(__file__).with_name('execution_surface159.py'))
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def valid():
    now=datetime.now(timezone.utc)
    return {'scope':'CURRENT_PREVIEW_LOCAL_EXECUTION_SURFACE_ONLY','source_id':'9cc6091c304b55f637987f1fb7ffff57d64cc5020e65f2912a18969df99e9cde','cluster':'7683855731447750695','database':'aos_current_preview_20260927','at':now.isoformat(),'binding':{'thread':'01a107a2-e9e4-7670-bc44-1144fa9b27e2','owner':'codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2','task_id':'current159-maintenance-20261010','authority_revision':'AOS-001711','head':'a'*40},'counts':dict.fromkeys(('runtime_bindings','host_assignments','enabled_host_identities','enabled_meta_schedules','host_leases'),0),'process_inventory_utf8_strict':True,'process_inventory_sha256':'a'*64,'forbidden_runtime_pids':[],'legacy_api_label_absent':True,'host_label_absent':True,'global_fleet_off_proven':False,'business_runtime_authorized':False,'contexts':{
        'default':{'endpoint':'unix:///var/run/docker.sock','state':'SOCKET_ABSENT','socket_exists':False},
        'colima-aos-a0v-test-only':{'endpoint':'unix:///Users/ddt/.colima/aos-a0v-test-only/docker.sock','state':'STOPPED_COLIMA','socket_exists':False,'colima_status':'Stopped'},
        'desktop-linux':{'endpoint':'unix:///Users/ddt/.docker/run/docker.sock','state':'RUNNING','containers':[]},
        'colima-aos-extension':{'endpoint':'unix:///Users/ddt/.colima/aos-extension/docker.sock','state':'RUNNING','containers':[{'id':'9cc6091c304b55f637987f1fb7ffff57d64cc5020e65f2912a18969df99e9cde','image':'sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd','cmd':['postgres'],'entrypoint':['docker-entrypoint.sh']}]} }},now

def test_valid_is_local_only():
    v,n=valid();assert module().require_current_surface(v,now=n) is None

@pytest.mark.parametrize('key,value',[('cluster','other'),('source_id','other'),('database','other'),('scope','GLOBAL_FLEET'),('process_inventory_utf8_strict',False),('process_inventory_sha256',''),('forbidden_runtime_pids',[99]),('legacy_api_label_absent',False),('host_label_absent',False),('global_fleet_off_proven',True),('business_runtime_authorized',True)])
def test_bad_scope_or_native_fact(key,value):
    v,n=valid();v[key]=value
    with pytest.raises(ValueError):module().require_current_surface(v,now=n)

@pytest.mark.parametrize('value',[False,True,'0',1,None])
def test_unknown_or_active_counts(value):
    v,n=valid();v['counts']['runtime_bindings']=value
    with pytest.raises(ValueError):module().require_current_surface(v,now=n)

@pytest.mark.parametrize('variant',['missing-context','remote-context','active-stopped','missing-colima-proof','extra-app','foreign-source','command-suffix','missing-count','stale','future','naive'])
def test_topology_or_freshness_rejected(variant):
    v,n=valid();ctx=v['contexts']
    if variant=='missing-context':del ctx['default']
    if variant=='remote-context':ctx['default']['endpoint']='tcp://example:2375'
    if variant=='active-stopped':ctx['colima-aos-a0v-test-only']['socket_exists']=True
    if variant=='missing-colima-proof':ctx['colima-aos-a0v-test-only']['colima_status']='Running'
    if variant=='extra-app':ctx['desktop-linux']['containers']=[{'id':'b'*64,'image':'python','cmd':['python','worker.py'],'entrypoint':[]}]
    if variant=='foreign-source':ctx['colima-aos-extension']['containers'][0]['id']='b'*64
    if variant=='command-suffix':ctx['colima-aos-extension']['containers'][0]['cmd']=['postgres','worker.py']
    if variant=='missing-count':del v['counts']['host_leases']
    if variant=='stale':n+=timedelta(seconds=31)
    if variant=='future':n-=timedelta(seconds=1)
    if variant=='naive':v['at']='2026-10-10T08:00:00'
    with pytest.raises(ValueError):module().require_current_surface(v,now=n)
