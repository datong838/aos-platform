from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
import a0v_w5a_governance_clone as clone


@pytest.mark.parametrize("table", ["ecommerce_order", "pipeline_source", "aip_eval_run", "twa_other"])
def test_non_governance_table_is_rejected(table):
    with pytest.raises(ValueError, match="OUTSIDE_GOVERNANCE_ALLOWLIST"):
        clone.require_table(table)


def test_scope_is_exact_and_never_cross_tenant():
    assert clone.scope_clause("twa_org") == ("id=%s", ("org-org",))
    assert clone.scope_clause("aip_model_governance_policy_revision") == (
        "org_id=%s AND project_id=%s", ("org-org", "dev-project"))


def test_prepare_refuses_existing_state_before_any_connect(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("existing state must stop before database access")
    monkeypatch.setattr(clone, "database_connect", forbidden)
    with pytest.raises(ValueError, match="STATE_ALREADY_EXISTS"):
        clone.prepare(tmp_path)


def test_preservation_requires_prepared_and_applied_clone(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("unprepared preservation must not open a database")
    monkeypatch.setattr(clone, "database_connect", forbidden)
    with pytest.raises(ValueError, match="PRESERVATION_BOUNDARY_INVALID"):
        clone.preserve_main(tmp_path)
