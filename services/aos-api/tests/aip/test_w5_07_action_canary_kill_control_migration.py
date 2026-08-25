"""Static safety checks for the W5-07 Action Canary/Kill migration."""
from pathlib import Path

MIGRATION = Path(__file__).parents[2] / "alembic/versions/w5_006_action_canary_kill_control.py"


def test_w5_006_is_tenant_scoped_append_only_idempotent_and_simulation_only() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    for table in (
        "aip_action_kill_policy_revision",
        "aip_action_kill_policy_approval_event",
        "aip_action_kill_policy_command_receipt",
        "aip_action_canary_plan_revision",
        "aip_action_canary_plan_approval_event",
        "aip_action_kill_drill_receipt",
    ):
        assert f"CREATE TABLE {table}" in text
        assert f'"{table}"' in text
    assert "CREATE POLICY {table}_tenant_scope" in text
    assert "CREATE TRIGGER {table}_append_only" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "idempotency_key" in text
    assert "CHECK (simulation_only)" in text
    assert "W5_006_FACTS_EXIST" in text
    assert "max_quantity BETWEEN 1 AND 10" in text
