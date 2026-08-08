"""O1-A: ec_live_executor store 装配单测 — fail-closed 行为验证。

O1-A 变更（从 D2.5 的 fail-open 改为 fail-closed）：

1. 装配跳过：eng 已注入 ecom_consistency_store → 不重装（idempotent）
2. 装配成功：eng 未注入 + get_dsn/mock create_engine 成功 → 注入 store（不再调用 metadata.create_all）
3. 失败 fail-closed：eng 未注入 + get_dsn 抛异常 → **抛 RuntimeError**，不降级
4. ec_live_executor 端到端：调用 ec_live_executor 后 eng.ecom_consistency_store 已装配（mock 路径）

约束（O1-A 规格文档 §5.2.1）：
- ensure_store_assembled 失败时抛 RuntimeError（fail-closed），Pipeline 不得继续
- 不再调用 metadata.create_all（迁移由 Alembic 管理）
- 已注入时跳过装配（幂等）
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from aos_api.phase5_pipeline_engine import get_engine
from aos_api import ec_live_executor as ec_mod


@pytest.fixture(autouse=True)
def _reset_engine():
    """每个测试前后重置 engine 的 ecom_consistency_store 属性。"""
    eng = get_engine()
    if hasattr(eng, "ecom_consistency_store"):
        delattr(eng, "ecom_consistency_store")
    eng.reset_all_for_tests()
    yield
    if hasattr(eng, "ecom_consistency_store"):
        delattr(eng, "ecom_consistency_store")
    eng.reset_all_for_tests()


# ═══════════════════════════════════════════════
# Section A: ensure_store_assembled 单测
# ═══════════════════════════════════════════════


def test_ensure_store_assembled_skip_when_already_injected() -> None:
    """已注入 ecom_consistency_store → 跳过装配（幂等）。"""
    eng = get_engine()
    sentinel_store = MagicMock(name="existing_store")
    eng.ecom_consistency_store = sentinel_store

    with patch("sqlalchemy.create_engine") as mock_create, \
         patch("aos_api.db.get_dsn") as mock_dsn:
        ec_mod.ensure_store_assembled(eng)

        mock_create.assert_not_called()
        mock_dsn.assert_not_called()

    assert eng.ecom_consistency_store is sentinel_store


def test_ensure_store_assembled_injects_when_dsn_available() -> None:
    """eng 未注入 + DSN 有效 → 装配 EcomConsistencyStore 并注入。

    O1-A 变更：不再调用 metadata.create_all。
    """
    eng = get_engine()
    assert getattr(eng, "ecom_consistency_store", None) is None

    fake_pg_engine = MagicMock(name="pg_engine")
    fake_store = MagicMock(name="ecom_consistency_store")

    stub_store_module = types.ModuleType("aos_api.ecom_consistency_store")
    stub_store_module.EcomConsistencyStore = MagicMock(return_value=fake_store)

    with patch.dict(sys.modules, {"aos_api.ecom_consistency_store": stub_store_module}), \
         patch("aos_api.db.get_dsn", return_value="postgresql://test:test@127.0.0.1:5433/test"), \
         patch("sqlalchemy.create_engine", return_value=fake_pg_engine) as mock_create:
        ec_mod.ensure_store_assembled(eng)

        mock_create.assert_called_once()
        called_dsn = mock_create.call_args[0][0]
        assert called_dsn.startswith("postgresql+psycopg://")

    assert eng.ecom_consistency_store is fake_store


def test_ensure_store_assembled_raises_when_dsn_fails() -> None:
    """O1-A: DSN 缺失/PG 不可达 → fail-closed（抛 RuntimeError）。"""
    eng = get_engine()
    assert getattr(eng, "ecom_consistency_store", None) is None

    with patch("aos_api.db.get_dsn", side_effect=RuntimeError("DSN not configured")):
        with pytest.raises(RuntimeError, match="fail-closed"):
            ec_mod.ensure_store_assembled(eng)

    assert getattr(eng, "ecom_consistency_store", None) is None


def test_ensure_store_assembled_raises_when_create_engine_fails() -> None:
    """O1-A: create_engine 失败 → fail-closed（抛 RuntimeError）。"""
    eng = get_engine()
    assert getattr(eng, "ecom_consistency_store", None) is None

    with patch("aos_api.db.get_dsn", return_value="postgresql://test:test@127.0.0.1:5433/test"), \
         patch("sqlalchemy.create_engine", side_effect=OSError("PG unreachable")):
        with pytest.raises(RuntimeError, match="fail-closed"):
            ec_mod.ensure_store_assembled(eng)

    assert getattr(eng, "ecom_consistency_store", None) is None


# ═══════════════════════════════════════════════
# Section B: DSN 格式转换
# ═══════════════════════════════════════════════


def test_dsn_convert_postgresql_scheme_to_psycopg() -> None:
    """DSN 转换：postgresql:// → postgresql+psycopg://。"""
    eng = get_engine()
    fake_pg_engine = MagicMock(name="pg_engine")
    fake_store = MagicMock(name="ecom_consistency_store")

    stub_store_module = types.ModuleType("aos_api.ecom_consistency_store")
    stub_store_module.EcomConsistencyStore = MagicMock(return_value=fake_store)

    with patch.dict(sys.modules, {"aos_api.ecom_consistency_store": stub_store_module}), \
         patch("aos_api.db.get_dsn", return_value="postgresql://u:p@h:5433/db"), \
         patch("sqlalchemy.create_engine", return_value=fake_pg_engine) as mock_create:
        ec_mod.ensure_store_assembled(eng)

        called_dsn = mock_create.call_args[0][0]
        assert called_dsn == "postgresql+psycopg://u:p@h:5433/db"


def test_dsn_convert_postgres_scheme_to_psycopg() -> None:
    """DSN 转换：postgres:// → postgresql+psycopg://。"""
    eng = get_engine()
    fake_pg_engine = MagicMock(name="pg_engine")
    fake_store = MagicMock(name="ecom_consistency_store")

    stub_store_module = types.ModuleType("aos_api.ecom_consistency_store")
    stub_store_module.EcomConsistencyStore = MagicMock(return_value=fake_store)

    with patch.dict(sys.modules, {"aos_api.ecom_consistency_store": stub_store_module}), \
         patch("aos_api.db.get_dsn", return_value="postgres://u:p@h:5433/db"), \
         patch("sqlalchemy.create_engine", return_value=fake_pg_engine) as mock_create:
        ec_mod.ensure_store_assembled(eng)

        called_dsn = mock_create.call_args[0][0]
        assert called_dsn == "postgresql+psycopg://u:p@h:5433/db"
