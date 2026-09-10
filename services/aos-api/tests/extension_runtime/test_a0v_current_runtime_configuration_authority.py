"""Pure fail-closed checks for the A0-V configuration authority executor."""

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_current_runtime_configuration_authority.py"
SPEC = importlib.util.spec_from_file_location("a0v_configuration_authority", SCRIPT)
assert SPEC and SPEC.loader
AUTHORITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUTHORITY)


def test_preflight_has_fixed_scope_ids_and_zero_external_effects():
    result = AUTHORITY.run(AUTHORITY.parse_args([]))
    assert result["outcome"] == "PREFLIGHT_GREEN"
    assert result["scope"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert set(result["authorityIds"]) == {
        "egress", "data", "network", "budget", "quota", "budgetPolicy", "runtimePolicy"
    }
    assert result["effects"] == {
        "providerInvocationCount": 0,
        "externalPublicationCount": 0,
    }


def test_apply_requires_exact_isolated_database_before_loading_connector(monkeypatch):
    monkeypatch.setattr(
        AUTHORITY,
        "_load_first_installer",
        lambda: (_ for _ in ()).throw(AssertionError("connector loaded")),
    )
    with pytest.raises(AUTHORITY.ConfigurationAuthorityBlocked) as captured:
        AUTHORITY.run(AUTHORITY.parse_args(["--apply", "--database-name", "aos_meta"]))
    assert captured.value.code == "EXPLICIT_ISOLATED_DATABASE_REQUIRED"


def test_policy_window_and_ids_are_replay_stable():
    assert AUTHORITY.WINDOW_START.isoformat() == "2026-09-10T00:00:00+00:00"
    assert AUTHORITY.WINDOW_END.isoformat() == "2027-09-10T00:00:00+00:00"
    assert len(set(AUTHORITY.IDS.values())) == len(AUTHORITY.IDS)
    assert AUTHORITY.APPROVAL_REF == "approval:AOS-000573:A0-V-local-readonly"
