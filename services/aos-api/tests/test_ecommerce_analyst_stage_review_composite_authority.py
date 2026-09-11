import pytest

from aos_api.asset_registry.canonical_json import canonical_json
import aos_api.ecommerce_analyst_stage_review_composite_authority as module
from aos_api.ecommerce_analyst_stage_review_composite_authority import StageReviewCompositeAuthorityReader
from aos_api.ecommerce_growth_host_ports import HostTransaction
from test_ecommerce_analyst_stage_decision_store import item
from test_ecommerce_analyst_growth_plan_full_graph import SCOPE


class Empty:pass


def test_composite_has_fixed_five_messages_and_sealed_snapshots(monkeypatch):
    value=item();markings=['internal']
    monkeypatch.setattr(module,'read_stage_review_responsibility_authority',lambda *a,**k:
        {'reviewer':value.reviewer,'snapshot':{'responsibility':1},'payload':{'kind':'validate_review_slot'},'expected':{'slot':1}})
    monkeypatch.setattr(module,'read_stage_review_runtime_authority',lambda *a,**k:
        {'plan':{'steps':[]},'snapshot':{'runtime':1},'payload':{'kind':'validate_runtime'},'expected':{'run':1}})
    seen=[]
    def evaluated(tx,scope,item,plan,received_markings):
        seen.append(received_markings)
        return {'snapshot':{'eval':1},'evalPayload':{'kind':'validate_eval_proof'},
            'evalExpected':{'eval':1},'structurePayload':{'kind':'validate_structure_case'},
            'structureExpected':{'case':1}}
    monkeypatch.setattr(module,'read_stage_review_eval_source_authority',evaluated)
    reader=StageReviewCompositeAuthorityReader(markings);markings.append('changed')
    snapshot,exchanges=reader(HostTransaction(Empty()),SCOPE,value,value.created_by,'review',0)
    assert [entry.payload['kind'] for entry in exchanges]==['validate_command_identity',
        'validate_review_slot','validate_runtime','validate_eval_proof','validate_structure_case']
    assert seen==[['internal']] and snapshot['responsibility']=={'responsibility':1}
    canonical_json(snapshot)


def test_invalid_markings_and_component_shape_fail_before_exchange(monkeypatch):
    with pytest.raises(ValueError,match='markings'):StageReviewCompositeAuthorityReader([])
    value=item();reader=StageReviewCompositeAuthorityReader(['internal'])
    monkeypatch.setattr(module,'read_stage_review_responsibility_authority',lambda *a,**k:{})
    monkeypatch.setattr(module,'read_stage_review_runtime_authority',lambda *a,**k:{})
    monkeypatch.setattr(module,'read_stage_review_eval_source_authority',lambda *a,**k:{})
    with pytest.raises(ValueError,match='proof shape'):
        reader(HostTransaction(Empty()),SCOPE,value,value.created_by,'review',0)
