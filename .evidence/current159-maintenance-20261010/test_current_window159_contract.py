import copy,importlib.util,json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest
p=Path(__file__).with_name('current_window159_contract.py')
s=importlib.util.spec_from_file_location('window159_contract_test',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def valid():
 now=datetime(2026,10,10,8,tzinfo=timezone.utc)
 binding=dict(thread=m.THREAD,owner=m.OWNER,task_id=m.TASK,authority_revision='AOS-001706',head='a'*40,source_id=m.SOURCE_ID,volume=m.VOLUME,cluster=m.CLUSTER,database=m.DATABASE,version='a0v_157',image='sha256:'+'b'*64,code_archive_sha256='c'*64,first_rehearsal_sha256='d'*64)
 task=dict(task_id=m.TASK,owner=m.OWNER,status='ACTIVE',base_revision='AOS-001699',lease_expires_at=(now+timedelta(hours=1)).isoformat(),scope=['aos-platform/.evidence/'+m.TASK,'aos-platform/maintenance/current-preview-database'],excluded_scope=['aos-platform/services'])
 observed={**binding,'listen_addresses':'','tcp_exit':1,'other_clients':0,'prepared':0,'services':{name:False for name in m.SERVICES},'unknown_external':False}
 spec=importlib.util.spec_from_file_location('native_surface_fixture',Path(__file__).with_name('test_execution_surface159.py'));fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
 proof,_=fixture.valid();proof['at']=now.isoformat();proof['binding']={key:binding[key] for key in ('thread','owner','task_id','authority_revision','head')};observed['execution_surface']=proof
 return binding,observed,task,[copy.deepcopy(task)],now

def test_valid_predicate_is_not_business_authority():
 b,o,t,ls,n=valid();assert m.require_zero_window(b,o,task=t,leases=ls,now=n,delivered=False) is None

@pytest.mark.parametrize('field', ['thread','owner','task_id','authority_revision','head','source_id','volume','cluster','database','version','image','code_archive_sha256','first_rehearsal_sha256'])
def test_each_binding_drift_rejected(field):
 b,o,t,ls,n=valid();o[field]='wrong'
 with pytest.raises(m.Window159Rejected):m.require_zero_window(b,o,task=t,leases=ls,now=n,delivered=False)

@pytest.mark.parametrize('field,value',[('listen_addresses','*'),('tcp_exit',0),('tcp_exit',True),('other_clients',1),('other_clients',False),('other_clients','0'),('prepared',1),('prepared',False),('unknown_external',True)])
def test_live_or_unknown_window_rejected(field,value):
 b,o,t,ls,n=valid();o[field]=value
 with pytest.raises(m.Window159Rejected):m.require_zero_window(b,o,task=t,leases=ls,now=n,delivered=False)

@pytest.mark.parametrize('service',m.SERVICES)
def test_every_execution_service_must_be_off(service):
 b,o,t,ls,n=valid();o['services'][service]=True
 with pytest.raises(m.Window159Rejected):m.require_zero_window(b,o,task=t,leases=ls,now=n,delivered=False)

@pytest.mark.parametrize('variant',['expired','different-owner','receipt-drift','duplicate-lease','delivered','scope-missing','excluded','paused','future-base'])
def test_original_task_lease_and_authority_required(variant):
 b,o,t,ls,n=valid();delivered=False
 if variant=='expired':n+=timedelta(hours=2)
 if variant=='different-owner':t['owner']='other';ls=[copy.deepcopy(t)]
 if variant=='receipt-drift':ls[0]['lease_expires_at']=(n+timedelta(hours=2)).isoformat()
 if variant=='duplicate-lease':ls.append(copy.deepcopy(t))
 if variant=='delivered':delivered=True
 if variant=='scope-missing':t['scope']=['aos-platform/other'];ls=[copy.deepcopy(t)]
 if variant=='excluded':t['excluded_scope'].append('aos-platform/maintenance');ls=[copy.deepcopy(t)]
 if variant=='paused':t['status']='PAUSED';ls=[copy.deepcopy(t)]
 if variant=='future-base':t['base_revision']='AOS-001707';ls=[copy.deepcopy(t)]
 with pytest.raises(m.Window159Rejected):m.require_zero_window(b,o,task=t,leases=ls,now=n,delivered=delivered)

@pytest.mark.parametrize('expiry', ['2026-10-10T09:00:00', 'invalid'])
def test_naive_or_bad_expiry_rejected(expiry):
 b,o,t,ls,n=valid();t['lease_expires_at']=expiry;ls=[copy.deepcopy(t)]
 with pytest.raises(m.Window159Rejected):m.require_zero_window(b,o,task=t,leases=ls,now=n,delivered=False)

def test_other_expired_overlap_still_rejected():
 b,o,t,ls,n=valid();other=copy.deepcopy(t);other.update(task_id='historical-other',lease_expires_at=(n-timedelta(days=1)).isoformat());ls.append(other)
 with pytest.raises(m.Window159Rejected):m.require_zero_window(b,o,task=t,leases=ls,now=n,delivered=False)

def test_unknown_service_state_is_not_off():
 b,o,t,ls,n=valid();o['services']['worker']=None
 with pytest.raises(m.Window159Rejected):m.require_zero_window(b,o,task=t,leases=ls,now=n,delivered=False)

def test_boolean_services_without_native_surface_rejected():
 b,o,t,ls,n=valid();o.pop('execution_surface',None)
 with pytest.raises(m.Window159Rejected):m.require_zero_window(b,o,task=t,leases=ls,now=n,delivered=False)

@pytest.mark.parametrize('field',['thread','owner','task_id','authority_revision','head'])
def test_borrowed_surface_binding_rejected(field):
 b,o,t,ls,n=valid();o['execution_surface']['binding'][field]='other'
 with pytest.raises(m.Window159Rejected):m.require_zero_window(b,o,task=t,leases=ls,now=n,delivered=False)
