import importlib.util
import json
from pathlib import Path
import pytest
import yaml
from aos_api.pipeline_source_selection import derive_mapping_read_spec
from aos_api.pipeline_source_selection_owner import verify_graph_read_spec
from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping

ROOT=Path(__file__).resolve().parents[3]

@pytest.mark.parametrize('change',['valid','source','columns','write_mode'])
def test_product_graph_keeps_the_signed_read_scope(change):
    spec=importlib.util.spec_from_file_location('p02_preflight',ROOT/'scripts/a0v_p02_current_preflight.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    package=ROOT/'bundles/candidates/ecommerce/platform.ecommerce.niushop/1.22.0/content'
    mapping=yaml.safe_load((package/'mappings/p02-product.yaml').read_text())
    original=json.dumps(mapping,sort_keys=True)
    schema=json.loads((package/'schemas/niushop-schema-fingerprint.json').read_text())
    masking=yaml.safe_load((package/'mappings/_pii-exclusion.yaml').read_text())
    read=derive_mapping_read_spec(mapping,schema,masking);compile_snapshot_mapping(mapping,read)
    graph=m.build_graph(mapping)
    if change=='source':graph['nodes'][0]['config']['source_id']='other'
    if change=='columns':graph['nodes'][1]['config']['field_mappings'].pop()
    if change=='write_mode':graph['write_mode']='APPEND'
    assert json.dumps(mapping,sort_keys=True)==original
    if change=='valid':verify_graph_read_spec(graph,mapping,read,source_id='niushop-qyh')
    else:
        with pytest.raises(ValueError):verify_graph_read_spec(graph,mapping,read,source_id='niushop-qyh')


def test_current_head_requires_generation_d_ready_exact_state():
    spec=importlib.util.spec_from_file_location('p02_preflight',ROOT/'scripts/a0v_p02_current_preflight.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    receipt={'installationId':'installation-d','installationState':'approved'}
    head={'installation_id':'installation-d','etag_version':5,'state':'active',
        'lock_hash':'sha256:'+'a'*64,'overlay_revision':'a0v-canonical-ecommerce-v1'}
    binding={'revision':4,'execution_epoch':3,'enabled':True,'operation_fence':False,
        'desired_state':'enabled','observed_state':'ready','config_ref':{'configurationId':'config-d'}}
    assert m.require_current_head(receipt,head,binding)['installationId']=='installation-d'
    for field,value in (('revision',3),('execution_epoch',4),('enabled',False),
            ('operation_fence',True),('desired_state','disabled'),('observed_state','unknown')):
        with pytest.raises(ValueError,match='ready binding'):
            m.require_current_head(receipt,head,{**binding,field:value})
