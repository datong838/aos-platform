from copy import deepcopy
from types import SimpleNamespace

import pytest

from aos_api import ec_source_adapter as adapter
from aos_api.configured_source_observation import ConfiguredSourceObservation
from aos_api.db import connect
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.source_configuration_revision import SourceConfigurationRevisionStore
from tests.test_source_configuration_revision import SCOPE, upsert
from tests.test_ec_source_observation import setup


@pytest.mark.parametrize("spec_id", ["niushop.product-observation/v1", "niushop.product-quality-observation/v1"])
def test_configured_read_uses_current_input_and_returns_bound_observation(monkeypatch, spec_id):
    with connect(SCOPE) as conn:
        upsert(conn, "source-1", {"test": True})
        tx = HostTransaction(conn)
        store = SourceConfigurationRevisionStore(tx, SCOPE)
        expected = store.read_current("source-1").ref
        events, _ = setup(monkeypatch, [{"site_id": 1, "goods_id": 1}], expected_private=True)
        def forbid_legacy(*args):
            raise AssertionError("configured path cannot read props on a separate connection")
        monkeypatch.setattr(adapter, "_query_meta_source_props", forbid_legacy)
        node = SimpleNamespace(id="source-node", node_type="source", config={
            "source_id": "source-1", "table": "ns_goods", "site_filter": "site_id=1"})
        rows, bound = adapter.fetch_source_rows_configured_observed(
            nodes=[node], node_id="source-node", scope=SCOPE, transaction=tx,
            expected_configuration_ref=expected, spec_id=spec_id)
        assert bound.source_configuration_ref.model_dump() == expected.model_dump()
        assert bound.observation.source_configuration_ref is None
        assert bound.secret_material_version_known is False and bound.connection_identity_verified is False
        bound.verify_rows(rows)
        assert events == ["connect", "clock", "read", "clock", "close"]
        with pytest.raises(ValueError):
            bound.verify_rows([{"site_id": 1, "goods_id": 2}])
        with pytest.raises(ValueError):
            bound.source_configuration_ref = expected
        with pytest.raises(ValueError):
            bound.source_configuration_ref.resource_id = "other"
        with pytest.raises(ValueError):
            bound.observation.source_id = "other"
        upsert(conn, "source-1", {"test": "changed"})
        before = list(events)
        with pytest.raises(ValueError, match="configuration"):
            adapter.fetch_source_rows_configured_observed(
                nodes=[node], node_id="source-node", scope=SCOPE, transaction=tx,
                expected_configuration_ref=expected, spec_id=spec_id)
        assert events == before
        conn.rollback()


def test_connection_input_repr_omits_properties_and_uses_one_statement():
    from tests.test_source_read_observation_evidence import Connection
    with connect(SCOPE) as conn:
        upsert(conn, "source-1", {"test_private": "never-display"})
        store = SourceConfigurationRevisionStore(HostTransaction(conn), SCOPE)
        item = store.read_connection_input("source-1")
        assert item.props == {"test_private": "never-display"}
        assert "never-display" not in repr(item)
        assert item.revision.ref == store.read_current("source-1").ref
        row = conn.execute("SELECT r.*,s.props AS connection_props FROM public.meta_source s JOIN public.data_source_configuration_revision r ON (r.org_id,r.project_id,r.source_id,r.revision_id)=(s.org_id,s.project_id,s.id,s.configuration_revision) WHERE s.org_id=%s AND s.project_id=%s AND s.id='source-1'", SCOPE.key).fetchone()
        fake = Connection(row)
        assert SourceConfigurationRevisionStore(HostTransaction(fake), SCOPE).read_connection_input("source-1") == item
        assert len(fake.calls) == 1 and "s.props" in fake.calls[0][0]
        conn.rollback()


@pytest.mark.parametrize("change", [{"source_id": "missing"}, {"table": "ns_member"}, {"site_filter": ""}])
def test_missing_configuration_or_unbounded_scope_never_constructs_connector(monkeypatch, change):
    with connect(SCOPE) as conn:
        upsert(conn, "source-1", {"test": True})
        tx = HostTransaction(conn)
        expected = SourceConfigurationRevisionStore(tx, SCOPE).read_current("source-1").ref
        events, _ = setup(monkeypatch, [], expected_private=True)
        config = {"source_id": "source-1", "table": "ns_goods", "site_filter": "site_id=1"}
        config.update(change)
        node = SimpleNamespace(id="source-node", node_type="source", config=config)
        with pytest.raises(ValueError):
            adapter.fetch_source_rows_configured_observed(
                nodes=[node], node_id="source-node", scope=SCOPE, transaction=tx,
                expected_configuration_ref=expected, spec_id="niushop.product-observation/v1")
        assert events == []
        conn.rollback()


@pytest.mark.parametrize("phase", ["construct", "read"])
def test_connector_error_cannot_expose_private_configuration(monkeypatch, phase):
    with connect(SCOPE) as conn:
        upsert(conn, "source-1", {"test": True})
        tx = HostTransaction(conn)
        expected = SourceConfigurationRevisionStore(tx, SCOPE).read_current("source-1").ref
        events, _ = setup(monkeypatch, [], failure=RuntimeError("private-fixture-material"), expected_private=True)
        if phase == "construct":
            def failed_constructor(props, *, reuse_cache):
                assert reuse_cache is False
                raise RuntimeError("private-fixture-material")
            monkeypatch.setattr(adapter, "JdbcConnectorRuntime", failed_constructor)
        node = SimpleNamespace(id="source-node", node_type="source", config={
            "source_id": "source-1", "table": "ns_goods", "site_filter": "site_id=1"})
        with pytest.raises(ValueError) as error:
            adapter.fetch_source_rows_configured_observed(
                nodes=[node], node_id="source-node", scope=SCOPE, transaction=tx,
                expected_configuration_ref=expected, spec_id="niushop.product-observation/v1")
        import traceback
        assert "private-fixture-material" not in "".join(traceback.format_exception(error.value))
        assert events == ([] if phase == "construct" else ["connect", "clock", "read", "close"])
        conn.rollback()
