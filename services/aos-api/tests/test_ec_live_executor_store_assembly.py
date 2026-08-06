"""D2.5: ec_live_executor store 装配单测 — 装配/跳过/失败降级。

覆盖 ensure_store_assembled 函数（D2.5 缺口 2 修复）：

1. 装配跳过：eng 已注入 ecom_consistency_store → 不重装（idempotent）
2. 装配成功：eng 未注入 + get_dsn/mock create_engine 成功 → 注入 store
3. 失败降级：eng 未注入 + get_dsn 抛异常 → 记 warning，不抛异常，eng 保持无 store
4. ec_live_executor 端到端：调用 ec_live_executor 后 eng.ecom_consistency_store 已装配（mock 路径）

约束（D2.5 规格文档 §3.2）：
- ensure_store_assembled 失败时降级为骨架行为（sink_to_ot 自身有零计数分支，不抛异常）
- 已注入时跳过装配（幂等）
- 不在 PipelineEngine.__new__ 里装配（避免单例依赖 db engine，破坏单测）
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from aos_api.phase5_pipeline_engine import get_engine
from aos_api import ec_live_executor as ec_mod


@pytest.fixture(autouse=True)
def _reset_engine():
    """每个测试前后重置 engine 的 ecom_consistency_store 属性。"""
    eng = get_engine()
    # 重置：删除 ecom_consistency_store 属性（如已设置）
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
    """G2-1 已注入 ecom_consistency_store → 跳过装配（幂等）。

    验证：eng.ecom_consistency_store 已存在时，ensure_store_assembled
    不调用 create_engine / get_dsn，直接返回。
    """
    eng = get_engine()
    sentinel_store = MagicMock(name="existing_store")
    eng.ecom_consistency_store = sentinel_store

    # mock create_engine / get_dsn 确保不被调用
    with patch("sqlalchemy.create_engine") as mock_create, \
         patch("aos_api.db.get_dsn") as mock_dsn:
        ec_mod.ensure_store_assembled(eng)

        mock_create.assert_not_called()
        mock_dsn.assert_not_called()

    # 已注入的 store 不被覆盖
    assert eng.ecom_consistency_store is sentinel_store


def test_ensure_store_assembled_injects_when_dsn_available() -> None:
    """G2-2 eng 未注入 + DSN 有效 → 装配 EcomConsistencyStore 并注入。

    验证：eng.ecom_consistency_store 未设置时，ensure_store_assembled
    调用 create_engine(dsn) + EcomConsistencyStore(pg_engine) → setattr 到 eng。
    """
    eng = get_engine()
    assert getattr(eng, "ecom_consistency_store", None) is None

    # mock 依赖
    fake_pg_engine = MagicMock(name="pg_engine")
    fake_store = MagicMock(name="ecom_consistency_store")
    fake_metadata = MagicMock(name="ecom_metadata")

    # 注入 stub 模块到 sys.modules（避免真实 import ecom_consistency_store）
    stub_store_module = types.ModuleType("aos_api.ecom_consistency_store")
    stub_store_module.EcomConsistencyStore = MagicMock(return_value=fake_store)
    stub_store_module.metadata = fake_metadata

    with patch.dict(sys.modules, {"aos_api.ecom_consistency_store": stub_store_module}), \
         patch("aos_api.db.get_dsn", return_value="postgresql://test:test@127.0.0.1:5433/test"), \
         patch("sqlalchemy.create_engine", return_value=fake_pg_engine) as mock_create:
        ec_mod.ensure_store_assembled(eng)

        # 验证 create_engine 被调用 + DSN 转换为 sqlalchemy 格式
        mock_create.assert_called_once()
        called_dsn = mock_create.call_args[0][0]
        assert called_dsn.startswith("postgresql+psycopg://"), (
            f"DSN 应转换为 sqlalchemy+psycopg 格式，实际: {called_dsn}"
        )
        # 验证 metadata.create_all 被调用
        fake_metadata.create_all.assert_called_once_with(fake_pg_engine)

    # 验证 store 已注入到 eng
    assert eng.ecom_consistency_store is fake_store


def test_ensure_store_assembled_degrades_when_dsn_raises() -> None:
    """G2-3 DSN 缺失/PG 不可达 → 失败降级（不抛异常，eng 保持无 store）。

    验证：get_dsn 抛异常或 create_engine 失败时，ensure_store_assembled
    不抛异常，eng.ecom_consistency_store 保持未注入状态。
    """
    eng = get_engine()
    assert getattr(eng, "ecom_consistency_store", None) is None

    with patch("aos_api.db.get_dsn", side_effect=RuntimeError("DSN not configured")):
        # 不抛异常
        ec_mod.ensure_store_assembled(eng)

    # eng 仍未注入 store（降级行为）
    assert getattr(eng, "ecom_consistency_store", None) is None


def test_ensure_store_assembled_degrades_when_create_engine_fails() -> None:
    """G2-3b create_engine 失败（PG 不可达）→ 失败降级。

    验证：sqlalchemy.create_engine 抛异常时，ensure_store_assembled
    不抛异常，eng.ecom_consistency_store 保持未注入状态。
    """
    eng = get_engine()
    assert getattr(eng, "ecom_consistency_store", None) is None

    with patch("aos_api.db.get_dsn", return_value="postgresql://test:test@127.0.0.1:5433/test"), \
         patch("sqlalchemy.create_engine", side_effect=OSError("PG unreachable")):
        ec_mod.ensure_store_assembled(eng)

    assert getattr(eng, "ecom_consistency_store", None) is None


# ═══════════════════════════════════════════════
# Section B: DSN 格式转换
# ═══════════════════════════════════════════════


def test_dsn_convert_postgresql_scheme_to_psycopg() -> None:
    """DSN 转换：postgresql:// → postgresql+psycopg://。

    验证 sqlalchemy 2.x 需要 psycopg3 driver 前缀（postgresql+psycopg://）。
    """
    eng = get_engine()
    fake_pg_engine = MagicMock(name="pg_engine")
    fake_store = MagicMock(name="ecom_consistency_store")
    fake_metadata = MagicMock(name="ecom_metadata")

    stub_store_module = types.ModuleType("aos_api.ecom_consistency_store")
    stub_store_module.EcomConsistencyStore = MagicMock(return_value=fake_store)
    stub_store_module.metadata = fake_metadata

    with patch.dict(sys.modules, {"aos_api.ecom_consistency_store": stub_store_module}), \
         patch("aos_api.db.get_dsn", return_value="postgresql://u:p@h:5433/db"), \
         patch("sqlalchemy.create_engine", return_value=fake_pg_engine) as mock_create:
        ec_mod.ensure_store_assembled(eng)

        called_dsn = mock_create.call_args[0][0]
        assert called_dsn == "postgresql+psycopg://u:p@h:5433/db", (
            f"postgresql:// 应转为 postgresql+psycopg://，实际: {called_dsn}"
        )


def test_dsn_convert_postgres_scheme_to_psycopg() -> None:
    """DSN 转换：postgres:// → postgresql+psycopg://。"""
    eng = get_engine()
    fake_pg_engine = MagicMock(name="pg_engine")
    fake_store = MagicMock(name="ecom_consistency_store")
    fake_metadata = MagicMock(name="ecom_metadata")

    stub_store_module = types.ModuleType("aos_api.ecom_consistency_store")
    stub_store_module.EcomConsistencyStore = MagicMock(return_value=fake_store)
    stub_store_module.metadata = fake_metadata

    with patch.dict(sys.modules, {"aos_api.ecom_consistency_store": stub_store_module}), \
         patch("aos_api.db.get_dsn", return_value="postgres://u:p@h:5433/db"), \
         patch("sqlalchemy.create_engine", return_value=fake_pg_engine) as mock_create:
        ec_mod.ensure_store_assembled(eng)

        called_dsn = mock_create.call_args[0][0]
        assert called_dsn == "postgresql+psycopg://u:p@h:5433/db", (
            f"postgres:// 应转为 postgresql+psycopg://，实际: {called_dsn}"
        )
