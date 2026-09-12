import importlib.util
from pathlib import Path
from unittest.mock import MagicMock
import pytest

SPEC = importlib.util.spec_from_file_location("schema_receipts", Path(__file__).resolve().parents[4] / "scripts/a0v_ecommerce_schema_receipts.py")
M = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(M)


def test_schema_successor_uses_exact_new_profile_and_keeps_old_roots():
    old = M.select_successor()
    v17 = M.select_successor(successor_1_7=True)
    fresh = M.select_successor(niushop_1_4=True)
    assert len({item.NEW_ROOT for item in (old, v17, fresh)}) == 3
    assert v17.VERSIONS['platform.ecommerce.niushop'] == '1.3.0'
    assert fresh.VERSIONS['platform.ecommerce.niushop'] == '1.4.0'
    assert fresh.legacy()._builder().RUNTIME_CASES[1][2] == '1.4.0'
    with pytest.raises(ValueError):
        M.select_successor(successor_1_7=True, niushop_1_4=True)


@pytest.mark.parametrize("present", [True, False])
def test_schema_requires_physical_relation(present):
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [{"version_num": "head"}]
    conn.execute.return_value.fetchone.return_value = {"present": present}
    doc = {"noPackageOwnedMigration": True, "alembicRevision": "base", "requiredRelations": ["public.example"]}
    if present:
        M.verify_physical(conn, doc, lambda _: {"head", "base"})
    else:
        with pytest.raises(ValueError, match="missing"):
            M.verify_physical(conn, doc, lambda _: {"head", "base"})


def test_unapplied_revision_is_not_inferred_from_tables():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [{"version_num": "head"}]
    with pytest.raises(ValueError, match="not installed"):
        M.verify_physical(conn, {"noPackageOwnedMigration": True, "alembicRevision": "future"}, lambda _: {"head"})
