import asyncio

import pytest

from aos_api.ecommerce_analyst_stage_review_coordinator import (
    AsyncStageReviewCommandCoordinator,StageReviewValidationExchange)
from aos_api.ecommerce_analyst_stage_review_database_phases import StageReviewDatabasePhases
from aos_api.ecommerce_analyst_stage_review_package_port import InstalledGrowthStageReviewPort


class Transaction:
    def __init__(self,state,name):self.state,self.name=state,name
    def __enter__(self):
        self.state["active"]+=1;self.state["events"].append("open:"+self.name);return self
    def __exit__(self,error_type,*_):
        self.state["events"].append(("rollback:" if error_type else "close:")+self.name)
        self.state["active"]-=1


def build(*,current=None,ipc_error=None,publish_error=None):
    state={"active":0,"sequence":0,"events":[],"published":0}
    command={"decisionId":"decision-1"}
    snapshot={"tenantId":"tenant-1","ownerVersion":7}
    exchanges=(StageReviewValidationExchange(
        {"kind":"validate_command_identity"},{"ok":True}),)
    def transaction_factory(value):
        assert value is command;state["sequence"]+=1
        return Transaction(state,str(state["sequence"]))
    def prepare(transaction,value):
        assert state["active"]==1 and value is command
        state["events"].append("prepare")
        return snapshot,exchanges
    def load(transaction,value):
        assert state["active"]==1 and value is command
        state["events"].append("load")
        return snapshot if current is None else current
    def publish(transaction,value,prepared,results):
        assert state["active"]==1 and value is command and results==({"ok":True},)
        state["events"].append("publish");state["published"]+=1
        if publish_error:raise publish_error
        return {"resourceType":"AnalystStageDecisionRevision","resourceId":"decision-1"}
    phases=StageReviewDatabasePhases(transaction_factory=transaction_factory,
        prepare_in_transaction=prepare,load_current_snapshot=load,
        publish_in_transaction=publish)
    async def invoke(operation,payload):
        assert operation=="ecommerce_growth_review_advance" and state["active"]==0
        state["events"].append("ipc")
        if ipc_error:raise ipc_error
        return {"ok":True}
    coordinator=AsyncStageReviewCommandCoordinator(prepare=phases.prepare,
        port=InstalledGrowthStageReviewPort(invoke),commit=phases.commit)
    return coordinator,command,state,phases


def test_transactions_are_separate_and_ipc_holds_no_database_resource():
    coordinator,command,state,_=build()
    result=asyncio.run(coordinator.execute(command))
    assert result["resourceId"]=="decision-1"
    assert state["events"]==[
        "open:1","prepare","close:1","ipc","open:2","load","publish","close:2"]
    assert state["active"]==0 and state["published"]==1


def test_current_snapshot_drift_rolls_back_without_publish():
    coordinator,command,state,_=build(current={"tenantId":"tenant-1","ownerVersion":8})
    with pytest.raises(ValueError,match="snapshot changed"):
        asyncio.run(coordinator.execute(command))
    assert state["events"]==[
        "open:1","prepare","close:1","ipc","open:2","load","rollback:2"]
    assert state["published"]==0 and state["active"]==0


def test_unknown_ipc_outcome_never_opens_commit_transaction():
    coordinator,command,state,_=build(ipc_error=TimeoutError("unknown"))
    with pytest.raises(TimeoutError,match="unknown"):asyncio.run(coordinator.execute(command))
    assert state["events"]==["open:1","prepare","close:1","ipc"]
    assert state["sequence"]==1 and state["published"]==0


def test_publish_failure_rolls_back_once_without_replaying_ipc():
    coordinator,command,state,_=build(publish_error=RuntimeError("write failed"))
    with pytest.raises(RuntimeError,match="write failed"):asyncio.run(coordinator.execute(command))
    assert state["events"].count("ipc")==1 and state["events"].count("publish")==1
    assert state["events"][-1]=="rollback:2" and state["active"]==0


def test_dependencies_prepare_shape_and_result_count_fail_closed():
    async def invalid(*_):return None
    with pytest.raises(TypeError,match="synchronous"):
        StageReviewDatabasePhases(transaction_factory=invalid,prepare_in_transaction=lambda *_:None,
            load_current_snapshot=lambda *_:{},publish_in_transaction=lambda *_:{})
    _,command,_,phases=build()
    original=phases.prepare_in_transaction
    phases.prepare_in_transaction=lambda *_:(original.__name__,)
    with pytest.raises(TypeError,match="snapshot and exchanges"):
        asyncio.run(phases.prepare(command))
    _,command,_,phases=build()
    prepared=asyncio.run(phases.prepare(command))
    with pytest.raises(ValueError,match="complete"):
        asyncio.run(phases.commit(command,prepared,()))
