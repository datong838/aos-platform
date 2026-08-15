from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg import DatabaseError

from aos_api.db import connect

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "bind1_002_provider_instance_ref.py"


def _config() -> Config:
    config = Config(ROOT / "alembic.ini")
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return config


def test_00_bind1_provider_correction_is_single_head_and_does_not_rewrite_rows():
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "bind1_002"' in text
    assert 'down_revision: str | Sequence[str] | None = "bind1_001"' in text
    assert "ProviderInstanceRevision" in text
    assert "UPDATE aip_capability_binding" not in text
    command.upgrade(_config(), "head")


def test_provider_instance_ref_is_accepted_and_legacy_provider_kind_is_rejected():
    with connect() as conn:
        conn.execute("SAVEPOINT bind1_provider_instance")
        conn.execute(
            """INSERT INTO aip_capability_binding
               (org_id,project_id,binding_id,capability_ref,secret_ref,health,
                network_policy_revision,quota_policy_revision,timeout_ms,
                max_concurrency,status,version,provider_ref)
               VALUES ('dev-org','dev-project','bind1-valid-provider',
                '{"assetType":"CapabilityRevision"}'::jsonb,
                'secret://pytest/provider','unknown','network','quota',1000,1,
                'provisioning',1,
                '{"assetType":"ProviderInstanceRevision","assetId":"provider-1",
                  "revision":1,"contentHash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}'::jsonb)"""
        )
        with pytest.raises(DatabaseError):
            conn.execute(
                """UPDATE aip_capability_binding
                   SET provider_ref='{"assetType":"ProviderRevision"}'::jsonb
                   WHERE org_id='dev-org' AND project_id='dev-project'
                     AND binding_id='bind1-valid-provider'"""
            )
        conn.execute("ROLLBACK TO SAVEPOINT bind1_provider_instance")
        conn.execute("RELEASE SAVEPOINT bind1_provider_instance")
        conn.rollback()
