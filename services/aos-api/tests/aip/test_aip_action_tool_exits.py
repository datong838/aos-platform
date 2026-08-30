from aos_api.aip_action_tool_exits import (
    ACTION_BLOCKED_REASON,
    invoke_action_tool,
    list_action_tool_exits,
)


def test_action_close_requires_draft():
    items = list_action_tool_exits()
    assert len(items) == 1
    assert items[0]["id"] == "action.close"
    assert items[0]["requiresDraft"] is True
    assert items[0]["blocked"] is True
    inv = invoke_action_tool(
        "action.close",
        payload={"objectType": "WorkOrder", "objectId": "work-order-1"},
    )
    assert inv["ok"] is False
    assert inv["requiresDraft"] is True
    assert inv["productionWritten"] is False
    assert inv["proposal"] == {
        "actionTypeId": "CloseWorkOrder",
        "objectType": "WorkOrder",
        "objectId": "work-order-1",
        "proposed": {},
        "status": "proposal",
    }
    assert inv["controlChain"] == ["proposal", "draft", "approval", "receipt"]
    assert inv["nextStage"] == "draft"
    assert ACTION_BLOCKED_REASON in inv["result"]["message"]
