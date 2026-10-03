"""Legacy in-memory Tool HTTP routes cannot issue formal ToolBinding source."""

from aos_api.main import app


def test_legacy_tool_http_routes_are_not_exposed():
    exposed = {(method.upper(), path)
               for path, operations in app.openapi()["paths"].items()
               for method in operations}
    forbidden = {
        ("POST", "/v1/tools/register"),
        ("POST", "/v1/tools/invoke"),
        ("GET", "/v1/tools/{tool_id}"),
        ("DELETE", "/v1/tools/{tool_id}"),
        ("GET", "/v1/tools"),
        ("GET", "/v1/capabilities"),
        ("POST", "/v1/capabilities"),
        ("POST", "/v1/capabilities/{cap_id}/tools"),
        ("GET", "/v1/capabilities/{cap_id}/tools"),
    }
    assert not (exposed & forbidden)
