from pathlib import Path


def test_w5_005_migration_has_endpoint_directory_rls_replay_and_fact_guard() -> None:
    api_root = Path(__file__).resolve().parents[2]
    text = (api_root / "alembic/versions/w5_005_action_webhook_inbox.py").read_text()
    for table in (
        "aip_action_webhook_endpoint_directory",
        "aip_action_webhook_endpoint_revision",
        "aip_action_webhook_inbox_receipt",
        "aip_action_webhook_replay_key",
        "aip_action_webhook_observation",
        "aip_action_webhook_reducer_view",
        "aip_action_webhook_case",
    ):
        assert f"CREATE TABLE {table}" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "guard_aip4_append_only()" in text
    assert "W5_005_FACTS_EXIST" in text
    assert "raw_body" not in text
    assert "secret_ref TEXT" in text
