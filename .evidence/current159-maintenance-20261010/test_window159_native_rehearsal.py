import copy,importlib.util
from pathlib import Path
import pytest
s=importlib.util.spec_from_file_location('window159_test',Path(__file__).with_name('window159_native_rehearsal.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def resource():return {'Name':'/window159-lab-source-abc','Id':'lab-id','State':{'Running':True},'Image':'sha256:'+'a'*64,'HostConfig':{'NetworkMode':'none','Privileged':False,'RestartPolicy':{'Name':'no'}},'Config':{'Labels':{'aos.maintenance-task':m.TASK}},'Mounts':[{'Type':'volume','Name':'window159-lab-source-abc-data','Destination':'/var/lib/postgresql/data','RW':True}],'NetworkSettings':{'Ports':{'5432/tcp':None}}}

@pytest.mark.parametrize('variant',['formal-name','formal-id','formal-volume','network','port','privileged','image','label','extra-mount','readonly-volume','stopped'])
def test_resource_drift_denied(variant):
 x=resource()
 if variant=='formal-name':x['Name']='/aos-a0v-recovery-pg'
 if variant=='formal-id':x['Id']=m.FORMAL_ID
 if variant=='formal-volume':x['Mounts'][0]['Name']='aos-a0v-recovery-pg-data'
 if variant=='network':x['HostConfig']['NetworkMode']='bridge'
 if variant=='port':x['NetworkSettings']['Ports']['5432/tcp']=[{'HostPort':'18435'}]
 if variant=='privileged':x['HostConfig']['Privileged']=True
 if variant=='image':x['Image']='other'
 if variant=='label':x['Config']['Labels']['aos.maintenance-task']='other'
 if variant=='extra-mount':x['Mounts'].append(copy.deepcopy(x['Mounts'][0]))
 if variant=='readonly-volume':x['Mounts'][0]['RW']=False
 if variant=='stopped':x['State']['Running']=False
 with pytest.raises(ValueError):m.require_lab(x,'window159-lab-source-abc','sha256:'+'a'*64)

def test_exact_none_network_resource_allowed():m.require_lab(resource(),'window159-lab-source-abc','sha256:'+'a'*64)

@pytest.mark.parametrize('args',[['exec','aos-a0v-recovery-pg','psql'],['restart',m.FORMAL_ID],['rm','window159-lab-source-abc'],['volume','rm','x'],['exec','unknown','psql'],['run','--name','unknown','postgres']])
def test_formal_unknown_and_destructive_command_denied(args):
 with pytest.raises(ValueError):m.require_lab_command(args,{'window159-lab-source-abc'},set())

def test_original157_table_and_role_loss_after_migration_denied():
 before={'version':'a0v_157','tables':{'old':{'rows':2,'sha256':'old'},'["public","alembic_version"]':{'rows':1,'sha256':'157'}},'roles':[{'name':'old-role'}],'sequences':{'seq':17},'functions':[{'name':'old-function'}]}
 after=copy.deepcopy(before);after['version']='a0v_158';after['roles']=[]
 with pytest.raises(ValueError):m.require_step_preservation(before,after,158)
 after=copy.deepcopy(before);after['version']='a0v_158';after['tables']['old']['sha256']='changed'
 with pytest.raises(ValueError):m.require_step_preservation(before,after,158)
 after=copy.deepcopy(before);after['version']='a0v_158';after['tables']['new']={'rows':1,'sha256':'new'}
 with pytest.raises(ValueError):m.require_step_preservation(before,after,158)

def test_expected_next_version_and_multiset_catalogue_required():
 before={'version':'a0v_157','tables':{},'sequences':{},'functions':[{'name':'same'},{'name':'same'}]};after=copy.deepcopy(before);after['version']='a0v_159'
 with pytest.raises(ValueError):m.require_step_preservation(before,after,158)
 after['version']='a0v_158';after['functions'].pop()
 with pytest.raises(ValueError):m.require_step_preservation(before,after,158)
