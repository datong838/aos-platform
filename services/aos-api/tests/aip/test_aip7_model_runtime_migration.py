from pathlib import Path


def test_aip7_migration_is_additive_tenant_safe_and_append_only() -> None:
    path = Path(__file__).parents[2] / "alembic" / "versions" / "aip7_001_model_runtime_authority.py"
    text = path.read_text(encoding="utf-8")
    assert 'down_revision: str | Sequence[str] | None = "w2_001"' in text
    for kind in ("provider_instance", "registered_model", "runtime_policy", "model_route"):
        assert kind in text
    assert "aip_provider_health_observation" in text
    assert "aip_model_runtime_receipt" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "SELECT,INSERT" in text
    assert "228ti5b1" not in text
