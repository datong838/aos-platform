from pathlib import Path


def test_aip7_capacity_migration_is_tenant_safe_exact_and_append_only() -> None:
    path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "aip7_002_model_capacity_reservation.py"
    )
    text = path.read_text(encoding="utf-8")
    assert 'down_revision: str | Sequence[str] | None = "w2_002"' in text
    for table in (
        "aip_model_price_snapshot_head",
        "aip_model_price_snapshot_revision",
        "aip_model_capacity_pool_head",
        "aip_model_capacity_pool_revision",
        "aip_model_capacity_reservation",
        "aip_model_capacity_event",
    ):
        assert table in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "guard_aip4_append_only" in text
    assert "capacity reservation identity is immutable" in text
    assert "aip_model_capacity_one_active_exact_idx" in text
    assert "capacity_limits" not in text
    assert "capacity_usage" not in text
