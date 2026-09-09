from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from aos_api import ec_source_adapter as adapter
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 9, 9, tzinfo=UTC)


def setup(monkeypatch, rows, *, config=None, failure=None, spec_id="niushop.product-observation/v1"):
    events = []
    times = iter((NOW, NOW + timedelta(seconds=2)))
    monkeypatch.setattr(adapter, "_read_observation_clock", lambda: (events.append("clock"), next(times))[1])
    monkeypatch.setattr(adapter, "_query_meta_source_props", lambda source, scope: {"test": True})

    class Runtime:
        def __init__(self, props):
            assert props == {"test": True}
        def __enter__(self):
            events.append("connect")
            return self
        def __exit__(self, *_):
            events.append("close")
        def read_rows(self, table, **kwargs):
            assert table == "ns_goods" and kwargs == {"limit": 101, "where_equals": {"site_id": 1}}
            events.append("read")
            if failure:
                raise failure
            return rows

    monkeypatch.setattr(adapter, "JdbcConnectorRuntime", Runtime)
    cfg = {"source_id": "source-1", "table": "ns_goods", "site_filter": "site_id=1"}
    cfg.update(config or {})
    node = SimpleNamespace(id="source-node", node_type="source", config=cfg)
    return events, lambda: adapter.fetch_source_rows_observed(
        nodes=[node], node_id="source-node", scope=SCOPE,
        spec_id=spec_id)


def test_actual_interval_public_projection_and_local_counts(monkeypatch):
    monkeypatch.setitem(adapter._SOFT_DELETE_COUNTS, ("existing", "source-node"), 7)
    before = dict(adapter._SOFT_DELETE_COUNTS)
    events, fetch = setup(monkeypatch, [
        {"goods_id": 1, "site_id": 1, "goods_name": "商品", "create_time": 0,
         "mobile": "private", "unexpected_secret": "never-keep"},
        {"goods_id": 2, "site_id": 1, "is_delete": 1},
    ])
    rows, observation = fetch()
    assert events == ["connect", "clock", "read", "clock", "close"]
    assert rows == [{"goods_id": 1, "site_id": 1, "goods_name": "商品", "create_time": None}]
    assert (observation.fetched_count, observation.excluded_count, observation.retained_count) == (2, 1, 1)
    assert observation.read_started_at == NOW
    assert observation.read_finished_at == NOW + timedelta(seconds=2)
    observation.verify_rows(rows)
    assert adapter._SOFT_DELETE_COUNTS == before
    assert "private" not in observation.model_dump_json()


@pytest.mark.parametrize("count", [0, 100, 101])
def test_complete_bound_before_cleaning(monkeypatch, count):
    _, fetch = setup(monkeypatch, [{"site_id": 1, "goods_id": n + 1, "is_delete": 1} for n in range(count)])
    if count == 101:
        with pytest.raises(ValueError, match="limit"):
            fetch()
    else:
        rows, observation = fetch()
        assert rows == [] and observation.fetched_count == count


@pytest.mark.parametrize("config", [{"site_filter": "status=1"}, {"site_filter": ""},
    {"site_filter": "site_id=1 AND status=1"}, {"site_filter": "site_id='1'"},
    {"table": "ns_member"}, {"cursor": {"watermark": 1}}, {"source_id": ""}])
def test_unbounded_or_wrong_source_spec_rejected_before_read(monkeypatch, config):
    events, fetch = setup(monkeypatch, [], config=config)
    with pytest.raises(ValueError):
        fetch()
    assert events == []


def test_failed_read_never_returns_observation(monkeypatch):
    events, fetch = setup(monkeypatch, [], failure=RuntimeError("read failed"))
    with pytest.raises(RuntimeError, match="read failed"):
        fetch()
    assert events == ["connect", "clock", "read", "close"]


def test_scope_drift_in_returned_rows_is_rejected(monkeypatch):
    _, fetch = setup(monkeypatch, [{"site_id": 2, "goods_id": 1}])
    with pytest.raises(ValueError, match="scope"):
        fetch()


@pytest.mark.parametrize("scope,spec_id", [(None, "niushop.product-observation/v1"),
    (SCOPE, "unknown")])
def test_missing_scope_and_unknown_spec_fail_before_source_access(monkeypatch, scope, spec_id):
    def unexpected(*_, **__):
        raise AssertionError("source must not be accessed")
    monkeypatch.setattr(adapter, "_query_meta_source_props", unexpected)
    with pytest.raises(ValueError):
        adapter.fetch_source_rows_observed(nodes=[], node_id=None, scope=scope, spec_id=spec_id)


def test_backwards_clock_returns_no_observation(monkeypatch):
    _, fetch = setup(monkeypatch, [])
    times = iter((NOW, NOW - timedelta(seconds=1)))
    monkeypatch.setattr(adapter, "_read_observation_clock", lambda: next(times))
    with pytest.raises(ValueError, match="backwards"):
        fetch()


def test_quality_projection_preserves_raw_invalid_deleted_and_duplicate_rows(monkeypatch):
    original = [
        {"goods_id": 1, "site_id": 1, "goods_name": "", "price": -2, "goods_stock": "invalid",
         "goods_state": 0, "state": "not-an-authority", "category_id": None, "create_time": 0,
         "mobile": "private", "secret": "never-return"},
        {"goods_id": 1, "site_id": 1, "is_delete": 1, "goods_state": 1, "modify_time": 0},
        {"site_id": 1, "price": None},
    ]
    events, fetch = setup(monkeypatch, original, spec_id="niushop.product-quality-observation/v1")
    before = dict(adapter._SOFT_DELETE_COUNTS)
    rows, item = fetch()
    assert rows == [
        {"goods_id": 1, "site_id": 1, "goods_name": "", "price": -2, "goods_stock": "invalid",
         "goods_state": 0, "category_id": None, "create_time": 0},
        original[1], original[2],
    ]
    assert item.cleaning_version == "niushop.product-quality-fields/v1"
    assert (item.fetched_count, item.excluded_count, item.retained_count) == (3, 0, 3)
    assert events == ["connect", "clock", "read", "clock", "close"]
    assert adapter._SOFT_DELETE_COUNTS == before
    assert original[0]["state"] == "not-an-authority"
    item.verify_rows(rows)


@pytest.mark.parametrize("count", [0, 100, 101])
def test_quality_spec_retains_complete_bound_before_any_business_filter(monkeypatch, count):
    _, fetch = setup(monkeypatch, [{"site_id": 1, "is_delete": 1} for _ in range(count)],
        spec_id="niushop.product-quality-observation/v1")
    if count == 101:
        with pytest.raises(ValueError, match="limit"): fetch()
    else:
        rows, item = fetch()
        assert len(rows) == item.retained_count == item.fetched_count == count
        assert item.excluded_count == 0


@pytest.mark.parametrize("row", [{"site_id": 2}, {"site_id": 1, "price": float("nan")}])
def test_quality_spec_never_drops_scope_or_unhashable_values_to_succeed(monkeypatch, row):
    _, fetch = setup(monkeypatch, [row], spec_id="niushop.product-quality-observation/v1")
    with pytest.raises(ValueError): fetch()
