from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
RETIREMENT = ROOT / "scripts/a0v_au_stale_health_retirement.py"
GUARD = ROOT / "scripts/a0v_au_stale_health_guard.py"


def test_au_stale_health_retirement_locks_exact_safe_boundary():
    source = RETIREMENT.read_text(encoding="utf-8")
    assert 'AU_ID = "eddc89f9-1e91-4e42-be4e-7d81dc941c1d"' in source
    assert 'GENERATION = "01a5eb0a-f41f-40f7-ba00-b5db23a7806f"' in source
    assert 'STALE_ATTEMPTS = ()' in source
    assert '"revision": 7, "execution_epoch": 4' in source
    assert 'row["revision"] != 114' in source
    assert 'row["cutover_group_revision"] != 141' in source
    assert 'operation["expected_binding_revision"] != 7' in source
    assert "require_released_owner_settlement" in source


def test_au_retirement_uses_owner_and_guard_is_read_only():
    retirement = RETIREMENT.read_text(encoding="utf-8")
    guard = GUARD.read_text(encoding="utf-8")
    assert "RuntimeDisableConsumer" in retirement
    assert "run_definition" not in retirement + guard
    assert "UPDATE extension_operation_dispatch_binding" not in retirement + guard
    assert "INSERT " not in guard and "UPDATE " not in guard and "DELETE " not in guard
