"""Infrastructure boundary tests; no mock proves a real database restore."""
import importlib.util
from pathlib import Path

import pytest


def gate():
    path=Path(__file__).resolve().parents[1]/'a0v_current_150_restore_gate.py'
    spec=importlib.util.spec_from_file_location('restore150',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('fault',['source_volume','network','port','bind','privileged','image','name'])
def test_current150_restore_target_cannot_alias_or_expose_current_source(fault):
    g=gate()
    item=dict(Name='/current150-probe',State=dict(Running=True),Image='sha256:pinned',
        Config=dict(Labels={'aos.restore-gate':'20261005-150'}),
        HostConfig=dict(NetworkMode='none',Privileged=False),
        NetworkSettings=dict(Ports={'5432/tcp':None}),
        Mounts=[dict(Type='volume',Name='current150-probe-data',Destination='/var/lib/postgresql/data',RW=True)])
    if fault=='source_volume':item['Mounts'][0]['Name']='aos-a0v-recovery-pg-data'
    elif fault=='network':item['HostConfig']['NetworkMode']='bridge'
    elif fault=='port':item['NetworkSettings']['Ports']['5432/tcp']=[dict(HostPort='18435')]
    elif fault=='bind':item['Mounts'].append(dict(Type='bind',Destination='/host'))
    elif fault=='privileged':item['HostConfig']['Privileged']=True
    elif fault=='image':item['Image']='sha256:other'
    elif fault=='name':item['Name']='/aos-a0v-recovery-pg'
    with pytest.raises(g.Restore150Blocked):
        g.require_target(item,container='current150-probe',image='sha256:pinned')


def test_current150_exact_restore_rejects_same_count_changed_history():
    g=gate()
    with pytest.raises(g.Restore150Blocked):
        g.require_exact_restore({'tables':{'history':{'count':1,'sha256':'a'}}},
            {'tables':{'history':{'count':1,'sha256':'b'}}})


def test_current150_exact_restore_rejects_database_permission_change():
    g=gate()
    with pytest.raises(g.Restore150Blocked):
        g.require_exact_restore({'database_permissions':[{'create':False}]},
            {'database_permissions':[{'create':True}]})
