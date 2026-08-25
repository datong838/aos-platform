from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic/versions/w7_001_profile_projected_cost_confirmation.py"
)
BUNDLE_ROOT = (
    Path(__file__).resolve().parents[4]
    / "bundles/candidates/ecommerce/solution.ecommerce.growth/1.4.0"
)


def test_w7_02_migration_extends_existing_tenant_authorities_without_apply():
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision: str | Sequence[str] | None = "w6_009"' in text
    assert "ALTER TABLE aip_profile_recommendation_revision" in text
    assert "projected_cost_ranges JSONB" in text
    assert "ALTER TABLE aip_profile_confirmation_receipt" in text
    assert "UNIQUE (org_id,project_id,idempotency_key)" in text
    assert "DISABLE ROW LEVEL SECURITY" not in text
    assert "CREATE TABLE" not in text


def test_w7_02_migration_module_imports_without_running_upgrade():
    spec = importlib.util.spec_from_file_location("w7_001", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "w7_001"
    assert module.down_revision == "w6_009"


def test_media_candidate_exports_fail_closed_cost_projection_contract():
    contract_path = BUNDLE_ROOT / "content/cost-projection-contracts/media.v1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    module = json.loads(
        (BUNDLE_ROOT / "content/workshops/ecommerce.media-studio.json").read_text(
            encoding="utf-8"
        )
    )

    assert module["impactCalculatorRefs"] == [
        "content/cost-projection-contracts/media.v1.json"
    ]
    assert contract["profiles"] == ["LITE", "STANDARD", "FULL"]
    assert contract["currencyPolicy"]["crossCurrencyAggregation"] is False
    assert contract["unknownPolicy"] == {
        "numericZeroForbidden": True,
        "confirmationBlocked": True,
    }
    assert "invoke_provider" in contract["forbiddenEffects"]
    assert "debit_hard_budget" in contract["forbiddenEffects"]
