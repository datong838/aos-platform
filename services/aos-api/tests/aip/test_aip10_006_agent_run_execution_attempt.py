from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "aip10_006_agent_run_execution_attempt.py"


def test_execution_attempt_migration_is_linear_additive_and_tenant_scoped() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "aip10_006"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip10_005"' in text
    assert "CREATE TABLE aip_agent_run_execution_attempt" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "REFERENCES aip_agent_run(org_id,project_id,agent_run_id)" in text
    assert "DELETE FROM" not in text


def test_execution_attempt_migration_enforces_unknown_and_success_evidence() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert "status IN ('prepared','invoking','succeeded','failed','unknown')" in text
    assert "jsonb_array_length(usage_receipt_ids)>0" in text
    assert "output_artifact_ref IS NOT NULL" in text
    assert "status IN ('failed','unknown')" in text
    assert "NULLIF(reason_code,'') IS NOT NULL" in text


def test_execution_attempt_identity_and_idempotency_are_immutable() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert "UNIQUE(org_id,project_id,idempotency_key)" in text
    assert "UNIQUE(org_id,project_id,agent_run_id,attempt_no)" in text
    assert "guard_aip10_agent_run_attempt_identity" in text
    assert "request_hash ~ '^[0-9a-f]{64}$'" in text
    assert "prompt" not in text.lower()
    assert "answer" not in text.lower()
