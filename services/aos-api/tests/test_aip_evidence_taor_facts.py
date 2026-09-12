import pytest
from aos_api.aip_production_contract_store import AipProductionContractStore


@pytest.mark.parametrize('payload,expected',[
    ({'factIds':['source-license','scope']},['source-license','scope']),
    ({'facts':{'source-license':'internal'}},['source-license']),
    ({'stepRunId':'step-1','stepKey':'verify','payload':{'factIds':['source-license']}},['source-license']),
    ({'stepRunId':'','stepKey':'verify','payload':{'factIds':['source-license']}},[]),
    ({'stepRunId':'step-1','stepKey':'verify','payload':{'factIds':['source-license']},'extra':True},[]),
    ({'payload':{'factIds':['source-license']}},[]),
    ({'stepRunId':'step-1','stepKey':'verify','payload':{'payload':{'factIds':['source-license']}}},[]),
    ({'stepRunId':'step-1','stepKey':'verify','payload':{}},[]),
])
def test_only_canonical_taor_envelope_exposes_original_facts(payload,expected):
    assert AipProductionContractStore._evidence_fact_ids(payload)==expected
