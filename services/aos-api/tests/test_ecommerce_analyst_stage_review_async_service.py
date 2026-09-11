import asyncio
import os
import pytest

import aos_api.ecommerce_analyst_stage_review_async_service as module
from aos_api.ecommerce_analyst_stage_review_async_service import AsyncAnalystStageReviewCommandService
from aos_api.ecommerce_analyst_stage_review_coordinator import StageReviewValidationExchange
from aos_api.ecommerce_analyst_stage_decision_store import AnalystStageDecisionStore
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_growth_host_ports import HostTransaction
from test_ecommerce_analyst_stage_decision_store import migrate,item,hashed
from test_ecommerce_analyst_growth_plan_full_graph import disposable_database,SCOPE

pytestmark=pytest.mark.skipif(os.getenv('AOS_GROWTH_DRAFT_FULL_GRAPH_TEST')!='1',reason='explicit disposable database')
KINDS=('validate_command_identity','validate_review_slot','validate_runtime','validate_eval_proof','validate_structure_case')


class Reader:
    calls=0
    def __init__(self,markings):assert markings==['internal']
    def __call__(self,*args):
        type(self).calls+=1
        return {'authority':1},tuple(StageReviewValidationExchange({'kind':kind},{'ok':kind}) for kind in KINDS)


def test_new_publish_then_replay_uses_zero_additional_ipc_or_reader(monkeypatch):
    with disposable_database() as connect:
        migrate(connect);value=item();Reader.calls=0;ipc=[]
        monkeypatch.setattr(module,'StageReviewCompositeAuthorityReader',Reader)
        async def invoke(operation,payload):ipc.append(payload['kind']);return {'ok':payload['kind']}
        service=AsyncAnalystStageReviewCommandService(connect,invoke_installed_once=invoke,markings=['internal'])
        first=asyncio.run(service.decide(SCOPE,value,actor=value.created_by,key='review',expected_version=0))
        assert ipc==list(KINDS) and Reader.calls==2
        second=asyncio.run(service.decide(SCOPE,value,actor=value.created_by,key='review',expected_version=0))
        assert second==first and ipc==list(KINDS) and Reader.calls==2
        changed=hashed(value.model_copy(update={'reason':'different replay body'}))
        with pytest.raises(ValueError,match='replay command drifted'):
            asyncio.run(service.decide(SCOPE,changed,actor=changed.created_by,key='review',expected_version=0))
        assert ipc==list(KINDS) and Reader.calls==2
        with connect(SCOPE) as conn:
            assert AnalystStageDecisionStore(HostTransaction(conn),SCOPE).read_exact(
                AnalystExactRef.model_validate(first))==value


def test_unknown_ipc_never_publishes(monkeypatch):
    with disposable_database() as connect:
        migrate(connect);value=item();monkeypatch.setattr(module,'StageReviewCompositeAuthorityReader',Reader)
        async def invoke(*_):raise TimeoutError('unknown')
        service=AsyncAnalystStageReviewCommandService(connect,invoke_installed_once=invoke,markings=['internal'])
        with pytest.raises(TimeoutError):asyncio.run(service.decide(
            SCOPE,value,actor=value.created_by,key='unknown',expected_version=0))
        with connect(SCOPE) as conn:
            assert conn.execute('SELECT count(*) AS n FROM ecommerce_analyst_stage_decision_head').fetchone()['n']==0
