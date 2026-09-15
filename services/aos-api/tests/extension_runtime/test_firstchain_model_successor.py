import importlib
from copy import deepcopy
import pytest
from test_growth19_successor_business import profile
from aos_api.aip_d03_pilot import build_d03_graph_request
from aos_api.aip_logic_graph_models import LogicGraphSnapshot, logic_graph_content_payload


def snapshot(request):
    return LogicGraphSnapshot(id=request.id, revision=2, graph_hash='a'*64,
        published_version=1, created_at='2026-09-12T00:00:00Z',
        updated_at='2026-09-12T00:00:00Z', **logic_graph_content_payload(request))


def test_model_only_successor_keeps_revision_cas(profile):
    m=importlib.import_module('a0v_firstchain_model_successor')
    old=build_d03_graph_request(model_id='old-exact')
    new=build_d03_graph_request(model_id='new-exact')
    request=m.replacement(snapshot(old),old,new)
    assert request.expected_revision==2
    assert request.nodes[1].config['model']=='new-exact'


@pytest.mark.parametrize('fault',['prompt','tool','id','old-model','no-change'])
def test_successor_rejects_unrelated_drift(profile,fault):
    m=importlib.import_module('a0v_firstchain_model_successor')
    old=build_d03_graph_request(model_id='old-exact')
    current=snapshot(old);new=build_d03_graph_request(model_id='new-exact')
    if fault=='prompt':new.nodes[1].config['prompt']='changed'
    elif fault=='tool':new.nodes[1].config['tool']='external'
    elif fault=='id':new.id='other'
    elif fault=='old-model':current.nodes[1].config['model']='unexpected'
    elif fault=='no-change':new=deepcopy(old)
    with pytest.raises(ValueError):m.replacement(current,old,new)


def test_successor_existing_intent_never_calls_store(profile,tmp_path):
    m=importlib.import_module('a0v_firstchain_model_successor')
    p=tmp_path/'intent.json';p.write_text('{}')
    with pytest.raises(ValueError,match='read-only'):
        m.apply_graph(None,None,None,None,None,p)
