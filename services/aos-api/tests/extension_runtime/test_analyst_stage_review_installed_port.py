import asyncio

import pytest

from aos_api.ecommerce_analyst_stage_review_package_port import InstalledGrowthStageReviewPort


@pytest.mark.parametrize("kind", ["validate_command_identity", "validate_review_slot", "validate_runtime", "validate_eval_proof", "validate_structure_case"])
def test_each_kind_invokes_installed_runtime_exactly_once(kind):
    calls=[]
    async def invoke(operation,payload):
        calls.append((operation,payload));return {"ok":kind}
    port=InstalledGrowthStageReviewPort(invoke)
    result=asyncio.run(port.validate(payload={"kind":kind},expected={"ok":kind}))
    assert result=={"ok":kind}
    assert calls==[("ecommerce_growth_review_advance",{"kind":kind})]


@pytest.mark.parametrize("failure", ["old", "unknown", "cancel"])
def test_runtime_failure_is_never_retried_or_replaced(failure):
    calls=[]
    async def invoke(operation,payload):
        calls.append((operation,payload))
        if failure=="old":raise PermissionError("registration-only")
        if failure=="unknown":raise TimeoutError("outcome unknown")
        raise asyncio.CancelledError()
    port=InstalledGrowthStageReviewPort(invoke)
    error={"old":PermissionError,"unknown":TimeoutError,"cancel":asyncio.CancelledError}[failure]
    with pytest.raises(error):asyncio.run(port.validate(payload={"kind":"validate_runtime"},expected={"ok":True}))
    assert len(calls)==1


@pytest.mark.parametrize("result", [None, [], {"ok":False}, {"ok":True,"extra":1}])
def test_response_must_equal_host_expectation(result):
    calls=[]
    async def invoke(operation,payload):calls.append(1);return result
    with pytest.raises(ValueError,match="response drifted"):
        asyncio.run(InstalledGrowthStageReviewPort(invoke).validate(payload={"kind":"validate_runtime"},expected={"ok":True}))
    assert calls==[1]


def test_non_json_or_unknown_request_never_invokes_runtime():
    calls=[]
    async def invoke(operation,payload):calls.append(1);return {}
    port=InstalledGrowthStageReviewPort(invoke)
    for payload in ({"kind":"unknown"},{"kind":"validate_runtime","items":(1,)}):
        with pytest.raises(ValueError):asyncio.run(port.validate(payload=payload,expected={}))
    assert calls==[]


def test_port_requires_async_installed_invoker():
    with pytest.raises(TypeError,match="installed async"):
        InstalledGrowthStageReviewPort(lambda operation,payload: {})
