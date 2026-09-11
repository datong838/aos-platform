import asyncio
from contextlib import contextmanager
import os

import pytest

from aos_api.ecommerce_analyst_stage_decision_store import AnalystStageDecisionStore
from aos_api.ecommerce_analyst_stage_review_coordinator import (
    AsyncStageReviewCommandCoordinator,StageReviewValidationExchange)
from aos_api.ecommerce_analyst_stage_review_database_phases import StageReviewDatabasePhases
from aos_api.ecommerce_analyst_stage_review_owner_binding import StageReviewDecisionOwnerBinding
from aos_api.ecommerce_analyst_stage_review_package_port import InstalledGrowthStageReviewPort
from aos_api.ecommerce_growth_host_ports import HostTransaction
from test_ecommerce_analyst_stage_decision_store import migrate,item
from test_ecommerce_analyst_growth_plan_full_graph import disposable_database,SCOPE


pytestmark=pytest.mark.skipif(os.getenv('AOS_GROWTH_DRAFT_FULL_GRAPH_TEST')!='1',
    reason='explicit disposable database')
KINDS=("validate_command_identity","validate_review_slot","validate_runtime","validate_eval_proof")


def command(value,key="review"):
    return {"scope":{"orgId":SCOPE.org_id,"projectId":SCOPE.project_id},
        "item":value.model_dump(mode="json",by_alias=True),"actor":value.created_by,
        "key":key,"expectedVersion":value.version-1}


def exchanges(kinds=KINDS):
    return tuple(StageReviewValidationExchange({"kind":kind},{"ok":kind}) for kind in kinds)


def test_real_owner_publish_and_exact_readback_after_four_validations():
    with disposable_database() as connect:
        migrate(connect);value=item();reads=[];calls=[]
        def read_authority(tx,scope,received,actor):
            assert type(tx) is HostTransaction and scope==SCOPE and received==value and actor==value.created_by
            reads.append("authority")
            return {"taskRunId":value.task_run_id,"authorityVersion":1},exchanges()
        binding=StageReviewDecisionOwnerBinding(SCOPE,read_authority=read_authority)
        @contextmanager
        def transaction_factory(_command):
            with connect(SCOPE) as conn:yield HostTransaction(conn)
        phases=StageReviewDatabasePhases(transaction_factory=transaction_factory,
            prepare_in_transaction=binding.prepare_in_transaction,
            load_current_snapshot=binding.load_current_snapshot,
            publish_in_transaction=binding.publish_in_transaction)
        async def invoke(operation,payload):
            calls.append((operation,payload["kind"]));return {"ok":payload["kind"]}
        coordinator=AsyncStageReviewCommandCoordinator(prepare=phases.prepare,
            port=InstalledGrowthStageReviewPort(invoke),commit=phases.commit)
        result=asyncio.run(coordinator.execute(command(value)))
        assert [kind for _,kind in calls]==list(KINDS) and reads==["authority","authority"]
        with connect(SCOPE) as conn:
            owner=AnalystStageDecisionStore(HostTransaction(conn),SCOPE)
            assert owner.read_exact(_ref(result))==value
            with pytest.raises(ValueError,match="owner fast path"):
                binding.prepare_in_transaction(HostTransaction(conn),command(value))
        assert reads==["authority","authority"]


def _ref(body):
    from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
    return AnalystExactRef.model_validate(body)


def test_owner_head_change_during_ipc_blocks_target_publish():
    with disposable_database() as connect:
        migrate(connect);value=item();inserted=False
        def read_authority(*_):return {"authorityVersion":1},exchanges()
        binding=StageReviewDecisionOwnerBinding(SCOPE,read_authority=read_authority)
        @contextmanager
        def transaction_factory(_command):
            with connect(SCOPE) as conn:yield HostTransaction(conn)
        phases=StageReviewDatabasePhases(transaction_factory=transaction_factory,
            prepare_in_transaction=binding.prepare_in_transaction,
            load_current_snapshot=binding.load_current_snapshot,
            publish_in_transaction=binding.publish_in_transaction)
        async def invoke(operation,payload):
            nonlocal inserted
            if not inserted:
                with connect(SCOPE) as conn:
                    AnalystStageDecisionStore(HostTransaction(conn),SCOPE).put(value,
                        actor=value.created_by,key="competing",expected_version=0)
                inserted=True
            return {"ok":payload["kind"]}
        coordinator=AsyncStageReviewCommandCoordinator(prepare=phases.prepare,
            port=InstalledGrowthStageReviewPort(invoke),commit=phases.commit)
        with pytest.raises(ValueError,match="snapshot changed"):
            asyncio.run(coordinator.execute(command(value,"target")))
        with connect(SCOPE) as conn:
            assert conn.execute("""SELECT count(*) AS n FROM ecommerce_analyst_authority_receipt
                WHERE operation='analyst.stage_decision_publish' AND idempotency_key='target'""").fetchone()["n"]==0


@pytest.mark.parametrize("kinds",[KINDS[:-1],(KINDS[0],)*4])
def test_incomplete_or_duplicate_validations_never_publish(kinds):
    with disposable_database() as connect:
        migrate(connect);value=item()
        binding=StageReviewDecisionOwnerBinding(SCOPE,
            read_authority=lambda *_:({"authorityVersion":1},exchanges(kinds)))
        with connect(SCOPE) as conn:
            with pytest.raises(ValueError,match="four exact"):
                binding.prepare_in_transaction(HostTransaction(conn),command(value))
            assert conn.execute('SELECT count(*) AS n FROM ecommerce_analyst_stage_decision_head').fetchone()['n']==0
