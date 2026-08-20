from aos_api.aip_function_tool_exits import (
    FN_ECHO_BLOCKED_REASON,
    invoke_function_tool,
    list_function_tool_exits,
)
from aos_api.tenant_scope import TenantScope


def test_fn_echo_always_blocked():
    items = list_function_tool_exits(TenantScope("org-org", "dev-project"), graphs=[])
    echo = next(i for i in items if i["id"] == "fn.echo")
    assert echo["blocked"] is True
    assert "published Logic" in echo["blockedReason"] or "W-T6" in echo["blockedReason"]
    inv = invoke_function_tool("fn.echo")
    assert inv["ok"] is False
    assert FN_ECHO_BLOCKED_REASON in inv["result"]["message"]


def test_published_logic_projected():
    class Snap:
        id = "g-demo"
        name = "Demo Logic"
        published_version = 2
        revision = 5

    class Draft:
        id = "g-draft"
        name = "Draft"
        published_version = 0
        revision = 1

    items = list_function_tool_exits(
        TenantScope("org-org", "dev-project"), graphs=[Snap(), Draft()]
    )
    ids = [i["id"] for i in items]
    assert "fn.echo" in ids
    assert "fn.logic.g-demo" in ids
    assert "fn.logic.g-draft" not in ids
    pub = next(i for i in items if i["id"] == "fn.logic.g-demo")
    assert pub["blocked"] is False
    assert pub["publishedVersion"] == 2
