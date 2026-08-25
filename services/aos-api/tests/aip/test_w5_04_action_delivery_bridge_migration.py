"""W5-04 migration safety contract."""
from __future__ import annotations

from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "w5_003_action_delivery_bridge.py"
)


def test_w5_003_freezes_tenant_rls_append_only_and_safe_downgrade() -> None:
    source = MIGRATION.read_text()
    for table in (
        "aip_action_execution_attempt",
        "aip_action_dispatch_outbox",
        "aip_action_response_artifact",
        "aip_action_settlement_request",
        "aip_action_lineage_projection_request",
    ):
        assert f"CREATE TABLE {table}" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "guard_aip4_append_only()" in source
    assert "cannot downgrade w5_003 with Action delivery facts" in source
    assert "unknown" in source
    assert "receipt_content_hash" in source
