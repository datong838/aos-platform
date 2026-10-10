import copy,importlib.util,json,subprocess
from pathlib import Path
import pytest
s=importlib.util.spec_from_file_location('api_start_guard159',Path(__file__).with_name('api159_registered_entrypoint.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def source():
 return {'Id':m.ID,'Name':'/aos-a0v-recovery-pg','Image':m.IMAGE,'State':{'Running':True},'Config':{'Cmd':['postgres'],'Entrypoint':['docker-entrypoint.sh']},'HostConfig':{'NetworkMode':'bridge','RestartPolicy':{'Name':'no'}},'NetworkSettings':{'Ports':{'5432/tcp':[{'HostIp':'127.0.0.1','HostPort':'18435'}]}},'Mounts':[{'Type':'volume','Name':'aos-a0v-recovery-pg-data','RW':True,'Destination':'/var/lib/postgresql/data'},{'Type':'bind','RW':False,'Destination':'/backup','Source':'/Users/ddt/work/projects/ai_agent/.aos-recovery-20260910/backups'}]}

def test_original_source_only():
 assert m.require_source(source()) is None
 assert m.require_database({'cluster':m.CLUSTER,'database':m.DB,'version':'a0v_159'}) is None

@pytest.mark.parametrize('variant',['id','name','image','stopped','command','entrypoint','network','restart','port','volume','rw','backup','extra-mount'])
def test_foreign_resource_rejected(variant):
 x=source()
 if variant=='id':x['Id']='other'
 if variant=='name':x['Name']='/other'
 if variant=='image':x['Image']='other'
 if variant=='stopped':x['State']['Running']=False
 if variant=='command':x['Config']['Cmd']=['postgres','worker.py']
 if variant=='entrypoint':x['Config']['Entrypoint']=['sh']
 if variant=='network':x['HostConfig']['NetworkMode']='host'
 if variant=='restart':x['HostConfig']['RestartPolicy']['Name']='always'
 if variant=='port':x['NetworkSettings']['Ports']['5432/tcp'][0]['HostPort']='5432'
 if variant=='volume':x['Mounts'][0]['Name']='empty-new'
 if variant=='rw':x['Mounts'][0]['RW']=False
 if variant=='backup':x['Mounts'][1]['RW']=True
 if variant=='extra-mount':x['Mounts'].append(x['Mounts'][0])
 with pytest.raises(ValueError):m.require_source(x)

@pytest.mark.parametrize('key',['cluster','database','version'])
def test_foreign_database_rejected(key):
 x={'cluster':m.CLUSTER,'database':m.DB,'version':'a0v_159'};x[key]='other'
 with pytest.raises(ValueError):m.require_database(x)

def test_original_export_and_manifest_change_rejected():
 manifest=json.loads((m.STATE/'manifest.json').read_text());assert m.verify_source(m.SOURCE,manifest) is None
 key=next(iter(manifest));manifest[key]='0'*64
 with pytest.raises(ValueError):m.verify_source(m.SOURCE,manifest)
