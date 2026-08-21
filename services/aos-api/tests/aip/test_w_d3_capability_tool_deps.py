from aos_api.aip_capability_tool_deps import TOOL_ASSET_TYPE, tool_ref_for


def test_tool_ref_shape() -> None:
    ref = tool_ref_for("evidence-bundle-demo", 1, "b" * 64)
    assert ref.asset_type == TOOL_ASSET_TYPE
    assert ref.revision == 1
