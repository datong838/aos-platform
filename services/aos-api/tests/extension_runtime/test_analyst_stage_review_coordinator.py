import asyncio

import pytest

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_analyst_stage_review_coordinator import (
    AsyncStageReviewCommandCoordinator,PreparedStageReviewValidation,StageReviewValidationExchange)
from aos_api.ecommerce_analyst_stage_review_package_port import InstalledGrowthStageReviewPort


def run(*,runtime=None,prepare_change=None,commit_error=None):
    events=[];command={"decisionId":"decision-1"}
    exchanges=(StageReviewValidationExchange({"kind":"validate_command_identity"},{"ok":1}),
        StageReviewValidationExchange({"kind":"validate_runtime"},{"ok":2}))
    async def prepare(value):
        events.append("prepare")
        prepared=PreparedStageReviewValidation(canonical_sha256(value),exchanges,{"owner":"owner-1"})
        if prepare_change:prepare_change(prepared)
        return prepared
    async def invoke(operation,payload):
        events.append("ipc:"+payload["kind"])
        if runtime:return runtime(payload)
        return {"ok":1 if payload["kind"]=="validate_command_identity" else 2}
    async def commit(value,prepared,results):
        events.append("commit")
        assert value is command and prepared.exchanges is exchanges and len(results)==2
        if commit_error:raise commit_error
        return {"resourceType":"AnalystStageDecisionRevision","resourceId":"decision-1"}
    coordinator=AsyncStageReviewCommandCoordinator(prepare=prepare,
        port=InstalledGrowthStageReviewPort(invoke),commit=commit)
    return coordinator,command,events


def test_prepare_ipc_commit_order_and_exact_objects():
    coordinator,command,events=run()
    result=asyncio.run(coordinator.execute(command))
    assert result["resourceId"]=="decision-1"
    assert events==["prepare","ipc:validate_command_identity","ipc:validate_runtime","commit"]


def test_wrong_prepare_hash_never_invokes_runtime_or_commit():
    async def prepare(value):return PreparedStageReviewValidation("sha256:"+"0"*64,
        (StageReviewValidationExchange({"kind":"validate_runtime"},{"ok":True}),),{"owner":"owner-1"})
    calls=[]
    async def invoke(*args):calls.append("ipc");return {"ok":True}
    async def commit(*args):calls.append("commit");return {}
    c=AsyncStageReviewCommandCoordinator(prepare=prepare,port=InstalledGrowthStageReviewPort(invoke),commit=commit)
    with pytest.raises(ValueError,match="command drifted"):asyncio.run(c.execute({"id":1}))
    assert calls==[]


def test_unknown_ipc_outcome_is_not_retried_and_never_commits():
    calls=[]
    def fail(payload):calls.append(payload["kind"]);raise TimeoutError("unknown")
    coordinator,command,events=run(runtime=fail)
    with pytest.raises(TimeoutError):asyncio.run(coordinator.execute(command))
    assert calls==["validate_command_identity"] and "commit" not in events


def test_runtime_payload_mutation_is_detected_before_commit():
    def mutate(payload):
        payload["extra"]=True
        return {"ok":1}
    coordinator,command,events=run(runtime=mutate)
    with pytest.raises(ValueError,match="exchange changed"):asyncio.run(coordinator.execute(command))
    assert events==["prepare","ipc:validate_command_identity"]


def test_commit_failure_never_replays_ipc():
    coordinator,command,events=run(commit_error=RuntimeError("current drift"))
    with pytest.raises(RuntimeError,match="current drift"):asyncio.run(coordinator.execute(command))
    assert events.count("ipc:validate_command_identity")==1 and events.count("ipc:validate_runtime")==1


def test_dependencies_and_unique_bounded_exchanges_are_strict():
    async def async_fn(*args):return {}
    port=InstalledGrowthStageReviewPort(async_fn)
    with pytest.raises(TypeError):AsyncStageReviewCommandCoordinator(prepare=lambda x:x,port=port,commit=async_fn)
    item=StageReviewValidationExchange({"kind":"validate_runtime"},{})
    with pytest.raises(ValueError,match="unique"):PreparedStageReviewValidation(
        "sha256:"+"a"*64,(item,item),{"owner":"owner-1"})
    with pytest.raises(ValueError,match="bounded"):PreparedStageReviewValidation(
        "sha256:"+"a"*64,tuple(StageReviewValidationExchange(
            {"kind":"kind-"+str(index)},{}) for index in range(6)),{"owner":"owner-1"})


def test_authority_snapshot_must_be_non_empty_and_remain_unchanged():
    item=StageReviewValidationExchange({"kind":"validate_runtime"},{})
    with pytest.raises(ValueError,match="non-empty"):
        PreparedStageReviewValidation("sha256:"+"a"*64,(item,),{})
    snapshot={"owner":"owner-1"}
    prepared=PreparedStageReviewValidation("sha256:"+"a"*64,(item,),snapshot)
    snapshot["owner"]="owner-2"
    with pytest.raises(ValueError,match="validation changed"):prepared.verify()
