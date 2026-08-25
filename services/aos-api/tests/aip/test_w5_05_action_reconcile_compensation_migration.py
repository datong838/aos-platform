"""Static safety checks for the W5-05 reconciliation migration."""
from pathlib import Path


MIGRATION = Path(__file__).parents[2] / "alembic/versions/w5_004_action_reconcile_compensation.py"


def test_w5_004_is_tenant_scoped_append_only_and_safe_to_downgrade() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    for table in (
        "aip_action_reconcile_attempt",
        "aip_action_manual_reconcile_case",
        "aip_action_manual_reconcile_decision_receipt",
        "aip_action_compensation_policy_revision",
        "aip_action_compensation_intent",
        "aip_action_compensation_link",
    ):
        assert f"CREATE TABLE {table}" in text
        assert f'_scope(table, update=update)' in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "maker_id <> checker_id" in text
    assert "guard_aip4_append_only()" in text
    assert "cannot downgrade w5_004 with reconciliation facts" in text
    assert "provider_outcome" in text
    assert "reconciliation_status" in text
    assert "CompensationPolicy" not in text or "aip_action_compensation_policy_revision" in text
