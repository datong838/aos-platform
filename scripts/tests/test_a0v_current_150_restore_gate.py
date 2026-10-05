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
    coverage={name:[] for name in g.CATALOG_KEYS}
    with pytest.raises(g.Restore150Blocked):
        g.require_exact_restore({'full_catalog':coverage,'tables':{'history':{'count':1,'sha256':'a'}}},
            {'full_catalog':coverage,'tables':{'history':{'count':1,'sha256':'b'}}})


def test_current150_exact_restore_rejects_database_permission_change():
    g=gate()
    coverage={name:[] for name in g.CATALOG_KEYS}
    with pytest.raises(g.Restore150Blocked):
        g.require_exact_restore({'full_catalog':coverage,'database_permissions':[{'create':False}]},
            {'full_catalog':coverage,'database_permissions':[{'create':True}]})


@pytest.mark.parametrize('field',['column_acl','triggers','constraints','columns','default_acl'])
def test_restore_rejects_structural_or_grant_drift_with_unchanged_rows(field):
    g=gate();coverage={name:[] for name in g.CATALOG_KEYS}
    original={'tables':{'history':{'count':1,'sha256':'same'}},'full_catalog':coverage}
    changed={**original,'full_catalog':{**coverage,field:[{'changed':True}]}}
    with pytest.raises(g.Restore150Blocked):g.require_exact_restore(original,changed)


@pytest.mark.parametrize('schemas',[['public','foreign'],['other'],[]])
def test_restore_rejects_unsupported_or_missing_user_schema(schemas):
    g=gate()
    with pytest.raises(g.Restore150Blocked):g.require_supported_schemas(schemas)


def test_restore_rejects_equal_but_incomplete_old_comparison():
    g=gate()
    with pytest.raises(g.Restore150Blocked):g.require_exact_restore({'tables':{}},{'tables':{}})


def test_restore_private_directory_rejects_linked_parent(tmp_path):
    parent=tmp_path/'actual';parent.mkdir(mode=0o700)
    linked=tmp_path/'linked';linked.symlink_to(parent,target_is_directory=True)
    g=gate()
    with pytest.raises(g.Restore150Blocked):g.require_private_parent(linked)


@pytest.mark.parametrize('field',['Id','Image'])
def test_restore_rejects_source_container_replacement_with_same_name_and_mounts(field):
    before={'Id':'same-container','Image':'same-image'};after={**before,field:'replacement'}
    g=gate()
    with pytest.raises(g.Restore150Blocked):g.require_source_identity(before,after)


@pytest.mark.parametrize('field',[None,'Config','RootFS','Architecture','Os','Id'])
def test_image_binding_requires_actual_content_and_native_identity(field):
    import hashlib,json
    g=gate()
    source={'Id':'sha256:'+'a'*64,'Config':{'Cmd':['postgres']},'RootFS':{'Layers':['x']},'Architecture':'arm64','Os':'linux'}
    target={**source,'Id':'sha256:'+'b'*64}
    binding={'source_config_id':source['Id'],'target_manifest_id':target['Id'],
        'config_hash':hashlib.sha256(json.dumps(source['Config'],sort_keys=True).encode()).hexdigest(),
        'rootfs_hash':hashlib.sha256(json.dumps(source['RootFS'],sort_keys=True).encode()).hexdigest()}
    if field is None:assert g.bound_image(source,target,binding)==target['Id']
    else:
        target[field]='drift'
        with pytest.raises(g.Restore150Blocked):g.bound_image(source,target,binding)


def test_length_and_candidate_preserves_every_atom():
    g=gate()
    old="CHECK ((((length(actor) >= 1) AND (length(actor) <= 240)) AND (actor = btrim(actor))))"
    new="CHECK (((length(actor) >= 1) AND (length(actor) <= 240) AND (actor = btrim(actor))))"
    assert g.length_and_candidate(old)==new
    for altered in [new.replace('240','239'),new.replace('>= 1','>= 2'),new.replace(' AND ',' OR ',1),new.replace('btrim(actor)','btrim(subject)')]:
        assert g.length_and_candidate(old)!=g.length_and_candidate(altered)
    assert g.length_and_candidate(old.replace(' AND ',' OR ',1))==old.replace(' AND ',' OR ',1)


@pytest.mark.parametrize('tail',["(actor = btrim(subject))","(actor = btrim(actor)) OR (actor IS NULL)","(dangerous(actor))","(actor !~ 'other'::text)"])
def test_length_and_candidate_refuses_unreviewed_tail(tail):
    g=gate()
    value="CHECK ((((length(actor) >= 1) AND (length(actor) <= 240)) AND "+tail+"))"
    assert g.length_and_candidate(value)==value


@pytest.mark.parametrize('kind',['f','m','p','I','v','c','unknown'])
def test_snapshot_rejects_uncovered_relation_kinds(kind):
    g=gate()
    with pytest.raises(g.Restore150Blocked):g.require_supported_relations(['S','i','r',kind])

def test_snapshot_allows_actual_relation_inventory():
    g=gate()
    g.require_supported_relations(['S','i','r'])


@pytest.mark.parametrize('fault',[None,'bound','validated','acl'])
def test_dump_restore_equivalence_keeps_all_other_invariants(fault):
    import copy
    g=gate()
    old="CHECK ((((length(actor) >= 1) AND (length(actor) <= 240)) AND (actor = btrim(actor))))"
    row={'relation':'example','conname':'actor_check','contype':'c','convalidated':True,'definition':old}
    a={'full_catalog':{k:[] for k in g.CATALOG_KEYS},'tables':{'example':'same'}}
    a['full_catalog']['constraints']=[row]
    b=copy.deepcopy(a);b['full_catalog']['constraints'][0]['definition']=g.length_and_candidate(old)
    if fault=='bound':b['full_catalog']['constraints'][0]['definition']=b['full_catalog']['constraints'][0]['definition'].replace('240','239')
    elif fault=='validated':b['full_catalog']['constraints'][0]['convalidated']=False
    elif fault=='acl':b['full_catalog']['column_acl']=[{'grant':'unexpected'}]
    if fault is None:assert g.require_dump_restore_equivalence(a,b)==['example.actor_check']
    else:
        with pytest.raises(g.Restore150Blocked):g.require_dump_restore_equivalence(a,b)
