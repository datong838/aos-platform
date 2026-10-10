import copy,importlib.util
from pathlib import Path
import pytest
p=Path(__file__).with_name('reboot_resource_review.py');s=importlib.util.spec_from_file_location('reboot_rr',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def metadata():return dict(Id='original',started='original-time',mounts=[{'Name':'data','RW':True,'Source':'/a','Destination':'/data'},{'Name':'evidence','RW':False,'Source':'/b','Destination':'/evidence'}],ports={'5432':[{'HostIp':'127.0.0.1','HostPort':'5441'}]})
def test_mount_order_only_is_irrelevant_without_mutating_inputs():
 a=metadata();b=copy.deepcopy(a);b['mounts'].reverse();assert a!=b and m.require_same(a,b);assert a['mounts'][0]['Name']=='data'
@pytest.mark.parametrize('change',['rw','source','name','destination','duplicate','started','ports','id','omission'])
def test_any_actual_metadata_change_rejected(change):
 a=metadata();b=copy.deepcopy(a)
 if change=='rw':b['mounts'][0]['RW']=False
 elif change in ('source','name','destination'):b['mounts'][0][change.capitalize()]='other'
 elif change=='duplicate':b['mounts'].append(copy.deepcopy(b['mounts'][0]))
 elif change=='omission':del b['ports']
 elif change=='ports':b['ports']['5432'][0]['HostPort']='5433'
 elif change=='started':b['started']='new-time'
 else:b['Id']='new-id'
 with pytest.raises(ValueError):m.require_same(a,b)
