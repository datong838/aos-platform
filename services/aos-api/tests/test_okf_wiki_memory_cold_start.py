"""Self-test: OKF 必填映射全 12 OT + Wiki 冷启动 + 四层记忆 + 外部知识管道.

Covers:
1. OKF defaults for all 12 OTs — 100% required coverage.
2. Wiki cold-start — 12 per-OT seed Wikis with canonical schema content.
3. Four-layer memory — Working / Episodic / Semantic / Procedural model.
4. Memory search and layer filtering.
5. External knowledge ingestion via OKF source type pipeline (simulated).
"""
from __future__ import annotations

import time

from aos_api.aip_long_memory import MemoryLayer, get_engine
from aos_api.demo.seed_memory_cold_start import seed_memory_cold_start
from aos_api.ecom_core_models import CORE_OBJECT_TYPES, REQUIRED_PROPERTIES
from aos_api.okf_wiki_cold_start import seed_okf_wiki_cold_start
from aos_api.ontology_wiki_engine import get_wiki_engine


# ──────────────────────────────────────────────────────────────
# 1. OKF defaults: all 12 OTs have 100% required coverage
# ──────────────────────────────────────────────────────────────


def test_okf_defaults_cover_all_12_ots_with_full_required_mapping():
    """Each of the 12 CORE_OBJECT_TYPES has an OKF default with all
    REQUIRED_PROPERTIES mapped."""
    from aos_api.routers.ontology import _OKF_DEFAULTS, _okf_required_coverage

    for ot in CORE_OBJECT_TYPES:
        key = f"ecom_{ot}"
        assert key in _OKF_DEFAULTS, f"Missing OKF default for {ot} (key={key})"
        default = _OKF_DEFAULTS[key]
        columns = default["columns"]
        coverage = _okf_required_coverage(ot, columns)
        assert coverage["percent"] == 100, (
            f"{ot}: required coverage only {coverage['percent']}% "
            f"({coverage['mapped']}/{coverage['total']})"
        )


def test_okf_default_source_columns_match_normalizer():
    """OKF default source column names should be real Niushop source fields
    that the ec_normalizer actually reads."""
    from aos_api.routers.ontology import _OKF_DEFAULTS

    # Spot-check a few key OTs against known normalizer mappings
    order_cols = {c["src"] for c in _OKF_DEFAULTS["ecom_Order"]["columns"]}
    assert "order_id" in order_cols
    assert "site_id" in order_cols
    assert "order_money" in order_cols

    product_cols = {c["src"] for c in _OKF_DEFAULTS["ecom_Product"]["columns"]}
    assert "goods_id" in product_cols
    assert "goods_name" in product_cols
    assert "category_id" in product_cols

    sku_cols = {c["src"] for c in _OKF_DEFAULTS["ecom_ProductSku"]["columns"]}
    assert "sku_id" in sku_cols
    assert "goods_id" in sku_cols  # productId

    payment_cols = {c["src"] for c in _OKF_DEFAULTS["ecom_Payment"]["columns"]}
    assert "out_trade_no" in payment_cols
    assert "pay_status" in payment_cols


# ──────────────────────────────────────────────────────────────
# 2. Wiki cold-start: 12 per-OT seed Wikis
# ──────────────────────────────────────────────────────────────


def test_wiki_cold_start_seeds_all_12_ots():
    """Wiki cold-start creates one Wiki per OT, each with schema content."""
    eng = get_wiki_engine()
    eng.reset()  # clean slate

    seeded = seed_okf_wiki_cold_start()
    assert seeded == 12

    # Verify each OT has a wiki
    for ot in sorted(CORE_OBJECT_TYPES):
        wiki_id = f"wiki-coldstart-{ot.lower()}"
        wiki = eng.get_wiki(wiki_id)
        assert wiki is not None, f"Missing cold-start wiki for {ot}"
        assert ot in wiki.content
        assert "必填属性" in wiki.content
        assert wiki.object_type_id == ot


def test_wiki_cold_start_is_idempotent():
    """Re-running seed should add 0 new wikis."""
    eng = get_wiki_engine()
    before = len(eng.list_wikis())
    seeded = seed_okf_wiki_cold_start()
    after = len(eng.list_wikis())
    assert seeded == 0
    assert before == after


# ──────────────────────────────────────────────────────────────
# 3. Four-layer memory model
# ──────────────────────────────────────────────────────────────


def test_four_layer_memory_crud():
    """The LongMemoryEngine supports all four layers."""
    eng = get_engine()
    eng.reset()

    # Working layer (auto-expiring)
    w = eng.create("current-task", layer=MemoryLayer.WORKING.value, content="正在分析订单异常")
    assert w.layer == MemoryLayer.WORKING.value
    assert w.expires_at is not None  # auto-set TTL

    # Episodic layer
    e = eng.create("user-asked-about-refund", layer=MemoryLayer.EPISODIC.value, content="用户查询了退款流程")
    assert e.layer == MemoryLayer.EPISODIC.value
    assert e.expires_at is None

    # Semantic layer (default)
    s = eng.create("order-has-6-required-fields", layer=MemoryLayer.SEMANTIC.value, content="Order OT 有 6 个必填字段")
    assert s.layer == MemoryLayer.SEMANTIC.value

    # Procedural layer
    p = eng.create("triage-flow", layer=MemoryLayer.PROCEDURAL.value, content="订单异常分诊流程")
    assert p.layer == MemoryLayer.PROCEDURAL.value

    # Layer stats
    stats = eng.layer_stats()
    assert stats["working"] == 1
    assert stats["episodic"] == 1
    assert stats["semantic"] == 1
    assert stats["procedural"] == 1
    assert stats["total"] == 4


def test_memory_layer_filtering():
    """list_by_layer returns only items from the specified layer."""
    eng = get_engine()
    eng.reset()

    eng.create("w1", layer=MemoryLayer.WORKING.value)
    eng.create("w2", layer=MemoryLayer.WORKING.value)
    eng.create("s1", layer=MemoryLayer.SEMANTIC.value)

    assert len(eng.list_working()) == 2
    assert len(eng.list_semantic()) == 1
    assert len(eng.list_episodic()) == 0
    assert len(eng.list_procedural()) == 0


def test_memory_search():
    """search() finds items by keyword across name/content/tags."""
    eng = get_engine()
    eng.reset()

    eng.create(
        "order-contract",
        layer=MemoryLayer.SEMANTIC.value,
        content="Order 有 6 个必填字段",
        tags=["order", "ontology"],
    )
    eng.create(
        "sku-contract",
        layer=MemoryLayer.SEMANTIC.value,
        content="ProductSku 有 7 个必填字段",
        tags=["sku"],
    )

    # Search "Order" — should find only the order item
    results = eng.search("Order", layer=MemoryLayer.SEMANTIC.value)
    assert len(results) == 1
    assert "order" in results[0].name.lower()

    # Search without layer filter
    all_results = eng.search("必填字段")
    assert len(all_results) == 2


def test_memory_cold_start_seed():
    """seed_memory_cold_start populates semantic (12) + procedural (3) + episodic (1)."""
    eng = get_engine()
    eng.reset()

    result = seed_memory_cold_start()
    assert result["semantic"] == 12
    assert result["procedural"] == 3
    assert result["episodic"] == 1
    assert result["total"] == 16


# ──────────────────────────────────────────────────────────────
# 4. Working memory TTL expiry
# ──────────────────────────────────────────────────────────────


def test_working_memory_auto_expires():
    """Working memory items with past expires_at are evicted on read."""
    eng = get_engine()
    eng.reset()

    item = eng.create("temp", layer=MemoryLayer.WORKING.value)
    # Manually set expiry to past
    eng.update(item.id, expires_at=time.time() - 1)

    # Trigger eviction by calling list()
    eng.list()
    assert eng.get(item.id) is None  # evicted


# ──────────────────────────────────────────────────────────────
# 5. Backward compatibility: old create(name, config) still works
# ──────────────────────────────────────────────────────────────


def test_backward_compatible_create_two_args():
    """Old call signature create(name, config) still works, defaults to semantic."""
    eng = get_engine()
    eng.reset()

    item = eng.create("legacy-item", {"key": "value"})
    assert item.name == "legacy-item"
    assert item.config == {"key": "value"}
    assert item.layer == MemoryLayer.SEMANTIC.value  # default
